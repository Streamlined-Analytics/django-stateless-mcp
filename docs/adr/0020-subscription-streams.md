# ADR-0020: Subscription streams — ASGI serves them, WSGI refuses them

- **Status:** Accepted
- **Date:** 2026-07-30
- **Builds on:** [ADR-0007](0007-stateless-view-bridge.md) — the buffered bridge this
  adds a second path to; [ADR-0017](0017-post-only-view.md) — where GET streams were
  ruled out and this door was left ajar

## Context

The last deferred protocol feature: on the `2026-07-28` wire there is no standing GET
stream — a client opts in to server events by POSTing `subscriptions/listen`, **whose
response is itself the stream** (SEP-2575). The bridge buffered every response, so the
SDK's `ListenHandler` (which streams until the client goes away) could never complete:
the conformance suite's three `server-stateless` failures, and four
`handler returned no HTTP response` 500s, were all this.

Two facts shaped the design:

1. The SDK owns everything above the transport: `ListenHandler` acks, stamps
   subscription ids, and filters events; `MCPServer(subscriptions=…)` is a public seam
   taking a `SubscriptionBus` — in-memory by default, implementable over Redis/NATS for
   multi-replica fan-out. The bridge's only job is carrying a streamed response.
2. A live stream under WSGI pins a worker for its whole lifetime — precisely the
   per-flow resource tax this package exists to remove — and Django cannot iterate an
   async stream outside the request's event loop there (the per-request loop is gone
   when the response body is consumed).

## Decision

`subscriptions/listen` is routed by the spec's **required `mcp-method` header** (the
body is never parsed) to a streaming path; every other request keeps the buffered path
unchanged.

- **Under ASGI** the dispatch runs as a background task that owns the entire
  session-manager lifecycle (anyio task groups must enter and exit in one task), and a
  `StreamingHttpResponse` relays its ASGI messages as they arrive. Closing the response
  — Django does so on client disconnect — cancels the dispatch, which is the SDK's
  documented end-of-stream signal. The streaming `receive` parks after the body instead
  of synthesizing a disconnect (ADR-0017's buffered contract would end the stream
  instantly).
- **Under WSGI** the view answers `501` with an explicit
  `unsupported_deployment` body. This is the asterisk the build plan predicted on the
  "identical under WSGI and ASGI" promise, now a documented contract instead of a hang:
  request/response MCP is identical under both; subscription *streams* need ASGI.
- The conformance script boots **uvicorn instead of `runserver`** so the
  `server-stateless` scenario exercises the streaming path; the scenario went from
  25/28 (3 failures) to **30/30**, and `server-stateless` left the expected-failures
  baseline.
- The example wires `MCPServer(subscriptions=InMemorySubscriptionBus())` and the
  `test_trigger_tool_change` / `test_trigger_prompt_change` fixtures the suite drives;
  an in-memory bus is correct for one instance, and a real fleet supplies an external
  bus — a deliberate downstream choice the docs state rather than a default we fake.

## Consequences

- `mcp_view`'s return type widens to `HttpResponseBase` (streaming responses are not
  `HttpResponse` subclasses) — a compatible, more-accurate published annotation.
- A fleet on the default in-memory bus delivers each event only to streams held by the
  worker that published it; cross-replica delivery is the `SubscriptionBus` seam's job.
- Tests parse real SSE frames off a live in-process stream (ack → published event →
  close) and pin the WSGI refusal; frames arrive CRLF-terminated, which the test reader
  normalises.
- The buffered path is untouched — tools, elicitation and everything else behave
  byte-identically.
