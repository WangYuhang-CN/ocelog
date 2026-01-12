import json
import tempfile
import time
import types
import asyncio
import importlib
import sys
import contextlib
import io

from ocelog.core import Ocelogger
from ocelog.lazy import LazyLogger
from ocelog.settings import OcelogSettings
from ocelog.context import get_scope, get_trace_id, set_scope, set_trace_id


def _read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_basic_logging_buffer():
    logger = Ocelogger(flush_interval=None)
    logger.info("hello")
    logger.error("world")

    assert len(logger._buffer) == 2
    assert logger._buffer[0]["level"] == "INFO"
    assert logger._buffer[1]["level"] == "ERROR"


def test_flush_file_writer():
    with tempfile.TemporaryDirectory() as tmpdir:
        logfile = f"{tmpdir}/ocelog.jsonl"
        logger = Ocelogger(logfile=logfile, mode="file", flush_interval=None)
        logger.info("hello", user="alice")
        logger.warning("warn")
        logger.flush()

        assert logger._buffer == []
        records = _read_jsonl(logfile)
        assert len(records) == 2
        assert records[0]["message"] == "hello"
        assert records[0]["extra"]["user"] == "alice"
        assert records[1]["level"] == "WARNING"


def test_flush_db_writer():
    seen = {}

    def writer(records):
        seen["records"] = records

    logger = Ocelogger(mode="db", db_writer=writer, flush_interval=None)
    logger.warning("db")
    logger.flush()

    assert len(seen["records"]) == 1
    assert seen["records"][0]["message"] == "db"
    assert logger._buffer == []


def test_exception_formatting():
    logger = Ocelogger(flush_interval=None)
    try:
        raise ValueError("boom")
    except Exception as exc:
        logger.error("fail", exc=exc)

    record = logger._buffer[0]
    assert "exception" in record
    assert "ValueError" in record["exception"]
    assert "exc" not in record.get("extra", {})


def test_writer_mode_errors():
    try:
        Ocelogger(mode="db", flush_interval=None)
        assert False, "expected ValueError for missing db_writer"
    except ValueError as exc:
        assert "db_writer" in str(exc)

    try:
        Ocelogger(mode="nope", flush_interval=None)
        assert False, "expected ValueError for unsupported mode"
    except ValueError as exc:
        assert "unsupported" in str(exc)

    try:
        Ocelogger(mode="db", db_writer=lambda records: None, db_error_mode="nope", flush_interval=None)
        assert False, "expected ValueError for unsupported db_error_mode"
    except ValueError as exc:
        assert "db_error_mode" in str(exc)


def test_context_scope_and_trace_id():
    set_scope("web")
    assert get_scope() == "web"

    trace_id = set_trace_id("trace-1")
    assert trace_id == "trace-1"
    assert get_trace_id() == "trace-1"


def test_lazy_logger_initialization():
    calls = {"count": 0}

    def factory():
        calls["count"] += 1
        return Ocelogger(flush_interval=None)

    logger = LazyLogger(factory)
    assert calls["count"] == 0
    logger.info("one")
    logger.info("two")
    assert calls["count"] == 1


def test_db_writer_error_handling():
    calls = {"errors": 0}

    def writer(_records):
        raise RuntimeError("db down")

    def on_error(_records, _exc):
        calls["errors"] += 1

    logger = Ocelogger(
        mode="db",
        db_writer=writer,
        db_retries=0,
        db_retry_delay=0,
        db_error_mode="stderr",
        db_on_error=on_error,
        flush_interval=None,
    )
    logger.info("fail")
    with contextlib.redirect_stderr(io.StringIO()):
        logger.flush()
    assert calls["errors"] == 1

    logger = Ocelogger(
        mode="db",
        db_writer=writer,
        db_retries=0,
        db_retry_delay=0,
        db_error_mode="raise",
        flush_interval=None,
    )
    logger.info("fail")
    try:
        logger.flush()
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_flusher_restart_and_after_fork():
    import os

    logger = Ocelogger(flush_interval=0.01)
    logger._flusher = None
    logger._flusher_pid = None
    logger._ensure_flusher()
    assert logger._flusher is not None
    logger._after_fork()
    assert logger._pid == os.getpid()
    logger.close()


def test_auto_flush_interval():
    seen = {}

    def writer(records):
        seen["records"] = records

    logger = Ocelogger(mode="db", db_writer=writer, flush_interval=0.01)
    logger.info("tick")

    deadline = time.monotonic() + 0.2
    while "records" not in seen and time.monotonic() < deadline:
        time.sleep(0.005)

    logger.close()
    assert "records" in seen
    assert seen["records"][0]["message"] == "tick"


