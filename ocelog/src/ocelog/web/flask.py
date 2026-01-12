from ..context import get_trace_id, set_trace_id
from ..core import Ocelogger
from ..lazy import LazyLogger
from ..lifecycle import register_exit_hooks
from ..settings import OcelogSettings
from .common import pick_trace_id, require_dependency

require_dependency("flask", "Flask")


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


class FlaskMiddleware:
    def __init__(self, app):
        self.app = app
        if app is not None:
            app.before_request(self._before_request)
            app.after_request(self._after_request)

    def _before_request(self):
        from flask import request, g

        g._ocelog_previous_trace_id = get_trace_id()
        trace_id = pick_trace_id(request.headers, environ=request.environ)
        set_trace_id(trace_id)

    def _after_request(self, response):
        from flask import g

        previous = getattr(g, "_ocelog_previous_trace_id", None)
        set_trace_id(previous)
        return response


__all__ = ["logger", "FlaskMiddleware"]
