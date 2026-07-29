# ADR-0009: Autodiscover per-app `mcp.py` modules

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0007](0007-stateless-view-bridge.md) — the view bridge

## Context

Phase 2: the "tool sources / discovery" extension point — a way for an
installed app to contribute a family of tools without the project's URLconf
importing it.

The scope revision against the installed SDK matters here: registration
already exists (`@server.tool()` and friends are public SDK API), so the only
genuine gap is that **nothing imports an app's tool registrations**. Building a
registry of our own on top would duplicate the SDK's and re-create the exact
coupling that broke `django-mcp-server`.

## Decision

An `AppConfig.ready()` that calls Django's own
`django.utils.module_loading.autodiscover_modules("mcp")` — the mechanism
`django.contrib.admin` uses for `admin.py`. Adding `django_stateless_mcp` to
`INSTALLED_APPS` is the whole opt-in.

- Imports are app-relative (`myapp.mcp`), so there is no collision with the
  SDK's top-level `mcp` package.
- Apps without an `mcp` module are skipped; an `mcp` module that fails to
  import **raises at startup** — errors are not swallowed.
- No package-level registry, no default server. An app's `mcp.py` imports
  whichever server the project defines and registers against it with SDK API.
  The explicit-instance contract from ADR-0007 is unchanged.

## Consequences

- The proof-shaped test: nothing in the suite imports `tests/mcp.py`, so its
  `multiply` tool appears in `tools/list` only if autodiscovery imported it.
- The tool registry is populated at import time and read per request. That is
  configuration, like the URLconf — not the request-spanning mutable state the
  statelessness invariant forbids.
- A project that mounts `mcp_view` without adding the app to `INSTALLED_APPS`
  simply gets no autodiscovery; explicit imports keep working.
- `autodiscover_modules` is long-stable but lives in `django.utils` — worth a
  glance at release notes on new Django majors.
