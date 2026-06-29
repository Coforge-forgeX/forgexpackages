"""Global conversation/workflow cancellation.

Public API (import-friendly):

`from common_adapters.cancel_convesation import cancel_conversation`
"""

from .api import (
    CancelledError,
    CancellationToken,
    cancel_conversation,
    is_cancelled,
    register_cancellation,
    register_task,
    unregister_cancellation,
    unregister_task,
)

__all__ = [
    "CancelledError",
    "CancellationToken",
    "cancel_conversation",
    "is_cancelled",
    "register_cancellation",
    "register_task",
    "unregister_cancellation",
    "unregister_task",
]
