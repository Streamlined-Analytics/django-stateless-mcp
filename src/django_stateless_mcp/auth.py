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
    from collections.abc import Awaitable, Callable, Iterator, MutableMapping, Sequence

    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from mcp.server.auth.provider import TokenVerifier

    UserResolver = Callable[[str], Awaitable[AbstractBaseUser | AnonymousUser | None]]

__all__ = ["BearerAuthenticator", "access_token_context"]

_DJANGO_REQUEST_KEY = "django_request"


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


def _bearer_token(connection: HTTPConnection) -> str | None:
    """Extract the bearer token from an Authorization header, if present."""
    header = connection.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    return header[7:]


class BearerAuthenticator:
    """Authenticates a synthesised ASGI scope with the SDK's own machinery.

    Wraps the SDK's ``BearerAuthBackend`` — extraction, verification and
    expiry all stay SDK-owned — and reproduces the scope contract its
    Starlette middleware would have established: ``scope["user"]`` and
    ``scope["auth"]``, plus the ``auth_context_var`` that backs the SDK's
    ``get_access_token()``. That contract is also what request-state
    security binds resume tokens to.

    When a ``user_resolver`` is given, the verified token is resolved to a
    Django user which is set on the request, so a tool reaching the request
    with ``django_request(ctx)`` sees ``request.user`` populated and can
    permission-check with the ordinary ``user.has_perm(...)``.
    """

    __slots__ = ("_backend", "_required_scopes", "_user_resolver")

    def __init__(
        self,
        token_verifier: TokenVerifier,
        required_scopes: Sequence[str] = (),
        user_resolver: UserResolver | None = None,
    ) -> None:
        self._backend = BearerAuthBackend(token_verifier)
        self._required_scopes = tuple(required_scopes)
        self._user_resolver = user_resolver

    async def authenticate(self, scope: MutableMapping[str, Any]) -> HttpResponse | None:
        """Authenticate ``scope`` in place, or return the error response.

        On success the scope carries the authenticated user and credentials
        and ``None`` is returned; the caller proceeds to the handler.
        """
        connection = HTTPConnection(scope)
        result = await self._backend.authenticate(connection)
        if result is None:
            return _challenge(401, "invalid_token", "Authentication required")

        credentials, user = result
        missing = [s for s in self._required_scopes if s not in credentials.scopes]
        if missing:
            return _challenge(403, "insufficient_scope", f"Required scope: {missing[0]}")

        scope["user"] = user
        scope["auth"] = credentials
        await self._bind_django_user(scope, connection)
        return None

    async def _bind_django_user(self, scope: MutableMapping[str, Any], connection: HTTPConnection) -> None:
        """Set ``request.user`` from the verified token, if a resolver is set.

        When the resolver yields no user -- a client-credentials token, or a
        user since deleted -- ``request.user`` is set to ``AnonymousUser`` so a
        permission check fails closed, never with ``AttributeError``.
        """
        if self._user_resolver is None:
            return
        request = scope.get("state", {}).get(_DJANGO_REQUEST_KEY)
        if request is None:
            return
        token = _bearer_token(connection)
        django_user = await self._user_resolver(token) if token is not None else None
        if django_user is None:
            from django.contrib.auth.models import AnonymousUser

            django_user = AnonymousUser()
        request.user = django_user
