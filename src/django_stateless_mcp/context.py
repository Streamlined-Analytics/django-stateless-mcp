"""Access the Django request from inside MCP handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.http import HttpRequest
    from mcp.server.mcpserver import Context

__all__ = ["django_request"]

_STATE_KEY = "django_request"


def django_request(context: Context[Any, Any]) -> HttpRequest:
    """Return the Django request being served by this MCP call.

    Tools receive the SDK's ``Context`` by declaring a parameter of that
    type; this reads the ``HttpRequest`` the view stored on the transport
    scope, giving access to headers, ``user`` and anything middleware
    attached — without any global state::

        @server.tool()
        def whoami(ctx: Context) -> str:
            return django_request(ctx).user.get_username()

    Raises ``LookupError`` if the call did not come through ``mcp_view``,
    for example when a tool is invoked directly in a unit test.
    """
    try:
        request_context = context.request_context
    except ValueError as error:
        raise LookupError("No Django request on this MCP call; it did not arrive through mcp_view().") from error
    transport_request = getattr(request_context, "request", None)
    state = getattr(transport_request, "state", None)
    http_request: HttpRequest | None = getattr(state, _STATE_KEY, None)
    if http_request is None:
        raise LookupError("No Django request on this MCP call; it did not arrive through mcp_view().")
    return http_request
