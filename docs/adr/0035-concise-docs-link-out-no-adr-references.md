# ADR-0035: User-facing docs stay concise, link out, and never cite ADRs

- **Status:** Accepted
- **Date:** 2026-08-05
- **Builds on:** [ADR-0023](0023-adrs-unpublished-from-docs-site.md) (ADRs are
  contributor-facing, kept in-repo only), [ADR-0029](0029-benefits-led-messaging.md)
  (benefits-led messaging), [ADR-0030](0030-quick-start-first-example-guide.md)
  (the example README's quick-start shape)

## Context

A full documentation review (Read the Docs, READMEs, GitHub, PyPI) was run
against the question "is this too verbose?", grounded first in external
research on what good documentation looks like. The research landed on the
[Diátaxis](https://diataxis.fr/) framework: docs serve four needs — tutorial,
how-to, reference, explanation — and each has its own conciseness rule.
Verbosity is usually a *mixing* problem: pages bloat when explanation leaks
into how-to material, not because any single type is too long.

Measured against that, the structure was already right (the example README is
the tutorial, `usage.md` the how-to, mkdocstrings the reference,
`why-stateless.md` the explanation), but the review found:

- **The spec was never linked.** "2026-07-28" appeared roughly a dozen times
  across every surface with no hyperlink anywhere; `why-stateless.md` cited
  SEP-2567/2575/2322 by bare number. Restating what a linked source owns is
  also where several of the verbosity patches came from.
- **Explanation had leaked into `usage.md`** — multi-sentence rationale for
  the CSRF and `ATOMIC_REQUESTS` exemptions, and a hint-by-hint gloss of
  `ToolAnnotations` whose semantics the spec schema (already linked) owns.
- **Pure boilerplate survived from the cookiecutter** — `installation.md`'s
  "From source" tarball recipe, CONTRIBUTING's "Types of Contributions"
  section (which also claimed Python "3.12, 3.13, 3.14" against a real floor
  of 3.10).
- **ADR links had crept onto user-facing surfaces** — eleven across
  `docs/index.md`, `usage.md`, the long-running-jobs recipe, and the example
  README — despite ADR-0023 already excluding `docs/adr/` from the built
  site. Every one was a trailing citation on prose that already stated the
  reason, so they added maintenance surface without adding information.
- **Two README relative links** (`example/README.md`, `ARCHITECTURE.md`)
  break on PyPI, which resolves them against `pypi.org`.

## Decision

User-facing documentation answers **how to use** and **why to use**, and links
out for everything another project owns:

- Every surface links "2026-07-28" to the spec (or its changelog) at first
  mention; `why-stateless.md` links each SEP to its canonical document in the
  spec repository. Semantics the spec owns (e.g. `ToolAnnotations` hints) are
  linked, not restated.
- **ADRs are never referenced from user-facing surfaces** (Read the Docs
  pages, README, example README). The "why" is stated inline in one
  self-contained sentence; readers wanting the decision history can find
  `docs/adr/` in the repository. This completes ADR-0023: contributor
  surfaces (ARCHITECTURE.md, CONTRIBUTING.md, the ADRs themselves) keep their
  ADR links — chaining decisions there is the point of the system.
- Explanation stays out of how-to pages: `usage.md` rationale is compressed
  to single sentences, and cookiecutter boilerplate with no audience is
  deleted rather than trimmed.
- README links that must survive PyPI's rendering are absolute GitHub URLs.
- Dated client-support claims ("as of July 2026") were re-verified during the
  review and remain accurate; they keep their explicit dates so future staleness
  is visible.

Repository metadata was aligned in the same pass: homepage set to the docs
site, discovery topics added, and the unused wiki disabled so the docs have a
single home.

## Consequences

- `usage.md`, `installation.md`, and CONTRIBUTING shrink with no loss of
  stated rationale; the README's "Why use this" converges on
  `docs/index.md`'s bullet form, reducing the hand-synced near-duplicate that
  ADR-0029 accepted.
- Removing an ADR citation is now the default when editing user-facing docs;
  adding one is a review flag.
- The one-sentence inline "why" must genuinely carry the reason — if it
  cannot, the material belongs in `why-stateless.md`, not in a citation.
