# 0039. `mcp_view()` keeps the view `non_atomic_requests()` returns, and re-marks it async

- **Status:** Accepted
- **Date:** 2026-08-10
- **Deciders:** Ben Atkinson
- **Feature / area:** stateless view (`mcp_view`)
- **Builds on:** ADR-0031 — the `ATOMIC_REQUESTS` exemption this repairs
- **Supersedes / Superseded by:** none

## What problem were we trying to solve?

Fixing the `MiddlewareMixin` import (ADR-0038) took the Django-main leg from 57
failures to 3, and the three that remained were the ADR-0031 production bug
returning verbatim:

```
RuntimeError: You cannot use ATOMIC_REQUESTS with async views.
```

Django [#29303](https://code.djangoproject.com/ticket/29303) (`bdbda29c`,
2026-05-08, first shipping in 6.2) changed `_non_atomic_requests()` from
mutating the view to returning a new wrapper:

```diff
-    view._non_atomic_requests.add(using)
-    return view
+    @wraps(view)
+    def wrapper(*args, **kwargs): ...
+    wrapper._non_atomic_requests = databases
+    return wrapper
```

`mcp_view()` called the decorator for its side effect and threw the result away:

```python
for alias in connections:
    transaction.non_atomic_requests(using=alias)(exempt_view)
return exempt_view
```

That only ever worked because of the in-place mutation. From 6.2 the exemption
lands on a wrapper nobody keeps, the returned view carries no
`_non_atomic_requests`, and every consumer running `ATOMIC_REQUESTS = True` —
the cookiecutter-django default — gets the issue-#45 500 back on every request.

The second half is nastier. Django's new wrapper is a plain `def` even when it
wraps an async view, and `functools.wraps` does not carry coroutine-function
identity. Simply keeping the return value therefore hands Django something it
reads as a *sync* view, so it would call our async view through the sync path
and get a coroutine object where a response belongs.

## What did we try?

### Attempt 1 — keep the return value, and stop there   <!-- ❌ insufficient -->

The obvious one-word fix (`exempt_view = ...`). Necessary but not sufficient:
it fixes the exemption and introduces the sync-demotion bug above.

### Attempt 2 — set `_non_atomic_requests` on the view ourselves   <!-- ❌ rejected -->

`exempt_view._non_atomic_requests = set(connections)`. Sidesteps both problems
and is exactly the private-attribute reach this package exists not to do —
the failure mode in the second invariant, aimed at Django instead of the SDK.
It also re-breaks the moment Django renames the attribute, which is precisely
what #29303 signals it feels free to do.

### Attempt 3 — keep the return value and re-mark the result   <!-- ✅ chosen -->

```python
for alias in connections:
    exempt_view = transaction.non_atomic_requests(using=alias)(exempt_view)
if not iscoroutinefunction(exempt_view):
    markcoroutinefunction(exempt_view)
```

`markcoroutinefunction` is public asgiref API for this exact case — Django's own
`MiddlewareMixin` uses it to the same end. The guard keeps the call a no-op on
5.2/6.0/6.1, where the decorator still returns the async view unchanged.

## What did we land on, and why?

Attempt 3. Public API on both halves, correct on every supported line, and the
wrapper Django hands back is awaited rather than demoted: it returns the inner
coroutine, so marking it makes `await view(request)` behave as before.

`tests/test_views.py::test_view_stays_a_coroutine_function` pins the second
half, which no existing test covered — the three `ATOMIC_REQUESTS` tests catch
the missing exemption, but nothing caught a view quietly turning sync.

## Consequences

- The `ATOMIC_REQUESTS` exemption survives Django 6.2, so ADR-0031 keeps holding.
- `mcp_view()` gains an asgiref import and a version-agnostic guard; no public
  signature changes and nothing to document in `docs/`.
- Worth a CHANGELOG entry at the next release: consumers on 6.2 pre-releases
  would otherwise hit a 500 that looks exactly like the one 0.1.x already fixed.
- A reminder that discarding a decorator's return value is a latent bug even
  when the decorator documents itself as mutating.
