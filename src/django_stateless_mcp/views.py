"""Serve an MCP server from Django over stateless streamable HTTP."""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any

import anyio
import anyio.to_thread
from django.core.handlers.asgi import ASGIRequest
from django.db import close_old_connections
from django.http import HttpResponse, HttpResponseBase, HttpResponseNotAllowed, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from mcp.server.transport_security import TransportSecuritySettings

from django_stateless_mcp.auth import BearerAuthenticator, access_token_context
from django_stateless_mcp.context import _DJANGO_REQUEST_KEY

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Coroutine, Sequence

    from anyio.streams.memory import MemoryObjectReceiveStream
    from django.http import HttpRequest
    from mcp.server.auth.provider import TokenVerifier
    from mcp.server.mcpserver import MCPServer
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    from django_stateless_mcp.auth import UserResolver

__all__ = ["mcp_view"]

# Django sets Content-Length itself; echoing the SDK's risks a mismatch.
_SKIPPED_RESPONSE_HEADERS = frozenset({b"content-length"})

# The one method whose response is a live stream, routed by header so the body is never parsed. See ADR-0020.
_LISTEN_METHOD = "subscriptions/listen"
_MCP_METHOD_HEADER = "mcp-method"
_STREAM_BUFFER_MESSAGES = 64

# Django's ALLOWED_HOSTS owns host validation; a second allowlist here would be
# a conflicting source of truth over a scope we synthesise. See ADR-0007.
_TRANSPORT_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)


def _listen_needs_asgi() -> HttpResponse:
    """Refuse a subscription stream on a deployment that cannot hold one.

    Under WSGI a live stream would pin a worker for its whole lifetime --
    the per-flow resource tax this package exists to remove -- and Django
    cannot iterate the bridge's async stream outside the request's event
    loop there. Deploy under ASGI for subscription streams. See ADR-0020.
    """
    payload = {
        "error": "unsupported_deployment",
        "error_description": "subscriptions/listen streams require an ASGI deployment.",
    }
    return HttpResponse(json.dumps(payload), status=501, content_type="application/json")


def _port(request: HttpRequest) -> int | None:
    """Read the server port from META, which unlike get_host() cannot raise."""
    raw_port = request.META.get("SERVER_PORT")
    if not raw_port:
        return None
    return int(raw_port)


class _ASGIResponse:
    """Accumulates the ASGI messages the SDK emits for one request."""

    __slots__ = ("body", "headers", "status")

    def __init__(self) -> None:
        self.status: int | None = None
        self.headers: list[tuple[bytes, bytes]] = []
        self.body = bytearray()

    async def send(self, message: MutableMapping[str, Any]) -> None:
        """Record one ASGI ``send`` message from the SDK's handler."""
        message_type = message["type"]
        if message_type == "http.response.start":
            self.status = message["status"]
            self.headers = list(message.get("headers", []))
            return
        if message_type == "http.response.body":
            self.body.extend(message.get("body", b""))
            return
        raise ValueError(f"Unsupported ASGI message type: {message_type!r}")

    def to_django(self) -> HttpResponse:
        """Build the Django response, raising if the handler started none."""
        if self.status is None:
            raise RuntimeError("The MCP handler returned no HTTP response.")

        response = HttpResponse(bytes(self.body), status=self.status)
        for name, value in self.headers:
            if name.lower() in _SKIPPED_RESPONSE_HEADERS:
                continue
            response[name.decode("latin-1")] = value.decode("latin-1")
        return response


class _ListenStreamResponse(StreamingHttpResponse):
    """A streamed listen response that cancels its dispatch when closed.

    The generator's ``finally`` covers a stream that was consumed -- but a
    client that disconnects before the first frame leaves the generator
    unstarted, and an unstarted generator's ``finally`` never runs. Django
    closes every response either way, so the ``close`` hook is what
    guarantees the dispatch task cannot leak.
    """

    def __init__(self, streaming_content: AsyncIterator[bytes], status: int, dispatch_task: asyncio.Task[None]) -> None:
        super().__init__(streaming_content, status=status)
        self._dispatch_task = dispatch_task

    def close(self) -> None:
        """Cancel the dispatch (a no-op if it already finished) and close."""
        self._dispatch_task.cancel()
        super().close()


