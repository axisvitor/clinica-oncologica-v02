"""
Connection information and state tracking for WebSocket connections.

Extracted from enhanced_websocket_manager.py for modular architecture.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import WebSocket


class ConnectionState(Enum):
    """WebSocket connection state."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class ConnectionInfo:
    """
    Enhanced connection information with state tracking and metrics.

    Combines simple dict-based storage from original with rich metadata
    from enhanced version.
    """

    connection_id: str
    websocket: WebSocket
    state: ConnectionState = ConnectionState.CONNECTED

    # Authentication & User Info
    user_id: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None

    # Connection Metadata
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    authenticated_at: Optional[datetime] = None

    # Metrics
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    patient_rooms: set = field(default_factory=set)

    def is_authenticated(self) -> bool:
        """Check if connection is authenticated."""
        return self.state == ConnectionState.AUTHENTICATED and self.user_id is not None

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)

    def record_message_sent(self, size_bytes: int = 0):
        """Record a sent message."""
        self.messages_sent += 1
        self.bytes_sent += size_bytes
        self.update_activity()

    def record_message_received(self, size_bytes: int = 0):
        """Record a received message."""
        self.messages_received += 1
        self.bytes_received += size_bytes
        self.update_activity()
