# ADR-0002: Host docs on Read the Docs, with hand-written guides

- **Status:** Accepted
- **Date:** 2026-07-29
- **Builds on:** none — first ADR for documentation

## Context

The scaffold shipped **Zensical** building to **GitHub Pages**. That had three
problems, one fatal and two structural.

The fatal one: the site had never deployed. Every `Documentation` run failed
because GitHub Pages was never enabled on the repository —
`actions/configure-pages` returns *"Get Pages site failed. Please verify that
the repository has Pages enabled."* The workflow had been red since the repo was
created.

The structural ones:

1. **No versioned docs.** GitHub Pages publishes one site: latest. This package
   commits to a stated spec-version support policy — which MCP spec and which
   `mcp` SDK version each release supports. A reader pinned to an older release
   has no matching documentation, which makes that promise hard to honour.
2. **No pre-merge check.** `docs.yml` triggered only on push to `main`, so a PR
   that broke the docs build passed CI and failed only after merge.

## What we considered

### Stay on Zensical + GitHub Pages, add `mike`

Keeps the most modern generator and adds no third-party dependency. Rejected
because versioning and per-PR previews then become ours to build and maintain,
and previews in particular are awkward on Pages.

### Sphinx + furo on Read the Docs

The best-supported path on RTD, and what `adamchainz` runs across his Django
packages. Rejected on cost: it means rewriting the docs from Markdown to reST for
benefits that are mostly stylistic. reST is more precise for API work; Markdown
has far lower contribution friction, which matters more for a package that wants
outside contributors.

### Zensical on Read the Docs via `build.commands`

RTD can host any generator by overriding the build entirely. Rejected for the
same reason ADR-0001 rejected `ty`: `build.commands` is beta, and when it is used
RTD installs none of its own extensions, so integrations like the version-warning
banner are lost. The published artefact should not sit on beta infrastructure.

### MkDocs-Material on Read the Docs (chosen)

Keeps Markdown and mkdocstrings, so existing pages carry over unchanged. RTD
supports MkDocs natively via the `mkdocs:` config key — no beta path, all
integrations intact — and provides versioned URLs and per-PR previews as
defaults rather than as work.

## Decision

**Read the Docs hosts the documentation**, built by **MkDocs-Material**, using
uv's native RTD support:

```yaml
python:
  install:
    - method: uv
      command: sync
      groups: [docs]
mkdocs:
  configuration: mkdocs.yml
  fail_on_warning: true
```

`docs.yml` no longer deploys. It builds with `mkdocs build --strict` on pull
requests and on `main`, so breakage is caught before merge.

**Documentation is a hybrid**, not purely generated:

- `reference.md` stays generated from docstrings via mkdocstrings, so the API
  listing cannot drift from the code.
- Narrative pages are **hand-written and carry the reasoning** — why the
  2026-07-28 spec matters, why elicitation used to break on a multi-worker
  deployment, and what follows from statelessness. Generated docs can only ever
  say *what*; the *why* has to be written.
- ADRs are published as part of the site, because the reasoning behind a
  decision is often more useful to someone extending the package than the
  resulting code.

## Consequences

- **A manual step remains:** the project must be imported on readthedocs.org and
  connected to the repository. `.readthedocs.yaml` alone does not create the
  site. Until that is done, `documentation` in `pyproject.toml` points at a URL
  that does not resolve.
- GitHub Pages is abandoned rather than fixed. This resolves the permanently red
  workflow.
- **We have knowingly adopted a generator with a deadline.** Material for MkDocs
  reaches end of life on **5 November 2026**, and MkDocs 2.0 will remove the
  plugin system and rewrite theming with no migration path — the Material team
  describe it as "currently unlicensed — unsuitable for production use". `mkdocs`
  is therefore pinned `<2` explicitly, since Dependabot now covers the `uv`
  ecosystem and would otherwise propose it.
- **The escape hatch is deliberate:** Zensical natively reads `mkdocs.yml`, so
  the config written here is the migration path back. Revisit before November
  2026.

## Follow-ups

- Import the project on Read the Docs and verify the first build.
- Decide the versioning scheme once there is a release to version.
- Add doc linting (link checking, `blacken-docs` for code blocks) when a
  pre-commit config is introduced — the repo currently has none.
