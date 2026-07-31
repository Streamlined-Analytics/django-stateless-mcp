# ADR-0023: ADRs live in the repository only, not on the docs site

- **Status:** Accepted
- **Date:** 2026-07-31
- **Builds on:** [ADR-0002](0002-docs-on-read-the-docs.md) — docs hosted on Read the Docs

## Context

Since ADR-0002 the Read the Docs site carried a "Decisions" section publishing
every ADR, on the theory that the reasoning helps someone extending the package.
In practice the section aged badly on two axes:

- **Audience mismatch.** The site is for people *using* the package; ADRs are
  engineering history for people *changing* it. Twenty-plus records of internal
  tooling decisions (pre-commit, test matrices, dependency exemptions) sat in the
  reader's navigation next to Installation and Usage, outnumbering the user-facing
  pages.
- **A hand-maintained nav that rotted immediately.** mkdocs requires each page
  listed in `nav:`; the list was last touched at ADR-0015, so ADR-0016–0022 were
  built but unreachable, and every strict build warned about them. The maintenance
  cost bought nothing a GitHub link doesn't.

An auto-globbing nav (the literate-nav plugin) was considered as a fix for the
rot alone — rejected because it adds a plugin to solve the symptom while leaving
the audience mismatch in place.

## Decision

`docs/adr/` is excluded from the mkdocs build (`exclude_docs`), and the
"Decisions" nav section is gone. The ADRs themselves are unchanged and stay
where the workflow requires them — `docs/adr/` in the repository, reviewed in
the same PR as the code they explain. The published site links once to the
GitHub `docs/adr/` tree for anyone who wants the history; the one in-content
ADR reference (usage → ADR-0007) became a GitHub link.

## Consequences

- Old Read the Docs builds still serve the ADR pages; only builds from this
  commit forward omit them. Any external links to `…readthedocs.io/…/adr/…`
  land on the version selector's older builds or a 404 — accepted, the GitHub
  copies are canonical.
- Future ADRs need no mkdocs.yml touch at all — one less thing to forget.
- If a future ADR is genuinely user-facing, the move is to write its content
  into the narrative docs and link the ADR, not to republish the section.
