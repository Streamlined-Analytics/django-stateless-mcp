# django-stateless-mcp

A stateless Model Context Protocol server for Django, built on the **2026-07-28**
spec. An MCP endpoint becomes an ordinary Django view: no sessions, no SSE, no
sticky routing, and no dedicated single-process service.

!!! warning "Pre-release"

    The package is scaffolded but the API is not published yet. The design and
    its rationale are documented; the implementation is in progress.

## Start here

**[Why stateless](why-stateless.md)** — read this first. It explains the problem
the 2026-07-28 spec solved, why elicitation used to break on a multi-worker
deployment, and why that change is what makes a good Django MCP package
possible. Most of the API follows from it.

- [Installation](installation.md) — installing the package
- [Usage](usage.md) — using it in a Django project
- [API reference](reference.md) — generated from the source
- [Decisions](adr/index.md) — the reasoning behind the project's choices

## What this package is not

It deliberately does **not** expose your models or ORM to an agent, and does not
convert DRF viewsets into tools. Those are opinionated product surface with a
large security blast radius; this package is the foundation they should be built
on. See [Why stateless](why-stateless.md#design-consequences) for the reasoning.
