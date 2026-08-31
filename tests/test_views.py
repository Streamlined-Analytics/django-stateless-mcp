"""Tests for the stateless MCP view."""

from __future__ import annotations

import functools
import json
from typing import Any

import pytest
from django.conf import settings
from django.db import connections
from django.test import Client, RequestFactory

MCP_URL = "/mcp/"
MCP_HEADERS = {"accept": "application/json, text/event-stream"}


@pytest.fixture
def anyio_backend():
    """Run async tests on asyncio only; the SDK targets it."""
    return "asyncio"


def request_body(method: str, params: dict[str, Any] | None = None, request_id: int = 1) -> str:
    """Build a JSON-RPC request body for the given MCP method."""
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return json.dumps(payload)


def post(client: Client, method: str, params: dict[str, Any] | None = None) -> Any:
    return client.post(
        MCP_URL,
        data=request_body(method, params),
        content_type="application/json",
        headers=MCP_HEADERS,
    )


def test_tools_list_returns_registered_tool(client):
    """The endpoint advertises tools without an initialize handshake."""
    response = post(client, "tools/list")

    assert response.status_code == 200
    tools = json.loads(response.content)["result"]["tools"]
    assert "list_books" in {tool["name"] for tool in tools}


def test_tools_call_executes_the_tool(client):
    """A tool call runs and returns its structured result."""
    response = post(client, "tools/call", {"name": "book_slug", "arguments": {"title": "Two Scoops of Django"}})

    assert response.status_code == 200
    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": "two-scoops-of-django"}
    assert result["isError"] is False


def test_response_carries_no_session_identifier(client):
    """No session is established, so nothing needs sticky routing.

    This is the property the package exists to provide: if a session header
    ever appears here, horizontal scaling is silently broken.
    """
    response = post(client, "tools/list")

    assert "Mcp-Session-Id" not in response.headers


def test_view_is_csrf_exempt():
    """CsrfViewMiddleware must not 403 MCP requests.

    The default test client skips CSRF enforcement, which is how this went
    unseen: in any project running the standard middleware, every MCP POST
    got \"403 CSRF cookie not set\" until the view was marked exempt. MCP
    clients hold no CSRF token -- they authenticate by bearer token, not
    ambient cookies, so CSRF does not apply.
    """
    csrf_client = Client(enforce_csrf_checks=True)

    response = post(csrf_client, "tools/list")

    assert response.status_code == 200


def test_get_is_rejected_not_hung(client):
    """GET gets an immediate 405: stateless MCP has no server-push stream.

    0.1.1 routed GET into the SDK's SSE path, whose disconnect listener
    looped forever against the bridge's synthesized ``receive`` -- one
    anonymous GET pegged a worker at 100% CPU permanently.
    """
    response = client.get(MCP_URL, headers=MCP_HEADERS)

    assert response.status_code == 405
    assert response.headers["Allow"] == "POST"


def test_delete_is_rejected(client):
    """DELETE (session termination) is meaningless without sessions."""
    response = client.delete(MCP_URL, headers=MCP_HEADERS)

    assert response.status_code == 405
    assert response.headers["Allow"] == "POST"


@pytest.mark.anyio
async def test_get_is_rejected_under_asgi(async_client):
    """The POST-only guard holds on the native async path too."""
    response = await async_client.get(MCP_URL, headers=MCP_HEADERS)

    assert response.status_code == 405


@pytest.fixture
def atomic_requests():
    """Turn on per-request transactions on every alias, as consumer projects do.

    ``override_settings(DATABASES=...)`` does not reach ``connections.settings``,
    so this mutates the live settings dicts the way Django's own handler tests
    do, restoring the originals afterwards.
    """
    originals = {alias: settings_dict["ATOMIC_REQUESTS"] for alias, settings_dict in connections.settings.items()}
    for settings_dict in connections.settings.values():
        settings_dict["ATOMIC_REQUESTS"] = True
    yield
    for alias, settings_dict in connections.settings.items():
        settings_dict["ATOMIC_REQUESTS"] = originals[alias]


