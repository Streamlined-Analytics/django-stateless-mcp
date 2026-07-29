# django-stateless-mcp

![PyPI version](https://img.shields.io/pypi/v/django-stateless-mcp.svg)

A stateless Model Context Protocol server for Django, built on the **2026-07-28**
spec. An MCP endpoint becomes an ordinary Django view — no sessions, no SSE, no
sticky routing, and no dedicated single-process service.

* [GitHub](https://github.com/Streamlined-Analytics/django-stateless-mcp/) | [PyPI](https://pypi.org/project/django-stateless-mcp/) | [Documentation](https://django-stateless-mcp.readthedocs.io/)
* Created by [Ben Atkinson](https://streamlinedanalytics.co.uk) | GitHub [@BenA-SA](https://github.com/BenA-SA)
* MIT License

## Why stateless

Before 2026-07-28, MCP needed a persistent connection: elicitation held an open
stream and a blocked worker, so a reply that round-robined to another worker
failed. The 2026-07-28 spec makes MCP plain request/response HTTP — Django's home
turf — and turns elicitation into a retry any instance can serve. That is the
change this package is built on; see
[Why stateless](https://django-stateless-mcp.readthedocs.io/why-stateless/) for
the full story.

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

Tool registration, elicitation, resources and prompts are the MCP SDK's own API;
this package is the Django layer around it.

## Supported versions

* Python 3.12–3.14
* Django 5.2 LTS and 6.0
* `mcp` 2.0.x

Each is exercised in CI, along with an advisory job tracking the SDK's git main.

## Documentation

Full documentation, including a worked elicitation example and the design
decisions behind the package, is at
**<https://django-stateless-mcp.readthedocs.io/>**.

## Development

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
