# ADR-0029: Benefits-led messaging across the README and docs

- **Status:** Accepted
- **Date:** 2026-07-31
- **Builds on:** none — first ADR for the project's user-facing messaging

## Context

The README opened with the stateless mechanism (spec history, SEPs, transport
details) rather than what a reader gets from the package. A review of the
intended pitch surfaced three claims that needed correction before leading with
them:

- **"Not achievable in MCP 1.x" conflated the SDK with the protocol.** The
  enabling change was the `2026-07-28` spec revision; the SDK's 1.x → 2.0 bump
  merely tracked it. It also overstated the old world: horizontal scaling *was*
  achievable — via a dedicated single-process MCP service, a permanent second
  deployment artefact. "No second deployment artefact" is both accurate and the
  more compelling claim, so it became the lead benefit.
- **"Full use of Django's authentication system" overstated auth.** The package
  bridges OAuth bearer tokens to real Django users via `user_resolver`; it is
  not session/cookie login. The wording landed on "bearer auth resolves to a
  real Django user, so `user.has_perm(...)` just works".
- **Tool visibility filtering must not read as security.** `PermittedToolsFilter`
  hides tools from `tools/list`, but a hidden tool can still be called by name
  (ADR-0014); the messaging keeps the "each tool still gates its own execution"
  qualifier wherever filtering is mentioned.

Separately, subscriptions were a one-line footnote in "What it provides",
despite enabling the package's most user-visible workflow: a tool starts a long
job and returns instantly, and the client is notified when the result is ready.
Working through the scaling question ("would 50 subscribers be a problem?")
showed the story survives scrutiny — an idle stream is a parked connection, not
a blocked worker — but only if the docs say it plainly and state the honest
caveats (ASGI-only, external `SubscriptionBus` beyond one process, client-side
support still uneven as of July 2026).

## Decision

Lead every user-facing surface with benefits, in plain language, before
mechanism:

- **README** opens with a "Why use this" section ordered: ordinary Django view
  (no separate service) → scales like the rest of the app → elicitation in
  concrete terms (form-filling, approval before create/update/delete) →
  long-running jobs that report back → auth/permissions inside tools →
  structlog observability → `admin.py`-style registration.
- **`docs/index.md`** carries a condensed one-line-per-benefit version of the
  same list, and gains the previously missing "Try it live" link.
- **`docs/why-stateless.md`** keeps its structure; elicitation gets the same
  concrete use-case gloss.
- **Subscriptions get a full recipe** (`docs/recipes/long-running-jobs.md`):
  the start-job → notify → fetch pattern with Celery, the thin-signal rule
  (data travels the permission-checked tool path, never the stream), the
  parked-connection scale economics, the multi-process bus requirement, and the
  client-support caveat. The README and `usage.md` link to it.

README and `docs/index.md` are synced by hand — there is no include mechanism
(ADR-0002's hand-written-docs choice) — so the condensed docs list deliberately
tracks the README's benefit *leads*, not its full prose, to keep the sync
surface small.

Drive-by fix in the same change: `usage.md` carried two near-verbatim logging
sections ("Structured request logging" and "Logging tool dispatch"); the
duplicate was merged into the former.

## Consequences

- The first screen of the README now answers "why would I use this?" rather
  than "what changed in the spec?"; the spec story moves to second position
  with `why-stateless.md` as the deep dive.
- The corrected claims are the durable wording: future copy should not
  reintroduce "MCP 1.x", "not achievable", or unqualified "Django
  authentication" phrasing.
- The long-running-jobs recipe is the canonical subscriptions example; example
  README and future messaging should point at it rather than restating the
  pattern.
- Any future benefit added to the README's "Why use this" must be mirrored in
  `docs/index.md` in the same PR.