def test_view_serves_under_atomic_requests(client, atomic_requests):
    """``ATOMIC_REQUESTS = True`` must not break the endpoint.

    Django's ``make_view_atomic`` refuses to serve an async view on any alias
    running per-request transactions, so without the ``non_atomic_requests``
    exemption every request raised ``RuntimeError`` before dispatch -- unit
    tests against the server object never crossed the handler and stayed
    green while production 500d (issue #45).
    """
    response = post(client, "tools/list")

    assert response.status_code == 200


@pytest.fixture
def atomic_requests_on_secondary_alias():
    """Turn on per-request transactions for the non-default alias only.

    Mirrors a real consumer running a second database with its own
    ``ATOMIC_REQUESTS`` value. This is exactly the case a bare
    ``non_atomic_requests`` decorator (which exempts only ``default``)
    would miss -- ``make_view_atomic`` checks every alias.
    """
    connections.settings["apikeys"]["ATOMIC_REQUESTS"] = True
    yield
    connections.settings["apikeys"]["ATOMIC_REQUESTS"] = False


def test_view_serves_with_atomic_requests_on_secondary_alias(client, atomic_requests_on_secondary_alias):
    """The exemption must cover every configured alias, not just default."""
    response = post(client, "tools/list")

    assert response.status_code == 200


