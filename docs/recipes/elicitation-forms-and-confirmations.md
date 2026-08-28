# Recipe: elicitation — forms and destructive-action confirmations

Elicitation lets a tool pause mid-call and ask the user for input.
Two Django-shaped uses cover most of what you will want it for:

- **Filling in a form** — a tool was called with missing or invalid fields; instead of failing, it asks for exactly what a Django form says is wrong.
- **Confirming a destructive action** — an update or delete does not run until the user has explicitly approved it.

Both patterns need [`request_state_security()`](../usage.md#elicitation-that-survives-your-load-balancer) wired, so the answer can land on any worker.

## Which clients support it

Elicitation is the most unevenly adopted part of the spec, so check your users' client before you design a flow around it.
Support is per *product*, not per vendor — Claude Code has it and Claude.ai does not.
No consumer web portal has it at all: Claude.ai, ChatGPT and the Gemini app each route in-conversation UI through their own app or widget model instead, which makes elicitation a coding-agent and IDE feature today.

| Client | Elicitation | Notes |
| --- | --- | --- |
| Claude Code (CLI) | ✅ | Form and URL modes since [v2.1.76](https://claude-world.com/articles/claude-code-2176-release/) (14 Mar 2026). [`Elicitation` and `ElicitationResult` hooks](https://code.claude.com/docs/en/hooks) let users auto-answer. |
| Claude.ai (web) | ❌ | Tracked in [anthropics/claude-ai-mcp#153](https://github.com/anthropics/claude-ai-mcp/issues/153), open. |
| Claude Desktop | ❌ | No support and no live tracker — [anthropics/claude-code#41110](https://github.com/anthropics/claude-code/issues/41110) was filed against the CLI repository and closed as invalid. |
| Codex CLI | ✅ | Server-driven elicitation merged in [openai/codex#17043](https://github.com/openai/codex/pull/17043) (8 Apr 2026). |
| ChatGPT (web, developer mode) | ❌ | No documented support; interactive UI goes through the Apps SDK widget model instead. |
| Gemini CLI | ❌ | Advertises `roots` only, so the request answers `Method not found`. Both trackers — [#22249](https://github.com/google-gemini/gemini-cli/issues/22249) and, for URL mode, [#15613](https://github.com/google-gemini/gemini-cli/issues/15613) — were closed in May 2026 as "no immediate plans". |
| Gemini (consumer app) | ❌ | No self-serve third-party MCP servers at all — Spark connectors are partnership-only. |
| GitHub Copilot (VS Code) | ✅ | Form and URL modes; server-supplied defaults since [v1.105](https://code.visualstudio.com/updates/v1_105). |
| GitHub Copilot (Visual Studio) | ✅ | Answered in the chat window. VS 2026, backported to [VS 2022 17.14+](https://learn.microsoft.com/en-us/visualstudio/releases/2022/release-notes). |
| Cursor | ✅ | Since [v1.5](https://cursor.com/changelog/1-5) (Aug 2025), form mode only; string, number, boolean and enum schemas. |
| MCP Inspector | ✅ | Renders each elicitation as a real form — the quickest way to try yours. |

Checked 28 August 2026; treat it as a snapshot and confirm against your client's own release notes.

A client without elicitation does not degrade on your behalf, and the two patterns below want opposite things from that.

Form filling should still work: take the values as ordinary arguments and elicit only the corrections, as `create_customer` does, so a client that cannot ask still succeeds whenever the agent supplied valid fields.
Destructive confirmation should not: if the client cannot put the question to a human, the safe outcome is that `delete_customer` never deletes.
That is what the code below already does — an unanswered request means no confirmation, and no confirmation means no delete.

## How a tool asks

On the 2026-07-28 spec there is no held connection and no callback.
The tool returns the SDK's `InputRequiredResult` naming what it needs; the client renders that as a form and **retries the same call** with the answers attached.
The tool runs top-to-bottom both times — the retry finds the answers in `ctx.input_responses` and finishes:

```python
from mcp.server.mcpserver import Context
from mcp.types import (
    ElicitRequest,
    ElicitRequestFormParams,
    ElicitResult,
    InputRequiredResult,
)


def _ask(message: str, properties: dict[str, dict[str, str]]) -> ElicitRequest:
    """Build a form elicitation for the given JSON-schema properties."""
    return ElicitRequest(
        params=ElicitRequestFormParams(
            message=message,
            requested_schema={
                "type": "object",
                "properties": properties,
                "required": list(properties),
            },
        )
    )
```

Each answer is an `ElicitResult` whose `action` is `"accept"`, `"decline"`, or `"cancel"`, with the submitted values in `.content` on accept.
Treat anything but an explicit accept as a no.

## Confirming a destructive action

The tool asks before it deletes, and only an accepted `True` runs the ORM delete.
Pair it with `destructive_hint` so well-behaved clients add their own confirmation UX on top — [annotations are hints](../usage.md#annotating-tools-optional-encouraged), this elicitation is the enforcement:

```python
from mcp.types import ToolAnnotations

from customers.models import Customer


@server.tool(annotations=ToolAnnotations(destructive_hint=True, open_world_hint=False))
def delete_customer(ctx: Context, customer_id: int) -> str | InputRequiredResult:
    """Delete a customer, after explicit confirmation."""
    answer = (ctx.input_responses or {}).get("confirm_delete")
    if answer is None:
        return InputRequiredResult(
            input_requests={
                "confirm_delete": _ask(
                    f"Really delete customer {customer_id}? This cannot be undone.",
                    {"confirm": {"type": "boolean"}},
                )
            }
        )
    accepted = isinstance(answer, ElicitResult) and answer.action == "accept"
    if not accepted or not (answer.content or {}).get("confirm"):
        return "Delete cancelled."
    deleted, _ = Customer.objects.filter(pk=customer_id).delete()
    return f"Deleted {deleted} customer(s)."
```

The two requests are independent — the confirmation can be answered by a different worker, or a worker started after the question was asked.

## Filling in a form

Let a Django form own validation, exactly as it would for a browser: the tool feeds it whatever the agent supplied, and elicits corrections for the fields the form rejects — quoting the form's own error messages:

```python
from django import forms

from customers.models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "email"]


@server.tool()
def create_customer(
    ctx: Context,
    name: str = "",
    email: str = "",
) -> str | InputRequiredResult:
    """Create a customer, asking for whatever the form finds missing or invalid."""
    supplied = {"name": name, "email": email}
    answer = (ctx.input_responses or {}).get("corrections")
    if isinstance(answer, ElicitResult):
        if answer.action != "accept":
            return "Creation cancelled."
        corrections = answer.content or {}
        supplied |= {k: v for k, v in corrections.items() if isinstance(v, str)}

    form = CustomerForm(data=supplied)
    if form.is_valid():
        customer = form.save()
        return f"Created customer {customer.pk}: {customer.name}"

    problems = [f"{field}: {' '.join(errors)}" for field, errors in form.errors.items()]
    return InputRequiredResult(
        input_requests={
            "corrections": _ask(
                f"Please correct: {'; '.join(problems)}",
                {field: {"type": "string"} for field in form.errors},
            )
        }
    )
```

Call it with `email="not-an-email"` and the user is asked to correct exactly that field, with Django's own "Enter a valid email address." as the reason.
If a correction is still invalid, the same code path simply asks again — multi-round flows need nothing extra.

Because the retry replays the original arguments alongside the answers, valid fields never need re-entering; and because validation lives in the form, the rules stay identical whether the customer arrives via this tool or your ordinary views.

## Seeing it live

The [example project](../example.md)'s `test_input_required_result_*` fixtures run these mechanics — including multi-round flows and tampered-state rejection — and MCP Inspector renders each elicitation as a real form.
