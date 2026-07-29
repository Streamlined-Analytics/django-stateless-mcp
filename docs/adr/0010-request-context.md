# ADR-0010: Carry the Django request on the transport scope

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0007](0007-stateless-view-bridge.md) — the view bridge

## Context

Phase 3: tools need the authenticated Django `request`/`user` without global
state. A thread-local or contextvar set by the view would work under one
deployment model and silently misbehave under the other — precisely the class
of hazard this package exists to remove.

## Decision

The bridge already synthesises the ASGI scope, and the SDK's transport wraps
that scope in a Starlette `Request` which it stamps onto every message's
metadata (`ServerMessageMetadata.request_context`), reachable from a tool as
`Context.request_context.request` — public attributes throughout. So the view
puts the `HttpRequest` into `scope["state"]`, and a public accessor reads it
back:

```python
@server.tool()
def whoami(ctx: Context) -> str:
    return django_request(ctx).user.get_username()
```

No global, no contextvar: the request travels *inside the call*, which is the
same shape as statelessness itself. Off the request path the accessor raises
`LookupError` — never `None` — and the SDK's "Context is not available outside
of a request" `ValueError` is normalised to the same `LookupError`, so callers
have one failure mode.

## Sync tools: the SDK already does the work

The plan assumed we would wrap sync tools in `sync_to_async`. Inspection shows
the SDK runs sync tool functions via `anyio.to_thread.run_sync` — a worker
thread with no event loop — so ORM access inside a plain `def` tool simply
works, under WSGI and ASGI both. Verified end to end by a tool that counts
`auth.User` rows through the view.

Async tools remain event-loop-bound: ORM there raises
`SynchronousOnlyOperation`, and the documented guidance is `sync_to_async` or
keeping database tools synchronous.

## Known gap: worker-thread connection hygiene

Django closes database connections at request end via signals **on the
handler's thread** — connections are thread-local. The SDK's worker threads
are not that thread, so connections opened by tools are not covered by
Django's request-end cleanup; they close when anyio's idle worker threads are
reaped, which bounds but does not manage them. A `ServerMiddleware` cannot fix
this either — it runs on the event loop thread, and `close_old_connections`
only touches the calling thread's connections.

Accepted for now and deliberately not papered over: revisit alongside Phase 7
observability middleware, with measurements from a real deployment, and
consider raising upstream whether the SDK should expose a post-call hook in
the worker thread.

## A testing lesson worth recording

The ORM test needs `django_db(transaction=True)`: the tool's query runs on a
*different connection*, so a fixture row created inside the default
test-transaction is invisible to it. The plain `django_db` marker passes an
emptier test than it appears to — the row simply is not there for the tool.
