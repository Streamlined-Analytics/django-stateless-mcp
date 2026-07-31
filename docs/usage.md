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
[ADR-0007](https://github.com/Streamlined-Analytics/django-stateless-mcp/blob/main/docs/adr/0007-stateless-view-bridge.md).

## Registering tools from your apps

Add `django_stateless_mcp` to `INSTALLED_APPS` and each installed app's
`mcp.py` module is imported at startup — the same convention as `admin.py`:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "django_stateless_mcp",
]
```

```python
# myapp/mcp.py
from project.mcp import server


@server.tool()
def lookup_order(order_id: int) -> str:
    """Return the status of an order."""
    ...
```

Registration itself is the SDK's own API — `@server.tool()`,
`@server.resource()`, `@server.prompt()` — imported against whichever server
your project defines. Autodiscovery only guarantees the module is imported, so
apps can contribute tools without the URLconf knowing about them.

Apps without an `mcp.py` are skipped. An `mcp.py` that fails to import raises
at startup rather than being silently ignored.

## Reaching the Django request from a tool

Declare the SDK's `Context` parameter and pass it to `django_request()`:

```python
from mcp.server.mcpserver import Context

from django_stateless_mcp import django_request


@server.tool()
def whoami(ctx: Context) -> str:
    """Name the user making this MCP call."""
    return django_request(ctx).user.get_username()
```

The request is the real `HttpRequest` for the call — headers, `user`, and
anything your middleware attached — carried on the transport scope rather than
in any global.
Off the request path (for example calling a tool directly in a unit test) it
raises `LookupError` instead of returning `None`.

`request.user` exists only where something sets it: Django's
`AuthenticationMiddleware` (which gives `AnonymousUser` on unauthenticated
calls), or `mcp_view(user_resolver=…)` resolving it from the verified token.
On a project with neither, a tool touching `.user` raises `AttributeError` —
keep the standard auth middleware in `MIDDLEWARE`, as any conventional Django
project does.

The view is CSRF-exempt, so `CsrfViewMiddleware` in that standard stack does
not 403 your MCP endpoint.
CSRF forges the browser's ambient cookie credentials; MCP clients hold no CSRF
token and authenticate with a bearer header an attacker's page cannot set —
the same posture DRF takes for token-authenticated APIs.
If you deliberately put cookie-session authentication in front of an MCP
endpoint, that protection becomes yours to provide.

## Sync tools and the ORM

Plain `def` tools are run by the SDK in a worker thread, off the event loop, so
ORM access inside them just works — no `sync_to_async` needed:

```python
@server.tool()
def open_orders(ctx: Context) -> int:
    """Count open orders for the calling user."""
    user = django_request(ctx).user
    return Order.objects.filter(owner=user, closed=False).count()
```

`async def` tools run on the event loop, where the ORM raises
`SynchronousOnlyOperation`; wrap ORM work in `asgiref.sync.sync_to_async`
there, or keep database tools synchronous.

Connections opened by sync tools live in the SDK's worker threads, outside
Django's per-request cleanup; the view recycles them there after each request
with Django's own `close_old_connections`, so `CONN_MAX_AGE` and
`CONN_HEALTH_CHECKS` behave exactly as they do for ordinary views.

When testing tools that write and read the database, remember the tool's query
runs on a different connection than the test — use
`pytest.mark.django_db(transaction=True)` so fixture rows are committed and
visible to it.

## Subscription streams

On the 2026-07-28 wire there is no standing GET stream: a client opts in to
server events by POSTing `subscriptions/listen`, and **the response is the
stream** (SEP-2575).
The view serves it under **ASGI**: the SDK acknowledges first, then delivers
the requested event kinds as SSE frames until the client disconnects.
Under **WSGI** the view answers `501` instead — a live stream would pin a
worker for its whole lifetime, which is exactly the per-flow cost this package
exists to remove; request/response MCP is identical under both deployment
models, subscription streams are the one ASGI-only feature.

Publishing events is the SDK's seam, not this package's: pass a
`SubscriptionBus` to your server and publish to it —

```python
from mcp.server.mcpserver import MCPServer
from mcp.server.subscriptions import InMemorySubscriptionBus, ToolsListChanged

