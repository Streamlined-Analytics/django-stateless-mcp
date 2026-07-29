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

A Claude Code session opened in the repository picks up the committed `.mcp.json` and connects to the demo automatically.
Any streamable-HTTP MCP client can register `http://127.0.0.1:8000/mcp/`; the bearer endpoints take `Authorization: Bearer good-token` (a published demo constant).
MCP Inspector (`npx @modelcontextprotocol/inspector`) provides a full elicitation UI.

The complete walkthrough — endpoints, curl transcripts for the cross-worker elicitation, the permission-filtered tool list — lives in the repository's [`example/README.md`](https://github.com/Streamlined-Analytics/django-stateless-mcp/blob/main/example/README.md).
