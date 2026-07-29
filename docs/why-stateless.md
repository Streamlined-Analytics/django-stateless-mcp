# Why stateless

Most people arrive at this package without knowing what changed on 2026-07-28.
This page explains the problem the MCP spec solved, and why that makes a Django
MCP package worth having at all.

## The problem: elicitation could not scale horizontally

Before the 2026-07-28 spec, MCP required a **persistent, bidirectional
connection**. A server that needed to ask the user a question mid-tool-call —
*elicitation* — held an open SSE stream and a blocked coroutine while it waited
for the answer.

That works on one process. It breaks on a fleet:

1. A tool call arrives at worker A, which needs input and blocks, holding the
   pending request **in that process's memory**.
2. The user answers. The reply is a **separate HTTP request**.
3. The load balancer round-robins it to worker B.
4. Worker B has never heard of this session. The elicitation fails.

The obvious fixes do not work. A shared session store solves session
*validation* but not live server-to-client *routing* — the blocked coroutine
still only exists on worker A. Sticky sessions are the other instinct, but MCP
keyed on the `Mcp-Session-Id` **header** while common load balancers offer
**cookie**-based affinity.

The practical workaround was to run MCP as a dedicated single-process service:
one worker, its own subdomain, its own auth. That works, and it is a permanent
tax — no horizontal scaling for one endpoint, and a second deployment artefact
to maintain.

## What the spec changed

Three Spec Enhancement Proposals do the load-bearing work:

| SEP | Change |
|---|---|
| **SEP-2567** | Removes the `Mcp-Session-Id` header and the protocol-level session. No sticky routing needed. |
| **SEP-2575** | Removes the `initialize`/`initialized` handshake. Metadata travels on every request, so a load balancer can route without parsing the JSON body. |
| **SEP-2322** | Multi round-trip requests — the stateless replacement for SSE-based elicitation. |

Elicitation becomes a **retry** rather than a held connection:

1. The server returns a result meaning *"I need input"*, carrying the prompts
   and an **opaque state value** the client must echo back unmodified.
2. The client gathers answers and **re-issues the original call**, including
   those answers and the echoed state.
3. **Any server instance can serve that retry**, because everything needed to
   resume is in the payload.

No session. No SSE. No affinity. No shared store.

!!! note "Wire details"

    The exact field names were recorded before the spec went final and may have
    drifted. Rely on the SDK's types rather than hand-written literals, so any
    drift is absorbed by the layer that owns the protocol.

## Why this makes Django a first-class MCP citizen

This is the whole thesis of the package.

The old protocol lived in territory Django is not naturally good at: persistent
bidirectional connections, event loops, server-initiated messages. Every Django
MCP package to date has therefore been a wrapper fighting the framework — which
is why the category has been consistently thin or stale.

The 2026-07-28 spec deletes that mismatch. MCP is now plain request/response
HTTP with self-describing requests, which is **exactly what Django is built
for**. An MCP server becomes a view. Elicitation becomes a retry. The
impedance mismatch that made this category bad is gone.

That is why this package exists now rather than a year ago.

## Design consequences

Three commitments follow directly, and they explain most of the API:

**Statelessness is the product, not an implementation detail.** There is no
session mode and there will not be one. Any state must travel in the request or
live in the database. A dictionary mutated between requests would reintroduce
precisely the bug the spec removed — and it would pass every test on a single
dev worker before failing in production.

**Per-request auth is the natural fit.** A stateless protocol wants the token
verified on every request rather than once at handshake, so authentication stops
being a session concern.

**We are a foundation, not a product.** Transport, elicitation, tool
registration and auth are shared infrastructure that every Django MCP server
needs. Model and ORM exposure is opinionated surface with a large security blast
radius, so it belongs in packages built *on top of* this one — which means the
extension API is the deliverable, and is documented and versioned accordingly.
