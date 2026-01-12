"""Helpers for building configured logger instances."""

import os
import uuid

from .core import Ocelogger
from .context import get_trace_id, set_trace_id
from . import lifecycle


def build_logger(settings, db_writer=None, init_trace_id=False):
    """Create a logger and register lifecycle hooks."""
    instance = Ocelogger(settings=settings, db_writer=db_writer)
    if init_trace_id and get_trace_id() is None:
        trace_id = f"ocelog-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        set_trace_id(trace_id)
    lifecycle.register_exit_hooks(
        instance,
        enable_signals=settings.enable_signals,
        enable_atexit=settings.enable_atexit,
    )
    return instance
