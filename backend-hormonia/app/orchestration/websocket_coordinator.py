"""
WebSocket Coordination System for Real-time Communication
Handles connection management, event distribution, and state synchronization
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Set, Any, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect

from app.core.redis_unified import get_async_redis
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    """WebSocket event types"""

    # User events
    USER_CONNECTED = "user.connected"
    USER_DISCONNECTED = "user.disconnected"

    # Patient events
    PATIENT_UPDATED = "patient.updated"
    PATIENT_CREATED = "patient.created"
    PATIENT_STATUS_CHANGED = "patient.status_changed"

    # Message events
    MESSAGE_SENT = "message.sent"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_READ = "message.read"
    MESSAGE_FAILED = "message.failed"

    # Flow events
    FLOW_STARTED = "flow.started"
    FLOW_COMPLETED = "flow.completed"
    FLOW_STATE_CHANGED = "flow.state_changed"

    # Alert events
    ALERT_CREATED = "alert.created"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    ALERT_RESOLVED = "alert.resolved"

    # System events
    SYSTEM_MAINTENANCE = "system.maintenance"
    SYSTEM_NOTIFICATION = "system.notification"


@dataclass
class WebSocketEvent:
    """WebSocket event data structure"""

    event_type: EventType
    data: Dict[str, Any]
    user_id: Optional[str] = None
    patient_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    correlation_id: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization"""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "user_id": self.user_id,
            "patient_id": self.patient_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebSocketEvent":
        """Create event from dictionary"""
        timestamp = None
        if data.get("timestamp"):
            timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

        return cls(
            event_type=EventType(data["event_type"]),
            data=data["data"],
            user_id=data.get("user_id"),
            patient_id=data.get("patient_id"),
            timestamp=timestamp,
            correlation_id=data.get("correlation_id"),
        )


class ConnectionState(str, Enum):
    """WebSocket connection states"""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


