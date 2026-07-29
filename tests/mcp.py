"""Autodiscovered tool registrations for the ``tests`` app.

Nothing imports this module explicitly: it registers ``multiply`` only if
``django_stateless_mcp``'s autodiscovery imported it, which is what the
autodiscovery tests assert.
"""

from __future__ import annotations

from tests.mcp_server import server


@server.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b
