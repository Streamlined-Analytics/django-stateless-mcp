# Usage

!!! warning "Not yet available"

    The public API is not published. This page documents *intent* so the design
    can be reviewed before it is built; it is not yet a working example, and the
    names below will change.

The package is designed around one idea: an MCP endpoint is a Django view, so it
mounts in `urls.py` like anything else and runs on your existing web fleet under
either WSGI or ASGI.

Two things follow from that, and they are the reason to read
[Why stateless](why-stateless.md) first:

- **A tool that needs input from the user returns a result saying so**, rather
  than holding a connection open and blocking. The client re-issues the call
  with the answers, and any worker can serve that retry.
- **Nothing is remembered between requests.** State travels in the request or
  lives in the database.

When the API lands, this page will carry a worked elicitation example that runs
across two separate requests against two different workers — the case the old
protocol could not express, and the one this package exists to make ordinary.

Until then, [Why stateless](why-stateless.md) is the useful page, and the
[decision records](adr/index.md) cover the choices made so far.
