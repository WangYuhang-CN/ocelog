from ..context import get_trace_id, set_trace_id
from ..core import Ocelogger
from ..lazy import LazyLogger
from ..lifecycle import register_exit_hooks
from ..settings import OcelogSettings
from .common import pick_trace_id, require_dependency

require_dependency("django", "Django")


def _load_django_settings():
    from django.conf import settings as django_settings

    config = None
    db_writer = None
    if getattr(django_settings, "configured", False):
        config = getattr(django_settings, "OCELOG", None)
        db_writer = getattr(django_settings, "OCELOG_DB_WRITER", None)
    return config, db_writer


def _build_settings():
    settings = OcelogSettings.from_env_with_defaults(
        name="ocelog.web",
        flush_interval=0.5,
        max_buffer=300,
        enable_signals=False,
    )
    config, _ = _load_django_settings()
    if isinstance(config, dict):
        for key, value in config.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
    return settings


def _build_db_writer():
    config, db_writer = _load_django_settings()
    if db_writer is not None:
        return db_writer
    if isinstance(config, dict):
        return config.get("db_writer")
    return None


def _build_logger():
    settings = _build_settings()
    instance = Ocelogger(settings=settings, db_writer=_build_db_writer())
    register_exit_hooks(
        instance,
        enable_signals=settings.enable_signals,
        enable_atexit=settings.enable_atexit,
    )
    return instance


logger = LazyLogger(_build_logger)


class DjangoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        previous = get_trace_id()
        headers = getattr(request, "headers", None)
        environ = getattr(request, "META", None)
        trace_id = pick_trace_id(headers, environ=environ)
        set_trace_id(trace_id)
        try:
            return self.get_response(request)
        finally:
            set_trace_id(previous)


__all__ = ["logger", "DjangoMiddleware"]
