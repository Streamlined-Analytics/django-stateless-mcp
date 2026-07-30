"""Autodiscovered tool registrations for the ``example`` app.

Nothing imports this module explicitly: it registers ``multiply`` only if
``django_stateless_mcp``'s autodiscovery imported it, which is what the
autodiscovery tests assert.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.prompts.base import UserMessage
from mcp.shared.exceptions import MCPError
from mcp.types import (
    MISSING_REQUIRED_CLIENT_CAPABILITY,
    CreateMessageRequest,
    CreateMessageRequestParams,
    CreateMessageResult,
    ElicitRequest,
    ElicitRequestFormParams,
    ElicitResult,
    InputRequest,
    InputRequiredResult,
    ListRootsRequest,
    ListRootsResult,
    SamplingMessage,
    TextContent,
)

from example.mcp_server import server, server_b


@server.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b


# SEP-2322 conformance fixtures, ported from the mcp-everything-server in
# modelcontextprotocol/python-sdk (MIT, Copyright (c) 2024 Anthropic, PBC).


def _elicitation(message: str, field: str, field_type: str = "string") -> ElicitRequest:
    """Build a form elicitation requesting one field."""
    requested_schema: dict[str, Any] = {
        "type": "object",
        "properties": {field: {"type": field_type}},
        "required": [field],
    }
    return ElicitRequest(params=ElicitRequestFormParams(message=message, requested_schema=requested_schema))


def _sampling_request(prompt: str, max_tokens: int) -> CreateMessageRequest:
    """Build a sampling request carrying one user message."""
    return CreateMessageRequest(
        params=CreateMessageRequestParams(
            messages=[SamplingMessage(role="user", content=TextContent(type="text", text=prompt))],
            max_tokens=max_tokens,
        )
    )


def _elicited(answer: object, field: str) -> str | None:
    """Read one string field from an elicitation answer, or ``None``."""
    if not isinstance(answer, ElicitResult) or not answer.content:
        return None
    value = answer.content.get(field)
    return value if isinstance(value, str) else None


def _sampled_text(answer: object) -> str | None:
    """Read the text of a sampling answer, or ``None``."""
    if not isinstance(answer, CreateMessageResult) or answer.content.type != "text":
        return None
    return answer.content.text


@server_b.tool()
@server.tool()
async def test_input_required_result_elicitation(
    ctx: Context,
) -> str | InputRequiredResult:
    """Return input_required once, then greet with the elicited name."""
    responses = ctx.input_responses or {}
    if "user_name" in responses:
        name = _elicited(responses["user_name"], "name") or "stranger"
        return f"Hello, {name}!"
    return InputRequiredResult(input_requests={"user_name": _elicitation("What is your name?", "name")})


@server.tool()
async def test_input_required_result_sampling(
    ctx: Context,
) -> str | InputRequiredResult:
    """Request one sampling round trip and echo the model's answer."""
    responses = ctx.input_responses or {}
    if "capital_question" in responses:
        text = _sampled_text(responses["capital_question"]) or "?"
        return f"Model said: {text}"
    return InputRequiredResult(
        input_requests={"capital_question": _sampling_request("What is the capital of France?", max_tokens=100)}
    )


@server.tool()
async def test_input_required_result_list_roots(
    ctx: Context,
) -> str | InputRequiredResult:
    """Request the client's roots and count them."""
    responses = ctx.input_responses or {}
    if "client_roots" in responses:
        answer = responses["client_roots"]
        count = len(answer.roots) if isinstance(answer, ListRootsResult) else 0
        return f"Client exposed {count} root(s)."
    return InputRequiredResult(input_requests={"client_roots": ListRootsRequest()})


@server_b.tool()
@server.tool()
async def test_input_required_result_request_state(
    ctx: Context,
) -> str | InputRequiredResult:
    """Round-trip an opaque requestState through the input_required flow."""
    responses = ctx.input_responses or {}
    confirmed = "confirm" in responses
    state_round_tripped = ctx.request_state == "request-state-nonce"
    if confirmed and state_round_tripped:
        return "state-ok: confirmation received"
    return InputRequiredResult(
        input_requests={"confirm": _elicitation("Please confirm", "ok", field_type="boolean")},
        request_state="request-state-nonce",
    )


