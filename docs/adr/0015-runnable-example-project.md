# ADR-0015: One runnable example project, shared with the test suite

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0008](0008-conformance-suite.md) — the bootable fixture; [ADR-0009](0009-mcp-autodiscovery.md) — `mcp.py` autodiscovery

## Context

The test fixture under `tests/` (`settings.py`, `urls.py`, `mcp_server.py`, `mcp.py`) was
explicitly labelled "not an example project", yet it was already the closest thing to one:
`scripts/run_conformance.sh` booted it with `runserver` for the conformance suite. What it
could not do was serve as *demonstration infrastructure* — there was no ASGI entrypoint, no
multi-worker launch (ironic for a package whose thesis is multi-worker statelessness), no
migrated database for the ORM/permission tools, and no documented way to point a real MCP
client at it. A newcomer could read that elicitation survives a fleet; they could not watch
it happen.

Three shapes were considered:

1. **Keep the fixture, add a separate `example/` demo.** Two Django projects to maintain,
   guaranteed to drift; the demo would not be under test.
2. **Add launch scaffolding inside `tests/`.** No drift, but a public package's example
   buried under `tests/` is undiscoverable, and mixes launch concerns into fixture code.
3. **Promote the fixture to a root-level `example/` project and have the tests import it.**

## Decision

Option 3. `example/` is a real, tiny Django project — `settings.py`, `urls.py`,
`mcp_server.py`, `mcp.py`, `asgi.py`, `wsgi.py`, a root `manage.py`, and a `seed` command —
launched by `just demo` (WSGI) and `just demo-asgi` (uvicorn, four workers). The test suite
consumes it: `tests/settings.py` is `from example.settings import *` plus an in-memory
database override, and the tests drive the same URLs the demo serves. The conformance
suite boots `example.settings` directly.

The dependency direction is the point. The example is a genuine downstream consumer of the
public API, type-checked under the same `mypy --strict` gate, so it doubles as living
documentation of what a consumer writes — and because the tests inherit it, the demo can
never drift from what CI verifies. A `worker_pid` tool was added so the multi-worker claim
is observable, and a committed secret-free `.mcp.json` connects a Claude Code session in
the repo to the running demo.

## What we learned

Strict-typing the example immediately surfaced an API wart the untyped fixture had hidden:
`PermittedToolsFilter`'s `ToolVisible` types the user as `AbstractBaseUser | AnonymousUser`,
but `AbstractBaseUser` has no `has_perm`, so a typed downstream predicate must narrow (the
example uses `isinstance(user, PermissionsMixin)`). Recorded here as a candidate API fix
rather than silently worked around — per the project rule that a downstream forced into
contortions is our defect.

## Consequences

- The demo user (`mcp-test-user`) and bearer token (`good-token`) are published constants;
  the example must never grow a real secret.
- `example/` ships in the repository, not the wheel; coverage tracks it (launch entrypoints
  omitted) and CI type-checks it.
- Anything added to the fixture servers is now also demo surface — tool names and endpoint
  paths are quasi-public, and the conformance baseline pins the `test_*` names regardless.
