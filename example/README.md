# The runnable example project

A tiny but real Django project serving `django-stateless-mcp`, used two ways:

- **Launch it** to exercise the package as actual AI infrastructure — watch elicitation resume across worker processes, toggle tool permissions live, kill the whole fleet mid-flow and resume anyway.
- **The test suite reuses it**: `tests/settings.py` inherits `example/settings.py`, and the pytest suite drives the same servers and URLs you can boot here.

See [ADR-0015](../docs/adr/0015-runnable-example-project.md) for why one project plays both roles.
Everything below is a walkthrough you can reproduce end to end; each step was run against this project before being written down.

> **Which client should I test with?**
> As of this writing (July 2026), **Claude Code does not yet speak the `2026-07-28` protocol fully**: it connects and calls plain tools over stateless streamable HTTP, but it sends no SEP-2322 capabilities envelope, so any elicitation flow fails client-side with `MCP error -32603: Handler returned an invalid result`.
> **[MCP Inspector](https://github.com/modelcontextprotocol/inspector) is the way to test this package properly** — its v2 line implements the full modern era, including the elicitation round-trip. The walkthrough below uses it.

## 1. Run the server

```sh
just demo-asgi   # migrate + seed + uvicorn with FOUR worker processes on :8000
just demo        # the same project under WSGI (single-process dev server)
```

Seeding creates `mcp-test-user`, the user the bearer endpoints resolve the demo token to.
The bearer token `good-token` is a published demo constant, not a secret.

Two practical notes:

- **Port 8000 busy?** Run `uv run --with uvicorn uvicorn example.asgi:application --workers 4 --port 8001` and substitute the port below. The committed `.mcp.json` expects 8000, so the Claude Code auto-connect only works on the default port.
- **Launching from a coding-agent session?** Run the server detached (`setsid nohup … &`) — a session-scoped background process dies with the session, and the next session then finds a dead endpoint.

## 2. The endpoints

| URL | Configuration |
|---|---|
| `/mcp/` | Open, no auth |
| `/mcp-b/` | A second server instance — "another worker in the fleet" |
| `/auth-mcp/` | Bearer auth (`good-token`), scope `mcp:read` |
| `/user-mcp/` | Bearer auth + Django user resolution |
| `/nouser-mcp/` | Bearer auth, resolver that finds no user |
| `/filtered-mcp/` | Tool visibility filtered by user permission |
| `/admin-mcp/` | Requires scope `mcp:admin`, which the demo token lacks |

The view serves **POST only**; any other method gets an immediate `405` ([ADR-0017](../docs/adr/0017-post-only-view.md)).

## 3. Test with MCP Inspector

```sh
npx @modelcontextprotocol/inspector
```

Open the tokened URL it prints, then connect:

1. **Transport Type:** Streamable HTTP. **URL:** `http://127.0.0.1:8000/mcp/`.
2. **Set Protocol Era to "Modern" — this is the step everyone misses.**
   Open the server's settings (the edit control on the server entry); in the **Options** section, change **Protocol Era** from its default, *Legacy (2025-11-25 handshake)*, to **Modern**, which pins `2026-07-28`.
   Don't use *Auto* — it can fall back to legacy.
   The symptom of a legacy connection is exactly the Claude Code failure: elicitation tools error with *"Handler returned an invalid result"*.
   A connected modern session shows a **Modern** era badge, and the server log shows `server/discover` with **no** `initialize` handshake.
3. **Connect**, then in the **Tools** tab click **List Tools**.
   Expect `add`, `multiply`, `worker_pid`, `count_users`, and the `test_input_required_result_*` fixtures.
4. Run `add` with `a=2, b=3` → `5`. Run `worker_pid` a few times.
   (Inspector may report the same pid repeatedly: HTTP keep-alive pins its TCP connection to one worker. That is connection affinity, not server state — the curl transcript below shows the real spread.)
5. **The elicitation round-trip:** run `test_input_required_result_elicitation`.
   Inspector pauses at a pending-request modal asking for a name; submit it, and Inspector automatically retries with the returned `requestState` → the tool completes with a greeting.
   In the server log that is two independent requests: `exit=input_required`, then `exit=completed`.
6. Also worth clicking: `test_input_required_result_multi_round` (chained elicitations), `…_multiple_inputs` (several inputs in one retry), and `…_tampered_state` (corrupt-state rejection).

## 4. Test permissions through Inspector

The permission cycle demonstrates both layers: *visibility filtering* (`PermittedToolsFilter`) and *execution gating* (the tool's own check) — and why only the second is a security boundary.

1. Add a second Inspector server: URL `http://127.0.0.1:8000/filtered-mcp/`, Protocol Era **Modern**, and in the settings' auth section a bearer token of `good-token`.
2. Connect → List Tools. Fresh from `seed`, the demo user lacks the permission, so you see only `public_ping` — `delete_widget` is hidden.
3. Grant the permission and re-list:

   ```sh
   uv run python manage.py seed --grant-delete
   ```

   `delete_widget` appears (each request re-evaluates — nothing is cached anywhere).
   Run it with `widget_id: 1` → `"deleted widget 1"`.
4. Revoke, and — **without re-listing** — run `delete_widget` again from the still-visible entry:

   ```sh
   uv run python manage.py seed --revoke-delete
   ```

   It is refused: *"You may not delete widgets."*
   The client could still name the tool; hiding it from `tools/list` was never the protection. **Tools must gate their own execution** ([ADR-0014](../docs/adr/0014-user-and-tool-permissions.md)).

For the user-resolution half, connect to `/user-mcp/` (same token): `current_username` returns `mcp-test-user`.
On the open `/mcp/` it returns `""` — Django's `AuthenticationMiddleware` supplies `AnonymousUser` when nothing authenticates the request.
And `/admin-mcp/` answers `403` to everything: the demo token lacks the `mcp:admin` scope.

## 5. See statelessness with your own eyes (curl)

Under `just demo-asgi` there are four worker processes and no sticky routing.
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

## 6. Connect Claude Code (partial, as of July 2026)

The repo ships a `.mcp.json`, so a Claude Code session opened in this repository automatically connects to `http://127.0.0.1:8000/mcp/` when the demo is running — the package dogfoods itself.
The server must be up **before** the session starts (or use `/mcp` → reconnect).

What works today: connection, `tools/list`, and plain tool calls.
What doesn't: any `test_input_required_result_*` tool fails with `MCP error -32603` — Claude Code sends no SEP-2322 capabilities envelope yet, so the server (correctly, per spec) refuses to return an `input_required` result.
That is a client gap, not a server one; when Claude's client speaks `2026-07-28` elicitation, the same tools will start working with no server change.
Until then, Inspector (section 3) is the reference client for the full flow.

## 7. Watch the logs while you test

`just demo-asgi` prints structured flow logs — the optional `StructlogRequestLogger` middleware in action.
The elicitation round-trip is visible as two lines with a closed exit vocabulary, which is precisely what makes a paused flow distinguishable from a finished one in production log queries:

```
mcp.request.completed … method=tools/call exit=input_required
mcp.request.completed … method=tools/call exit=completed
```

## Tools worth trying

- `add`, `multiply` — plain tools (`multiply` arrives via `mcp.py` autodiscovery).
- `worker_pid` — which process answered.
- `count_users`, `current_username`, `delete_widget` — ORM, resolved user, permission gating (on `/user-mcp/`); `delete_widget` requires a `widget_id` argument.
- `public_ping` vs `delete_widget` on `/filtered-mcp/` — tool visibility filtered per user.
- `test_input_required_result_*` — the SEP-2322 elicitation/sampling/roots fixtures the conformance suite also runs against.

## Gotchas collected from real runs

- **Inspector defaults to the Legacy protocol era** — set Modern per section 3, or elicitation fails exactly like a legacy client.
- **The grant/revoke state persists** in `example/db.sqlite3` between runs — start permission demos with `seed --revoke-delete` if you want the hidden-tool state.
- **A bare GET is answered with `405`**, not an SSE stream — stateless MCP has no server-push channel ([ADR-0017](../docs/adr/0017-post-only-view.md)).
- **`delete_widget` without `widget_id`** is a validation error, not a permission refusal — don't misread it in permission tests.
