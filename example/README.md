# The runnable example project

A tiny but real Django project serving `django-stateless-mcp`, used two ways:

- **Launch it** to exercise the package as actual AI infrastructure — point Claude Code or MCP Inspector at it, watch elicitation resume across worker processes.
- **The test suite reuses it**: `tests/settings.py` inherits `example/settings.py`, and the pytest suite drives the same servers and URLs you can boot here.

See [ADR-0015](../docs/adr/0015-runnable-example-project.md) for why one project plays both roles.

## Run it

```sh
just demo        # WSGI: migrate + seed + runserver on :8000
just demo-asgi   # ASGI: migrate + seed + uvicorn with 4 worker processes
```

Seeding creates `mcp-test-user`, the user the bearer endpoints resolve the demo token to.
Toggle the permission the locked `delete_widget` tool gates on:

```sh
uv run python manage.py seed --grant-delete
uv run python manage.py seed --revoke-delete
```

## The endpoints

| URL | Configuration |
|---|---|
| `/mcp/` | Open, no auth |
| `/mcp-b/` | A second server instance — "another worker in the fleet" |
| `/auth-mcp/` | Bearer auth (`good-token`), scope `mcp:read` |
| `/user-mcp/` | Bearer auth + Django user resolution |
| `/nouser-mcp/` | Bearer auth, resolver that finds no user |
| `/filtered-mcp/` | Tool visibility filtered by user permission |
| `/admin-mcp/` | Requires scope `mcp:admin`, which the demo token lacks |

The bearer token `good-token` is a published demo constant, not a secret.

## Call a tool

There is no `initialize` handshake — one request is a complete exchange:

```sh
curl -s -X POST http://127.0.0.1:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"add","arguments":{"a":2,"b":3}}}'
```

## See statelessness with your own eyes

Under `just demo-asgi` there are four worker processes and no sticky routing.
The `worker_pid` tool names the process serving each call:

```sh
curl -s -X POST http://127.0.0.1:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"worker_pid","arguments":{}}}'
```

Run it a few times: different pids answer.
Now start an elicitation (the spec's routing headers and `_meta` envelope are required for stateless input flows):

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

You can even stop the server between the two requests and start it again: the resume still works, because nothing about the flow lives in any process.

## Connect a real AI client

The repo ships a `.mcp.json`, so a Claude Code session opened in this repository automatically connects to `http://127.0.0.1:8000/mcp/` when the demo is running — the package dogfoods itself.
For any other client, register the same URL as a streamable-HTTP server; for the authenticated endpoints add the header `Authorization: Bearer good-token`.

MCP Inspector works too, and has full elicitation UI:

```sh
npx @modelcontextprotocol/inspector
```

## Tools worth trying

- `add`, `multiply` — plain tools (multiply arrives via `mcp.py` autodiscovery).
- `worker_pid` — which process answered.
- `count_users`, `current_username`, `delete_widget` — ORM, resolved user, permission gating (on `/user-mcp/`).
- `public_ping` vs `delete_widget` on `/filtered-mcp/` — tool visibility filtered per user.
- `test_input_required_result_*` — the SEP-2322 elicitation/sampling/roots fixtures the conformance suite also runs against.