@dataclass
class ConnectionInfo:
    """WebSocket connection information"""

    user_id: str
    websocket: WebSocket
    connected_at: datetime
    last_ping: datetime
    state: ConnectionState = ConnectionState.CONNECTED
    subscriptions: Set[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.subscriptions is None:
            self.subscriptions = set()
        if self.metadata is None:
            self.metadata = {}


class WebSocketCoordinator:
    """
    Coordinates WebSocket connections and real-time event distribution
    """

    def __init__(self, redis_url: str = None):
        # redis_url parameter kept for backward compatibility but not used
        self.redis_client = None
        self.connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self.ping_interval = 30  # seconds
        self.connection_timeout = 300  # 5 minutes
        self._ping_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize the WebSocket coordinator"""
        try:
            # Get unified Redis client
            self.redis_client = await get_async_redis()
            await self.redis_client.ping()

            # Start background tasks
            self._ping_task = asyncio.create_task(self._ping_connections())
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())

            # Subscribe to Redis pub/sub for distributed events
            await self._setup_redis_subscription()

            logger.info("WebSocket coordinator initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize WebSocket coordinator: {e}")
            raise

    async def shutdown(self):
        """Shutdown the WebSocket coordinator"""
        try:
            # Cancel background tasks
            if self._ping_task:
                self._ping_task.cancel()
            if self._cleanup_task:
                self._cleanup_task.cancel()

            # Close all connections
            await self._close_all_connections()

            # Close Redis connection
            if self.redis_client:
                await self.redis_client.aclose()  # Redis 5.x uses aclose() for async

            logger.info("WebSocket coordinator shutdown completed")

        except Exception as e:
            logger.error(f"Error during WebSocket coordinator shutdown: {e}")

    async def connect_user(
        self, websocket: WebSocket, user_id: str, metadata: Dict[str, Any] = None
    ) -> str:
        """Connect a user's WebSocket"""
        try:
            # Accept WebSocket connection
            await websocket.accept()

            # Generate connection ID
            connection_id = f"{user_id}_{int(time.time() * 1000)}"

            # Create connection info
            connection_info = ConnectionInfo(
                user_id=user_id,
                websocket=websocket,
                connected_at=datetime.utcnow(),
                last_ping=datetime.utcnow(),
                metadata=metadata or {},
            )

            # Store connection
            self.connections[connection_id] = connection_info

            # Update user connections mapping
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)

            # Send connection confirmation
            await self._send_to_connection(
                connection_id,
                WebSocketEvent(
                    event_type=EventType.USER_CONNECTED,
                    data={
                        "connection_id": connection_id,
                        "user_id": user_id,
                        "server_time": datetime.utcnow().isoformat(),
                    },
                    user_id=user_id,
                ),
            )

            # Broadcast user connection event
            await self.broadcast_event(
                WebSocketEvent(
                    event_type=EventType.USER_CONNECTED,
                    data={"user_id": user_id, "connection_id": connection_id},
                    user_id=user_id,
                )
            )

            logger.info(f"User {user_id} connected with connection {connection_id}")
            return connection_id

        except Exception as e:
            logger.error(f"Failed to connect user {user_id}: {e}")
            raise

    async def disconnect_user(self, connection_id: str, reason: str = "normal"):
        """Disconnect a user's WebSocket"""
        try:
            connection_info = self.connections.get(connection_id)
            if not connection_info:
                return

            user_id = connection_info.user_id

            # Update connection state
            connection_info.state = ConnectionState.DISCONNECTING

            # Remove from connections
            del self.connections[connection_id]

            # Update user connections mapping
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]

            # Broadcast user disconnection event
            await self.broadcast_event(
                WebSocketEvent(
                    event_type=EventType.USER_DISCONNECTED,
                    data={
                        "user_id": user_id,
                        "connection_id": connection_id,
                        "reason": reason,
                    },
                    user_id=user_id,
                )
            )

            logger.info(
                f"User {user_id} disconnected (connection {connection_id}, reason: {reason})"
            )

        except Exception as e:
            logger.error(f"Error disconnecting connection {connection_id}: {e}")

    async def send_to_user(self, user_id: str, event: WebSocketEvent):
        """Send event to all of a user's connections"""
        user_connection_ids = self.user_connections.get(user_id, set())

        for (
            connection_id
        ) in user_connection_ids.copy():  # Copy to avoid modification during iteration
            await self._send_to_connection(connection_id, event)

    async def send_to_users(self, user_ids: List[str], event: WebSocketEvent):
        """Send event to multiple users"""
        tasks = [self.send_to_user(user_id, event) for user_id in user_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_event(self, event: WebSocketEvent, exclude_user: str = None):
        """Broadcast event to all connected users"""
        tasks = []

        for user_id in self.user_connections.keys():
            if exclude_user and user_id == exclude_user:
                continue
            tasks.append(self.send_to_user(user_id, event))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Also publish to Redis for other server instances
        if self.redis_client:
            await self._publish_to_redis(event)

    async def subscribe_to_events(
        self, connection_id: str, event_types: List[EventType]
    ):
        """Subscribe a connection to specific event types"""
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            return

        for event_type in event_types:
            connection_info.subscriptions.add(event_type.value)

        logger.debug(
            f"Connection {connection_id} subscribed to events: {[e.value for e in event_types]}"
        )

    async def unsubscribe_from_events(
        self, connection_id: str, event_types: List[EventType]
    ):
        """Unsubscribe a connection from specific event types"""
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            return

        for event_type in event_types:
            connection_info.subscriptions.discard(event_type.value)

        logger.debug(
            f"Connection {connection_id} unsubscribed from events: {[e.value for e in event_types]}"
        )

    def register_event_handler(self, event_type: EventType, handler: Callable):
        """Register an event handler for specific event types"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    async def handle_connection(self, websocket: WebSocket, user_id: str):
        """Handle a WebSocket connection lifecycle"""
        connection_id = None
        try:
            # Connect user
            connection_id = await self.connect_user(websocket, user_id)

            # Handle messages
            while True:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(
                        websocket.receive_text(), timeout=self.connection_timeout
                    )

                    # Process incoming message
                    await self._handle_incoming_message(connection_id, message)

                except asyncio.TimeoutError:
                    # Connection timeout
                    await self.disconnect_user(connection_id, "timeout")
                    break

                except WebSocketDisconnect:
                    # Client disconnected
                    await self.disconnect_user(connection_id, "client_disconnect")
                    break

        except Exception as e:
            logger.error(f"WebSocket connection error for user {user_id}: {e}")
            if connection_id:
                await self.disconnect_user(connection_id, "error")

    async def _send_to_connection(self, connection_id: str, event: WebSocketEvent):
        """Send event to a specific connection"""
        try:
            connection_info = self.connections.get(connection_id)
            if not connection_info:
                return

            # Check if connection is subscribed to this event type
            if (
                connection_info.subscriptions
                and event.event_type.value not in connection_info.subscriptions
            ):
                return

            # Send event
            await connection_info.websocket.send_text(json.dumps(event.to_dict()))

        except Exception as e:
            logger.error(f"Failed to send event to connection {connection_id}: {e}")
            # Remove failed connection
            await self.disconnect_user(connection_id, "send_failed")

    async def _handle_incoming_message(self, connection_id: str, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)

            # Handle ping/pong
            if data.get("type") == "ping":
                connection_info = self.connections.get(connection_id)
                if connection_info:
                    connection_info.last_ping = datetime.utcnow()
                    await connection_info.websocket.send_text(
                        json.dumps({"type": "pong"})
                    )
                return

            # Handle event subscription
            if data.get("type") == "subscribe":
                event_types = [EventType(et) for et in data.get("events", [])]
                await self.subscribe_to_events(connection_id, event_types)
                return

            # Handle event unsubscription
            if data.get("type") == "unsubscribe":
                event_types = [EventType(et) for et in data.get("events", [])]
                await self.unsubscribe_from_events(connection_id, event_types)
                return

            # Handle custom events
            if data.get("type") == "event":
                event = WebSocketEvent.from_dict(data)
                await self._process_event(event)
                return

            logger.warning(
                f"Unknown message type from connection {connection_id}: {data.get('type')}"
            )

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from connection {connection_id}: {message}")
        except Exception as e:
            logger.error(f"Error handling message from connection {connection_id}: {e}")

    async def _process_event(self, event: WebSocketEvent):
        """Process incoming event from client"""
        try:
            # Call registered event handlers
            handlers = self.event_handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Event handler error for {event.event_type}: {e}")

        except Exception as e:
            logger.error(f"Error processing event {event.event_type}: {e}")

    async def _ping_connections(self):
        """Periodically ping connections to keep them alive"""
        while True:
            try:
                await asyncio.sleep(self.ping_interval)

                current_time = datetime.utcnow()
                ping_tasks = []

                for connection_id, connection_info in self.connections.items():
                    try:
                        ping_event = WebSocketEvent(
                            event_type=EventType.SYSTEM_NOTIFICATION,
                            data={
                                "type": "ping",
                                "server_time": current_time.isoformat(),
                            },
                        )
                        ping_tasks.append(
                            self._send_to_connection(connection_id, ping_event)
                        )
                    except Exception as e:
                        logger.error(
                            f"Error creating ping for connection {connection_id}: {e}"
                        )

                if ping_tasks:
                    await asyncio.gather(*ping_tasks, return_exceptions=True)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ping task: {e}")

    async def _cleanup_stale_connections(self):
        """Clean up stale connections"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                current_time = datetime.utcnow()
                stale_connections = []

                for connection_id, connection_info in self.connections.items():
                    # Check if connection is stale
                    if (
                        current_time - connection_info.last_ping
                    ).total_seconds() > self.connection_timeout:
                        stale_connections.append(connection_id)

                # Remove stale connections
                for connection_id in stale_connections:
                    await self.disconnect_user(connection_id, "stale_connection")

                if stale_connections:
                    logger.info(
                        f"Cleaned up {len(stale_connections)} stale connections"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

    async def _close_all_connections(self):
        """Close all WebSocket connections"""
        tasks = []
        for connection_id in list(self.connections.keys()):
            tasks.append(self.disconnect_user(connection_id, "server_shutdown"))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _setup_redis_subscription(self):
        """Set up Redis pub/sub for distributed events"""
        if not self.redis_client:
            return

        try:
            # Subscribe to WebSocket events channel
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe("websocket_events")

            # Start Redis message processing task
            asyncio.create_task(self._process_redis_messages(pubsub))

        except Exception as e:
            logger.error(f"Failed to set up Redis subscription: {e}")

    async def _process_redis_messages(self, pubsub):
        """Process messages from Redis pub/sub"""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        event_data = json.loads(message["data"])
                        event = WebSocketEvent.from_dict(event_data)

                        # Broadcast to local connections
                        await self.broadcast_event(event)

                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in Redis message processing: {e}")

    async def _publish_to_redis(self, event: WebSocketEvent):
        """Publish event to Redis for other server instances"""
        if not self.redis_client:
            return

        try:
            await self.redis_client.publish(
                "websocket_events", json.dumps(event.to_dict())
            )
        except Exception as e:
            logger.error(f"Failed to publish event to Redis: {e}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""
        return {
            "total_connections": len(self.connections),
            "total_users": len(self.user_connections),
            "connections_by_user": {
                user_id: len(connections)
                for user_id, connections in self.user_connections.items()
            },
            "average_connections_per_user": (
                len(self.connections) / len(self.user_connections)
                if self.user_connections
                else 0
            ),
        }


# Global WebSocket coordinator instance
websocket_coordinator = WebSocketCoordinator()
