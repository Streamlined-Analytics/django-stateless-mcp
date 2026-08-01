"""Django settings for the test suite: the example project plus test overrides.

The tests exercise the same settings, URLs and MCP servers a person can boot
with `just demo`, so the runnable example is itself under test. See ADR-0015.
"""

from __future__ import annotations

from example.settings import *  # noqa: F403

# The transport is stateless and stores nothing, so an in-memory DB is enough.
# A second alias mirrors real consumers' multi-database setups, so the per-alias
# ATOMIC_REQUESTS exemption loop in mcp_view() is exercised for real. See ADR-0032.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "apikeys": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}
