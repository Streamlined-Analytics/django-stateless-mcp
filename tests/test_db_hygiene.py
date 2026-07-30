"""Worker-thread database-connection hygiene (ADR-0021)."""

from __future__ import annotations

import json
import threading

import pytest
from django.db import close_old_connections
from django.test import AsyncClient

from tests.test_views import MCP_HEADERS, MCP_URL, request_body


async def call_tool(async_client: AsyncClient, name: str) -> str:
    response = await async_client.post(
        MCP_URL,
        data=request_body("tools/call", {"name": name, "arguments": {}}),
        content_type="application/json",
        headers=MCP_HEADERS,
    )
    result = json.loads(response.content)["result"]
    assert result["isError"] is False, result
    return str(result["structuredContent"]["result"])


@pytest.mark.anyio
@pytest.mark.django_db(transaction=True)
async def test_connections_are_recycled_in_the_worker_pool(async_client, monkeypatch):
    """Every request recycles DB connections inside anyio's thread pool.

    The SDK runs sync tools in anyio's worker threads, which Django's
    request_finished cleanup never reaches: a connection opened there was
    never aged out or health-checked. The bridge must run Django's own
    ``close_old_connections`` in that pool after each dispatch. (The
    *closing* itself is unobservable here -- Django deliberately never
    closes in-memory SQLite test connections -- so this pins the wiring:
    the recycle runs, and runs on a pool thread. The example's
    ``db_thread_info`` tool shows the real effect on a file-backed
    database.)
    """
    recycle_threads: list[str] = []

    def recording_close_old_connections() -> None:
        recycle_threads.append(threading.current_thread().name)
        close_old_connections()

    monkeypatch.setattr("django_stateless_mcp.views.close_old_connections", recording_close_old_connections)

    await call_tool(async_client, "count_users")

    assert recycle_threads, "close_old_connections never ran"
    assert all("AnyIO worker" in name for name in recycle_threads), recycle_threads
