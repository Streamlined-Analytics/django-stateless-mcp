# 0045. Share Django usage counts with Django Probe from a monthly workflow

- **Status:** Accepted
- **Date:** 2026-09-04
- **Deciders:** Ben Atkinson
- **Feature / area:** django-probe
- **Builds on:** none — first ADR for django-probe
- **Supersedes / Superseded by:** none

## What problem were we trying to solve?

Django's maintainers cannot see which features real projects depend on, so
deprecations run on guesswork. [Django Probe](https://github.com/django-probe/django-probe)
fixes that from the project side: a dev-only CLI walks the repository's Python
files with an AST scan, counts a fixed set of patterns (`.filter()`,
`.annotate()`, `transaction.atomic`, signal receivers, the custom user model,
and the `.extra()` and `@cache_page` usages the maintainers are deciding on),
and posts integers, package names and version strings to djangoprobe.org.
No source, paths or repository names leave the machine.

We wanted this project to contribute, with three constraints: the job must
not slow down or gate ordinary CI, nothing beyond the documented payload may
leave the runner, and the setup must be provable on the pull request that
adds it rather than discovered on the first scheduled run.

## What did we try?

### Attempt 1 — run it as a standalone tool (`uvx django-probe`)   <!-- ❌ rejected up front -->

The payload's `django_version` and `dependencies` come from
`importlib.metadata` of the interpreter running the scan. In an isolated tool
environment that reports no Django and a one-package inventory, which defeats
the point. The scan has to run inside the project's own environment, so the
workflow syncs the locked project environment first and then installs
django-probe into that same interpreter.

### Attempt 2 — bolt it onto the existing CI job   <!-- ❌ rejected up front -->

The test job runs on self-hosted runners with the full compose stack. Adding
a monthly submit there couples it to the heaviest path in the repository and
a scheduled run would still need the runner-creation dance. A GitHub-hosted
`ubuntu-latest` job that installs the development environment once a month
costs a few minutes and nothing else.

### Attempt 3 — run on every push or pull request   <!-- ❌ rejected up front -->

Aggregate usage data does not need to block builds, and the upstream guidance
is a schedule. We kept a `pull_request` trigger scoped to the workflow file
itself, and in that event the job runs `submit --dry-run`, which prints the
payload and sends nothing. So a change to the job is proven by the PR that
makes it, and the first real submission is the scheduled one.

### Attempt 4 — get past the one-week `exclude-newer` window   <!-- ❌ superseded before merge -->

Both django-probe releases were uploaded on 1 and 2 September 2026, so
`uv lock` refused them under `exclude-newer = "1 week"`. A one-shot
`UV_EXCLUDE_NEWER` or `--frozen` was rejected: both lift the guard for every
package in the resolution and leave nothing in the repo to reverse. Waiting
until 9 September would have left the PR red for five days with the job
unproven. The first version of this PR took the house escape hatch instead: a
dated `[tool.uv] exclude-newer-package` entry pinned to the 0.2.0 upload time,
which let exactly that release through and expired by arithmetic on
9 September. It was removed, not swept, once django-probe moved out of the
lockfile altogether (see "Where the package is declared" below): with nothing
new to resolve, `uv lock` needs no override.

### Attempt 5 — how the job installs the environment   <!-- ✅ chosen -->

`uv sync --locked` syncs the locked dependency groups on a GitHub-hosted
runner, so the inventory is exactly what the lockfile says and a drifted lock
fails the job rather than reporting a stale environment. `uv pip install
django-probe==0.2.0` then adds the scanner to that same `.venv`, and
`uv run --no-sync` runs it without a second sync touching the environment.

### Where the token lives   <!-- ✅ repository secret -->

django-probe reads `[tool.django_probe] token` from `pyproject.toml` or the
`DJANGO_PROBE_TOKEN` environment variable. The token only attributes a
submission to a project and grants nothing, but committing it invites
misattribution by anyone with the file. The project token is minted once by hand (`django-probe login` needs a
browser) and stored as the `DJANGO_PROBE_TOKEN` repository secret.
With the secret unset the CLI submits anonymously rather than failing, so the
job degrades to a still-useful contribution instead of a red run.

## What did we land on, and why?

A `.github/workflows/django-probe.yml` that runs `django-probe submit .`
monthly on a GitHub-hosted runner, with `workflow_dispatch` (including a
`dry_run` input) and a dry run on pull requests touching the workflow. The
job runs `uv sync --locked` and then installs `django-probe==0.2.0` into the
same `.venv`, so the payload's inventory is the real development
environment. Job permissions are `contents: read` and the checkout persists
no credentials.

### Where the package is declared   <!-- ✅ workflow only, not a project dependency -->

The first version of this PR added `django-probe` to the `lint` dependency
group, with the `exclude-newer-package` override above to get it into
`uv.lock`. Nothing but this job uses it, and a dependency-group entry puts a
third-party submission tool into every contributor's default `uv sync` (the `lint` group is part of the default `dev` group) and the lockfile for the sake of a monthly run.
Installing it in the job itself, after the locked sync, keeps the same
interpreter (which is all the version inventory needs) without making it a
project dependency, and `pyproject.toml` and `uv.lock` are untouched.

The pin lives in the workflow, so Dependabot's uv updates do not see it and it
is bumped by hand. It stays at 0.2.0 for now: 0.3.0–0.3.2 were published on
11–12 Sep 2026, inside the project's 7-day supply-chain cooldown.

## What does this cost us?

- A few GitHub-hosted minutes a month.
- The full development dependency inventory, names and versions, goes to a
  third party. Nothing in it is secret, but it is a disclosure and the reason
  the job runs `--dry-run` on pull requests rather than submitting.
- The token has to be minted by hand once and rotated if it is ever revoked
  on djangoprobe.org; the job keeps working, anonymously, in the meantime.
- The django-probe version is pinned in the workflow and has to be bumped by
  hand, because Dependabot does not track a `uv pip install` inside a job.
