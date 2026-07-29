# ADR-0004: Add pre-commit, with mypy as a local hook

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0001](0001-mypy-strict-over-ty.md) — type checking

## Context

The repository had **no `.pre-commit-config.yaml` at all**. Nothing ran ruff,
mypy, or any file hygiene check before a commit; the only gate was CI, which
means feedback arrived minutes after a push rather than seconds before one.

The project's own testing plan assumes "pre-commit + mypy", so this was a stated
requirement that had simply never been implemented.

## Decision

Adopt pre-commit, modelled on `adamchainz/django-crawl` — the closest
well-maintained analogue to this package — minus its reStructuredText-specific
hooks, which do not apply to a Markdown docs tree.

| Hook | Why |
|---|---|
| `pre-commit-hooks` basics | File hygiene: large files, merge conflicts, TOML/YAML validity, trailing whitespace |
| `pyproject-fmt` | Normalises and sorts `pyproject.toml`, keeping classifiers in step with `requires-python` |
| `ruff-check --fix`, `ruff-format` | Same linter and formatter as CI, applied before the commit |
| `blacken-docs` | Formats code blocks *inside* documentation, so examples cannot rot into unformatted code |
| `django-upgrade --target-version 5.2` | Rewrites deprecated Django idioms, matching the floor set in [ADR-0003](0003-real-dependencies-drop-scaffold.md) |
| `mypy` (local) | Type gate, per ADR-0001 |

### mypy runs as a `local` hook, not `mirrors-mypy`

The conventional approach passes third-party stubs to `mirrors-mypy` through
`additional_dependencies`, because the hook runs in its own isolated environment.
That means maintaining a second, hand-written copy of the dependency list which
drifts from `pyproject.toml` silently — and it is exactly the kind of duplication
that goes stale unnoticed.

Instead the hook runs `uv run mypy` against the project environment, so it type
checks with the real resolved dependencies and needs no duplicated list. It also
runs precisely what CI runs, so the two cannot disagree.

The trade-off is that the hook needs `uv` on `PATH`, which is already true for
every other workflow in this repo.

`pyproject-fmt` is pinned with `max_supported_python = "3.14"` so it does not
start proposing classifiers for unreleased Python versions.

## Consequences

- `pre-commit` is added to the `lint` dependency group, so
  `uv run pre-commit run --all-files` works without a global install.
- Running it over the existing tree reformatted `pyproject.toml` substantially —
  a one-off cost of adopting `pyproject-fmt` on a file that had never been
  normalised.
- Doc **link** checking is still absent. `blacken-docs` covers code blocks only,
  and a broken cross-reference will not be caught until the `mkdocs --strict`
  build fails.
