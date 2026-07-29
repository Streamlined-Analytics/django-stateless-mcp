"""An MCP server fixture for the test suite."""

from __future__ import annotations

from django.contrib.auth.models import User
from mcp.server.mcpserver import Context, MCPServer

from django_stateless_mcp import django_request

server = MCPServer(name="test-server", version="0.0.1")


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
