"""URLconf fixture for the test suite."""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, path

from django_stateless_mcp import mcp_view
from tests.mcp_server import StubVerifier, server

urlpatterns: list[URLPattern | URLResolver] = [
    path("mcp/", mcp_view(server)),
    path(
        "auth-mcp/",
        mcp_view(
            server,
            token_verifier=StubVerifier(),
            required_scopes=["mcp:read"],
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
