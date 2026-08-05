# Recipe: OAuth and per-user tool permissions

This recipe wires an MCP endpoint to
[django-oauth-toolkit](https://django-oauth-toolkit.readthedocs.io/) (DOT) so an
MCP client such as Claude authenticates with OAuth, then permission-locks and
hides tools per Django user.

**This is the posture to default to in production.**
An open endpoint can only ever serve anonymous callers; verifying each request
is what makes the package's access-control features work, and it is what turns
an MCP server from "some tools on a URL" into a real per-user product surface:

- **Every request is authenticated** — per-request bearer verification, the
  natural fit for a stateless protocol; unauthenticated calls get a clean `401`
  challenge, out-of-scope tokens a `403`.
- **A real Django user** — the verified token resolves to `request.user`, so
  the users, groups, and permissions your project already manages apply inside
  tools unchanged.
- **Access control per tool** — tools gate execution with `user.has_perm(...)`,
  and `PermittedToolsFilter` hides tools a user may not use from `tools/list`,
  so different users see and can do different things through the same endpoint.
- **Clients onboard themselves** — Dynamic Client Registration
  ([django-oauth-toolkit-dcr](https://pypi.org/project/django-oauth-toolkit-dcr/))
  lets an MCP client register automatically, so connecting an agent never means
  handing out client credentials by hand.

The layers are independent, and only the last is this package's job:

| Layer | Package | Serves |
|---|---|---|
| Authorization server | `django-oauth-toolkit` | `/o/authorize/`, `/o/token/` |
| Dynamic Client Registration | `django-oauth-toolkit-dcr` | `/o/register/` |
| Discovery metadata | your Django views | `.well-known/*` |
| **Resource server (the MCP endpoint)** | **django-stateless-mcp** | `/mcp` |

DOT and DCR are configured exactly as their own docs describe; this recipe only
covers the seam into `mcp_view`.

## The token verifier

`mcp_view` verifies each request through the SDK's `TokenVerifier` protocol —
one async method returning the SDK's `AccessToken` or `None`. Back it with DOT's
token store:

```python
# myproject/mcp_auth.py
from asgiref.sync import sync_to_async
from mcp.server.auth.provider import AccessToken
from oauth2_provider.models import AccessToken as DOTToken


class DOTTokenVerifier:
    """Validate a bearer token against django-oauth-toolkit's store."""

    async def verify_token(self, token: str) -> AccessToken | None:
        dot = await sync_to_async(self._lookup)(token)
        if dot is None:
            return None
        return AccessToken(
            token=token,
            client_id=dot.application.client_id,
            scopes=dot.scope.split(),
        )

    def _lookup(self, token: str) -> DOTToken | None:
        dot = DOTToken.objects.filter(token=token).select_related("application").first()
        if dot is None or not dot.is_valid():
            return None
        return dot
```

`sync_to_async` is required because `verify_token` runs on the event loop and the
lookup is ORM.

## Resolving the Django user

To permission-check inside tools you need the Django `User`, not just the token.
A `user_resolver` — an async `(token) -> user` — sets `request.user`, so tools
read it the ordinary way:

```python
from asgiref.sync import sync_to_async
from oauth2_provider.models import AccessToken as DOTToken


async def user_for_token(token: str):
    return await sync_to_async(_user)(token)


def _user(token: str):
    dot = DOTToken.objects.filter(token=token).select_related("user").first()
    return dot.user if dot and dot.is_valid() else None
```

## Wiring it up

```python
# urls.py
from django.urls import path

from django_stateless_mcp import mcp_view
from myproject.mcp import server
from myproject.mcp_auth import DOTTokenVerifier, user_for_token

urlpatterns = [
    path(
        "mcp",
        mcp_view(
            server,
            token_verifier=DOTTokenVerifier(),
            required_scopes=["mcp"],
            user_resolver=user_for_token,
        ),
    ),
]
```

## Permission-locking a tool

With `request.user` populated, gating execution is ordinary Django:

```python
@server.tool()
def delete_company(ctx: Context, company_id: int) -> str:
    """Delete a company. Requires the delete_company permission."""
    if not django_request(ctx).user.has_perm("companies.delete_company"):
        raise PermissionError("You may not delete companies.")
    ...
```

`user.has_perm` here is fine: tools run in a worker thread, off the event loop.

## Hiding tools the user cannot use

Add `PermittedToolsFilter` so `tools/list` only returns tools a user may use —
the client never even learns a forbidden tool exists:

```python
from django_stateless_mcp import PermittedToolsFilter

_TOOL_PERMS = {"delete_company": "companies.delete_company"}


def tool_visible(user, tool_name: str) -> bool:
    permission = _TOOL_PERMS.get(tool_name)
    return permission is None or user.has_perm(permission)


server = MCPServer(
    name="my-server",
    request_state_security=request_state_security(),
    middleware=[PermittedToolsFilter(tool_visible)],
)
```

`tool_visible` is a plain synchronous predicate; the filter runs it in a worker
thread, so `has_perm` is safe there too.

!!! danger "Hiding is not gating"
    Visibility filtering is least-knowledge ergonomics, **not** a security
    boundary. Nothing stops a client calling a hidden tool by name, so the tool
    must still gate its own execution (above). Use both together: gate to be
    safe, hide to be tidy.
