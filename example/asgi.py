"""ASGI entrypoint for the example project."""

from __future__ import annotations

import os

from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings")

# Demo-only static serving for the admin; a real deployment uses whitenoise/CDN.
application = ASGIStaticFilesHandler(get_asgi_application())
