# Recipe: long-running jobs that report back

A tool call should return in milliseconds, but real work — a quarterly report, a data export, a reindex — takes minutes.
This recipe shows the pattern for that: the tool starts the job and returns immediately, and a [subscription stream](../usage.md#subscription-streams) tells the client the moment the result is ready.

The experience it buys the user: **kick off a long job, keep chatting with the AI, and the result comes back when it's ready.**

## Why not just do the work inside the tool?

Three things go wrong if a tool blocks until a slow job finishes:

1. **The conversation stalls.** The user sits at a spinner for minutes, unable to ask anything else.
2. **A server worker is pinned for the whole job.** A handful of concurrent slow calls and your fleet is fully occupied doing nothing.
3. **Timeouts and load balancers cut it off.** Minutes-long HTTP requests get killed by proxies, and a retry re-runs the whole job.

And the alternative without subscriptions — polling — is not much better: the client hammers a status tool every few seconds (wasteful, laggy), or the user has to keep asking *"is it done yet?"*.

## The pattern

1. The tool starts a background job (Celery here) and returns **immediately** with a job reference.
2. The client holds one open subscription stream (see [Subscription streams](../usage.md#subscription-streams) — ASGI only).
3. When the job finishes, it publishes a `ResourceUpdated` event; the server pushes it down the stream.
4. The client fetches the finished result with an ordinary tool call.

The notification is a thin *"something changed, come and fetch"* signal — the data itself travels through the normal tool path, where your authentication, permission checks, and logging already apply.

## The tool: start the job, return at once

```python
# reports/mcp.py
from django_stateless_mcp import django_request
from mcp.server.context import Context

from reports.tasks import generate_report


@server.tool()
def start_quarterly_report(ctx: Context, quarter: str) -> str:
    """Start generating the quarterly report; returns a job id."""
    job = generate_report.delay(quarter, django_request(ctx).user.pk)
    return f"Report for {quarter} started (job {job.id}). You will be notified at report://{job.id} when it is ready."
```

The tool is a plain sync function — it runs in a worker thread, so the ORM and Celery's `.delay()` are both fine — and it returns in milliseconds regardless of how long the report takes.

## The job: publish an event when done

When the job completes, publish the SDK's `ResourceUpdated` event to your server's `SubscriptionBus`:

```python
# reports/tasks.py
from asgiref.sync import async_to_sync
from celery import shared_task
from mcp.server.subscriptions import ResourceUpdated

from myproject.mcp import bus


@shared_task(bind=True)
def generate_report(self, quarter: str, user_pk: int) -> None:
    report = build_the_report(quarter, user_pk)
    report.job_id = self.request.id
    report.save()
    async_to_sync(bus.publish)(ResourceUpdated(uri=f"report://{report.job_id}"))
```

The task stores its own Celery id on the model (`bind=True` exposes it as `self.request.id`), so the URI it publishes is exactly the one the tool promised — and the same id is what `get_report` looks up below.

One important wrinkle: the Celery worker is a **different process** from your web workers, so the SDK's default `InMemorySubscriptionBus` cannot carry this event to an open stream — it only reaches streams held by the process that published.
For any deployment with a task queue or more than one web worker, implement `SubscriptionBus` over an external pub/sub backend (Redis, NATS, …).
The protocol is deliberately small — two methods, `publish` and `subscribe` — and one Redis-backed instance shared by the Celery workers and every web replica fans events out to whichever replica holds the stream.

## Fetching the result

The client, seeing the notification, calls a normal tool:

```python
@server.tool()
def get_report(ctx: Context, job_id: str) -> str:
    """Fetch a finished report by job id."""
    report = Report.objects.get(job_id=job_id, owner=django_request(ctx).user)
    return report.rendered_text
```

Because this is an ordinary permission-checked tool call, a pushed notification never becomes a way around your access rules — the event says *that* something is ready, never *what is in it*.

## Does this scale?

Better than the alternatives.
An idle subscription stream is just a parked connection: while nothing is happening it costs no CPU and a few kilobytes of memory, and a single small ASGI server holds thousands of them.
Fifty users each holding a stream is unmeasurable; this is the same economics as any chat or live-dashboard SSE feature.

Two real requirements:

- **ASGI only.** Under WSGI a held stream would pin an entire worker process for its lifetime — exactly the per-flow cost this package exists to remove — so the view answers `501` there rather than let you do it badly ([ADR-0020](https://github.com/Streamlined-Analytics/django-stateless-mcp/blob/main/docs/adr/0020-subscription-streams.md)).
  Everything else in this recipe (the tool, the task, the fetch) works under both.
- **An external bus once you have more than one process** — see the wrinkle above.

## Client support

The final hop — the result popping back into the user's conversation — belongs to the MCP **client**: it must hold the stream, react to the event, and surface the fetched result.
As of July 2026, MCP Inspector consumes subscription events; Claude Code does not yet.
The server side shown here is complete either way — when a client catches up with the spec, the same endpoint starts delivering with no server change.
