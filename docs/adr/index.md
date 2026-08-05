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
| [ADR-0024](0024-weekly-django-main-ci.md) | Weekly advisory CI run against Django git main |
| [ADR-0025](0025-django-61-matrix-factor.md) | Django 6.1 joins the test matrix at release candidate |
| [ADR-0026](0026-architecture-document.md) | A living ARCHITECTURE.md at the repository root |
| [ADR-0027](0027-adamchainz-tooling-adoptions.md) | Tooling adoptions from the django-linear-migrations / django-mysql review |
| [ADR-0028](0028-python-310-floor.md) | Python floor lowered to 3.10, tracking Django 5.2's own support |
| [ADR-0029](0029-benefits-led-messaging.md) | Benefits-led messaging across the README and docs |
| [ADR-0030](0030-quick-start-first-example-guide.md) | The example README is a quick-start guide, not a reference dump |
| [ADR-0031](0031-non-atomic-requests-exemption.md) | `mcp_view()` exempts itself from `ATOMIC_REQUESTS` on every alias |
| [ADR-0032](0032-consumer-realistic-example-settings.md) | The example project runs consumer-realistic settings, and the suite tests the gaps |
| [ADR-0033](0033-book-author-example-domain.md) | The example project gets a Book/Author domain, admin, and a slow tool |
| [ADR-0034](0034-encourage-tool-annotations.md) | Encourage tool annotations, demonstrated on the example's Book/Author tools |
| [ADR-0035](0035-concise-docs-link-out-no-adr-references.md) | User-facing docs stay concise, link out, and never cite ADRs |
| [ADR-0036](0036-elicitation-recipe.md) | A worked elicitation recipe — forms and destructive-action confirmations |
