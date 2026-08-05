"""Tests pinning consumer-realistic configuration shapes.

Issue #45 shipped because the suite only ever ran the one configuration that
works: the ATOMIC_REQUESTS crash was invisible until the first production
deployment. These tests mirror what the real consumer projects actually run --
slash-less mounts, proxy-derived schemes, bracketing response middleware, and
database-backed token verification -- so divergences of that class surface in
CI rather than in production. See ADR-0032.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.test import Client, override_settings

from tests.test_views import MCP_HEADERS, post, request_body

SLASHLESS_URL = "/mcp"
DB_AUTH_URL = "/db-mcp/"


@pytest.fixture
def anyio_backend():
    """Run async tests on asyncio only; the SDK targets it."""
    return "asyncio"


def call_tool(client: Client, url: str, tool: str, token: str | None = None) -> Any:
    """POST a tools/call for ``tool`` with an optional bearer token."""
    headers = dict(MCP_HEADERS)
    if token is not None:
        headers["authorization"] = f"Bearer {token}"
    return client.post(
        url,
        data=request_body("tools/call", {"name": tool, "arguments": {}}),
        content_type="application/json",
        headers=headers,
    )


def tool_result(response: Any) -> Any:
    return json.loads(response.content)["result"]["structuredContent"]["result"]


def test_slashless_mount_serves_without_redirect(client):
    """POST /mcp (no trailing slash) serves directly, the way consumers mount it.

    APPEND_SLASH only ever redirects *toward* a slash, on a 404 -- and MCP
    clients do not re-POST through a redirect -- so the slash-less mount must
    match exactly, with CommonMiddleware in the stack.
    """
    response = post(client, "tools/list")
    slashless = client.post(
        SLASHLESS_URL,
        data=request_body("tools/list"),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    assert response.status_code == 200
    assert slashless.status_code == 200


def test_slashless_mount_reports_exact_path(client):
    """The Django request the tool sees carries the slash-less path verbatim."""
    response = call_tool(client, SLASHLESS_URL, "request_path")

    assert response.status_code == 200
    assert tool_result(response) == "/mcp"


def test_proxy_header_sets_https_scheme(client):
    """Behind a proxy, request.scheme -- and so the ASGI scope -- reads https.

    Consumers deploy behind Traefik with ``SECURE_PROXY_SSL_HEADER`` set; the
    bridge forwards ``request.scheme`` verbatim as the scope's ``scheme``.
    """
    with override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https")):
        response = call_tool(
            Client(headers={"x-forwarded-proto": "https"}),
            SLASHLESS_URL,
            "request_scheme",
        )

    assert tool_result(response) == "https"


def test_scheme_stays_http_without_proxy_setting(client):
    """The forwarded-proto header alone must not upgrade the scheme."""
    response = call_tool(
        Client(headers={"x-forwarded-proto": "https"}),
        SLASHLESS_URL,
        "request_scheme",
    )

    assert tool_result(response) == "http"


def test_bracketing_middleware_stamps_the_mcp_response(client):
    """Response-processing middleware first and last in the stack sees MCP responses."""
    response = post(client, "tools/call", {"name": "book_slug", "arguments": {"title": "Django"}})

    assert response.status_code == 200
    assert response.headers["X-Example-Bracket-Outer"] == "seen"
    assert response.headers["X-Example-Bracket-Inner"] == "seen"


def test_oversized_body_is_refused_not_500(client):
    """A body over DATA_UPLOAD_MAX_MEMORY_SIZE gets Django's 400, not a crash."""
    with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1):
        response = post(client, "tools/list")

    assert response.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_db_verifier_rejects_unknown_token(client):
    """A token with no matching database row is refused before dispatch."""
    response = call_tool(client, DB_AUTH_URL, "token_client", token="nobody")

    assert response.status_code == 401
    assert json.loads(response.content)["error"] == "invalid_token"


@pytest.mark.django_db(transaction=True)
def test_db_verifier_accepts_token_from_db(client):
    """A token backed by a database row verifies, one lookup per request."""
    User.objects.create_user(username="db-token-user")

    response = call_tool(client, DB_AUTH_URL, "token_client", token="db-token-user")

    assert response.status_code == 200
    assert tool_result(response) == "db-token-user"


@pytest.mark.django_db(transaction=True)
def test_db_verifier_resolves_the_django_user(client):
    """The resolver sets request.user from the same database row."""
    User.objects.create_user(username="db-token-user")

    response = call_tool(client, DB_AUTH_URL, "current_username", token="db-token-user")

    assert response.status_code == 200
    assert tool_result(response) == "db-token-user"


@pytest.mark.django_db(transaction=True)
@pytest.mark.anyio
async def test_db_verifier_accepts_token_under_asgi(async_client):
    """Database-backed verification holds on the ASGI path consumers deploy."""
    await sync_to_async(User.objects.create_user)(username="db-token-user")

    response = await async_client.post(
        DB_AUTH_URL,
        data=request_body("tools/call", {"name": "token_client", "arguments": {}}),
        content_type="application/json",
        headers={**MCP_HEADERS, "authorization": "Bearer db-token-user"},
    )

    assert response.status_code == 200
    assert tool_result(response) == "db-token-user"
