"""Default logger for CLI and scripts."""

from .lazy import LazyLogger
from .settings import OcelogSettings
from .bootstrap import build_logger


def _build_logger():
    """Build the default logger lazily."""
    settings = OcelogSettings.from_env()
    return build_logger(settings, init_trace_id=True)


logger = LazyLogger(_build_logger)
