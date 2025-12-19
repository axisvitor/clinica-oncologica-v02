"""
Redis Pub/Sub Manager for Horizontal WebSocket Scaling

Implements Redis publish/subscribe pattern to distribute WebSocket messages
across multiple FastAPI instances. This allows horizontal scaling without
sticky sessions.

Architecture:
- Each instance maintains local WebSocket connections in ConnectionManager
- When a message needs broadcasting, publish to Redis channel
- All instances subscribe to Redis channels and forward to their local connections
- Redis acts as the central message broker

Channels:
- ws:broadcast - Global broadcasts to all connections
- ws:room:{room_id} - Room-specific messages
- ws:user:{user_id} - User-specific messages (across devices)
- ws:heartbeat - Health check channel

Usage:
    pubsub_manager = RedisPubSubManager(redis_client)
    await pubsub_manager.start()

    # Publish message to all instances
    await pubsub_manager.publish_broadcast({
        "type": "notification",
        "data": {"message": "System update"}
    })

    # Publish to specific room
    await pubsub_manager.publish_to_room("room_123", {
        "type": "patient_update",
        "data": {"patient_id": "123"}
    })
"""

import asyncio
import json
import logging
from typing import Dict, Any, Callable, Optional, Set
from datetime import datetime
import redis.asyncio as redis
from app.services.websocket import UnifiedWebSocketConnectionManager

logger = logging.getLogger(__name__)


