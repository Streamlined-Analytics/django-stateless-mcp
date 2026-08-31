"""Tests for the SEP-2322 fixture tools in ``example/mcp.py``.

Those tools exist for the MCP conformance harness, which runs as its own
workflow against a pinned alpha npm package and reports nothing back to
pytest. Driving them here too means the fixtures are regression-tested by the
suite that gates every commit, not only by a harness whose failures are
triaged through an expected-failures baseline. See ADR-0041.

Each flow is the package's thesis in miniature: a first request pauses with
``input_required``, and a second request carrying the answers -- and nothing
else -- completes it.
"""

from __future__ import annotations

from typing import Any

from django.test import Client

from tests.test_views import MCP_URL, accept, post_stateless

ALL_CAPABILITIES: dict[str, Any] = {"elicitation": {}, "sampling": {}, "roots": {}}


def call(
    client: Client,
    tool: str,
    params: dict[str, Any],
    *,
    capabilities: dict[str, Any] | None = None,
    method: str = "tools/call",
) -> Any:
    """Run one round of a fixture tool and return its JSON-RPC result."""
    return post_stateless(
        client,
        MCP_URL,
        tool,
        params,
        capabilities=ALL_CAPABILITIES if capabilities is None else capabilities,
        method=method,
    )["result"]


def sampled(text: str) -> dict[str, Any]:
    """Build the client's answer to a sampling request."""
    return {
        "role": "assistant",
        "content": {"type": "text", "text": text},
        "model": "stub-model",
        "stopReason": "endTurn",
    }


def roots(*uris: str) -> dict[str, Any]:
    """Build the client's answer to a roots request."""
    return {"roots": [{"uri": uri, "name": uri.rsplit("/", 1)[-1]} for uri in uris]}


def text_of(result: dict[str, Any]) -> Any:
    """Read the single text block off a completed tool result."""
    return result["content"][0]["text"]


def test_a_declined_elicitation_falls_back_to_the_default(client):
    """A client that refuses to answer still completes the call."""
    tool = "test_input_required_result_elicitation"
    assert call(client, tool, {"arguments": {}})["resultType"] == "input_required"

    resumed = call(client, tool, {"arguments": {}, "inputResponses": {"user_name": {"action": "decline"}}})

    assert text_of(resumed) == "Hello, stranger!"


def test_sampling_round_trips_the_models_answer(client):
    """A sampling request pauses the call; the model's text resumes it."""
    tool = "test_input_required_result_sampling"
    paused = call(client, tool, {"arguments": {}})

    assert paused["resultType"] == "input_required"
    assert "capital_question" in paused["inputRequests"]

    resumed = call(client, tool, {"arguments": {}, "inputResponses": {"capital_question": sampled("Paris")}})

    assert text_of(resumed) == "Model said: Paris"


def test_a_non_sampling_answer_is_not_read_as_text(client):
    """An answer of the wrong shape is ignored rather than misread as text."""
    tool = "test_input_required_result_sampling"

    resumed = call(client, tool, {"arguments": {}, "inputResponses": {"capital_question": {"action": "decline"}}})

    assert text_of(resumed) == "Model said: ?"


def test_list_roots_counts_what_the_client_exposed(client):
    """A roots request pauses the call; the client's roots resume it."""
    tool = "test_input_required_result_list_roots"
    paused = call(client, tool, {"arguments": {}})

    assert paused["resultType"] == "input_required"
    assert "client_roots" in paused["inputRequests"]

    resumed = call(
        client,
        tool,
        {"arguments": {}, "inputResponses": {"client_roots": roots("file:///a", "file:///b")}},
    )

    assert text_of(resumed) == "Client exposed 2 root(s)."


def test_a_non_roots_answer_counts_as_no_roots(client):
    """An answer of the wrong shape counts zero rather than raising."""
    tool = "test_input_required_result_list_roots"

    resumed = call(client, tool, {"arguments": {}, "inputResponses": {"client_roots": {"action": "decline"}}})

    assert text_of(resumed) == "Client exposed 0 root(s)."


def test_multiple_inputs_travel_in_one_round(client):
    """Elicitation, sampling and roots can pause on a single request."""
    tool = "test_input_required_result_multiple_inputs"
    paused = call(client, tool, {"arguments": {}})

    assert paused["resultType"] == "input_required"
    assert set(paused["inputRequests"]) == {"user_name", "greeting", "client_roots"}

    resumed = call(
        client,
        tool,
        {
            "arguments": {},
            "inputResponses": {
                "user_name": accept({"name": "Alice"}),
                "greeting": sampled("Hello!"),
                "client_roots": roots("file:///a"),
            },
            "requestState": paused["requestState"],
        },
    )

    assert text_of(resumed) == "All inputs received."


