# ADR-0003: Declare real dependencies and delete the scaffold CLI

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** none — first ADR for packaging

## Context

The repository was generated from a framework-agnostic Python package template.
Its defaults survived untouched, so the distribution described itself as
something it is not:

- `dependencies = ["typer", "rich"]` — no Django, no `mcp`. Installing the
  package gave you a CLI toolkit.
- A console entry point, `django_stateless_mcp = "django_stateless_mcp.cli:app"`,
  which makes no sense for a Django library.
- `src/django_stateless_mcp/` contained only `cli.py`, `utils.py` and
  `__main__.py`, all placeholders. `utils.do_something_useful()` printed
  *"Replace this with a utility function"*.
- Classifiers named neither Django nor any Python version.

The placeholder modules were not merely untidy. `docs/reference.md` renders
`::: django_stateless_mcp` through mkdocstrings, so the moment Read the Docs
builds, `do_something_useful()` becomes the package's **published API
reference**.

## Decision

**Django 5.2 LTS is the supported floor.** Declared as `django>=5.2`.

Django 4.2 reached end of life on 7 April 2026 and 5.1 in December 2025, so only
5.2 LTS (to April 2028) and 6.0 (to April 2027) are supported upstream. The
original build plan specified a "Django 4.2 / 5.x" matrix; that is now out of
date, and shipping support for an end-of-life Django would mean inheriting a
migration cost with no security coverage. A new package has no back-compatibility
obligation, so it starts at the current LTS.

The scaffold CLI — `cli.py`, `utils.py`, `__main__.py` and the `[project.scripts]`
entry point — is **deleted**. Classifiers now name Django 5.2 and 6.0, and Python
3.12–3.14.

### `mcp` is deliberately not declared yet

The package is built on `mcp>=2,<3`, and `mcp==2.0.0` went GA on **2026-07-28**.
The project sets `exclude-newer = "1 week"` as a supply-chain quarantine, which
currently anchors at **2026-07-22** — so the resolver cannot see 2.0.0 at all,
and fails with *"only mcp<=2.0.0b2 is available"*.

The options were to weaken the quarantine with an `exclude-newer-package`
override, to pin the beta, or to wait. We wait. No code imports `mcp` yet, so
declaring it buys nothing today, and the window clears on its own around
**2026-08-04**. Suppressing a supply-chain guard to add an unused dependency is
a bad trade — and the guard doing exactly its job on a one-day-old release is
evidence it works, not that it is misconfigured.

`mcp>=2,<3` lands with the first code that imports it.

## Consequences

- The distribution now installs Django and nothing spurious.
- The published API reference is empty rather than wrong. It stays empty until
  there is real API to document, which is the honest state.
- `requires-python` stays `>=3.12`, which is also Django 6.0's floor.
- **The first code PR must add `mcp`.** If it is written before ~2026-08-04, that
  PR has to solve the quarantine problem rather than inherit a solution.

## Follow-ups

- `README.md` is stale: it advertises Zensical and a GitHub Pages URL, and its
  Features section is `TODO`. It is also where the spec-version support policy
  belongs.
- `CHANGELOG/0.1.0.md` describes the scaffold that this ADR removes — it claims
  a Typer CLI and `ty`. It has never been published to PyPI, so it can be
  corrected rather than superseded.
