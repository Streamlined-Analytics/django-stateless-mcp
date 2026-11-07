# Recipe: OAuth with django-allauth

This recipe uses
[django-allauth's OpenID Connect provider](https://docs.allauth.org/en/latest/idp/openid-connect/)
as the authorization server for a protected `django-stateless-mcp` endpoint.
It is an alternative to the
[django-oauth-toolkit recipe](oauth-and-permissions.md): allauth issues and
stores the access tokens, while `mcp_view` verifies them and resolves them to
the Django user making each MCP request.

The result supports the OAuth authorization-code flow and server discovery.
allauth also supports both MCP client-onboarding mechanisms out of the box:
Dynamic Client Registration (DCR), where a client registers its metadata at
runtime, and Client ID Metadata Documents (CIMD), where an HTTPS metadata URL is
itself the client ID. Enable either mechanism so compatible MCP clients can
configure themselves without manually provisioned client credentials.

## Install and configure the provider

Follow the allauth installation manual to setup `allauth.account` and
`allauth.idp`. For our use case, these settings are most relevant:

```python
IDP_OIDC_PRIVATE_KEY = os.environ["IDP_OIDC_PRIVATE_KEY"].replace(r"\n", "\n")

# Let MCP clients register themselves.
IDP_OIDC_DCR_ENABLED = True
IDP_OIDC_DCR_REQUIRES_INITIAL_ACCESS_TOKEN = False
```

## Advertise the MCP scope

Define the scope once, then use an OIDC adapter to add it to the consent screen
and the authorization server's discovery metadata:

```python
# myproject/oidc.py
from allauth.idp.oidc.adapter import DefaultOIDCAdapter
from django.utils.translation import gettext_lazy as _

MCP_SCOPE = "mcp"


class OIDCAdapter(DefaultOIDCAdapter):
    scope_display = {
        **DefaultOIDCAdapter.scope_display,
        MCP_SCOPE: _("Access the MCP server"),
    }

    def populate_server_metadata(self, data: dict[str, object]) -> None:
        data["scopes_supported"].append(MCP_SCOPE)
```

Select it in settings:

```python
IDP_OIDC_ADAPTER = "myproject.oidc.OIDCAdapter"
```

## Verify tokens and resolve users

`mcp_view` expects the MCP SDK's async `TokenVerifier` protocol. allauth's
`Token.objects.lookup()` performs the appropriate hashed-token lookup and
rejects expired tokens:

```python
# myproject/mcp_auth.py
from allauth.idp.oidc.models import Token
from asgiref.sync import sync_to_async
from mcp.server.auth.provider import AccessToken


class AllauthTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        oidc_token = await sync_to_async(self._lookup)(token)
        if oidc_token is None:
            return None
        return AccessToken(
            token=token,
            client_id=oidc_token.client.id,
            scopes=oidc_token.get_scopes(),
        )

    def _lookup(self, token: str) -> Token | None:
        oidc_token = Token.objects.select_related("client", "user").lookup(
            Token.Type.ACCESS_TOKEN,
            token,
        )
        return oidc_token if oidc_token and oidc_token.user.is_active else None


async def user_for_token(token: str):
    return await sync_to_async(_user)(token)


def _user(token: str):
    oidc_token = Token.objects.select_related("user").lookup(
        Token.Type.ACCESS_TOKEN,
        token,
    )
    return oidc_token.user if oidc_token and oidc_token.user.is_active else None
```


## Publish protected-resource metadata

MCP clients discover the authorization server through OAuth Protected Resource
Metadata. Publish it at the well-known URL corresponding to the `/mcp`
resource:

```python
# myproject/mcp_views.py
from django.http import JsonResponse
from django.urls import reverse

from myproject.oidc import MCP_SCOPE


def oauth_protected_resource_metadata(request):
    origin = request.build_absolute_uri("/").rstrip("/")
    return JsonResponse(
        {
            "resource": request.build_absolute_uri(reverse("mcp")),
            "authorization_servers": [origin],
            "scopes_supported": [MCP_SCOPE],
        }
    )
```

Finally, protect the endpoint and expose its metadata:

```python
# urls.py
from django.urls import path
from django_stateless_mcp import mcp_view

from myproject.mcp import server
from myproject.mcp_auth import AllauthTokenVerifier, user_for_token
from myproject.mcp_views import oauth_protected_resource_metadata
from myproject.oidc import MCP_SCOPE

urlpatterns += [
    path(
        "mcp",
        mcp_view(
            server,
            token_verifier=AllauthTokenVerifier(),
            required_scopes=[MCP_SCOPE],
            user_resolver=user_for_token,
        ),
        name="mcp",
    ),
    path(
        ".well-known/oauth-protected-resource/mcp",
        oauth_protected_resource_metadata,
        name="mcp_oauth_protected_resource_metadata",
    ),
]
```

The authorization server now advertises the `mcp` scope and the resource
server requires it. `user_resolver` also places the token's active Django user
on `request.user`, so tools can use ordinary Django permissions. Follow the
[permission-locking and tool-hiding sections](oauth-and-permissions.md#permission-locking-a-tool)
of the django-oauth-toolkit recipe; those parts are provider-independent.
