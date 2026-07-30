# Try it live

The repository contains a runnable example project — a real, tiny Django project serving every configuration of `mcp_view`.
It exists so you can experience the stateless model rather than take our word for it.

```sh
git clone https://github.com/Streamlined-Analytics/django-stateless-mcp
cd django-stateless-mcp
just demo-asgi
```

`just demo-asgi` migrates a local SQLite database, seeds a demo user, and starts **four worker processes** behind one port with no sticky routing.
That fleet is the point: the `worker_pid` tool shows different processes answering successive calls, and an elicitation started on one worker resumes on another, because the encrypted `requestState` is keyed from `SECRET_KEY` rather than the SDK's per-process default.
You can stop the server mid-elicitation, start it again, and the resume still completes — no process ever held the flow.

`just demo` runs the same project under WSGI (Django's dev server), because the view serves both.

The example is not a separate artifact that can drift: the package's test suite inherits its settings and drives the same servers and URLs, and the MCP conformance suite in CI boots it over real HTTP.
What the demo serves is exactly what the tests assert on.

## Connecting an AI client

**MCP Inspector is the reference client for testing this package** (`npx @modelcontextprotocol/inspector`): its v2 line implements the full `2026-07-28` era, including the elicitation round-trip, rendered as a form.
One setting matters: set the connection's **Protocol Era to "Modern"** — Inspector defaults to the legacy 2025 handshake, under which elicitation fails.

As of this writing (July 2026), Claude Code speaks the stateless transport — a session opened in the repository picks up the committed `.mcp.json`, connects, and calls plain tools — but does not yet send the SEP-2322 capabilities envelope, so elicitation flows fail client-side.
That is a client gap, not a server one; the same tools will work unchanged once the client catches up.

Any other streamable-HTTP MCP client can register `http://127.0.0.1:8000/mcp/`; the bearer endpoints take `Authorization: Bearer good-token` (a published demo constant).

The complete step-by-step walkthrough — Inspector setup including the era setting, the elicitation and permission cycles, curl transcripts for the cross-worker and kill-the-fleet resumes — lives in the repository's [`example/README.md`](https://github.com/Streamlined-Analytics/django-stateless-mcp/blob/main/example/README.md).