class RedisPubSubManager:
    """
    Redis Pub/Sub manager for distributing WebSocket messages across instances.

    Attributes:
        redis_client: Async Redis client for pub/sub operations
        connection_manager: Local ConnectionManager instance
        subscriptions: Active Redis subscriptions
        is_running: Whether the pub/sub listener is active
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        connection_manager: UnifiedWebSocketConnectionManager,
        instance_id: Optional[str] = None,
    ):
        """
        Initialize Redis Pub/Sub manager.

        Args:
            redis_client: Async Redis client
            connection_manager: Local UnifiedWebSocketConnectionManager for this instance
            instance_id: Unique identifier for this instance (auto-generated if None)
        """
        self.redis_client = redis_client
        self.connection_manager = connection_manager
        self.instance_id = instance_id or f"instance_{id(self)}"

        # Pub/Sub state
        self.pubsub: Optional[redis.client.PubSub] = None
        self.subscriptions: Set[str] = set()
        self.is_running = False
        self._listener_task: Optional[asyncio.Task] = None

        # Message handlers
        self._handlers: Dict[str, Callable] = {}

        logger.info(f"RedisPubSubManager initialized for instance: {self.instance_id}")

    async def start(self):
        """
        Start the Redis pub/sub listener.

        Subscribes to all necessary channels and starts background listener task.
        """
        if self.is_running:
            logger.warning("RedisPubSubManager already running")
            return

        try:
            # Create pubsub instance
            self.pubsub = self.redis_client.pubsub()

            # Subscribe to standard channels
            await self._subscribe_to_channels()

            # Start listener task
            self._listener_task = asyncio.create_task(self._listen_for_messages())

            self.is_running = True
            logger.info(f"RedisPubSubManager started on instance {self.instance_id}")

        except Exception as e:
            logger.error(f"Failed to start RedisPubSubManager: {e}")
            raise

    async def stop(self):
        """
        Stop the Redis pub/sub listener and cleanup resources.
        """
        if not self.is_running:
            return

        logger.info(f"Stopping RedisPubSubManager on instance {self.instance_id}")

        self.is_running = False

        # Cancel listener task
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe and close pubsub (redis 5.x uses aclose)
        if self.pubsub:
            try:
                await self.pubsub.unsubscribe()
                await self.pubsub.aclose()
            except Exception as e:
                logger.error(f"Error closing pubsub: {e}")

        self.subscriptions.clear()
        logger.info("RedisPubSubManager stopped")

    async def _subscribe_to_channels(self):
        """Subscribe to all standard Redis channels."""
        if not self.pubsub:
            raise RuntimeError("PubSub not initialized")

        channels = [
            "ws:broadcast",  # Global broadcasts
            "ws:heartbeat",  # Health checks
        ]

        for channel in channels:
            await self.pubsub.subscribe(channel)
            self.subscriptions.add(channel)
            logger.debug(f"Subscribed to channel: {channel}")

    async def subscribe_to_room(self, room_id: str):
        """
        Subscribe to a specific room channel.

        Args:
            room_id: Room identifier
        """
        if not self.pubsub:
            raise RuntimeError("PubSub not initialized")

        channel = f"ws:room:{room_id}"

        if channel not in self.subscriptions:
            await self.pubsub.subscribe(channel)
            self.subscriptions.add(channel)
            logger.debug(f"Subscribed to room channel: {channel}")

    async def unsubscribe_from_room(self, room_id: str):
        """
        Unsubscribe from a specific room channel.

        Args:
            room_id: Room identifier
        """
        if not self.pubsub:
            return

        channel = f"ws:room:{room_id}"

        if channel in self.subscriptions:
            await self.pubsub.unsubscribe(channel)
            self.subscriptions.discard(channel)
            logger.debug(f"Unsubscribed from room channel: {channel}")

    async def subscribe_to_user(self, user_id: str):
        """
        Subscribe to user-specific channel for multi-device messaging.

        Args:
            user_id: User identifier
        """
        if not self.pubsub:
            raise RuntimeError("PubSub not initialized")

        channel = f"ws:user:{user_id}"

        if channel not in self.subscriptions:
            await self.pubsub.subscribe(channel)
            self.subscriptions.add(channel)
            logger.debug(f"Subscribed to user channel: {channel}")

    async def _listen_for_messages(self):
        """
        Background task that listens for Redis pub/sub messages.

        Runs continuously until stopped. Handles incoming messages and
        dispatches them to local WebSocket connections.
        """
        logger.info("Redis pub/sub listener started")

        try:
            async for message in self.pubsub.listen():
                if not self.is_running:
                    break

                if message["type"] == "message":
                    await self._handle_pubsub_message(message)

        except asyncio.CancelledError:
            logger.info("Redis pub/sub listener cancelled")
        except Exception as e:
            logger.error(f"Error in pub/sub listener: {e}", exc_info=True)
        finally:
            logger.info("Redis pub/sub listener stopped")

    async def _handle_pubsub_message(self, message: Dict[str, Any]):
        """
        Handle incoming pub/sub message from Redis.

        Parses the message and forwards to appropriate local WebSocket connections.

        Args:
            message: Redis pub/sub message
        """
        try:
            channel = message["channel"].decode("utf-8")
            data = json.loads(message["data"].decode("utf-8"))

            # Skip messages from this instance (echo prevention)
            if data.get("instance_id") == self.instance_id:
                return

            logger.debug(
                f"Received pub/sub message on channel {channel}: {data.get('type')}"
            )

            # Route to appropriate handler
            if channel == "ws:broadcast":
                await self._handle_broadcast(data)
            elif channel.startswith("ws:room:"):
                room_id = channel.split("ws:room:")[-1]
                await self._handle_room_message(room_id, data)
            elif channel.startswith("ws:user:"):
                user_id = channel.split("ws:user:")[-1]
                await self._handle_user_message(user_id, data)
            elif channel == "ws:heartbeat":
                await self._handle_heartbeat(data)

        except Exception as e:
            logger.error(f"Error handling pub/sub message: {e}", exc_info=True)

    async def _handle_broadcast(self, data: Dict[str, Any]):
        """
        Handle broadcast message - send to all local connections.

        Args:
            data: Message data
        """
        payload = data.get("payload", {})
        await self.connection_manager.broadcast(payload)

    async def _handle_room_message(self, room_id: str, data: Dict[str, Any]):
        """
        Handle room-specific message - send to connections in that room.

        Args:
            room_id: Room identifier
            data: Message data
        """
        payload = data.get("payload", {})
        await self.connection_manager.broadcast_to_room(room_id, payload)

    async def _handle_user_message(self, user_id: str, data: Dict[str, Any]):
        """
        Handle user-specific message - send to all user's connections.

        Args:
            user_id: User identifier
            data: Message data
        """
        payload = data.get("payload", {})

        # Get all connections for this user
        user_connections = [
            conn_id
            for conn_id, conn_data in self.connection_manager.connections.items()
            if conn_data.get("user_id") == user_id
        ]

        # Send to each connection
        for conn_id in user_connections:
            await self.connection_manager.send_personal_message(payload, conn_id)

    async def _handle_heartbeat(self, data: Dict[str, Any]):
        """
        Handle heartbeat message for instance discovery.

        Args:
            data: Heartbeat data
        """
        source_instance = data.get("instance_id")
        logger.debug(f"Heartbeat received from instance: {source_instance}")

    # =========================================================================
    # PUBLISH METHODS
    # =========================================================================

    async def publish_broadcast(self, payload: Dict[str, Any]):
        """
        Publish broadcast message to all instances.

        Args:
            payload: Message payload to broadcast
        """
        message = {
            "instance_id": self.instance_id,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        }

        await self.redis_client.publish("ws:broadcast", json.dumps(message))

        logger.debug(f"Published broadcast message: {payload.get('type')}")

    async def publish_to_room(self, room_id: str, payload: Dict[str, Any]):
        """
        Publish message to specific room across all instances.

        Args:
            room_id: Room identifier
            payload: Message payload
        """
        message = {
            "instance_id": self.instance_id,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        }

        channel = f"ws:room:{room_id}"
        await self.redis_client.publish(channel, json.dumps(message))

        logger.debug(f"Published to room {room_id}: {payload.get('type')}")

    async def publish_to_user(self, user_id: str, payload: Dict[str, Any]):
        """
        Publish message to specific user across all devices/instances.

        Args:
            user_id: User identifier
            payload: Message payload
        """
        message = {
            "instance_id": self.instance_id,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        }

        channel = f"ws:user:{user_id}"
        await self.redis_client.publish(channel, json.dumps(message))

        logger.debug(f"Published to user {user_id}: {payload.get('type')}")

    async def send_heartbeat(self):
        """
        Send heartbeat to notify other instances this instance is alive.
        """
        message = {
            "instance_id": self.instance_id,
            "timestamp": datetime.utcnow().isoformat(),
            "connections": len(self.connection_manager.connections),
        }

        await self.redis_client.publish("ws:heartbeat", json.dumps(message))


# Singleton instance (will be initialized in lifespan)
_pubsub_manager: Optional[RedisPubSubManager] = None


def get_pubsub_manager() -> Optional[RedisPubSubManager]:
    """Get the global RedisPubSubManager instance."""
    return _pubsub_manager


def set_pubsub_manager(manager: RedisPubSubManager):
    """Set the global RedisPubSubManager instance."""
    global _pubsub_manager
    _pubsub_manager = manager
