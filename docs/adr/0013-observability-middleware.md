# ADR-0013: Flow logging via the SDK's middleware seam

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0007](0007-stateless-view-bridge.md) — the view bridge

## Context

Phase 7: structured per-request logging, per the `flow-logging` convention.
The build plan lists "dispatch hooks / middleware" as an extension point we
must provide — but the scope revision established the SDK already has one
(`MCPServer(middleware=[...])`, `ServerMiddleware` protocol). Building our own
wrapper would duplicate it and re-create the private-internals coupling that
broke `django-mcp-server`.

## Decision

`StructlogRequestLogger`, a `ServerMiddleware` registered on the server. It
times each dispatch and logs one event:

- `mcp.request.completed` at `info`, with `method`, `tool_name`,
  `request_id`, `duration_ms`, and `exit` (`"completed"` /
  `"input_required"`).
- `mcp.request.failed` at `warning`, with `error_type`, then **re-raises** —
  errors belong to the SDK's protocol handling and to Sentry, not to a
  logged-and-swallowed branch.

Dotted stable event names, variables as structlog kwargs, an `*_id` on every
line, numbers as numbers — the `flow-logging` house style, so the events
render to queryable JSON fields.

`structlog` is an **optional dependency** (`django-stateless-mcp[structlog]`),
imported only by this module. A project not using it never loads it, and the
rest of the package has no structlog dependency.

## Consequences and details worth recording

- **Protocol matching is by parameter name.** The middleware's first
  parameter must be `ctx`, not `context`: `ServerMiddleware` is a `Protocol`,
  and mypy checks the parameter name against it. Renaming was the fix.
- **The result arrives in two shapes.** At the middleware tier the handler
  result is sometimes a model (`result_type`) and sometimes an already-dumped
  dict (`resultType`); `exit` classification reads both. A test that only
  exercised the completed path would have missed this — the
  `input_required` assertion caught it.
- The middleware runs on the event-loop thread, which is why it cannot help
  with the worker-thread DB-connection cleanup noted in
  [ADR-0010](0010-request-context.md): that hazard needs a worker-thread hook
  the SDK does not currently expose, and remains a documented gap rather than
  something this middleware silently half-fixes.
- Registration is the project's choice — the package ships the middleware but
  does not force it on, matching the explicit-instance philosophy of the
  whole configuration surface.