def _streamed_response(
    start: MutableMapping[str, Any],
    messages: MemoryObjectReceiveStream[MutableMapping[str, Any]],
    dispatch_task: asyncio.Task[None],
) -> StreamingHttpResponse:
    """Relay a live dispatch's ASGI body messages as a streaming response.

    Closing the response -- Django does so when the client disconnects --
    cancels the dispatch, which is the SDK's documented end-of-stream signal.
    """

    async def stream_body() -> AsyncIterator[bytes]:
        try:
            async for message in messages:
                if message["type"] == "http.response.body" and message.get("body"):
                    yield bytes(message["body"])
        finally:
            dispatch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await dispatch_task

    response = _ListenStreamResponse(stream_body(), start["status"], dispatch_task)
    for name, value in start.get("headers", []):
        if name.lower() in _SKIPPED_RESPONSE_HEADERS:
            continue
        response[name.decode("latin-1")] = value.decode("latin-1")
    return response


class _StatelessBridge:
    """Runs one Django request through the SDK's ASGI handler.

    A session manager's ``run()`` may be entered only once, and under WSGI each
    request gets a fresh event loop, so no task group can span requests. Both
    facts point the same way: build a manager per request and discard it. That
    is also what statelessness means here -- nothing survives the exchange.
    """

    __slots__ = ("_authenticator", "_construction_lock", "_server")

    def __init__(self, server: MCPServer, authenticator: BearerAuthenticator | None) -> None:
        self._server = server
        self._authenticator = authenticator
        self._construction_lock = threading.Lock()

    async def handle(self, request: HttpRequest) -> HttpResponseBase:
        """Dispatch ``request`` to the SDK and return its response.

        Only POST is served: a stateless exchange is one request and one
        response, so the transport's GET/DELETE session machinery (the GET
        listen stream, session termination) has nothing to attach to here.
        The one streamed exchange -- ``subscriptions/listen``, whose POST
        response is itself the stream (SEP-2575) -- is routed by the spec's
        required ``mcp-method`` header. See ADR-0020.
        """
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        scope = self._build_scope(request)
        if self._authenticator is not None:
            challenge = await self._authenticator.authenticate(scope)
            if challenge is not None:
                return challenge

        if request.headers.get(_MCP_METHOD_HEADER, "").strip().lower() == _LISTEN_METHOD:
            if not isinstance(request, ASGIRequest):
                return _listen_needs_asgi()
            return await self._handle_listen(request, scope)
        return await self._handle_buffered(request, scope)

    async def _handle_buffered(self, request: HttpRequest, scope: MutableMapping[str, Any]) -> HttpResponse:
        """Run one complete exchange and return the whole response at once."""
        body = request.body
        response = _ASGIResponse()
        body_delivered = False

        async def receive() -> MutableMapping[str, Any]:
            # Body once, then disconnect -- a repeated body spins SSE disconnect-listeners forever. See ADR-0017.
            nonlocal body_delivered
            if body_delivered:
                return {"type": "http.disconnect"}
            body_delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        session_manager = self._new_session_manager()
        try:
            with access_token_context(scope):
                async with session_manager.run():
                    await session_manager.handle_request(scope, receive, response.send)
        finally:
            # Django's request_finished never reaches anyio's tool threads; recycle there. See ADR-0021.
            await anyio.to_thread.run_sync(close_old_connections)
        return response.to_django()

    async def _handle_listen(self, request: HttpRequest, scope: MutableMapping[str, Any]) -> StreamingHttpResponse:
        """Serve ``subscriptions/listen``: the response is a live SSE stream.

        The SDK's handler streams until the client goes away, so the dispatch
        cannot be buffered: it runs as a background task that owns the whole
        session-manager lifecycle (anyio task groups must enter and exit in
        one task), while the returned ``StreamingHttpResponse`` relays its
        ASGI messages. Closing the response -- Django does so when the client
        disconnects -- cancels the dispatch, which is the SDK's documented
        end-of-stream signal.
        """
        body = request.body
        body_delivered = False
        parked = asyncio.Event()

        async def receive() -> MutableMapping[str, Any]:
            # Body once, then park -- the stream ends by cancellation, never a synthesized disconnect. See ADR-0020.
            nonlocal body_delivered
            if body_delivered:
                await parked.wait()
            body_delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        message_send, message_receive = anyio.create_memory_object_stream[MutableMapping[str, Any]](
            _STREAM_BUFFER_MESSAGES
        )

        async def forward(message: MutableMapping[str, Any]) -> None:
            await message_send.send(message)

        session_manager = self._new_session_manager(json_response=False)

        async def dispatch() -> None:
            try:
                with access_token_context(scope):
                    async with session_manager.run():
                        await session_manager.handle_request(scope, receive, forward)
            finally:
                message_send.close()

        dispatch_task = asyncio.create_task(dispatch())

        try:
            start = await message_receive.receive()
        except anyio.EndOfStream:
            await dispatch_task
            raise RuntimeError("The MCP handler returned no HTTP response.") from None
        except BaseException:
            # Cancelled while waiting (client already gone): take the dispatch down or it outlives the request.
            dispatch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await dispatch_task
            raise

        return _streamed_response(start, message_receive, dispatch_task)

    def _new_session_manager(self, *, json_response: bool = True) -> StreamableHTTPSessionManager:
        """Build a fresh session manager for this request.

        ``streamable_http_app()`` both constructs the manager and stores it on
        the shared server, so the two steps are locked together: without the
        lock, concurrent requests could each read the other's manager.
        """
        with self._construction_lock:
            self._server.streamable_http_app(
                stateless_http=True,
                json_response=json_response,
                transport_security=_TRANSPORT_SECURITY,
            )
            return self._server.session_manager

    def _build_scope(self, request: HttpRequest) -> MutableMapping[str, Any]:
        return {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": request.method,
            "scheme": request.scheme,
            "path": request.path,
            "raw_path": request.path.encode("utf-8"),
            "query_string": request.META.get("QUERY_STRING", "").encode("latin-1"),
            "root_path": "",
            "headers": [
                (name.lower().encode("latin-1"), value.encode("latin-1")) for name, value in request.headers.items()
            ],
            "client": (request.META.get("REMOTE_ADDR", ""), 0),
            "server": (request.META.get("SERVER_NAME", ""), _port(request)),
            # The transport carries this to django_request(); no global state.
            "state": {_DJANGO_REQUEST_KEY: request},
        }


