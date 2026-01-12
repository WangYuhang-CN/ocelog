"""Shared helpers for web integrations."""

import importlib

from ..settings import OcelogSettings


def require_dependency(module_name, display_name):
    """Import a dependency or raise a clear error."""
    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        raise ImportError(
            f"{display_name} support requires '{module_name}'. Install it to use this module."
        ) from exc


def build_web_settings(overrides=None):
    """Build web-default settings with optional overrides."""
    settings = OcelogSettings.from_env_with_defaults(
        name="ocelog.web",
        flush_interval=0.5,
        max_buffer=300,
        enable_signals=False,
    )
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
    return settings


def pick_trace_id(headers=None, environ=None):
    """Extract trace/request ID from headers or WSGI environ."""
    if headers:
        trace_id = headers.get("x-trace-id") or headers.get("x-request-id")
        if trace_id:
            return trace_id
    if environ:
        return environ.get("HTTP_X_TRACE_ID") or environ.get("HTTP_X_REQUEST_ID")
    return None
