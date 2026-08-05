"""Settings for the runnable example project.

This is a real, launchable Django project (`just demo` / `just demo-asgi`)
that doubles as the base fixture for the package's test suite —
``tests.settings`` inherits everything here and overrides the database.
See ADR-0015.
"""

from __future__ import annotations

from pathlib import Path

import django_stubs_ext

# Lets the example's admin classes be parameterized (ModelAdmin[Author]) at runtime.
django_stubs_ext.monkeypatch()

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
    # Admin (and the staticfiles/TEMPLATES it needs) exists so the reader can
    # toggle the demo user's permission through a GUI. See ADR-0033.
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_stateless_mcp",
    # An installed app with an mcp.py, so autodiscovery has something to find.
    "example",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

STATIC_URL = "static/"

# The full stack real consumer projects carry (ADR-0018), bracketed first-and-last
# by prometheus-shaped response middleware the way the consumers run it. See ADR-0032.
MIDDLEWARE = [
    "example.middleware.BracketBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "example.middleware.BracketAfterMiddleware",
]

USE_TZ = True

TIME_ZONE = "UTC"
