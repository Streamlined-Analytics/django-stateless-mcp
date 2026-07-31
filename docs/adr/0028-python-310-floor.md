# ADR-0028: Python floor lowered to 3.10, tracking Django 5.2's own support

- **Status:** Accepted
- **Date:** 2026-07-31
- **Builds on:** [ADR-0003](0003-real-dependencies-drop-scaffold.md) — which set the original 3.12 floor alongside the Django 5.2 floor

## Context

The 3.12 floor from ADR-0003 was a convenience choice, not a constraint: the
`mcp` SDK requires only 3.10, Django 5.2 LTS supports 3.10–3.13, and a syntax
audit found nothing 3.12-only in the package (every module uses
`from __future__ import annotations`). Meanwhile the audience most likely to
adopt the package — teams adding MCP to an existing Django 5.2 LTS project —
is precisely the audience still on Python 3.10/3.11. The community norm (Adam
Johnson's packages, Django Commons) is to support every Python that the
supported Djangos support.

## Decision

`requires-python = ">=3.10"`, with 3.10/3.11 classifiers. The matrix follows
Adam Johnson's shape: `py{310,311}` pair **only with `django52`** (Django 6.0+
requires 3.12), and only with the released SDK — the git-main advisory lane
stays 3.12+. CI's Test matrix grows to five interpreter versions; mypy is
pinned to `python_version = "3.10"` so 3.12-only stdlib usage fails
type-checking rather than surviving until a 3.10 user hits it, and ruff's
pyupgrade rules now target 3.10 automatically via `requires-python`.

Verified before merge: the full suite passes on CPython 3.10 and 3.11 against
Django 5.2 (53 passed each, warnings-as-errors including ResourceWarning),
and mypy is clean under 3.10 semantics.

## Consequences

- The floor now moves with Django's, not ours: 3.10/3.11 support ends when
  Django 5.2 LTS does (April 2028) or when the package drops 5.2 — whichever
  comes first, per the April LTS-season review.
- New code must stay 3.10-compatible (no `type` aliases, no 3.12-only stdlib);
  mypy at 3.10 semantics and the py310 CI lane both enforce it mechanically.
- `uv.lock` now carries forked resolutions (Django 5.2 for <3.12, 6.0 for
  >=3.12) and the 3.10 backport shims (`exceptiongroup`, `tomli`) as
  marker-gated entries.
- Takes effect on PyPI at the next release; the changelog entry for that
  release must call out the widened floor.
