"""
WebSocket Service - Consolidated WebSocket Management (QW-024).

Consolidates:
    - websocket_manager.py (ConnectionManager)
    - enhanced_websocket_manager.py (EnhancedConnectionManager)
    - websocket_events.py (WebSocketEventService)
    - websocket_heartbeat.py (HeartbeatMonitor)
    - Redis pub/sub integration

Total: 5 files → 1 file (80% reduction)

Version: 1.0.0 (QW-024)
"""

import logging
from typing import Dict, Set, Optional, Any, List
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import WebSocket
from redis import Redis
import jwt  # PyJWT - replaces python-jose to fix CVE-2024-23342

from app.config import settings
from app.schemas.websocket import (
    WebSocketEventType,
    create_websocket_message,
    FlowEventData,
    AlertEventData,
    MessageEventData,
)

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """
    Manages WebSocket connections, authentication, and broadcasting.

    Features:
    - Connection lifecycle management
    - JWT authentication
    - Room-based grouping (user, patient)
    - Event broadcasting
    - Heartbeat monitoring
    - Redis pub/sub integration

    Consolidates:
        - ConnectionManager (websocket_manager.py)
        - EnhancedConnectionManager (enhanced_websocket_manager.py)
        - HeartbeatMonitor (websocket_heartbeat.py)
    """

    def __init__(self, redis: Optional[Redis] = None):
        """
        Initialize WebSocket connection manager.

        Args:
            redis: Optional Redis client for pub/sub
        """
        self.redis = redis

        # Active connections by connection ID
        self.active_connections: Dict[str, WebSocket] = {}

        # User connections mapping
        self.user_connections: Dict[str, Set[str]] = {}

        # Patient room connections
        self.patient_rooms: Dict[str, Set[str]] = {}

        # Connection metadata
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}

        # Authenticated connections
        self.authenticated_connections: Set[str] = set()

        # Heartbeat tracking
        self.last_heartbeat: Dict[str, datetime] = {}
        self.heartbeat_timeout = 60  # seconds

        logger.info("WebSocketConnectionManager initialized")

    async def connect(
        self, websocket: WebSocket, connection_id: str, token: Optional[str] = None
    ) -> bool:
        """
        Accept and authenticate WebSocket connection.

        Args:
            websocket: WebSocket instance
            connection_id: Unique connection identifier
            token: Optional JWT token for authentication

        Returns:
            True if connection successful, False otherwise
        """
        try:
            await websocket.accept()

            self.active_connections[connection_id] = websocket
            self.connection_metadata[connection_id] = {
                "connected_at": datetime.now(timezone.utc),
                "user_id": None,
                "patient_id": None,
                "authenticated": False,
            }
            self.last_heartbeat[connection_id] = datetime.now(timezone.utc)

            # Authenticate if token provided
            if token:
                authenticated = await self._authenticate_connection(
                    connection_id, token
                )
                if not authenticated:
                    await self.disconnect(connection_id)
                    return False

            logger.info(f"WebSocket connected: {connection_id}")
            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    async def disconnect(self, connection_id: str) -> None:
        """
        Disconnect and clean up WebSocket connection.

        Args:
            connection_id: Connection identifier
        """
        if connection_id not in self.active_connections:
            return

        # Close connection
        try:
            websocket = self.active_connections[connection_id]
            await websocket.close()
        except Exception as e:
            logger.warning(f"Error closing websocket: {e}")

        # Clean up connections
        del self.active_connections[connection_id]

        # Clean up user connections
        metadata = self.connection_metadata.get(connection_id, {})
        user_id = metadata.get("user_id")
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        # Clean up patient rooms
        patient_id = metadata.get("patient_id")
        if patient_id and patient_id in self.patient_rooms:
            self.patient_rooms[patient_id].discard(connection_id)
            if not self.patient_rooms[patient_id]:
                del self.patient_rooms[patient_id]

        # Clean up metadata
        self.connection_metadata.pop(connection_id, None)
        self.authenticated_connections.discard(connection_id)
        self.last_heartbeat.pop(connection_id, None)

        logger.info(f"WebSocket disconnected: {connection_id}")

    async def _authenticate_connection(self, connection_id: str, token: str) -> bool:
        """
        Authenticate connection with JWT token.

        Args:
            connection_id: Connection identifier
            token: JWT token

        Returns:
            True if authenticated, False otherwise
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECURITY_SECRET_KEY,
                algorithms=[settings.SECURITY_ALGORITHM],
            )
            user_id = payload.get("sub")

            if not user_id:
                return False

            # Update metadata
            self.connection_metadata[connection_id]["user_id"] = user_id
            self.connection_metadata[connection_id]["authenticated"] = True
            self.authenticated_connections.add(connection_id)

            # Add to user connections
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)

            logger.info(f"Connection {connection_id} authenticated as {user_id}")
            return True

        except jwt.exceptions.PyJWTError as e:
            logger.error(f"JWT authentication error: {e}")
            return False

    async def join_patient_room(self, connection_id: str, patient_id: str) -> bool:
        """
        Add connection to patient room.

        Args:
            connection_id: Connection identifier
            patient_id: Patient identifier

        Returns:
            True if joined successfully
        """
        if connection_id not in self.active_connections:
            return False

        if patient_id not in self.patient_rooms:
            self.patient_rooms[patient_id] = set()

        self.patient_rooms[patient_id].add(connection_id)
        self.connection_metadata[connection_id]["patient_id"] = patient_id

        logger.info(f"Connection {connection_id} joined patient room {patient_id}")
        return True

    async def leave_patient_room(self, connection_id: str, patient_id: str) -> bool:
        """
        Remove connection from patient room.

        Args:
            connection_id: Connection identifier
            patient_id: Patient identifier

        Returns:
            True if left successfully
        """
        if patient_id in self.patient_rooms:
            self.patient_rooms[patient_id].discard(connection_id)
            if not self.patient_rooms[patient_id]:
                del self.patient_rooms[patient_id]

        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["patient_id"] = None

        return True

    async def broadcast_to_all(self, message: Dict[str, Any]) -> int:
        """
        Broadcast message to all connections.

        Args:
            message: Message dictionary

        Returns:
            Number of connections message was sent to
        """
        sent_count = 0
        dead_connections = []

        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Broadcast error for {connection_id}: {e}")
                dead_connections.append(connection_id)

        # Clean up dead connections
        for connection_id in dead_connections:
            await self.disconnect(connection_id)

        return sent_count

    async def broadcast_to_user(self, message: Dict[str, Any], user_id: str) -> int:
        """
        Broadcast message to all connections of a user.

        Args:
            message: Message dictionary
            user_id: User identifier

        Returns:
            Number of connections message was sent to
        """
        if user_id not in self.user_connections:
            return 0

        sent_count = 0
        dead_connections = []

        for connection_id in self.user_connections[user_id]:
            if connection_id not in self.active_connections:
                dead_connections.append(connection_id)
                continue

            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Broadcast error for {connection_id}: {e}")
                dead_connections.append(connection_id)

        # Clean up dead connections
        for connection_id in dead_connections:
            await self.disconnect(connection_id)

        return sent_count

    async def broadcast_to_patient_room(
        self, message: Dict[str, Any], patient_id: str
    ) -> int:
        """
        Broadcast message to patient room.

        Args:
            message: Message dictionary
            patient_id: Patient identifier

        Returns:
            Number of connections message was sent to
        """
        if patient_id not in self.patient_rooms:
            return 0

        sent_count = 0
        dead_connections = []

        for connection_id in self.patient_rooms[patient_id]:
            if connection_id not in self.active_connections:
                dead_connections.append(connection_id)
                continue

            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Broadcast error for {connection_id}: {e}")
                dead_connections.append(connection_id)

        # Clean up dead connections
        for connection_id in dead_connections:
            await self.disconnect(connection_id)

        return sent_count

    async def handle_heartbeat(self, connection_id: str) -> bool:
        """
        Handle heartbeat from connection.

        Args:
            connection_id: Connection identifier

        Returns:
            True if heartbeat accepted
        """
        if connection_id not in self.active_connections:
            return False

        self.last_heartbeat[connection_id] = datetime.now(timezone.utc)
        return True

    async def check_stale_connections(self) -> List[str]:
        """
        Check for stale connections (no heartbeat).

        Returns:
            List of stale connection IDs
        """
        stale = []
        now = datetime.now(timezone.utc)
        timeout = timedelta(seconds=self.heartbeat_timeout)

        for connection_id, last_beat in self.last_heartbeat.items():
            if now - last_beat > timeout:
                stale.append(connection_id)

        return stale

    async def cleanup_stale_connections(self) -> int:
        """
        Disconnect stale connections.

        Returns:
            Number of connections cleaned up
        """
        stale = await self.check_stale_connections()

        for connection_id in stale:
            await self.disconnect(connection_id)

        if stale:
            logger.info(f"Cleaned up {len(stale)} stale connections")

        return len(stale)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_connections": len(self.active_connections),
            "authenticated_connections": len(self.authenticated_connections),
            "users_connected": len(self.user_connections),
            "patient_rooms": len(self.patient_rooms),
        }


class WebSocketEventBroadcaster:
    """
    Service for broadcasting typed WebSocket events.

    Consolidates:
        - WebSocketEventService (websocket_events.py)
    """

    def __init__(
        self,
        connection_manager: WebSocketConnectionManager,
        redis: Optional[Redis] = None,
    ):
        """
        Initialize event broadcaster.

        Args:
            connection_manager: Connection manager instance
            redis: Optional Redis client
        """
        self.manager = connection_manager
        self.redis = redis

    async def broadcast_flow_event(
        self,
        event_type: WebSocketEventType,
        patient_id: UUID,
        flow_data: Dict[str, Any],
    ) -> int:
        """
        Broadcast flow event.

        Args:
            event_type: Event type
            patient_id: Patient UUID
            flow_data: Flow event data

        Returns:
            Number of connections reached
        """
        try:
            enriched_data = dict(flow_data or {})
            if not enriched_data.get("patient_id"):
                enriched_data["patient_id"] = patient_id
            flow_type = enriched_data.get("flow_type")
            if not flow_type:
                flow_type = "unknown"
            elif not isinstance(flow_type, str):
                flow_type = (
                    flow_type.value if hasattr(flow_type, "value") else str(flow_type)
                )
            enriched_data["flow_type"] = flow_type
            if enriched_data.get("current_day") is None:
                enriched_data["current_day"] = 0
            if not enriched_data.get("enrollment_date"):
                enriched_data["enrollment_date"] = datetime.now(timezone.utc)

            event_data = FlowEventData(**enriched_data)
            message = create_websocket_message(event_type, event_data)

            sent = await self.manager.broadcast_to_patient_room(
                message.dict(), str(patient_id)
            )

            logger.info(
                f"Flow event {event_type.value} sent to "
                f"{sent} connections for patient {patient_id}"
            )

            return sent

        except Exception as e:
            logger.error(f"Error broadcasting flow event: {e}")
            return 0

    async def broadcast_alert_event(
        self, event_type: WebSocketEventType, alert_data: Dict[str, Any]
    ) -> int:
        """
        Broadcast alert event.

        Args:
            event_type: Event type
            alert_data: Alert event data

        Returns:
            Number of connections reached
        """
        try:
            event_data = AlertEventData(**alert_data)
            message = create_websocket_message(event_type, event_data)

            patient_id = alert_data.get("patient_id")
            sent = await self.manager.broadcast_to_patient_room(
                message.dict(), str(patient_id)
            )

            return sent

        except Exception as e:
            logger.error(f"Error broadcasting alert event: {e}")
            return 0

    async def broadcast_message_event(
        self, event_type: WebSocketEventType, message_data: Dict[str, Any]
    ) -> int:
        """
        Broadcast message event.

        Args:
            event_type: Event type
            message_data: Message event data

        Returns:
            Number of connections reached
        """
        try:
            event_data = MessageEventData(**message_data)
            message = create_websocket_message(event_type, event_data)

            patient_id = message_data.get("patient_id")
            sent = await self.manager.broadcast_to_patient_room(
                message.dict(), str(patient_id)
            )

            return sent

        except Exception as e:
            logger.error(f"Error broadcasting message event: {e}")
            return 0

    async def publish_patient_event(
        self,
        event_type: WebSocketEventType,
        patient_id: UUID,
        data: Dict[str, Any],
    ) -> int:
        """
        Publish patient-specific event.

        Broadcasts to the patient's room with arbitrary event data.
        Used for patient lifecycle events (registration, status changes, etc.)

        Args:
            event_type: Event type
            patient_id: Patient UUID
            data: Event data dictionary

        Returns:
            Number of connections reached
        """
        try:
            message = {
                "type": event_type.value,
                "patient_id": str(patient_id),
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            sent_count = await self.manager.broadcast_to_patient_room(
                message, str(patient_id)
            )
            logger.info(
                f"Published patient event {event_type.value} for {patient_id} "
                f"to {sent_count} connections"
            )
            return sent_count
        except Exception as e:
            logger.error(f"Error publishing patient event: {e}")
            return 0


# Global instances
connection_manager = WebSocketConnectionManager()
websocket_events = WebSocketEventBroadcaster(connection_manager)


def get_connection_manager() -> WebSocketConnectionManager:
    """Get global connection manager instance."""
    return connection_manager


def get_event_broadcaster() -> WebSocketEventBroadcaster:
    """Get global event broadcaster instance."""
    return websocket_events
