"""Lazy logger proxy to defer initialization."""

import threading


class LazyLogger:
    """Proxy that builds the logger on first use."""
    def __init__(self, factory):
        self._factory = factory
        self._lock = threading.Lock()
        self._logger = None

    def _get_logger(self):
        """Create the logger instance on first access."""
        if self._logger is None:
            with self._lock:
                if self._logger is None:
                    self._logger = self._factory()
        return self._logger

    def __getattr__(self, name):
        """Proxy attribute access to the real logger."""
        return getattr(self._get_logger(), name)

    def __repr__(self):
        return f"<LazyLogger initialized={self._logger is not None}>"
