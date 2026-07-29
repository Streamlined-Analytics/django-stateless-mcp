# ADR-0005: Depend on mcp 2.0.0 via a time-boxed exclude-newer exemption

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0003](0003-real-dependencies-drop-scaffold.md) — packaging

## Context

The package is built on the MCP Python SDK v2. `mcp==2.0.0` reached GA on
**2026-07-28**, one day after the 2026-07-28 spec went final, and `mcp-types`
— which v2 split into a separate distribution — shipped 2.0.0 the same day.

The project runs a supply-chain quarantine, `exclude-newer = "1 week"`, so uv
refuses to resolve anything published in the last seven days. Anchored at
**2026-07-22**, that made the SDK invisible:

```
× No solution found ...
╰─▶ Because only mcp<=2.0.0b2 is available and your project depends on
    mcp>=2,<3, we can conclude that your project's requirements are
    unsatisfiable.
```

The guard was working exactly as designed. It simply collided with the fact that
this package exists *because* of a spec that went final last week — the whole
premise is being early.

[ADR-0003](0003-real-dependencies-drop-scaffold.md) deferred the dependency on
the grounds that no code imported it yet. That is no longer the position:
implementation starts now, so the SDK has to be resolvable.

## What we considered

### Wait until ~2026-08-04

Zero risk, and the window clears by itself. Rejected because it blocks the start
of implementation for a week, against a first-mover window that is the reason for
the project's timing.

### Pin the beta, `mcp==2.0.0b2`

Resolvable today. Rejected outright: the build plan is explicit that the package
targets **GA**, and writing the ASGI bridge against a beta that GA has already
superseded means writing code twice and testing against a wire format nobody
will run.

### Drop `exclude-newer` globally

The originally suggested route. Rejected as disproportionate — it removes the
quarantine from **every** dependency, roughly forty packages, to solve a problem
with two of them. The blast radius is the entire dependency tree, and there would
be nothing recording that the guard was ever meant to come back.

### Per-package exemption (chosen)

`exclude-newer-package` narrows the hole to exactly the packages we have
reasoned about:

```toml
exclude-newer = "1 week"
exclude-newer-package = { mcp = "2026-07-29T23:59:59Z", mcp-types = "2026-07-29T23:59:59Z" }
```

Everything else stays quarantined.

## Decision

Depend on `mcp>=2,<3`, with a **time-boxed per-package exemption** for `mcp` and
`mcp-types`, tracked in **issue #12** and to be removed **on or after
2026-08-04**.

This is an accepted risk, not an oversight: for roughly a week, two packages are
installed without the seven-day soak that protects the rest of the tree. It is
bounded in scope, bounded in time, and recorded in three places — here, in the
issue, and in a comment beside the setting.

## Consequences

- Implementation can begin against the GA SDK immediately.
- **The exemption must cover both packages.** Exempting only `mcp` still fails,
  because `mcp==2.0.0` requires `mcp-types==2.0.0` — a trap worth recording,
  since the error names only `mcp-types` and reads like an unrelated problem.
- Resolved versions: `mcp 2.0.0`, `mcp-types 2.0.0`, `django 6.0.7`.
- If issue #12 is not actioned, the exemption becomes permanent by neglect —
  which is the failure mode this ADR exists to make visible.

## Also settled here

**Django 6.0 is supported, not merely tested.** The floor stays at 5.2 LTS
(supported to April 2028) and 6.0 (to April 2027) is a first-class target;
both appear in the classifiers and both will appear in the test matrix.
