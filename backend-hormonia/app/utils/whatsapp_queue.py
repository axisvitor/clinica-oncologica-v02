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


class PerPatientRateLimiter:
    """
    Per-patient rate limiter for WhatsApp messages.

    QW-003: Implements per-patient rate limiting to prevent message flooding
    and ensure fair resource distribution across patients.
    """

    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        max_messages_per_minute: int = 10,
        max_messages_per_hour: int = 50,
        max_messages_per_day: int = 200
    ):
        """
        Initialize per-patient rate limiter.

        Args:
            redis_client: Redis client for distributed rate limiting
            max_messages_per_minute: Max messages per patient per minute
            max_messages_per_hour: Max messages per patient per hour
            max_messages_per_day: Max messages per patient per day
        """
        self.redis = redis_client
        self.max_per_minute = max_messages_per_minute
        self.max_per_hour = max_messages_per_hour
        self.max_per_day = max_messages_per_day
        self._local_counters: Dict[str, Dict[str, int]] = {}
        self._lock = asyncio.Lock()

    def _get_time_keys(self, patient_id: str) -> Dict[str, tuple]:
        """Get Redis keys and TTLs for rate limit windows."""
        now = datetime.utcnow()
        return {
            "minute": (f"rate:patient:{patient_id}:minute:{now.strftime('%Y%m%d%H%M')}", 60),
            "hour": (f"rate:patient:{patient_id}:hour:{now.strftime('%Y%m%d%H')}", 3600),
            "day": (f"rate:patient:{patient_id}:day:{now.strftime('%Y%m%d')}", 86400)
        }

    async def check_rate_limit(self, patient_id: str) -> Dict[str, Any]:
        """
        Check if patient is within rate limits.

        Returns:
            Dict with 'allowed' bool and 'retry_after' seconds if blocked
        """
        if self.redis:
            return await self._check_rate_limit_redis(patient_id)
        return await self._check_rate_limit_local(patient_id)

    async def _check_rate_limit_redis(self, patient_id: str) -> Dict[str, Any]:
        """Check rate limits using Redis."""
        time_keys = self._get_time_keys(patient_id)

        # Get all current counts
        pipe = self.redis.pipeline()
        for key, _ in time_keys.values():
            pipe.get(key)
        results = await pipe.execute()

        minute_count = int(results[0] or 0)
        hour_count = int(results[1] or 0)
        day_count = int(results[2] or 0)

        # Check limits
        if minute_count >= self.max_per_minute:
            return {"allowed": False, "retry_after": 60, "reason": "minute_limit"}
        if hour_count >= self.max_per_hour:
            return {"allowed": False, "retry_after": 3600, "reason": "hour_limit"}
        if day_count >= self.max_per_day:
            return {"allowed": False, "retry_after": 86400, "reason": "day_limit"}

        return {"allowed": True, "remaining_minute": self.max_per_minute - minute_count}

    async def _check_rate_limit_local(self, patient_id: str) -> Dict[str, Any]:
        """Check rate limits using local memory (single instance only)."""
        async with self._lock:
            now = datetime.utcnow()
            minute_key = now.strftime('%Y%m%d%H%M')
            hour_key = now.strftime('%Y%m%d%H')
            day_key = now.strftime('%Y%m%d')

            if patient_id not in self._local_counters:
                self._local_counters[patient_id] = {}

            counters = self._local_counters[patient_id]

            # Clean old keys
            keys_to_remove = [k for k in counters.keys()
                             if not k.startswith(('m:' + minute_key, 'h:' + hour_key, 'd:' + day_key))]
            for k in keys_to_remove:
                del counters[k]

            minute_count = counters.get(f'm:{minute_key}', 0)
            hour_count = counters.get(f'h:{hour_key}', 0)
            day_count = counters.get(f'd:{day_key}', 0)

            if minute_count >= self.max_per_minute:
                return {"allowed": False, "retry_after": 60, "reason": "minute_limit"}
            if hour_count >= self.max_per_hour:
                return {"allowed": False, "retry_after": 3600, "reason": "hour_limit"}
            if day_count >= self.max_per_day:
                return {"allowed": False, "retry_after": 86400, "reason": "day_limit"}

            return {"allowed": True, "remaining_minute": self.max_per_minute - minute_count}

    async def record_message(self, patient_id: str) -> None:
        """Record a message sent to patient for rate limiting."""
        if self.redis:
            await self._record_message_redis(patient_id)
        else:
            await self._record_message_local(patient_id)

    async def _record_message_redis(self, patient_id: str) -> None:
        """Record message in Redis with atomic increment."""
        time_keys = self._get_time_keys(patient_id)

        pipe = self.redis.pipeline()
        for key, ttl in time_keys.values():
            pipe.incr(key)
            pipe.expire(key, ttl)
        await pipe.execute()

    async def _record_message_local(self, patient_id: str) -> None:
        """Record message in local memory."""
        async with self._lock:
            now = datetime.utcnow()

            if patient_id not in self._local_counters:
                self._local_counters[patient_id] = {}

            counters = self._local_counters[patient_id]
            counters[f'm:{now.strftime("%Y%m%d%H%M")}'] = counters.get(f'm:{now.strftime("%Y%m%d%H%M")}', 0) + 1
            counters[f'h:{now.strftime("%Y%m%d%H")}'] = counters.get(f'h:{now.strftime("%Y%m%d%H")}', 0) + 1
            counters[f'd:{now.strftime("%Y%m%d")}'] = counters.get(f'd:{now.strftime("%Y%m%d")}', 0) + 1


