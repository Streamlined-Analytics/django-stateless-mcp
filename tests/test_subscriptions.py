"""Tests for the subscriptions/listen streaming path (ADR-0020)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from mcp.server.subscriptions import ToolsListChanged

from example.mcp_server import subscription_bus
from tests.test_views import MCP_HEADERS, MCP_URL

LISTEN_HEADERS = {
    **MCP_HEADERS,
    "mcp-protocol-version": "2026-07-28",
    "mcp-method": "subscriptions/listen",
}

FRAME_TIMEOUT_SECONDS = 5


def listen_body(request_id: int = 7) -> str:
    """A subscriptions/listen request asking only for tool-list changes."""
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "subscriptions/listen",
            "params": {
                "notifications": {"toolsListChanged": True},
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                },
            },
        }
    )


class SSEFrameReader:
    """Accumulates streamed chunks and yields parsed SSE data payloads."""

    def __init__(self, stream: AsyncIterator[bytes]) -> None:
        self._stream = stream
        self._buffer = b""
        self._frames: list[dict[str, Any]] = []

    async def next_frame(self) -> dict[str, Any]:
        """Return the next JSON payload carried by a ``data:`` SSE frame."""
        while not self._frames:
            chunk = await asyncio.wait_for(anext(self._stream), FRAME_TIMEOUT_SECONDS)
            # SSE frames arrive with CRLF line endings; normalise once.
            self._buffer += chunk.replace(b"\r\n", b"\n")
            while b"\n\n" in self._buffer:
                raw_frame, self._buffer = self._buffer.split(b"\n\n", 1)
                for line in raw_frame.splitlines():
                    if line.startswith(b"data:"):
                        self._frames.append(json.loads(line[5:].strip()))
        return self._frames.pop(0)


@pytest.mark.anyio
async def test_listen_streams_ack_then_filtered_events(async_client):
    """The listen response is a live SSE stream: ack first, then events.

    The ack must be the first frame and every frame must carry the listen
    request's id as its subscription id; an event published mid-stream
    arrives as a filtered notification frame.
    """
    response = await async_client.post(
        MCP_URL, data=listen_body(request_id=7), content_type="application/json", headers=LISTEN_HEADERS
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")

    stream = aiter(response.streaming_content)
    reader = SSEFrameReader(stream)
    try:
        ack = await reader.next_frame()
        assert ack["method"] == "notifications/subscriptions/acknowledged"
        assert ack["params"]["_meta"]["io.modelcontextprotocol/subscriptionId"] == 7

        await subscription_bus.publish(ToolsListChanged())

        event = await reader.next_frame()
        assert event["method"] == "notifications/tools/list_changed"
        assert event["params"]["_meta"]["io.modelcontextprotocol/subscriptionId"] == 7
    finally:
        await stream.aclose()


def test_listen_under_wsgi_is_refused(client):
    """A WSGI deployment cannot hold a live stream, and says so.

    A pinned worker per subscription is the per-flow resource tax the
    package exists to remove; the refusal is explicit rather than a hang.
    """
    response = client.post(MCP_URL, data=listen_body(), content_type="application/json", headers=LISTEN_HEADERS)

    assert response.status_code == 501
    assert json.loads(response.content)["error"] == "unsupported_deployment"


def test_trigger_tool_publishes_without_a_stream(client):
    """The example's trigger tool runs cleanly with no stream open."""
    response = client.post(
        MCP_URL,
        data=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "test_trigger_tool_change", "arguments": {}},
            }
        ),
        content_type="application/json",
        headers=MCP_HEADERS,
    )

    result = json.loads(response.content)["result"]
    assert result["isError"] is False
