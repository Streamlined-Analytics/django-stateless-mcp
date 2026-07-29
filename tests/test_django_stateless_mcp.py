"""Tests for `django_stateless_mcp` package."""

from __future__ import annotations

import subprocess
import sys
import textwrap

import django
import pytest
from django.apps import apps

import django_stateless_mcp


def _run_without_structlog(code: str) -> None:
    """Run a snippet in a subprocess where importing structlog fails.

    A `None` entry in `sys.modules` makes `import structlog` raise
    ImportError, simulating a bare install without the [structlog] extra.
    """
    blocker = 'import sys\nsys.modules["structlog"] = None\n'
    subprocess.run([sys.executable, "-c", blocker + textwrap.dedent(code)], check=True)


def test_import():
    """The package imports under its distribution name."""
    assert django_stateless_mcp.__name__ == "django_stateless_mcp"


def test_installed_as_django_app():
    """The package loads as an installed app under the version being tested."""
    assert apps.is_installed("django_stateless_mcp")


def test_supported_django_version():
    """The Django under test is one this package claims to support."""
    assert django.VERSION[:2] >= (5, 2)


def test_bare_install_imports_without_structlog():
    """A bare install, without the [structlog] extra, must import cleanly.

    0.1.0 eagerly imported the optional structlog dependency from
    `__init__`, so `pip install django-stateless-mcp` produced a package
    that could not be imported at all.
    """
    _run_without_structlog("import django_stateless_mcp")


def test_structlog_logger_without_structlog_raises_helpful_error():
    """Reaching the logger without structlog names the extra to install."""
    _run_without_structlog(
        """
        import django_stateless_mcp

        try:
            django_stateless_mcp.StructlogRequestLogger
        except ImportError as error:
            assert "django-stateless-mcp[structlog]" in str(error), str(error)
        else:
            raise AssertionError("expected ImportError without structlog")
        """
    )


def test_structlog_logger_resolves_lazily():
    """With structlog installed, the lazy attribute is the real class."""
    from django_stateless_mcp.logging import StructlogRequestLogger

    assert django_stateless_mcp.StructlogRequestLogger is StructlogRequestLogger


def test_unknown_attribute_still_raises():
    """The lazy hook must not swallow genuine attribute errors."""
    with pytest.raises(AttributeError, match="does_not_exist"):
        _ = django_stateless_mcp.does_not_exist
