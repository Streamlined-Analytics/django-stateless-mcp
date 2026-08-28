# Try it live

The repository contains a runnable example project — a real, tiny Django project serving every configuration of `mcp_view`.
It exists so you can experience the stateless model rather than take our word for it.

```sh
git clone https://github.com/Streamlined-Analytics/django-stateless-mcp
cd django-stateless-mcp
docker compose up
```

`docker compose up` migrates a local SQLite database, seeds a small book library plus demo users, and starts **four worker processes** behind one port with no sticky routing — no local uv, Python, or just required.
The domain is a deliberately familiar one — books and authors, in the spirit of Django's own documentation:

- `list_books` reads seeded rows through the ORM.
- `update_author` gates on a custom permission you toggle live in the Django admin (`/admin/`, `admin`/`admin`) while MCP Inspector re-lists the tools.
- `slow_book_report` blocks for 30 seconds — a slow tool occupies one worker thread, never the event loop or the fleet.
- `worker_pid` shows different processes answering successive calls.

That fleet is the point: an elicitation started on one worker resumes on another, because the encrypted `requestState` is keyed from `SECRET_KEY` rather than the SDK's per-process default.
You can stop the server mid-elicitation, start it again, and the resume still completes — no process ever held the flow.

Have uv installed? `just demo-asgi` runs the same fleet on the host, `just demo-gunicorn` runs it under WSGI gunicorn, and `just demo` runs a single-process WSGI dev server — the view serves both deployment models.

The example is not a separate artifact that can drift: the package's test suite inherits its settings and drives the same servers and URLs, and the MCP conformance suite in CI boots it over real HTTP.
What the demo serves is exactly what the tests assert on.

## Connecting an AI client

**MCP Inspector is the reference client for testing this package** (`npx @modelcontextprotocol/inspector`): its v2 line implements the full `2026-07-28` era, including the elicitation round-trip, rendered as a form.
One setting matters: set the connection's **Protocol Era to "Modern"** — Inspector defaults to the legacy 2025 handshake, under which elicitation fails.

Claude Code drives this example too: a session opened in the repository picks up the committed `.mcp.json`, connects, calls tools, and completes the elicitation round-trip — it declares the `elicitation` capability in its SEP-2322 envelope, and the demo's flow log shows the two requests as `exit=input_required` then `exit=completed`.
It declares no `sampling` capability, so `test_missing_capability` still refuses — which is that fixture doing its job.
(Verified against Claude Code 2.1.250, 28 August 2026.)

Any other streamable-HTTP MCP client can register `http://127.0.0.1:8000/mcp/`; the bearer endpoints take `Authorization: Bearer good-token` (a published demo constant).

The repository's [`example/README.md`](https://github.com/Streamlined-Analytics/django-stateless-mcp/blob/main/example/README.md) opens with a numbered quick start covering all of the above, then the complete walkthrough — the elicitation and permission cycles, curl transcripts for the cross-worker and kill-the-fleet resumes, and the subscription-stream demo.
