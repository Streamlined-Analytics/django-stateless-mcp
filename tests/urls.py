"""URLconf fixture for the test suite.

The MCP endpoint mounts here once the view exists. Kept deliberately empty
rather than stubbed, so nothing here can be mistaken for package API.
"""

from __future__ import annotations

from django.urls import URLPattern, URLResolver

urlpatterns: list[URLPattern | URLResolver] = []
