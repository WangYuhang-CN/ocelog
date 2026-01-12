import threading


class LazyLogger:
    def __init__(self, factory):
        self._factory = factory
        self._lock = threading.Lock()
        self._logger = None

    def _get_logger(self):
        if self._logger is None:
            with self._lock:
                if self._logger is None:
                    self._logger = self._factory()
        return self._logger

    def __getattr__(self, name):
        return getattr(self._get_logger(), name)

    def __repr__(self):
        return f"<LazyLogger initialized={self._logger is not None}>"
