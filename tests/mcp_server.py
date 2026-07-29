"""An MCP server fixture for the test suite."""

from __future__ import annotations

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver import Context, MCPServer

from django_stateless_mcp import (
    PermittedToolsFilter,
    StructlogRequestLogger,
    django_request,
    request_state_security,
)


def _delete_widget_visible(user, tool_name):
    """delete_widget is visible only to users who may delete users."""
    if tool_name != "delete_widget":
        return True
    return user.has_perm("auth.delete_user")


server = MCPServer(
    name="test-server",
    version="0.0.1",
    request_state_security=request_state_security(),
    middleware=[StructlogRequestLogger()],
)

# A server that filters tool visibility by permission.
server_filtered = MCPServer(
    name="test-server",
    version="0.0.1",
    request_state_security=request_state_security(),
    middleware=[PermittedToolsFilter(_delete_widget_visible)],
)


@server_filtered.tool()
def public_ping() -> str:
    """A tool everyone may see."""
    return "pong"


@server_filtered.tool(name="delete_widget")
def filtered_delete_widget(ctx: Context, widget_id: int) -> str:
    """Hidden from users lacking the perm; also gates its own execution."""
    if not django_request(ctx).user.has_perm("auth.delete_user"):
        raise PermissionError("You may not delete widgets.")
    return f"deleted widget {widget_id}"


# A second, independent instance modelling another worker in a fleet. Same
# name deliberately: request-state audience binding is by server name, which
# identical replicas share.
server_b = MCPServer(
    name="test-server",
    version="0.0.1",
    request_state_security=request_state_security(),
)


@server.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@server.tool()
def request_path(ctx: Context) -> str:
    """Echo the path of the Django request serving this call."""
    return django_request(ctx).path


@server.tool()
def count_users(ctx: Context) -> int:
    """Count users via the ORM, exercising sync DB access in a tool."""
    django_request(ctx)
    return User.objects.count()


class StubVerifier:
    """A TokenVerifier accepting one hard-coded token, for auth tests."""

    async def verify_token(self, token: str) -> AccessToken | None:
        """Accept ``good-token`` with read scope; reject everything else."""
        if token != "good-token":
            return None
        return AccessToken(token=token, client_id="test-client", scopes=["mcp:read"])


async def resolve_stub_user(token: str) -> User | None:
    """Resolve the bearer token to a Django user.

    Models a real user_resolver: one async lookup returning the Django user
    the token was issued for. ORM access is wrapped, as it must be on the
    event loop.
    """
    return await sync_to_async(User.objects.filter(username="mcp-test-user").first)()


@server.tool()
def token_client(ctx: Context) -> str:
    """Name the OAuth client the SDK sees for this call."""
    access_token = get_access_token()
    return access_token.client_id if access_token else "anonymous"


@server.tool()
def current_username(ctx: Context) -> str:
    """Name the authenticated Django user reached via the request."""
    return django_request(ctx).user.get_username()


@server.tool()
def delete_widget(ctx: Context, widget_id: int) -> str:
    """A permission-locked tool: refuses a user without the perm."""
    user = django_request(ctx).user
    if not user.has_perm("auth.delete_user"):
        raise PermissionError("You may not delete widgets.")
    return f"deleted widget {widget_id}"
