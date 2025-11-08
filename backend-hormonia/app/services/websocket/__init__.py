"""
Unified WebSocket Management Module.

This module consolidates the original websocket_manager.py and
enhanced_websocket_manager.py into a single, production-ready solution.

Exports:
- UnifiedWebSocketConnectionManager: Main connection manager
- ConnectionState: Connection state enum
- ConnectionInfo: Connection metadata dataclass
- get_websocket_manager: Singleton accessor
"""

from .connection_info import ConnectionState, ConnectionInfo
from .connection_manager import UnifiedWebSocketConnectionManager, get_websocket_manager

__all__ = [
    "UnifiedWebSocketConnectionManager",
    "ConnectionState",
    "ConnectionInfo",
    "get_websocket_manager",
]
