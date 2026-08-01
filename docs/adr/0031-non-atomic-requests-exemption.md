# 0031. `mcp_view()` exempts itself from `ATOMIC_REQUESTS` on every alias

- **Status:** Accepted
- **Date:** 2026-08-01
- **Deciders:** Ben Atkinson
- **Feature / area:** stateless view (`mcp_view`)
- **Builds on:** ADR-0018 — the view's prior request-layer exemption decision (CSRF)
- **Supersedes / Superseded by:** none

## What problem were we trying to solve?

The first production deployment of this library (ic_cookie, 2026-08-01) broke
its `/mcp` endpoint outright: every request raised

```
RuntimeError: You cannot use ATOMIC_REQUESTS with async views.
```

`mcp_view()` returns an async view, and Django's `BaseHandler.make_view_atomic`
refuses to serve an async view on any database alias configured with
`ATOMIC_REQUESTS = True`. That setting is the default in cookiecutter-django
projects — a large slice of the consumers this package targets — so out of the
box the view was guaranteed to 500 there.

The failure only appears at request time. Unit tests that exercised the server
object directly never crossed `make_view_atomic` and stayed green, which is
exactly how this shipped. Reported as issue #45; the consumer was hotfixed in
Streamlined-Analytics/ic_cookie#1235 (their ADR-0233).

## What did we try?

### Attempt 1 — fix it consumer-side   <!-- ❌ failed in practice -->

The production hotfix: the consumer wraps its registration in
`transaction.non_atomic_requests(...)`. It works, but as the library's answer
it means every `ATOMIC_REQUESTS` consumer must independently discover the
requirement — at request time, in production, because their unit tests won't
catch it either. A library whose view cannot run under a mainstream Django
setting without undocumented consumer surgery is broken, not under-documented.

### Attempt 2 — document the requirement   <!-- ❌ rejected up front -->

A prominent quick-start note telling consumers to wrap the view themselves.
Rejected because there is **no configuration under which the unwrapped view
works** — an async view on an `ATOMIC_REQUESTS` alias never runs; it always
raises before dispatch. Documentation is for choices; this has no choice in it.

### Attempt 3 — auto-apply `transaction.non_atomic_requests` in `mcp_view()`   <!-- ✅ chosen -->

Apply the exemption inside `mcp_view()` itself, so the returned view is always
servable. One refinement over the issue's sketch: `make_view_atomic` checks
**every** alias in `connections.settings`, not just `default`, so the bare
decorator (which exempts only `default`) still crashes a multi-database
project with `ATOMIC_REQUESTS` on another alias. The public decorator
accumulates aliases into the view's exemption set across calls, so we apply it
once per configured alias.

## What did we land on, and why?

`mcp_view()` wraps the view in `transaction.non_atomic_requests(using=alias)`
for every alias in `django.db.connections` (evaluated at URLconf import, when
settings are final). The exemption can only ever convert a guaranteed crash
into working behaviour, so auto-applying takes nothing from any consumer.

Per-request transactions are also a poor semantic fit for MCP traffic: a
request may dispatch a long-running tool, and tools that need transactional
writes should hold their own `transaction.atomic()` blocks (the affected
consumer's already did, which is why its hotfix was safe).

The gap that let this ship is closed with a request-layer regression test: a
test-client POST with `ATOMIC_REQUESTS` switched on for every alias (mutating
`connections.settings`, since `override_settings(DATABASES=...)` does not
reach it), asserting the request gets a 200 instead of the pre-fix
`RuntimeError`.

## What does this cost us?

- Consumers cannot opt the MCP endpoint back *into* per-request transactions.
  That is deliberate and documented in the view's docstring: transactional
  tools own their own `transaction.atomic()` blocks.
- The exempted alias set is captured when `mcp_view()` runs. Aliases added to
  `settings.DATABASES` after URLconf import would not be covered — not a
  supported Django pattern, so accepted.
- The docstring grows another "the view is exempt from X" paragraph; the view
  now carries two request-layer exemptions (CSRF, ADR-0018; atomicity, this
  one), which is coherent — both are protections designed for browser-session
  traffic that MCP traffic is not.
