"""Request-state security keyed from Django settings."""

from __future__ import annotations

from django.conf import settings
from mcp.server.mcpserver import RequestStateSecurity

__all__ = ["request_state_security"]


def request_state_security(*, ttl: float = 600.0) -> RequestStateSecurity:
    """Build the SDK's ``RequestStateSecurity`` from ``SECRET_KEY``.

    Elicitation resumes by echoing an encrypted ``requestState`` back to the
    server, and the SDK's default encryption key is random **per process** —
    so with defaults, a retry landing on a different worker cannot decrypt
    it, which is the multi-worker failure this package exists to remove.
    Keying from settings makes resume state portable across every worker and
    instance that shares the Django configuration::

        server = MCPServer(
            name="my-server",
            request_state_security=request_state_security(),
        )

    ``SECRET_KEY_FALLBACKS`` are included, so Django's standard key-rotation
    story covers in-flight elicitations too: state issued under the old key
    still resumes while the fallback remains configured.

    ``ttl`` bounds how long issued state stays resumable, in seconds. The SDK
    requires keys of at least 32 bytes; Django's generated ``SECRET_KEY`` is
    longer, but a hand-shortened key raises the SDK's error at startup.
    """
    keys: list[str] = [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
    return RequestStateSecurity(keys=keys, ttl=ttl)
