# 0032. The example project runs consumer-realistic settings, and the suite tests the gaps

- **Status:** Accepted
- **Date:** 2026-08-01
- **Deciders:** Ben Atkinson
- **Feature / area:** test suite / example project
- **Builds on:** ADR-0031 — the ATOMIC_REQUESTS failure this generalises from
- **Supersedes / Superseded by:** none

## What problem were we trying to solve?

ADR-0031 fixed a bug that shipped for one reason: the suite only ever ran the
one configuration that works. The example project's settings (which the tests
inherit, ADR-0015) had three middleware entries, one database alias, no proxy
configuration — and `ATOMIC_REQUESTS` off. The first production deployment ran
a different configuration and 500d on every request.

An audit of the two real consumer projects (ic_cookie, safersphere) found five
more places where their configuration diverges from anything this repo tests:

- **Two database aliases with mixed `ATOMIC_REQUESTS`** (ic_cookie: `default`
  on, `apikeys` off). The per-alias exemption loop shipped in ADR-0031 was
  being exercised as a loop of one.
- **Slash-less mounts.** Both mount the view at `"mcp"`; every mount in this
  repo carried a trailing slash, and every test POSTed to `/mcp/`.
- **Database-backed token verification** (django-oauth-toolkit) with
  `required_scopes` and a `user_resolver` on every request — while every
  bearer-auth test here used the sync WSGI client and an in-memory stub, and
  both consumers deploy ASGI.
- **A ten-plus-entry middleware stack**, bracketed first-and-last by
  django-prometheus response middleware that processes every response —
  including the subscription `StreamingHttpResponse`, which no
  response-processing middleware had ever touched in this suite.
- **`SECURE_PROXY_SSL_HEADER` behind Traefik.** The bridge forwards
  `request.scheme` as the ASGI scope's `scheme`; nothing asserted it reads
  `https` behind a proxy.

## What did we try?

### Attempt 1 — a second settings module and a tox/CI leg   <!-- ❌ rejected up front -->

A `tests/settings_consumer.py` variant run as its own matrix factor. Rejected:
it recreates exactly the drift ADR-0015 exists to kill — two fixtures, one of
which quietly stops matching reality — and the multiworker fleet and the
conformance suite boot `example.settings` directly, so they would silently
keep running the thin configuration.

### Attempt 2 — make the example itself consumer-shaped   <!-- ✅ chosen -->

Extend `example/settings.py` to the stack consumers actually run, so every
existing test, the conformance suite, and the multiworker harness all inherit
it, and add explicit tests only for the behaviours that need asserting. The
one consumer middleware worth modelling but not depending on
(django-prometheus) is reproduced by two tiny in-repo `MiddlewareMixin`
classes (`example/middleware.py`) that stamp response headers from the same
first-and-last bracket positions.

## What did we land on, and why?

- `example/settings.py` carries the full standard-Django consumer stack
  (Security, Session, Locale, Common, CSRF, Auth, Message, XFrameOptions)
  bracketed by the prometheus-shaped pair, plus `django.contrib.messages`.
- `tests/settings.py` adds a second `apikeys` database alias, making the
  ADR-0031 exemption loop real; a fixture toggles `ATOMIC_REQUESTS` on the
  secondary alias alone — the case a bare default-only exemption would miss.
- The example mounts `"mcp"` (slash-less, the consumer shape) alongside
  `"mcp/"`, and a `db-mcp/` endpoint whose `DatabaseTokenVerifier` and
  `resolve_db_user` derive everything from a `User` row per request,
  mirroring the django-oauth-toolkit shape.
- New tests pin: slash-less serving without redirect, proxy-header scheme
  (`request_scheme` tool echoes what the bridge forwards), bracket headers on
  buffered and streaming responses with the stream still delivering frames,
  oversized bodies getting Django's 400, database-backed auth under WSGI and
  ASGI, and ASGI variants of the atomic and bearer-auth tests.

An unplanned win confirmed the approach: with `CommonMiddleware` in the stack,
`request.get_host()` runs on every request, so `ALLOWED_HOSTS` now rejects
evil-Host requests and the conformance suite's `dns-rebinding-protection`
scenario — a deliberate expected failure since ADR-0007 — passes. The
consumer-shaped stack is not just more realistic; it is what makes the
ADR-0007 "Django owns host validation" stance actually hold at runtime.

Nothing installed changes: `example/` and `tests/` ship in the repository,
not the wheel, so there is no version bump and no release.

## What does this cost us?

- The example is no longer minimal — a reader meets ten middleware entries
  where three would demonstrate the integration. Accepted: the example's job
  (ADR-0015) is to be the consumer-shaped fixture, not the smallest demo.
- The bracketing middleware is a stand-in, not django-prometheus itself; a
  breakage specific to the real package would still escape. Accepted to keep
  the example dependency-free.
- Consumer parity is a snapshot of two projects as of 2026-08-01. The next
  divergence class (new middleware, new deployment shape) still needs a human
  to notice and add it here.
