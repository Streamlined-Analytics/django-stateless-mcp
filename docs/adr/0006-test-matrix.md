# ADR-0006: Test across Django 5.2 and 6.0, with an advisory SDK-main env

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0003](0003-real-dependencies-drop-scaffold.md) — packaging,
  [ADR-0005](0005-temporary-exclude-newer-exemption.md) — the mcp dependency

## Context

The package claimed `Framework :: Django :: 5.2` and `:: 6.0` in its classifiers
and declared `django>=5.2`, but **tested neither deliberately**. CI ran
`uv run coverage run -m pytest`, which resolves from `uv.lock` — so every job
tested whatever was pinned there, currently Django 6.0.7. Three Python versions,
one Django version.

Django 5.2 LTS, the declared floor and the version most production Django runs
on, had never been executed once.

There was also no Django test infrastructure at all: no `pytest-django`, no
settings module, no URLconf. Any test touching a request or a setting would have
failed with `ImproperlyConfigured`, so the infrastructure had to exist before the
first line of transport code.

## Decision

### A test project inside `tests/`, not an example app

```
tests/
  settings.py   # sqlite :memory:, INSTALLED_APPS includes django_stateless_mcp
  urls.py       # URLconf the MCP view will mount into
  test_*.py     # assertions about the package
```

This is the `django-crawl` shape: a crawler needs pages to crawl, and an MCP
package needs an app exposing tools. The distinction that matters is **the
fixtures live in `tests/` and the assertions are about the package**.

The project's own analysis criticises `django-mcp-server` for burying its only
real tests in `examples/mcpexample/bird_counter/tests.py` — testing the example
rather than the package. That is a different thing from this, and the difference
is where the tests live and what they assert. A separate human-facing `example/`
demo may be added later; it will not be the test vehicle.

### tox owns the dependency axes; GitHub Actions owns Python

```ini
env_list = py{312,313,314}-django{52,60}-mcp{-release,-latest}
```

Twelve environments, but CI stays at three jobs per channel: the workflow
matrixes over Python only and calls `tox run -f py313 mcp-release`, letting tox
fan out Django versions inside. This is Adam Johnson's structure, and it keeps
the checks list readable as axes are added.

WSGI-versus-ASGI is deliberately **not** a matrix axis. Both must be exercised,
but as parametrised fixtures inside the tests — doubling twelve environments to
twenty-four to express it would be a bad trade.

### `mcp-latest` is advisory

An env tracking the SDK's git main is the early-warning system for a spec that
broke compatibility last week. It runs as a **separate job with
`continue-on-error: true`**, excluded from the `all-checks-pass` aggregator, so
it can never block a merge.

The reasoning: upstream can break us through no fault of our own, and a required
check that is red for reasons nobody can fix trains people to ignore CI. An
advisory signal that is read is worth more than a blocking one that is muted.

### Deprecation warnings are errors

```
python -W error::DeprecationWarning -W error::PendingDeprecationWarning -m pytest
```

with `PYTHONDEVMODE=1`. This is what actually catches 5.2-versus-6.0 drift
*early*: anything 5.2 deprecates and 6.x removes fails the build while the code
is being written, rather than when a user upgrades. It applies equally to the
SDK, which deprecates sampling and roots in v2.

## Consequences

- **Django 5.2.16 now passes**, verified locally — the first time that version
  has ever been exercised in this repo.
- `django-stubs` is added and the mypy plugin enabled. [ADR-0001](0001-mypy-strict-over-ty.md)
  deferred it for want of a `django_settings_module`; `tests/settings.py` supplies
  it, so the deferral is now closed.
- CI grows from 3 test jobs to 6, of which 3 cannot fail the build.

## Traps worth recording

- **`#` starts a comment in `tox.ini`.** A dependency written as
  `...@main#subdirectory=src/mcp-types` is silently truncated at the `#`,
  producing a confusing "conflicting URLs" resolution error. In this case the
  line was unnecessary anyway — `mcp` from git main declares `mcp-types` with the
  correct subdirectory itself — so it was removed rather than escaped.
- **pytest-django resolves settings before pytest touches `sys.path`.** It needs
  both `django_find_project = false` and `pythonpath = ["."]`; with only the
  former it fails with a bare `ImportError: No module named 'tests'`.
- pytest 9 reads a native `[tool.pytest]` table, so `ini_options` nesting is no
  longer required.

## Follow-ups

- Add a `django-latest` env tracking Django's git main, if the same early-warning
  argument is wanted for the framework as well as the SDK.
- Parametrise WSGI/ASGI once there is a view to exercise.
