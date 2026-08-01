"""The example project's MCP servers, shared with the package's test suite."""

from __future__ import annotations

import os
import threading
import time

from asgiref.sync import sync_to_async
from django.contrib.auth.models import (
    AbstractBaseUser,
    AnonymousUser,
    PermissionsMixin,
    User,
)
from django.db import connection
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.subscriptions import InMemorySubscriptionBus, PromptsListChanged, ToolsListChanged

from django_stateless_mcp import (
    PermittedToolsFilter,
    StructlogRequestLogger,
    django_request,
    request_state_security,
)
from example.models import Author, Book

# Read at call time inside slow_book_report, so tests monkeypatch it to zero.
SLOW_BOOK_REPORT_SECONDS = 30.0


def _update_author_visible(user: AbstractBaseUser | AnonymousUser, tool_name: str) -> bool:
    """update_author is visible only to users holding the custom permission."""
    if tool_name != "update_author":
        return True
    # AbstractBaseUser alone has no has_perm; anyone outside the mixin lacks the perm.
    return isinstance(user, PermissionsMixin) and user.has_perm("example.can_update_authors")


# In-process bus: one instance only; a real fleet supplies an external bus. See ADR-0020.
subscription_bus = InMemorySubscriptionBus()

server = MCPServer(
    name="test-server",
    version="0.0.1",
    request_state_security=request_state_security(),
    middleware=[StructlogRequestLogger()],
    subscriptions=subscription_bus,
)

# A server that filters tool visibility by permission.
server_filtered = MCPServer(
    name="test-server",
    version="0.0.1",
    request_state_security=request_state_security(),
    middleware=[PermittedToolsFilter(_update_author_visible)],
)


@server_filtered.tool()
def public_ping() -> str:
    """A tool everyone may see."""
    return "pong"


@server_filtered.tool(name="update_author")
def filtered_update_author(ctx: Context, author_id: int, name: str) -> str:
    """Hidden from users lacking the perm; also gates its own execution."""
    if not django_request(ctx).user.has_perm("example.can_update_authors"):
        raise PermissionError("You may not update authors.")
    return _rename_author(author_id, name)


# A second, independent instance modelling another worker in a fleet. Same
# name deliberately: request-state audience binding is by server name, which
# identical replicas share.
server_b = MCPServer(
    name="test-server",
    version="0.0.1",
    request_state_security=request_state_security(),
)


def _rename_author(author_id: int, name: str) -> str:
    """Rename the author, or raise ValueError if the id names no row."""
    updated = Author.objects.filter(pk=author_id).update(name=name)
    if not updated:
        raise ValueError(f"no author with id {author_id}")
    return f"author {author_id} renamed to {name}"


@server.tool()
def list_books(ctx: Context) -> list[str]:
    """List every book in the library as "Title (Author)" strings."""
    django_request(ctx)
    return [f"{book.title} ({book.author.name})" for book in Book.objects.select_related("author")]


@server.tool()
def slow_book_report(ctx: Context) -> list[str]:
    """Return the book list after a deliberately long blocking pause.

    Sleeps ``SLOW_BOOK_REPORT_SECONDS`` (30 s) in its worker thread — the
    event loop and every other tool keep serving meanwhile, which you can
    see by calling ``worker_pid`` while this runs. Raise Inspector's request
    timeout before calling. Real applications should not block like this:
    see the long-running-jobs recipe in the package docs for the
    start-job-and-notify pattern.
    """
    django_request(ctx)
    time.sleep(SLOW_BOOK_REPORT_SECONDS)
    return [f"{book.title} ({book.author.name})" for book in Book.objects.select_related("author")]


@server.tool()
def worker_pid() -> int:
    """Return the OS process id of the worker serving this call.

    Under `just demo-asgi` (several worker processes) this makes the
    package's thesis visible: an elicitation issued by one pid resumes
    on another, because no worker holds any per-flow state.
    """
    return os.getpid()


