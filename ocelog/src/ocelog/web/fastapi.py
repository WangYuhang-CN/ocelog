"""FastAPI integration for ocelog."""

from ..context import get_trace_id, set_trace_id
from .common import pick_trace_id, require_dependency
from . import logger as _web_logger

require_dependency("fastapi", "FastAPI")

logger = _web_logger


class FastAPIMiddleware:  # pylint: disable=too-few-public-methods
    """Attach trace IDs for FastAPI requests."""
    def __init__(self, app):
        """Store the ASGI app."""
        self.app = app

    async def __call__(self, scope, receive, send):
        """ASGI middleware entry point."""
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        previous = get_trace_id()
        trace_id = pick_trace_id(headers)
        set_trace_id(trace_id)
        try:
            return await self.app(scope, receive, send)
        finally:
            set_trace_id(previous)


__all__ = ["logger", "FastAPIMiddleware"]
