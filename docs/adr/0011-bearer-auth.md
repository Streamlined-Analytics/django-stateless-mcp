# ADR-0011: Bearer auth via the SDK's TokenVerifier, enforced in the view

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0007](0007-stateless-view-bridge.md) — the view bridge

## Context

Phase 4. MCP clients authenticate with OAuth bearer tokens, and the SDK
defines the seam: `TokenVerifier`, a Protocol with one method
(`verify_token(token) -> AccessToken | None`). Downstream implements a shape
rather than inheriting a class — exactly the extension style this package
promises.

The complication: the SDK normally enforces auth with Starlette middleware
inside the app built by `streamable_http_app()` — **the app our bridge
discards** (ADR-0007). Passing `token_verifier` to `MCPServer` would therefore
silently do nothing through this view. Auth has to be enforced by the bridge
itself.

## Decision

`mcp_view(server, token_verifier=..., required_scopes=[...])`. The bridge
authenticates the synthesised scope before dispatch, **reusing the SDK's own
machinery rather than reimplementing it**:

- `BearerAuthBackend` does extraction, verification and expiry — SDK-owned.
- On success the scope carries `scope["user"]` (`AuthenticatedUser`) and
  `scope["auth"]` (`AuthCredentials`) — the exact contract the SDK's own
  middleware establishes, which is also what request-state security binds
  resume tokens to (Phase 5 depends on this).
- Failures reproduce the SDK's wire shape: `401` with
  `WWW-Authenticate: Bearer error="invalid_token"...` and a JSON body, `403`
  with `insufficient_scope` for missing scopes.
- `auth_context_var` is set around the dispatch so the SDK's public
  `get_access_token()` works inside tools.

Without a verifier the endpoint is open and protection is the project's
responsibility. This is deliberate: a Django project may prefer session auth,
network isolation, or its own middleware, and forcing OAuth on it would be
opinionated in the wrong place.

## A bug worth recording: the contextvar leak

The first implementation called `auth_context_var.set(user)` and never reset
it. Every test passed in isolation; the suite failed, because the contextvar
outlives the request in whichever thread served it — the anonymous-endpoint
test observed the previous test's token. That is precisely the
request-spanning state this package exists to forbid, and the SDK's own
`AuthContextMiddleware` resets for the same reason.

The fix is a set-and-reset context manager around each dispatch
(`access_token_context`). The lesson generalises: **contextvars set per
request must be reset per request, and only an ordering-sensitive test suite
notices when they are not.**

## Consequences

- Auth-verified requests and open endpoints coexist in one URLconf — the
  fixture mounts three views (open, `mcp:read`-scoped, `mcp:admin`-scoped)
  against one server.
- The verifier runs on the event loop; a verifier doing blocking I/O (e.g. an
  ORM token lookup) must wrap it — `sync_to_async` — or introspect tokens
  remotely. A Django-ORM-backed verifier is a natural downstream package.
- Scope enforcement reports the first missing scope, matching the SDK's
  message shape.
