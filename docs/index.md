# django-stateless-mcp

An [MCP](https://modelcontextprotocol.io) (Model Context Protocol) server is how AI agents — Claude Code, ChatGPT, and the assistants built on them — connect to your application in a controlled way: they see and call only the tools you choose to expose, under the permissions you enforce.
As your users lean on AI for more of their work, it pays to be ready to accommodate their agents without loosening the protections Django already gives your data and infrastructure — and that is what this package is for.

django-stateless-mcp is a stateless MCP server for Django, built on the [**2026-07-28** spec](https://modelcontextprotocol.io/specification/2026-07-28).
An MCP endpoint becomes an ordinary Django view: no sessions, no SSE, no sticky routing, and no dedicated single-process service.

## Why use this

- **Your MCP server is an ordinary Django view** — same deployment, same
  middleware, same monitoring, and tools call your models and business logic
  directly. No separate MCP service to build, secure, and operate.
- **It scales like the rest of your Django app** — any worker on any instance
  can serve any request, including an elicitation answer.
- **Tools can ask the user questions** — pause mid-call for missing form
  fields or an explicit approval, then resume on whichever worker the answer
  lands on.
- **Kick off a long job, keep chatting, and the result comes back when it's
  ready** — see the [long-running jobs recipe](recipes/long-running-jobs.md).
- **Your authentication and permissions work inside tools** — bearer auth
  resolves to a real Django user, so `user.has_perm(...)` just works.
- **You can see what your MCP is doing** — optional structlog middleware logs
  one queryable event per request.
- **Tools register the Django way** — each app's `mcp.py` is discovered
  automatically, exactly like `admin.py`.

## Start here

**[Why stateless](why-stateless.md)** — read this first. It explains the problem
the 2026-07-28 spec solved, why elicitation used to break on a multi-worker
deployment, and why that change is what makes a good Django MCP package
possible. Most of the API follows from it.

- [Installation](installation.md) — installing the package
- [Usage](usage.md) — using it in a Django project
- [Try it live](example.md) — the runnable example project
- [API reference](reference.md) — generated from the source

## What this package is not

It deliberately does **not** expose your models or ORM to an agent, and does not
convert DRF viewsets into tools. Those are opinionated product surface with a
large security blast radius; this package is the foundation they should be built
on. See [Why stateless](why-stateless.md#design-consequences) for the reasoning.
