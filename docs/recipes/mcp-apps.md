# Recipe: MCP Apps — a UI inside the chat

MCP Apps let a tool carry a small HTML page that the client renders inside the conversation, in a sandboxed iframe.
The page can show the tool's result, take clicks, and call tools on your server through the host.

It matters for one reason above the others: it is the in-conversation UI the consumer products chose.
Claude.ai, Claude Desktop and ChatGPT render MCP Apps and do not support [elicitation](elicitation-forms-and-confirmations.md), so on those clients an app is the only way to put a button in front of a human mid-flow.
It is not a replacement for elicitation, and the [limitations](#limitations) below say exactly where the two differ.

Nothing in this recipe needs anything from this package beyond `mcp_view`.
The `mcp` SDK ships the extension as `mcp.server.apps.Apps`, and the view passes its tools and resources through like any others.
Every request is ordinary request/response: the app runs in the client, the server serves one static document and answers tool calls, and no worker holds anything in between.

## Which clients support it

Support is by *host*, and it is close to the mirror image of elicitation: the consumer products have it, the coding agents mostly do not.

| Client | MCP Apps | Source |
| --- | --- | --- |
| Claude.ai (web) | ✅ | [Extension support matrix](https://modelcontextprotocol.io/extensions/client-matrix) |
| Claude Desktop | ✅ | Extension support matrix |
| ChatGPT | ✅ | Extension support matrix; [OpenAI's Apps SDK](https://developers.openai.com/apps-sdk/mcp-apps-in-chatgpt) is built on it |
| GitHub Copilot (VS Code) | ✅ | Extension support matrix |
| Cursor | ✅ | Extension support matrix |
| Goose, Postman, MCPJam | ✅ | Extension support matrix |
| Claude Code (CLI) | ❌ | Terminal client; listed as not rendering apps by [MCPJam's client directory](https://www.mcpjam.com/clients) |
| Codex CLI | ❌ | Same |
| Gemini CLI | ❌ | Advertises no extensions |

These are the vendors' and the community matrix's claims as of 4 September 2026, not runs against this package's example.
The server side below is exercised by the test suite through the view; rendering in a real host is not.
MCPJam's inspector renders apps and is the quickest way to try yours.

## What the server provides

Three things, all declared once at startup:

1. An `Apps()` extension instance, passed to `MCPServer(extensions=[...])`.
2. A `ui://` resource served as `text/html;profile=mcp-app` — the document the host renders.
3. Tools bound to that resource with `@apps.tool(resource_uri=...)`, which stamps `_meta.ui.resourceUri` on the tool so the host knows to fetch the document.

The host reads the resource with `resources/read`, renders it in an iframe, and pushes the tool's result into it.
When the user clicks something, the iframe sends `tools/call` to the host, which forwards it to your server on the same connection, with the same token.

## The resource: a Django template

The document is a template, rendered on each `resources/read`.
The context is fixed at registration — the document is the app's *shell*, and the data it shows arrives from tool results.

```python
# library/mcp_apps.py
from typing import Any

from asgiref.sync import sync_to_async
from django.template.loader import render_to_string
from mcp.server.apps import Apps
from mcp.server.mcpserver.resources import Resource

BOOK_SHELF_URI = "ui://library/book-shelf.html"


class DjangoTemplateResource(Resource):
    """A ui:// resource whose HTML is a Django template, rendered on each read."""

    template_name: str
    context: dict[str, Any] = {}

    async def read(self) -> str:
        return await sync_to_async(render_to_string)(self.template_name, self.context)


book_shelf = Apps()
book_shelf.add_resource(
    DjangoTemplateResource(
        uri=BOOK_SHELF_URI,
        name="book-shelf",
        template_name="library/book_shelf.html",
        context={"retire_tool": "retire_book", "browse_tool": "browse_books"},
    )
)
```

`Apps.add_resource` fills in the MIME type and refuses any other, so a plain `Resource` subclass is all that is needed.
Rendering runs in a worker thread, so the ASGI path never blocks the event loop.
If your document is static, `book_shelf.add_html_resource(uri, html)` skips the template entirely.

## The tool: return data the app can render

```python
from mcp.server.apps import client_supports_apps
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from django_stateless_mcp import django_request
from library.models import Book


@book_shelf.tool(
    resource_uri=BOOK_SHELF_URI,
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def browse_books(ctx: Context) -> dict[str, Any]:
    """Show the library as a shelf, or as a plain list where apps are unsupported."""
    django_request(ctx)
    books = [
        {"id": b.pk, "title": b.title, "author": b.author.name}
        for b in Book.objects.select_related("author").order_by("title")
    ]
    summary = ", ".join(f"{b['title']} ({b['author']})" for b in books) or "no books"
    return {
        "books": books,
        "rendered_as": "app" if client_supports_apps(ctx) else "text",
        "summary": summary,
    }
```

Return structured data: the host hands the whole `CallToolResult` to the app, and `structuredContent` is what the page reads.
Return a human-readable summary too — a client that did not negotiate apps shows the result as text, and `client_supports_apps(ctx)` tells you which case you are in from the request's own capability envelope.
Then register the extension on the server the view mounts:

```python
server = MCPServer(name="library", extensions=[book_shelf])
```

## The template

The page speaks JSON-RPC to the host over `postMessage`.
Without the JavaScript SDK that is a handshake, one notification to listen for, and one request to send, so the whole app fits in a template.
The example project's `example/templates/example/book_shelf.html` is the complete version; the parts that matter are:

```html
<ul id="shelf"></ul>
<script>
(function () {
  const RETIRE_TOOL = "{{ retire_tool|escapejs }}";
  const pending = new Map();
  let nextId = 1;

  function request(method, params) {
    const id = nextId++;
    return new Promise(function (resolve, reject) {
      pending.set(id, { resolve: resolve, reject: reject });
      window.parent.postMessage({ jsonrpc: "2.0", id: id, method: method, params: params }, "*");
    });
  }

  window.addEventListener("message", function (event) {
    const message = event.data;
    if (message.id !== undefined && pending.has(message.id)) {
      const waiter = pending.get(message.id);
      pending.delete(message.id);
      message.error ? waiter.reject(new Error(message.error.message)) : waiter.resolve(message.result);
    } else if (message.method === "ui/notifications/tool-result") {
      renderShelf(message.params.structuredContent.books);
    }
  });

  function retireBook(bookId) {
    return request("tools/call", { name: RETIRE_TOOL, arguments: { book_id: bookId } });
  }

  request("ui/initialize", {
    appInfo: { name: "book-shelf", version: "0.0.1" },
    appCapabilities: {},
    protocolVersion: "2026-01-26",
  }).then(function () {
    window.parent.postMessage({ jsonrpc: "2.0", method: "ui/notifications/initialized", params: {} }, "*");
  });
})();
</script>
```

The template tags do what they always do: `escapejs` puts the tool name into the script safely, and nothing else on the page is dynamic.
For anything larger, the [`@modelcontextprotocol/ext-apps`](https://github.com/modelcontextprotocol/ext-apps) package wraps this protocol in an `App` class with React, Vue and Svelte starters; the postMessage dialect is the same.

## A confirmation you can reach from Claude.ai

The retire button calls a second tool, and that tool is where the human-in-the-loop lives:

```python
@book_shelf.tool(
    resource_uri=BOOK_SHELF_URI,
    visibility=["app"],
    annotations=ToolAnnotations(
        destructive_hint=True,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
def retire_book(ctx: Context, book_id: int) -> str:
    """Delete a book; reachable only from the shelf's button, and only with the permission."""
    if not django_request(ctx).user.has_perm("library.delete_book"):
        raise PermissionError("You may not retire books.")
    deleted, _ = Book.objects.filter(pk=book_id).delete()
    if not deleted:
        raise ValueError(f"no book with id {book_id}")
    return f"book {book_id} retired"
```

`visibility=["app"]` asks the host to keep the tool off the model's list and to accept calls to it only from the app.
The model can therefore browse but not retire; retiring takes a person clicking a button.
That is the same outcome the [elicitation recipe](elicitation-forms-and-confirmations.md#confirming-a-destructive-action) reaches with a form, on the clients that have no forms.

The permission check stays in the tool, exactly as it would without an app.
Visibility is enforced by the host, and the server cannot tell an app's call from any other, so a client that ignores the metadata could call `retire_book` by name.
The `has_perm` line is the boundary that holds when that happens.

## Limitations

Read these before designing a flow around an app; several are the reasons elicitation still exists.

- **An app cannot pause a tool call.**
  Elicitation returns `input_required` and the tool finishes later, with the answer.
  An app renders *after* the tool has returned.
  A confirmation is therefore a second tool the user triggers, never a gate inside the first, and the model's original call has already completed by the time anyone sees a button.
- **Visibility is a host promise, not a server guarantee.**
  `visibility=["app"]` hides a tool from the model only on hosts that honour it, and nothing on the wire distinguishes an app's `tools/call` from the model's.
  Authorise inside the tool.
  `PermittedToolsFilter` still applies, and hides app-only tools from users who lack the permission the same way it hides any other.
- **The page runs on the host's origin, not yours.**
  It has none of your cookies, sessions or CSRF tokens, and `{% static %}` URLs will not load unless you declare your host in the resource's `csp.resourceDomains`; the host builds the iframe's Content-Security-Policy from that declaration and blocks everything else.
  Inline the CSS and script, and reach your data only through tools.
- **The server cannot push to the app.**
  There is no server-to-iframe channel; the [subscription stream](long-running-jobs.md) reaches the host, not the page.
  An app that needs fresh data calls a tool for it.
- **Clients without apps see text.**
  Claude Code, Codex and Gemini CLI render none of this, and get the summary string instead.
  Keep every app-bound tool useful as text, and keep destructive actions app-only so a text client simply cannot reach them.
- **The spec is young and negotiated per request.**
  MCP Apps is a draft extension, and the extension mechanism it rides on (SEP-2133) arrived with the 2026-07-28 revision.
  The SDK keeps it in core, so wire drift is absorbed there, but expect the shapes above to move.
- **Not yet verified against the consumer clients.**
  Claude.ai negotiates the 2025-11-25 handshake today; the SDK answers it, and the tests here drive the modern path through the view.
  Neither this package nor its example has been run inside Claude.ai or ChatGPT, so treat the table above as the vendors' word until that run exists.

## Seeing it live

The example project registers the shelf on its open endpoint: `browse_books` is the app-bound tool and `retire_book` the app-only one, gated on Django's built-in `example.delete_book` permission.
Under `just demo`, `resources/read` on `ui://example/book-shelf.html` returns the rendered template, and `tools/list` shows the `_meta.ui` bindings, from any client.
To see the shelf render, connect a host that supports apps, such as MCPJam's inspector, and call `browse_books`.
