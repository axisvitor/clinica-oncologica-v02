"""
Enhanced WebSocket Support for Real-time Features.
Implements comprehensive real-time communication with advanced features.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from uuid import UUID, uuid4
from enum import Enum

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.websockets import WebSocketState
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError
import redis.asyncio as redis

from app.dependencies import get_db, get_current_user_websocket, get_websocket_manager, get_current_user
from app.models.user import User
from app.utils.logging import get_logger
from app.services.websocket_manager import WebSocketManager, ConnectionManager
from app.config import settings

logger = get_logger(__name__)
router = APIRouter()

class WebSocketEventType(str, Enum):
    """WebSocket event types."""
    # Connection events
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    HEARTBEAT = "heartbeat"

    # Patient events
    PATIENT_CREATED = "patient_created"
    PATIENT_UPDATED = "patient_updated"
    PATIENT_DELETED = "patient_deleted"
    PATIENT_STATUS_CHANGED = "patient_status_changed"

    # Message events
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_STATUS_UPDATED = "message_status_updated"
    TYPING_INDICATOR = "typing_indicator"

    # Quiz events
    QUIZ_SESSION_CREATED = "quiz_session_created"
    QUIZ_PROGRESS_UPDATED = "quiz_progress_updated"
    QUIZ_COMPLETED = "quiz_completed"

    # System events
    ALERT_CREATED = "alert_created"
    ALERT_RESOLVED = "alert_resolved"
    SYSTEM_NOTIFICATION = "system_notification"

    # Real-time metrics
    METRICS_UPDATE = "metrics_update"
    DASHBOARD_UPDATE = "dashboard_update"

class WebSocketMessage(BaseModel):
    """WebSocket message structure."""
    id: str = None
    type: WebSocketEventType
    data: Dict[str, Any]
    timestamp: datetime = None
    user_id: Optional[str] = None
    channel: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __init__(self, **data):
        if 'id' not in data or data['id'] is None:
            data['id'] = str(uuid4())
        if 'timestamp' not in data or data['timestamp'] is None:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)

class WebSocketChannel(str, Enum):
    """WebSocket channel types."""
    GLOBAL = "global"
    USER = "user"
    PATIENT = "patient"
    SYSTEM = "system"
    ALERTS = "alerts"
    METRICS = "metrics"

class ConnectionInfo(BaseModel):
    """WebSocket connection information."""
    connection_id: str
    user_id: str
    user_role: str
    connected_at: datetime
    last_heartbeat: datetime
    channels: Set[str]
    metadata: Dict[str, Any] = {}

class EnhancedWebSocketManager:
    """
    Enhanced WebSocket manager with advanced features.

    Features:
    - Multi-channel support
    - Connection pooling
    - Message queuing
    - Heartbeat monitoring
    - Event subscription management
    - Redis pub/sub integration
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.connections: Dict[str, WebSocket] = {}
        self.connection_info: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = {}
        self.channel_subscriptions: Dict[str, Set[str]] = {}
        self.redis = redis_client
        self.heartbeat_interval = 30  # seconds
        self.message_queue: Dict[str, List[WebSocketMessage]] = {}
        self._background_tasks: List[asyncio.Task] = []
        self._started = False

    async def start(self):
        """Start background tasks after event loop is available."""
        if self._started:
            return

        self._started = True
        try:
            self._background_tasks.append(asyncio.create_task(self._heartbeat_monitor()))
            self._background_tasks.append(asyncio.create_task(self._process_message_queue()))

            if self.redis:
                self._background_tasks.append(asyncio.create_task(self._redis_subscriber()))

            logger.info("WebSocket background tasks started successfully")
        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")

    async def stop(self):
        """Stop background tasks gracefully."""
        for task in self._background_tasks:
            task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
        self._started = False

    async def connect(
        self,
        websocket: WebSocket,
        user: User,
        connection_id: Optional[str] = None,
        already_accepted: bool = False
    ) -> str:
        """Accept WebSocket connection with enhanced tracking."""
        if not already_accepted:
            await websocket.accept()

        if not connection_id:
            connection_id = str(uuid4())

        # Store connection
        self.connections[connection_id] = websocket

        # Create connection info
        conn_info = ConnectionInfo(
            connection_id=connection_id,
            user_id=str(user.id),
            user_role=user.role,
            connected_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow(),
            channels=set()
        )
        self.connection_info[connection_id] = conn_info

        # Track user connections
        user_id = str(user.id)
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)

        # Auto-subscribe to user channel
        await self.subscribe_to_channel(connection_id, f"user:{user_id}")

        # Send connection confirmation
        await self.send_to_connection(connection_id, WebSocketMessage(
            type=WebSocketEventType.CONNECT,
            data={
                "connection_id": connection_id,
                "status": "connected",
                "server_time": datetime.utcnow().isoformat()
            }
        ))

        logger.info(
            f"WebSocket connection established: {connection_id}",
            extra={
                "event_type": "websocket_connected",
                "connection_id": connection_id,
                "user_id": user_id,
                "user_role": user.role
            }
        )

        return connection_id

    async def disconnect(self, connection_id: str):
        """Disconnect WebSocket with cleanup."""
        if connection_id not in self.connections:
            return

        conn_info = self.connection_info.get(connection_id)
        if conn_info:
            # Remove from user connections
            user_id = conn_info.user_id
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]

            # Remove from channel subscriptions
            for channel in conn_info.channels:
                if channel in self.channel_subscriptions:
                    self.channel_subscriptions[channel].discard(connection_id)
                    if not self.channel_subscriptions[channel]:
                        del self.channel_subscriptions[channel]

        # Clean up
        del self.connections[connection_id]
        if connection_id in self.connection_info:
            del self.connection_info[connection_id]
        if connection_id in self.message_queue:
            del self.message_queue[connection_id]

        logger.info(
            f"WebSocket connection closed: {connection_id}",
            extra={
                "event_type": "websocket_disconnected",
                "connection_id": connection_id,
                "user_id": conn_info.user_id if conn_info else "unknown"
            }
        )

    async def send_to_connection(self, connection_id: str, message: WebSocketMessage):
        """Send message to specific connection."""
        if connection_id not in self.connections:
            return False

        websocket = self.connections[connection_id]

        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(message.json())
                return True
            else:
                # Connection is not active, clean it up
                await self.disconnect(connection_id)
                return False
        except Exception as e:
            logger.error(f"Error sending WebSocket message to {connection_id}: {str(e)}")
            await self.disconnect(connection_id)
            return False

    async def send_to_user(self, user_id: str, message: WebSocketMessage):
        """Send message to all connections of a user."""
        if user_id not in self.user_connections:
            return 0

        sent_count = 0
        connections = self.user_connections[user_id].copy()

        for connection_id in connections:
            if await self.send_to_connection(connection_id, message):
                sent_count += 1

        return sent_count

    async def broadcast_to_channel(self, channel: str, message: WebSocketMessage):
        """Broadcast message to all subscribers of a channel."""
        if channel not in self.channel_subscriptions:
            return 0

        sent_count = 0
        connections = self.channel_subscriptions[channel].copy()

        for connection_id in connections:
            if await self.send_to_connection(connection_id, message):
                sent_count += 1

        # Also publish to Redis for multi-instance support
        if self.redis:
            await self.redis.publish(f"ws_channel:{channel}", message.json())

        return sent_count

    async def subscribe_to_channel(self, connection_id: str, channel: str):
        """Subscribe connection to a channel."""
        if connection_id not in self.connections:
            return False

        if channel not in self.channel_subscriptions:
            self.channel_subscriptions[channel] = set()

        self.channel_subscriptions[channel].add(connection_id)

        # Update connection info
        if connection_id in self.connection_info:
            self.connection_info[connection_id].channels.add(channel)

        return True

    async def unsubscribe_from_channel(self, connection_id: str, channel: str):
        """Unsubscribe connection from a channel."""
        if channel in self.channel_subscriptions:
            self.channel_subscriptions[channel].discard(connection_id)
            if not self.channel_subscriptions[channel]:
                del self.channel_subscriptions[channel]

        # Update connection info
        if connection_id in self.connection_info:
            self.connection_info[connection_id].channels.discard(channel)

    async def _heartbeat_monitor(self):
        """Monitor connection heartbeats."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                current_time = datetime.utcnow()
                stale_connections = []

                for connection_id, conn_info in self.connection_info.items():
                    time_since_heartbeat = (current_time - conn_info.last_heartbeat).total_seconds()

                    if time_since_heartbeat > self.heartbeat_interval * 2:
                        stale_connections.append(connection_id)

                # Clean up stale connections
                for connection_id in stale_connections:
                    await self.disconnect(connection_id)

            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {str(e)}")

    async def _process_message_queue(self):
        """Process queued messages."""
        while True:
            try:
                await asyncio.sleep(1)  # Process every second

                for connection_id, messages in list(self.message_queue.items()):
                    if connection_id in self.connections and messages:
                        message = messages.pop(0)
                        await self.send_to_connection(connection_id, message)

                        if not messages:
                            del self.message_queue[connection_id]

            except Exception as e:
                logger.error(f"Error processing message queue: {str(e)}")

    async def _redis_subscriber(self):
        """Subscribe to Redis pub/sub for multi-instance support."""
        if not self.redis:
            return

        pubsub = self.redis.pubsub()
        await pubsub.subscribe("ws_channel:*")

        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    try:
                        channel = message['channel'].decode().replace('ws_channel:', '')
                        data = json.loads(message['data'])
                        ws_message = WebSocketMessage.parse_obj(data)

                        # Broadcast to local connections
                        await self.broadcast_to_channel(channel, ws_message)

                    except Exception as e:
                        logger.error(f"Error processing Redis message: {str(e)}")

                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in Redis subscriber: {str(e)}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.connections),
            "unique_users": len(self.user_connections),
            "channels": len(self.channel_subscriptions),
            "queued_messages": sum(len(queue) for queue in self.message_queue.values()),
            "connections_by_role": self._get_connections_by_role()
        }

    def _get_connections_by_role(self) -> Dict[str, int]:
        """Get connection count by user role."""
        role_counts = {}
        for conn_info in self.connection_info.values():
            role = conn_info.user_role
            role_counts[role] = role_counts.get(role, 0) + 1
        return role_counts

# Global WebSocket manager instance - initialize without Redis initially
websocket_manager = EnhancedWebSocketManager(redis_client=None)

@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    """Main WebSocket connection endpoint."""
    connection_id = None
    try:
        # Accept WebSocket connection first
        await websocket.accept()

        # Try to authenticate user (Supabase token validation)
        user = await get_current_user_websocket(websocket)
        if not user:
            # Send authentication error message instead of closing immediately
            error_msg = {
                "type": "error",
                "data": {
                    "error": "authentication_required",
                    "message": "Authentication required. Provide a valid Supabase access token via 'token' query parameter or 'Authorization' header.",
                    "code": 4001
                }
            }
            await websocket.send_text(json.dumps(error_msg))
            await websocket.close(code=4001, reason="Authentication required")

        # Create a temporary connection ID for unauthenticated state
        from uuid import uuid4
        connection_id = str(uuid4())

        # Store the websocket temporarily
        websocket_manager.connections[connection_id] = websocket

        # Establish authenticated connection (connection already accepted)
        connection_id = await websocket_manager.connect(websocket, user, connection_id, already_accepted=True)

        # Message handling loop
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)

                # Process message
                await _handle_websocket_message(connection_id, message_data, user)

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket_manager.send_to_connection(connection_id, WebSocketMessage(
                    type=WebSocketEventType.SYSTEM_NOTIFICATION,
                    data={"error": "Invalid JSON format"}
                ))
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {str(e)}")
                await websocket_manager.send_to_connection(connection_id, WebSocketMessage(
                    type=WebSocketEventType.SYSTEM_NOTIFICATION,
                    data={"error": "Message processing failed"}
                ))

    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")

    finally:
        if connection_id:
            await websocket_manager.disconnect(connection_id)

async def _handle_websocket_message(connection_id: str, message_data: dict, user: User):
    """Handle incoming WebSocket messages."""
    try:
        message_type = message_data.get('type')
        data = message_data.get('data', {})

        if message_type == 'heartbeat':
            # Update heartbeat timestamp
            if connection_id in websocket_manager.connection_info:
                websocket_manager.connection_info[connection_id].last_heartbeat = datetime.utcnow()

            # Send heartbeat response
            await websocket_manager.send_to_connection(connection_id, WebSocketMessage(
                type=WebSocketEventType.HEARTBEAT,
                data={"status": "alive", "server_time": datetime.utcnow().isoformat()}
            ))

        elif message_type == 'subscribe':
            # Subscribe to channel
            channel = data.get('channel')
            if channel:
                await websocket_manager.subscribe_to_channel(connection_id, channel)
                await websocket_manager.send_to_connection(connection_id, WebSocketMessage(
                    type=WebSocketEventType.SYSTEM_NOTIFICATION,
                    data={"status": "subscribed", "channel": channel}
                ))

        elif message_type == 'unsubscribe':
            # Unsubscribe from channel
            channel = data.get('channel')
            if channel:
                await websocket_manager.unsubscribe_from_channel(connection_id, channel)
                await websocket_manager.send_to_connection(connection_id, WebSocketMessage(
                    type=WebSocketEventType.SYSTEM_NOTIFICATION,
                    data={"status": "unsubscribed", "channel": channel}
                ))

        elif message_type == 'typing':
            # Handle typing indicator
            patient_id = data.get('patient_id')
            if patient_id:
                # Broadcast typing indicator to relevant users
                await websocket_manager.broadcast_to_channel(
                    f"patient:{patient_id}",
                    WebSocketMessage(
                        type=WebSocketEventType.TYPING_INDICATOR,
                        data={
                            "user_id": str(user.id),
                            "user_name": user.full_name,
                            "patient_id": patient_id,
                            "typing": data.get('typing', True)
                        }
                    )
                )

        else:
            # Unknown message type
            await websocket_manager.send_to_connection(connection_id, WebSocketMessage(
                type=WebSocketEventType.SYSTEM_NOTIFICATION,
                data={"error": f"Unknown message type: {message_type}"}
            ))

    except Exception as e:
        logger.error(f"Error handling WebSocket message: {str(e)}")

@router.get("/stats")
async def get_websocket_stats(
    current_user: User = Depends(get_current_user)
):
    """Get WebSocket connection statistics."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    stats = websocket_manager.get_connection_stats()

    logger.info(
        "WebSocket stats retrieved",
        extra={
            "event_type": "websocket_stats_viewed",
            "user_id": str(current_user.id),
            "total_connections": stats["total_connections"]
        }
    )

    return stats

