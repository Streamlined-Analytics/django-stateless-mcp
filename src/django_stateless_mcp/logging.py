"""Structured flow logging for MCP request dispatch."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from mcp.server.context import CallNext, HandlerResult, ServerRequestContext

__all__ = ["StructlogRequestLogger"]

logger = structlog.get_logger("django_stateless_mcp")


def _tool_name(context: ServerRequestContext[Any, Any]) -> str | None:
    """Read the tool name from raw params, present only on tools/call."""
    params = context.params
    if isinstance(params, dict):
        name = params.get("name")
        return name if isinstance(name, str) else None
    return None


def _result_kind(result: object) -> str:
    """Name how the request ended: completed, or paused for input.

    The middleware tier sees either a model (``result_type``) or an
    already-dumped dict (``resultType``), depending on the handler.
    """
    result_type = getattr(result, "result_type", None)
    if result_type is None and isinstance(result, dict):
        result_type = result.get("resultType")
    if result_type == "input_required":
        return "input_required"
    return "completed"


class StructlogRequestLogger:
    """Middleware logging one flow event per MCP request.

    Register on the server so every request logs its method, tool, outcome
    and duration in queryable structlog kwargs::

        server = MCPServer(
            name="my-server",
            middleware=[StructlogRequestLogger()],
        )

    Completions log at ``info`` as ``mcp.request.completed`` with
    ``exit="completed"`` or ``exit="input_required"`` — so an elicitation
    pause is distinguishable from a finished call in LogQL. Failures log at
    ``warning`` as ``mcp.request.failed`` with the exception type, then
    **re-raise**: the SDK's protocol error handling and Sentry own errors,
    this middleware only records that the flow ended that way.

    The context is typed ``Any`` over its lifespan parameter, per the SDK's
    own guidance that reusable middleware register as
    ``ServerMiddleware[Any]``.
    """

    __slots__ = ()

    async def __call__(
        self,
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> HandlerResult:
        """Time one dispatch and log how it ended."""
        started = time.monotonic()
        method = ctx.method
        tool_name = _tool_name(ctx)
        request_id = str(ctx.request_id) if ctx.request_id is not None else None

        try:
            result = await call_next(ctx)
        except Exception as error:
            logger.warning(
                "mcp.request.failed",
                method=method,
                tool_name=tool_name,
                request_id=request_id,
                duration_ms=round((time.monotonic() - started) * 1000, 2),
                error_type=type(error).__name__,
            )
            raise

        logger.info(
            "mcp.request.completed",
            method=method,
            tool_name=tool_name,
            request_id=request_id,
            duration_ms=round((time.monotonic() - started) * 1000, 2),
            exit=_result_kind(result),
        )
        return result
