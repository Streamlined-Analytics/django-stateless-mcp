# ADR-0008: Run the official MCP conformance suite in CI

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0007](0007-stateless-view-bridge.md) — the view bridge

## Context

Our own tests assert that the bridge behaves as we expect; they cannot tell us
whether it implements the *spec* correctly, because both sides of the assertion
are ours. The MCP project publishes an official conformance harness
(`@modelcontextprotocol/conformance`) for exactly this, and the Python SDK runs
it against itself in CI — a proven, copyable pattern.

The package's own test rule ("no live server, no bound port") governs the pytest
suite. This is deliberately the other layer: black-box validation over real
HTTP, in its own workflow, against a bootable server.

## Decision

A `Conformance` workflow runs on every PR and push to `main`:

- `scripts/run_conformance.sh` boots Django's `runserver` on the test fixture
  (`tests.settings` + `tests.urls` — the same fixture the pytest suite uses),
  waits for readiness with a `ping`, and hands over to the harness.
- The harness is pinned via `CONFORMANCE_PKG` (`0.2.0-alpha.10`, matching the
  SDK's pin) and run as `--suite all --spec-version 2026-07-28`.
- Known failures live in `.github/conformance/expected-failures.2026-07-28.yml`,
  so the job is green when reality matches the recorded baseline and red only on
  a *new* failure.

## The baseline, established empirically

First full run: **56 checks passed, 35 failed**, across 27 failing scenarios.
Every failure was investigated before being baselined; they fall into exactly
three categories, and none is a statelessness bug:

1. **A deliberate deviation.** `dns-rebinding-protection` fails because
   [ADR-0007](0007-stateless-view-bridge.md) hands host validation to Django's
   `ALLOWED_HOSTS`. This entry is permanent unless that decision changes.
2. **A deferred feature.** `server-stateless` fails only on its
   `subscriptions/listen` SSE checks (plus one missing diagnostic fixture tool)
   — the streaming question ADR-0007 explicitly deferred. The core stateless
   lifecycle checks pass.
3. **Fixture gaps.** Everything else expects the server under test to implement
   named `test_*` tools, resources and prompts — the harness's
   "everything-server" pattern (the SDK maintains `mcp-everything-server` for
   this). Our fixture has one `add` tool, so content-type, progress, prompt,
   resource and elicitation scenarios cannot run. The harness frequently says so
   itself: *"Not testable: server exposes no tool with x-mcp-header
   annotations."*

The elicitation block (`input-required-result-*`) is grouped separately in the
baseline because it burns down at a known point: Phase 6, when eliciting fixture
tools are added. Those scenarios are the flagship feature's conformance tests,
and flipping that group from baseline to live assertions is a Phase 6 exit
criterion.

## Two behaviours worth recording

- **Two scenarios flip pass/fail** against a server with no eliciting tool
  (`input-required-result-missing-input-response`, `-validate-input`) — e.g.
  *"Server accepted null inputResponses and returned complete result"* happens
  only because `add` executes instead of eliciting. They are baselined with the
  others and become deterministic in Phase 6.
- **This harness version tolerates stale baseline entries** — a baselined
  scenario that passes does not fail the job (verified empirically; the SDK's
  own comments suggest stricter behaviour, possibly in a newer harness). So the
  burn-down is advisory: removing conquered entries is manual discipline, done
  when the phase that fixes them lands.

## Consequences

- The bridge's spec compliance is now measured by the protocol's own tests, not
  only ours: 56 checks green today, including lifecycle, caching and header
  validation.
- Bumping `CONFORMANCE_PKG` is a deliberate act that must reconcile the baseline
  in the same change.
- The workflow is not in the `all-checks-pass` aggregator (it is a separate
  workflow, like CodeQL), but the pre-merge gate script fails on any red check,
  so a conformance regression still blocks merges in practice.
- `tests/settings.py` gained `localhost`/`127.0.0.1` in `ALLOWED_HOSTS` so the
  fixture is bootable over real HTTP.
