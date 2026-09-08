# How this compares

People arriving from the wider Python AI ecosystem often ask why they should
use this package rather than an agent framework such as
[Pydantic AI](https://pydantic.dev/docs/ai/) or
[LlamaIndex](https://developers.llamaindex.ai/).
The short answer is that those are not alternatives to this package.
They sit at the other end of the wire.
This page explains the distinction, then compares the packages that *are*
alternatives.

## Agent frameworks are the other side of MCP

Every MCP conversation has two sides:

- An **MCP client** is the AI side: Claude Code, ChatGPT, Cursor, or an agent
  you write yourself.
  It holds the model, decides what to do next, and calls tools to do it.
- An **MCP server** is the application side.
  It publishes a set of tools with permissions and waits to be called.

**Pydantic AI and LlamaIndex build the client side.**
Your code holds the LLM API key, pays for the tokens, picks the model, and runs
the loop in which the model chooses which of your Python functions to call.
Pydantic AI describes itself as "a typed, extensible agent loop"; LlamaIndex adds
heavy support for getting your documents in front of the model (indexing,
retrieval, RAG) and for multi-step workflows.
In both, the AI lives inside your process, and you are building it.

**django-stateless-mcp builds the server side.**
Your code never calls an LLM.
There is no API key in `settings.py` and no token bill.
The AI is someone else's: a user's Claude Code, a company's ChatGPT deployment,
or an agent a third party wrote with Pydantic AI.
Your job is to expose a user's data within your app, and the business logic
that reads and updates it, as tools under your own auth and permissions.
The user's AI then decides how to interact with your system: which tools to
call, in what order, and to what end.
That is the reverse of an agent framework, where you decide how the AI
interacts with your system and you foot the bill for every call it makes.
You are not building an AI; you are making your Django app reachable by one.

The Django analogy holds well.
Django REST Framework lets other people's *programs* call your app over HTTP.
django-stateless-mcp lets other people's *AI agents* call your app over MCP.
Pydantic AI and LlamaIndex are what those other people might use to build the
agent, the way they might use `httpx` to build a client for your REST API.
Nobody asks "why DRF instead of httpx?", and this is the same question.

### Why the "MCP support" badge misleads

Both frameworks advertise MCP support, which is where the confusion starts.
That support is on the client side: Pydantic AI's
[`MCPToolset`](https://pydantic.dev/docs/ai/mcp/client/) and LlamaIndex's
[`McpToolSpec`](https://developers.llamaindex.ai/python/framework/module_guides/mcp/llamaindex_mcp/)
connect an agent *to* an MCP server and turn that server's tools into things
the agent can call.
It is the feature that would let a Pydantic AI agent talk to a server built
with this package.
LlamaIndex also offers
[`workflow_as_mcp`](https://developers.llamaindex.ai/python/framework/module_guides/mcp/convert_existing/),
which does publish a server, but it publishes a LlamaIndex workflow running its
own process, not a Django application with your models, users and middleware.

### Two questions that settle it

1. **Is there an LLM API key in my settings?**
   If yes, you are building an agent, and you want Pydantic AI, LlamaIndex, or
   similar.
2. **Do my users bring their own AI and want it to work with my app?**
   If yes, you want an MCP server, and if the app is Django, that is this
   package.

Both can be yes in one project.
A Django app can run a Pydantic AI agent inside a Celery task for an in-app
assistant *and* expose an MCP endpoint so a user's Claude Code can drive the
same business logic.
The two packages never touch each other.

## The actual alternatives: other MCP servers

Once you know you need a server, the real choices are these.

| Option | What it is | Where it falls short for a Django app |
|---|---|---|
| [Official `mcp` SDK](https://github.com/modelcontextprotocol/python-sdk) v2 | The reference implementation of the protocol, which this package builds on. Runs as its own ASGI app. | Deployed as a separate service beside Django, with its own auth and monitoring. Tools do not naturally see `request.user` or the ORM. |
| [FastMCP 4](https://gofastmcp.com/) | A batteries-included layer over the SDK: OAuth providers, extensions, and support for both old and new protocol clients. ASGI only. | The same separate-service cost. No WSGI, no Django integration, and it deliberately keeps the old stateful features alive for pre-2026 clients. |
| [django-mcp-server](https://github.com/gts360/django-mcp-server) | The existing Django package. Exposes models and DRF viewsets as tools. | Built on the pre-[2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28) protocol: stateful by default via Django sessions, pinned to the 1.x SDK, and coupled to SDK internals that moved in 2.0. |
| django-stateless-mcp | An MCP endpoint as an ordinary Django view on the 2026-07-28 spec, under WSGI or ASGI. | Deliberately does not expose models or DRF. It is the foundation such packages should be built on, not the product. See [why stateless](why-stateless.md#design-consequences). |

## When not to use this package

- You have no Django application to expose.
- You want to *build* an AI assistant rather than let one in.
  Reach for an agent framework, and come back here when you want that
  assistant, or anyone else's, to call your Django app.