bus = InMemorySubscriptionBus()
server = MCPServer(name="my-server", subscriptions=bus)


async def on_tools_changed() -> None:
    await bus.publish(ToolsListChanged())
```

The in-memory bus reaches only streams held by the worker that published.
On a multi-worker fleet, implement `SubscriptionBus` over an external pub/sub
backend (Redis, NATS, …) so events fan out across replicas — the SDK protocol
is two methods, `publish` and `subscribe`.

## Requiring bearer authentication

Pass the SDK's `TokenVerifier` protocol to `mcp_view()` and the endpoint
requires OAuth bearer tokens:

```python
from myproject.auth import MyTokenVerifier

urlpatterns = [
    path(
        "mcp/",
        mcp_view(
            server,
            token_verifier=MyTokenVerifier(),
            required_scopes=["mcp:read"],
        ),
    ),
]
```

Every request is verified before dispatch — per-request verification is what a
stateless protocol wants.
Missing or invalid tokens get a `401` with a `WWW-Authenticate: Bearer`
challenge; a valid token lacking a required scope gets a `403`.
Inside tools, the SDK's own `get_access_token()` returns the verified token.

Without a `token_verifier` the endpoint is open, and protecting it is your
project's responsibility — session auth behind `login_required`, a private
network, or whatever the deployment calls for.

## Elicitation that survives your load balancer

Wire the SDK's request-state security from your Django settings and
elicitation works across a multi-worker fleet with no sticky routing:

```python
from mcp.server.mcpserver import MCPServer

from django_stateless_mcp import request_state_security

server = MCPServer(
    name="my-server",
    request_state_security=request_state_security(),
)
```

A tool that needs input returns the SDK's `InputRequiredResult`; the client
answers by re-issuing the call with `inputResponses` and the echoed
`requestState`.
That state is encrypted, and here is the part that matters: **the SDK's
default encryption key is random per process**, so with defaults a retry
landing on a different worker cannot decrypt it — the exact multi-worker
failure this package exists to remove.
`request_state_security()` keys from `SECRET_KEY` instead, so every worker
sharing your settings can resume any elicitation.

`SECRET_KEY_FALLBACKS` are included: Django's normal key-rotation story
covers in-flight elicitations too.
A tampered or expired `requestState` is rejected with a protocol error —
never accepted, never a crash.

## Structured request logging

Install the optional extra and register the middleware:

```sh
uv add "django-stateless-mcp[structlog]"
```

```python
from django_stateless_mcp import StructlogRequestLogger

server = MCPServer(
    name="my-server",
    middleware=[StructlogRequestLogger()],
)
```

Every request logs one event with queryable kwargs — `method`, `tool_name`,
`request_id`, `duration_ms`, and `exit`:

```
mcp.request.completed  method=tools/call tool_name=add duration_ms=3.1 exit=completed
mcp.request.completed  method=tools/call tool_name=confirm_order exit=input_required
mcp.request.failed     method=tools/call error_type=MCPError
```

An elicitation pause (`exit="input_required"`) is distinguishable from a
finished call, so multi-round flows can be reconstructed from logs.
Failures log at `warning` and **re-raise** — errors stay owned by the SDK's
protocol handling and your error tracker.

## Logging tool dispatch

Add the middleware to log one structured event per request:

```python
from django_stateless_mcp import StructlogRequestLogger

server = MCPServer(
    name="my-server",
    middleware=[StructlogRequestLogger()],
)
```

Each request logs `mcp.request.completed` at `info` — with `method`,
`tool_name`, `request_id`, `duration_ms`, and `exit` (`"completed"` or
`"input_required"`, so an elicitation pause is queryable apart from a finished
call). A failure logs `mcp.request.failed` at `warning` with the exception
type and then **re-raises** — the SDK's protocol handling and Sentry own
errors; the middleware only records that the flow ended that way.

Event names are dotted and stable and the variables are structlog kwargs, so
they render to JSON fields you can query (for example
`| json | duration_ms > 500`). Install the optional dependency with
`django-stateless-mcp[structlog]`, and configure structlog as your project
prefers.
