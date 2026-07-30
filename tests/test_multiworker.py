"""Out-of-process multi-worker proof of the horizontal-scaling claim.

The in-process flagship tests (test_views) drive two ``MCPServer`` instances,
but both live in one interpreter, so module-level state would be shared and
invisible to them. These tests boot the example project as a **real server
fleet in a separate OS process** — uvicorn under ASGI, gunicorn under WSGI,
four workers each — and prove the claim no in-process test can: an
elicitation issued by one fleet resumes on a brand-new fleet whose processes
did not exist when the flow began. See ADR-0019.

Deliberately excluded from the default run (they bind a port and spawn
processes); enable with ``MULTIWORKER=1`` — locally via ``just multiworker``,
and in CI as a dedicated job.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("MULTIWORKER") != "1",
    reason="Out-of-process fleet tests run only with MULTIWORKER=1 (just multiworker).",
)

WORKER_COUNT = 4
STARTUP_DEADLINE_SECONDS = 30.0
SHUTDOWN_DEADLINE_SECONDS = 10.0
DISTINCT_PID_ATTEMPTS = 100

SEP_2322_META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {"elicitation": {}},
}

SERVER_COMMANDS = {
    "asgi-uvicorn": lambda port: [
        sys.executable,
        "-m",
        "uvicorn",
        "example.asgi:application",
        "--workers",
        str(WORKER_COUNT),
        "--port",
        str(port),
        "--log-level",
        "warning",
    ],
    "wsgi-gunicorn": lambda port: [
        sys.executable,
        "-m",
        "gunicorn",
        "example.wsgi:application",
        "--workers",
        str(WORKER_COUNT),
        "--bind",
        f"127.0.0.1:{port}",
        "--log-level",
        "warning",
    ],
}


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class Fleet:
    """A live multi-worker server fleet run as a separate OS process group."""

    def __init__(self, server_id: str, port: int) -> None:
        self._command = SERVER_COMMANDS[server_id](port)
        self.url = f"http://127.0.0.1:{port}/mcp/"
        self._process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        """Boot the fleet and wait until a tool call is served."""
        # A new session makes the master and its workers one killable group.
        self._process = subprocess.Popen(self._command, start_new_session=True)
        deadline = time.monotonic() + STARTUP_DEADLINE_SECONDS
        while time.monotonic() < deadline:
            try:
                self.call_tool("add", {"a": 1, "b": 1})
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                time.sleep(0.25)
                continue
            return
        raise RuntimeError(f"Fleet did not serve within {STARTUP_DEADLINE_SECONDS}s: {self._command}")

    def stop(self) -> None:
        """Kill the whole process group and wait for the port to free up."""
        if self._process is None:
            return
        os.killpg(self._process.pid, signal.SIGTERM)
        try:
            self._process.wait(timeout=SHUTDOWN_DEADLINE_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(self._process.pid, signal.SIGKILL)
            self._process.wait(timeout=SHUTDOWN_DEADLINE_SECONDS)
        self._process = None

    def post(self, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
        """POST one JSON-RPC request on a fresh connection; return the parsed body."""
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **(headers or {}),
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())  # type: ignore[no-any-return]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        body = self.post(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
        )
        result = body["result"]
        return result  # type: ignore[no-any-return]

    def worker_pids(self, *, want_distinct: int) -> set[int]:
        """Collect serving pids over fresh connections until enough are seen."""
        pids: set[int] = set()
        for _ in range(DISTINCT_PID_ATTEMPTS):
            result = self.call_tool("worker_pid", {})
            pids.add(int(result["structuredContent"]["result"]))
            if len(pids) >= want_distinct:
                break
        return pids


def _sep_2322_headers() -> dict[str, str]:
    return {
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": "tools/call",
        "mcp-name": "test_input_required_result_request_state",
    }


def _start_elicitation(fleet: Fleet) -> str:
    """Begin the stateless input flow; return the encrypted requestState."""
    body = fleet.post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "test_input_required_result_request_state",
                "arguments": {},
                "_meta": SEP_2322_META,
            },
        },
        headers=_sep_2322_headers(),
    )
    result = body["result"]
    assert result["resultType"] == "input_required"
    return str(result["requestState"])


def _resume_elicitation(fleet: Fleet, request_state: str) -> dict[str, Any]:
    body = fleet.post(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "test_input_required_result_request_state",
                "arguments": {},
                "inputResponses": {"confirm": {"action": "accept", "content": {"ok": True}}},
                "requestState": request_state,
                "_meta": SEP_2322_META,
            },
        },
        headers=_sep_2322_headers(),
    )
    result: dict[str, Any] = body["result"]
    return result


@pytest.fixture(params=sorted(SERVER_COMMANDS))
def fleet(request):
    """A running multi-worker fleet, torn down after the test."""
    live_fleet = Fleet(request.param, _free_port())
    live_fleet.start()
    yield live_fleet
    live_fleet.stop()


def test_multiple_workers_serve(fleet):
    """Successive fresh connections are answered by different OS processes."""
    pids = fleet.worker_pids(want_distinct=2)

    assert len(pids) >= 2, f"only one worker ever answered: {pids}"


def test_elicitation_resumes_on_a_replacement_fleet(fleet):
    """The whole thesis: kill every process mid-flow, resume on new ones.

    The elicitation's only artifact is the encrypted requestState held by
    the client. The fleet that issued it is killed outright; a brand-new
    fleet — provably disjoint pids — decrypts and completes the flow,
    because request_state_security() keys from SECRET_KEY, not from
    anything a process held.
    """
    pids_before = fleet.worker_pids(want_distinct=2)
    request_state = _start_elicitation(fleet)

    fleet.stop()
    fleet.start()

    pids_after = fleet.worker_pids(want_distinct=2)
    assert pids_before.isdisjoint(pids_after), "replacement fleet reused a pid"

    result = _resume_elicitation(fleet, request_state)
    assert result["resultType"] == "complete"
    assert result["structuredContent"]["result"] == "state-ok: confirmation received"
