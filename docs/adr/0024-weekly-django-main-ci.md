# ADR-0024: Weekly advisory CI run against Django git main

- **Status:** Accepted
- **Date:** 2026-07-31
- **Builds on:** [ADR-0006](0006-test-matrix.md) — the test matrix and the advisory-lane precedent

## Context

The matrix (ADR-0006) covers both released Django lines (5.2 LTS, 6.0) and, per
PR, an advisory lane against the `mcp` SDK's git main. The package's other
foundation — Django itself — had no pre-release coverage: the first contact with
Django 6.1 would be its alpha, with every deprecation arriving at once. Adam
Johnson's packages and the Django Commons practices both run against Django
main continuously for exactly this early-warning reason.

The one real choice was **where the run lives**:

1. **Per-PR, like `mcp-latest`.** Rejected. The SDK is pre-1.0-culture, moves
   weekly, and is this package's single upstream coupling risk — per-PR is
   proportionate there. Django main moves conservatively under a deprecation
   policy; per-PR coverage would add three matrix jobs to every push for a
   signal that changes at most weekly, and an upstream breakage would sit
   red on unrelated PRs for days.
2. **A weekly scheduled workflow.** Chosen. Breakage surfaces within a week —
   ample against Django's release cadence — and PR CI stays exactly as it was.

## Decision

A `djangomain` tox factor (`django @ git+https://github.com/django/django@main`,
paired with `mcp-release` to isolate the variable) and a
`.github/workflows/django-main.yml` running
`py{312,313,314}-djangomain-mcp-release` every Monday 06:00 UTC, plus
`workflow_dispatch` for on-demand runs. The envs are deliberately **not** in
tox's `env_list`: `ci.yml` selects by factor filter (`-f py312 mcp-release`),
which would otherwise sweep the djangomain envs into every PR — the weekly
workflow addresses them by explicit `-e` name instead. The existing
`PYTHONDEVMODE` + deprecations-as-errors tox setup does the real work: the run
fails on the *next* Django's deprecation warnings, not just hard breakage.

Verified before merge: `tox run -e py314-djangomain-mcp-release` passes locally
against Django main (53 passed).

## Consequences

- Advisory by nature: a red weekly run means "Django main moved", not "a PR is
  wrong" — nothing gates on it, and GitHub notifies on scheduled-run failure.
- GitHub disables cron workflows after ~60 days without repository activity;
  a dormant period needs a manual re-enable (or any commit).
- When Django 6.1 reaches beta/RC, the matrix decision (add `django61` as a
  released-line factor) is a follow-up ADR building on ADR-0006, not this one.
