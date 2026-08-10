# 0038. The example's middleware imports `MiddlewareMixin` version-conditionally

- **Status:** Accepted
- **Date:** 2026-08-10
- **Deciders:** Ben Atkinson
- **Feature / area:** test suite / example project
- **Builds on:** ADR-0032 — the decision to model django-prometheus with in-repo `MiddlewareMixin` classes
- **Supersedes / Superseded by:** none

## What problem were we trying to solve?

The weekly Django-main run (ADR-0024) has failed for two consecutive Mondays —
2026-08-03 and 2026-08-10 — on all three interpreters, 57 failed / 16 passed.
The count is noise: one deprecation accounts for every failure.

```
django.utils.deprecation.RemovedInDjango71Warning: Importing MiddlewareMixin from
django.utils.deprecation is deprecated. Import from django.middleware.MiddlewareMixin instead.
```

Django main (`6.2.0 alpha`) moved `MiddlewareMixin` to `django.middleware` and
left a warning shim behind at the old path. `example/middleware.py` imports from
that old path, `example/settings.py` lists both bracket classes in `MIDDLEWARE`,
and the tox envs run pytest under `-W error::DeprecationWarning` — so the shim's
warning becomes an error during middleware loading, and every test that builds a
response dies before it asserts anything.

Nothing in `src/` imports `MiddlewareMixin`; the released matrix (5.2, 6.0, 6.1)
is unaffected. The removal is not due until 7.1, so this is exactly the advisory
early warning ADR-0024 was built to surface — but a permanently red leg teaches
us to ignore it, which defeats the purpose.

## What did we try?

### Attempt 1 — move to the new path outright   <!-- ❌ rejected -->

`from django.middleware import MiddlewareMixin`. Rejected: `django/middleware/__init__.py`
is empty in 6.1 and every earlier release, so this breaks the three supported
lines to fix the unsupported one.

### Attempt 2 — silence the warning in tox   <!-- ❌ rejected -->

A `-W ignore::RemovedInDjango71Warning` filter. Rejected: it turns the one leg
whose whole job is to shout about deprecations into a leg that swallows this
class of them, and it would mask the *next* move as well.

### Attempt 3 — `try: … except ImportError:`   <!-- ❌ rejected -->

Works at runtime and needs no version literal, but states no removal condition —
nothing tells a future reader when the fallback may go, so it survives forever.

### Attempt 4 — a `django.VERSION` branch   <!-- ✅ chosen -->

```python
if django.VERSION >= (6, 2):
    from django.middleware import MiddlewareMixin  # type: ignore[attr-defined]
else:
    from django.utils.deprecation import MiddlewareMixin
```

The version literal is the deletion condition: when the supported floor reaches
6.2, the `else` branch goes.

## What did we land on, and why?

Attempt 4, in `example/middleware.py`. The `# type: ignore[attr-defined]` is
required because django-stubs ships an empty `django-stubs/middleware/__init__.pyi`;
`warn_unused_ignores` (via `strict`) will fail the build once the stubs catch up,
which is the signal to revisit.

No matrix change accompanies this. Django main is 6.2-alpha and 6.1 — already a
matrix factor since ADR-0025 — is the latest release, so there is no new released
line to add. A `django62` factor lands when 6.2a1 reaches PyPI, on the ADR-0025
pre-release-floor pattern.

## Consequences

- The weekly advisory leg goes green again, so a future failure means something new.
- `example/middleware.py` now carries a version branch — the first in the
  repository — and one `type: ignore` that is expected to become unused.
- No `src/` change, no public-API change, and no CHANGELOG entry: the example
  project is not part of the published wheel.
