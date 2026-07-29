# Usage

Build an `MCPServer` as you normally would with the MCP SDK, then mount it with
`mcp_view()`:

```python
# myapp/mcp.py
from mcp.server.mcpserver import MCPServer

server = MCPServer(name="my-server", version="1.0.0")


@server.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b
```

```python
# urls.py
from django.urls import path

from django_stateless_mcp import mcp_view
from myapp.mcp import server

urlpatterns = [
    path("mcp/", mcp_view(server)),
]
```

That is the whole integration. The endpoint is an ordinary Django view: it needs
no session store, no sticky routing, and no dedicated process.

## What you get

Clients call the endpoint directly — **there is no `initialize` handshake**, so a
single request is a complete exchange:

```console
$ curl -sX POST http://localhost:8000/mcp/ \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
         "params":{"name":"add","arguments":{"a":2,"b":3}}}'
{"jsonrpc":"2.0","id":1,"result":{"content":[{"text":"5","type":"text"}],
 "isError":false,"structuredContent":{"result":5}}}
```

Responses carry no session identifier, which is what lets any worker serve any
request. See [Why stateless](why-stateless.md) for why that matters.

## WSGI and ASGI

The view is asynchronous, so it runs natively under ASGI. Under WSGI, Django
starts an event loop per request to run it — the same view serves both, with no
configuration.

## Host validation

Host checking is left to Django's `ALLOWED_HOSTS`. The SDK's own DNS-rebinding
protection is disabled deliberately, so that host policy has a single home in
your project settings rather than two. See
[ADR-0007](adr/0007-stateless-view-bridge.md).
