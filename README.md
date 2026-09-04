# django-stateless-mcp

![PyPI version](https://img.shields.io/pypi/v/django-stateless-mcp.svg)
[![Documentation status](https://readthedocs.org/projects/django-stateless-mcp/badge/?version=stable)](https://django-stateless-mcp.readthedocs.io/)

An [MCP](https://modelcontextprotocol.io) (Model Context Protocol) server is
how AI agents — Claude Code, ChatGPT, and the assistants built on them —
connect to your application in a controlled way: they see and call only the
tools you choose to expose, under the permissions you enforce. As your users
lean on AI for more of their work, it pays to be ready to accommodate their
agents without loosening the protections Django already gives your data and
infrastructure — and that is what this package is for.

django-stateless-mcp is a stateless MCP server for Django, built on the
[**2026-07-28** spec](https://modelcontextprotocol.io/specification/2026-07-28).
An MCP endpoint becomes an ordinary Django view — no sessions, no SSE, no
sticky routing, and no dedicated single-process service.

* [GitHub](https://github.com/Streamlined-Analytics/django-stateless-mcp/) | [PyPI](https://pypi.org/project/django-stateless-mcp/) | [Documentation](https://django-stateless-mcp.readthedocs.io/)
* Created by [Ben Atkinson](https://streamlinedanalytics.co.uk) | GitHub [@BenA-SA](https://github.com/BenA-SA)
* MIT License

## Why use this

* **Your MCP server is an ordinary Django view** — same deployment, same
  middleware, same monitoring, and tools call your models and business logic
  directly. No separate MCP service to build, secure, and operate.
* **It scales like the rest of your Django app** — any worker on any instance
  can serve any request, including an elicitation answer. See
  [Why stateless](https://django-stateless-mcp.readthedocs.io/en/stable/why-stateless/)
  for what changed on 2026-07-28 to make that possible.
* **Tools can ask the user questions** — fill in missing form fields, or
  require explicit confirmation before an update or delete, resuming on
  whichever worker the answer lands on: `request_state_security()` keys the
  resume state from `SECRET_KEY`. See the
  [elicitation recipe](https://django-stateless-mcp.readthedocs.io/en/stable/recipes/elicitation-forms-and-confirmations/).
* **Kick off a long job, keep chatting, and the result comes back when it's
  ready** — see the
  [long-running jobs recipe](https://django-stateless-mcp.readthedocs.io/en/stable/recipes/long-running-jobs/).
* **Tools can render a page inside the chat** — a Django template the client
  shows in a sandboxed iframe, with buttons that call your tools; the route to
  a confirmation on Claude.ai and ChatGPT, which have no elicitation. See the
  [MCP Apps recipe](https://django-stateless-mcp.readthedocs.io/en/stable/recipes/mcp-apps/).
* **Your authentication and permissions work inside tools** — bearer auth
  resolves to a real Django user, so `user.has_perm(...)` just works, and
  `PermittedToolsFilter` hides tools a user may not use from `tools/list`.
* **You can see what your MCP is doing** — optional structlog middleware logs
  one queryable event per request.
* **Tools register the Django way** — each app's `mcp.py` is discovered
  automatically, exactly like `admin.py`.

## Usage

```python
# myproject/mcp.py
from mcp.server.mcpserver import MCPServer

from django_stateless_mcp import request_state_security

server = MCPServer(
    name="my-server",
    version="1.0.0",
    request_state_security=request_state_security(),
)


@server.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b
```

```python
# urls.py
from django.urls import path

from django_stateless_mcp import mcp_view
from myproject.mcp import server

urlpatterns = [path("mcp/", mcp_view(server))]
```

That is the whole integration. The endpoint runs under both WSGI and ASGI.

## What it provides

* **`mcp_view(server)`** — serve an `MCPServer` as a stateless streamable-HTTP
  Django view, optionally requiring OAuth bearer auth via a `token_verifier`.
* **`mcp.py` autodiscovery** — add `django_stateless_mcp` to `INSTALLED_APPS`
  and each app's `mcp.py` registers tools, like `admin.py`.
* **`request_state_security()`** — key the SDK's elicitation-resume encryption
  from `SECRET_KEY`, so elicitation survives a multi-worker deployment.
* **`django_request(ctx)`** — reach the authenticated Django request from inside
  a tool, with no global state.
* **`StructlogRequestLogger`** — optional flow-logging middleware.
* **Subscription streams** — clients can subscribe to server-pushed events
  under ASGI; under WSGI the endpoint declines cleanly rather than pinning a
  worker.

Tool registration, elicitation, resources and prompts are the MCP SDK's own API;
this package is the Django layer around it.

## Supported versions

* Python 3.10–3.14 (3.10 and 3.11 with Django 5.2 LTS only, matching Django's own support)
* Django 5.2 LTS and 6.0
* `mcp` 2.0.x

Each is exercised in CI, along with an advisory job tracking the SDK's git main.

## Try it live

The repo ships a runnable example project. `docker compose up` starts it
behind four worker processes (no local uv or Python needed; `just demo-asgi`
is the host-run equivalent); the
[example README](https://github.com/Streamlined-Analytics/django-stateless-mcp/blob/main/example/README.md)
quick start walks through watching an elicitation started on one worker resume
on another — the package's thesis, observable with curl or any MCP client.

## Documentation

Full documentation, including a worked elicitation example and the design
decisions behind the package, is at
**<https://django-stateless-mcp.readthedocs.io/>**.

## Development

Contributors: [ARCHITECTURE.md](https://github.com/Streamlined-Analytics/django-stateless-mcp/blob/main/ARCHITECTURE.md)
maps how the package works and the invariants every change must preserve;
[CONTRIBUTING.md](https://github.com/Streamlined-Analytics/django-stateless-mcp/blob/main/CONTRIBUTING.md)
covers the workflow.

```bash
git clone git@github.com:Streamlined-Analytics/django-stateless-mcp.git
cd django-stateless-mcp
uv sync

uv run pytest                        # quick run: locked Django
uvx --with tox-uv tox run -f py313   # the full matrix: Django 5.2 + 6.0
just qa                              # format, lint, type check, test
just conformance                     # the official MCP conformance suite
```

## Author

django-stateless-mcp was created in 2026 by Ben Atkinson.

Started from the [audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) template.
