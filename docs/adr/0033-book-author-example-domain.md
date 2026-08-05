# 0033. The example project gets a Book/Author domain, admin, and a slow tool

- **Status:** Accepted
- **Date:** 2026-08-01
- **Deciders:** Ben Atkinson
- **Feature / area:** example project
- **Builds on:** ADR-0015 — the runnable example this re-themes; ADR-0014 — the
  permission layering the demo teaches; ADR-0030 — the quick-start structure the
  new steps slot into
- **Supersedes / Superseded by:** none

## What problem were we trying to solve?

The example project had no domain of its own: no models, no admin, and a
permission demo built on an imaginary `delete_widget` tool gated on Django's
built-in `auth.delete_user` — chosen (ADR-0015) precisely because the example
had no models to hang a permission on. Three consequences:

- The permission walkthrough taught a *borrowed* permission, not the
  `Meta.permissions` mechanism a real project would use.
- Toggling the permission required a management command; a Django developer's
  instinct — do it in the admin — was impossible, because the admin was not
  installed.
- Nothing in the example was recognisably "a Django app". Readers arriving
  from Django's own documentation, which teaches with books and authors,
  found arithmetic toys (`add`, `multiply`) and abstract plumbing probes.

Separately, the long-running-jobs recipe (ADR-0029) documented why tools must
not block — but the example offered no way to *feel* what a blocking tool
does, or to observe that it does not stall the fleet.

## What did we try?

### Attempt 1 — minimal re-theme, keep the toys   <!-- ❌ rejected by the user -->

Replace only the permission demo and add the book tools, keeping `add`,
`multiply` and `count_users` to minimise test churn. Rejected in review: the
generic toys are exactly the un-Django-ness being removed, and the churn is
confined to the suite's own assertions.

### Attempt 2 — parameterized admin classes without a runtime shim   <!-- ❌ failed -->

`class BookInline(admin.TabularInline[Book, Author])` satisfies mypy strict
(django-stubs declares the generics) but crashes at import:
`TypeError: type 'TabularInline' is not subscriptable`. Django's real classes
carry no `__class_getitem__`; only `django_stubs_ext.monkeypatch()` adds it,
and django-stubs lived in the `typecheck` dependency group, absent from the
Docker demo image. Un-parameterized classes flip the failure to mypy
(`type-arg` under strict).

### Attempt 3 — guard the monkeypatch on importability   <!-- ❌ superseded -->

An `importlib.util.find_spec` guard in settings let each environment do what
it could — but the Docker image would then import parameterized admin classes
*without* the patch and crash anyway. The guard protected the wrong module.

## What did we decide?

A full Book/Author re-theme, Django-docs style:

- **Models with the custom permission.** `Author` (with
  `Meta.permissions = [("can_update_authors", "Can update authors")]`) and
  `Book`, in a real `example/migrations/` package. The permission demo now
  teaches the mechanism Django's docs recommend instead of borrowing
  `auth.delete_user`.
- **Tool mapping.** `delete_widget` → `update_author` (execution-gated and
  visibility-filtered, both layers unchanged in shape); `count_users` →
  `count_books` (the ADR-0021 connection-hygiene probe, same role);
  `add` → `list_books` (the quick start's first tool call now reads the ORM);
  `multiply` → `book_slug` (the autodiscovery canary, ADR-0009 — kept
  deliberately ORM-free, see the constraint below). All `test_*` conformance
  fixtures keep their names: the conformance baseline pins them (ADR-0015).
- **The admin is the primary permission toggle.** `django.contrib.admin` +
  `staticfiles` + a `TEMPLATES` setting join the example; seed creates an
  `admin`/`admin` superuser (published demo credentials, same stance as the
  committed `SECRET_KEY`). The README walkthrough toggles
  *Can update authors* in the admin while Inspector re-lists tools. The seed
  flags (`--grant-update-authors`/`--revoke-update-authors`) stay as the
  scriptable alternative.
- **Static files via handler wrapping, not whitenoise.** The entrypoints wrap
  in `ASGIStaticFilesHandler`/`StaticFilesHandler`, which serve from app
  finders with no `collectstatic` and no new dependency — demo-grade is the
  point. `django-stubs-ext` joins the `test` group (the group the Docker
  image installs) so `django_stubs_ext.monkeypatch()` can run unconditionally
  in settings, resolving attempts 2–3: admin classes stay parameterized for
  mypy strict *and* importable everywhere.
- **`slow_book_report` sleeps a full 30 seconds.** The SDK dispatches sync
  tools via `anyio.to_thread.run_sync` (a pooled thread per call), so the
  sleep occupies one thread — never the event loop, never the fleet, which
  the README has the reader verify by calling `worker_pid` mid-sleep. A
  shorter sleep was rejected: the point is to *feel* the block and to force
  the Inspector request-timeout lesson (the README raises it to 60 s before
  the call, per ADR-0030's inline-gotcha principle). The duration is a module
  constant read at call time, so tests monkeypatch it to zero and never pay
  the 30 s.

## Constraints this records

- **`test_*` fixtures must stay ORM-free.** The conformance harness and the
  multi-worker suite boot the example without running `migrate`; any `test_*`
  tool touching the database would crash there. `book_slug` is ORM-free for
  the same reason.
- The conformance baseline (`expected-failures.2026-07-28.yml`) needs no edit
  for this change — and the runner failing on stale entries is the check.

## Consequences

- The example finally demonstrates the package against a recognisable Django
  app: ORM reads, a custom permission, the admin, and migrations.
- The Docker image carries `django-stubs-ext` (a tiny typing shim) at
  runtime — the cost of keeping the admin code both strict-typed and
  importable.
- `example/db.sqlite3` on developer machines may retain an old
  `auth.delete_user` grant; it is harmless, and `migrate` creates the new
  tables on every entry path.
