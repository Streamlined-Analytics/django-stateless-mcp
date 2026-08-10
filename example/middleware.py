"""Response-bracketing middleware modelling the consumers' prometheus stack.

Real consumer projects run ``django-prometheus``, whose Before/After pair sits
first and last in ``MIDDLEWARE`` and processes every response — including the
subscription ``StreamingHttpResponse``. These two classes reproduce that shape
without the dependency, so the suite proves a response-processing
``MiddlewareMixin`` neither breaks nor consumes the MCP responses. See ADR-0032.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import django
from django.http import HttpRequest, HttpResponseBase

if TYPE_CHECKING:
    # django-stubs has yet to carry the 6.2 location. See ADR-0038.
    from django.utils.deprecation import MiddlewareMixin
elif django.VERSION >= (6, 2):
    # Moved in 6.2; the old path warns. Drop this branch at the 6.2 floor. See ADR-0038.
    from django.middleware import MiddlewareMixin
else:
    from django.utils.deprecation import MiddlewareMixin


class BracketBeforeMiddleware(MiddlewareMixin):
    """Outermost middleware, mirroring ``PrometheusBeforeMiddleware``."""

    def process_response(self, request: HttpRequest, response: HttpResponseBase) -> HttpResponseBase:
        response["X-Example-Bracket-Outer"] = "seen"
        return response


class BracketAfterMiddleware(MiddlewareMixin):
    """Innermost middleware, mirroring ``PrometheusAfterMiddleware``."""

    def process_response(self, request: HttpRequest, response: HttpResponseBase) -> HttpResponseBase:
        response["X-Example-Bracket-Inner"] = "seen"
        return response
