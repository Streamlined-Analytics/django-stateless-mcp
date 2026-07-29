"""Minimal Django settings for the package's own test suite.

This is a test fixture, not an example project: the tests assert on
``django_stateless_mcp``, not on anything defined here.
"""

from __future__ import annotations

SECRET_KEY = "NOTASECRET"

ALLOWED_HOSTS = ["testserver"]

# The transport is stateless and stores nothing, so an in-memory DB is enough.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

ROOT_URLCONF = "tests.urls"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_stateless_mcp",
]

USE_TZ = True

TIME_ZONE = "UTC"
