"""URLconf fixture for the test suite."""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, path

from django_stateless_mcp import mcp_view
from tests.mcp_server import (
    StubVerifier,
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