@dataclass
class OrderedMessage:
    """Message with sequence number for ordering."""
    id: str
    patient_id: str
    request: MessageRequest
    sequence_number: int
    priority: Priority = Priority.NORMAL
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)


class OrderedMessageQueue:
    """
    Per-patient ordered message queue with FIFO guarantee.

    QW-003: Ensures messages are delivered to each patient in order,
    while allowing concurrent processing across different patients.

    Uses Redis sorted sets for ordering and per-patient processing locks.
    """

    def __init__(
        self,
        redis_client: Redis,
        rate_limiter: Optional[PerPatientRateLimiter] = None
    ):
        """
        Initialize ordered message queue.

        Args:
            redis_client: Redis client (required for distributed ordering)
            rate_limiter: Optional per-patient rate limiter
        """
        self.redis = redis_client
        self.rate_limiter = rate_limiter or PerPatientRateLimiter(redis_client)
        self._processing_patients: set = set()
        self._lock = asyncio.Lock()

    def _queue_key(self, patient_id: str) -> str:
        """Get Redis key for patient's message queue."""
        return f"ordered_queue:patient:{patient_id}"

    def _sequence_key(self, patient_id: str) -> str:
        """Get Redis key for patient's sequence counter."""
        return f"sequence:patient:{patient_id}"

    def _message_key(self, message_id: str) -> str:
        """Get Redis key for message data."""
        return f"ordered_message:{message_id}"

    def _processing_lock_key(self, patient_id: str) -> str:
        """Get Redis key for patient processing lock."""
        return f"processing_lock:patient:{patient_id}"

    async def get_next_sequence(self, patient_id: str) -> int:
        """
        Get next sequence number for patient atomically.

        Uses Redis INCR for atomic sequence generation.
        """
        key = self._sequence_key(patient_id)
        sequence = await self.redis.incr(key)
        # Set TTL of 24 hours on first creation
        if sequence == 1:
            await self.redis.expire(key, 86400)
        return sequence

    async def enqueue(
        self,
        patient_id: str,
        request: MessageRequest,
        priority: Priority = Priority.NORMAL,
        message_id: Optional[str] = None
    ) -> OrderedMessage:
        """
        Add message to patient's ordered queue.

        Messages are stored in a sorted set with sequence number as score,
        ensuring FIFO ordering per patient.

        Args:
            patient_id: Patient identifier
            request: Message request
            priority: Message priority
            message_id: Optional custom message ID

        Returns:
            OrderedMessage with assigned sequence number
        """
        # Check rate limit first
        rate_check = await self.rate_limiter.check_rate_limit(patient_id)
        if not rate_check["allowed"]:
            logger.warning(
                f"Rate limit exceeded for patient {patient_id}: {rate_check['reason']}. "
                f"Retry after {rate_check['retry_after']}s"
            )
            # Still enqueue but with delay flag
            # The processor will respect the delay

        # Get sequence number atomically
        sequence = await self.get_next_sequence(patient_id)

        message = OrderedMessage(
            id=message_id or str(uuid4()),
            patient_id=patient_id,
            request=request,
            sequence_number=sequence,
            priority=priority
        )

        # Store message data
        await self.redis.hset(
            self._message_key(message.id),
            mapping={
                "patient_id": patient_id,
                "request": json.dumps(request.dict()),
                "sequence_number": sequence,
                "priority": priority.value,
                "retry_count": 0,
                "max_retries": message.max_retries,
                "created_at": message.created_at.isoformat()
            }
        )
        # Set TTL on message data
        await self.redis.expire(self._message_key(message.id), 86400)

        # Add to sorted set with sequence as score (FIFO)
        # Use priority * 1000000 + sequence for priority-aware FIFO
        score = (5 - priority.value) * 1000000 + sequence
        await self.redis.zadd(self._queue_key(patient_id), {message.id: score})

        logger.debug(
            f"Enqueued message {message.id} for patient {patient_id} "
            f"with sequence {sequence}, priority {priority.name}"
        )

        return message

    async def dequeue(self, patient_id: str) -> Optional[OrderedMessage]:
        """
        Get next message from patient's queue.

        Uses ZPOPMIN to atomically get and remove the lowest score message.

        Args:
            patient_id: Patient identifier

        Returns:
            OrderedMessage if available, None otherwise
        """
        queue_key = self._queue_key(patient_id)

        # Atomic pop of lowest score (next in sequence)
        result = await self.redis.zpopmin(queue_key)

        if not result:
            return None

        message_id, score = result[0]
        if isinstance(message_id, bytes):
            message_id = message_id.decode('utf-8')

        # Get message data
        data = await self.redis.hgetall(self._message_key(message_id))
        if not data:
            logger.warning(f"Message data not found for {message_id}")
            return None

        # Decode bytes if necessary
        if isinstance(list(data.keys())[0], bytes):
            data = {k.decode('utf-8'): v.decode('utf-8') for k, v in data.items()}

        return OrderedMessage(
            id=message_id,
            patient_id=data["patient_id"],
            request=MessageRequest(**json.loads(data["request"])),
            sequence_number=int(data["sequence_number"]),
            priority=Priority(int(data["priority"])),
            retry_count=int(data["retry_count"]),
            max_retries=int(data["max_retries"]),
            created_at=datetime.fromisoformat(data["created_at"])
        )

    async def peek(self, patient_id: str) -> Optional[OrderedMessage]:
        """
        Peek at next message without removing.

        Args:
            patient_id: Patient identifier

        Returns:
            OrderedMessage if available, None otherwise
        """
        queue_key = self._queue_key(patient_id)

        # Get lowest score without removing
        result = await self.redis.zrange(queue_key, 0, 0, withscores=True)

        if not result:
            return None

        message_id = result[0][0]
        if isinstance(message_id, bytes):
            message_id = message_id.decode('utf-8')

        data = await self.redis.hgetall(self._message_key(message_id))
        if not data:
            return None

        if isinstance(list(data.keys())[0], bytes):
            data = {k.decode('utf-8'): v.decode('utf-8') for k, v in data.items()}

        return OrderedMessage(
            id=message_id,
            patient_id=data["patient_id"],
            request=MessageRequest(**json.loads(data["request"])),
            sequence_number=int(data["sequence_number"]),
            priority=Priority(int(data["priority"])),
            retry_count=int(data["retry_count"]),
            max_retries=int(data["max_retries"]),
            created_at=datetime.fromisoformat(data["created_at"])
        )

    async def requeue(self, message: OrderedMessage, delay_seconds: int = 0) -> None:
        """
        Re-add failed message to queue for retry.

        Args:
            message: Message to requeue
            delay_seconds: Optional delay before reprocessing
        """
        message.retry_count += 1

        if message.retry_count > message.max_retries:
            logger.error(
                f"Message {message.id} exceeded max retries ({message.max_retries}). "
                f"Moving to DLQ."
            )
            await self._move_to_dlq(message)
            return

        # Update retry count in Redis
        await self.redis.hset(
            self._message_key(message.id),
            "retry_count",
            str(message.retry_count)
        )

        # Requeue with same sequence to maintain order
        score = (5 - message.priority.value) * 1000000 + message.sequence_number
        if delay_seconds > 0:
            # Add delay to score to push it back
            score += delay_seconds * 1000

        await self.redis.zadd(self._queue_key(message.patient_id), {message.id: score})

        logger.info(
            f"Requeued message {message.id} for patient {message.patient_id}, "
            f"retry {message.retry_count}/{message.max_retries}"
        )

    async def _move_to_dlq(self, message: OrderedMessage) -> None:
        """Move failed message to dead letter queue."""
        dlq_key = f"dlq:patient:{message.patient_id}"
        await self.redis.lpush(dlq_key, message.id)
        await self.redis.expire(dlq_key, 604800)  # 7 days retention

        logger.warning(f"Message {message.id} moved to DLQ for patient {message.patient_id}")

    async def queue_size(self, patient_id: str) -> int:
        """Get number of messages in patient's queue."""
        return await self.redis.zcard(self._queue_key(patient_id))

    async def get_patients_with_pending_messages(self) -> List[str]:
        """Get list of patients with pending messages."""
        pattern = "ordered_queue:patient:*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            if isinstance(key, bytes):
                key = key.decode('utf-8')
            # Extract patient_id from key
            patient_id = key.replace("ordered_queue:patient:", "")
            # Check if queue is not empty
            if await self.redis.zcard(key) > 0:
                keys.append(patient_id)
        return keys

    async def acquire_patient_processing_lock(
        self,
        patient_id: str,
        ttl: int = 60
    ) -> Optional[str]:
        """
        Acquire exclusive processing lock for patient.

        Ensures only one worker processes messages for a patient at a time,
        maintaining order while allowing parallel processing across patients.

        Args:
            patient_id: Patient identifier
            ttl: Lock time-to-live in seconds

        Returns:
            Lock ID if acquired, None otherwise
        """
        lock_key = self._processing_lock_key(patient_id)
        lock_id = str(uuid4())

        # Use SET NX EX for atomic lock acquisition
        acquired = await self.redis.set(lock_key, lock_id, nx=True, ex=ttl)

        if acquired:
            logger.debug(f"Acquired processing lock for patient {patient_id}")
            return lock_id

        return None

    async def release_patient_processing_lock(
        self,
        patient_id: str,
        lock_id: str
    ) -> bool:
        """
        Release patient processing lock.

        Uses Lua script for atomic check-and-delete.

        Args:
            patient_id: Patient identifier
            lock_id: Lock ID from acquire

        Returns:
            True if released, False if not owner
        """
        lock_key = self._processing_lock_key(patient_id)

        # Lua script for atomic check-and-delete
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await self.redis.eval(script, 1, lock_key, lock_id)
        return result == 1

    async def extend_patient_processing_lock(
        self,
        patient_id: str,
        lock_id: str,
        ttl: int = 60
    ) -> bool:
        """
        Extend patient processing lock TTL.

        Args:
            patient_id: Patient identifier
            lock_id: Lock ID from acquire
            ttl: New TTL in seconds

        Returns:
            True if extended, False if not owner
        """
        lock_key = self._processing_lock_key(patient_id)

        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = await self.redis.eval(script, 1, lock_key, lock_id, str(ttl))
        return result == 1
