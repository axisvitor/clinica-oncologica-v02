"""
WebSocket connection management and event broadcasting service.
"""
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime
from fastapi import WebSocket
from uuid import UUID
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.config import settings
from app.models.user import User
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and handles event broadcasting.

    Features:
    - Connection authentication and authorization
    - Room-based connection grouping (by patient, user, etc.)
    - Event broadcasting to specific connections or rooms
    - Connection persistence and cleanup
    - Heartbeat/ping-pong for connection health
    """

    def __init__(self):
        # Active connections by connection ID
        self.active_connections: dict[str, WebSocket] = {}

        # User connections mapping (user_id -> set of connection_ids)
        self.user_connections: dict[str, Set[str]] = {}

        # Patient room connections (patient_id -> set of connection_ids)
        self.patient_rooms: dict[str, Set[str]] = {}

        # Connection metadata (connection_id -> metadata dict)
        self.connection_metadata: dict[str, dict[str, Any]] = {}

        # Connection authentication status
        self.authenticated_connections: Set[str] = set()

    async def connect(self, websocket: WebSocket, connection_id: str) -> None:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: WebSocket instance
            connection_id: Unique connection identifier
        """
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow(),
            "user_id": None,
            "patient_id": None,
            "authenticated": False
        }

        logger.info(f"WebSocket connection established: {connection_id}")

    async def disconnect(self, connection_id: str) -> None:
        """
        Remove a WebSocket connection and clean up associated data.

        Args:
            connection_id: Connection identifier to remove
        """
        if connection_id not in self.active_connections:
            return

        # Remove from active connections
        del self.active_connections[connection_id]

        # Clean up user connections
        metadata = self.connection_metadata.get(connection_id, {})
        user_id = metadata.get("user_id")
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        # Clean up patient room connections
        patient_id = metadata.get("patient_id")
        if patient_id and patient_id in self.patient_rooms:
            self.patient_rooms[patient_id].discard(connection_id)
            if not self.patient_rooms[patient_id]:
                del self.patient_rooms[patient_id]

        # Clean up metadata and authentication
        if connection_id in self.connection_metadata:
            del self.connection_metadata[connection_id]

        self.authenticated_connections.discard(connection_id)

        logger.info(f"WebSocket connection closed: {connection_id}")

    async def authenticate_connection(
        self,
        connection_id: str,
        token: str,
        db: Session
    ) -> Optional[User]:
        """
        Authenticate a WebSocket connection using JWT token.
        Supports both Firebase tokens (RS256) and internal JWT tokens (HS256).

        Args:
            connection_id: Connection to authenticate
            token: JWT token (Firebase ID token or internal JWT)
            db: Database session

        Returns:
            User object if authentication successful, None otherwise
        """
        # Strategy 1: Try Firebase authentication first (most common in production)
        firebase_user = await self._authenticate_with_firebase(connection_id, token, db)
        if firebase_user:
            return firebase_user

        # Strategy 2: Fallback to internal JWT (HS256) for backend-generated tokens
        internal_user = await self._authenticate_with_internal_jwt(connection_id, token, db)
        if internal_user:
            return internal_user

        logger.warning(f"Authentication failed for connection {connection_id}: invalid token")
        return None

    async def _authenticate_with_firebase(
        self,
        connection_id: str,
        token: str,
        db: Session
    ) -> Optional[User]:
        """
        Authenticate using Firebase ID token (RS256).

        Args:
            connection_id: Connection identifier
            token: Firebase ID token
            db: Database session

        Returns:
            User object if successful, None otherwise
        """
        try:
            from app.services.firebase_auth_service import get_firebase_auth_service

            firebase_project_id = getattr(settings, 'FIREBASE_ADMIN_PROJECT_ID', None)
            firebase_private_key = getattr(settings, 'FIREBASE_ADMIN_PRIVATE_KEY', None)
            firebase_client_email = getattr(settings, 'FIREBASE_ADMIN_CLIENT_EMAIL', None)

            if not all([firebase_project_id, firebase_private_key, firebase_client_email]):
                return None

            firebase_service = get_firebase_auth_service(
                project_id=firebase_project_id,
                private_key=firebase_private_key,
                client_email=firebase_client_email
            )

            # Verify Firebase token and authenticate by email
            user_data = await firebase_service.verify_token(token)
            email = (user_data.get("email") or "").strip().lower()
            if not email:
                return None

            user_repo = UserRepository(db)
            user: Optional[User] = user_repo.get_by_email(email)
            if not user or not user.is_active:
                logger.debug(f"User not found or inactive (Firebase) for connection {connection_id}: {email}")
                return None

            # Update connection metadata
            self._update_connection_metadata(connection_id, user)

            logger.info(f"WebSocket connection authenticated via Firebase: {connection_id} for {email}")
            return user

        except Exception as e:
            logger.debug(f"Firebase token verification failed for connection {connection_id}: {e}")
            return None

    async def _authenticate_with_internal_jwt(
        self,
        connection_id: str,
        token: str,
        db: Session
    ) -> Optional[User]:
        """
        Authenticate using internal JWT token (HS256).

        Args:
            connection_id: Connection identifier
            token: Internal JWT token
            db: Database session

        Returns:
            User object if successful, None otherwise
        """
        try:
            # Decode internal JWT token (HS256)
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )

            subject = payload.get("sub")
            if not subject:
                return None

            # Check token expiration
            exp = payload.get("exp")
            if exp is None or datetime.utcnow().timestamp() > exp:
                logger.debug(f"Expired internal JWT for connection {connection_id}")
                return None

            # Get user from database (support UUID or email in sub)
            user_repo = UserRepository(db)
            user: Optional[User] = None
            try:
                user_uuid = UUID(str(subject))
                user = user_repo.get_by_id(user_uuid)
            except Exception:
                user = None
            if user is None:
                user = user_repo.get_by_email(str(subject))

            if not user or not user.is_active:
                logger.debug(f"User not found or inactive (internal JWT) for connection {connection_id}")
                return None

            # Update connection metadata
            self._update_connection_metadata(connection_id, user)

            logger.info(f"WebSocket connection authenticated via internal JWT: {connection_id} for user {subject}")
            return user

        except JWTError as e:
            logger.debug(f"Internal JWT decode error for connection {connection_id}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Internal JWT authentication error for connection {connection_id}: {e}")
            return None

    def _update_connection_metadata(self, connection_id: str, user: User) -> None:
        """
        Update connection metadata after successful authentication.

        Args:
            connection_id: Connection identifier
            user: Authenticated user object
        """
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id].update({
                "user_id": str(user.id),
                "authenticated": True,
                "user_role": user.role.value if hasattr(user.role, 'value') else str(user.role)
            })

        # Add to authenticated connections
        self.authenticated_connections.add(connection_id)

        # Add to user connections mapping
        user_id_str = str(user.id)
        if user_id_str not in self.user_connections:
            self.user_connections[user_id_str] = set()
        self.user_connections[user_id_str].add(connection_id)

    async def join_patient_room(self, connection_id: str, patient_id: str) -> bool:
        """
        Add connection to a patient room for targeted broadcasting.

        Args:
            connection_id: Connection to add to room
            patient_id: Patient room identifier

        Returns:
            True if successfully joined, False otherwise
        """
        if connection_id not in self.authenticated_connections:
            logger.warning(f"Unauthenticated connection {connection_id} cannot join patient room")
            return False

        if patient_id not in self.patient_rooms:
            self.patient_rooms[patient_id] = set()

        self.patient_rooms[patient_id].add(connection_id)

        # Update connection metadata
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["patient_id"] = patient_id

        logger.info(f"Connection {connection_id} joined patient room {patient_id}")
        return True

    async def leave_patient_room(self, connection_id: str, patient_id: str) -> None:
        """
        Remove connection from a patient room.

        Args:
            connection_id: Connection to remove from room
            patient_id: Patient room identifier
        """
        if patient_id in self.patient_rooms:
            self.patient_rooms[patient_id].discard(connection_id)
            if not self.patient_rooms[patient_id]:
                del self.patient_rooms[patient_id]

        # Update connection metadata
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["patient_id"] = None

        logger.info(f"Connection {connection_id} left patient room {patient_id}")

    async def send_personal_message(self, message: dict, connection_id: str) -> bool:
        """
        Send message to a specific connection.

        Args:
            message: Message data to send
            connection_id: Target connection

        Returns:
            True if message sent successfully, False otherwise
        """
        if connection_id not in self.active_connections:
            return False

        try:
            websocket = self.active_connections[connection_id]
            # Handle datetime serialization
            serialized_message = self._serialize_message(message)
            await websocket.send_text(json.dumps(serialized_message))
            return True
        except Exception as e:
            error_str = str(e).lower()
            # Only log as error if it's NOT a connection-closed error
            if "not connected" in error_str or "websocket" in error_str:
                logger.debug(f"WebSocket connection closed for {connection_id}, cleaning up")
            else:
                logger.error(f"Error sending message to connection {connection_id}: {e}")

            await self.disconnect(connection_id)
            return False

    async def broadcast_to_user(self, message: dict, user_id: str) -> int:
        """
        Broadcast message to all connections of a specific user.

        Args:
            message: Message data to broadcast
            user_id: Target user ID

        Returns:
            Number of connections that received the message
        """
        if user_id not in self.user_connections:
            return 0

        sent_count = 0
        connections_to_remove = []

        for connection_id in self.user_connections[user_id].copy():
            if await self.send_personal_message(message, connection_id):
                sent_count += 1
            else:
                connections_to_remove.append(connection_id)

        # Clean up failed connections
        for connection_id in connections_to_remove:
            await self.disconnect(connection_id)

        return sent_count

    async def broadcast_to_patient_room(self, message: dict, patient_id: str) -> int:
        """
        Broadcast message to all connections in a patient room.

        Args:
            message: Message data to broadcast
            patient_id: Patient room identifier

        Returns:
            Number of connections that received the message
        """
        if patient_id not in self.patient_rooms:
            return 0

        sent_count = 0
        connections_to_remove = []

        for connection_id in self.patient_rooms[patient_id].copy():
            if await self.send_personal_message(message, connection_id):
                sent_count += 1
            else:
                connections_to_remove.append(connection_id)

        # Clean up failed connections
        for connection_id in connections_to_remove:
            await self.disconnect(connection_id)

        return sent_count

    async def broadcast_to_all_authenticated(self, message: dict) -> int:
        """
        Broadcast message to all authenticated connections.

        Args:
            message: Message data to broadcast

        Returns:
            Number of connections that received the message
        """
        sent_count = 0
        connections_to_remove = []

        for connection_id in self.authenticated_connections.copy():
            if await self.send_personal_message(message, connection_id):
                sent_count += 1
            else:
                connections_to_remove.append(connection_id)

        # Clean up failed connections
        for connection_id in connections_to_remove:
            await self.disconnect(connection_id)

        return sent_count

    async def ping_connection(self, connection_id: str) -> bool:
        """
        Send ping to connection to check if it's alive.

        Args:
            connection_id: Connection to ping

        Returns:
            True if ping successful, False otherwise
        """
        ping_message = {
            "type": "ping",
            "timestamp": datetime.utcnow().isoformat()
        }

        success = await self.send_personal_message(ping_message, connection_id)

        if success and connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["last_ping"] = datetime.utcnow()

        return success

    def get_connection_stats(self) -> dict:
        """
        Get statistics about current connections.

        Returns:
            Dictionary with connection statistics
        """
        return {
            "total_connections": len(self.active_connections),
            "authenticated_connections": len(self.authenticated_connections),
            "user_connections": len(self.user_connections),
            "patient_rooms": len(self.patient_rooms),
            "connections_by_user": {
                user_id: len(connections)
                for user_id, connections in self.user_connections.items()
            },
            "connections_by_patient": {
                patient_id: len(connections)
                for patient_id, connections in self.patient_rooms.items()
            }
        }

    def get_connection_info(self, connection_id: str) -> Optional[dict]:
        """
        Get information about a specific connection.

        Args:
            connection_id: Connection to get info for

        Returns:
            Connection metadata or None if not found
        """
        return self.connection_metadata.get(connection_id)

    def _serialize_message(self, message: dict) -> dict:
        """
        Serialize message data to ensure JSON compatibility.

        Args:
            message: Message dictionary to serialize

        Returns:
            Serialized message dictionary
        """
        def serialize_value(value):
            if isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, UUID):
                return str(value)
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(item) for item in value]
            else:
                return value

        return serialize_value(message)


