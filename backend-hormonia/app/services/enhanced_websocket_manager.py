"""
Enhanced WebSocket connection management with robust features.

This module provides an enhanced WebSocket connection manager that includes:
- Robust connection pooling and lifecycle management
- Heartbeat system for connection health monitoring
- Automatic cleanup for disconnected clients
- Connection state tracking and metrics
- Resource management and memory optimization
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Any, List
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.services.websocket_manager import ConnectionManager
from app.services.websocket_heartbeat import WebSocketHeartbeatManager, HeartbeatMetrics

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class ConnectionInfo:
    """Enhanced connection information with state tracking."""
    connection_id: str
    websocket: WebSocket
    state: ConnectionState = ConnectionState.CONNECTING
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: datetime = field(default_factory=datetime.utcnow)
    last_pong: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    patient_id: Optional[str] = None
    authenticated: bool = False
    user_role: Optional[str] = None
    ping_count: int = 0
    pong_count: int = 0
    missed_pings: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EnhancedWebSocketConnectionManager:
    """
    Enhanced WebSocket connection manager with robust features.
    
    Features:
    - Connection pooling with state management
    - Heartbeat system with configurable intervals
    - Automatic cleanup for dead connections
    - Connection health monitoring
    - Resource usage tracking
    - Graceful shutdown handling
    """
    
    def __init__(
        self,
        heartbeat_interval: int = 30,  # seconds
        heartbeat_timeout: int = 10,   # seconds
        max_missed_pings: int = 3,
        cleanup_interval: int = 60,    # seconds
        max_connections_per_user: int = 5
    ):
        """
        Initialize enhanced WebSocket connection manager.
        
        Args:
            heartbeat_interval: Interval between heartbeat pings (seconds)
            heartbeat_timeout: Timeout for heartbeat responses (seconds)
            max_missed_pings: Maximum missed pings before disconnection
            cleanup_interval: Interval for cleanup tasks (seconds)
            max_connections_per_user: Maximum connections per user
        """
        # Connection storage
        self.connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = {}
        self.patient_rooms: Dict[str, Set[str]] = {}
        
        # Configuration
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.max_missed_pings = max_missed_pings
        self.cleanup_interval = cleanup_interval
        self.max_connections_per_user = max_connections_per_user
        
        # Heartbeat manager
        self.heartbeat_manager = WebSocketHeartbeatManager(
            heartbeat_interval=heartbeat_interval,
            heartbeat_timeout=heartbeat_timeout,
            max_missed_pings=max_missed_pings,
            cleanup_interval=cleanup_interval
        )
        
        # Set heartbeat callbacks
        self.heartbeat_manager.set_callbacks(
            on_connection_dead=self._handle_dead_connection,
            on_connection_warning=self._handle_connection_warning,
            on_ping_timeout=self._handle_ping_timeout
        )
        
        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics
        self.total_connections_created = 0
        self.total_connections_closed = 0
        self.total_messages_sent = 0
        self.total_messages_received = 0
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        
        logger.info("Enhanced WebSocket connection manager initialized")
    
    async def start(self) -> None:
        """Start the connection manager and background tasks."""
        if self._running:
            return
            
        self._running = True
        
        # Start heartbeat manager
        await self.heartbeat_manager.start()
        
        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Enhanced WebSocket connection manager started")
    
    async def stop(self) -> None:
        """Stop the connection manager and cleanup all connections."""
        if not self._running:
            return
            
        self._running = False
        
        # Stop heartbeat manager
        await self.heartbeat_manager.stop()
        
        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
                
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect all connections gracefully
        connection_ids = list(self.connections.keys())
        for connection_id in connection_ids:
            await self.disconnect(connection_id, reason="Server shutdown")
        
        logger.info("Enhanced WebSocket connection manager stopped")
    
    async def connect(self, websocket: WebSocket, connection_id: Optional[str] = None) -> str:
        """
        Accept a new WebSocket connection with enhanced tracking.
        
        Args:
            websocket: WebSocket instance
            connection_id: Optional connection ID (generated if not provided)
            
        Returns:
            Connection ID
        """
        if connection_id is None:
            connection_id = str(uuid4())
        
        # Accept the WebSocket connection
        await websocket.accept()
        
        # Create connection info
        connection_info = ConnectionInfo(
            connection_id=connection_id,
            websocket=websocket,
            state=ConnectionState.CONNECTED
        )
        
        # Store connection
        self.connections[connection_id] = connection_info
        self.total_connections_created += 1
        
        # Register with heartbeat manager
        self.heartbeat_manager.register_connection(connection_id)
        
        logger.info(f"WebSocket connection established: {connection_id}")
        
        # Send welcome message
        welcome_message = {
            "type": "connected",
            "data": {
                "connection_id": connection_id,
                "server_time": datetime.utcnow().isoformat(),
                "heartbeat_interval": self.heartbeat_interval
            }
        }
        
        await self.send_message(connection_id, welcome_message)
        
        return connection_id
    
    async def disconnect(self, connection_id: str, reason: str = "Client disconnect") -> None:
        """
        Disconnect a WebSocket connection with cleanup.
        
        Args:
            connection_id: Connection to disconnect
            reason: Reason for disconnection
        """
        if connection_id not in self.connections:
            return
        
        connection_info = self.connections[connection_id]
        connection_info.state = ConnectionState.DISCONNECTING
        
        try:
            # Send disconnect message if connection is still active
            if connection_info.websocket and connection_info.state != ConnectionState.ERROR:
                disconnect_message = {
                    "type": "disconnecting",
                    "data": {
                        "reason": reason,
                        "server_time": datetime.utcnow().isoformat()
                    }
                }
                await self._send_raw_message(connection_info, disconnect_message)
                
                # Close WebSocket connection
                await connection_info.websocket.close()
        
        except Exception as e:
            logger.debug(f"Error during disconnect for {connection_id}: {e}")
        
        finally:
            # Clean up connection data
            await self._cleanup_connection(connection_id)
            
        logger.info(f"WebSocket connection disconnected: {connection_id} - {reason}")
    
    async def authenticate_connection(
        self,
        connection_id: str,
        token: str,
        db: Session
    ) -> Optional[User]:
        """
        Authenticate a WebSocket connection.
        
        Args:
            connection_id: Connection to authenticate
            token: JWT token
            db: Database session
            
        Returns:
            User object if successful, None otherwise
        """
        if connection_id not in self.connections:
            return None
        
        connection_info = self.connections[connection_id]
        
        # Use existing authentication logic from base ConnectionManager
        base_manager = ConnectionManager()
        user = await base_manager.authenticate_connection(connection_id, token, db)
        
        if user:
            # Update connection info
            connection_info.authenticated = True
            connection_info.user_id = str(user.id)
            connection_info.user_role = user.role.value if hasattr(user.role, 'value') else str(user.role)
            connection_info.state = ConnectionState.AUTHENTICATED
            
            # Check connection limits per user
            user_id_str = str(user.id)
            if user_id_str not in self.user_connections:
                self.user_connections[user_id_str] = set()
            
            # Enforce connection limit
            if len(self.user_connections[user_id_str]) >= self.max_connections_per_user:
                # Disconnect oldest connection for this user
                oldest_connection = min(
                    self.user_connections[user_id_str],
                    key=lambda cid: self.connections[cid].connected_at
                )
                await self.disconnect(oldest_connection, "Connection limit exceeded")
            
            self.user_connections[user_id_str].add(connection_id)
            
            logger.info(f"WebSocket connection authenticated: {connection_id} for user {user_id_str}")
        
        return user
    
    async def join_patient_room(self, connection_id: str, patient_id: str) -> bool:
        """
        Add connection to a patient room.
        
        Args:
            connection_id: Connection to add
            patient_id: Patient room ID
            
        Returns:
            True if successful, False otherwise
        """
        if connection_id not in self.connections:
            return False
        
        connection_info = self.connections[connection_id]
        
        if not connection_info.authenticated:
            logger.warning(f"Unauthenticated connection {connection_id} cannot join patient room")
            return False
        
        # Add to patient room
        if patient_id not in self.patient_rooms:
            self.patient_rooms[patient_id] = set()
        
        self.patient_rooms[patient_id].add(connection_id)
        connection_info.patient_id = patient_id
        
        logger.info(f"Connection {connection_id} joined patient room {patient_id}")
        return True
    
    async def leave_patient_room(self, connection_id: str, patient_id: str) -> None:
        """
        Remove connection from a patient room.
        
        Args:
            connection_id: Connection to remove
            patient_id: Patient room ID
        """
        if patient_id in self.patient_rooms:
            self.patient_rooms[patient_id].discard(connection_id)
            if not self.patient_rooms[patient_id]:
                del self.patient_rooms[patient_id]
        
        if connection_id in self.connections:
            self.connections[connection_id].patient_id = None
        
        logger.info(f"Connection {connection_id} left patient room {patient_id}")
    
    async def send_message(self, connection_id: str, message: dict) -> bool:
        """
        Send message to a specific connection.
        
        Args:
            connection_id: Target connection
            message: Message to send
            
        Returns:
            True if successful, False otherwise
        """
        if connection_id not in self.connections:
            return False
        
        connection_info = self.connections[connection_id]
        
        if connection_info.state in [ConnectionState.DISCONNECTING, ConnectionState.DISCONNECTED, ConnectionState.ERROR]:
            return False
        
        return await self._send_raw_message(connection_info, message)
    
    async def broadcast_to_user(self, user_id: str, message: dict) -> int:
        """
        Broadcast message to all connections of a user.
        
        Args:
            user_id: Target user ID
            message: Message to broadcast
            
        Returns:
            Number of successful sends
        """
        if user_id not in self.user_connections:
            return 0
        
        sent_count = 0
        failed_connections = []
        
        for connection_id in self.user_connections[user_id].copy():
            if await self.send_message(connection_id, message):
                sent_count += 1
            else:
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.disconnect(connection_id, "Send failed")
        
        return sent_count
    
    async def broadcast_to_patient_room(self, patient_id: str, message: dict) -> int:
        """
        Broadcast message to all connections in a patient room.
        
        Args:
            patient_id: Patient room ID
            message: Message to broadcast
            
        Returns:
            Number of successful sends
        """
        if patient_id not in self.patient_rooms:
            return 0
        
        sent_count = 0
        failed_connections = []
        
        for connection_id in self.patient_rooms[patient_id].copy():
            if await self.send_message(connection_id, message):
                sent_count += 1
            else:
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.disconnect(connection_id, "Send failed")
        
        return sent_count
    
    async def broadcast_to_all_authenticated(self, message: dict) -> int:
        """
        Broadcast message to all authenticated connections.
        
        Args:
            message: Message to broadcast
            
        Returns:
            Number of successful sends
        """
        sent_count = 0
        failed_connections = []
        
        for connection_id, connection_info in self.connections.items():
            if connection_info.authenticated:
                if await self.send_message(connection_id, message):
                    sent_count += 1
                else:
                    failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.disconnect(connection_id, "Send failed")
        
        return sent_count
    
    async def ping_connection(self, connection_id: str) -> bool:
        """
        Send ping to connection for health check.
        
        Args:
            connection_id: Connection to ping
            
        Returns:
            True if ping sent successfully, False otherwise
        """
        if connection_id not in self.connections:
            return False
        
        # Use heartbeat manager to send ping
        return await self.heartbeat_manager.send_ping(
            connection_id,
            self._send_ping_callback
        )
    
    async def handle_pong(self, connection_id: str, ping_id: Optional[str] = None, client_timestamp: Optional[str] = None) -> None:
        """
        Handle pong response from client.
        
        Args:
            connection_id: Connection that sent pong
            ping_id: Optional ping ID for tracking
            client_timestamp: Optional client timestamp
        """
        if connection_id not in self.connections:
            return
        
        connection_info = self.connections[connection_id]
        connection_info.pong_count += 1
        connection_info.last_pong = datetime.utcnow()
        connection_info.missed_pings = 0  # Reset missed pings counter
        
        # Use heartbeat manager to handle pong
        if ping_id:
            self.heartbeat_manager.handle_pong(connection_id, ping_id, client_timestamp)
        
        logger.debug(f"Received pong from connection {connection_id}")
    
    def get_connection_stats(self) -> dict:
        """
        Get comprehensive connection statistics.
        
        Returns:
            Dictionary with detailed statistics
        """
        now = datetime.utcnow()
        
        # Calculate connection health metrics
        healthy_connections = 0
        unhealthy_connections = 0
        
        for connection_info in self.connections.values():
            if connection_info.authenticated and connection_info.missed_pings < self.max_missed_pings:
                healthy_connections += 1
            else:
                unhealthy_connections += 1
        
        return {
            "total_connections": len(self.connections),
            "authenticated_connections": sum(1 for c in self.connections.values() if c.authenticated),
            "healthy_connections": healthy_connections,
            "unhealthy_connections": unhealthy_connections,
            "user_connections": len(self.user_connections),
            "patient_rooms": len(self.patient_rooms),
            "total_created": self.total_connections_created,
            "total_closed": self.total_connections_closed,
            "total_messages_sent": self.total_messages_sent,
            "total_messages_received": self.total_messages_received,
            "total_bytes_sent": self.total_bytes_sent,
            "total_bytes_received": self.total_bytes_received,
            "connections_by_state": {
                state.value: sum(1 for c in self.connections.values() if c.state == state)
                for state in ConnectionState
            },
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
        Get detailed information about a specific connection.
        
        Args:
            connection_id: Connection to get info for
            
        Returns:
            Connection information dictionary or None
        """
        if connection_id not in self.connections:
            return None
        
        connection_info = self.connections[connection_id]
        
        return {
            "connection_id": connection_info.connection_id,
            "state": connection_info.state.value,
            "connected_at": connection_info.connected_at.isoformat(),
            "last_ping": connection_info.last_ping.isoformat(),
            "last_pong": connection_info.last_pong.isoformat(),
            "user_id": connection_info.user_id,
            "patient_id": connection_info.patient_id,
            "authenticated": connection_info.authenticated,
            "user_role": connection_info.user_role,
            "ping_count": connection_info.ping_count,
            "pong_count": connection_info.pong_count,
            "missed_pings": connection_info.missed_pings,
            "bytes_sent": connection_info.bytes_sent,
            "bytes_received": connection_info.bytes_received,
            "messages_sent": connection_info.messages_sent,
            "messages_received": connection_info.messages_received,
            "error_count": connection_info.error_count,
            "last_error": connection_info.last_error,
            "metadata": connection_info.metadata
        }
    
    async def _send_raw_message(self, connection_info: ConnectionInfo, message: dict) -> bool:
        """
        Send raw message to connection with error handling.
        
        Args:
            connection_info: Connection information
            message: Message to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Serialize message
            serialized_message = self._serialize_message(message)
            message_text = json.dumps(serialized_message)
            
            # Send message
            await connection_info.websocket.send_text(message_text)
            
            # Update statistics
            connection_info.messages_sent += 1
            connection_info.bytes_sent += len(message_text.encode('utf-8'))
            self.total_messages_sent += 1
            self.total_bytes_sent += len(message_text.encode('utf-8'))
            
            return True
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if it's a connection error
            if any(keyword in error_str for keyword in [
                "disconnect", "not connected", "websocket", "connection closed"
            ]):
                logger.debug(f"WebSocket connection error for {connection_info.connection_id}: {e}")
                connection_info.state = ConnectionState.ERROR
            else:
                logger.error(f"Error sending message to {connection_info.connection_id}: {e}")
                connection_info.error_count += 1
                connection_info.last_error = str(e)
            
            return False
    
    async def _heartbeat_loop(self) -> None:
        """Background task for sending heartbeat pings."""
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if not self._running:
                    break
                
                # Send pings to all authenticated connections
                dead_connections = []
                
                for connection_id, connection_info in self.connections.items():
                    if not connection_info.authenticated:
                        continue
                    
                    # Check if connection has missed too many pings
                    if connection_info.missed_pings >= self.max_missed_pings:
                        dead_connections.append(connection_id)
                        continue
                    
                    # Send ping
                    success = await self.ping_connection(connection_id)
                    if not success:
                        connection_info.missed_pings += 1
                
                # Clean up dead connections
                for connection_id in dead_connections:
                    await self.disconnect(connection_id, "Heartbeat timeout")
                
                logger.debug(f"Heartbeat cycle completed. Active connections: {len(self.connections)}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Background task for periodic cleanup."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                if not self._running:
                    break
                
                await self._perform_cleanup()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _perform_cleanup(self) -> None:
        """Perform periodic cleanup tasks."""
        now = datetime.utcnow()
        cleanup_threshold = now - timedelta(minutes=5)  # 5 minutes
        
        connections_to_remove = []
        
        for connection_id, connection_info in self.connections.items():
            # Remove connections that have been in error state for too long
            if (connection_info.state == ConnectionState.ERROR and 
                connection_info.last_ping < cleanup_threshold):
                connections_to_remove.append(connection_id)
            
            # Remove connections that haven't responded to pings for too long
            elif (connection_info.authenticated and 
                  connection_info.last_pong < cleanup_threshold and
                  connection_info.missed_pings >= self.max_missed_pings):
                connections_to_remove.append(connection_id)
        
        # Clean up identified connections
        for connection_id in connections_to_remove:
            await self.disconnect(connection_id, "Cleanup - inactive connection")
        
        if connections_to_remove:
            logger.info(f"Cleanup removed {len(connections_to_remove)} inactive connections")
    
    async def _cleanup_connection(self, connection_id: str) -> None:
        """
        Clean up all data associated with a connection.
        
        Args:
            connection_id: Connection to clean up
        """
        if connection_id not in self.connections:
            return
        
        connection_info = self.connections[connection_id]
        
        # Remove from user connections
        if connection_info.user_id and connection_info.user_id in self.user_connections:
            self.user_connections[connection_info.user_id].discard(connection_id)
            if not self.user_connections[connection_info.user_id]:
                del self.user_connections[connection_info.user_id]
        
        # Remove from patient rooms
        if connection_info.patient_id and connection_info.patient_id in self.patient_rooms:
            self.patient_rooms[connection_info.patient_id].discard(connection_id)
            if not self.patient_rooms[connection_info.patient_id]:
                del self.patient_rooms[connection_info.patient_id]
        
        # Unregister from heartbeat manager
        self.heartbeat_manager.unregister_connection(connection_id)
        
        # Update statistics
        self.total_connections_closed += 1
        
        # Remove connection info
        connection_info.state = ConnectionState.DISCONNECTED
        del self.connections[connection_id]
    
    def _serialize_message(self, message: dict) -> dict:
        """
        Serialize message for JSON compatibility.
        
        Args:
            message: Message to serialize
            
        Returns:
            Serialized message
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
    
    async def _send_ping_callback(self, connection_id: str, ping_message: dict) -> bool:
        """
        Callback for heartbeat manager to send ping messages.
        
        Args:
            connection_id: Connection to send ping to
            ping_message: Ping message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if connection_id not in self.connections:
            return False
        
        connection_info = self.connections[connection_id]
        return await self._send_raw_message(connection_info, ping_message)
    
    def _handle_dead_connection(self, connection_id: str) -> None:
        """
        Handle a connection that has been marked as dead by heartbeat manager.
        
        Args:
            connection_id: Dead connection ID
        """
        logger.warning(f"Connection marked as dead by heartbeat manager: {connection_id}")
        
        # Schedule disconnection
        asyncio.create_task(self.disconnect(connection_id, "Heartbeat failure"))
    
    def _handle_connection_warning(self, connection_id: str, metrics: HeartbeatMetrics) -> None:
        """
        Handle a connection that has entered warning state.
        
        Args:
            connection_id: Connection in warning state
            metrics: Heartbeat metrics for the connection
        """
        logger.warning(
            f"Connection {connection_id} in warning state: "
            f"missed_pings={metrics.missed_pings}, "
            f"avg_latency={metrics.average_latency:.2f}ms"
        )
    
    def _handle_ping_timeout(self, connection_id: str, ping_id: str) -> None:
        """
        Handle a ping timeout event.
        
        Args:
            connection_id: Connection that timed out
            ping_id: Ping ID that timed out
        """
        logger.debug(f"Ping timeout for connection {connection_id}: {ping_id}")
        
        # Update connection info if it exists
        if connection_id in self.connections:
            connection_info = self.connections[connection_id]
            connection_info.missed_pings += 1
    
    def get_heartbeat_stats(self) -> dict:
        """
        Get heartbeat statistics for all connections.
        
        Returns:
            Dictionary with heartbeat statistics
        """
        return self.heartbeat_manager.get_health_summary()
    
    def get_connection_heartbeat_info(self, connection_id: str) -> Optional[dict]:
        """
        Get heartbeat information for a specific connection.
        
        Args:
            connection_id: Connection to get heartbeat info for
            
        Returns:
            Heartbeat metrics dictionary or None
        """
        metrics = self.heartbeat_manager.get_connection_health(connection_id)
        if not metrics:
            return None
        
        return {
            "connection_id": metrics.connection_id,
            "status": metrics.status.value,
            "last_ping_sent": metrics.last_ping_sent.isoformat() if metrics.last_ping_sent else None,
            "last_pong_received": metrics.last_pong_received.isoformat() if metrics.last_pong_received else None,
            "ping_count": metrics.ping_count,
            "pong_count": metrics.pong_count,
            "missed_pings": metrics.missed_pings,
            "average_latency_ms": round(metrics.average_latency, 2),
            "min_latency_ms": round(metrics.min_latency, 2) if metrics.min_latency != float('inf') else None,
            "max_latency_ms": round(metrics.max_latency, 2),
            "created_at": metrics.created_at.isoformat()
        }


# Global enhanced connection manager instance
enhanced_connection_manager = EnhancedWebSocketConnectionManager()


class EnhancedWebSocketManager:
    """
    Enhanced WebSocket manager with singleton pattern and additional features.
    """
    
    _instance: Optional['EnhancedWebSocketManager'] = None
    _initialized: bool = False
    
    def __init__(self):
        if EnhancedWebSocketManager._initialized:
            raise RuntimeError("EnhancedWebSocketManager is a singleton. Use get_instance() instead.")
        
        self.connection_manager = enhanced_connection_manager
        self.is_running = False
        EnhancedWebSocketManager._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'EnhancedWebSocketManager':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def start(self) -> None:
        """Start the enhanced WebSocket manager."""
        if self.is_running:
            return
        
        await self.connection_manager.start()
        self.is_running = True
        logger.info("Enhanced WebSocket manager started")
    
    async def stop(self) -> None:
        """Stop the enhanced WebSocket manager."""
        if not self.is_running:
            return
        
        await self.connection_manager.stop()
        self.is_running = False
        logger.info("Enhanced WebSocket manager stopped")
    
    # Delegate methods to connection manager
    async def connect(self, websocket: WebSocket, connection_id: Optional[str] = None) -> str:
        """Connect a new WebSocket."""
        return await self.connection_manager.connect(websocket, connection_id)
    
    async def disconnect(self, connection_id: str, reason: str = "Client disconnect") -> None:
        """Disconnect a WebSocket."""
        await self.connection_manager.disconnect(connection_id, reason)
    
    async def authenticate_connection(self, connection_id: str, token: str, db: Session) -> Optional[User]:
        """Authenticate a WebSocket connection."""
        return await self.connection_manager.authenticate_connection(connection_id, token, db)
    
    async def join_patient_room(self, connection_id: str, patient_id: str) -> bool:
        """Join a connection to a patient room."""
        return await self.connection_manager.join_patient_room(connection_id, patient_id)
    
    async def leave_patient_room(self, connection_id: str, patient_id: str) -> None:
        """Remove a connection from a patient room."""
        await self.connection_manager.leave_patient_room(connection_id, patient_id)
    
    async def send_message(self, connection_id: str, message: dict) -> bool:
        """Send a message to a specific connection."""
        return await self.connection_manager.send_message(connection_id, message)
    
    async def broadcast_to_user(self, user_id: str, message: dict) -> int:
        """Send a message to all connections of a specific user."""
        return await self.connection_manager.broadcast_to_user(user_id, message)
    
    async def broadcast_to_patient_room(self, patient_id: str, message: dict) -> int:
        """Broadcast a message to all connections in a patient room."""
        return await self.connection_manager.broadcast_to_patient_room(patient_id, message)
    
    async def broadcast_to_all_authenticated(self, message: dict) -> int:
        """Broadcast a message to all authenticated clients."""
        return await self.connection_manager.broadcast_to_all_authenticated(message)
    
    async def ping_connection(self, connection_id: str) -> bool:
        """Send ping to connection for health check."""
        return await self.connection_manager.ping_connection(connection_id)
    
    async def handle_pong(self, connection_id: str, ping_id: Optional[int] = None) -> None:
        """Handle pong response from client."""
        await self.connection_manager.handle_pong(connection_id, ping_id)
    
    def get_connection_stats(self) -> dict:
        """Get statistics about current connections."""
        return self.connection_manager.get_connection_stats()
    
    def get_connection_info(self, connection_id: str) -> Optional[dict]:
        """Get metadata for a specific connection."""
        return self.connection_manager.get_connection_info(connection_id)


def get_enhanced_websocket_manager() -> EnhancedWebSocketManager:
    """Get the global enhanced WebSocket manager instance."""
    return EnhancedWebSocketManager.get_instance()