# ADR-0036: A worked elicitation recipe — forms and destructive-action confirmations

- **Status:** Accepted
- **Date:** 2026-08-05
- **Builds on:** [ADR-0029](0029-benefits-led-messaging.md) (benefits-led
  messaging), [ADR-0034](0034-encourage-tool-annotations.md) (encourage tool
  annotations), [ADR-0035](0035-concise-docs-link-out-no-adr-references.md)
  (concise docs that link out)

## Context

A benefits audit asked whether every benefit of the package (and of the
2026-07-28 spec generally) for Django was both *listed* and *demonstrated*.
The list held up — scaling, elicitation, long-running jobs, auth, logging,
autodiscovery all appear on the README and `docs/index.md` — but two gaps
surfaced:

- **Elicitation had no worked example anywhere.** The README even promised
  "a worked elicitation example" in the documentation, but `usage.md` covers
  only the `request_state_security()` wiring, and the example project's
  `test_input_required_result_*` fixtures are conformance ports, not
  Django-shaped patterns. A reader knew elicitation existed but not how to
  write an eliciting tool.
- **The destructive-action framing had been diluted.** ADR-0035's bullet
  conversion shortened "require explicit approval before a create, update or
  delete" to "an explicit approval", losing the concrete update/delete hook
  that makes the benefit land.

The two named use cases — form filling and destructive-action confirmation —
map naturally onto Django idioms: a `ModelForm` already owns field validation
and error messages, and a boolean confirm elicitation is the enforcement
behind the `destructive_hint` annotation that ADR-0034 encourages clients to
build UX around.

## Decision

Add `docs/recipes/elicitation-forms-and-confirmations.md`, third in the
recipe series, with two patterns:

- **Confirm before a destructive write** — a `delete_customer` tool that
  returns `InputRequiredResult` with a boolean elicitation, treats anything
  but an explicit accept as a no, and pairs with
  `ToolAnnotations(destructive_hint=True)` (hints for the client, elicitation
  as the enforcement).
- **Form filling owned by a Django form** — a `create_customer` tool that
  feeds supplied arguments to a `ModelForm`, elicits corrections for exactly
  the fields the form rejects (quoting the form's own error messages), and
  saves once valid. Multi-round correction falls out of the same code path.

The recipe code uses only public SDK types (`InputRequiredResult`,
`ElicitRequest`, `ElicitRequestFormParams`, `ElicitResult`), mirroring the
example project's fixtures, and its constructor calls were validated against
the installed SDK before landing. The elicitation benefit bullets on the
README and `docs/index.md` regain the explicit update/delete wording and link
to the recipe, making the README's existing "worked elicitation example"
promise true.

## Consequences

- Each headline benefit now has a demonstration: statelessness (the example
  project and curl proofs), elicitation (this recipe), auth (the OAuth
  recipe), long-running jobs (the subscriptions recipe).
- The Django-form pattern establishes the answer to "where does validation
  live?" for eliciting tools: in the form, shared with ordinary views —
  consistent with the package's foundation-not-product stance.
- Recipe code is hand-maintained documentation; if the SDK's elicitation
  types drift, the conformance fixtures fail first and the recipe follows.
