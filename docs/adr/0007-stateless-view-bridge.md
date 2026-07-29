# ADR-0007: Bridge Django to the SDK with a per-request session manager

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0005](0005-temporary-exclude-newer-exemption.md) — the mcp dependency

## Context

Phase 1 of the build: turn an `MCPServer` into a Django view. The SDK's HTTP
entry point is `StreamableHTTPSessionManager.handle_request(scope, receive,
send)` — an ASGI signature — so the work is adapting an `HttpRequest` into a
scope, driving the handler, and assembling an `HttpResponse` from what it sends.

Four decisions had to be made, three of them forced by SDK behaviour that is not
obvious from its documentation.

## Decision 1: an explicit `MCPServer`, not settings

```python
urlpatterns = [path("mcp/", mcp_view(server))]
```

Considered a single `MCP = {...}` settings dict and discrete `MCP_*` settings.
Both are more Django-idiomatic on the surface, but both bake in a single global
server, make multiple endpoints awkward, and require every SDK option we choose
to expose to be mapped through a settings key.

The deciding argument is that **the explicit form does not foreclose the
others**. A settings-driven convenience can be layered on later as sugar over
`mcp_view(server)`; the reverse is not true. Since the view's signature becomes
public API the moment it merges, the reversible option wins.

## Decision 2: a fresh session manager per request

This is forced, not chosen. Two SDK facts combine:

- `session_manager.run()` raises `RuntimeError` if entered twice — *"can only be
  called once per instance"* — and `handle_request` fails without it having been
  entered (*"Task group is not initialized"*).
- Under WSGI, Django starts a **new event loop per request**, so a task group
  created during one request is unusable in the next.

So no manager can span requests. A manager is built, entered, used and discarded
inside each request — which is also exactly what statelessness means here:
nothing survives the exchange.

The public route to a fresh manager is `server.streamable_http_app(...)`, whose
returned Starlette app is deliberately discarded; calling it is what constructs
the manager.

> **This is an API gap worth reporting upstream.** There is no public way to
> obtain a configured session manager without building a Starlette app, and the
> only direct route is the private `_lowlevel_server`. Per our own rule, we do
> not reach in — we accept the wasted app and record the problem.

### The concurrency hazard it creates

`streamable_http_app()` both constructs the manager **and assigns it to the
shared server**. Two concurrent requests would therefore race: request A
constructs, request B constructs, then A reads back B's manager.

Construction and read-back are held under a `threading.Lock`. The lock is
infrastructure, not request state, so it does not violate the statelessness
invariant — nothing about a request survives it. Handling happens outside the
lock, so only the brief construction serialises.

## Decision 3: one async view for both WSGI and ASGI

`handle_request` is async, so there is no sync entry point to take (closing an
open question from the build plan). Rather than maintain two views, `mcp_view`
returns an `async def`: native under ASGI, and Django starts an event loop per
request for it under WSGI. One code path, both deployments.

## Decision 4: Django owns host validation

`streamable_http_app()` silently enables DNS-rebinding protection when `host` is
left at its default `127.0.0.1`, and `TransportSecuritySettings()` defaults to
`enable_dns_rebinding_protection=True` with **empty** allow-lists — which would
reject every request.

It is disabled explicitly. Django already validates `Host` through
`ALLOWED_HOSTS`; a second allow-list, configured separately and judging a scope
we synthesised ourselves, would be a conflicting source of truth and a
first-class footgun. Host validation belongs to the Django project.

## Consequences

- Verified end to end: `tools/list` and `tools/call` both work **without an
  `initialize` handshake**, which is the stateless spec doing its job.
- **No `Mcp-Session-Id` header appears on responses**, and there is a test
  asserting it. If one ever does, horizontal scaling is silently broken.
- Nine tests pass on Django **5.2.16 and 6.0.7**, across sync (`client`) and
  async (`async_client`) paths.
- Per-request cost is one Starlette app plus one manager, and the SDK logs two
  INFO lines per request from the manager lifecycle. Both are worth revisiting
  with measurements rather than guesses.
- `json_response=True` is fixed for now. Streaming responses would need SSE and
  a different response assembly; that is the deferred subscriptions question.

## A typing trap worth recording

`mcp_view` first returned `Callable[..., Awaitable[HttpResponse]]`, which
**fails** to match django-stubs' `path()` overloads — they require
`Coroutine[Any, Any, HttpResponseBase]`, and `Awaitable` is broader. Left
unfixed, every downstream user would have needed a `# type: ignore` in their
URLconf, which by our own rule is a defect in our API rather than theirs.

It surfaced only because `tests/urls.py` is written exactly as a user would
write it — evidence for the build plan's "public-API contract tests import only
what a downstream package would" principle.

Related: annotating a test helper with django-stubs' `_MonkeyPatchedWSGIResponse`
type-checks cleanly and then **fails at runtime**, because it exists only in the
stubs. mypy passing is not proof the code runs.
