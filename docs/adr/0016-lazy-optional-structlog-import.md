# ADR-0016: Lazy import for the optional structlog dependency

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0013](0013-observability-middleware.md) — made structlog an optional
  extra

## Context

The 0.1.0 release shipped broken for its headline install path. A bare
`pip install django-stateless-mcp` succeeded, but `import django_stateless_mcp` then raised
`ModuleNotFoundError: No module named 'structlog'`: `__init__.py` eagerly re-exported
`StructlogRequestLogger`, whose module does `import structlog` at the top — and ADR-0013
had deliberately made structlog an optional extra (`django-stateless-mcp[structlog]`), so a
bare install does not have it.

No environment we test in could see this. The dev dependency group installs structlog, so
every pytest run, every tox cell, and the whole CI matrix imported the package with the
extra effectively always on. The bug only existed for a real downstream consumer, and was
caught minutes after publishing by a clean-venv install verification.

Two fixes were considered:

1. **Promote structlog to a hard dependency.** One line, but it reverses ADR-0013's
   decision and taxes every consumer who never touches the logging middleware.
2. **Keep the extra optional and import it lazily.**

## Decision

Option 2. `__init__.py` re-exports `StructlogRequestLogger` under `TYPE_CHECKING` (so mypy
and mkdocstrings/griffe still see the public symbol) and resolves it at runtime through a
PEP 562 module `__getattr__`; the name stays in `__all__`. `logging.py` wraps its
`import structlog` so a missing module re-raises as an `ImportError` that names the fix:
install `django-stateless-mcp[structlog]`.

The regression tests run in a subprocess with structlog blocked (`sys.modules["structlog"]
= None`), proving both that the bare package imports and that reaching the logger without
the extra fails with the helpful message. In-process tests pin that the lazy attribute is
the real class and that the hook does not swallow genuine `AttributeError`s.

0.1.0 was yanked on PyPI; the fix ships as 0.1.1.

## Consequences

- Any future optional dependency must follow this pattern: nothing reachable from a bare
  `import django_stateless_mcp` may import an extra at module level, and the subprocess
  test is the enforcement shape to copy.
- The module `__getattr__` weakens mypy's checking of *unknown* attributes on the package
  for consumers (unknown names now type as the hook's return rather than erroring).
  Accepted: one lazy symbol, and the `TYPE_CHECKING` re-export keeps the real one fully
  typed.
- Clean-venv install verification (`uv venv` + install from PyPI + import) is now part of
  the release routine — CI cannot catch what its own environment hides.
