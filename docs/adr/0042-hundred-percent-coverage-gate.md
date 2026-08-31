# 0042. Coverage is gated at 100%, and every exclusion is named

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** Ben Atkinson
- **Feature / area:** CI, test suite
- **Builds on:** none — first ADR for the coverage gate
- **Supersedes / Superseded by:** none

## What problem were we trying to solve?

`report.fail_under` was **50**, so the `coverage` job reported a number nobody
had to act on. Behind that, two things were wrong that only a real gate would
have surfaced.

**CI measured the package at 0%.** `run.source` was
`["example/", "src/", "tests/"]`, but the `test` job runs tox, which installs a
wheel — so `django_stateless_mcp` executes from `site-packages`, which matches
no entry in `source` and is therefore never measured. The combined CI report
listed every `src/django_stateless_mcp/*.py` at **0%**, and the total still
cleared 50, so the job stayed green. Local runs (editable install, imports
resolve to `src/`) reported ~87% and looked fine; the two shapes had been
disagreeing since the config was written.

**CI never saw the multiworker coverage.** The `multiworker` job ran
`MULTIWORKER=1 uv run pytest tests/test_multiworker.py -v` — no `coverage run`,
no artifact — so `tests/test_multiworker.py` reported 33% in the combine when
its real figure is 100%. Those tests are in `run.source`, so they were dragging
the total down for no reason.

Both were invisible at `fail_under = 50`. That is the argument for the gate: not
that 100% is a virtue, but that a decorative threshold hides configuration bugs
in the thing measuring it.

## What did we try?

### The measurement bug: `[paths]` remapping   <!-- ✅ chosen -->

```toml
run.source = [ "example/", "tests/" ]
run.source_pkgs = [ "django_stateless_mcp" ]
paths.source = [ "src/django_stateless_mcp", "*/site-packages/django_stateless_mcp" ]
```

`source_pkgs` matches the package wherever it is imported from, so the tox runs
measure it; `paths.source` folds the installed location back onto `src/` at
combine time. Verified both ways round: `uvx tox run -e py314-django60-mcp-release`
and a local `uv run coverage run -m pytest` now produce data that combines to
the same file list.

### Unreachable lines: pragmas, not tests   <!-- ✅ chosen -->

The alternative was forcing each one — faking `django.VERSION` for the 6.2
import branch, simulating a fleet that never boots. Those tests would assert
nothing except that a line ran, which is padding, not coverage.

Every exclusion is one line, carries its reason, and is listed here so the set
stays auditable rather than accreting:

| Location | Exclusion | Why |
|---|---|---|
| `example/middleware.py:20` | `no cover` | The `MiddlewareMixin` import branch for Django ≥ 6.2, past the supported matrix. See ADR-0038 |
| `tests/test_multiworker.py:101` | `no cover` | `Fleet.start` timeout — reached only when the fleet never boots, i.e. the test failing |
| `tests/test_multiworker.py:108` | `no cover` | `Fleet.stop` double-stop guard; no test stops twice |
| `tests/test_multiworker.py:112` | `no cover` | SIGKILL escalation for a fleet ignoring SIGTERM |
| `tests/test_multiworker.py:141` | `no branch` | Poll loop that always exits by `break`; exhausting it is the test failing |
| `tests/test_subscriptions.py:114` | `no branch` | Poll loop that always exits by `break`; exhausting it means a task leaked |

`no branch` rather than `no cover` on the two loops is deliberate: the loop body
*is* covered, only the exhaustion edge is not. A `for ... else: pytest.fail(...)`
was tried first and does not help — it relocates the uncovered line into the
`else` rather than removing the branch.

### Gaps that were simply untested   <!-- ✅ closed with tests -->

Everything else got a real test. The package's own defensive paths —
`_ASGIResponse`'s malformed-message and no-response raises, the buffered
`http.disconnect` retry guard (ADR-0017), the listen dispatch that sends nothing
or is cancelled before its first frame, `_bearer_token` on a non-Bearer header —
live in a new `tests/test_internals.py`, deliberately separate so the public-API
contract tests in `test_views.py` stay free of internals.

Two were worth having regardless of coverage. `mcp_view()` under a plain-`def`
`non_atomic_requests` wrapper now has the *second* half of ADR-0039 pinned: the
existing test asserts the view is a coroutine function, but on 5.2–6.1 the
decorator returns it unchanged, so the `markcoroutinefunction` repair itself was
never executed. And `PermittedToolsFilter` on a request with no `user` at all —
no `AuthenticationMiddleware`, no `user_resolver` — is the shape its docstring
promises fails closed; it needed the new `filtered-open-mcp/` mount to reach.

Writing those tests turned up two real defects, both in code that had no test
precisely because it is only reached when something goes wrong.

`PermittedToolsFilter` read the tool list as `result["tools"]` for a dict but
`getattr(result, "tools", None)` for a model, so a `tools/list` result without
the key raised `KeyError` where the model branch already tolerated it being
absent. The `getattr` default says plainly that absence is meant to pass
through; the dict branch now uses `.get()` and does the same. Not live — the SDK
always sets the key — but it is public middleware.

`_handle_listen()` leaked its memory object stream on both error exits: only the
success path hands `message_receive` to `_streamed_response`, so the
`EndOfStream` and cancellation paths dropped it unclosed, and anyio's
`ResourceWarning` fired from `__del__`. The cancellation path is the client
disconnecting mid-stream, which is not rare under load. Both exits now close it.
This one is the argument for the gate in miniature: the leak had existed since
ADR-0020, and it became visible the moment a test executed the path.

The SEP-2322 fixtures are ADR-0041.

## What did we land on, and why?

`report.fail_under = 100`, with the measurement fixed and the exclusions named.
`coverage report` exits non-zero below the threshold, so the existing `coverage`
job became a real gate with no workflow change.

The `multiworker` job now runs under `coverage run` and uploads
`coverage-multiworker`; the `coverage` job gained `multiworker` in its `needs`,
with a comment saying why — those tests are the only cover for
`tests/test_multiworker.py`, so dropping the dependency silently fails the gate
rather than obviously skipping a job.

`just coverage` gained the fleet run for the same reason: without it the recipe
would now fail locally, and the fix would look like a broken gate rather than a
missing input.

## Consequences

- A line added without a test fails CI. That is the point, and it is a real cost
  on future work — the escape hatch is a pragma with a reason, reviewed like any
  other line.
- `tests/` is inside `run.source`, so dead test-helper code fails the gate too.
  That is a feature: it caught a stub wrapper this change had written and never
  called.
- The tox-versus-local disagreement cannot silently return; either shape now has
  to reach 100 on its own.
- `coverage report` after a plain `uv run pytest` now fails, because the fleet
  tests are skipped without `MULTIWORKER=1`. Use `just coverage`, which runs
  both.
- `PermittedToolsFilter` grew strictly more forgiving, so no deprecation path is
  needed; worth a CHANGELOG line at the next release, alongside the
  `subscriptions/listen` stream leak.
- Assertions on SDK-owned strings are a trap: a test pinning a tool exception's
  text passed on `mcp==2.0.x` and failed on git main, which now wraps it in
  `UnexpectedToolError` and redacts the message. Assert on `isError`, not on
  wording the SDK is free to change.
