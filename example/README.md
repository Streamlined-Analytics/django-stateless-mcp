# The runnable example project

A tiny but real Django project serving `django-stateless-mcp`.
The quick start below shows the package's thesis live in about two minutes; everything deeper — permissions, curl proofs, subscriptions — is in [the details](#the-details).

## Quick start

1. **Run the demo fleet** — migrates, seeds, then serves four worker processes on `:8000`, no local uv, Python, or just required:

   ```sh
   docker compose up
   ```

   (Have uv installed? `just demo-asgi` runs the same fleet on the host — see [server variants](#server-variants-and-options).)

2. **Run MCP Inspector** and open the tokened URL it prints:

   ```sh
   npx @modelcontextprotocol/inspector
   ```

   (Inspector, not Claude Code — Claude Code cannot drive elicitation yet; see [Connect Claude Code](#connect-claude-code-partial-as-of-july-2026).)

3. **Connect**: Transport Type **Streamable HTTP**, URL `http://127.0.0.1:8000/mcp/`.

4. **Set Protocol Era to "Modern" — this is the step everyone misses.**
   Open the server entry's settings (the edit control on the server entry); in the **Options** section, change **Protocol Era** from its default, *Legacy (2025-11-25 handshake)*, to **Modern**, which pins `2026-07-28`.
   Don't use *Auto* — it can fall back to legacy.
   A legacy-era connection is what makes elicitation tools fail with *"Handler returned an invalid result"*; a connected modern session shows a **Modern** era badge.

5. **Call a tool**: **Tools** tab → **List Tools** → run `add` with `a=2, b=3` → `5`.

6. **Run the elicitation round-trip**: run `test_input_required_result_elicitation`.
   Inspector pauses at a pending-request modal asking for a name; submit it, and Inspector automatically retries with the returned `requestState` → the tool completes with a greeting.
   In the server log that is two independent requests — `exit=input_required`, then `exit=completed` — with no state held between them.

That is the package's thesis, observed live.
The harder proofs — the retry answered by a **different server instance**, the whole fleet **killed and restarted mid-flow**, tampered state rejected — are in [the curl walkthrough](#see-statelessness-with-your-own-eyes-curl).

---

## The details

### What this project is

The example plays two roles ([ADR-0015](../docs/adr/0015-runnable-example-project.md)):

- **Launch it** to exercise the package as actual AI infrastructure — watch elicitation resume across worker processes, toggle tool permissions live, kill the whole fleet mid-flow and resume anyway.
- **The test suite reuses it**: `tests/settings.py` inherits `example/settings.py`, and the pytest suite drives the same servers and URLs you can boot here.

Every step in this document was run against this project before being written down.

### Server variants and options

```sh
docker compose up   # the four-worker ASGI fleet in a container (just demo-docker rebuilds first)
just demo-asgi      # the same fleet on the host: migrate + seed + uvicorn, four workers on :8000
just demo-gunicorn  # the same fleet under WSGI gunicorn, four workers on :8000
just demo           # the same project under WSGI (single-process dev server)
```

The Docker variant bind-mounts `example/`, so it shares `db.sqlite3` with the host — the in-container and host-run `seed` commands below reach the same database.
Everything below works identically against either fleet — connect Inspector to whichever is running and watch `worker_pid` and the structlog output to see which processes serve.
The automated version of the fleet proofs is `just multiworker` ([ADR-0019](../docs/adr/0019-multiworker-harness.md)): it boots both fleets itself and asserts the kill-the-fleet elicitation resume, so you only need the demo targets for interactive testing.

Seeding creates `mcp-test-user`, the user the bearer endpoints resolve the demo token to.
The bearer token `good-token` is a published demo constant, not a secret.

Two practical notes:

- **Port 8000 busy?** Run `uv run --with uvicorn uvicorn example.asgi:application --workers 4 --port 8001` and substitute the port below. The committed `.mcp.json` expects 8000, so the Claude Code auto-connect only works on the default port.
- **Launching from a coding-agent session?** Run the server detached (`setsid nohup … &`) — a session-scoped background process dies with the session, and the next session then finds a dead endpoint.

### The endpoints

| URL | Configuration |
|---|---|
| `/mcp/` | Open, no auth |
| `/mcp-b/` | A second server instance — "another worker in the fleet" |
| `/auth-mcp/` | Bearer auth (`good-token`), scope `mcp:read` |
| `/user-mcp/` | Bearer auth + Django user resolution |
| `/nouser-mcp/` | Bearer auth, resolver that finds no user |
| `/filtered-mcp/` | Tool visibility filtered by user permission |
| `/admin-mcp/` | Requires scope `mcp:admin`, which the demo token lacks |

The view serves **POST only**; any other method — including a bare GET expecting an SSE stream — gets an immediate `405`, because stateless MCP has no standing server-push channel ([ADR-0017](../docs/adr/0017-post-only-view.md)).
`CsrfViewMiddleware` does not block the endpoints: the view is CSRF-exempt, because MCP clients authenticate with bearer headers rather than the ambient cookies CSRF forgery relies on ([ADR-0018](../docs/adr/0018-example-auth-middleware.md)).

### More Inspector fixtures

Beyond the quick start's round-trip, also worth clicking: `test_input_required_result_multi_round` (chained elicitations), `…_multiple_inputs` (several inputs in one retry), and `…_tampered_state` (corrupt-state rejection).

A connected modern session's server log shows `server/discover` with **no** `initialize` handshake.
Inspector may report the same pid from `worker_pid` repeatedly: HTTP keep-alive pins its TCP connection to one worker.
That is connection affinity, not server state — the curl transcript below shows the real spread.

### Test permissions through Inspector

The permission cycle demonstrates both layers: *visibility filtering* (`PermittedToolsFilter`) and *execution gating* (the tool's own check) — and why only the second is a security boundary.

The grant/revoke state persists in `example/db.sqlite3` between runs, so start from a known state — the revoked default:

```sh
docker compose exec demo python manage.py seed --revoke-delete
```

(Running the host fleet instead? `uv run python manage.py seed --revoke-delete` — the bind mount means both forms reach the same database.)

1. Add a second Inspector server: URL `http://127.0.0.1:8000/filtered-mcp/`, Protocol Era **Modern**, and in the settings' auth section a bearer token of `good-token`.
2. Connect → List Tools. With the permission revoked, you see only `public_ping` — `delete_widget` is hidden.
3. Grant the permission and re-list:

   ```sh
   docker compose exec demo python manage.py seed --grant-delete
   ```

   `delete_widget` appears (each request re-evaluates — nothing is cached anywhere).
   Run it with `widget_id: 1` → `"deleted widget 1"`.
   (Run it *without* `widget_id` and you get a validation error, not a permission refusal — don't misread it in permission tests.)
4. Revoke, and — **without re-listing** — run `delete_widget` again from the still-visible entry:

   ```sh
   docker compose exec demo python manage.py seed --revoke-delete
   ```

   It is refused: *"You may not delete widgets."*
   The client could still name the tool; hiding it from `tools/list` was never the protection. **Tools must gate their own execution** ([ADR-0014](../docs/adr/0014-user-and-tool-permissions.md)).

For the user-resolution half, connect to `/user-mcp/` (same token): `current_username` returns `mcp-test-user`.
On the open `/mcp/` it returns `""` — Django's `AuthenticationMiddleware` supplies `AnonymousUser` when nothing authenticates the request.
And `/admin-mcp/` answers `403` to everything: the demo token lacks the `mcp:admin` scope.

### See statelessness with your own eyes (curl)

The demo fleet runs four worker processes with no sticky routing.
There is no `initialize` handshake — one request is a complete exchange:

```sh
curl -s -X POST http://127.0.0.1:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"worker_pid","arguments":{}}}'
```

Run it a few times: different pids answer.
Now start an elicitation (the spec's routing headers and `_meta` envelope are required for stateless input flows — omitting them reproduces the legacy-client failure):

```sh
curl -s -X POST http://127.0.0.1:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'mcp-protocol-version: 2026-07-28' \
  -H 'mcp-method: tools/call' \
  -H 'mcp-name: test_input_required_result_request_state' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"test_input_required_result_request_state","arguments":{},
                 "_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",
                          "io.modelcontextprotocol/clientCapabilities":{"elicitation":{}}}}}'
```

The result is `"resultType": "input_required"` with an encrypted `requestState`.
Copy that state and answer — the retry lands on whichever worker the OS picks, and it decrypts anyway, because `request_state_security()` keys from `SECRET_KEY` rather than the SDK's per-process random default:

```sh
curl -s -X POST http://127.0.0.1:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'mcp-protocol-version: 2026-07-28' \
  -H 'mcp-method: tools/call' \
  -H 'mcp-name: test_input_required_result_request_state' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call",
       "params":{"name":"test_input_required_result_request_state","arguments":{},
                 "inputResponses":{"confirm":{"action":"accept","content":{"ok":true}}},
                 "requestState":"<paste the requestState here>",
                 "_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",
                          "io.modelcontextprotocol/clientCapabilities":{"elicitation":{}}}}}'
```

Three harder variants, all verified against this project:

- **Cross-instance:** send the answer to `/mcp-b/` instead of `/mcp/` — a *different* `MCPServer` object completes a flow it never started.
- **Kill the fleet:** stop the server entirely between the two requests, start it again, then resume. It completes on processes that did not exist when the flow began — no process ever held the flow.
- **Tamper with the state:** change one character of the `requestState` and send it. Expect a clean `400` with `"Invalid or expired requestState"` — the `SECRET_KEY`-keyed crypto refusing, not a stack trace.

### Connect Claude Code (partial, as of July 2026)

As of this writing (July 2026), **Claude Code does not yet speak the `2026-07-28` protocol fully**, which is why the quick start uses [MCP Inspector](https://github.com/modelcontextprotocol/inspector) — its v2 line implements the full modern era, including the elicitation round-trip.

The repo ships a `.mcp.json`, so a Claude Code session opened in this repository automatically connects to `http://127.0.0.1:8000/mcp/` when the demo is running — the package dogfoods itself.
The server must be up **before** the session starts (or use `/mcp` → reconnect).

What works today: connection, `tools/list`, and plain tool calls.
What doesn't: any `test_input_required_result_*` tool fails with `MCP error -32603` — Claude Code sends no SEP-2322 capabilities envelope yet, so the server (correctly, per spec) refuses to return an `input_required` result.
That is a client gap, not a server one; when Claude's client speaks `2026-07-28` elicitation, the same tools will start working with no server change.

### Watch the logs while you test

The demo fleet prints structured flow logs — the optional `StructlogRequestLogger` middleware in action.
The elicitation round-trip is visible as two lines with a closed exit vocabulary, which is precisely what makes a paused flow distinguishable from a finished one in production log queries:

```
mcp.request.completed … method=tools/call exit=input_required
mcp.request.completed … method=tools/call exit=completed
```

### Watch a subscription stream (ASGI only)

`subscriptions/listen`'s POST response is a live SSE stream (SEP-2575).
Open one with curl against the ASGI demo, then trigger an event from a second terminal and watch the frame arrive:

```sh
curl -N -X POST http://127.0.0.1:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'mcp-protocol-version: 2026-07-28' \
  -H 'mcp-method: subscriptions/listen' \
  -d '{"jsonrpc":"2.0","id":1,"method":"subscriptions/listen",
       "params":{"notifications":{"toolsListChanged":true},
                 "_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",
                          "io.modelcontextprotocol/clientCapabilities":{}}}}'
```

The first frame is the acknowledgement; then, from another terminal, call the `test_trigger_tool_change` tool (any client — Inspector works) and a `notifications/tools/list_changed` frame appears on the open stream.
Under `just demo` (WSGI) the same request gets an explicit `501` — live streams need ASGI ([ADR-0020](../docs/adr/0020-subscription-streams.md)).
Note the in-memory bus is per-process: under the 4-worker demo, the trigger only reaches streams held by the worker that serves it — and the worker holding a stream wins *fewer* `accept()`s, so expect to fire the trigger tens of times (a real run took 31) before one lands.
That lottery is the live demonstration of why a real fleet wires an external `SubscriptionBus`; for a deterministic demo, run a single worker (`uvicorn example.asgi:application --workers 1`).

### Tools worth trying

- `add`, `multiply` — plain tools (`multiply` arrives via `mcp.py` autodiscovery).
- `worker_pid` — which process answered.
- `count_users`, `current_username`, `delete_widget` — ORM, resolved user, permission gating (on `/user-mcp/`); `delete_widget` requires a `widget_id` argument.
- `db_thread_info` — which worker thread served the call and whether it still holds a DB connection; call `count_users` then this to watch connection hygiene working ([ADR-0021](../docs/adr/0021-worker-thread-connection-hygiene.md)).
- `public_ping` vs `delete_widget` on `/filtered-mcp/` — tool visibility filtered per user.
- `test_input_required_result_*` — the SEP-2322 elicitation/sampling/roots fixtures the conformance suite also runs against.
