# ADR-0018: The example carries the standard auth middleware

- **Status:** Accepted
- **Date:** 2026-07-30
- **Builds on:** [ADR-0015](0015-runnable-example-project.md) — the example project;
  [ADR-0014](0014-user-and-tool-permissions.md) — the `.user`-touching tools

## Context

Live testing through MCP Inspector found that calling `current_username` on the **open**
`/mcp/` endpoint crashed with `'ASGIRequest' object has no attribute 'user'`. The example
settings were minimal to a fault: no `MIDDLEWARE` at all, so outside the endpoints where
`mcp_view(user_resolver=…)` sets the user, `request.user` simply did not exist.

Real Django projects virtually always run `AuthenticationMiddleware`, under which an
unauthenticated request carries `AnonymousUser` and `get_username()` returns `""`. The
crash was therefore an example-project artefact — but a misleading one, because the
example doubles as the package's demonstration of what downstream code should look like,
and it was demonstrating an environment no consumer would run.

## Decision

`example/settings.py` gains the standard pair — `SessionMiddleware` +
`AuthenticationMiddleware` (and `django.contrib.sessions`) — so the example behaves like
the projects the package will actually be installed into: `.user` exists everywhere,
anonymous on the open endpoints, resolved on the `user_resolver` ones. A regression test
pins the anonymous case (`current_username` on `/mcp/` → `""`, not an error), and
`docs/usage.md` now states the contract explicitly: `request.user` requires either the
project's auth middleware or a `user_resolver`.

Alongside this, `example/README.md` was rewritten as a reproduction-grade walkthrough of
the full manual test plan (Inspector setup including the protocol-era gotcha, the
elicitation and permission cycles, the statelessness curl proofs), recording the July 2026
client reality: Claude Code speaks the stateless transport but not yet SEP-2322
elicitation, so **MCP Inspector with Protocol Era = Modern is the reference client** for
verifying the package.

## Consequences

- The tests inherit the example settings, so the whole suite now runs with the standard
  middleware — closer to consumer reality for every test, not just the new one.
- The example database gains the `sessions` migration; `just demo` re-runs `migrate`
  idempotently, so existing checkouts self-heal.
- A tool touching `.user` in a project *without* auth middleware still raises
  `AttributeError`; that is now a documented contract rather than a surprise.
