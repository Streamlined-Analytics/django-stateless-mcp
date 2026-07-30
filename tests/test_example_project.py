"""Tests for the runnable example project's own scaffolding.

The example's servers and URLs are exercised throughout test_views; this
file covers the pieces that only exist for the live demo — the seed
command and the worker_pid tool.
"""

from __future__ import annotations

import json
import os

import pytest
from django.core.management import call_command

from tests.test_views import MCP_HEADERS, MCP_URL, request_body


@pytest.mark.django_db
def test_seed_creates_demo_user_without_perm():
    """A plain seed creates the resolver's user with no permissions."""
    from django.contrib.auth.models import User

    call_command("seed")

    user = User.objects.get(username="mcp-test-user")
    assert not user.has_perm("auth.delete_user")


@pytest.mark.django_db
def test_seed_toggles_delete_permission():
    """--grant-delete and --revoke-delete flip the locked tool's permission."""
    from django.contrib.auth.models import User

    call_command("seed", "--grant-delete")
    assert User.objects.get(username="mcp-test-user").has_perm("auth.delete_user")

    call_command("seed", "--revoke-delete")
    assert not User.objects.get(username="mcp-test-user").has_perm("auth.delete_user")


@pytest.mark.django_db
def test_seed_is_idempotent():
    """Reseeding never duplicates the demo user."""
    from django.contrib.auth.models import User

    call_command("seed")
    call_command("seed")

    assert User.objects.filter(username="mcp-test-user").count() == 1


@pytest.mark.django_db
def test_current_username_is_anonymous_on_the_open_endpoint(client):
    """A .user tool on the open endpoint sees AnonymousUser, not a crash.

    Found live in Inspector: without AuthenticationMiddleware the request has
    no ``user`` attribute at all, so ``current_username`` raised
    ``AttributeError`` on ``/mcp/``. The example now carries the standard auth
    middleware a real project would, and the anonymous username is ``""``.
    """
    response = client.post(
        MCP_URL,
        data=request_body("tools/call", {"name": "current_username", "arguments": {}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    result = json.loads(response.content)["result"]
    assert result["isError"] is False
    assert result["structuredContent"] == {"result": ""}


def test_worker_pid_reports_the_serving_process(client):
    """The demo tool names the pid serving the call — here, the test process."""
    response = client.post(
        MCP_URL,
        data=request_body("tools/call", {"name": "worker_pid", "arguments": {}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": os.getpid()}