def test_multi_round_flow_advances_through_three_rounds(client):
    """A flow whose requestState evolves each round completes across three posts.

    Nothing is held between them: round three's answer is built entirely from
    the state round two minted and the answer this request carries.
    """
    tool = "test_input_required_result_multi_round"
    first = call(client, tool, {"arguments": {}})

    assert set(first["inputRequests"]) == {"step1"}

    second = call(
        client,
        tool,
        {
            "arguments": {},
            "inputResponses": {"step1": accept({"name": "Alice"})},
            "requestState": first["requestState"],
        },
    )

    assert set(second["inputRequests"]) == {"step2"}

    third = call(
        client,
        tool,
        {
            "arguments": {},
            "inputResponses": {"step2": accept({"color": "green"})},
            "requestState": second["requestState"],
        },
    )

    assert text_of(third) == "Alice likes green."


def test_multi_round_restarts_when_the_answers_are_missing(client):
    """A round the tool cannot serve reopens the flow at step one.

    The state says round one, but the request carries no ``step1`` answer, so
    there is nothing to advance on -- the retry has to start over rather than
    guess at an answer it was never given.
    """
    tool = "test_input_required_result_multi_round"
    opened = call(client, tool, {"arguments": {}})
    restarted = call(
        client,
        tool,
        {"arguments": {}, "inputResponses": {}, "requestState": opened["requestState"]},
    )

    assert restarted["resultType"] == "input_required"
    assert set(restarted["inputRequests"]) == {"step1"}

    resumed = call(
        client,
        tool,
        {
            "arguments": {},
            "inputResponses": {"step1": accept({"name": "Alice"})},
            "requestState": restarted["requestState"],
        },
    )

    assert set(resumed["inputRequests"]) == {"step2"}


def test_plaintext_request_state_is_echoed_back(client):
    """The tamper fixture stays plaintext; the SDK's boundary owns rejection."""
    tool = "test_input_required_result_tampered_state"
    opened = call(client, tool, {"arguments": {}})

    assert opened["resultType"] == "input_required"

    resumed = call(
        client,
        tool,
        {
            "arguments": {},
            "inputResponses": {"confirm": accept({"ok": True})},
            "requestState": opened["requestState"],
        },
    )

    assert text_of(resumed) == "state-ok: round-1"


def test_only_declared_capabilities_are_requested(client):
    """The tool asks for exactly what the client said it can answer."""
    tool = "test_input_required_result_capabilities"

    both = call(client, tool, {"arguments": {}})
    sampling_only = call(client, tool, {"arguments": {}}, capabilities={"sampling": {}})
    elicitation_only = call(client, tool, {"arguments": {}}, capabilities={"elicitation": {}})
    neither = call(client, tool, {"arguments": {}}, capabilities={})

    assert set(both["inputRequests"]) == {"sample", "ask"}
    assert set(sampling_only["inputRequests"]) == {"sample"}
    assert set(elicitation_only["inputRequests"]) == {"ask"}
    assert neither["inputRequests"] == {}


def test_missing_capability_is_a_protocol_error(client):
    """A tool needing sampling refuses a client that never declared it.

    The refusal is a JSON-RPC error naming the capability, not a tool result
    flagged ``isError`` -- the client cannot fix this by retrying.
    """
    tool = "test_missing_capability"

    refused = post_stateless(client, MCP_URL, tool, {"arguments": {}}, capabilities={"elicitation": {}})
    served = call(client, tool, {"arguments": {}}, capabilities={"sampling": {}})

    assert refused["error"]["data"]["requiredCapabilities"] == {"sampling": {}}
    assert text_of(served) == "Client declared sampling capability; proceeding."


def test_a_prompt_can_pause_for_input(client):
    """input_required is not a tools/call privilege: prompts/get pauses too."""
    tool = "test_input_required_result_prompt"
    paused = call(client, tool, {"arguments": {}}, method="prompts/get")

    assert paused["resultType"] == "input_required"
    assert "user_context" in paused["inputRequests"]

    resumed = call(
        client,
        tool,
        {"arguments": {}, "inputResponses": {"user_context": accept({"context": "a bookshop"})}},
        method="prompts/get",
    )

    assert resumed["messages"][0]["content"]["text"] == "Use the following context: a bookshop"
