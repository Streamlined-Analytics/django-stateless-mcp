# ADR-0044: MCP Apps are supported by recipe and example, not by package API

- **Status:** Accepted
- **Date:** 2026-09-04
- **Builds on:** [ADR-0036](0036-elicitation-recipe.md) (the elicitation
  recipe, whose confirmation pattern this one reaches on other clients),
  [ADR-0040](0040-client-claims-verified-against-the-client.md) (client-support
  claims are verified by running the client)

## Context

The elicitation recipe's client table shows that no consumer web product
supports elicitation: Claude.ai, Claude Desktop and ChatGPT route
in-conversation UI through **MCP Apps** (the `io.modelcontextprotocol/ui`
extension, SEP-1865) instead, and a server maintainer's report on the Claude.ai
tracker shows why — Claude.ai advertises only that extension, and the
pre-2026-07-28 elicitation stream did not survive its connector proxy. So for
the users this package is pitched at ("accommodate your users' agents"), an
app is the only way to put a confirmation button in front of a human on the
consumer clients.

The question was whether the package needs to do anything to support it, and
if so what.

## What we found

Driving an `Apps()`-extended `MCPServer` through `mcp_view` with Django's test
client, with no package changes:

- `server/discover` advertises the extension;
- `tools/list` carries `_meta.ui.resourceUri` and `visibility`;
- `resources/list` and `resources/read` serve the `ui://` document under
  `text/html;profile=mcp-app`;
- `tools/call` sees whether the client negotiated Apps from the per-request
  `_meta` capability envelope, so a tool can degrade to text;
- an app-only tool is callable;
- a 2025-11-25 `initialize` (the handshake Claude.ai negotiates today) is
  answered by the SDK's legacy surface.

The SDK ships the extension in core (`mcp.server.apps`) as an additive
contribution of tools and resources. All interactive state lives in the
host's iframe; the server serves one static document and answers ordinary
tool calls. It is stateless by construction.

## Decision

**Support MCP Apps with a recipe and an example tool, and add nothing to the
public API.**

- `docs/recipes/mcp-apps.md` shows the three server-side parts (the `Apps()`
  extension, a `ui://` resource, bound tools), a Django-template-backed
  resource, the text fallback via `client_supports_apps`, and the
  confirmation pattern for consumer clients: an app-bound read tool plus an
  app-only destructive tool that still gates on `has_perm`. Its limitations
  section is the point of the document.
- The example project gains `example/book_shelf.py` (a `DjangoTemplateResource`
  and two tools) and `example/templates/example/book_shelf.html`, registered
  on the open server with `extensions=[book_shelf]`, so the test suite
  exercises discovery, the rendered template, the fallback and the permission
  gate through the view under WSGI and ASGI.

Three alternatives were weighed:

1. **A public `django_stateless_mcp` helper** (a `TemplateAppResource` or a
   `django_apps()` factory). Rejected for now. The whole Django-specific part
   is a dozen lines — a `Resource` subclass whose `read()` calls
   `render_to_string` in a worker thread — and the protocol work is the SDK's.
   A public symbol is a maintenance promise (semver, docstring, `docs/api.md`)
   over a draft extension whose shapes are still moving. If downstream
   packages end up copying the class, that is the signal to promote it.
2. **Rendering the document at import time** with `add_html_resource(uri,
   render_to_string(...))`. Rejected: it renders during URL import, and every
   template edit needs a restart. Per-read rendering costs one template render
   per `resources/read`, which hosts cache, and keeps the template editable.
3. **Reusing the elicitation confirmation.** Not possible: an app renders
   after the tool has returned and cannot pause the call. The confirmation
   becomes a second, app-only tool the human triggers, with `visibility`
   keeping it off the model's list. Because visibility is enforced by the
   host and invisible on the wire, the tool keeps its own permission check —
   the same boundary rule `PermittedToolsFilter` documents.

Per ADR-0040, the recipe's client table is labelled as the vendors' and the
community matrix's claims, and says plainly that no run against Claude.ai or
ChatGPT exists yet.

## Consequences

- Consumers get a working, tested pattern for the consumer clients without
  waiting on a package release, and the package's surface does not grow.
- The template's JavaScript is exercised only for syntax and for the strings
  the tests assert on; rendering in a host is unverified. The follow-up is a
  recorded run of the example inside Claude.ai and ChatGPT, which would also
  settle whether those portals talk to a stateless 2026-07-28 server at all.
- The example now depends on Django's default `example.delete_book`
  permission, which the seed command does not grant; the demo user cannot
  retire books until an admin grants it, mirroring the `update_author` cycle.
- If the SDK moves MCP Apps out of core, or the extension's wire shape
  changes, the recipe's code samples need revisiting; the package itself does
  not.
