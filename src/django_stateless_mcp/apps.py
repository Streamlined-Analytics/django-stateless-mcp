"""Django application configuration for django-stateless-mcp."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class DjangoStatelessMCPConfig(AppConfig):
    """Imports each installed app's ``mcp`` module at startup.

    Adding ``django_stateless_mcp`` to ``INSTALLED_APPS`` makes an app's
    ``mcp.py`` the place to register tools, exactly as ``admin.py`` is the
    place to register admin models. Registration itself belongs to the SDK
    (``@server.tool()`` and friends); this only guarantees the module is
    imported. Apps without an ``mcp`` module are skipped, and an ``mcp``
    module that fails to import raises at startup rather than being ignored.
    """

    name = "django_stateless_mcp"
    verbose_name = "Stateless MCP"

    def ready(self) -> None:
        """Import every installed app's ``mcp`` module."""
        autodiscover_modules("mcp")
