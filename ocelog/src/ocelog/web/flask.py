"""Flask integration for ocelog."""

try:
    from flask import request, g  # pylint: disable=import-error
except Exception as exc:
    raise ImportError(
        "Flask support requires 'flask'. Install it to use this module."
    ) from exc

from ..context import get_trace_id, set_trace_id
from .common import pick_trace_id
from . import logger as _web_logger

logger = _web_logger


class FlaskMiddleware:  # pylint: disable=too-few-public-methods
    """Attach trace IDs for Flask requests."""
    def __init__(self, app):
        """Register before/after request hooks."""
        self.app = app
        if app is not None:
            app.before_request(self._before_request)
            app.after_request(self._after_request)

    def _before_request(self):
        """Capture previous trace ID and set the request trace ID."""
        g.ocelog_previous_trace_id = get_trace_id()
        trace_id = pick_trace_id(request.headers, environ=request.environ)
        set_trace_id(trace_id)

    def _after_request(self, response):
        """Restore the previous trace ID after the request."""
        previous = getattr(g, "ocelog_previous_trace_id", None)
        set_trace_id(previous)
        return response


__all__ = ["logger", "FlaskMiddleware"]
