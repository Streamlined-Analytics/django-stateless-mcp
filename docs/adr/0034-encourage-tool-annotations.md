# 0034. Encourage tool annotations, demonstrated on the example's Book/Author tools

- **Status:** Accepted
- **Date:** 2026-08-05
- **Deciders:** Ben Atkinson
- **Feature / area:** docs (usage guide), example project
- **Builds on:** ADR-0033 — the Book/Author tools the demonstration hangs off;
  ADR-0014 — the hints-are-not-enforcement stance this restates
- **Supersedes / Superseded by:** none

## What problem were we trying to solve?

The MCP spec's `ToolAnnotations` hints (`readOnlyHint`, `destructiveHint`,
`idempotentHint`, `openWorldHint`) let a well-behaved client build safer UX
around a server — auto-approve reads, confirm destructive calls, retry
idempotent ones. Nothing in this package's docs mentioned them, and no example
tool set any, so a consumer following our usage guide would ship an
unannotated server without ever learning the feature exists.

Two constraints shaped where and how to document them:

- The hint list belongs to the MCP spec and is actively evolving (a Tool
  Annotations Interest Group exists; new hints such as `agencyHint` are under
  proposal). Duplicating the authoritative list wholesale would rot.
- Annotations are explicitly untrusted hints. Any encouragement had to avoid
  presenting them as a permission mechanism, or it would undercut the
  execution-gating lesson of ADR-0014.

## What did we consider?

- **A dedicated recipe page.** Rejected: annotations are one decorator
  argument, not a workflow; a whole recipe overweights them and readers
  choosing tools from the usage guide would still miss it.
- **Documenting only, without touching the example.** Rejected: the example's
  README promises everything documented was run first, and live annotations
  cost five decorator edits while making the hints visible in Inspector and
  `tools/list`.
- **Annotating every example tool.** Rejected: the `test_*` conformance
  fixtures exist for SEP-2322 wire behaviour; annotating them adds diff noise
  without teaching anything. Only the Book/Author domain tools carry
  annotations.

## What did we land on?

A "Annotating tools (optional, encouraged)" section in `docs/usage.md`,
placed directly after tool registration — the point where a reader is
deciding what a tool declaration looks like. It gives one hint-per-bullet
with Book/Author illustrations, links the **versioned** spec schema
(`…/2026-07-28/schema#toolannotations`) as the authoritative list — frozen
per spec revision, so it stays correct for the era this package implements
rather than drifting — and closes by restating that hints are untrusted and
authorization stays inside the tool.

The example's five Book/Author tools now carry annotations: `list_books`,
`count_books`, `slow_book_report`, `book_slug` as read-only closed-world;
`update_author` as destructive, idempotent, closed-world. Verified on the
wire: `tools/list` serializes them camelCase on both `/mcp/` and
`/filtered-mcp/`.

## Consequences

- Consumers meet annotations at the moment they define tools, with working
  examples one `docker compose up` away.
- The spec link is version-pinned; when the package moves to a newer spec
  revision, the link must move with it (and any new hints get documented
  then).
- The example's `tools/list` payloads gained `annotations` fields — tests
  asserting exact tool-list shapes would need updating (none did).
