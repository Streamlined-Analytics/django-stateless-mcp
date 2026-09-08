# 0043. A "How this compares" page separates agent frameworks from MCP servers

- **Status:** Accepted
- **Date:** 2026-09-08
- **Deciders:** Ben Atkinson
- **Feature / area:** Documentation, positioning
- **Builds on:** [ADR-0029](0029-benefits-led-messaging.md) (benefits-led
  messaging), [ADR-0035](0035-concise-docs-link-out-no-adr-references.md)
  (concise user-facing docs that link out)
- **Supersedes / Superseded by:** none

## What problem were we trying to solve?

[Issue #84](https://github.com/Streamlined-Analytics/django-stateless-mcp/issues/84)
asked for documentation of why someone should choose this package "over
PydanticAI or something similar". The request reads as a competitor
comparison, but the premise is a category error the docs had left open: an
agent framework and an MCP server are the two ends of the same protocol, not
two answers to one question.

The confusion is reasonable. Pydantic AI and LlamaIndex both advertise "MCP
support", and a developer who knows code but not MCP has no way to tell that
this support is *client-side* (connecting an agent to a server like ours)
rather than a competing way to publish one. Nothing on the README, the index,
or `why-stateless.md` named the distinction, and `why-stateless.md` assumes the
reader already knows they want a server.

## What did we try?

### Answer the question as asked: a feature table against Pydantic AI   <!-- ❌ rejected -->

A first pass compared server-side options only (official SDK, FastMCP 4,
django-mcp-server). That is useful, but it skips the reader's actual state:
they do not yet know which side of the wire they are on, so a server-versus-
server table answers a question they have not reached.

### Fold the distinction into `why-stateless.md`   <!-- ❌ rejected -->

That page is the explanation of *the protocol change*; adding "and here is
what an agent framework is" would mix two explanations (the Diátaxis mixing
problem ADR-0035 identified) and bury the answer to #84 below the SEP table.

### A dedicated page, two-step   <!-- ✅ chosen -->

`docs/how-this-compares.md`, in the nav directly after "Why stateless":

1. **Agent framework or MCP server?** Framed around one question, *who calls
   the LLM*: with Pydantic AI or LlamaIndex your code holds the API key and
   runs the loop; with this package someone else's AI calls your app and your
   code never calls a model. The DRF analogy carries it (DRF lets programs
   call your app over HTTP; this lets agents call it over MCP; the agent
   frameworks are the `httpx` of that picture). Two self-diagnosis questions
   and an explicit "both can be true in one project" close the section.
2. **The actual alternatives.** The server-side table from the first pass,
   now placed where the reader is ready for it.

A two-line "not an agent framework" note goes under "What this package is
not" on the index and a new "What it is not" section in the README, since
that is where a newcomer looks first; both link to the page.

## Research findings that shaped the wording

Verified against primary sources on 2026-09-08 so the page does not carry
stale claims:

- Pydantic AI's own "MCP server" docs page shows an agent used *inside* a
  server built with the SDK; Pydantic AI is not a server framework. Its
  `MCPToolset` is a client.
- LlamaIndex's `McpToolSpec` is a client; `workflow_as_mcp` does publish a
  server, but of a LlamaIndex workflow in its own process, so the page names
  it rather than claiming LlamaIndex has no server story.
- **FastMCP 4 (2026-08-31) fully supports the 2026-07-28 spec.** Earlier
  articles saying standalone FastMCP is handshake-only describe 3.x. The
  page must not claim a capability gap; the differentiator is separate-
  service deployment and deliberate dual-era statefulness. (The repo's own
  rule against building on FastMCP 4 is a layering choice, unchanged.)
- django-mcp-server: latest release 0.5.7 on 2025-10-10, `mcp>=1.8.0`,
  stateful by default via Django sessions, and it documents WSGI *and* ASGI
  support, so portability is not a differentiator against it; protocol age
  and SDK-internals coupling are.

## Consequences

- Issue #84 is answered on Read the Docs, the README, and the index, in the
  order a newcomer encounters them.
- The comparison table carries dated, checkable claims about third-party
  packages (FastMCP 4's spec support, django-mcp-server's SDK pin). Per
  ADR-0040's spirit, re-verify them when those packages release, and keep the
  wording specific enough that staleness is visible.
- The page follows ADR-0035: it links out to every third party's own docs and
  restates nothing they own.
