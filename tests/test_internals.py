"""Tests for the package's own private seams.

Everything a downstream package touches is exercised through the public API
in test_views; these cover the defensive paths behind it — malformed ASGI
messages, a handler that returns no response, a client that disappears
mid-stream — which no well-behaved request reaches. They are deliberately
narrow unit tests: forcing these through the SDK would mean stubbing more of
it than the assertions are worth.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from typing import Any

import anyio
import pytest
from django.test import RequestFactory

from django_stateless_mcp.auth import BearerAuthenticator, _bearer_token
from django_stateless_mcp.context import _DJANGO_REQUEST_KEY, django_request
from django_stateless_mcp.logging import _result_kind
from django_stateless_mcp.permissions import PermittedToolsFilter
from django_stateless_mcp.views import _ASGIResponse, _port, _StatelessBridge, _streamed_response

Handler = Callable[[MutableMapping[str, Any], Any, Any], Awaitable[None]]


@pytest.fixture
def anyio_backend():
    """Run async tests on asyncio only; the SDK targets it."""
    return "asyncio"


class _StubConnection:
    """The one thing BearerAuthenticator reads off an HTTPConnection."""

    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def _connection(headers: dict[str, str]) -> Any:
    """A stand-in HTTPConnection, typed Any so stubs need no starlette internals."""
    return _StubConnection(headers)


class _StubManager:
    """A session manager whose handle_request is supplied per test."""

    def __init__(self, handle: Handler) -> None:
        self._handle = handle

    @contextlib.asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        yield

    async def handle_request(self, scope: MutableMapping[str, Any], receive: Any, send: Any) -> None:
        await self._handle(scope, receive, send)


def _bridge(handle: Handler) -> _StatelessBridge:
    """A bridge whose dispatch runs ``handle`` instead of the SDK's."""

    class StubbedBridge(_StatelessBridge):
        def _new_session_manager(self, *, json_response: bool = True) -> Any:
            return _StubManager(handle)

    return StubbedBridge(server=None, authenticator=None)  # type: ignore[arg-type]


def test_port_is_absent_when_the_server_reports_none():
    """A request whose META carries no SERVER_PORT yields no scope port."""
    request = RequestFactory().post("/mcp/")
    del request.META["SERVER_PORT"]

    assert _port(request) is None


def test_port_reads_the_server_port_from_meta():
    """SERVER_PORT is read from META, which unlike get_host() cannot raise."""
    request = RequestFactory().post("/mcp/", SERVER_PORT="8731")

    assert _port(request) == 8731


@pytest.mark.anyio
async def test_unsupported_asgi_message_is_rejected():
    """An ASGI message type the bridge cannot translate must not pass silently."""
    response = _ASGIResponse()

    with pytest.raises(ValueError, match="http.response.trailers"):
        await response.send({"type": "http.response.trailers"})


def test_a_handler_that_started_no_response_raises():
    """A dispatch that emitted no http.response.start is a bug, not an empty 200."""
    with pytest.raises(RuntimeError, match="no HTTP response"):
        _ASGIResponse().to_django()


@pytest.mark.anyio
async def test_streamed_response_relays_bodies_and_drops_content_length():
    """The stream yields only non-empty bodies, and never echoes Content-Length.

    Django sets Content-Length itself, so echoing the SDK's risks a mismatch;
    keepalive messages carrying no body would show up as empty SSE frames.
    """
    send, receive = anyio.create_memory_object_stream[MutableMapping[str, Any]](4)
    async with send, receive:
        await send.send({"type": "http.response.body", "body": b"frame-one"})
        await send.send({"type": "http.response.body", "body": b""})
        await send.send({"type": "http.response.debug"})
        await send.send({"type": "http.response.body", "body": b"frame-two"})
        send.close()

        dispatch_task = asyncio.create_task(asyncio.sleep(0))
        start = {
            "status": 200,
            "headers": [(b"content-type", b"text/event-stream"), (b"content-length", b"9")],
        }

        response = _streamed_response(start, receive, dispatch_task)
        frames = [chunk async for chunk in response.streaming_content]  # type: ignore[union-attr]

    assert frames == [b"frame-one", b"frame-two"]
    assert response["Content-Type"] == "text/event-stream"
    assert not response.has_header("Content-Length")


@pytest.mark.anyio
async def test_buffered_receive_disconnects_after_the_body():
    """A second read yields http.disconnect, never the body again.

    Replaying the body spins the SDK's SSE disconnect-listeners forever.
    See ADR-0017.
    """
    reads = []

    async def handle(scope, receive, send):
        reads.append(await receive())
        reads.append(await receive())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    request = RequestFactory().post("/mcp/", data=b"{}", content_type="application/json")
    response = await _bridge(handle)._handle_buffered(request, {"type": "http"})

    assert response.status_code == 200
    assert reads[0]["type"] == "http.request"
    assert reads[1] == {"type": "http.disconnect"}


