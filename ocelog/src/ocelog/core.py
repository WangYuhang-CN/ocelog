"""Core logger implementation and writer backends."""

import threading
import datetime
import json
import os
import sys
import time
import traceback

from .context import get_trace_id


class Ocelogger:  # pylint: disable=too-many-instance-attributes
    """Buffered structured logger with pluggable output writers."""
    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        logfile="ocelog.jsonl",
        name="ocelog",
        mode="file",
        db_writer=None,
        flush_interval=1.0,
        max_buffer=1000,
        db_retries=3,
        db_retry_delay=0.1,
        db_error_mode="silent",
        db_on_error=None,
        settings=None,
    ):
        if settings is not None:
            logfile = settings.logfile
            name = settings.name
            mode = settings.mode
            flush_interval = settings.flush_interval
            max_buffer = settings.max_buffer
            db_retries = settings.db_retries
            db_retry_delay = settings.db_retry_delay
            db_error_mode = settings.db_error_mode
            db_on_error = settings.db_on_error
        self._buffer = []
        self._lock = threading.Lock()
        self._logfile = logfile
        self._name = name
        self._pid = os.getpid()
        self._writer = self._init_writer(
            mode, db_writer, db_retries, db_retry_delay, db_error_mode, db_on_error
        )
        self._max_buffer = max_buffer
        self._flush_interval = flush_interval
        self._stop_event = threading.Event()
        self._flusher = None
        self._flusher_pid = None
        self._closed = False
        if self._flush_interval and self._flush_interval > 0:
            self._start_flusher()
        if hasattr(os, "register_at_fork"):
            try:
                os.register_at_fork(after_in_child=self._after_fork)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def _init_writer(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, mode, db_writer, db_retries, db_retry_delay, db_error_mode, db_on_error
    ):
        """Create the writer backend for the configured mode."""
        if mode == "file":
            return _FileWriter(self._logfile)
        if mode == "db":
            if db_writer is None:
                raise ValueError("db_writer is required when mode='db'")
            if db_error_mode not in ("silent", "raise", "stderr"):
                raise ValueError(f"unsupported db_error_mode: {db_error_mode!r}")
            return _DBWriter(db_writer, db_retries, db_retry_delay, db_error_mode, db_on_error)
        raise ValueError(f"unsupported mode: {mode!r}")

    def _now(self):
        """Return the current UTC timestamp string."""
        return datetime.datetime.utcnow().isoformat(timespec="milliseconds") + "Z"

    def _log(self, level, message, **kwargs):
        """Build a record and append it to the buffer."""
        self._ensure_flusher()
        record = {
            "ts": self._now(),
            "level": level,
            "message": message,
            "logger": self._name,
            "pid": self._pid,
        }

        trace_id = get_trace_id()
        if trace_id:
            record["trace_id"] = trace_id

        if "exc" in kwargs and kwargs["exc"] is not None:
            record["exception"] = "".join(
                traceback.format_exception(
                    type(kwargs["exc"]),
                    kwargs["exc"],
                    kwargs["exc"].__traceback__,
                )
            )
            kwargs.pop("exc")

        if kwargs:
            record["extra"] = kwargs

        with self._lock:
            self._buffer.append(record)
            should_flush = self._max_buffer and len(self._buffer) >= self._max_buffer

        if should_flush:
            self.flush()

    def info(self, message, **kwargs):
        """Log an INFO record."""
        self._log("INFO", message, **kwargs)

    def warning(self, message, **kwargs):
        """Log a WARNING record."""
        self._log("WARNING", message, **kwargs)

    def error(self, message, **kwargs):
        """Log an ERROR record."""
        self._log("ERROR", message, **kwargs)

    def flush(self):
        """Flush buffered records via the writer."""
        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer
            self._buffer = []

        self._writer.write(batch)

    def close(self):
        """Stop background flushing and flush remaining records."""
        self._closed = True
        if self._flusher is not None:
            self._stop_event.set()
            self._flusher.join(timeout=1.0)
        self.flush()

    def _ensure_flusher(self):
        """Ensure the flush thread is running for the current PID."""
        if self._closed:
            return
        if not self._flush_interval or self._flush_interval <= 0:
            return
        current_pid = os.getpid()
        if self._pid != current_pid:
            self._pid = current_pid
        if (
            self._flusher is None
            or not self._flusher.is_alive()
            or self._flusher_pid != current_pid
        ):
            self._start_flusher()

    def _flush_loop(self, interval):
        """Periodically flush on a background thread."""
        while not self._stop_event.wait(interval):
            try:
                self.flush()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def _start_flusher(self):
        """Start the background flush thread."""
        self._stop_event = threading.Event()
        self._flusher = threading.Thread(
            target=self._flush_loop, args=(self._flush_interval,), daemon=True
        )
        self._flusher_pid = os.getpid()
        self._flusher.start()

    def _after_fork(self):
        """Reset state after fork to restart background flushing."""
        self._pid = os.getpid()
        self._flusher = None
        self._flusher_pid = self._pid
        self._stop_event = threading.Event()


class _FileWriter:  # pylint: disable=too-few-public-methods
    """Write records to a JSONL file."""
    def __init__(self, logfile):
        self._logfile = logfile

    def write(self, records):
        """Write a batch of records to disk."""
        dumps = json.dumps
        lines = [dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in records]
        with open(self._logfile, "a", encoding="utf-8") as f:
            f.write("".join(lines))


class _DBWriter:  # pylint: disable=too-few-public-methods
    """Write records using a user-supplied DB writer with retries."""
    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, writer, retries, retry_delay, error_mode, on_error
    ):
        self._writer = writer
        self._retries = retries
        self._retry_delay = retry_delay
        self._error_mode = error_mode
        self._on_error = on_error

    def write(self, records):
        """Write records with retry and error handling."""
        attempts = 0
        last_exc = None
        while True:
            try:
                self._writer(records)
                return
            except Exception as exc:  # pylint: disable=broad-exception-caught
                last_exc = exc
                attempts += 1
                if attempts > self._retries:
                    self._handle_error(records, last_exc)
                    return
                if self._retry_delay:
                    time.sleep(self._retry_delay)

    def _handle_error(self, records, exc):
        """Handle a terminal write error based on configured policy."""
        if self._on_error is not None:
            try:
                self._on_error(records, exc)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        if self._error_mode == "raise":
            raise exc
        if self._error_mode == "stderr":
            detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            sys.stderr.write(detail)
            sys.stderr.flush()
