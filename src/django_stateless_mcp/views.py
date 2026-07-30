"""Serve an MCP server from Django over stateless streamable HTTP."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from django.http import HttpResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from mcp.server.transport_security import TransportSecuritySettings

from django_stateless_mcp.auth import BearerAuthenticator, access_token_context
from django_stateless_mcp.context import _DJANGO_REQUEST_KEY

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, MutableMapping, Sequence

    from django.http import HttpRequest
    from mcp.server.auth.provider import TokenVerifier
    from mcp.server.mcpserver import MCPServer
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    from django_stateless_mcp.auth import UserResolver

__all__ = ["mcp_view"]

# Django sets Content-Length itself; echoing the SDK's risks a mismatch.
_SKIPPED_RESPONSE_HEADERS = frozenset({b"content-length"})

# Django's ALLOWED_HOSTS owns host validation; a second allowlist here would be
# a conflicting source of truth over a scope we synthesise. See ADR-0007.
_TRANSPORT_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)


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

    async def handle(self, request: HttpRequest) -> HttpResponse:
        """Dispatch ``request`` to the SDK and return its response.

        Only POST is served: a stateless exchange is one request and one
        response, so the transport's GET/DELETE session machinery (the SSE
        listen stream, session termination) has nothing to attach to here.
        """
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        body = request.body
        response = _ASGIResponse()
        body_delivered = False

        async def receive() -> MutableMapping[str, Any]:
            # After the buffered body there is only disconnect; repeating the
            # body message spins SSE disconnect-listeners forever. See ADR-0017.
            nonlocal body_delivered
            if body_delivered:
                return {"type": "http.disconnect"}
            body_delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        scope = self._build_scope(request)
        if self._authenticator is not None:
            challenge = await self._authenticator.authenticate(scope)
            if challenge is not None:
                return challenge

        session_manager = self._new_session_manager()
        with access_token_context(scope):
            async with session_manager.run():
                await session_manager.handle_request(scope, receive, response.send)
        return response.to_django()

    def _new_session_manager(self) -> StreamableHTTPSessionManager:
        """Build a fresh session manager for this request.

        ``streamable_http_app()`` both constructs the manager and stores it on
        the shared server, so the two steps are locked together: without the
        lock, concurrent requests could each read the other's manager.
        """
        with self._construction_lock:
            self._server.streamable_http_app(
                stateless_http=True,
                json_response=True,
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
) -> Callable[[HttpRequest], Coroutine[Any, Any, HttpResponse]]:
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

    async def view(request: HttpRequest) -> HttpResponse:
        return await bridge.handle(request)

    return csrf_exempt(view)
