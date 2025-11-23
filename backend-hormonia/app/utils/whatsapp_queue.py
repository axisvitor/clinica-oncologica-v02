"""
WhatsApp Message Queue and related types.
Extracted from whatsapp_helper.py to resolve circular dependencies.
"""
import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from uuid import uuid4

from redis.asyncio import Redis

from app.integrations.whatsapp.models.message import (
    MessageRequest, MessageResponse, MessageStatus
)

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Message priority levels for queue processing."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class DeliveryMode(Enum):
    """Message delivery modes."""
    IMMEDIATE = "immediate"
    QUEUED = "queued"
    SCHEDULED = "scheduled"


@dataclass
class QueuedMessage:
    """Queued message with metadata."""
    id: str
    request: MessageRequest
    priority: Priority
    retry_count: int = 0
    max_retries: int = 3
    scheduled_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    callback: Optional[Callable] = None


@dataclass
class DeliveryReport:
    """Message delivery status report."""
    message_id: str
    status: MessageStatus
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class RateLimiter:
    """Rate limiter for WhatsApp API calls."""

    def __init__(self, max_requests: int = 50, time_window: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire rate limit permission."""
        async with self._lock:
            now = time.time()
            # Remove old requests outside the time window
            while self.requests and self.requests[0] <= now - self.time_window:
                self.requests.popleft()

            # Check if we're at the limit
            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest_request = self.requests[0]
                wait_time = self.time_window - (now - oldest_request)
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                    await asyncio.sleep(wait_time)
                    return await self.acquire()

            # Record this request
            self.requests.append(now)


class MessageQueue:
    """Advanced message queue with priority and batch processing."""

    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize message queue."""
        self.redis_client = redis_client
        self.local_queue: Dict[Priority, List[QueuedMessage]] = {
            priority: [] for priority in Priority
        }
        self._lock = asyncio.Lock()
        self._processing = False

    async def enqueue(self, message: QueuedMessage) -> None:
        """Add message to queue."""
        async with self._lock:
            if self.redis_client:
                # Use Redis for persistent queue
                queue_key = f"whatsapp_queue:{message.priority.name}"
                await self.redis_client.lpush(queue_key, message.id)
                await self.redis_client.hset(
                    f"whatsapp_message:{message.id}",
                    mapping={
                        "data": json.dumps({
                            "request": message.request.dict(),
                            "priority": message.priority.value,
                            "retry_count": message.retry_count,
                            "max_retries": message.max_retries,
                            "scheduled_at": message.scheduled_at.isoformat() if message.scheduled_at else None,
                            "created_at": message.created_at.isoformat()
                        })
                    }
                )
            else:
                # Use local queue
                self.local_queue[message.priority].append(message)

    async def dequeue(self, priority: Optional[Priority] = None) -> Optional[QueuedMessage]:
        """Get next message from queue."""
        async with self._lock:
            if self.redis_client:
                # Try Redis queue
                priorities = [priority] if priority else list(Priority)[::-1]  # High to low
                for p in priorities:
                    queue_key = f"whatsapp_queue:{p.name}"
                    message_id = await self.redis_client.rpop(queue_key)
                    if message_id:
                        data = await self.redis_client.hget(f"whatsapp_message:{message_id}", "data")
                        if data:
                            message_data = json.loads(data)
                            return QueuedMessage(
                                id=message_id,
                                request=MessageRequest(**message_data["request"]),
                                priority=Priority(message_data["priority"]),
                                retry_count=message_data["retry_count"],
                                max_retries=message_data["max_retries"],
                                scheduled_at=datetime.fromisoformat(message_data["scheduled_at"]) if message_data["scheduled_at"] else None,
                                created_at=datetime.fromisoformat(message_data["created_at"])
                            )
            else:
                # Try local queue
                priorities = [priority] if priority else list(Priority)[::-1]
                for p in priorities:
                    if self.local_queue[p]:
                        return self.local_queue[p].pop(0)

            return None

    async def size(self, priority: Optional[Priority] = None) -> int:
        """Get queue size."""
        if self.redis_client:
            if priority:
                return await self.redis_client.llen(f"whatsapp_queue:{priority.name}")
            else:
                total = 0
                for p in Priority:
                    total += await self.redis_client.llen(f"whatsapp_queue:{p.name}")
                return total
        else:
            if priority:
                return len(self.local_queue[priority])
            else:
                return sum(len(queue) for queue in self.local_queue.values())
