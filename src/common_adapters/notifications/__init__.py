"""
Push Notification Service

Real-time event delivery to browser clients via WebSocket:
- Connection management with session/tab routing
- Broadcast modes (tab-only vs session-wide)
- Heartbeat/keepalive for proxy compatibility
- Backpressure handling with bounded queues
"""

from .connection_manager import ConnectionManager, Connection
from .protocol import (
    ServerEvent,
    ClientCommand,
    StatusEvent,
    ProgressEvent,
    AssistantMessageEvent,
    PingEvent,
    ElicitationRequestEvent,
    UserMessageCommand,
    ElicitationResponseCommand,
    PongCommand,
    event_to_dict,
    parse_client_command,
)
from .broadcast import BroadcastMode, get_broadcast_mode_str

__all__ = [
    # Connection management
    "ConnectionManager",
    "Connection",
    # Protocol types
    "ServerEvent",
    "ClientCommand",
    "StatusEvent",
    "ProgressEvent",
    "AssistantMessageEvent",
    "PingEvent",
    "ElicitationRequestEvent",
    "UserMessageCommand",
    "ElicitationResponseCommand",
    "PongCommand",
    "event_to_dict",
    "parse_client_command",
    # Broadcast
    "BroadcastMode",
    "get_broadcast_mode_str",
]