def test_register_exit_hooks():
    import ocelog.lifecycle as lifecycle

    calls = {"atexit": [], "signals": [], "exited": False}

    def fake_register(func):
        calls["atexit"].append(func)

    def fake_signal(sig, handler):
        calls["signals"].append((sig, handler))

    def fake_exit(code=0):
        calls["exited"] = True
        calls["exit_code"] = code

    class DummyLogger:
        def __init__(self):
            self.flushed = 0
            self.closed = 0

        def flush(self):
            self.flushed += 1

        def close(self):
            self.closed += 1

    orig_atexit = lifecycle.atexit
    orig_signal = lifecycle.signal
    orig_sys = lifecycle.sys
    try:
        lifecycle.atexit = types.SimpleNamespace(register=fake_register)
        lifecycle.signal = types.SimpleNamespace(signal=fake_signal, SIGTERM=15, SIGINT=2)
        lifecycle.sys = types.SimpleNamespace(exit=fake_exit)

        logger = DummyLogger()
        lifecycle.register_exit_hooks(logger, enable_signals=True, enable_atexit=True)

        assert calls["atexit"]
        assert len(calls["signals"]) == 2

        calls["atexit"][0]()
        assert logger.closed == 1

        handler = calls["signals"][0][1]
        handler(calls["signals"][0][0], None)
        assert logger.closed == 2
        assert calls["exited"] is True

        prev_atexit = len(calls["atexit"])
        prev_signals = len(calls["signals"])
        lifecycle.register_exit_hooks(logger, enable_signals=False, enable_atexit=False)
        assert len(calls["atexit"]) == prev_atexit
        assert len(calls["signals"]) == prev_signals
    finally:
        lifecycle.atexit = orig_atexit
        lifecycle.signal = orig_signal
        lifecycle.sys = orig_sys


def test_logger_module_initializes():
    import os

    old = {
        "OCELOG_ENABLE_SIGNALS": os.environ.get("OCELOG_ENABLE_SIGNALS"),
        "OCELOG_ENABLE_ATEXIT": os.environ.get("OCELOG_ENABLE_ATEXIT"),
    }
    try:
        os.environ["OCELOG_ENABLE_SIGNALS"] = "0"
        os.environ["OCELOG_ENABLE_ATEXIT"] = "0"
        from ocelog import logger as logger_instance

        assert logger_instance is not None
        logger_instance.info("ping")
        assert get_trace_id() is not None
        assert isinstance(logger_instance._buffer, list)
    finally:
        for key, val in old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def test_settings_from_env():
    import os

    old = {k: os.environ.get(k) for k in [
        "OCELOG_LOGFILE",
        "OCELOG_MODE",
        "OCELOG_FLUSH_INTERVAL",
        "OCELOG_MAX_BUFFER",
        "OCELOG_DB_RETRIES",
        "OCELOG_DB_RETRY_DELAY",
        "OCELOG_NAME",
        "OCELOG_ENABLE_SIGNALS",
        "OCELOG_ENABLE_ATEXIT",
        "OCELOG_DB_ERROR_MODE",
    ]}
    try:
        os.environ["OCELOG_LOGFILE"] = "test.jsonl"
        os.environ["OCELOG_MODE"] = "file"
        os.environ["OCELOG_FLUSH_INTERVAL"] = "2.5"
        os.environ["OCELOG_MAX_BUFFER"] = "123"
        os.environ["OCELOG_DB_RETRIES"] = "4"
        os.environ["OCELOG_DB_RETRY_DELAY"] = "0.2"
        os.environ["OCELOG_NAME"] = "test"
        os.environ["OCELOG_ENABLE_SIGNALS"] = "0"
        os.environ["OCELOG_ENABLE_ATEXIT"] = "1"
        os.environ["OCELOG_DB_ERROR_MODE"] = "stderr"

        settings = OcelogSettings.from_env()
        assert settings.logfile == "test.jsonl"
        assert settings.mode == "file"
        assert settings.flush_interval == 2.5
        assert settings.max_buffer == 123
        assert settings.db_retries == 4
        assert settings.db_retry_delay == 0.2
        assert settings.name == "test"
        assert settings.enable_signals is False
        assert settings.enable_atexit is True
        assert settings.db_error_mode == "stderr"
    finally:
        for key, val in old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def test_settings_from_env_with_defaults():
    import os

    old = os.environ.get("OCELOG_FLUSH_INTERVAL")
    try:
        os.environ.pop("OCELOG_FLUSH_INTERVAL", None)
        settings = OcelogSettings.from_env_with_defaults(flush_interval=9.0)
        assert settings.flush_interval == 9.0
    finally:
        if old is None:
            os.environ.pop("OCELOG_FLUSH_INTERVAL", None)
        else:
            os.environ["OCELOG_FLUSH_INTERVAL"] = old


