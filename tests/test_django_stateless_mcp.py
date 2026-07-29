"""Tests for `django_stateless_mcp` package."""

from __future__ import annotations

import django
from django.apps import apps

import django_stateless_mcp


def test_import():
    """The package imports under its distribution name."""
    assert django_stateless_mcp.__name__ == "django_stateless_mcp"


def test_installed_as_django_app():
    """The package loads as an installed app under the version being tested."""
    assert apps.is_installed("django_stateless_mcp")


def test_supported_django_version():
    """The Django under test is one this package claims to support."""
    assert django.VERSION[:2] >= (5, 2)
