"""Stateless Model Context Protocol server for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django_stateless_mcp.context import django_request as django_request
from django_stateless_mcp.permissions import (
    PermittedToolsFilter as PermittedToolsFilter,
)
from django_stateless_mcp.security import (
    request_state_security as request_state_security,
)
from django_stateless_mcp.views import mcp_view as mcp_view

if TYPE_CHECKING:
    from django_stateless_mcp.logging import (
        StructlogRequestLogger as StructlogRequestLogger,
    )

__all__ = [
    "PermittedToolsFilter",
    "StructlogRequestLogger",
    "django_request",
    "mcp_view",
    "request_state_security",
]


def __getattr__(name: str) -> type[StructlogRequestLogger]:
    """Import `StructlogRequestLogger` lazily so structlog stays optional.

    structlog ships as the ``django-stateless-mcp[structlog]`` extra; a bare
    install must still import this package. The eager import here would make
    the extra a hard dependency in disguise.
    """
    if name != "StructlogRequestLogger":
        message = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(message)
    from django_stateless_mcp.logging import StructlogRequestLogger

    return StructlogRequestLogger
