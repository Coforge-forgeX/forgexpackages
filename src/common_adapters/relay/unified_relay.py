"""
Unified Service Bus WebSocket Relay

A centralized relay that subscribes to multiple Azure Service Bus topics
and routes messages dynamically to WebSocket clients based on agent type
and conversation ID.

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │                   Azure Service Bus                      │
    │  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐  │
    │  │ ba-dev  │   │ po-dev  │   │arch-dev │   │ qe-dev  │  │
    │  └────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘  │
    └───────┼─────────────┼─────────────┼─────────────┼───────┘
            │             │             │             │
            └─────────────┴──────┬──────┴─────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   Unified Relay        │
                    │   (Single Web App)     │
                    │                        │
                    │  ┌──────────────────┐  │
                    │  │ Topic Consumers  │  │
                    │  │ (one per topic)  │  │
                    │  └────────┬─────────┘  │
                    │           │            │
                    │  ┌────────▼─────────┐  │
                    │  │ ConnectionManager│  │
                    │  │ (routes by agent │  │
                    │  │  + conversation) │  │
                    │  └────────┬─────────┘  │
                    └───────────┼────────────┘
                                │
           ┌────────────────────┼────────────────────┐
           │                    │                    │
           ▼                    ▼                    ▼
    ┌────────────┐       ┌────────────┐       ┌────────────┐
    │ BA Client  │       │ PO Client  │       │Arch Client │
    │ (Frontend) │       │ (Frontend) │       │ (Frontend) │
    └────────────┘       └────────────┘       └────────────┘

Usage:
    # Run locally
    python -m common_adapters.relay.unified_relay

    # Or with uvicorn
    uvicorn common_adapters.relay.unified_relay:app --host 0.0.0.0 --port 8000

Connect via WebSocket:
    ws://host:port/ws?agent=ba&channel=<conversation_id>
    ws://host:port/ws?agent=po&channel=<conversation_id>
    ws://host:port/ws?agent=arch&channel=<conversation_id>
    ws://host:port/ws?agent=qe&channel=<conversation_id>
    ws://host:port/ws?agent=devagent&channel=<conversation_id>
    ws://host:port/ws?agent=kb&channel=<conversation_id>

Environment Variables:
    SERVICE_BUS_CONNECTION_STRING: Azure Service Bus connection string
    RELAY_TOPICS: Comma-separated list of topics (default: ba-dev,po-dev,arch-dev,qe-dev,devagent-dev,kb-dev)
    RELAY_SUBSCRIPTION_PREFIX: Subscription name prefix (default: unified-relay)
    PORT: Server port (default: 8000)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Dict, Set, Optional
from enum import Enum
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class RelayConfig:
    """Unified relay configuration."""
    
    service_bus_connection_string: str = field(default_factory=lambda: os.getenv("SERVICE_BUS_CONNECTION_STRING", ""))
    
    # Topics to subscribe to (comma-separated or list)
    topics: list[str] = field(default_factory=lambda: _parse_topics())
    
    # Subscription naming
    subscription_prefix: str = field(default_factory=lambda: os.getenv("RELAY_SUBSCRIPTION_PREFIX", "unified-relay"))
    
    # Server settings
    host: str = field(default_factory=lambda: os.getenv("RELAY_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", os.getenv("RELAY_PORT", "8000"))))
    
    # WebSocket settings
    max_queue: int = field(default_factory=lambda: int(os.getenv("WS_MAX_QUEUE", "200")))
    ping_interval_s: int = field(default_factory=lambda: int(os.getenv("WS_PING_INTERVAL_S", "25")))
    idle_timeout_s: int = field(default_factory=lambda: int(os.getenv("WS_IDLE_TIMEOUT_S", "180")))
    
    def __post_init__(self):
        if not self.service_bus_connection_string:
            raise ValueError("SERVICE_BUS_CONNECTION_STRING environment variable is required")


def _parse_topics() -> list[str]:
    """Parse topics from environment variable."""
    topics_str = os.getenv("RELAY_TOPICS", "ba-dev,po-dev,arch-dev,qe-dev,devagent-dev,kb-dev")
    return [t.strip() for t in topics_str.split(",") if t.strip()]


def _topic_to_agent(topic: str) -> str:
    """Map topic name to agent type for routing."""
    mapping = {
        "ba-dev": "ba",
        "ba-prod": "ba",
        "po-dev": "po",
        "po-prod": "po",
        "arch-dev": "arch",
        "arch-prod": "arch",
        "qe-dev": "qe",
        "qe-prod": "qe",
        "devagent-dev": "devagent",
        "devagent-prod": "devagent",
        "kb-dev": "kb",
        "kb-prod": "kb",
    }
    return mapping.get(topic, topic.split("-")[0])


# =============================================================================
# Connection Manager with Agent-Aware Routing
# =============================================================================

@dataclass
class ClientConnection:
    """Represents a connected WebSocket client."""
    websocket: WebSocket
    session_id: str
    tab_id: str
    agent: str  # Which agent this client is listening to (ba, po, qe, arch, devagent, kb, all)
    last_seen: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class UnifiedConnectionManager:
    """
    Manages WebSocket connections with agent-aware routing.
    
    Connections are indexed by:
    - agent -> session_id -> tab_id -> connection
    
    This allows efficient routing of messages to the correct clients
    based on both agent type and conversation/session ID.
    """
    
    def __init__(self, max_queue: int = 200, ping_interval_s: int = 25, idle_timeout_s: int = 180):
        # agent -> session_id -> tab_id -> connection
        self._connections: Dict[str, Dict[str, Dict[str, ClientConnection]]] = {}
        self._lock = asyncio.Lock()
        self._max_queue = max_queue
        self._ping_interval_s = ping_interval_s
        self._idle_timeout_s = idle_timeout_s
    
    async def connect(
        self,
        websocket: WebSocket,
        agent: str,
        session_id: str,
        tab_id: str,
    ) -> ClientConnection:
        """Register a new WebSocket connection."""
        await websocket.accept()
        
        conn = ClientConnection(
            websocket=websocket,
            session_id=session_id,
            tab_id=tab_id,
            agent=agent,
        )
        
        async with self._lock:
            if agent not in self._connections:
                self._connections[agent] = {}
            if session_id not in self._connections[agent]:
                self._connections[agent][session_id] = {}
            self._connections[agent][session_id][tab_id] = conn
        
        return conn
    
    async def disconnect(self, conn: ClientConnection) -> None:
        """Unregister a WebSocket connection."""
        async with self._lock:
            agent_conns = self._connections.get(conn.agent, {})
            session_conns = agent_conns.get(conn.session_id, {})
            session_conns.pop(conn.tab_id, None)
            
            # Cleanup empty dicts
            if not session_conns:
                agent_conns.pop(conn.session_id, None)
            if not agent_conns:
                self._connections.pop(conn.agent, None)
    
    async def send_to_agent_session(
        self,
        agent: str,
        session_id: str,
        message: dict,
    ) -> int:
        """Send message to all tabs in a session for a specific agent."""
        count = 0
        async with self._lock:
            # Get connections for this agent
            agent_conns = self._connections.get(agent, {})
            session_conns = agent_conns.get(session_id, {})
            tabs_to_remove = []
            
            for tab_id, conn in session_conns.items():
                try:
                    await conn.websocket.send_json(message)
                    count += 1
                except Exception:
                    tabs_to_remove.append(tab_id)
            
            # Cleanup failed connections
            for tab_id in tabs_to_remove:
                session_conns.pop(tab_id, None)
        
        # Also send to "all" agent subscribers
        if agent != "all":
            count += await self._send_to_all_subscribers(session_id, message)
        
        return count
    
    async def _send_to_all_subscribers(self, session_id: str, message: dict) -> int:
        """Send to clients subscribed to 'all' agents."""
        count = 0
        async with self._lock:
            all_conns = self._connections.get("all", {})
            session_conns = all_conns.get(session_id, {})
            tabs_to_remove = []
            
            for tab_id, conn in session_conns.items():
                try:
                    await conn.websocket.send_json(message)
                    count += 1
                except Exception:
                    tabs_to_remove.append(tab_id)
            
            for tab_id in tabs_to_remove:
                session_conns.pop(tab_id, None)
        
        return count
    
    async def broadcast_to_agent(self, agent: str, message: dict) -> int:
        """Broadcast message to ALL sessions for a specific agent."""
        count = 0
        async with self._lock:
            agent_conns = self._connections.get(agent, {})
            
            for session_id, session_conns in list(agent_conns.items()):
                for tab_id, conn in list(session_conns.items()):
                    try:
                        await conn.websocket.send_json(message)
                        count += 1
                    except Exception:
                        session_conns.pop(tab_id, None)
        
        return count
    
    async def close_all(self) -> None:
        """Close all connections gracefully."""
        async with self._lock:
            for agent_conns in self._connections.values():
                for session_conns in agent_conns.values():
                    for conn in session_conns.values():
                        try:
                            await conn.websocket.close()
                        except Exception:
                            pass
            self._connections.clear()
    
    def get_stats(self) -> dict:
        """Get connection statistics."""
        total_clients = 0
        total_sessions = 0
        agent_stats = {}
        
        for agent, agent_conns in self._connections.items():
            sessions = len(agent_conns)
            clients = sum(len(tabs) for tabs in agent_conns.values())
            total_sessions += sessions
            total_clients += clients
            agent_stats[agent] = {"sessions": sessions, "clients": clients}
        
        return {
            "total_clients": total_clients,
            "total_sessions": total_sessions,
            "by_agent": agent_stats,
        }
    
    def update_last_seen(self, conn: ClientConnection) -> None:
        """Update last-seen timestamp for a connection."""
        conn.last_seen = asyncio.get_event_loop().time()


# =============================================================================
# Service Bus Multi-Topic Consumer
# =============================================================================

class MultiTopicConsumer:
    """
    Consumes messages from multiple Service Bus topics concurrently.
    
    Each topic gets its own subscription and consumer task.
    """
    
    def __init__(
        self,
        connection_string: str,
        topics: list[str],
        subscription_prefix: str,
        connection_manager: UnifiedConnectionManager,
    ):
        self.connection_string = connection_string
        self.topics = topics
        self.subscription_prefix = subscription_prefix
        self.connection_manager = connection_manager
        self._tasks: list[asyncio.Task] = []
        self._running = False
    
    def _get_subscription_name(self, topic: str) -> str:
        """Generate subscription name for a topic."""
        return f"{self.subscription_prefix}-{topic}"
    
    async def ensure_subscriptions(self) -> None:
        """Create subscriptions if they don't exist."""
        try:
            from azure.servicebus.management import ServiceBusAdministrationClient
            
            admin = ServiceBusAdministrationClient.from_connection_string(self.connection_string)
            
            for topic in self.topics:
                sub_name = self._get_subscription_name(topic)
                try:
                    admin.get_subscription(topic, sub_name)
                    print(f"  ✓ Subscription '{sub_name}' exists on topic '{topic}'")
                except Exception:
                    try:
                        admin.create_subscription(topic, sub_name)
                        print(f"  ✓ Created subscription '{sub_name}' on topic '{topic}'")
                    except Exception as e:
                        print(f"  ⚠ Could not create subscription for '{topic}': {e}")
        except Exception as e:
            print(f"⚠ Could not manage subscriptions: {e}")
            print("  Will attempt to consume anyway...")
    
    async def start(self) -> None:
        """Start consumer tasks for all topics."""
        self._running = True
        
        for topic in self.topics:
            task = asyncio.create_task(
                self._consume_topic(topic),
                name=f"consumer-{topic}"
            )
            self._tasks.append(task)
            print(f"  ✓ Started consumer for topic: {topic}")
    
    async def stop(self) -> None:
        """Stop all consumer tasks."""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        print("✓ All consumers stopped")
    
    async def _consume_topic(self, topic: str) -> None:
        """Consume messages from a single topic."""
        try:
            from azure.servicebus.aio import ServiceBusClient
        except ImportError:
            print(f"❌ azure-servicebus not installed for topic {topic}")
            return
        
        subscription_name = self._get_subscription_name(topic)
        agent = _topic_to_agent(topic)
        
        print(f"👂 [{topic}] Listening on subscription '{subscription_name}' (agent: {agent})")
        
        while self._running:
            try:
                async with ServiceBusClient.from_connection_string(self.connection_string) as client:
                    receiver = client.get_subscription_receiver(
                        topic_name=topic,
                        subscription_name=subscription_name,
                        max_wait_time=5,
                    )
                    
                    async with receiver:
                        async for msg in receiver:
                            if not self._running:
                                break
                            
                            try:
                                body = str(msg)
                                data = json.loads(body)
                                
                                # Extract routing info
                                conversation_id = data.get("conversation_id") or "default"
                                status = data.get("status", "?")
                                operation = data.get("operation", "?")
                                
                                print(f"📨 [{topic}] {operation} [{status}] conv={conversation_id[:20]}...")
                                
                                # Route to appropriate clients
                                await self._route_message(agent, conversation_id, data, topic)
                                
                                # Acknowledge
                                await receiver.complete_message(msg)
                                
                            except json.JSONDecodeError as e:
                                print(f"⚠ [{topic}] Invalid JSON: {e}")
                                await receiver.complete_message(msg)
                            except Exception as e:
                                print(f"⚠ [{topic}] Error processing: {e}")
                                await receiver.abandon_message(msg)
                                
            except asyncio.CancelledError:
                print(f"🛑 [{topic}] Consumer cancelled")
                raise
            except Exception as e:
                if self._running:
                    print(f"⚠ [{topic}] Connection error: {e}")
                    print(f"   Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)
    
    async def _route_message(
        self,
        agent: str,
        conversation_id: str,
        data: dict,
        topic: str,
    ) -> None:
        """Route message to WebSocket clients."""
        # Build payload
        payload = {
            "type": data.get("type", "progress"),
            "agent": agent,
            "topic": topic,
            "channel": conversation_id,
            "event": data,
        }
        
        # Send to clients subscribed to this agent + session
        count = await self.connection_manager.send_to_agent_session(
            agent=agent,
            session_id=conversation_id,
            message=payload,
        )
        
        stats = self.connection_manager.get_stats()
        print(f"   └─ Routed to {count} clients (total: {stats['total_clients']})")


# =============================================================================
# FastAPI Application
# =============================================================================

# Global instances
config: Optional[RelayConfig] = None
connection_manager: Optional[UnifiedConnectionManager] = None
consumer: Optional[MultiTopicConsumer] = None
startup_error: Optional[str] = None
startup_complete: bool = False


def _load_local_settings():
    """Load environment variables from local.settings.json if present."""
    possible_paths = [
        os.path.join(os.getcwd(), "local.settings.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "local.settings.json"),
        "/home/site/wwwroot/local.settings.json",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, value in data.get("Values", {}).items():
                    if key not in os.environ:
                        os.environ[key] = str(value)
                print(f"✓ Loaded settings from: {path}")
                return
            except Exception as e:
                print(f"⚠ Failed to load {path}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global config, connection_manager, consumer, startup_error, startup_complete
    
    # Load settings
    _load_local_settings()
    
    startup_error = None
    startup_complete = False

    try:
        # Initialize
        config = RelayConfig()
        connection_manager = UnifiedConnectionManager(
            max_queue=config.max_queue,
            ping_interval_s=config.ping_interval_s,
            idle_timeout_s=config.idle_timeout_s,
        )
        consumer = MultiTopicConsumer(
            connection_string=config.service_bus_connection_string,
            topics=config.topics,
            subscription_prefix=config.subscription_prefix,
            connection_manager=connection_manager,
        )
        
        print()
        print("=" * 70)
        print("  Unified Service Bus WebSocket Relay")
        print("=" * 70)
        print(f"  Topics:      {', '.join(config.topics)}")
        print(f"  Subscription Prefix: {config.subscription_prefix}")
        print(f"  WebSocket:   ws://{config.host}:{config.port}/ws?agent=<agent>&channel=<conv_id>")
        print(f"  Health:      http://{config.host}:{config.port}/health")
        print("=" * 70)
        print()
        
        # Ensure subscriptions exist
        await consumer.ensure_subscriptions()
        
        # Start consumers
        await consumer.start()

        startup_complete = True
        
        print()
        print("Unified relay is ready")
        print()
    except Exception as e:
        startup_error = str(e)
        print(f"Startup initialization failed: {startup_error}")
        print("Health endpoint will remain available for diagnostics")
    
    yield
    
    # Shutdown
    print()
    print("🛑 Shutting down...")
    
    if consumer:
        await consumer.stop()

    if connection_manager:
        await connection_manager.close_all()
    
    print("✓ Shutdown complete")


app = FastAPI(
    title="Unified Service Bus WebSocket Relay",
    description="Centralized relay for multiple agents",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """Health check with detailed statistics."""
    stats = connection_manager.get_stats() if connection_manager else {}
    
    return {
        "status": "ok" if startup_complete else "degraded",
        "service": "unified-servicebus-relay",
        "startup_complete": startup_complete,
        "startup_error": startup_error,
        "topics": config.topics if config else [],
        "subscription_prefix": config.subscription_prefix if config else "",
        "stats": stats,
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint with usage info."""
    return {
        "service": "Unified Service Bus WebSocket Relay",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "websocket": "/ws?agent=<agent>&channel=<conversation_id>",
        },
        "agents": ["ba", "po", "qe", "arch", "devagent", "kb", "all"],
        "topics": config.topics if config else [],
        "startup_complete": startup_complete,
        "startup_error": startup_error,
    }


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    agent: str = Query(default="all", description="Agent type: ba, po, qe, arch, devagent, kb, or all"),
    channel: str = Query(default=None, description="Conversation/session ID"),
    session_id: str = Query(default=None, description="Alias for channel"),
    tab_id: str = Query(default=None, description="Browser tab ID"),
) -> None:
    """
    WebSocket endpoint for receiving agent progress messages.
    
    Query Parameters:
    - agent: Which agent to listen to (ba, po, qe, arch, devagent, kb, all)
    - channel/session_id: Conversation or session ID for routing
    - tab_id: Unique browser tab identifier (auto-generated if missing)
    
    Examples:
        ws://host/ws?agent=ba&channel=conv_123
        ws://host/ws?agent=all&channel=conv_123  # Receive from all agents
        ws://host/ws?agent=po&session_id=sess_456&tab_id=tab_789
    """
    # Resolve parameters
    resolved_session_id = channel or session_id or "default"
    resolved_tab_id = tab_id or f"tab_{uuid.uuid4().hex[:8]}"
    resolved_agent = agent.lower() if agent else "all"
    
    # Register connection
    conn = await connection_manager.connect(
        websocket=websocket,
        agent=resolved_agent,
        session_id=resolved_session_id,
        tab_id=resolved_tab_id,
    )
    
    stats = connection_manager.get_stats()
    print(f"✓ Client connected")
    print(f"  Agent:   {resolved_agent}")
    print(f"  Session: {resolved_session_id[:30]}...")
    print(f"  Tab:     {resolved_tab_id}")
    print(f"  Total:   {stats['total_clients']} clients, {stats['total_sessions']} sessions")
    
    try:
        while True:
            data = await websocket.receive_text()
            connection_manager.update_last_seen(conn)
            
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")
                
                if msg_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "ts": int(asyncio.get_event_loop().time() * 1000)
                    })
                elif msg_type == "subscribe":
                    # Future: support dynamic subscription changes
                    new_agent = msg.get("agent")
                    print(f"  ℹ Subscribe request for agent '{new_agent}' (not implemented)")
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"  ⚠ WebSocket error: {e}")
    finally:
        await connection_manager.disconnect(conn)
        stats = connection_manager.get_stats()
        print(f"✗ Client disconnected")
        print(f"  Agent:   {resolved_agent}")
        print(f"  Session: {resolved_session_id[:30]}...")
        print(f"  Remaining: {stats['total_clients']} clients")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    _load_local_settings()
    
    port = int(os.getenv("PORT", os.getenv("RELAY_PORT", "8000")))
    host = os.getenv("RELAY_HOST", "0.0.0.0")
    
    print(f"Starting Unified Relay on {host}:{port}")
    
    uvicorn.run(
        "common_adapters.relay.unified_relay:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
