# Decision records

Architecture Decision Records capture *why* the project is the way it is: the
problem, what was tried, what failed, and what was chosen. They are written when
the decision is made and are not rewritten afterwards — a superseded decision
gets a new record rather than an edit.

They are published rather than kept internal because the reasoning is often more
useful to someone extending the package than the resulting code is.

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
