"""WSGI entrypoint for the example project."""

from __future__ import annotations

import os

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings")

# Demo-only static serving for the admin; a real deployment uses whitenoise/CDN.
application = StaticFilesHandler(get_wsgi_application())
