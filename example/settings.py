"""Settings for the runnable example project.

This is a real, launchable Django project (`just demo` / `just demo-asgi`)
that doubles as the base fixture for the package's test suite —
``tests.settings`` inherits everything here and overrides the database.
See ADR-0015.
"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Deliberately published: the demo depends on every worker sharing this key,
# which is exactly the property request_state_security() exists to exploit.
SECRET_KEY = "django-insecure-NOTASECRET-test-only-0123456789abcdef"

SECRET_KEY_FALLBACKS = ["django-insecure-NOTASECRET-previous-0123456789abcd"]

DEBUG = True

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}

ROOT_URLCONF = "example.urls"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_stateless_mcp",
    # An installed app with an mcp.py, so autodiscovery has something to find.
    "example",
]

USE_TZ = True

TIME_ZONE = "UTC"
