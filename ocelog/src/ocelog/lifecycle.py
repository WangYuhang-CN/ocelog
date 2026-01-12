import atexit
import signal
import sys

def register_exit_hooks(logger, enable_signals=True, enable_atexit=True):
    def _cleanup():
        try:
            if hasattr(logger, "close"):
                logger.close()
            else:
                logger.flush()
        except Exception:
            pass

    def _handle_signal(signum, frame):
        _cleanup()
        sys.exit(0)

    if enable_atexit:
        atexit.register(_cleanup)

    if enable_signals:
        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)
