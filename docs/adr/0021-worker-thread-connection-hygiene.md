# ADR-0021: Worker-thread database-connection hygiene

- **Status:** Accepted
- **Date:** 2026-07-30
- **Builds on:** [ADR-0010](0010-request-context.md) — where sync-tool ORM access was
  established and this gap was first recorded

## Context

Sync tools run in the SDK's thread pool (`anyio.to_thread.run_sync`, `resolve.py` — there
is no per-tool wrapper seam). A Django connection is thread-local, so a tool touching the
ORM opens a connection **in a pool thread that Django's request machinery never sees**:
`request_finished` → `close_old_connections` runs in the request's own thread. Pool
threads are reused indefinitely, so their connections were never aged out
(`CONN_MAX_AGE`), never health-checked, and never closed — a slow leak of stale
connections that surfaces as `server closed the connection unexpectedly` errors after
database restarts or idle timeouts, under exactly the sustained production load the
package is built for.

ADR-0010 recorded this as "measure in a real deployment before acting; possibly an
upstream SDK ask". Acting now (the deferred-work sweep), the constraint stands: the SDK
offers no hook around tool execution, so the fix must reach into the pool from outside.

## Decision

After each buffered dispatch, the bridge runs Django's own `close_old_connections`
**inside the pool** — `await anyio.to_thread.run_sync(close_old_connections)`. This is
Django's per-request cleanup executed where the connections actually live:

- anyio's pool reuses idle workers **LIFO**, so the hop overwhelmingly lands on the very
  thread that just served the tool; under concurrency, every request's hop cleans
  whichever thread it lands on, so all active threads are recycled continuously.
- Semantics are exactly Django's: with the default `CONN_MAX_AGE=0` the tool's
  connection is closed after the request; with a positive max age, connections persist
  and are aged/health-checked on the same schedule as request-thread connections. With
  `CONN_MAX_AGE>0` a connection can still go stale *between* a thread's visits — the
  same window Django's own request threads have.
- Cost: one thread hop (~0.1–0.3 ms) per request, tool-bearing or not — the same
  always-on posture as Django's `request_finished` signal.
- The listen path (ADR-0020) is exempt: the stream's handler does not run tools, and
  the resolver's ORM access runs via `sync_to_async` in asgiref's executor, which
  Django's own cleanup already covers.

The regression test pins the wiring — the recycle runs, on a pool thread — because the
closing itself is unobservable under pytest (Django deliberately never closes in-memory
SQLite test connections). The example's `db_thread_info` tool makes the real effect
visible live: call `count_users` then `db_thread_info` in Inspector against the
file-backed demo and the reused worker thread reports `connection_open=False`.

## Consequences

- Long-running fleets no longer accumulate stale ORM connections in tool threads; DB
  restarts stop breaking the next tool call per pool thread.
- `views.py` imports `django.db.close_old_connections` — still no model imports at
  module level (the mypy-plugin rule).
- If the SDK ever grows a tool-execution hook, the hop can move inside it and become
  exact rather than LIFO-probabilistic; that remains worth an upstream ask.
