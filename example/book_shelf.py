"""The example's MCP App: a book shelf rendered inside the chat.

MCP Apps (the ``io.modelcontextprotocol/ui`` extension) let a tool carry a
reference to an HTML resource that the client renders in a sandboxed iframe.
The SDK owns the protocol -- ``mcp.server.apps.Apps`` stamps the tool
metadata and serves the ``ui://`` resource -- and this module adds the
Django-shaped parts: the HTML comes from a Django template, and the app's
"retire" button reaches a tool that gates on a Django permission.

Everything here is ordinary request/response: the app runs in the client, the
server serves one static document and answers tool calls, and no worker holds
anything between requests. See the MCP Apps recipe in the package docs.
"""

from __future__ import annotations

from typing import Any

from asgiref.sync import sync_to_async
from django.template.loader import render_to_string
from mcp.server.apps import Apps, client_supports_apps
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.resources import Resource
from mcp.types import ToolAnnotations

from django_stateless_mcp import django_request
from example.models import Book

BOOK_SHELF_URI = "ui://example/book-shelf.html"


class DjangoTemplateResource(Resource):
    """A ``ui://`` resource whose HTML is a Django template, rendered on each read.

    Rendering per read keeps the template editable without a restart in
    development and costs one template render per ``resources/read``, which
    hosts cache. The context is fixed at registration time: the document is
    the app's shell, and the data it shows arrives from tool results.
    """

    template_name: str
    context: dict[str, Any] = {}

    async def read(self) -> str:
        """Render the template in a worker thread, off the event loop."""
        return await sync_to_async(render_to_string)(self.template_name, self.context)


book_shelf = Apps()

book_shelf.add_resource(
    DjangoTemplateResource(
        uri=BOOK_SHELF_URI,
        name="book-shelf",
        title="Book shelf",
        description="The library as a shelf, with a retire button per book.",
        template_name="example/book_shelf.html",
        context={"retire_tool": "retire_book", "browse_tool": "browse_books"},
    )
)


def _shelf() -> list[dict[str, Any]]:
    """The library as the rows the shelf renders."""
    return [
        {"id": book.pk, "title": book.title, "author": book.author.name}
        for book in Book.objects.select_related("author").order_by("title")
    ]


@book_shelf.tool(
    resource_uri=BOOK_SHELF_URI,
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def browse_books(ctx: Context) -> dict[str, Any]:
    """Show the library as an interactive shelf, or as a plain list where apps are unsupported.

    The structured result is what the app renders; the summary is what a
    client without MCP Apps shows instead, so the tool degrades to text
    rather than to nothing.
    """
    django_request(ctx)
    books = _shelf()
    summary = ", ".join(f"{book['title']} ({book['author']})" for book in books) or "no books"
    return {"books": books, "rendered_as": "app" if client_supports_apps(ctx) else "text", "summary": summary}


@book_shelf.tool(
    resource_uri=BOOK_SHELF_URI,
    visibility=["app"],
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True, open_world_hint=False),
)
def retire_book(ctx: Context, book_id: int) -> str:
    """Delete a book; reachable only from the shelf's retire button, and only with the permission.

    ``visibility=["app"]`` hides the tool from the model and lets the app call
    it -- the confirmation is the human clicking the button. Hosts enforce
    that visibility, the server cannot, so the permission check here is the
    boundary that holds if a client ignores it.
    """
    if not django_request(ctx).user.has_perm("example.delete_book"):
        raise PermissionError("You may not retire books.")
    deleted, _ = Book.objects.filter(pk=book_id).delete()
    if not deleted:
        raise ValueError(f"no book with id {book_id}")
    return f"book {book_id} retired"
