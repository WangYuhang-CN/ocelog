"""Settings and environment parsing for ocelog."""

import os


def _parse_bool(value):
    """Parse a boolean from environment-like values."""
    if isinstance(value, bool):
        return value
    if value is None:
        raise ValueError("bool value is None")
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _parse_db_error_mode(value):
    """Parse db error mode from string values."""
    text = str(value).strip().lower()
    if text in ("silent", "raise", "stderr"):
        return text
    raise ValueError(f"invalid db_error_mode: {value!r}")


class OcelogSettings:  # pylint: disable=too-many-instance-attributes
    """Configuration container for ocelog."""
    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        logfile="ocelog.jsonl",
        name="ocelog",
        mode="file",
        flush_interval=1.0,
        max_buffer=1000,
        db_retries=3,
        db_retry_delay=0.1,
        enable_signals=True,
        enable_atexit=True,
        db_error_mode="silent",
        db_on_error=None,
    ):
        self.logfile = logfile
        self.name = name
        self.mode = mode
        self.flush_interval = flush_interval
        self.max_buffer = max_buffer
        self.db_retries = db_retries
        self.db_retry_delay = db_retry_delay
        self.enable_signals = enable_signals
        self.enable_atexit = enable_atexit
        self.db_error_mode = db_error_mode
        self.db_on_error = db_on_error

    @classmethod
    def from_env(cls):
        """Load settings from environment variables."""
        return cls.from_env_with_defaults()

    @classmethod
    def from_env_with_defaults(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        cls,
        logfile="ocelog.jsonl",
        name="ocelog",
        mode="file",
        flush_interval=1.0,
        max_buffer=1000,
        db_retries=3,
        db_retry_delay=0.1,
        enable_signals=True,
        enable_atexit=True,
        db_error_mode="silent",
        strict=False,
    ):
        """Load settings from env, falling back to supplied defaults."""
        strict_env = os.getenv("OCELOG_STRICT_ENV")
        if strict_env is not None and strict_env != "":
            try:
                strict = strict or _parse_bool(strict_env)
            except ValueError:
                if strict:
                    raise
                strict = False

        def _get(name, cast, default):
            val = os.getenv(name)
            if val is None or val == "":
                return default
            try:
                return cast(val)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                if strict:
                    raise ValueError(f"invalid value for {name}: {val!r}") from exc
                return default

        return cls(
            logfile=_get("OCELOG_LOGFILE", str, logfile),
            name=_get("OCELOG_NAME", str, name),
            mode=_get("OCELOG_MODE", str, mode),
            flush_interval=_get("OCELOG_FLUSH_INTERVAL", float, flush_interval),
            max_buffer=_get("OCELOG_MAX_BUFFER", int, max_buffer),
            db_retries=_get("OCELOG_DB_RETRIES", int, db_retries),
            db_retry_delay=_get("OCELOG_DB_RETRY_DELAY", float, db_retry_delay),
            enable_signals=_get("OCELOG_ENABLE_SIGNALS", _parse_bool, enable_signals),
            enable_atexit=_get("OCELOG_ENABLE_ATEXIT", _parse_bool, enable_atexit),
            db_error_mode=_get("OCELOG_DB_ERROR_MODE", _parse_db_error_mode, db_error_mode),
        )
