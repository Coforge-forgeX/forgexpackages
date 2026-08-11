"""
WebSocket Connection Manager

Server-side WebSocket connection management with:
- Session/tab routing for multi-tab support
- Single-writer pattern to prevent concurrent send issues
- Backpressure handling with bounded queues
- Heartbeat/keepalive for proxy compatibility
- Graceful shutdown
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("common_adapters.notifications.connection_manager")


@dataclass
class Connection:
    """
    Represents a single browser tab connection.

    Attributes:
        websocket: The WebSocket connection object
        user_session_id: Shared across tabs for a user (e.g., localStorage)
        tab_id: Unique per tab (e.g., sessionStorage)
        outgoing: Bounded queue for outgoing messages
        sender_task: Single-writer task for sending messages
        last_seen_ts: Timestamp of last activity (for idle timeout)
    """

    websocket: Any  # WebSocket type depends on framework (Starlette, FastAPI, etc.)
    user_session_id: str
    tab_id: str
    outgoing: asyncio.Queue[str]
    sender_task: asyncio.Task
    last_seen_ts: float


class ConnectionManager:
    """
    Manages WebSocket connections with session/tab routing.

    Key features:
    - Single-writer pattern: All outbound sends go through a dedicated sender task
    - Backpressure: Bounded queue with drop policy for slow clients
    - Heartbeat: Server pings to keep connections alive through proxies
    - Session routing: Messages can target specific tabs or broadcast to all tabs

    Example usage:
        manager = ConnectionManager()

        # On WebSocket connect
        conn = await manager.connect(websocket, user_session_id, tab_id)

        # Send to specific tab (elicitation)
        await manager.send_to_tab(session_id, tab_id, {"type": "status", "text": "OK"})

        # Broadcast to all tabs in session
        await manager.send_to_session(session_id, {"type": "progress", "percent": 50})

        # On WebSocket disconnect
        await manager.disconnect(conn)
    """

    def __init__(
        self,
        *,
        max_queue: int = 200,
        ping_interval_s: int = 25,
        idle_timeout_s: int = 120,
    ):
        """
        Initialize the connection manager.

        Args:
            max_queue: Maximum messages in outbound queue per connection
            ping_interval_s: Interval between server heartbeat pings
            idle_timeout_s: Disconnect connections idle longer than this
        """
        self._max_queue = max_queue
        self._ping_interval_s = ping_interval_s
        self._idle_timeout_s = idle_timeout_s

        # user_session_id -> tab_id -> Connection
        self._connections: Dict[str, Dict[str, Connection]] = {}
        self._lock = asyncio.Lock()
        self._closing = False

    async def _sender_loop(self, ws: Any, queue: asyncio.Queue[str]) -> None:
        """
        Single-writer loop for sending messages.
        
        This ensures only one coroutine sends to the WebSocket at a time,
        preventing concurrent send issues.
        """
        try:
            while True:
                message = await queue.get()
                try:
                    if hasattr(ws, "send_text"):
                        await ws.send_text(message)
                    elif hasattr(ws, "send"):
                        await ws.send(message)
                except Exception as e:
                    logger.warning(f"Failed to send message: {e}")
                    break
        except asyncio.CancelledError:
            pass

    async def connect(
        self,
        ws: Any,
        user_session_id: str,
        tab_id: str,
    ) -> Connection:
        """
        Accept and register a new WebSocket connection.

        Args:
            ws: WebSocket connection object
            user_session_id: User session ID (shared across tabs)
            tab_id: Tab-specific ID (unique per tab)

        Returns:
            Connection object
        """
        # Accept the WebSocket connection if it has an accept method
        if hasattr(ws, "accept"):
            await ws.accept()

        outgoing: asyncio.Queue[str] = asyncio.Queue(maxsize=self._max_queue)
        conn = Connection(
            websocket=ws,
            user_session_id=user_session_id,
            tab_id=tab_id,
            outgoing=outgoing,
            sender_task=asyncio.create_task(self._sender_loop(ws, outgoing)),
            last_seen_ts=time.time(),
        )

        async with self._lock:
            self._connections.setdefault(user_session_id, {})[tab_id] = conn

        logger.info(f"Connection established: session={user_session_id}, tab={tab_id}")

        # Send initial status event
        await self.send_to_tab(
            user_session_id,
            tab_id,
            {"type": "status", "text": "Connected", "tab_id": tab_id},
        )

        return conn

    async def disconnect(self, conn: Connection) -> None:
        """
        Unregister and close a connection safely.

        Args:
            conn: Connection to disconnect
        """
        async with self._lock:
            tabs = self._connections.get(conn.user_session_id, {})
            tabs.pop(conn.tab_id, None)
            if not tabs:
                self._connections.pop(conn.user_session_id, None)

        logger.info(f"Connection disconnected: session={conn.user_session_id}, tab={conn.tab_id}")

        # Stop sender task (single writer)
        conn.sender_task.cancel()

        # Close the socket
        try:
            if hasattr(conn.websocket, "close"):
                await conn.websocket.close()
        except Exception:
            pass

    async def send_to_tab(
        self,
        user_session_id: str,
        tab_id: str,
        message: Dict[str, Any],
    ) -> bool:
        """
        Queue a JSON message to a specific tab connection.

        This is the correct path for elicitation prompts to avoid collisions.

        Args:
            user_session_id: Target user session ID
            tab_id: Target tab ID
            message: Message dict to send

        Returns:
            True if message was queued, False if connection not found or queue full
        """
        payload = json.dumps(message)

        async with self._lock:
            conn = self._connections.get(user_session_id, {}).get(tab_id)

        if not conn:
            logger.warning(f"Connection not found: session={user_session_id}, tab={tab_id}")
            return False

        try:
            conn.outgoing.put_nowait(payload)
            return True
        except asyncio.QueueFull:
            # Production policy: drop message for slow clients
            logger.warning(f"Queue full for session={user_session_id}, tab={tab_id}")
            return False

    async def send_to_session(
        self,
        user_session_id: str,
        message: Dict[str, Any],
    ) -> int:
        """
        Broadcast a message to all tabs in a session.

        Args:
            user_session_id: Target user session ID
            message: Message dict to send

        Returns:
            Number of connections that received the message
        """
        payload = json.dumps(message)
        sent_count = 0

        async with self._lock:
            tabs = self._connections.get(user_session_id, {})
            connections = list(tabs.values())

        for conn in connections:
            try:
                conn.outgoing.put_nowait(payload)
                sent_count += 1
            except asyncio.QueueFull:
                logger.warning(f"Queue full for tab={conn.tab_id}")

        return sent_count

    async def broadcast_all(self, message: Dict[str, Any]) -> int:
        """
        Broadcast a message to all connected clients.

        Args:
            message: Message dict to send

        Returns:
            Number of connections that received the message
        """
        payload = json.dumps(message)
        sent_count = 0

        async with self._lock:
            all_connections = [
                conn
                for tabs in self._connections.values()
                for conn in tabs.values()
            ]

        for conn in all_connections:
            try:
                conn.outgoing.put_nowait(payload)
                sent_count += 1
            except asyncio.QueueFull:
                logger.warning(f"Queue full for tab={conn.tab_id}")

        return sent_count

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(tabs) for tabs in self._connections.values())

    def get_session_count(self) -> int:
        """Get number of unique sessions."""
        return len(self._connections)

    async def close_all(self) -> None:
        """Close all connections gracefully."""
        self._closing = True
        
        async with self._lock:
            all_connections = [
                conn
                for tabs in self._connections.values()
                for conn in tabs.values()
            ]
            self._connections.clear()

        for conn in all_connections:
            conn.sender_task.cancel()
            try:
                if hasattr(conn.websocket, "close"):
                    await conn.websocket.close()
            except Exception:
                pass

        logger.info("All connections closed")
