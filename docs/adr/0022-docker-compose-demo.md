# ADR-0022: The example project also boots with `docker compose up`

- **Status:** Accepted
- **Date:** 2026-07-31
- **Builds on:** [ADR-0015](0015-runnable-example-project.md) — the runnable example project

## Context

The example project (ADR-0015) is the package's demonstration infrastructure, but every
launch path required a local toolchain: uv, a compatible Python, and just. That is exactly
the audience mismatch for a demo — the person most worth convincing (a newcomer evaluating
whether stateless MCP is real) is the person least likely to have the repository's dev
stack installed. "Clone and `docker compose up`" removes the last local dependency while
booting the same four-worker uvicorn fleet as `just demo-asgi`, since the multi-worker
fleet *is* the demonstration.

Two design questions had real alternatives:

1. **How the image installs dependencies.** A plain `python:3.14-slim` base with
   `pip install -e . uvicorn structlog` is the least Docker ceremony, but it resolves
   dependencies freshly at build time — bypassing `uv.lock` and with it the
   `exclude-newer` supply-chain quarantine the project deliberately carries. Rejected.
   The image instead builds on the uv Python 3.14 image and runs
   `uv sync --frozen --no-default-groups --group test` into `/opt/venv` — the `test`
   group already carries the demo's runtime extras (uvicorn, gunicorn, structlog), so
   no new dependency group was needed.
2. **Where the database lives.** Baking SQLite into the container is the conventional
   shape, but it silently breaks the README's permission walkthrough: the grant/revoke
   cycle is driven by *host-run* `manage.py seed --grant-delete` mutating
   `example/db.sqlite3`, and a container-private database never sees those writes.
   The compose service instead bind-mounts `./example`, so container and host share the
   one SQLite file, and runs as the host uid/gid so container-created files stay
   host-writable.

## Decision

A root `Dockerfile`, `compose.yaml`, and `.dockerignore`; a `just demo-docker` target;
docs updated in the same PR. `docker compose up` runs migrate + seed then
`uvicorn example.asgi:application --workers 4` on port 8000 — the same sequence as
`just demo-asgi`, containerized. The committed port stays 8000 because the repository's
`.mcp.json` (the Claude Code auto-connect, ADR-0015) expects it.

Verified against the running container: 24 concurrent `worker_pid` calls spread across
all four workers; the elicitation round-trip completed across two independent requests;
host-run `seed --grant-delete`/`--revoke-delete` toggled `delete_widget` visibility on
the containerized `/filtered-mcp/`; GET answered `405`.

## Consequences

- Docker is demo surface only — the package itself gains no Docker dependency, and
  nothing in CI builds the image, so image rot is only detected by humans running it.
- The shared bind mount means the container inherits the host's `db.sqlite3` state,
  including the grant/revoke persistence gotcha already documented in the example README.
- `--frozen` ties the image to `uv.lock`; a lockfile update is automatically a demo-image
  update, which is the point.
- Host port 8000 must be free, as with every other launch path; the compose file is
  overridable per the standard cross-project port-conflict practice without editing the
  committed mapping.
