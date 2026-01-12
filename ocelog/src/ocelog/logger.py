import os
import uuid

from .core import Ocelogger
from .lazy import LazyLogger
from .settings import OcelogSettings
from .lifecycle import register_exit_hooks
from .context import set_trace_id, get_trace_id


def _build_logger():
    settings = OcelogSettings.from_env()
    instance = Ocelogger(settings=settings)
    if get_trace_id() is None:
        trace_id = f"ocelog-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        set_trace_id(trace_id)
    register_exit_hooks(
        instance,
        enable_signals=settings.enable_signals,
        enable_atexit=settings.enable_atexit,
    )
    return instance


logger = LazyLogger(_build_logger)