@pytest.mark.anyio
async def test_listen_dispatch_sending_nothing_raises():
    """A listen dispatch that ends without a response is a bug, not a hang."""

    async def handle(scope, receive, send):
        return

    request = RequestFactory().post("/mcp/", data=b"{}", content_type="application/json")

    with pytest.raises(RuntimeError, match="no HTTP response"):
        await _bridge(handle)._handle_listen(request, {"type": "http"})


@pytest.mark.anyio
async def test_listen_cancelled_before_the_first_frame_takes_the_dispatch_down():
    """A client gone before the stream starts must not leave the dispatch running.

    The dispatch is a background task, so cancelling the request without
    cancelling it too would leak a task that outlives the response.
    """
    started = asyncio.Event()

    async def handle(scope, receive, send):
        started.set()
        await asyncio.Event().wait()

    request = RequestFactory().post("/mcp/", data=b"{}", content_type="application/json")
    tasks_before = asyncio.all_tasks()
    listening = asyncio.ensure_future(_bridge(handle)._handle_listen(request, {"type": "http"}))
    await started.wait()
    listening.cancel()

    with pytest.raises(asyncio.CancelledError):
        await listening

    leaked = {task for task in asyncio.all_tasks() - tasks_before if not task.done()} - {listening}
    assert not leaked, leaked


def test_bearer_token_ignores_a_missing_or_foreign_authorization_header():
    """Only a Bearer header yields a token; anything else yields none."""
    assert _bearer_token(_connection({})) is None
    assert _bearer_token(_connection({"authorization": "Basic abc"})) is None
    assert _bearer_token(_connection({"authorization": "Bearer abc"})) == "abc"


@pytest.mark.anyio
async def test_binding_a_user_is_skipped_without_a_django_request():
    """A scope carrying no Django request leaves the resolver unrun.

    The resolver's whole job is setting ``request.user``; with no request to
    set it on there is nothing to do, and reaching for one would raise.
    """
    from django.contrib.auth.models import AnonymousUser

    resolved = []

    async def resolver(token):
        resolved.append(token)
        return AnonymousUser()

    authenticator = BearerAuthenticator(token_verifier=None, user_resolver=resolver)  # type: ignore[arg-type]
    connection = _connection({"authorization": "Bearer abc"})

    await authenticator._bind_django_user({"state": {}}, connection)
    assert resolved == []

    request = RequestFactory().post("/mcp/")
    await authenticator._bind_django_user({"state": {_DJANGO_REQUEST_KEY: request}}, connection)
    assert resolved == ["abc"]
    assert request.user.is_anonymous


def test_django_request_rejects_a_transport_request_without_one():
    """A call that reached a handler off the view path names the cause."""

    class _RequestContext:
        request = object()

    class _Context:
        request_context = _RequestContext()

    with pytest.raises(LookupError, match="did not arrive through mcp_view"):
        django_request(_Context())  # type: ignore[arg-type]


class _TypedResult:
    """A model-shaped result, which names its type on ``result_type``."""

    def __init__(self, result_type: str) -> None:
        self.result_type = result_type


def test_result_kind_reads_a_model_or_an_already_dumped_result():
    """The middleware tier sees a dict as often as a model; both must be named."""
    assert _result_kind(_TypedResult("input_required")) == "input_required"
    assert _result_kind(_TypedResult("completed")) == "completed"
    assert _result_kind({"resultType": "input_required"}) == "input_required"
    assert _result_kind({}) == "completed"


class _StubContext:
    """The two attributes PermittedToolsFilter reads off a request context."""

    def __init__(self, method: str) -> None:
        self.method = method
        self.request = None


class _ToolsResult:
    """A model-shaped handler result, as opposed to an already-dumped dict."""

    def __init__(self, tools: list[Any] | None) -> None:
        self.tools = tools


def _context(method: str) -> Any:
    """A stand-in ServerRequestContext, typed Any so stubs stay this small."""
    return _StubContext(method)


@pytest.mark.parametrize("result", [_ToolsResult(None), {"nextCursor": "abc"}])
@pytest.mark.anyio
async def test_filter_leaves_a_result_without_tools_alone(result):
    """A tools/list result carrying no tools is passed through untouched.

    Both result shapes get the same forgiveness: reading the key off a dict
    used to raise KeyError where the model branch already tolerated the
    attribute being absent.
    """

    async def call_next(ctx):
        return result

    filtered: Any = await PermittedToolsFilter(lambda user, name: False)(_context("tools/list"), call_next)

    assert filtered is result


@pytest.mark.anyio
async def test_filter_rewrites_a_model_shaped_result():
    """Tools are filtered whether the result is a dict or a model."""
    result = _ToolsResult([{"name": "public_ping"}, {"name": "update_author"}])

    async def call_next(ctx):
        return result

    filtered: Any = await PermittedToolsFilter(lambda user, name: name == "public_ping")(
        _context("tools/list"), call_next
    )

    assert [tool["name"] for tool in filtered.tools] == ["public_ping"]
