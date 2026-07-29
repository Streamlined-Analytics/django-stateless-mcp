"""Bearer-token authentication for the stateless MCP view."""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Any

from django.http import HttpResponse
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser, BearerAuthBackend
from starlette.requests import HTTPConnection

if TYPE_CHECKING:
    from collections.abc import Iterator, MutableMapping, Sequence

    from mcp.server.auth.provider import TokenVerifier

__all__ = ["BearerAuthenticator", "access_token_context"]


@contextlib.contextmanager
def access_token_context(scope: MutableMapping[str, Any]) -> Iterator[None]:
    """Expose the scope's authenticated user via the SDK's contextvar.

    Set-and-reset around one dispatch, mirroring the SDK's
    ``AuthContextMiddleware``. Without the reset the contextvar outlives the
    request in whichever thread served it -- exactly the request-spanning
    state this package must never hold.
    """
    user = scope.get("user")
    if not isinstance(user, AuthenticatedUser):
        yield
        return
    token = auth_context_var.set(user)
    try:
        yield
    finally:
        auth_context_var.reset(token)


def _challenge(status: int, error: str, description: str) -> HttpResponse:
    """Build the OAuth error response the SDK's own middleware would send."""
    response = HttpResponse(
        json.dumps({"error": error, "error_description": description}),
        status=status,
        content_type="application/json",
    )
    response["WWW-Authenticate"] = f'Bearer error="{error}", error_description="{description}"'
    return response


class BearerAuthenticator:
    """Authenticates a synthesised ASGI scope with the SDK's own machinery.

    Wraps the SDK's ``BearerAuthBackend`` — extraction, verification and
    expiry all stay SDK-owned — and reproduces the scope contract its
    Starlette middleware would have established: ``scope["user"]`` and
    ``scope["auth"]``, plus the ``auth_context_var`` that backs the SDK's
    ``get_access_token()``. That contract is also what request-state
    security binds resume tokens to.
    """

    __slots__ = ("_backend", "_required_scopes")

    def __init__(self, token_verifier: TokenVerifier, required_scopes: Sequence[str] = ()) -> None:
        self._backend = BearerAuthBackend(token_verifier)
        self._required_scopes = tuple(required_scopes)

    async def authenticate(self, scope: MutableMapping[str, Any]) -> HttpResponse | None:
        """Authenticate ``scope`` in place, or return the error response.

        On success the scope carries the authenticated user and credentials
        and ``None`` is returned; the caller proceeds to the handler.
        """
        result = await self._backend.authenticate(HTTPConnection(scope))
        if result is None:
            return _challenge(401, "invalid_token", "Authentication required")

        credentials, user = result
        missing = [s for s in self._required_scopes if s not in credentials.scopes]
        if missing:
            return _challenge(403, "insufficient_scope", f"Required scope: {missing[0]}")

        scope["user"] = user
        scope["auth"] = credentials
        return None
