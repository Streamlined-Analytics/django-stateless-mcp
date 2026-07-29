"""URLconf for the example project, shared with the test suite.

Each endpoint demonstrates one configuration of ``mcp_view`` — open,
bearer-authenticated, user-resolving, permission-filtered — and the tests
assert against the same URLs the demo serves.
"""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, path

from django_stateless_mcp import mcp_view
from example.mcp_server import (
    StubVerifier,
    resolve_no_user,
    resolve_stub_user,
    server,
    server_b,
    server_filtered,
)

urlpatterns: list[URLPattern | URLResolver] = [
    path("mcp/", mcp_view(server)),
    path("mcp-b/", mcp_view(server_b)),
    path(
        "auth-mcp/",
        mcp_view(
            server,
            token_verifier=StubVerifier(),
            required_scopes=["mcp:read"],
        ),
    ),
    path(
        "user-mcp/",
        mcp_view(
            server,
            token_verifier=StubVerifier(),
            required_scopes=["mcp:read"],
            user_resolver=resolve_stub_user,
        ),
    ),
    path(
        "nouser-mcp/",
        mcp_view(
            server,
            token_verifier=StubVerifier(),
            required_scopes=["mcp:read"],
            user_resolver=resolve_no_user,
        ),
    ),
    path(
        "filtered-mcp/",
        mcp_view(
            server_filtered,
            token_verifier=StubVerifier(),
            required_scopes=["mcp:read"],
            user_resolver=resolve_stub_user,
        ),
    ),
    path(
        "admin-mcp/",
        mcp_view(
            server,
            token_verifier=StubVerifier(),
            required_scopes=["mcp:admin"],
        ),
    ),
]