@server.tool()
async def test_trigger_tool_change() -> str:
    """Publish a tools-list-changed event onto open subscription streams."""
    await subscription_bus.publish(ToolsListChanged())
    return "tools list change published"


@server.tool()
async def test_trigger_prompt_change() -> str:
    """Publish a prompts-list-changed event onto open subscription streams."""
    await subscription_bus.publish(PromptsListChanged())
    return "prompts list change published"


@server.tool()
def request_path(ctx: Context) -> str:
    """Echo the path of the Django request serving this call."""
    return django_request(ctx).path


@server.tool()
def request_scheme(ctx: Context) -> str:
    """Echo the scheme of the Django request serving this call.

    ``request.scheme`` honours ``SECURE_PROXY_SSL_HEADER`` and is verbatim
    what the bridge forwards as the ASGI scope's ``scheme``, so this makes
    the behind-a-proxy deployment shape assertable.
    """
    # The stubs allow None for a request built without a handler; never on this path.
    return django_request(ctx).scheme or "unknown"


@server.tool()
def db_thread_info(ctx: Context) -> str:
    """Show the worker thread serving this tool and its DB connection state.

    With connection hygiene working, ``connection_open`` reads ``False``
    even on a thread that served an ORM tool moments ago -- the bridge
    recycled it after that request (ADR-0021). Watch it live in Inspector:
    call ``count_books`` then this.
    """
    django_request(ctx)
    thread_name = threading.current_thread().name
    return f"thread={thread_name} connection_open={connection.connection is not None}"


@server.tool()
def count_books(ctx: Context) -> int:
    """Count books via the ORM, exercising sync DB access in a tool."""
    # Raises LookupError off the view path; asserts the context wiring works.
    django_request(ctx)
    return Book.objects.count()


class StubVerifier:
    """A TokenVerifier accepting one hard-coded token, for auth tests."""

    async def verify_token(self, token: str) -> AccessToken | None:
        """Accept ``good-token`` with read scope; reject everything else."""
        if token != "good-token":
            return None
        return AccessToken(token=token, client_id="test-client", scopes=["mcp:read"])


async def resolve_stub_user(token: str) -> User | None:
    """Resolve the bearer token to a Django user.

    Models a real user_resolver: one async lookup returning the Django user
    the token was issued for. ORM access is wrapped, as it must be on the
    event loop.
    """
    return await sync_to_async(User.objects.filter(username="mcp-test-user").first)()


@server.tool()
def token_client() -> str:
    """Name the OAuth client the SDK sees for this call."""
    access_token = get_access_token()
    return access_token.client_id if access_token else "anonymous"


@server.tool()
def current_username(ctx: Context) -> str:
    """Name the authenticated Django user reached via the request."""
    return django_request(ctx).user.get_username()


@server.tool()
def update_author(ctx: Context, author_id: int, name: str) -> str:
    """A permission-locked tool: renames an author, refusing users without the perm."""
    user = django_request(ctx).user
    if not user.has_perm("example.can_update_authors"):
        raise PermissionError("You may not update authors.")
    return _rename_author(author_id, name)


async def resolve_no_user(token: str) -> None:
    """A resolver that never finds a user, modelling a client-credentials token."""
    return None


class DatabaseTokenVerifier:
    """A TokenVerifier that checks every token against the database.

    Mirrors the shape real consumers run (django-oauth-toolkit): one ORM
    lookup per request, no in-memory token state, so any worker can verify
    any request. The token doubles as the username, keeping the example
    free of extra models.
    """

    __slots__ = ()

    async def verify_token(self, token: str) -> AccessToken | None:
        """Accept a token naming an active user; reject everything else."""
        user = await sync_to_async(User.objects.filter(username=token, is_active=True).first)()
        if user is None:
            return None
        return AccessToken(token=token, client_id=user.get_username(), scopes=["mcp:read"])


async def resolve_db_user(token: str) -> User | None:
    """Resolve the token to its database user, the way a DOT resolver would."""
    return await sync_to_async(User.objects.filter(username=token, is_active=True).first)()
