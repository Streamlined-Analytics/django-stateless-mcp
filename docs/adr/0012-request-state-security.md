# ADR-0012: Key request-state security from SECRET_KEY

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** [ADR-0007](0007-stateless-view-bridge.md), [ADR-0008](0008-conformance-suite.md)

## Context

Phases 5 and 6, landed together deliberately: the mechanism
(`RequestStateSecurity`) and the proof (the flagship tests) belong in one
change, because each is unfalsifiable without the other.

Stateless elicitation resumes by the client echoing an opaque
`requestState`. The SDK encrypts it (AES-GCM), and the source shows the
default key is `os.urandom(32)` — **random per process**. With defaults, a
retry that round-robins onto a different worker cannot decrypt the state:
the multi-worker elicitation failure this package exists to remove,
reintroduced silently one layer down.

## Decision

`request_state_security()`, a one-call helper building the SDK's
`RequestStateSecurity` from `[SECRET_KEY, *SECRET_KEY_FALLBACKS]`. Every
worker sharing Django settings can then resume any elicitation, and Django's
standard key-rotation story extends to in-flight elicitations: state minted
under the old key resumes while the fallback stays configured.

Nothing else is ours — encryption, TTL, tamper rejection and principal
binding are all SDK-owned. The package's contribution is one deliberate
choice of key material.

Two SDK behaviours worth knowing, found while testing:

- **Audience binding is by server name.** State minted by `MCPServer(name=X)`
  resumes only on a server named `X`. Identical replicas share a name, so
  this is invisible in the deployment this package targets — but a fleet of
  differently-named servers sharing keys will not share state, by design.
- **Keys must be ≥ 32 bytes.** Django's generated keys are longer; the test
  settings' short placeholder had to grow.

## The flagship tests

1. **Elicitation across two separate requests** — `input_required` out,
   `inputResponses` back, completion. Nothing held between the posts.
2. **The retry served by a different `MCPServer` instance** than the one
   that minted the encrypted state, sharing only Django settings — two
   workers in a fleet, in miniature. This is the test the old architecture
   could not pass, with the in-process blind spot already recorded in the
   build plan (a multi-worker harness remains the out-of-process proof).
3. **Tampered state fails closed** with `invalid_request_state`.

## The wire lesson: three request requirements

The first flagship tests failed with instructive errors. A `2026-07-28`
request is not just a POST: it needs the `mcp-protocol-version` header
(without it the runner falls back to legacy handling, where a tools/call
returning `InputRequiredResult` is *invalid*), the `mcp-method` and
`mcp-name` routing headers (SEP-2575 — matching the body, so load balancers
route without parsing JSON), and the per-request `_meta` envelope carrying
`protocolVersion` and `clientCapabilities`. The conformance fixtures ported
from the SDK's everything-server (MIT, attributed in `tests/mcp.py`) only
elicit when the client declares the capability — a spec requirement, not a
quirk.

## Conformance burn-down

The entire `input-required-result-*` block — twelve scenarios, including the
two that flapped against a non-eliciting fixture — now **passes live** and
is out of the baseline: 78 checks green, up from 56. `server-stateless`
improved from many failures to three (the ported `test_missing_capability`
armed its capability checks; the remaining three are the deferred
`subscriptions/listen` SSE feature). This was the Phase 6 exit criterion.

## Consequences

- `request_state_security()` is public API, with the maintenance promise
  that implies.
- The remaining baseline is content-type/resource/prompt fixture gaps, one
  deliberate deviation, and the deferred SSE feature — no elicitation
  entries left.
