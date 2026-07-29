# ADR-0014: Resolve the Django user and filter tools by permission

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0011](0011-bearer-auth.md) — bearer auth

## Context

ADR-0011 verified bearer tokens but stopped at the token: a tool could learn the
OAuth client via `get_access_token()`, but not *which Django user* the call
acted for. Permission-locking tools — the central reason to authenticate an MCP
endpoint exposing a database — was therefore not expressible. Two needs followed:

1. Reach the authenticated Django user inside a tool, to gate execution.
2. Hide tools a user cannot use from `tools/list`, so a client is never shown
   them.

## Decision

### `user_resolver` sets `request.user`

`mcp_view(..., user_resolver=async (token) -> user)`. After a token verifies,
the authenticator resolves it to a Django user and sets `request.user`, so a
tool reads it the ordinary way:

```python
django_request(ctx).user.has_perm("app.delete_thing")
```

The resolver is separate from the SDK `token_verifier` deliberately: the SDK
contract returns a token-shaped `AccessToken` (client_id, scopes) with no slot
for a Django user, and it is the only place that knows the user, so the package
takes a second small hook rather than distorting the SDK's. `has_perm` inside a
tool is safe because tools run in a worker thread, off the event loop.

### `PermittedToolsFilter` hides tools on `tools/list`

A `ServerMiddleware` that filters the tool list to those an `is_visible(user,
name)` predicate approves. It reaches the user via the same `request.user`, and
runs the predicate in a worker thread — so `has_perm`, which queries, does not
raise `SynchronousOnlyOperation` on the event loop.

## The security model — the load-bearing decision

**Visibility filtering is not a security boundary, and the design refuses to
pretend otherwise.** Hiding a tool from `tools/list` does not stop a client
calling it by name; the MCP protocol has no notion of "you may not see this
method". So:

- **Execution gating** (the tool checking `has_perm` itself) is the security
  boundary. It must always be present.
- **Visibility filtering** is least-knowledge ergonomics on top — a tidy client
  experience and no disclosure of forbidden tools' existence.

A test encodes this exactly: a hidden tool called by name is still refused,
because the tool gates its own execution. Filtering alone would be security
theatre, and the package's docs and this ADR say so in as many words.

## Consequences and details worth recording

- **No package-level Django-model imports.** `permissions.py` first imported
  `AnonymousUser` at module top level, which forced Django's app registry to
  load when `django_stateless_mcp` was imported — crashing the django-stubs
  mypy plugin with `AppRegistryNotReady` (it imports the package before Django
  is set up). Django-model imports in package code must be lazy (inside the
  function) or `TYPE_CHECKING`-only. The other modules were already careful;
  this one taught the rule.
- **The tool-list result is a `dict` at the middleware tier**, not a
  `ListToolsResult` model (the same two-shapes quirk ADR-0013 met). The filter
  handles both.
- Two new public symbols — `mcp_view`'s `user_resolver` parameter and
  `PermittedToolsFilter` — each a maintenance promise.
- The `user_resolver` requires a `token_verifier`; without authentication there
  is no token to resolve, and `request.user` stays anonymous.

## The DOT recipe

`django-oauth-toolkit` + `django-oauth-toolkit-dcr` are the natural authorization
server behind this (ADR-0011 predicted the "Django-ORM-backed verifier" as a
downstream). The whole picture — a `DOTTokenVerifier`, a DOT-backed
`user_resolver`, and both permission features — is documented as a recipe rather
than shipped as a dependency, keeping DOT out of the package's requirements.
