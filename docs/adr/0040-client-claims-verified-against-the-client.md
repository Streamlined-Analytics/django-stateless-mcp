# ADR-0040: Client-support claims are verified by running the client, not by reading its changelog

- **Status:** Accepted
- **Date:** 2026-08-28
- **Builds on:** [ADR-0036](0036-elicitation-recipe.md) (the elicitation recipe
  and its client-support table), [ADR-0035](0035-concise-docs-link-out-no-adr-references.md)
  (concise docs that link out)

## Context

Three docs surfaces carried dated claims about what MCP *clients* can do: the
elicitation recipe's per-product support table (checked 10 August 2026), the
subscriptions recipe's client-support note, and the example project's
"Connect Claude Code" section, duplicated in `docs/example.md`.

A review three weeks later found each surface had rotted differently, and the
three failures are worth keeping apart because they need different fixes:

- **Verdict right, evidence dead.** Every ✅/❌ in the table still held, but
  two rows pointed at trackers that had since closed. The Gemini CLI issues
  were closed in May 2026 with "no immediate plans" — GitHub records that as
  `state_reason: completed`, which reads like the opposite of what happened.
  The Claude Desktop issue was bot-labelled `invalid` (it was filed against
  the Claude Code repository) and closed by its author. A reader following
  "tracked in …, open" would find a closed issue and reasonably conclude the
  feature had shipped.
- **A claim that was already false when written.** `docs/example.md` and
  `example/README.md` said Claude Code sends no SEP-2322 capabilities
  envelope, so every `test_input_required_result_*` tool fails with
  `-32603`. The recipe table published five days later marked Claude Code ✅
  for elicitation since v2.1.76 (March 2026). The repository contradicted
  itself for three weeks and neither surface noticed.
- **A claim that went stale silently.** The subscriptions recipe said Claude
  Code does not consume subscription events. Claude Code v2.1.233 carries a
  fix for reopening the `subscriptions/listen` stream in a loop — a bug you
  can only have if you hold the stream.

The common cause is that all three claims were sourced from what vendors
*say*, and the interesting client behaviours are ones vendors never mention.

## Decision

**Where the example project can exercise a claim, the evidence is a recorded
run against the example — client version and date — not a release note.**

The re-verification took three passes, and the first two are the reason for
the rule:

- **Release notes and changelogs.** Good for dating features that were
  announced: v2.1.76 added elicitation in form and URL modes, v2.1.238 and
  v2.1.239 fixed its dialogs. Useless for the question actually asked —
  no changelog anywhere mentions the SEP-2322 envelope, and subscription
  support appears exactly once, as a bug fix, never as an announcement.
- **Issue trackers.** Actively misleading, as above: closed-as-deferred and
  closed-as-invalid both present as `completed` through the API.
- **Running it.** The demo fleet booted, tools called from a real Claude Code
  session, and the answer read out of the server's own flow log:
  `exit=input_required`, then `exit=completed`. The envelope claim was
  dead; the round-trip completes. The same run surfaced two behaviours no
  document had: Claude Code declares no `sampling` capability (so
  `test_missing_capability` still refuses, exactly as that fixture intends),
  and its ten-round guard trips on
  `test_input_required_result_capabilities`, a fixture that returns
  `input_required` on every round by design.

Third-party compatibility matrices stay rejected, on the grounds ADR-0036
already recorded: they were wrong about Claude Code then, and the ones
consulted now do not cover elicitation at all.

Rows for clients that cannot be run on the maintainer's machine keep their
primary-source citation, but say what a tracker's state *means* rather than
asserting it is open.

## Consequences

- The example project takes on a second job. It was a demo and the test
  suite's fixture set; it is now also the probe for client claims, and its
  `test_input_required_result_*` fixtures double as a capability
  interrogation of whatever client is pointed at them.
- Verification costs a booted fleet and an installed client, so it reaches
  only the clients the maintainer runs — Claude Code today. Cursor, Copilot
  on Visual Studio, and the Gemini consumer app remain release-note claims,
  and are not presented as more than that.
- Claims now name a client version and a date, so they date faster but fail
  honestly: a reader can tell a stale claim from a live one.
- The two client behaviours recorded above are dated snapshots of a moving
  target. When Claude Code declares `sampling`, or changes its round guard,
  the example docs go stale — and the conformance fixtures notice first.
