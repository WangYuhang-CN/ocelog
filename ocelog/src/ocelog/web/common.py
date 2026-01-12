import importlib


def require_dependency(module_name, display_name):
    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        raise ImportError(
            f"{display_name} support requires '{module_name}'. Install it to use this module."
        ) from exc


def pick_trace_id(headers=None, environ=None):
    if headers:
        trace_id = headers.get("x-trace-id") or headers.get("x-request-id")
        if trace_id:
            return trace_id
    if environ:
        return environ.get("HTTP_X_TRACE_ID") or environ.get("HTTP_X_REQUEST_ID")
    return None
