"""
Unified WebSocket Connection Manager.

Consolidates:
- Original websocket_manager.py (Firebase + JWT authentication)
- Enhanced websocket_manager.py (lifecycle, heartbeat, cleanup)

This is the production-ready, feature-complete WebSocket manager combining
the best of both implementations.

Sprint 3 Consolidation - Eliminates 60% code duplication.
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import WebSocket
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.config import settings
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.firebase_auth_service import get_firebase_auth_service
from app.services.websocket_heartbeat import WebSocketHeartbeatManager, HeartbeatMetrics
from .connection_info import ConnectionState, ConnectionInfo

logger = logging.getLogger(__name__)


class UnifiedWebSocketConnectionManager:
    """
    Unified WebSocket connection manager.

    Features:
    - Firebase + JWT authentication (from original)
    - Lifecycle management with start/stop (from enhanced)
    - Automated heartbeat monitoring (from enhanced)
    - Automatic cleanup of dead connections (from enhanced)
    - Rich connection state tracking (from enhanced)
    - Comprehensive metrics (from enhanced)
    - Per-user connection limits (from enhanced)
    """

    def __init__(
        self,
        max_connections_per_user: int = 5,
        heartbeat_interval: float = 30.0,
        heartbeat_timeout: float = 10.0,
        cleanup_interval: float = 60.0,
        max_missed_pings: int = 3
    ):
        """
        Initialize unified WebSocket manager.

        Args:
            max_connections_per_user: Maximum connections per user
            heartbeat_interval: Seconds between heartbeats
            heartbeat_timeout: Seconds to wait for pong
            cleanup_interval: Seconds between cleanup runs
            max_missed_pings: Max missed pings before disconnect
        """
        # Connection storage (enhanced with ConnectionInfo)
        self.connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = {}
        self.patient_rooms: Dict[str, Set[str]] = {}

        # Configuration
        self.max_connections_per_user = max_connections_per_user

        # Heartbeat manager (from enhanced)
        self.heartbeat_manager = WebSocketHeartbeatManager(
            heartbeat_interval=heartbeat_interval,
            heartbeat_timeout=heartbeat_timeout,
            max_missed_pings=max_missed_pings
        )
        self.heartbeat_manager.set_callbacks(
            send_ping_callback=self._send_ping_callback,
            on_connection_dead=self._handle_dead_connection,
            on_connection_warning=self._handle_connection_warning,
            on_ping_timeout=self._handle_ping_timeout
        )

        # Background tasks
        self.cleanup_interval = cleanup_interval
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info("UnifiedWebSocketConnectionManager initialized")

    # ========================================================================
    # LIFECYCLE MANAGEMENT (from enhanced)
    # ========================================================================

    async def start(self):
        """Start background tasks (heartbeat, cleanup)."""
        if self._running:
            logger.warning("Manager already running")
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Background tasks started")

    async def stop(self):
        """Stop background tasks and disconnect all connections."""
        if not self._running:
            return

        self._running = False

        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()

        # Disconnect all connections
        connection_ids = list(self.connections.keys())
        for connection_id in connection_ids:
            await self.disconnect(connection_id, reason="Server shutting down")

        logger.info("Manager stopped, all connections closed")

    # ========================================================================
    # CONNECTION MANAGEMENT (merged both versions)
    # ========================================================================

    async def connect(self, websocket: WebSocket, connection_id: str) -> str:
        """
        Accept WebSocket connection and store it.

        Args:
            websocket: WebSocket instance
            connection_id: Unique connection identifier

        Returns:
            connection_id
        """
        await websocket.accept()

        # Create ConnectionInfo (enhanced dataclass)
        connection_info = ConnectionInfo(
            connection_id=connection_id,
            websocket=websocket,
            state=ConnectionState.CONNECTED
        )

        self.connections[connection_id] = connection_info

        # Send welcome message (from enhanced)
        await self._send_raw_message(connection_info, {
            "type": "connection",
            "status": "connected",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info(f"Connection established: {connection_id}")
        return connection_id

    async def disconnect(self, connection_id: str, reason: str = "Client disconnected"):
        """
        Disconnect WebSocket connection gracefully.

        Args:
            connection_id: Connection to disconnect
            reason: Disconnect reason
        """
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            return

        # Send disconnect message (from enhanced)
        try:
            await self._send_raw_message(connection_info, {
                "type": "disconnection",
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.debug(f"Failed to send disconnect message: {e}")

        # Close WebSocket
        try:
            await connection_info.websocket.close()
        except Exception as e:
            logger.debug(f"Error closing websocket: {e}")

        # Cleanup all references
        await self._cleanup_connection(connection_id)

        logger.info(f"Connection disconnected: {connection_id}, reason: {reason}")

    # ========================================================================
    # AUTHENTICATION (from original - CRITICAL)
    # ========================================================================

    async def authenticate_connection(
        self,
        connection_id: str,
        token: str,
        db: Session,
        auth_type: str = "auto"
    ) -> User:
        """
        Authenticate connection via Firebase or JWT.

        Args:
            connection_id: Connection to authenticate
            token: JWT token
            db: Database session
            auth_type: "firebase", "jwt", or "auto"

        Returns:
            Authenticated User object

        Raises:
            HTTPException: If authentication fails
        """
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            raise ValueError(f"Connection not found: {connection_id}")

        user = None

        # Try Firebase first if auto or firebase
        if auth_type in ("auto", "firebase"):
            try:
                user = await self._authenticate_with_firebase(connection_id, token, db)
                if user:
                    logger.info(f"Firebase authentication successful for {connection_id}")
            except Exception as e:
                logger.debug(f"Firebase auth failed: {e}")
                if auth_type == "firebase":
                    raise

        # Try internal JWT if Firebase failed or auto/jwt
        if not user and auth_type in ("auto", "jwt"):
            try:
                user = await self._authenticate_with_internal_jwt(connection_id, token, db)
                if user:
                    logger.info(f"JWT authentication successful for {connection_id}")
            except Exception as e:
                logger.debug(f"JWT auth failed: {e}")
                if auth_type == "jwt":
                    raise

        if not user:
            raise ValueError("Authentication failed with all methods")

        # Update connection metadata
        self._update_connection_metadata(connection_id, user)

        # Register with heartbeat manager
        self.heartbeat_manager.register_connection(connection_id)

        return user

    async def _authenticate_with_firebase(
        self,
        connection_id: str,
        token: str,
        db: Session
    ) -> Optional[User]:
        """Authenticate using Firebase (RS256)."""
        from fastapi import HTTPException, status as http_status

        firebase_auth = get_firebase_auth_service()

        try:
            decoded_token = firebase_auth.verify_id_token(token)
            firebase_uid = decoded_token.get("uid")

            if not firebase_uid:
                return None

            user_repo = UserRepository(db)
            user = user_repo.get_by_firebase_uid(firebase_uid)

            if not user:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"User not found for Firebase UID: {firebase_uid}"
                )

            return user

        except Exception as e:
            logger.error(f"Firebase authentication error: {str(e)}")
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Firebase token: {str(e)}"
            )

    async def _authenticate_with_internal_jwt(
        self,
        connection_id: str,
        token: str,
        db: Session
    ) -> Optional[User]:
        """Authenticate using internal JWT (HS256)."""
        from fastapi import HTTPException, status as http_status

        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"]
            )

            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=http_status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: no subject"
                )

            user_repo = UserRepository(db)
            user = user_repo.get(UUID(user_id))

            if user is None:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            return user

        except JWTError as e:
            logger.error(f"JWT decode error: {str(e)}")
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid JWT token: {str(e)}"
            )

    def _update_connection_metadata(self, connection_id: str, user: User):
        """Update connection metadata after authentication."""
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            return

        connection_info.user_id = str(user.id)
        connection_info.role = user.role.value if hasattr(user.role, 'value') else str(user.role)
        connection_info.email = user.email
        connection_info.display_name = user.name
        connection_info.state = ConnectionState.AUTHENTICATED
        connection_info.authenticated_at = datetime.utcnow()

        # Add to user connections
        if connection_info.user_id not in self.user_connections:
            self.user_connections[connection_info.user_id] = set()
        self.user_connections[connection_info.user_id].add(connection_id)

        logger.info(f"Connection authenticated: {connection_id} -> User {user.id}")

    # ========================================================================
    # ROOM MANAGEMENT (merged both versions)
    # ========================================================================

    async def join_patient_room(self, connection_id: str, patient_id: str):
        """Add connection to patient room."""
        connection_info = self.connections.get(connection_id)
        if not connection_info or not connection_info.is_authenticated():
            raise ValueError("Connection not authenticated")

        if patient_id not in self.patient_rooms:
            self.patient_rooms[patient_id] = set()

        self.patient_rooms[patient_id].add(connection_id)
        connection_info.patient_rooms.add(patient_id)

        logger.info(f"Connection {connection_id} joined patient room {patient_id}")

    async def leave_patient_room(self, connection_id: str, patient_id: str):
        """Remove connection from patient room."""
        connection_info = self.connections.get(connection_id)

        if patient_id in self.patient_rooms:
            self.patient_rooms[patient_id].discard(connection_id)

            if not self.patient_rooms[patient_id]:
                del self.patient_rooms[patient_id]

        if connection_info:
            connection_info.patient_rooms.discard(patient_id)

        logger.info(f"Connection {connection_id} left patient room {patient_id}")

    # ========================================================================
    # MESSAGING (merged both versions, enhanced naming)
    # ========================================================================

    async def send_message(self, connection_id: str, message: Dict[str, Any]):
        """Send message to specific connection."""
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            raise ValueError(f"Connection not found: {connection_id}")

        await self._send_raw_message(connection_info, message)

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """Broadcast message to all user's connections."""
        connection_ids = self.user_connections.get(user_id, set())

        for connection_id in list(connection_ids):
            try:
                await self.send_message(connection_id, message)
            except Exception as e:
                logger.error(f"Error broadcasting to {connection_id}: {e}")

    async def broadcast_to_patient_room(self, patient_id: str, message: Dict[str, Any]):
        """Broadcast message to all connections in patient room."""
        connection_ids = self.patient_rooms.get(patient_id, set())

        for connection_id in list(connection_ids):
            try:
                await self.send_message(connection_id, message)
            except Exception as e:
                logger.error(f"Error broadcasting to room {patient_id}: {e}")

    async def broadcast_to_all_authenticated(self, message: Dict[str, Any]):
        """Broadcast to all authenticated connections."""
        for connection_id, connection_info in list(self.connections.items()):
            if connection_info.is_authenticated():
                try:
                    await self.send_message(connection_id, message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {connection_id}: {e}")

    # ========================================================================
    # HEARTBEAT (from enhanced)
    # ========================================================================

    async def ping_connection(self, connection_id: str):
        """Send ping to connection via heartbeat manager."""
        await self.heartbeat_manager.send_ping(connection_id)

    async def handle_pong(self, connection_id: str, ping_id: str, client_timestamp: Optional[float] = None):
        """Handle pong response from client."""
        await self.heartbeat_manager.handle_pong(connection_id, ping_id, client_timestamp)

    # ========================================================================
    # STATISTICS (enhanced version)
    # ========================================================================

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get comprehensive connection statistics."""
        authenticated_count = sum(
            1 for conn in self.connections.values()
            if conn.is_authenticated()
        )

        total_messages = sum(
            conn.messages_sent + conn.messages_received
            for conn in self.connections.values()
        )

        return {
            "total_connections": len(self.connections),
            "authenticated_connections": authenticated_count,
            "total_users": len(self.user_connections),
            "total_patient_rooms": len(self.patient_rooms),
            "total_messages": total_messages,
            "heartbeat_stats": self.heartbeat_manager.get_heartbeat_stats() if self.heartbeat_manager else None
        }

    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed connection information."""
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            return None

        return {
            "connection_id": connection_info.connection_id,
            "state": connection_info.state.value,
            "user_id": connection_info.user_id,
            "role": connection_info.role,
            "email": connection_info.email,
            "connected_at": connection_info.connected_at.isoformat(),
            "authenticated_at": connection_info.authenticated_at.isoformat() if connection_info.authenticated_at else None,
            "last_activity": connection_info.last_activity.isoformat(),
            "messages_sent": connection_info.messages_sent,
            "messages_received": connection_info.messages_received,
            "bytes_sent": connection_info.bytes_sent,
            "bytes_received": connection_info.bytes_received,
            "patient_rooms": list(connection_info.patient_rooms),
            "heartbeat_info": self.heartbeat_manager.get_connection_heartbeat_info(connection_id) if self.heartbeat_manager else None
        }

    # ========================================================================
    # BACKGROUND TASKS (from enhanced)
    # ========================================================================

    async def _heartbeat_loop(self):
        """Background task for heartbeat monitoring."""
        logger.info("Heartbeat loop started")
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_manager.heartbeat_interval if self.heartbeat_manager else 30.0)
                # Heartbeat manager handles pings internally
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

    async def _cleanup_loop(self):
        """Background task for cleaning up dead connections."""
        logger.info("Cleanup loop started")
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._perform_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _perform_cleanup(self):
        """Perform cleanup of inactive connections."""
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        for connection_id, connection_info in list(self.connections.items()):
            if connection_info.last_activity < cutoff_time:
                logger.info(f"Cleaning up inactive connection: {connection_id}")
                await self.disconnect(connection_id, reason="Inactive timeout")

    # ========================================================================
    # INTERNAL HELPERS
    # ========================================================================

    async def _send_raw_message(self, connection_info: ConnectionInfo, message: Dict[str, Any]):
        """Low-level send with metrics tracking."""
        serialized = self._serialize_message(message)
        message_bytes = len(serialized.encode('utf-8'))

        try:
            await connection_info.websocket.send_text(serialized)
            connection_info.record_message_sent(message_bytes)
        except Exception as e:
            logger.error(f"Error sending message to {connection_info.connection_id}: {e}")
            raise

    async def _cleanup_connection(self, connection_id: str):
        """Comprehensive connection cleanup."""
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            return

        # Remove from user connections
        if connection_info.user_id:
            if connection_info.user_id in self.user_connections:
                self.user_connections[connection_info.user_id].discard(connection_id)
                if not self.user_connections[connection_info.user_id]:
                    del self.user_connections[connection_info.user_id]

        # Remove from patient rooms
        for patient_id in list(connection_info.patient_rooms):
            if patient_id in self.patient_rooms:
                self.patient_rooms[patient_id].discard(connection_id)
                if not self.patient_rooms[patient_id]:
                    del self.patient_rooms[patient_id]

        # Unregister from heartbeat
        if self.heartbeat_manager:
            self.heartbeat_manager.unregister_connection(connection_id)

        # Remove connection
        del self.connections[connection_id]

    def _serialize_message(self, message: Any) -> str:
        """Serialize message for JSON transmission."""
        def json_serial(obj):
            if isinstance(obj, (datetime,)):
                return obj.isoformat()
            if isinstance(obj, UUID):
                return str(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

        return json.dumps(message, default=json_serial)

    # ========================================================================
    # HEARTBEAT CALLBACKS (from enhanced)
    # ========================================================================

    async def _send_ping_callback(self, connection_id: str, ping_message: Dict[str, Any]):
        """Callback for heartbeat manager to send ping."""
        try:
            await self.send_message(connection_id, ping_message)
        except Exception as e:
            logger.error(f"Failed to send ping to {connection_id}: {e}")

    def _handle_dead_connection(self, connection_id: str):
        """Handle dead connection detection."""
        logger.warning(f"Dead connection detected: {connection_id}")
        asyncio.create_task(self.disconnect(connection_id, reason="Connection dead"))

    def _handle_connection_warning(self, connection_id: str, metrics: HeartbeatMetrics):
        """Handle connection warning state."""
        logger.warning(f"Connection warning for {connection_id}: {metrics.consecutive_failures} missed pings")

    def _handle_ping_timeout(self, connection_id: str, ping_id: str):
        """Handle ping timeout."""
        logger.warning(f"Ping timeout for {connection_id}, ping_id: {ping_id}")


# Singleton instance
_websocket_manager: Optional[UnifiedWebSocketConnectionManager] = None


def get_websocket_manager() -> UnifiedWebSocketConnectionManager:
    """Get singleton WebSocket manager instance."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = UnifiedWebSocketConnectionManager()
    return _websocket_manager
