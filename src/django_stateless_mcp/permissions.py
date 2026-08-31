"""Hide tools a request's user may not use from ``tools/list``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from asgiref.sync import sync_to_async

from django_stateless_mcp.context import _DJANGO_REQUEST_KEY

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from mcp.server.context import CallNext, HandlerResult, ServerRequestContext

    ToolVisible = Callable[[AbstractBaseUser | AnonymousUser, str], bool]

__all__ = ["PermittedToolsFilter"]

_LIST_TOOLS_METHOD = "tools/list"


def _request_user(ctx: ServerRequestContext[Any, Any]) -> AbstractBaseUser | AnonymousUser:
    """Return the Django user on the request, or an anonymous user."""
    from django.contrib.auth.models import AnonymousUser

    transport_request = getattr(ctx, "request", None)
    transport_state = getattr(transport_request, "state", None)
    http_request = getattr(transport_state, _DJANGO_REQUEST_KEY, None)
    user = getattr(http_request, "user", None)
    if user is None:
        return AnonymousUser()
    return cast("AbstractBaseUser | AnonymousUser", user)


def _tool_name(tool: Any) -> str:
    """Read a tool's name whether it arrives as a dict or a model."""
    name = tool["name"] if isinstance(tool, dict) else tool.name
    return cast("str", name)


class PermittedToolsFilter:
    """Middleware hiding tools the request's user may not use.

    Register on the server so ``tools/list`` returns only the tools
    ``is_visible(user, tool_name)`` approves — a user never sees, and a
    client is never told about, a tool they cannot use::

        server = MCPServer(middleware=[PermittedToolsFilter(is_visible)])

    ``is_visible`` is an ordinary synchronous predicate; it is run in a
    worker thread, so it may touch the database and call
    ``user.has_perm(...)`` freely. It receives the authenticated Django
    user, which requires a ``user_resolver`` on the view; without one the
    user is anonymous.

    !!! warning "Not a security boundary on its own"
        Hiding a tool from ``tools/list`` does not stop a client calling it
        by name. Visibility filtering is least-knowledge ergonomics; the
        security boundary is the tool **gating its own execution** on the
        same permission. Use both together.
    """

    __slots__ = ("_is_visible",)

    def __init__(self, is_visible: ToolVisible) -> None:
        self._is_visible = is_visible

    async def __call__(self, ctx: ServerRequestContext[Any, Any], call_next: CallNext) -> HandlerResult:
        """Filter the tool list; pass every other method through untouched."""
        result = await call_next(ctx)
        if ctx.method != _LIST_TOOLS_METHOD or result is None:
            return result

        user = _request_user(ctx)
        tools = result.get("tools") if isinstance(result, dict) else getattr(result, "tools", None)
        if tools is None:
            return result
        permitted = await sync_to_async(self._permitted)(user, list(tools))
        if isinstance(result, dict):
            result["tools"] = permitted
        else:
            setattr(result, "tools", permitted)  # noqa: B010 -- HandlerResult is BaseModel|dict
        return result

    def _permitted(self, user: AbstractBaseUser | AnonymousUser, tools: list[Any]) -> list[Any]:
        """Keep only the tools the user may see, in a worker thread."""
        return [tool for tool in tools if self._is_visible(user, _tool_name(tool))]
