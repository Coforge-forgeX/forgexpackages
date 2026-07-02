"""Global conversation/workflow cancellation.

Public API (import-friendly):

`from common_adapters.cancel_convesation import cancel_conversation`
"""
from . import api as _api

CancelledError = _api.CancelledError
SessionTerminatedError = getattr(_api, "SessionTerminatedError", RuntimeError)
CancellationToken = _api.CancellationToken
cancel_conversation = _api.cancel_conversation
is_cancelled = _api.is_cancelled
is_session_terminated = getattr(_api, "is_session_terminated", lambda **_: False)
register_cancellation = _api.register_cancellation
raise_if_session_terminated = getattr(_api, "raise_if_session_terminated", lambda **_: None)
terminate_session = getattr(_api, "terminate_session", lambda **_: {"status": "unsupported"})
unregister_cancellation = _api.unregister_cancellation
register_task = getattr(_api, "register_task", lambda **_: None)
unregister_task = getattr(_api, "unregister_task", lambda **_: None)


def clear_cancellation(*, job_id=None, conversation_id=None):
    """Backward-compatible cancellation clear shim.

    Newer adapters provide ``api.clear_cancellation``; older ones may not.
    Keep import contract stable for downstream agents.
    """
    fn = getattr(_api, "clear_cancellation", None)
    if callable(fn):
        return fn(job_id=job_id, conversation_id=conversation_id)
    return None

__all__ = [
    "CancelledError",
    "SessionTerminatedError",
    "CancellationToken",
    "cancel_conversation",
    "clear_cancellation",
    "is_cancelled",
    "terminate_session",
    "is_session_terminated",
    "raise_if_session_terminated",
    "register_cancellation",
    "register_task",
    "unregister_cancellation",
    "unregister_task",
]