@pytest.mark.anyio
async def test_view_serves_under_atomic_requests_under_asgi(async_client, atomic_requests):
    """``get_response_async`` carries the same refusal; the exemption must hold there too."""
    response = await async_client.post(
        MCP_URL,
        data=request_body("tools/list"),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    assert response.status_code == 200


def test_unknown_tool_reports_an_error(client):
    """An unknown tool is reported in-band rather than crashing the view."""
    response = post(client, "tools/call", {"name": "nope", "arguments": {}})

    assert response.status_code == 200
    payload = json.loads(response.content)
    assert "error" in payload or payload["result"]["isError"] is True


@pytest.mark.anyio
async def test_tools_call_under_asgi(async_client):
    """The same view serves ASGI, where it runs without a wrapping event loop."""
    response = await async_client.post(
        MCP_URL,
        data=request_body("tools/call", {"name": "book_slug", "arguments": {"title": "Stateless by Design"}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    assert response.status_code == 200
    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": "stateless-by-design"}


@pytest.mark.anyio
async def test_consecutive_requests_share_no_state(async_client):
    """Two requests are served independently, as separate workers would."""
    first = await async_client.post(
        MCP_URL,
        data=request_body("tools/call", {"name": "book_slug", "arguments": {"title": "Django"}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )
    second = await async_client.post(
        MCP_URL,
        data=request_body("tools/list", request_id=2),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    assert json.loads(first.content)["result"]["structuredContent"] == {"result": "django"}
    assert json.loads(second.content)["result"]["tools"][0]["name"] == "list_books"


def test_autodiscovery_imported_the_app_mcp_module(client):
    """Tools registered in an app's mcp.py are served without explicit import.

    Nothing in the test suite or URLconf imports example.mcp, so book_slug can
    only be present if the app config's autodiscovery imported it.
    """
    response = post(client, "tools/list")

    tools = {tool["name"] for tool in json.loads(response.content)["result"]["tools"]}
    assert {"list_books", "book_slug"} <= tools


def test_autodiscovered_tool_is_callable(client):
    """An autodiscovered tool executes like any directly registered one."""
    response = post(
        client, "tools/call", {"name": "book_slug", "arguments": {"title": "The Definitive Guide to Django"}}
    )

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": "the-definitive-guide-to-django"}


def test_broken_app_mcp_module_raises_at_startup(settings):
    """A failing mcp.py aborts startup instead of being silently skipped.

    The import error inside the module is a ModuleNotFoundError — the same
    class autodiscovery suppresses for apps with no mcp module at all — so
    this pins the sharp edge of the guarantee: only absence is forgiven.
    """
    from django.apps import apps

    try:
        with pytest.raises(ModuleNotFoundError, match="does_not_exist_xyz"):
            apps.set_installed_apps([*settings.INSTALLED_APPS, "tests.broken_mcp_app"])
    finally:
        apps.unset_installed_apps()


def test_tool_reads_the_django_request(client):
    """A tool sees the actual Django request via django_request(ctx)."""
    response = post(client, "tools/call", {"name": "request_path", "arguments": {}})

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": "/mcp/"}


@pytest.mark.django_db(transaction=True)
def test_sync_tool_uses_the_orm(client):
    """ORM access works inside a sync tool.

    transaction=True commits the fixture user, because the tool's query runs
    on a different connection: the SDK executes sync tools in a worker
    thread, and an uncommitted row would be invisible to it.
    """
    from example.models import Author, Book

    author = Author.objects.create(name="Adrian Holovaty")
    Book.objects.create(title="The Definitive Guide to Django", author=author)
    response = post(client, "tools/call", {"name": "count_books", "arguments": {}})

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": 1}


def test_django_request_outside_the_view_raises():
    """Calling the accessor off the request path fails loudly, not with None."""
    from mcp.server.mcpserver import Context

    from django_stateless_mcp import django_request

    with pytest.raises(LookupError):
        django_request(Context())


AUTH_URL = "/auth-mcp/"


def post_auth(client: Client, url: str, token: str | None = None) -> Any:
    """POST a tools/call for token_client with an optional bearer token."""
    headers = dict(MCP_HEADERS)
    if token is not None:
        headers["authorization"] = f"Bearer {token}"
    return client.post(
        url,
        data=request_body("tools/call", {"name": "token_client", "arguments": {}}),
        content_type="application/json",
        headers=headers,
    )


def test_missing_token_gets_401_with_challenge(client):
    """No bearer token means 401 and a WWW-Authenticate challenge."""
    response = post_auth(client, AUTH_URL)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer ")
    assert json.loads(response.content)["error"] == "invalid_token"


def test_invalid_token_gets_401(client):
    """A token the verifier rejects is refused before dispatch."""
    response = post_auth(client, AUTH_URL, token="wrong")

    assert response.status_code == 401


def test_valid_token_reaches_the_tool(client):
    """A verified token dispatches, and the SDK's get_access_token sees it."""
    response = post_auth(client, AUTH_URL, token="good-token")

    assert response.status_code == 200
    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": "test-client"}


@pytest.mark.anyio
async def test_missing_token_gets_401_under_asgi(async_client):
    """Bearer enforcement holds on the native async path consumers deploy."""
    response = await async_client.post(
        AUTH_URL,
        data=request_body("tools/call", {"name": "token_client", "arguments": {}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer ")


@pytest.mark.anyio
async def test_valid_token_reaches_the_tool_under_asgi(async_client):
    """A verified token dispatches under ASGI, not just the WSGI test path."""
    response = await async_client.post(
        AUTH_URL,
        data=request_body("tools/call", {"name": "token_client", "arguments": {}}),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
    )

    assert response.status_code == 200
    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": "test-client"}


def test_missing_scope_gets_403(client):
    """A valid token without a required scope is refused with 403."""
    response = post_auth(client, "/admin-mcp/", token="good-token")

    assert response.status_code == 403
    assert json.loads(response.content)["error"] == "insufficient_scope"


def test_unauthenticated_endpoint_stays_open(client):
    """The verifier-less endpoint still serves without credentials."""
    response = post_auth(client, MCP_URL)

    assert response.status_code == 200
    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": "anonymous"}


ELICIT_TOOL = "test_input_required_result_elicitation"
STATEFUL_TOOL = "test_input_required_result_request_state"

ELICITATION_ONLY: dict[str, Any] = {"elicitation": {}}

STATELESS_META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": ELICITATION_ONLY,
}


def stateless_meta(capabilities: dict[str, Any]) -> dict[str, Any]:
    """The _meta envelope declaring the protocol version and client capabilities."""
    return {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": capabilities,
    }


def post_stateless(
    client: Client,
    url: str,
    tool: str,
    params: dict[str, Any],
    *,
    capabilities: dict[str, Any] | None = None,
    method: str = "tools/call",
) -> Any:
    """POST a spec-2026-07-28 request: routing headers plus _meta envelope."""
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            "name": tool,
            **params,
            "_meta": stateless_meta(ELICITATION_ONLY if capabilities is None else capabilities),
        },
    }
    headers = {
        **MCP_HEADERS,
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": method,
        "mcp-name": tool,
    }
    response = client.post(url, data=json.dumps(body), content_type="application/json", headers=headers)
    return json.loads(response.content)


def accept(content: dict[str, Any]) -> dict[str, Any]:
    """Build the client's accepted-elicitation answer."""
    return {"action": "accept", "content": content}


def test_elicitation_across_two_separate_requests(client):
    """The flagship flow: elicit in one request, resume in another.

    No connection is held and nothing is remembered between the posts; the
    second request carries everything needed to complete the call.
    """
    round_one = post_stateless(client, MCP_URL, ELICIT_TOOL, {"arguments": {}})["result"]

    assert round_one["resultType"] == "input_required"
    assert "user_name" in round_one["inputRequests"]

    round_two = post_stateless(
        client,
        MCP_URL,
        ELICIT_TOOL,
        {
            "arguments": {},
            "inputResponses": {"user_name": accept({"name": "Alice"})},
        },
    )["result"]

    assert round_two["content"][0]["text"] == "Hello, Alice!"


def test_retry_resumes_on_a_different_server_instance(client):
    """The thesis: any instance can serve the retry, including its state.

    Round one runs on one MCPServer; round two on a separate instance
    sharing only the Django settings, as two workers in a fleet would. The
    encrypted requestState minted by the first instance decrypts on the
    second because request_state_security() keys from SECRET_KEY rather
    than the SDK's default per-process random key.
    """
    round_one = post_stateless(client, MCP_URL, STATEFUL_TOOL, {"arguments": {}})["result"]

    assert round_one["resultType"] == "input_required"
    state = round_one["requestState"]

    round_two = post_stateless(
        client,
        "/mcp-b/",
        STATEFUL_TOOL,
        {
            "arguments": {},
            "inputResponses": {"confirm": accept({"ok": True})},
            "requestState": state,
        },
    )["result"]

    assert round_two["content"][0]["text"] == "state-ok: confirmation received"


def test_tampered_request_state_is_rejected(client):
    """A modified requestState fails closed with a protocol error."""
    round_one = post_stateless(client, MCP_URL, STATEFUL_TOOL, {"arguments": {}})["result"]
    state = round_one["requestState"]

    tampered = state[:-4] + ("AAAA" if not state.endswith("AAAA") else "BBBB")
    payload = post_stateless(
        client,
        MCP_URL,
        STATEFUL_TOOL,
        {
            "arguments": {},
            "inputResponses": {"confirm": accept({"ok": True})},
            "requestState": tampered,
        },
    )

    assert payload["error"]["data"]["reason"] == "invalid_request_state"


def test_dispatch_logs_a_completed_event(client):
    """A tool call emits mcp.request.completed with queryable kwargs."""
    from structlog.testing import capture_logs

    with capture_logs() as captured:
        post(client, "tools/call", {"name": "book_slug", "arguments": {"title": "Django"}})

    events = [e for e in captured if e["event"] == "mcp.request.completed"]
    assert events, captured
    event = events[0]
    assert event["method"] == "tools/call"
    assert event["tool_name"] == "book_slug"
    assert isinstance(event["duration_ms"], float)
    assert event["exit"] == "completed"


def test_elicitation_pause_logs_input_required_exit(client):
    """An elicitation pause is distinguishable from completion in the logs."""
    from structlog.testing import capture_logs

    with capture_logs() as captured:
        post_stateless(client, MCP_URL, ELICIT_TOOL, {"arguments": {}})

    events = [e for e in captured if e["event"] == "mcp.request.completed"]
    assert events and events[0]["exit"] == "input_required"


def test_failed_dispatch_logs_and_reraises(client):
    """A protocol failure logs mcp.request.failed and still reaches the wire."""
    from structlog.testing import capture_logs

    with capture_logs() as captured:
        response = post_stateless(client, MCP_URL, "test_missing_capability", {"arguments": {}})

    assert "error" in response
    events = [e for e in captured if e["event"] == "mcp.request.failed"]
    assert events and events[0]["error_type"] == "MCPError"


USER_URL = "/user-mcp/"


@pytest.mark.django_db(transaction=True)
def test_tool_reads_authenticated_django_user(client):
    """With a user_resolver, django_request(ctx).user is the Django user."""
    from django.contrib.auth.models import User

    User.objects.create_user("mcp-test-user")
    response = client.post(
        USER_URL,
        data=request_body("tools/call", {"name": "current_username", "arguments": {}}),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
    )

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": "mcp-test-user"}


@pytest.mark.django_db(transaction=True)
def test_permission_locked_tool_denies_user_without_perm(client):
    """A tool gating on user.has_perm refuses a user who lacks it."""
    from django.contrib.auth.models import User

    from example.models import Author

    User.objects.create_user("mcp-test-user")
    author = Author.objects.create(name="Sally Author")
    response = client.post(
        USER_URL,
        data=request_body("tools/call", {"name": "update_author", "arguments": {"author_id": author.pk, "name": "X"}}),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
    )

    result = json.loads(response.content)["result"]
    assert result["isError"] is True
    author.refresh_from_db()
    assert author.name == "Sally Author"


@pytest.mark.django_db(transaction=True)
def test_permission_locked_tool_allows_user_with_perm(client):
    """The same tool runs for a user granted the permission."""
    from django.contrib.auth.models import Permission, User

    from example.models import Author

    user = User.objects.create_user("mcp-test-user")
    user.user_permissions.add(Permission.objects.get(codename="can_update_authors"))
    author = Author.objects.create(name="Sally Author")
    response = client.post(
        USER_URL,
        data=request_body(
            "tools/call", {"name": "update_author", "arguments": {"author_id": author.pk, "name": "Sally Renamed"}}
        ),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
    )

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": f"author {author.pk} renamed to Sally Renamed"}
    author.refresh_from_db()
    assert author.name == "Sally Renamed"


FILTERED_URL = "/filtered-mcp/"


def _list_names(response: Any) -> set[str]:
    return {t["name"] for t in json.loads(response.content)["result"]["tools"]}


@pytest.mark.django_db(transaction=True)
def test_hidden_tool_absent_from_list_without_perm(client):
    """A user lacking the perm never sees the tool in tools/list."""
    from django.contrib.auth.models import User

    User.objects.create_user("mcp-test-user")
    response = client.post(
        FILTERED_URL,
        data=request_body("tools/list"),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
    )

    names = _list_names(response)
    assert "public_ping" in names
    assert "update_author" not in names


@pytest.mark.django_db(transaction=True)
def test_hidden_tool_present_in_list_with_perm(client):
    """A user with the perm sees the tool."""
    from django.contrib.auth.models import Permission, User

    user = User.objects.create_user("mcp-test-user")
    user.user_permissions.add(Permission.objects.get(codename="can_update_authors"))
    response = client.post(
        FILTERED_URL,
        data=request_body("tools/list"),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
    )

    assert "update_author" in _list_names(response)


@pytest.mark.django_db(transaction=True)
def test_hidden_tool_still_execution_gated(client):
    """Visibility is not the boundary: a hidden tool called by name is refused.

    The client never saw update_author in tools/list, but nothing stops it
    calling the name directly. The tool's own permission check is what makes
    that safe -- filtering alone would be security theatre.
    """
    from django.contrib.auth.models import User

    User.objects.create_user("mcp-test-user")
    response = client.post(
        FILTERED_URL,
        data=request_body("tools/call", {"name": "update_author", "arguments": {"author_id": 1, "name": "X"}}),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
    )

    assert json.loads(response.content)["result"]["isError"] is True


@pytest.mark.django_db(transaction=True)
def test_list_books_returns_seeded_titles(client):
    """list_books reads real rows through the ORM, author included."""
    from example.models import Author, Book

    author = Author.objects.create(name="Audrey Roy Greenfeld")
    Book.objects.create(title="Two Scoops of Django", author=author)
    response = post(client, "tools/call", {"name": "list_books", "arguments": {}})

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": ["Two Scoops of Django (Audrey Roy Greenfeld)"]}


@pytest.mark.django_db(transaction=True)
def test_slow_book_report_returns_books(client, monkeypatch):
    """The slow tool returns the book list; tests never pay the 30 s sleep."""
    from example import mcp_server
    from example.models import Author, Book

    monkeypatch.setattr(mcp_server, "SLOW_BOOK_REPORT_SECONDS", 0.0)
    author = Author.objects.create(name="Sally Author")
    Book.objects.create(title="Stateless by Design", author=author)
    response = post(client, "tools/call", {"name": "slow_book_report", "arguments": {}})

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": ["Stateless by Design (Sally Author)"]}


def test_user_resolver_without_verifier_is_rejected():
    """Misconfiguring auth fails loudly rather than leaving the endpoint open."""
    from django_stateless_mcp import mcp_view
    from example.mcp_server import resolve_stub_user, server

    with pytest.raises(ValueError, match="require a token_verifier"):
        mcp_view(server, user_resolver=resolve_stub_user)


def test_view_stays_a_coroutine_function():
    """The ATOMIC_REQUESTS exemption must not demote the view to a sync one.

    Django 6.2 made ``non_atomic_requests()`` return a new wrapper -- a plain
    ``def`` -- instead of mutating the view in place, so an unmarked result
    would have Django run this async view through the sync path. See ADR-0039.
    """
    from asgiref.sync import iscoroutinefunction

    from django_stateless_mcp import mcp_view
    from example.mcp_server import server

    assert iscoroutinefunction(mcp_view(server))


@pytest.mark.anyio
async def test_view_stays_async_behind_a_sync_non_atomic_wrapper(monkeypatch):
    """A plain-def ATOMIC_REQUESTS wrapper must not demote the view to sync.

    Django 6.2 rewrote ``non_atomic_requests`` to return a ``def`` rather
    than passing the coroutine function through, which silently made the view
    look synchronous — Django would then run it in a thread and never await
    it. See ADR-0039.
    """
    from asgiref.sync import iscoroutinefunction
    from django.db import transaction

    from django_stateless_mcp import mcp_view
    from example.mcp_server import server

    def sync_non_atomic_requests(using=None):
        def decorator(view):
            @functools.wraps(view)
            def wrapper(*args, **kwargs):
                return view(*args, **kwargs)

            return wrapper

        return decorator

    monkeypatch.setattr(transaction, "non_atomic_requests", sync_non_atomic_requests)
    view = mcp_view(server)

    assert iscoroutinefunction(view)

    request = RequestFactory().post(
        "/mcp/",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        content_type="application/json",
        headers={"accept": "application/json, text/event-stream"},
    )
    response: Any = await view(request)

    assert response.status_code == 200
    assert json.loads(response.content)["result"] == {}


def test_required_scopes_without_verifier_is_rejected():
    """Scopes without a verifier are equally meaningless and rejected."""
    from django_stateless_mcp import mcp_view
    from example.mcp_server import server

    with pytest.raises(ValueError, match="require a token_verifier"):
        mcp_view(server, required_scopes=["mcp:read"])


def test_unresolved_user_falls_back_to_anonymous(client):
    """A verified token whose resolver yields no user gives an anonymous user.

    request.user is always present when a resolver is configured, so a
    permission check fails closed rather than raising AttributeError.
    """
    response = client.post(
        "/nouser-mcp/",
        data=request_body("tools/call", {"name": "current_username", "arguments": {}}),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
    )

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": ""}


@pytest.mark.django_db(transaction=True)
def test_visible_tool_runs_for_a_permitted_user(client):
    """The filtered server's locked tool executes once the user holds the perm."""
    from django.contrib.auth.models import Permission, User

    from example.models import Author

    user = User.objects.create_user("mcp-test-user")
    user.user_permissions.add(Permission.objects.get(codename="can_update_authors"))
    author = Author.objects.create(name="Sally Author")
    response = client.post(
        FILTERED_URL,
        data=request_body(
            "tools/call", {"name": "update_author", "arguments": {"author_id": author.pk, "name": "Sally Renamed"}}
        ),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
    )

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": f"author {author.pk} renamed to Sally Renamed"}
    author.refresh_from_db()
    assert author.name == "Sally Renamed"


@pytest.mark.django_db(transaction=True)
def test_public_tool_runs_on_the_filtered_server(client):
    """A tool everyone may see is callable by everyone."""
    from django.contrib.auth.models import User

    User.objects.create_user("mcp-test-user")
    response = client.post(
        FILTERED_URL,
        data=request_body("tools/call", {"name": "public_ping", "arguments": {}}),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
    )

    assert json.loads(response.content)["result"]["structuredContent"] == {"result": "pong"}


@pytest.mark.django_db(transaction=True)
def test_renaming_an_unknown_author_is_an_error(client):
    """A permitted user naming a row that does not exist gets a tool error.

    Only ``isError`` is asserted: how much of a tool's exception reaches the
    client is the SDK's decision, and it has changed -- git main wraps the
    ValueError in ``UnexpectedToolError`` and redacts the message.
    """
    from django.contrib.auth.models import Permission, User

    from example.models import Author

    user = User.objects.create_user("mcp-test-user")
    user.user_permissions.add(Permission.objects.get(codename="can_update_authors"))
    author = Author.objects.create(name="Sally Author")

    def rename(author_id: int) -> Any:
        return json.loads(
            client.post(
                USER_URL,
                data=request_body(
                    "tools/call", {"name": "update_author", "arguments": {"author_id": author_id, "name": "X"}}
                ),
                content_type="application/json",
                headers={**MCP_HEADERS, "authorization": "Bearer good-token"},
            ).content
        )["result"]

    assert rename(9999)["isError"] is True
    assert rename(author.pk)["isError"] is False


def test_filter_treats_a_request_without_a_user_as_anonymous(client):
    """Without auth middleware or a resolver the request carries no user at all.

    ``PermittedToolsFilter`` promises the user is anonymous when no
    ``user_resolver`` is configured; a middleware stack without
    ``AuthenticationMiddleware`` is the shape where ``request.user`` is not
    merely anonymous but absent, and the filter must still fail closed.
    """
    from django.test import override_settings

    unauthenticated = [m for m in settings.MIDDLEWARE if "AuthenticationMiddleware" not in m]
    with override_settings(MIDDLEWARE=unauthenticated):
        response = client.post(
            "/filtered-open-mcp/",
            data=request_body("tools/list"),
            content_type="application/json",
            headers=MCP_HEADERS,
        )

    names = _list_names(response)
    assert "public_ping" in names
    assert "update_author" not in names
