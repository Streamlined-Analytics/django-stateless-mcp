# 0041. The SEP-2322 fixture tools are tested by pytest, not only by the conformance harness

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** Ben Atkinson
- **Feature / area:** example project (`example/mcp.py`), test suite
- **Builds on:** ADR-0008 — the conformance harness and its expected-failures baseline
- **Supersedes / Superseded by:** none

## What problem were we trying to solve?

`example/mcp.py` holds the SEP-2322 fixtures — the `input_required` flows for
elicitation, sampling, roots, multi-round `requestState`, capability gating and
`prompts/get`. They are the richest demonstration of the package's thesis in the
repository, and pytest never touched most of them: 51 of its 110 statements were
uncovered, every branch of the three-round flow among them.

They were not untested, they were tested *elsewhere*. `scripts/run_conformance.sh`
boots the example under uvicorn and points the npm harness at it. That leaves
three gaps:

- The harness runs in its own workflow, against
  `@modelcontextprotocol/conformance@0.2.0-alpha.10` — a pinned alpha of a
  package that is not ours, on a spec still settling.
- Its failures are triaged through `expected-failures.2026-07-28.yml`
  (ADR-0008), so a fixture that stops working can be absorbed into the baseline
  rather than fixed.
- It boots uvicorn directly, so it produces no Python coverage. The combined
  report could not distinguish "exercised by a harness we do not own" from
  "never executed at all", and neither could a reviewer.

A regression in `test_input_required_result_multi_round`'s state machine would
have been caught by a suite pinned to an alpha npm release, or not at all.

## What did we try?

### Attempt 1 — collect coverage from the conformance run   <!-- ❌ rejected -->

Run the fixture server under `coverage run -m uvicorn`, flush on SIGTERM, upload
`.coverage.*` from `conformance.yml`, and add it to the `coverage` job's combine.
No new tests, and the existing harness keeps sole ownership.

Rejected on the coupling. The coverage gate would then depend on a second
workflow, an npm install, and a network fetch of an alpha package — so a
conformance-side outage becomes a coverage failure on an unrelated PR. It also
does nothing about the first two gaps: the fixtures would still only be checked
by a harness whose failures can be baselined away.

### Attempt 2 — omit `example/mcp.py` from coverage   <!-- ❌ rejected -->

Add it to `run.omit` beside `example/asgi.py` and `example/wsgi.py`, documented
as conformance-owned.

Cheap and honest about the status quo, but it makes the fixtures permanently
invisible: 100% would mean "100% of what pytest happens to own", and the number
would stop being a question anyone has to answer.

### Attempt 3 — drive every fixture through the view from pytest   <!-- ✅ chosen -->

`tests/test_conformance_fixtures.py`, one two-round flow per tool, driven
through the Django test client with the existing `post_stateless` helper.

The helper needed generalising — it hardcoded a `_meta` envelope declaring only
`elicitation`, and `tools/call` as the method — so it now takes the capability
set and the method, with the old behaviour as the default. That is what let the
sampling, roots, capability-gating and `prompts/get` fixtures be driven at all.

## What did we land on, and why?

Attempt 3. The fixtures are now regression-tested by the suite that gates every
commit, in the same process, with no network and no npm.

The tests are not a reimplementation of the conformance harness and should not
grow into one. The harness checks the *protocol*; these check that our fixtures
still behave, which is the part we own. `just conformance` remains the gate on
the first question, and its expected-failures baseline is unchanged by this
work.

Two of the flows turned out to be worth having as tests in their own right,
independent of coverage: the three-round `requestState` machine, and the
capability-gated tool asserted at all four declarations
(both / sampling only / elicitation only / neither).

## Consequences

- `example/mcp.py` reaches 100% from pytest alone, so the gate in ADR-0042 can
  cover it without importing a cross-workflow dependency.
- `post_stateless()` gains `capabilities` and `method` keyword arguments. It is
  a test helper, not public API, but three test modules import it, so the
  defaults were kept behaviour-preserving.
- Changing a fixture tool now means updating a pytest test as well as whatever
  the harness expects — deliberate friction on code whose whole purpose is
  demonstrating a wire contract.
- The conformance harness stays the authority on the spec. If the two ever
  disagree, the harness is right and the pytest expectation is the bug.
