# ADR-0017: The view serves POST only; receive follows the ASGI contract

- **Status:** Accepted
- **Date:** 2026-07-30
- **Builds on:** [ADR-0007](0007-stateless-view-bridge.md) — the bridge whose synthesized
  `receive` this corrects; [ADR-0015](0015-runnable-example-project.md) — the live demo
  that exposed the bug

## Context

Running the example project's manual test plan (boot `just demo-asgi`, poke the endpoints)
found a denial-of-service defect that the entire automated suite had missed: **a single
anonymous GET to any MCP endpoint permanently pegged one uvicorn worker at ~100% CPU.**
Four probe GETs wedged all four workers; the fleet then served nothing, forever. The
workers did not even die — they spun, invisible to anything but `top`.

The mechanism has two halves:

1. The view forwarded *every* HTTP method into the SDK's transport. On GET, the transport
   opens its SSE listen stream — the channel for server-initiated messages, which only
   exist for *sessions* — and waits for the client to go away by polling the ASGI
   `receive` callable until it yields `http.disconnect`.
2. The bridge's synthesized `receive` returned the buffered request body **every time it
   was called**, instantly, and without ever awaiting. The disconnect listener therefore
   became a hot loop that never yielded control, starving the worker's entire event loop.

Why no test caught it: the suite drives the view through Django's test client, which only
ever sends the POSTs the protocol uses; the conformance suite likewise speaks the protocol
rather than probing the HTTP surface. The failure needed a *wrong* request — the kind the
open internet sends constantly (crawlers, scanners, a browser URL bar).

## Decision

Two fixes, either of which alone stops the spin; both are correct independently:

1. **The view serves POST only.** A stateless exchange is one request and one response —
   that is the package's whole thesis. The transport's GET listen stream and DELETE
   session termination presuppose the session state this view exists to not have, so
   non-POST methods now get an immediate `405 Method Not Allowed` with `Allow: POST`,
   before the SDK is invoked at all. The guard is documented in the `mcp_view` docstring
   as public contract.
2. **The synthesized `receive` honours the ASGI contract.** First call: the buffered body
   with `more_body: False`. Every later call: `http.disconnect` — because for a fully
   buffered request there is nothing left but the end of the connection. Any
   wait-for-disconnect loop in the SDK now exits on its first iteration.

If SSE streaming is ever implemented (the deferred subscriptions item), the POST-only
guard is where GET support gets *deliberately* reintroduced — with a real streaming
response, not an accumulating buffer.

## Consequences

- Regression tests pin the 405 (WSGI and ASGI paths, plus DELETE); they run in
  milliseconds because the guard short-circuits before the SDK.
- CORS preflight (`OPTIONS`) also gets 405 from the view; browser-based clients need
  `django-cors-headers` or similar in front, which is standard Django practice and now
  implicitly documented by the guard.
- The wider lesson mirrors ADR-0016's: the automated suite exercises the *protocol*, and
  bugs live at the *HTTP surface* around it. The example project's manual poke-it plan is
  not a demo nicety — it is a test layer, and it caught in minutes what CI structurally
  could not.