def test_settings_strict_env_invalid_value():
    import os

    old = {
        "OCELOG_STRICT_ENV": os.environ.get("OCELOG_STRICT_ENV"),
        "OCELOG_MAX_BUFFER": os.environ.get("OCELOG_MAX_BUFFER"),
    }
    try:
        os.environ["OCELOG_STRICT_ENV"] = "1"
        os.environ["OCELOG_MAX_BUFFER"] = "nope"
        try:
            OcelogSettings.from_env_with_defaults()
            assert False, "expected ValueError for strict env"
        except ValueError:
            pass
    finally:
        for key, val in old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def test_web_common_pick_trace_id_and_dependency_error():
    from ocelog.web.common import pick_trace_id, require_dependency

    headers = {"x-trace-id": "t-1"}
    assert pick_trace_id(headers=headers) == "t-1"
    headers = {"x-request-id": "r-1"}
    assert pick_trace_id(headers=headers) == "r-1"
    assert pick_trace_id(environ={"HTTP_X_TRACE_ID": "t-2"}) == "t-2"
    assert pick_trace_id(environ={"HTTP_X_REQUEST_ID": "r-2"}) == "r-2"

    try:
        require_dependency("ocelog_missing_dep_xyz", "MissingDep")
        assert False, "expected ImportError"
    except ImportError as exc:
        assert "MissingDep support requires" in str(exc)


def test_web_init_and_worker_import():
    import ocelog.lifecycle as lifecycle

    orig_register = lifecycle.register_exit_hooks
    try:
        lifecycle.register_exit_hooks = lambda _logger, **_kwargs: None
        import ocelog.web as web_pkg
        importlib.reload(web_pkg)
        assert web_pkg.logger is not None

        import ocelog.worker as worker_pkg
        importlib.reload(worker_pkg)
        assert worker_pkg.logger is not None
    finally:
        lifecycle.register_exit_hooks = orig_register


def test_web_django_settings_override_and_middleware():
    import ocelog.lifecycle as lifecycle

    orig_register = lifecycle.register_exit_hooks
    django_mod = types.ModuleType("django")
    django_conf = types.ModuleType("django.conf")

    class FakeSettings:
        configured = True
        OCELOG = {
            "name": "dj",
            "logfile": "dj.jsonl",
            "mode": "file",
            "flush_interval": 0.25,
            "max_buffer": 12,
            "db_retries": 1,
            "db_retry_delay": 0.01,
        }
        OCELOG_DB_WRITER = None

    django_conf.settings = FakeSettings()
    sys.modules["django"] = django_mod
    sys.modules["django.conf"] = django_conf
    try:
        lifecycle.register_exit_hooks = lambda _logger, **_kwargs: None
        import ocelog.web.django as web_django
        importlib.reload(web_django)
        logger = web_django.logger
        assert logger._name == "dj"
        assert logger._logfile == "dj.jsonl"
        assert logger._max_buffer == 12

        class Request:
            headers = {"x-trace-id": "dj-trace"}
            META = {"HTTP_X_TRACE_ID": "dj-trace-meta"}

        middleware = web_django.DjangoMiddleware(lambda req: "ok")
        assert middleware(Request()) == "ok"
    finally:
        lifecycle.register_exit_hooks = orig_register
        sys.modules.pop("django", None)
        sys.modules.pop("django.conf", None)


def test_web_flask_and_fastapi_middleware():
    import ocelog.lifecycle as lifecycle

    orig_register = lifecycle.register_exit_hooks
    flask_mod = types.ModuleType("flask")
    flask_mod.g = types.SimpleNamespace()
    flask_mod.request = types.SimpleNamespace(
        headers={"x-request-id": "flask-req"},
        environ={"HTTP_X_REQUEST_ID": "flask-req"},
    )
    sys.modules["flask"] = flask_mod

    fastapi_mod = types.ModuleType("fastapi")
    sys.modules["fastapi"] = fastapi_mod

    try:
        lifecycle.register_exit_hooks = lambda _logger, **_kwargs: None
        import ocelog.web.flask as web_flask
        importlib.reload(web_flask)
        middleware = web_flask.FlaskMiddleware(app=None)
        middleware._before_request()
        response = middleware._after_request("ok")
        assert response == "ok"

        import ocelog.web.fastapi as web_fastapi
        importlib.reload(web_fastapi)

        async def app(scope, receive, send):
            return "ok"

        middleware = web_fastapi.FastAPIMiddleware(app)
        scope = {
            "type": "http",
            "headers": [(b"x-trace-id", b"fa-1")],
        }
        result = asyncio.run(middleware(scope, None, None))
        assert result == "ok"
    finally:
        lifecycle.register_exit_hooks = orig_register
        sys.modules.pop("flask", None)
        sys.modules.pop("fastapi", None)


test_basic_logging_buffer()
test_flush_file_writer()
test_flush_db_writer()
test_exception_formatting()
test_writer_mode_errors()
test_context_scope_and_trace_id()
test_lazy_logger_initialization()
test_db_writer_error_handling()
test_flusher_restart_and_after_fork()
test_auto_flush_interval()
test_register_exit_hooks()
test_logger_module_initializes()
test_settings_from_env()
test_settings_from_env_with_defaults()
test_settings_strict_env_invalid_value()
test_web_common_pick_trace_id_and_dependency_error()
test_web_init_and_worker_import()
test_web_django_settings_override_and_middleware()
test_web_flask_and_fastapi_middleware()
