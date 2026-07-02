"""Global conversation/workflow cancellation.

Public API (import-friendly):

`from common_adapters.cancel_convesation import cancel_conversation`
"""

from .api import (
    CancelledError,
    SessionTerminatedError,
    CancellationToken,
    cancel_conversation,
    is_cancelled,
    is_session_terminated,
    register_cancellation,
    register_task,
    raise_if_session_terminated,
    terminate_session,
    unregister_cancellation,
    unregister_task,
)

__all__ = [
    "CancelledError",
    "SessionTerminatedError",
    "CancellationToken",
    "cancel_conversation",
    "is_cancelled",
    "terminate_session",
    "is_session_terminated",
    "raise_if_session_terminated",
    "register_cancellation",
    "register_task",
    "unregister_cancellation",
    "unregister_task",
]
