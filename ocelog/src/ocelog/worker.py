from .core import Ocelogger
from .lazy import LazyLogger
from .lifecycle import register_exit_hooks
from .settings import OcelogSettings


def _build_logger():
    settings = OcelogSettings.from_env_with_defaults(
        name="ocelog.worker",
        flush_interval=2.0,
        max_buffer=5000,
        db_retries=5,
        db_retry_delay=0.2,
    )
    instance = Ocelogger(settings=settings)
    register_exit_hooks(
        instance,
        enable_signals=settings.enable_signals,
        enable_atexit=settings.enable_atexit,
    )
    return instance


logger = LazyLogger(_build_logger)
