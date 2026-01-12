from ..context import get_trace_id, set_trace_id
from ..core import Ocelogger
from ..lazy import LazyLogger
from ..lifecycle import register_exit_hooks
from ..settings import OcelogSettings
from .common import pick_trace_id, require_dependency

require_dependency("fastapi", "FastAPI")


def _build_logger():
    settings = OcelogSettings.from_env_with_defaults(
        name="ocelog.web",
        flush_interval=0.5,
        max_buffer=300,
        enable_signals=False,
    )
    instance = Ocelogger(settings=settings)
    register_exit_hooks(
        instance,
        enable_signals=settings.enable_signals,
        enable_atexit=settings.enable_atexit,
    )
    return instance


logger = LazyLogger(_build_logger)


class FastAPIMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
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
