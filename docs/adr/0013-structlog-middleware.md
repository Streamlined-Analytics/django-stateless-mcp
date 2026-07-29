# ADR-0013: Flow logging via the SDK's middleware seam

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0010](0010-request-context.md)

## Context

Phase 7: production logs should reconstruct what the MCP endpoint did —
which tool, how long, and crucially *how the call ended* — without a
debugger. The SDK provides the right seam: `ServerMiddleware`, `(ctx,
call_next)` wrapping every request at the dispatch tier. Building our own
hook would duplicate it.

## Decision

`StructlogRequestLogger`, registered by the user on
`MCPServer(middleware=[...])`. One event per request, flow-logging style:
dotted stable event names, variables as kwargs, numbers as numbers.

- `mcp.request.completed` at `info`, with `method`, `tool_name`,
  `request_id`, `duration_ms`, and a closed `exit` vocabulary —
  `"completed"` or `"input_required"`. The latter makes elicitation pauses
  first-class in logs: a multi-round flow reads as pause, pause, completion.
- `mcp.request.failed` at `warning` with `error_type`, then **re-raise** —
  errors stay owned by the SDK's protocol handling and Sentry; the
  middleware only records that the flow ended that way.

structlog is an **optional extra** (`django-stateless-mcp[structlog]`), not
a hard dependency: logging choice belongs to the project, and forcing a
logging framework from a transport package would be opinionated in the
wrong place.

## Notes from implementation

- The midd