def mcp_view(
    server: MCPServer,
    *,
    token_verifier: TokenVerifier | None = None,
    required_scopes: Sequence[str] = (),
    user_resolver: UserResolver | None = None,
) -> Callable[[HttpRequest], Coroutine[Any, Any, HttpResponseBase]]:
    """Return a Django view serving ``server`` over stateless streamable HTTP.

    Mount the returned view in a URLconf::

        from django_stateless_mcp import mcp_view

        urlpatterns = [path("mcp/", mcp_view(server))]

    Pass a ``token_verifier`` (the SDK's ``TokenVerifier`` protocol) to require
    OAuth bearer authentication: requests are verified before dispatch, missing
    or invalid tokens get a 401 with a ``WWW-Authenticate`` challenge, and any
    ``required_scopes`` the token lacks get a 403. Without a verifier the
    endpoint is open, and protecting it is the project's responsibility.

    Pass a ``user_resolver`` -- an async ``(token) -> user`` -- to set
    ``request.user`` from the verified token, so tools can permission-check with
    ``django_request(ctx).user.has_perm(...)``. Requires ``token_verifier``.

    The view serves POST only -- the entire stateless exchange -- and answers
    anything else with ``405 Method Not Allowed``. The transport's GET listen
    stream and DELETE session termination presuppose a session, which is
    exactly what this view does not have.

    The view is **CSRF-exempt**, or ``CsrfViewMiddleware`` would 403 every MCP
    request. CSRF forges the browser's ambient cookie credentials; MCP clients
    authenticate with a bearer token an attacker's page cannot set, and the
    view grants nothing based on session cookies. If you put cookie-based
    authentication in front of an MCP endpoint, that protection is yours to
    provide.

    The view is asynchronous, so it runs natively under ASGI. Django starts an
    event loop per request under WSGI, so one view serves both deployments.

    Raises ``ValueError`` if ``user_resolver`` or ``required_scopes`` is given
    without a ``token_verifier`` -- both are meaningless without authentication,
    and silently ignoring them would leave the endpoint unexpectedly open.
    """
    auth_features_requested = user_resolver is not None or bool(required_scopes)
    if token_verifier is None and auth_features_requested:
        raise ValueError(
            "user_resolver and required_scopes require a token_verifier; "
            "without one the endpoint is unauthenticated and they are ignored."
        )
    authenticator = (
        BearerAuthenticator(token_verifier, required_scopes, user_resolver) if token_verifier is not None else None
    )
    bridge = _StatelessBridge(server, authenticator)

    async def view(request: HttpRequest) -> HttpResponseBase:
        return await bridge.handle(request)

    return csrf_exempt(view)
