"""An MCP server fixture for the test suite."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

server = MCPServer(name="test-server", version="0.0.1")


@server.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b
