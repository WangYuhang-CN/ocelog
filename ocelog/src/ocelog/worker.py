"""Worker/job logger with throughput-oriented defaults."""

from .lazy import LazyLogger
from .settings import OcelogSettings
from .bootstrap import build_logger


def _build_logger():
    """Build the worker logger lazily."""
    settings = OcelogSettings.from_env_with_defaults(
        name="ocelog.worker",
        flush_interval=2.0,
        max_buffer=5000,
        db_retries=5,
        db_retry_delay=0.2,
    )
    return build_logger(settings)


logger = LazyLogger(_build_logger)
