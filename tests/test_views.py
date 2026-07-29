"""Tests for the stateless MCP view."""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

MCP_URL = "/mcp/"
MCP_HEADERS = {"accept": "application/json, text/event-stream"}


@pytest.fixture
def anyio_backend():
    """Run async tests on asyncio only; the SDK targets it."""
    return "asyncio"


def request_body(method: str, params: dict[str, Any] | None = None, request_id: int = 1) -> str:
    """Build a JSON-RPC request body for the given MCP method."""
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return json.dumps(payload)


def post(client: Client, method: str, params: dict[str, Any] | None = None) -> Any:
    return client.post(
        MCP_URL,
        data=request_body(method, params),
        content_type="application/json",
        headers=MCP_HEADERS,
    )


def test_tools_list_returns_registered_tool(client):
    """The endpoint advertises tools without an initialize handshake."""
    response = post(client, "tools/list")

    assert response.status_code == 200
    tools = json.loads(response.content)["result"]["tools"]
    assert "add" in {tool["name"] for tool in tools}


def test_tools_call_executes_the_tool(client):
    """A tool call runs and returns its structured result."""
    response = post(client, "tools/call", {"name": "add", "arguments": {"a": 2, "b": 3}})

    assert response.status_code == 200
    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": 5}
    assert result["isError"] is False


def test_response_carries_no_session_identifier(client):
    """No session is established, so nothing needs sticky routing.

    This is the property the package exists to provide: if a session header
    ever appears here, horizontal scaling is silently broken.
    """
    response = post(client, "tools/list")

    assert "Mcp-Session-Id" not in response.headers


def test_unknown_tool_reports_an_error(client):
    """An unknown tool is reported in-band rather than crashing the view."""
    response = post(client, "tools/call", {"name": "nope", "arguments": {}})

    assert response.status_code == 200
    payload = json.loads(response.content)
    assert "error" in payload or payload["result"]["isError"] is True


@pytest.mark.anyio
async def test_tools_call_under_asgi(async_client):
    """The same view serves ASGI, where it runs without a wrapping event loop."""
    response = await async_client.post(
        MCP_URL,
        data=request_body("tools/call", {"name": "add", "arguments": {"a": 7, "b": 5}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    assert response.status_code == 200
    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": 12}


@pytest.mark.anyio
async def test_consecutive_requests_share_no_state(async_client):
    """Two requests are served independently, as separate workers would."""
    first = await async_client.post(
        MCP_URL,
        data=request_body("tools/call", {"name": "add", "arguments": {"a": 1, "b": 1}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )
    second = await async_client.post(
        MCP_URL,
        data=request_body("tools/list", request_id=2),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    assert json.loads(first.content)["result"]["structuredContent"] == {"result": 2}
    assert json.loads(second.content)["result"]["tools"][0]["name"] == "add"


def test_autodiscovery_imported_the_app_mcp_module(client):
    """Tools registered in an app's mcp.py are served without explicit import.

    Nothing in the test suite or URLconf imports tests.mcp, so multiply can
    only be present if the app config's autodiscovery imported it.
    """
    response = post(client, "tools/list")

    tools = {tool["name"] for tool in json.loads(response.content)["result"]["tools"]}
    assert tools == {"add", "multiply"}


def test_autodiscovered_tool_is_callable(client):
    """An autodiscovered tool executes like any directly registered one."""
    response = post(client, "tools/call", {"name": "multiply", "arguments": {"a": 6, "b": 7}})

    result = json.loads(response.content)["result"]
    assert result["structuredContent"] == {"result": 42}
