# WebSocket API Documentation
**Version**: 2.0 (Unified Implementation)
**Date**: 2025-11-07
**Module**: `app.services.websocket`

---

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [API Reference](#api-reference)
4. [Connection Management](#connection-management)
5. [Authentication](#authentication)
6. [Room Management](#room-management)
7. [Messaging](#messaging)
8. [Lifecycle & Health](#lifecycle--health)
9. [Error Handling](#error-handling)
10. [Examples](#examples)

---

## Overview

The Unified WebSocket Manager provides real-time bidirectional communication for the Hormonia healthcare platform. It supports:

- ✅ Dual authentication (Firebase + JWT with auto-fallback)
- ✅ Room-based messaging (patient rooms, user channels)
- ✅ Automated lifecycle management
- ✅ Heartbeat monitoring and health checks
- ✅ Automatic cleanup of stale connections
- ✅ Horizontal scaling via Redis Pub/Sub

---

## Getting Started

### Basic Usage

```python
from app.services.websocket import get_websocket_manager

# Get singleton instance
manager = get_websocket_manager()

# Use in endpoint
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = await manager.connect(websocket)
    try:
        # Handle messages...
        pass
    finally:
        await manager.disconnect(connection_id)
```

### Lifecycle Integration

```python
# In app lifespan
async def startup():
    manager = get_websocket_manager()
    await manager.start()  # Starts background tasks

async def shutdown():
    manager = get_websocket_manager()
    await manager.stop()   # Graceful cleanup
```

---

## API Reference

### `UnifiedWebSocketConnectionManager`

Main class for WebSocket connection management.

#### Initialization

```python
manager = UnifiedWebSocketConnectionManager()
```

**Parameters**: None (singleton pattern via `get_websocket_manager()`)

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `connections` | `Dict[str, WebSocket]` | Active WebSocket connections |
| `connection_info` | `Dict[str, ConnectionInfo]` | Connection metadata |
| `patient_rooms` | `Dict[str, Set[str]]` | Patient room memberships |
| `user_connections` | `Dict[str, Set[str]]` | User → connections mapping |
| `heartbeat_interval` | `int` | Heartbeat interval in seconds (default: 30) |
| `cleanup_interval` | `int` | Cleanup interval in seconds (default: 60) |
| `max_connections_per_user` | `int` | Max connections per user (default: 5) |

---

## Connection Management

### `connect(websocket, connection_id=None)`

Establish a new WebSocket connection.

**Parameters**:
- `websocket` (WebSocket): FastAPI WebSocket instance
- `connection_id` (str, optional): Custom connection ID (auto-generated if None)

**Returns**: `str` - Connection ID

**Example**:
```python
connection_id = await manager.connect(websocket)
# Or with custom ID:
connection_id = await manager.connect(websocket, "custom-conn-id")
```

**Side Effects**:
- Accepts WebSocket connection
- Creates ConnectionInfo entry
- Initializes connection state as CONNECTED

---

### `disconnect(connection_id, reason=None)`

Disconnect and cleanup a WebSocket connection.

**Parameters**:
- `connection_id` (str): Connection to disconnect
- `reason` (str, optional): Reason for disconnection

**Returns**: `None`

**Example**:
```python
await manager.disconnect(connection_id, reason="User logout")
```

**Side Effects**:
- Removes from all rooms
- Cleans up connection metadata
- Updates user connection tracking

---

### `get_connection_info(connection_id)`

Get detailed information about a connection.

**Parameters**:
- `connection_id` (str): Connection ID

**Returns**: `ConnectionInfo | None`

**Example**:
```python
info = manager.get_connection_info(connection_id)
if info:
    print(f"User: {info.user_id}, State: {info.state}")
```

---

## Authentication

### `authenticate_connection(connection_id, token, db, auth_type="auto")`

Authenticate a WebSocket connection.

**Parameters**:
- `connection_id` (str): Connection to authenticate
- `token` (str): Authentication token (Firebase or JWT)
- `db` (Session): Database session
- `auth_type` (str): "firebase", "jwt", or "auto" (default: "auto")

**Returns**: `User | None` - Authenticated user object

**Authentication Flow**:
1. **auto** (default): Try Firebase first, fallback to JWT
2. **firebase**: Firebase RS256 token verification
3. **jwt**: JWT HS256 token verification

**Example**:
```python
user = await manager.authenticate_connection(
    connection_id=connection_id,
    token=auth_token,
    db=db,
    auth_type="auto"
)

if user:
    print(f"Authenticated: {user.email}")
else:
    print("Authentication failed")
```

**Side Effects**:
- Updates connection state to AUTHENTICATED
- Sets `user_id` and `role` in ConnectionInfo
- Increments authenticated connection count

---

## Room Management

### `join_patient_room(connection_id, patient_id)`

Join a patient room for receiving patient-specific updates.

**Parameters**:
- `connection_id` (str): Connection ID
- `patient_id` (str): Patient ID

**Returns**: `bool` - Success status

**Requirements**:
- Connection must be authenticated

**Example**:
```python
success = await manager.join_patient_room(connection_id, patient_id)
if success:
    print(f"Joined room for patient {patient_id}")
```

---

### `leave_patient_room(connection_id, patient_id)`

Leave a patient room.

**Parameters**:
- `connection_id` (str): Connection ID
- `patient_id` (str): Patient ID

**Returns**: `None`

**Example**:
```python
await manager.leave_patient_room(connection_id, patient_id)
```

---

## Messaging

### `send_message(connection_id, message)`

Send a message to a specific connection.

**Parameters**:
- `connection_id` (str): Target connection
- `message` (dict): Message payload (will be JSON-encoded)

**Returns**: `bool` - Success status

**Example**:
```python
success = await manager.send_message(connection_id, {
    "type": "notification",
    "data": {"message": "New quiz available"}
})
```

---

### `broadcast_to_patient_room(patient_id, message)`

Broadcast message to all connections in a patient room.

**Parameters**:
- `patient_id` (str): Patient room ID
- `message` (dict): Message payload

**Returns**: `int` - Number of connections that received the message

**Example**:
```python
count = await manager.broadcast_to_patient_room(patient_id, {
    "type": "patient_updated",
    "data": {"patient_id": patient_id, "status": "active"}
})
print(f"Broadcasted to {count} connections")
```

---

### `broadcast_to_user(user_id, message)`

Broadcast message to all connections of a specific user (all devices).

**Parameters**:
- `user_id` (str): User ID
- `message` (dict): Message payload

**Returns**: `int` - Number of connections reached

**Example**:
```python
count = await manager.broadcast_to_user(user_id, {
    "type": "alert",
    "data": {"message": "You have a new message"}
})
```

---

### `broadcast_to_all_authenticated(message)`

Broadcast message to all authenticated connections.

**Parameters**:
- `message` (dict): Message payload

**Returns**: `int` - Number of connections reached

**Example**:
```python
count = await manager.broadcast_to_all_authenticated({
    "type": "system_maintenance",
    "data": {"message": "System update in 10 minutes"}
})
```

---

## Lifecycle & Health

### `start()`

Start background tasks (heartbeat monitoring, cleanup).

**Returns**: `None`

**Side Effects**:
- Starts heartbeat monitor task (every 30s)
- Starts cleanup task (every 60s)
- Sets `_started` flag to True

**Example**:
```python
await manager.start()
```

---

### `stop()`

Stop background tasks and prepare for shutdown.

**Returns**: `None`

**Side Effects**:
- Cancels all background tasks
- Sets `_started` flag to False

**Example**:
```python
await manager.stop()
```

---

### `ping_connection(connection_id)`

Send a ping to a connection for health check.

**Parameters**:
- `connection_id` (str): Connection to ping

**Returns**: `str` - Ping ID for tracking

**Example**:
```python
ping_id = await manager.ping_connection(connection_id)
```

---

### `handle_pong(connection_id, ping_id, timestamp)`

Handle pong response from client.

**Parameters**:
- `connection_id` (str): Connection that responded
- `ping_id` (str): Ping ID from original ping
- `timestamp` (float): Client timestamp

**Returns**: `None`

**Side Effects**:
- Updates `last_heartbeat` timestamp
- Records round-trip time

**Example**:
```python
await manager.handle_pong(connection_id, ping_id, time.time())
```

---

### `get_connection_stats()`

Get statistics about all connections.

**Returns**: `dict` - Statistics dictionary

**Response Structure**:
```python
{
    "total_connections": 42,
    "authenticated_connections": 38,
    "connections_by_state": {
        "CONNECTED": 4,
        "AUTHENTICATED": 38
    },
    "connections_by_role": {
        "doctor": 25,
        "admin": 13
    },
    "patient_rooms": 15,
    "unique_users": 35,
    "uptime": 3600.5,  # seconds
    "total_messages_sent": 1523
}
```

**Example**:
```python
stats = manager.get_connection_stats()
print(f"Active connections: {stats['total_connections']}")
```

---

## Error Handling

### Exception Types

The manager handles these exceptions internally:

| Exception | Scenario | Behavior |
|-----------|----------|----------|
| `WebSocketDisconnect` | Client disconnects | Auto-cleanup connection |
| `ConnectionError` | Network error | Auto-cleanup, log error |
| `ValueError` | Invalid parameters | Raise to caller |
| `AuthenticationError` | Auth fails | Return None, connection stays |

### Best Practices

```python
try:
    connection_id = await manager.connect(websocket)

    try:
        # Authentication
        user = await manager.authenticate_connection(connection_id, token, db)
        if not user:
            await manager.send_message(connection_id, {
                "type": "error",
                "message": "Authentication failed"
            })
            return

        # Handle messages
        while True:
            data = await websocket.receive_text()
            # Process data...

    finally:
        await manager.disconnect(connection_id)

except WebSocketDisconnect:
    logger.info(f"Client disconnected: {connection_id}")
except Exception as e:
    logger.error(f"WebSocket error: {e}")
```

---

## Examples

### Complete WebSocket Endpoint

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket import get_websocket_manager
from app.database import get_db

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None)
):
    manager = get_websocket_manager()
    connection_id = None

    try:
        # Connect
        connection_id = await manager.connect(websocket)

        # Authenticate if token provided
        if token:
            db = next(get_db())
            try:
                user = await manager.authenticate_connection(
                    connection_id, token, db, auth_type="auto"
                )
                if user:
                    await manager.send_message(connection_id, {
                        "type": "authenticated",
                        "user": {"id": user.id, "email": user.email}
                    })
            finally:
                db.close()

        # Message loop
        while True:
            data = await websocket.receive_json()

            if data["type"] == "join_room":
                success = await manager.join_patient_room(
                    connection_id,
                    data["patient_id"]
                )
                await manager.send_message(connection_id, {
                    "type": "room_joined",
                    "success": success
                })

            elif data["type"] == "ping":
                ping_id = await manager.ping_connection(connection_id)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {connection_id}")
    finally:
        if connection_id:
            await manager.disconnect(connection_id)
```

### Broadcasting Patient Updates

```python
async def notify_patient_update(patient_id: str, update_data: dict):
    """Notify all listeners about a patient update."""
    manager = get_websocket_manager()

    message = {
        "type": "patient_updated",
        "patient_id": patient_id,
        "data": update_data,
        "timestamp": datetime.utcnow().isoformat()
    }

    count = await manager.broadcast_to_patient_room(patient_id, message)
    logger.info(f"Patient update sent to {count} connections")
```

### Multi-Device User Notifications

```python
async def notify_user(user_id: str, notification: dict):
    """Send notification to all user's devices."""
    manager = get_websocket_manager()

    message = {
        "type": "notification",
        "data": notification
    }

    count = await manager.broadcast_to_user(user_id, message)
    logger.info(f"Notification sent to {count} devices")
```

---

## Related Documentation

- **Migration Guide**: `docs/architecture/WEBSOCKET_MIGRATION_GUIDE.md`
- **Deployment Guide**: `docs/deployment/WEBSOCKET_DEPLOYMENT.md`
- **Sprint Summaries**: `docs/sprints/SPRINT_*.md`
- **Test Suite**: `tests/services/websocket/test_connection_manager.py`

---

**Last Updated**: 2025-11-07
**Maintained By**: Backend Team
**Version**: 2.0 (Unified Implementation)
