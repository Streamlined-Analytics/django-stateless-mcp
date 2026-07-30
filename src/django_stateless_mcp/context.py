"""Access the Django request from inside MCP handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.http import HttpRequest
    from mcp.server.mcpserver import Context

__all__ = ["django_request"]

# The one transport-scope key for the HttpRequest; views, auth and permissions import it from here.
_DJANGO_REQUEST_KEY = "django_request"

_MISSING_REQUEST_MESSAGE = "No Django request on this MCP call; it did not arrive through mcp_view()."


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
        raise LookupError(_MISSING_REQUEST_MESSAGE) from error
    transport_request = getattr(request_context, "request", None)
    transport_state = getattr(transport_request, "state", None)
    http_request: HttpRequest | None = getattr(transport_state, _DJANGO_REQUEST_KEY, None)
    if http_request is None:
        raise LookupError(_MISSING_REQUEST_MESSAGE)
    return http_request
