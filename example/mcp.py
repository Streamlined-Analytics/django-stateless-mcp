"""Autodiscovered tool registrations for the ``example`` app.

Nothing imports this module explicitly: it registers ``multiply`` only if
``django_stateless_mcp``'s autodiscovery imported it, which is what the
autodiscovery tests assert.
"""

from __future__ import annotations

import json

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

NAME_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
}


def _name_elicitation(message: str = "What is your name?") -> ElicitRequest:
    return ElicitRequest(params=ElicitRequestFormParams(message=message, requested_schema=NAME_SCHEMA))


@server_b.tool()
@server.tool()
async def test_input_required_result_elicitation(
    ctx: Context,
) -> str | InputRequiredResult:
    """Return input_required once, then greet with the elicited name."""
    responses = ctx.input_responses
    if responses and "user_name" in responses:
        answer = responses["user_name"]
        name = answer.content.get("name", "stranger") if isinstance(answer, ElicitResult) and answer.content else "?"
        return f"Hello, {name}!"
    return InputRequiredResult(input_requests={"user_name": _name_elicitation()})


@server.tool()
async def test_input_required_result_sampling(
    ctx: Context,
) -> str | InputRequiredResult:
    """Request one sampling round trip and echo the model's answer."""
    responses = ctx.input_responses
    if responses and "capital_question" in responses:
        answer = responses["capital_question"]
        text = answer.content.text if isinstance(answer, CreateMessageResult) and answer.content.type == "text" else "?"
        return f"Model said: {text}"
    return InputRequiredResult(
        input_requests={
            "capital_question": CreateMessageRequest(
                params=CreateMessageRequestParams(
                    messages=[
                        SamplingMessage(
                            role="user",
                            content=TextContent(type="text", text="What is the capital of France?"),
                        )
                    ],
                    max_tokens=100,
                )
            )
        }
    )


@server.tool()
async def test_input_required_result_list_roots(
    ctx: Context,
) -> str | InputRequiredResult:
    """Request the client's roots and count them."""
    responses = ctx.input_responses
    if responses and "client_roots" in responses:
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
    responses = ctx.input_responses
    if responses and "confirm" in responses and ctx.request_state == "request-state-nonce":
        return "state-ok: confirmation received"
    confirm = ElicitRequest(
        params=ElicitRequestFormParams(
            message="Please confirm",
            requested_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
        )
    )
    return InputRequiredResult(input_requests={"confirm": confirm}, request_state="request-state-nonce")


@server.tool()
async def test_input_required_result_multiple_inputs(
    ctx: Context,
) -> str | InputRequiredResult:
    """Carry elicitation, sampling and roots requests in one round."""
    responses = ctx.input_responses
    if responses and {"user_name", "greeting", "client_roots"} <= responses.keys():
        return "All inputs received."
    return InputRequiredResult(
        input_requests={
            "user_name": _name_elicitation(),
            "greeting": CreateMessageRequest(
                params=CreateMessageRequestParams(
                    messages=[
                        SamplingMessage(
                            role="user",
                            content=TextContent(type="text", text="Generate a greeting"),
                        )
                    ],
                    max_tokens=50,
                )
            ),
            "client_roots": ListRootsRequest(),
        },
        request_state="multiple-inputs",
    )


@server.tool()
async def test_input_required_result_multi_round(
    ctx: Context,
) -> str | InputRequiredResult:
    """Run a three-round flow whose requestState evolves each round."""
    state = json.loads(ctx.request_state) if ctx.request_state else {"round": 0}
    responses = ctx.input_responses or {}

    if state["round"] == 0:
        return InputRequiredResult(
            input_requests={"step1": _name_elicitation("Step 1: What is your name?")},
            request_state=json.dumps({"round": 1}),
        )

    if state["round"] == 1 and "step1" in responses:
        step1 = responses["step1"]
        name = step1.content.get("name") if isinstance(step1, ElicitResult) and step1.content else None
        color_schema = {
            "type": "object",
            "properties": {"color": {"type": "string"}},
            "required": ["color"],
        }
        return InputRequiredResult(
            input_requests={
                "step2": ElicitRequest(
                    params=ElicitRequestFormParams(
                        message="Step 2: What is your favorite color?",
                        requested_schema=color_schema,
                    )
                )
            },
            request_state=json.dumps({"round": 2, "name": name}),
        )

    if state["round"] == 2 and "step2" in responses:
        step2 = responses["step2"]
        color = step2.content.get("color") if isinstance(step2, ElicitResult) and step2.content else None
        return f"{state.get('name')} likes {color}."

    return InputRequiredResult(
        input_requests={"step1": _name_elicitation("Step 1: What is your name?")},
        request_state=json.dumps({"round": 1}),
    )


@server.tool()
async def test_input_required_result_tampered_state(
    ctx: Context,
) -> str | InputRequiredResult:
    """Stay plaintext; tamper rejection happens in the SDK's state boundary."""
    if ctx.request_state is None:
        confirm = ElicitRequest(
            params=ElicitRequestFormParams(
                message="Please confirm",
                requested_schema={
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                },
            )
        )
        return InputRequiredResult(input_requests={"confirm": confirm}, request_state="round-1")
    return f"state-ok: {ctx.request_state}"


@server.tool()
async def test_input_required_result_capabilities(ctx: Context) -> InputRequiredResult:
    """Only request methods the client declared capabilities for."""
    caps = ctx.client_capabilities
    requests: dict[str, InputRequest] = {}
    if caps is None or caps.sampling is not None:
        requests["sample"] = CreateMessageRequest(
            params=CreateMessageRequestParams(
                messages=[SamplingMessage(role="user", content=TextContent(type="text", text="Say hello"))],
                max_tokens=50,
            )
        )
    if caps is None or caps.elicitation is not None:
        requests["ask"] = _name_elicitation()
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
    responses = ctx.input_responses
    if responses and "user_context" in responses:
        answer = responses["user_context"]
        text = answer.content.get("context", "?") if isinstance(answer, ElicitResult) and answer.content else "?"
        return [
            UserMessage(
                role="user",
                content=TextContent(type="text", text=f"Use the following context: {text}"),
            )
        ]
    return InputRequiredResult(
        input_requests={
            "user_context": ElicitRequest(
                params=ElicitRequestFormParams(
                    message="What context should the prompt use?",
                    requested_schema={
                        "type": "object",
                        "properties": {"context": {"type": "string"}},
                        "required": ["context"],
                    },
                )
            )
        }
    )
