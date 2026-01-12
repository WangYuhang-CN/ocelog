import uuid
from contextvars import ContextVar

_scope: ContextVar[str] = ContextVar("scope", default="cli")
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_trace_id(trace_id: str | None = None) -> str:
    if trace_id is None:
        trace_id = uuid.uuid4().hex
    _trace_id.set(trace_id)
    return trace_id


def get_trace_id() -> str | None:
    return _trace_id.get()


def set_scope(scope: str):
    _scope.set(scope)

def get_scope() -> str:
    return _scope.get()
