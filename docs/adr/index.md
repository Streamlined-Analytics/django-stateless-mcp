# Decision records

Architecture Decision Records capture *why* the project is the way it is: the
problem, what was tried, what failed, and what was chosen. They are written when
the decision is made and are not rewritten afterwards — a superseded decision
gets a new record rather than an edit.

They live here in the repository, for contributors; the Read the Docs site
carries only the user-facing documentation (ADR-0023 — they were published there
until then).

| ADR | Decision |
|---|---|
| [ADR-0001](0001-mypy-strict-over-ty.md) | mypy strict is the type-checking gate, not ty |
| [ADR-0002](0002-docs-on-read-the-docs.md) | Docs are hosted on Read the Docs, with hand-written guides |
| [ADR-0003](0003-real-dependencies-drop-scaffold.md) | Django 5.2 LTS floor; scaffold CLI deleted; `mcp` deferred |
| [ADR-0004](0004-pre-commit.md) | pre-commit added, with mypy as a local hook |
| [ADR-0005](0005-temporary-exclude-newer-exemption.md) | Depend on mcp 2.0.0 via a time-boxed exclude-newer exemption |
| [ADR-0006](0006-test-matrix.md) | Test across Django 5.2 and 6.0; SDK-main env is advisory |
| [ADR-0007](0007-stateless-view-bridge.md) | `mcp_view(server)` bridges Django to the SDK, one session manager per request |
| [ADR-0008](0008-conformance-suite.md) | The official MCP conformance suite runs in CI against a bootable fixture |
| [ADR-0009](0009-mcp-autodiscovery.md) | Installed apps contribute tools via autodiscovered `mcp.py` modules |
| [ADR-0010](0010-request-context.md) | The Django request rides the transport scope; sync tools thread via the SDK |
| [ADR-0011](0011-bearer-auth.md) | Bearer auth enforced in the view via the SDK's TokenVerifier protocol |
| [ADR-0012](0012-request-state-security.md) | Request-state security keyed from SECRET_KEY; flagship elicitation tests |
| [ADR-0013](0013-observability-middleware.md) | Flow logging via the SDK's middleware seam, structlog optional |
| [ADR-0014](0014-user-and-tool-permissions.md) | Resolve the Django user in tools; filter tools/list by permission |
| [ADR-0015](0015-runnable-example-project.md) | One runnable example project, shared with the test suite |
| [ADR-0016](0016-lazy-optional-structlog-import.md) | Lazy import for the optional structlog dependency |
| [ADR-0017](0017-post-only-view.md) | The view serves POST only; receive follows the ASGI contract |
| [ADR-0018](0018-example-auth-middleware.md) | The example carries the standard middleware; the view is CSRF-exempt |
| [ADR-0019](0019-multiworker-harness.md) | Out-of-process multi-worker test harness |
| [ADR-0020](0020-subscription-streams.md) | Subscription streams — ASGI serves them, WSGI refuses them |
| [ADR-0021](0021-worker-thread-connection-hygiene.md) | Worker-thread database-connection hygiene |
| [ADR-0022](0022-docker-compose-demo.md) | The example project also boots with `docker compose up` |
| [ADR-0023](0023-adrs-unpublished-from-docs-site.md) | ADRs live in the repository only, not on the docs site |
