# ADR-0027: Tooling adoptions from the django-linear-migrations / django-mysql review

- **Status:** Accepted
- **Date:** 2026-07-31
- **Builds on:** [ADR-0004](0004-pre-commit.md) — the pre-commit setup this extends

## Context

A structured review of Adam Johnson's django-linear-migrations and django-mysql
(the reference packages named in mentoring, 2026-07-31) found the repos largely
convergent — our conventions derive from his — with six deltas. Four were
adopted here; two were declined: raising coverage `fail_under` to 100 (a
commitment deferred, not a tweak), and lowering the Python floor (a support-
policy question taken separately).

## Decision

1. **`-W error::ResourceWarning`** joins the tox test command. Leaked sockets,
   files and unclosed DB connections now fail the suite — precisely this
   package's risk profile (cf. ADR-0021). The full matrix passes with it on.
2. **The `typos` pre-commit hook** (crate-ci/typos) — mechanical spell-checking
   of the whole tree. Zero findings on adoption.
3. **`skip: [mypy]` in the pre-commit.ci block** — the monthly autoupdate was
   already configured, but the local `uv run mypy` hook (ADR-0004) cannot run
   on pre-commit.ci's infrastructure and would fail every run. With the skip in
   place, installing the pre-commit.ci GitHub App is safe (a manual, UI-only
   step; CI's own mypy job still gates every PR).
4. **All hook revs frozen to commit SHAs** (`pre-commit autoupdate --freeze`) —
   a moving tag can be re-pointed at malicious code, a SHA cannot; consistent
   with the exclude-newer supply-chain posture. pre-commit.ci's autoupdate
   preserves the frozen style.

## Consequences

- Hook updates now arrive as explicit SHA bumps (via autoupdate or
  pre-commit.ci PRs), never silently.
- A future genuine typo suppression belongs in a `.typos.toml`, not in
  disabling the hook.
- The declined items stay visible in the mentoring session note; the Python
  floor question is being assessed separately.
