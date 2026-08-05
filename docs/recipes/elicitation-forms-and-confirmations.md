# Recipe: elicitation — forms and destructive-action confirmations

Elicitation lets a tool pause mid-call and ask the user for input.
Two Django-shaped uses cover most of what you will want it for:

- **Filling in a form** — a tool was called with missing or invalid fields; instead of failing, it asks for exactly what a Django form says is wrong.
- **Confirming a destructive action** — an update or delete does not run until the user has explicitly approved it.

Both patterns need [`request_state_security()`](../usage.md#elicitation-that-survives-your-load-balancer) wired, so the answer can land on any worker.

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
    ctx: Context, name: str = "", email: str = ""
) -> str | InputRequiredResult:
    """Create a customer, asking for whatever the form finds missing or invalid."""
    supplied = {"name": name, "email": email}
    answer = (ctx.input_responses or {}).get("corrections")
    if isinstance(answer, ElicitResult):
        if answer.action != "accept":
            return "Creation cancelled."
        supplied |= {
            k: v for k, v in (answer.content or {}).items() if isinstance(v, str)
        }

    form = CustomerForm(data=supplied)
    if form.is_valid():
        customer = form.save()
        return f"Created customer {customer.pk}: {customer.name}"

    messages = "; ".join(
        f"{field}: {' '.join(errors)}" for field, errors in form.errors.items()
    )
    return InputRequiredResult(
        input_requests={
            "corrections": _ask(
                f"Please correct: {messages}",
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
