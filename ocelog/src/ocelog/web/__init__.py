from ..core import Ocelogger
from ..lazy import LazyLogger
from ..lifecycle import register_exit_hooks
from ..settings import OcelogSettings


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

__all__ = ["logger"]