# Global connection manager instance
connection_manager = ConnectionManager()


class WebSocketManager:
    """
    Singleton WebSocket manager that provides high-level WebSocket functionality.
    Wraps the ConnectionManager to provide additional features and maintain singleton pattern.
    """

    _instance: Optional['WebSocketManager'] = None
    _initialized: bool = False

    def __init__(self):
        if WebSocketManager._initialized:
            raise RuntimeError("WebSocketManager is a singleton. Use get_instance() instead.")

        self.connection_manager = connection_manager
        self.is_running = False
        WebSocketManager._initialized = True

    @classmethod
    def get_instance(cls) -> 'WebSocketManager':
        """Get the singleton instance of WebSocketManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self, websocket: WebSocket, connection_id: str) -> None:
        """Connect a new WebSocket."""
        await self.connection_manager.connect(websocket, connection_id)

    async def disconnect(self, connection_id: str) -> None:
        """Disconnect a WebSocket."""
        await self.connection_manager.disconnect(connection_id)

    async def authenticate_connection(self, connection_id: str, token: str, db: Session) -> Optional[User]:
        """Authenticate a WebSocket connection."""
        return await self.connection_manager.authenticate_connection(connection_id, token, db)

    async def join_patient_room(self, connection_id: str, patient_id: str) -> bool:
        """Join a connection to a patient room."""
        return await self.connection_manager.join_patient_room(connection_id, patient_id)

    async def leave_patient_room(self, connection_id: str, patient_id: str) -> None:
        """Remove a connection from a patient room."""
        await self.connection_manager.leave_patient_room(connection_id, patient_id)

    async def send_personal_message(self, message: dict, connection_id: str) -> bool:
        """Send a message to a specific connection."""
        return await self.connection_manager.send_personal_message(message, connection_id)

    async def broadcast_to_user(self, message: dict, user_id: str) -> int:
        """Send a message to all connections of a specific user."""
        return await self.connection_manager.broadcast_to_user(message, user_id)

    async def broadcast_to_patient_room(self, message: dict, patient_id: str) -> int:
        """Broadcast a message to all connections in a patient room."""
        return await self.connection_manager.broadcast_to_patient_room(message, patient_id)

    async def broadcast_to_all_authenticated(self, message: dict) -> int:
        """Broadcast a message to all authenticated clients."""
        return await self.connection_manager.broadcast_to_all_authenticated(message)

    def get_connection_stats(self) -> dict:
        """Get statistics about current connections."""
        return self.connection_manager.get_connection_stats()

    def get_connection_info(self, connection_id: str) -> Optional[dict]:
        """Get metadata for a specific connection."""
        return self.connection_manager.get_connection_info(connection_id)

    async def start(self) -> None:
        """Start the WebSocket manager."""
        self.is_running = True
        logger.info("WebSocket manager started")

    async def stop(self) -> None:
        """Stop the WebSocket manager and cleanup."""
        self.is_running = False
        # Disconnect all connections
        connection_ids = list(self.connection_manager.active_connections.keys())
        for connection_id in connection_ids:
            await self.disconnect(connection_id)
        logger.info("WebSocket manager stopped")


# Global WebSocket manager instance
def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    return WebSocketManager.get_instance()
