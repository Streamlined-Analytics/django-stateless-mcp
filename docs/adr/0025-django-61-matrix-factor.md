# ADR-0025: Django 6.1 joins the test matrix at release candidate

- **Status:** Accepted
- **Date:** 2026-07-31
- **Builds on:** [ADR-0024](0024-weekly-django-main-ci.md) — which anticipated this decision; matrix shape from [ADR-0006](0006-test-matrix.md)

## Context

Django 6.1 reached rc1 on 2026-07-22 (a1 in May, b1 in June; final expected
August 2026 on the 8-month cadence). The weekly django-main run (ADR-0024) no
longer covers it: once `stable/6.1.x` branched, `main` became 6.2-dev, leaving
the actual next release untested — precisely the gap between the released-line
factors (5.2, 6.0) and the git-main canary.

The choice was whether pre-release Django runs **blocking in the per-PR
matrix** or advisory like the git-main lane. Blocking, because the situations
differ: git main is a moving target that can break through no fault of ours,
but an RC is API-frozen under Django's own release policy — a failure against
it is a real forward-compatibility bug in this package that would otherwise
surface at 6.1 final. This is also Adam Johnson's practice across his packages
(add the upcoming Django at pre-release, blocking), and the matrix already runs
with deprecations-as-errors, so the lane catches 6.1's deprecations before
day one.

## Decision

`django61` becomes a released-line factor: `env_list` grows to
`py{312,313,314}-django{52,60,61}-mcp{-release,-latest}`, with
`django61: django>=6.1b1,<6.2`. The pre-release floor makes the specifier
resolve pre-releases (rc1 today) and **roll to 6.1 final automatically** when
it lands — no follow-up edit. `ci.yml` needs no change: its factor filters
(`-f py312 mcp-release`) pick the new envs up.

Verified before merge: `py314-django61-mcp-release` passes locally against
6.1rc1 (53 passed, deprecations-as-errors).

## Consequences

- Per-PR CI grows from 6 to 9 env runs across the three Test jobs (and the
  advisory mcp-latest job likewise); runtime cost is small since envs share
  the built wheel.
- An RC regression in Django itself would block PRs until pinned around —
  accepted as rare, and pulling the factor is a one-line revert.
- **At 6.1 final** (not before): add the `Framework :: Django :: 6.1` trove
  classifier and update the supported-versions statements in README/docs —
  classifiers for unreleased Djangos are rejected by PyPI, which is why this
  ADR deliberately touches neither.
- The support-policy question of *dropping* 5.2 LTS does not arise until
  April 2027 (6.2 LTS); revisit then per the ADR-0024 April reminder.
