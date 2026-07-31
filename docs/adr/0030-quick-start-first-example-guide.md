# ADR-0030: The example README is a quick-start guide, not a reference dump

- **Status:** Accepted
- **Date:** 2026-07-31
- **Builds on:** [ADR-0015](0015-runnable-example-project.md) — the example project
  this documents; [ADR-0022](0022-docker-compose-demo.md) — the Docker boot path
  this promotes to primary

## Context

The example README had grown into a reference document: seven numbered sections
of accurate, verified prose in which the actual actions a first-time visitor
must take — start a server, connect Inspector, flip one setting, run two tools —
were interleaved with rationale, variants, and caveats. Three specific problems:

- **The load-bearing steps were skimmable-past.** The Inspector "Protocol Era →
  Modern" setting is the single most common failure (a legacy-era connection
  makes every elicitation tool fail with *"Handler returned an invalid
  result"*), yet it sat mid-list inside section 3 *and* was repeated in a
  "Gotchas" appendix at the bottom — which a reader only meets after being
  bitten. A gotcha stored away from the step it bites is a post-mortem, not a
  guardrail.
- **The primary run method was buried.** `docker compose up` (ADR-0022) needs
  no local uv, Python, or just — the right default for someone evaluating the
  package — but it was listed last of four variants, after three `just`
  targets that assume the contributor toolchain.
- **Two audiences, one flat structure.** Evaluators need "do this, do this,
  done"; contributors need the endpoints table, curl transcripts, and the
  subscription-lottery caveat. Serving both in one linear document made the
  first two minutes read like the last twenty.

## Decision

Restructure `example/README.md` into a **numbered quick start followed by
linked detail sections**, and make **Docker the primary boot path** everywhere
the demo is mentioned:

- The quick start is six terse steps — `docker compose up` → Inspector →
  connect → **set Protocol Era to Modern** (its own unmissable step) → run
  `add` → run the elicitation round-trip — ending at the package's thesis
  observed live, with a pointer to the curl walkthrough for the harder proofs.
- The `just` targets move to a "Server variants" detail section as the
  host-run alternatives for people with uv installed.
- The standalone "Gotchas" appendix is deleted; each gotcha is folded into the
  step where it would bite: the Inspector era default into quick-start step 4
  (its duplicate removed), the `db.sqlite3` grant/revoke persistence into the
  top of the permissions walkthrough (which now *starts* from a known revoked
  state), the bare-GET-405 and CSRF-exemption notes into the endpoints
  section, and the `delete_widget`-without-`widget_id` validation-error note
  into the exact step that runs `delete_widget`.
- The permissions walkthrough leads with the `docker compose exec demo …` form
  of the `seed` commands (the bind-mounted `db.sqlite3` makes the host-run
  `uv run` form an equivalent, noted alternative).
- `docs/example.md` (the Read the Docs "Try it live" page) and the project
  README's "Try it live" section adopt the same docker-first ordering, keeping
  every surface consistent.

The acceptance test for the gotcha decision: **a reader following only the
numbered steps cannot hit the legacy-era failure**, because the guard is a
step, not an appendix. All prior content is preserved — reorganised, not
rewritten — keeping the "every step was run before being written down"
property intact.

## Consequences

- First-contact time-to-thesis drops to the length of the quick start; the
  depth remains one link away.
- Docker becomes the documented default everywhere, so instructions must keep
  the `docker compose exec` command forms first and the `just` forms as the
  alternative — not drift back.
- There is no Gotchas appendix to append to: a newly discovered gotcha must be
  filed into the step where it bites, which keeps the guide honest at the cost
  of slightly harder authoring.
- Section anchors in `example/README.md` are now link targets from the quick
  start (and from `docs/example.md`); renaming a heading requires updating its
  in-document links.
