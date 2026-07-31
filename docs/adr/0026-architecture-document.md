# ADR-0026: A living ARCHITECTURE.md at the repository root

- **Status:** Accepted
- **Date:** 2026-07-31
- **Builds on:** [ADR-0023](0023-adrs-unpublished-from-docs-site.md) — contributor material lives in-repo

## Context

The project had three kinds of documentation and a gap between them: the Read
the Docs site tells a *user* how to use the package, the ADR chain tells a
reader *why* each decision was made (frozen at decision time), and nothing told
a *contributor* how the package works now — the request lifecycle, the
invariants a change must preserve, and the traps that have already produced
real bugs (the contextvar leak, the spinning disconnect-listener, worker-thread
connection hygiene). That knowledge lived across twenty-five ADRs and the
maintainer's head; the cost of reconstructing it is exactly what an
architecture document amortises. Recommended directly by Tim Schilling
(mentoring, 2026-07-31) and modelled by Django Commons' best-practices repo.

Two placement options:

1. **A page on the docs site.** Rejected — ADR-0023 just established that the
   RTD site is user-facing and contributor material is in-repo markdown;
   republishing contributor docs there would reverse a week-old decision.
2. **Root `ARCHITECTURE.md`** (the convention popularised by matklad's
   "ARCHITECTURE.md" essay), linked from CONTRIBUTING and README. Chosen.

## Decision

`ARCHITECTURE.md` at the repository root: the request-lifecycle mental model
(with a Mermaid diagram), the SDK/Django layer boundary, the three invariants
with their named enforcement points, a module map keyed to the ADRs that shaped
each module, the traps list, the verification layers, and the evolution rules
(protocol work goes upstream, opinionated features go downstream).

Its relationship to the ADRs is explicit and directional: the architecture
document is **living** — a PR that changes the shape updates it in the same
PR — while ADRs stay frozen; it links to ADRs for the why and never restates
them. This is the same living/frozen split ADR diagrams already follow.

## Consequences

- A new maintenance duty: shape-changing PRs now touch ARCHITECTURE.md too.
  The document is deliberately a map, not a tour — module-level, not
  line-level — so ordinary refactors do not rot it.
- CONTRIBUTING and README point to it, making it the entry path for a new
  contributor before the code.
- The traps section is the institutional memory of bugs already paid for;
  future incident write-ups should add to it.
