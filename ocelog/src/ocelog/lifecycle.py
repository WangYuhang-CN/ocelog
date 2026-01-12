"""Process lifecycle hooks for flushing logs."""

import atexit
import signal
import sys

def register_exit_hooks(logger, enable_signals=True, enable_atexit=True):
    """Register process-exit hooks for a logger."""
    def _cleanup():
        try:
            if hasattr(logger, "close"):
                logger.close()
            else:
                logger.flush()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _handle_signal(_signum, _frame):
        _cleanup()
        sys.exit(0)

    if enable_atexit:
        atexit.register(_cleanup)

    if enable_signals:
        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)
