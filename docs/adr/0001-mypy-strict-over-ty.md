# ADR-0001: Use mypy strict as the type-checking gate, not ty

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** none — first ADR for type checking

## Context

The repo was scaffolded from `audreyfeldroy/cookiecutter-pypackage`, which ships
[ty](https://github.com/astral-sh/ty) (Astral's type checker) as the `typecheck`
dependency group and runs `uv run ty check .` in CI. The project build plan, by
contrast, specified mypy. Nothing had reconciled the two.

The choice matters more here than in an application, for one reason: this package
ships `src/django_stateless_mcp/py.typed`. Under PEP 561 that publishes our
annotations as part of the API — downstream consumers type-check *their* code
against *our* types, using whichever checker they run. Our annotations are a
promise, not an internal convenience.

## What we considered

### ty (the scaffold's default)

Fast — 10–60x mypy on cold checks — and from the same vendor as ruff and uv,
which we already use.

Rejected as the gate for three reasons:

1. **It is beta.** Astral recommend it for "motivated users willing to report
   issues", and it scores roughly 15% on the Python typing-spec conformance
   suite (Pyrefly ~58%). A gate should be an authority.
2. **It cannot use `django-stubs`.** django-stubs is a mypy *plugin*; the current
   guidance is explicit that projects depending on it should wait for ty's stable
   release. This is a Django package, so that limitation is not incidental.
3. **It is not what our consumers run.** Publishing `py.typed` and validating
   only with a low-conformance checker risks shipping annotations that pass for
   us and fail for users on mypy or pyright.

### Both, as dual gates

Rejected. Two checkers with different conformance levels produce contradictory
diagnostics, and there is no principled way to decide which one is right when
they disagree. Any ignore comment then has to satisfy both.

### mypy strict (chosen)

Slower, but authoritative, plugin-capable, and the de facto standard our
downstream users check against.

It is also what the exemplar does. `adamchainz/django-crawl` — pushed
2026-07-27, the closest analogue to this package — runs mypy `strict` with
`django-stubs==6.0.5` via pre-commit, with the same three extra error codes
adopted below. No ty.

## Decision

**mypy `strict` is the type-checking gate.** ty is removed from the `typecheck`
dependency group and from CI.

Configuration, adopted from `django-crawl`:

```toml
[tool.mypy]
mypy_path = "src/"
namespace_packages = false
strict = true
warn_unreachable = true
enable_error_code = ["ignore-without-code", "redundant-expr", "truthy-bool"]

[[tool.mypy.overrides]]
module = "tests.*"
allow_untyped_defs = true
```

Nothing prevents a developer running ty locally for speed; it simply is not the
gate, and it does not get a CI job.

## Consequences

- CI gains a slower type-check job. Acceptable: correctness of a published type
  contract beats seconds of CI.
- `tests/__init__.py` was added so the `tests.*` override actually matches.
  Without it mypy names the module `test_django_stateless_mcp` and the override
  silently does nothing — a trap worth recording.
- The strict settings immediately earned their place: `truthy-bool` rejected the
  scaffold's placeholder `assert django_stateless_mcp`, an assertion that cannot
  fail. It now asserts something real. This is precisely the class of empty test
  the build plan criticises in `django-mcp-server`.
- **`django-stubs` is deliberately deferred.** Its mypy plugin requires a
  `django_settings_module`, and this package has no Django code or test settings
  yet. It lands with the Django test matrix, which is the next planned step.
  Until then mypy runs without the plugin.

## Follow-ups

- Add `django-stubs` + plugin config alongside the Django/tox matrix.
- Consider a consumer-shaped module type-checked in CI with **both** mypy and
  pyright, to verify the published `py.typed` contract from the outside. Pyright
  matters because Pylance is what most users have in their editor.
