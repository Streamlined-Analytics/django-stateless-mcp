"""The example's MCP App, driven through ``mcp_view`` the way a host would.

MCP Apps is additive: the SDK stamps the tool metadata and serves the
``ui://`` resource, and the view passes both through untouched. These tests
pin the server-side half of the contract -- discovery, the rendered
template, the text fallback, and the permission gate on the app-only tool.
Rendering the iframe is the host's job and is not exercised here.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from tests.test_views import MCP_HEADERS, MCP_URL, USER_URL, request_body, stateless_meta

APPS_CAPABILITIES: dict[str, Any] = {
    "extensions": {"io.modelcontextprotocol/ui": {"mimeTypes": ["text/html;profile=mcp-app"]}}
}
NO_APPS_CAPABILITIES: dict[str, Any] = {"elicitation": {}}
SHELF_URI = "ui://example/book-shelf.html"


def post_modern(
    client: Client,
    method: str,
    params: dict[str, Any],
    *,
    capabilities: dict[str, Any],
    url: str = MCP_URL,
    headers: dict[str, str] | None = None,
) -> Any:
    """POST a 2026-07-28 request whose routing header names the tool or resource."""
    routed = params.get("name") or params.get("uri")
    request_headers = {**MCP_HEADERS, "mcp-protocol-version": "2026-07-28", "mcp-method": method, **(headers or {})}
    if routed is not None:
        request_headers["mcp-name"] = routed
    response = client.post(
        url,
        data=request_body(method, {**params, "_meta": stateless_meta(capabilities)}),
        content_type="application/json",
        headers=request_headers,
    )
    return json.loads(response.content)


def test_server_advertises_the_apps_extension(client):
    """``server/discover`` names the extension, so a host knows to look for ``ui://`` resources."""
    result = post_modern(client, "server/discover", {}, capabilities=APPS_CAPABILITIES)["result"]

    assert "io.modelcontextprotocol/ui" in result["capabilities"]["extensions"]


def test_tools_carry_the_ui_binding(client):
    """Both shelf tools point at the resource; only the retire tool is app-only."""
    tools = post_modern(client, "tools/list", {}, capabilities=APPS_CAPABILITIES)["result"]["tools"]
    by_name = {tool["name"]: tool for tool in tools}

    assert by_name["browse_books"]["_meta"]["ui"] == {"resourceUri": SHELF_URI}
    assert by_name["retire_book"]["_meta"]["ui"] == {"resourceUri": SHELF_URI, "visibility": ["app"]}


def test_shelf_is_listed_as_an_app_resource(client):
    """The ``ui://`` resource is discoverable under the app MIME type."""
    resources = post_modern(client, "resources/list", {}, capabilities=APPS_CAPABILITIES)["result"]["resources"]

    assert [(r["uri"], r["mimeType"]) for r in resources] == [(SHELF_URI, "text/html;profile=mcp-app")]


def test_shelf_html_is_rendered_from_the_django_template(client):
    """``resources/read`` returns the template, rendered with the tool names it calls."""
    contents = post_modern(client, "resources/read", {"uri": SHELF_URI}, capabilities=APPS_CAPABILITIES)["result"][
        "contents"
    ]

    (document,) = contents
    assert document["mimeType"] == "text/html;profile=mcp-app"
    assert document["text"].startswith("<!doctype html>")
    assert '"retire_book"' in document["text"]
    assert '"browse_books"' in document["text"]
    assert "ui/initialize" in document["text"]


@pytest.mark.django_db(transaction=True)
def test_browse_books_returns_the_shelf_for_an_apps_client(client):
    """A client that negotiated Apps gets the structured shelf, marked as rendered by the app."""
    from example.models import Author, Book

    author = Author.objects.create(name="Sally Author")
    book = Book.objects.create(title="Stateless by Design", author=author)

    result = post_modern(
        client, "tools/call", {"name": "browse_books", "arguments": {}}, capabilities=APPS_CAPABILITIES
    )["result"]

    assert result["structuredContent"] == {
        "books": [{"id": book.pk, "title": "Stateless by Design", "author": "Sally Author"}],
        "rendered_as": "app",
        "summary": "Stateless by Design (Sally Author)",
    }


@pytest.mark.django_db(transaction=True)
def test_browse_books_degrades_to_text_without_apps(client):
    """A client without Apps gets the same data plus a summary it can show as text."""
    result = post_modern(
        client, "tools/call", {"name": "browse_books", "arguments": {}}, capabilities=NO_APPS_CAPABILITIES
    )["result"]

    assert result["structuredContent"]["rendered_as"] == "text"
    assert result["structuredContent"]["summary"] == "no books"


@pytest.mark.django_db(transaction=True)
def test_retire_book_refuses_a_user_without_the_permission(client):
    """The app-only tool gates on Django's permission: visibility is not the boundary."""
    from django.contrib.auth.models import User

    from example.models import Author, Book

    User.objects.create_user("mcp-test-user")
    book = Book.objects.create(title="Keep Me", author=Author.objects.create(name="Sally Author"))

    result = post_modern(
        client,
        "tools/call",
        {"name": "retire_book", "arguments": {"book_id": book.pk}},
        capabilities=APPS_CAPABILITIES,
        url=USER_URL,
        headers={"authorization": "Bearer good-token"},
    )["result"]

    assert result["isError"] is True
    assert "You may not retire books." in result["content"][0]["text"]
    assert Book.objects.filter(pk=book.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_retire_book_deletes_for_a_permitted_user(client):
    """With the permission, the retire button's tool deletes the row."""
    from django.contrib.auth.models import Permission, User

    from example.models import Author, Book

    user = User.objects.create_user("mcp-test-user")
    user.user_permissions.add(Permission.objects.get(codename="delete_book"))
    book = Book.objects.create(title="Retire Me", author=Author.objects.create(name="Sally Author"))

    result = post_modern(
        client,
        "tools/call",
        {"name": "retire_book", "arguments": {"book_id": book.pk}},
        capabilities=APPS_CAPABILITIES,
        url=USER_URL,
        headers={"authorization": "Bearer good-token"},
    )["result"]

    assert result["structuredContent"] == {"result": f"book {book.pk} retired"}
    assert not Book.objects.filter(pk=book.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_retire_book_reports_an_unknown_id(client):
    """Retiring a book that does not exist is an error, not a silent no-op."""
    from django.contrib.auth.models import Permission, User

    user = User.objects.create_user("mcp-test-user")
    user.user_permissions.add(Permission.objects.get(codename="delete_book"))

    result = post_modern(
        client,
        "tools/call",
        {"name": "retire_book", "arguments": {"book_id": 999}},
        capabilities=APPS_CAPABILITIES,
        url=USER_URL,
        headers={"authorization": "Bearer good-token"},
    )["result"]

    assert result["isError"] is True
    assert "no book with id 999" in result["content"][0]["text"]


@pytest.mark.anyio
async def test_shelf_html_is_served_under_asgi(async_client):
    """The template render runs off the event loop, so the ASGI path serves it too."""
    response = await async_client.post(
        MCP_URL,
        data=request_body("resources/read", {"uri": SHELF_URI, "_meta": stateless_meta(APPS_CAPABILITIES)}),
        content_type="application/json",
        headers={
            **MCP_HEADERS,
            "mcp-protocol-version": "2026-07-28",
            "mcp-method": "resources/read",
            "mcp-name": SHELF_URI,
        },
    )

    (document,) = json.loads(response.content)["result"]["contents"]
    assert document["mimeType"] == "text/html;profile=mcp-app"
    assert "ui/initialize" in document["text"]
