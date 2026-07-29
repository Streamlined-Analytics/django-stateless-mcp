#!/bin/bash
# Boot the test-fixture server and run the MCP conformance harness. See ADR-0008.
set -e

PORT="${PORT:-8731}"
SERVER_URL="http://127.0.0.1:${PORT}/mcp/"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# A stale listener would mean silently testing old code, so refuse to start.
if (: > "/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null; then
    echo "Error: port ${PORT} is already in use." >&2
    exit 1
fi

echo "Starting Django fixture server on port ${PORT}..."
DJANGO_SETTINGS_MODULE=example.settings PYTHONPATH=. \
    uv run python -m django runserver "127.0.0.1:${PORT}" --noreload &
SERVER_PID=$!

cleanup() {
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "Waiting for server readiness..."
MAX_RETRIES=30
RETRY_COUNT=0
until curl -s --max-time 2 -o /dev/null -X POST "$SERVER_URL" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":0,"method":"ping"}'; do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "Server process exited unexpectedly" >&2
        exit 1
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        echo "Server failed to start after ${MAX_RETRIES} retries" >&2
        exit 1
    fi
    sleep 0.5
done

echo "Server ready at ${SERVER_URL}"

npx --yes "${CONFORMANCE_PKG:?set CONFORMANCE_PKG (pinned in .github/workflows/conformance.yml)}" \
    server --url "$SERVER_URL" "$@"
