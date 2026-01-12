"""Web defaults logger entrypoint."""

from ..lazy import LazyLogger
from ..bootstrap import build_logger
from .common import build_web_settings


def _build_logger():
    """Build the web-default logger lazily."""
    settings = build_web_settings()
    return build_logger(settings)


logger = LazyLogger(_build_logger)

__all__ = ["logger"]
