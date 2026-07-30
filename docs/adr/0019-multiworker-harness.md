# ADR-0019: Out-of-process multi-worker test harness

- **Status:** Accepted
- **Date:** 2026-07-30
- **Builds on:** [ADR-0012](0012-request-state-security.md) — the in-process flagship
  tests this completes; [ADR-0015](0015-runnable-example-project.md) — the example
  project the fleets boot

## Context

The flagship tests prove elicitation resumes across two `MCPServer` *instances*, but
both instances share one interpreter — module-level state (the exact failure class that
killed `django-mcp-server`) would be shared between them and invisible to the assertion.
The build plan called an out-of-process harness "the highest-value remaining test": only
separate OS processes prove the horizontal-scaling claim. We verified it by hand this
week (kill the uvicorn fleet mid-elicitation, restart, resume — it works), but a manual
proof evaporates on the next refactor.

The complication is the repo's own testing rule: *"No live server, no bound port."* That
rule exists so tests are hermetic and fast — but this property is untestable without a
real fleet, and the conformance suite (ADR-0008) already set the precedent of a live
server booted by CI, not by hand.

## Decision

`tests/test_multiworker.py` boots the example project as a real four-worker fleet in a
separate OS process group — parametrized over **uvicorn (ASGI)** and **gunicorn (WSGI)**,
so both deployment models are proven — on an ephemeral port, over fresh connections per
request (defeating keep-alive worker affinity). Two tests:

1. **Worker spread** — successive calls are answered by ≥2 distinct pids.
2. **The thesis** — an elicitation is started, the entire fleet is killed (process
   group SIGTERM), a replacement fleet boots, its pids are asserted **disjoint** from
   the first fleet's, and the saved `requestState` resumes to completion on it.

The rule tension is resolved by gating: the module skips unless `MULTIWORKER=1`, so the
default `pytest` run stays hermetic. `just multiworker` runs it locally; CI runs it as a
dedicated `multiworker` job wired into `all-checks-pass`. The interactive counterpart is
`just demo-gunicorn` (new), the WSGI sibling of `just demo-asgi`, so the same fleets can
be driven manually with MCP Inspector and read in the structlog output.

## Consequences

- Module-level request-spanning state anywhere in the package now fails CI
  deterministically — the disjoint-pid assertion makes "which worker holds this?"
  unanswerable by luck.
- `gunicorn` and `uvicorn` join the test dependency group; they are not runtime
  dependencies.
- The suite gains ~20s in a parallel CI job, not on the default local run.
- The harness drives only DB-free tools, so it needs no migrate/seed step; a future
  scenario touching the ORM must add one.
