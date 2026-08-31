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
    assert not user.has_perm("example.can_update_authors")


@pytest.mark.django_db
def test_seed_creates_the_demo_superuser():
    """Seeding creates the admin account the permission walkthrough logs into."""
    from django.contrib.auth.models import User

    call_command("seed")

    superuser = User.objects.get(username="admin")
    assert superuser.is_staff
    assert superuser.is_superuser
    assert superuser.check_password("admin")


@pytest.mark.django_db
def test_seed_creates_the_library():
    """Seeding creates the books the book tools read."""
    from example.models import Author, Book

    call_command("seed")

    assert Author.objects.exists()
    assert Book.objects.select_related("author").exists()


@pytest.mark.django_db
def test_seed_toggles_update_authors_permission():
    """--grant-update-authors and --revoke-update-authors flip the locked tool's permission."""
    from django.contrib.auth.models import User

    call_command("seed", "--grant-update-authors")
    assert User.objects.get(username="mcp-test-user").has_perm("example.can_update_authors")

    call_command("seed", "--revoke-update-authors")
    assert not User.objects.get(username="mcp-test-user").has_perm("example.can_update_authors")


@pytest.mark.django_db
def test_seed_is_idempotent():
    """Reseeding never duplicates users, authors, or books."""
    from django.contrib.auth.models import User

    from example.models import Author, Book

    call_command("seed")
    users, authors, books = User.objects.count(), Author.objects.count(), Book.objects.count()
    call_command("seed")

    assert User.objects.filter(username="mcp-test-user").count() == 1
    assert (User.objects.count(), Author.objects.count(), Book.objects.count()) == (users, authors, books)


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


@pytest.mark.django_db(transaction=True)
def test_db_thread_info_reports_a_recycled_connection(client):
    """The demo's hygiene tool shows the worker thread holding no connection.

    Its whole point is making ADR-0021's claim visible in Inspector: the
    bridge closes the thread's connection after each request, so even a
    thread that just served an ORM tool reports ``connection_open=False``.
    """
    from example.models import Author, Book

    Book.objects.create(title="Two Scoops", author=Author.objects.create(name="Audrey"))
    client.post(
        MCP_URL,
        data=request_body("tools/call", {"name": "count_books", "arguments": {}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    response = client.post(
        MCP_URL,
        data=request_body("tools/call", {"name": "db_thread_info", "arguments": {}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    reported = json.loads(response.content)["result"]["structuredContent"]["result"]
    assert reported.endswith("connection_open=False")


def test_trigger_prompt_change_publishes_onto_the_bus(client):
    """The demo tool publishing prompt-list changes runs without a listener."""
    response = client.post(
        MCP_URL,
        data=request_body("tools/call", {"name": "test_trigger_prompt_change", "arguments": {}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": "prompts list change published"}


def test_models_name_themselves_for_the_admin():
    """Author and Book render as their name and title in the demo admin."""
    from example.models import Author, Book

    author = Author(name="Audrey Roy Greenfeld")

    assert str(author) == "Audrey Roy Greenfeld"
    assert str(Book(title="Two Scoops of Django", author=author)) == "Two Scoops of Django"
