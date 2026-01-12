"""Django integration for ocelog."""

try:
    from django.conf import settings as django_settings  # pylint: disable=import-error
except Exception as exc:
    raise ImportError(
        "Django support requires 'django'. Install it to use this module."
    ) from exc

from ..context import get_trace_id, set_trace_id
from ..lazy import LazyLogger
from ..bootstrap import build_logger
from .common import pick_trace_id, build_web_settings


def _load_django_settings():
    """Load Django settings overrides if configured."""
    config = None
    db_writer = None
    if getattr(django_settings, "configured", False):
        config = getattr(django_settings, "OCELOG", None)
        db_writer = getattr(django_settings, "OCELOG_DB_WRITER", None)
    return config, db_writer


def _build_settings():
    """Build settings with Django overrides."""
    config, _ = _load_django_settings()
    overrides = config if isinstance(config, dict) else None
    return build_web_settings(overrides=overrides)


def _build_db_writer():
    """Resolve a DB writer from Django settings."""
    config, db_writer = _load_django_settings()
    if db_writer is not None:
        return db_writer
    if isinstance(config, dict):
        return config.get("db_writer")
    return None


def _build_logger():
    """Build the Django logger instance."""
    settings = _build_settings()
    return build_logger(settings, db_writer=_build_db_writer())


logger = LazyLogger(_build_logger)


class DjangoMiddleware:  # pylint: disable=too-few-public-methods
    """Attach trace IDs from Django requests."""
    def __init__(self, get_response):
        """Store the Django response handler."""
        self.get_response = get_response

    def __call__(self, request):
        """Wrap a Django request to set the trace ID."""
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