# Event broadcasting functions for use by other services
async def notify_patient_created(patient_id: UUID, patient_data: dict):
    """Notify about new patient creation."""
    await websocket_manager.broadcast_to_channel(
        WebSocketChannel.GLOBAL,
        WebSocketMessage(
            type=WebSocketEventType.PATIENT_CREATED,
            data={"patient_id": str(patient_id), "patient": patient_data}
        )
    )

async def notify_message_sent(patient_id: UUID, message_data: dict):
    """Notify about new message."""
    await websocket_manager.broadcast_to_channel(
        f"patient:{patient_id}",
        WebSocketMessage(
            type=WebSocketEventType.MESSAGE_SENT,
            data={"patient_id": str(patient_id), "message": message_data}
        )
    )

async def notify_quiz_progress_updated(patient_id: UUID, progress_data: dict):
    """Notify about quiz progress update."""
    await websocket_manager.broadcast_to_channel(
        f"patient:{patient_id}",
        WebSocketMessage(
            type=WebSocketEventType.QUIZ_PROGRESS_UPDATED,
            data={"patient_id": str(patient_id), "progress": progress_data}
        )
    )

async def notify_alert_created(alert_data: dict):
    """Notify about new alert."""
    await websocket_manager.broadcast_to_channel(
        WebSocketChannel.ALERTS,
        WebSocketMessage(
            type=WebSocketEventType.ALERT_CREATED,
            data=alert_data
        )
    )

async def notify_metrics_update(metrics_data: dict):
    """Notify about metrics update."""
    await websocket_manager.broadcast_to_channel(
        WebSocketChannel.METRICS,
        WebSocketMessage(
            type=WebSocketEventType.METRICS_UPDATE,
            data=metrics_data
        )
    )