@server.tool()
async def test_input_required_result_multiple_inputs(
    ctx: Context,
) -> str | InputRequiredResult:
    """Carry elicitation, sampling and roots requests in one round."""
    responses = ctx.input_responses or {}
    required_inputs = {"user_name", "greeting", "client_roots"}
    if required_inputs <= responses.keys():
        return "All inputs received."
    return InputRequiredResult(
        input_requests={
            "user_name": _elicitation("What is your name?", "name"),
            "greeting": _sampling_request("Generate a greeting", max_tokens=50),
            "client_roots": ListRootsRequest(),
        },
        request_state="multiple-inputs",
    )


def _multi_round_step1() -> InputRequiredResult:
    """Open the multi-round flow; also the restart for unrecognized state."""
    return InputRequiredResult(
        input_requests={"step1": _elicitation("Step 1: What is your name?", "name")},
        request_state=json.dumps({"round": 1}),
    )


@server.tool()
async def test_input_required_result_multi_round(
    ctx: Context,
) -> str | InputRequiredResult:
    """Run a three-round flow whose requestState evolves each round."""
    state = json.loads(ctx.request_state) if ctx.request_state else {"round": 0}
    responses = ctx.input_responses or {}

    if state["round"] == 0:
        return _multi_round_step1()

    if state["round"] == 1 and "step1" in responses:
        name = _elicited(responses["step1"], "name")
        return InputRequiredResult(
            input_requests={"step2": _elicitation("Step 2: What is your favorite color?", "color")},
            request_state=json.dumps({"round": 2, "name": name}),
        )

    if state["round"] == 2 and "step2" in responses:
        color = _elicited(responses["step2"], "color")
        return f"{state.get('name')} likes {color}."

    # Unrecognized state or missing answers: restart the flow from step 1.
    return _multi_round_step1()


@server.tool()
async def test_input_required_result_tampered_state(
    ctx: Context,
) -> str | InputRequiredResult:
    """Stay plaintext; tamper rejection happens in the SDK's state boundary."""
    if ctx.request_state is None:
        return InputRequiredResult(
            input_requests={"confirm": _elicitation("Please confirm", "ok", field_type="boolean")},
            request_state="round-1",
        )
    return f"state-ok: {ctx.request_state}"


@server.tool()
async def test_input_required_result_capabilities(ctx: Context) -> InputRequiredResult:
    """Only request methods the client declared capabilities for."""
    caps = ctx.client_capabilities
    # An absent capabilities declaration means "assume capable".
    sampling_supported = caps is None or caps.sampling is not None
    elicitation_supported = caps is None or caps.elicitation is not None

    requests: dict[str, InputRequest] = {}
    if sampling_supported:
        requests["sample"] = _sampling_request("Say hello", max_tokens=50)
    if elicitation_supported:
        requests["ask"] = _elicitation("What is your name?", "name")
    return InputRequiredResult(input_requests=requests, request_state="capability-gated")


@server.tool()
async def test_missing_capability(ctx: Context) -> str:
    """Raise MISSING_REQUIRED_CLIENT_CAPABILITY when sampling is undeclared."""
    capabilities = ctx.client_capabilities
    sampling_declared = capabilities is not None and capabilities.sampling is not None
    if not sampling_declared:
        raise MCPError(
            code=MISSING_REQUIRED_CLIENT_CAPABILITY,
            message="This tool requires the client 'sampling' capability",
            data={"requiredCapabilities": {"sampling": {}}},
        )
    return "Client declared sampling capability; proceeding."


@server.prompt()
async def test_input_required_result_prompt(
    ctx: Context,
) -> list[UserMessage] | InputRequiredResult:
    """Return input_required from prompts/get — the non-tool request case."""
    responses = ctx.input_responses or {}
    if "user_context" in responses:
        text = _elicited(responses["user_context"], "context") or "?"
        return [
            UserMessage(
                role="user",
                content=TextContent(type="text", text=f"Use the following context: {text}"),
            )
        ]
    return InputRequiredResult(
        input_requests={"user_context": _elicitation("What context should the prompt use?", "context")}
    )
