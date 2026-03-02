"""
Queue Manager for WhatsApp message processing.

Handles message queuing, routing, and delivery to Evolution instances.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Awaitable

import redis.asyncio as redis
from sqlalchemy.orm import Session

from .schemas import MessageRequest, MessageResponse, QueueStatus
from .dlq import DLQHandler
from app.models.failed_message import FailureReason
from app.integrations.wuzapi.errors import WuzAPIError
from app.utils.logging import get_logger
from app.config import settings
from app.core.redis_manager import get_async_redis_client, get_redis_connection_kwargs
from app.integrations.whatsapp.metrics import whatsapp_metrics
from app.utils.timezone import now_sao_paulo

logger = get_logger(__name__)


class QueueManager:
    """
    Manages message queues for WhatsApp integration.

    Provides functionality for:
    - Message queuing and routing
    - Multi-instance Evolution support
    - Retry logic and error handling
    - Queue monitoring and health checks
    """

    def __init__(
        self,
        default_instance: str = "primary",
        redis_url: Optional[str] = None,
        redis_client: Optional[redis.Redis] = None,
        message_sender: Optional[Callable[[MessageRequest], Awaitable[MessageResponse]]] = None,
        db: Optional[Session] = None,
    ):
        """
        Initialize the Queue Manager.

        Args:
            default_instance: Default Evolution instance name
            redis_url: Redis URL for queue storage
            redis_client: Optional Redis client
            message_sender: Optional async function to send messages
            db: Optional DB session for DLQ routing
        """
        self.default_instance = default_instance
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client = redis_client
        self._uses_shared_client = False
        self.message_sender = message_sender
        self.dlq_handler = DLQHandler(db) if db else None

        self._is_running = False
        self._watchdog_task: Optional[asyncio.Task] = None
        self._stats = {
            "messages_sent": 0,
            "messages_failed": 0,
            "last_activity": None,
        }

        logger.info(
            "QueueManager initialized",
            extra={"default_instance": default_instance},
        )

    async def connect(self) -> None:
        """Connect to Redis if needed."""
        if not self.redis_client:
            if self.redis_url == settings.REDIS_URL:
                self.redis_client = await get_async_redis_client()
                self._uses_shared_client = True
            else:
                kwargs = get_redis_connection_kwargs(
                    decode_responses=getattr(settings, "REDIS_ENABLE_DECODE_RESPONSES", True),
                    socket_timeout=getattr(settings, "REDIS_SOCKET_TIMEOUT_SECONDS", 5.0),
                    socket_connect_timeout=getattr(
                        settings, "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", 2.0
                    ),
                    mode="async",
                    max_connections=getattr(settings, "REDIS_POOL_MAX_CONNECTIONS", 20),
                    retry_on_timeout=getattr(settings, "REDIS_ENABLE_RETRY_ON_TIMEOUT", True),
                )
                self.redis_client = redis.from_url(self.redis_url, **kwargs)

    async def disconnect(self) -> None:
        """Disconnect Redis client."""
        if self.redis_client and not self._uses_shared_client:
            await self.redis_client.aclose()
            self.redis_client = None
        self._uses_shared_client = False

    def _queue_key(self, instance_name: str) -> str:
        return f"whatsapp:queue:{instance_name}"

    def _processing_key(self, instance_name: str) -> str:
        return f"whatsapp:processing:{instance_name}"

    def _failed_key(self, instance_name: str) -> str:
        return f"whatsapp:failed:{instance_name}"

    def _delayed_key(self, instance_name: str) -> str:
        return f"whatsapp:delayed:{instance_name}"

    def _idempotency_key(self, instance_name: str, message_id: str) -> str:
        return f"whatsapp:processed:{instance_name}:{message_id}"

    async def send_message(self, request: MessageRequest) -> MessageResponse:
        """
        Send a message through the queue system.

        Args:
            request: Message request to send

        Returns:
            MessageResponse with result
        """
        message_id = request.message_id or str(uuid.uuid4())
        request.message_id = message_id

        await self.queue_message(request)

        return MessageResponse(
            success=True,
            message_id=message_id,
            timestamp=now_sao_paulo(),
            instance_name=request.instance_name,
        )

    async def queue_message(self, request: MessageRequest) -> bool:
        """
        Add a message to the processing queue.

        Args:
            request: Message request to queue

        Returns:
            True if queued successfully
        """
        try:
            await self.connect()
            queue_name = request.instance_name or self.default_instance
            message_id = request.message_id or str(uuid.uuid4())
            request.message_id = message_id

            message_payload = {
                "message_id": message_id,
                "instance_name": queue_name,
                "request": request.model_dump(),
                "retry_count": request.retry_count,
                "retry_timestamps": [],
                "created_at": now_sao_paulo().isoformat(),
            }

            await self.redis_client.lpush(
                self._queue_key(queue_name), json.dumps(message_payload, default=str)
            )

            self._stats["last_activity"] = now_sao_paulo()
            logger.info("Message queued", extra={"instance": queue_name})
            return True

        except Exception as e:
            logger.error(f"Failed to queue message: {e}")
            return False

    async def get_queue_status(self, instance_name: Optional[str] = None) -> QueueStatus:
        """
        Get status of message queues.

        Args:
            instance_name: Specific instance to check, or None for default

        Returns:
            QueueStatus with current metrics
        """
        await self.connect()
        queue_name = instance_name or self.default_instance

        pending = await self.redis_client.llen(self._queue_key(queue_name))
        processing = await self.redis_client.llen(self._processing_key(queue_name))
        failed = await self.redis_client.llen(self._failed_key(queue_name))

        whatsapp_metrics.set_queue_size(queue_name, pending)
        whatsapp_metrics.set_dlq_size(queue_name, failed)

        return QueueStatus(
            queue_name=queue_name,
            pending_messages=pending,
            processing_messages=processing,
            failed_messages=failed,
            last_activity=self._stats["last_activity"],
            is_healthy=True,
        )

    async def start_processing(self, instance_name: Optional[str] = None) -> None:
        """Start the queue processing loop."""
        if self._is_running:
            logger.warning("Queue processing is already running")
            return

        self._is_running = True
        instance = instance_name or self.default_instance

        if not self._watchdog_task or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog_loop(instance))

        asyncio.create_task(self.process_queue_loop(instance))
        logger.info("Started queue processing", extra={"instance": instance})

    async def stop_processing(self) -> None:
        """Stop the queue processing loop."""
        self._is_running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
        logger.info("Stopped queue processing")

    async def process_queue_loop(self, instance_name: str) -> None:
        """Process messages from the queue in batches."""
        await self.connect()
        batch_size = 10

        while self._is_running:
            await self._drain_due_retries(instance_name)
            batch = await self._dequeue_batch(instance_name, batch_size)
            if not batch:
                await asyncio.sleep(0.1)
                continue

            tasks = [
                asyncio.create_task(self._process_payload(instance_name, item))
                for item in batch
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.sleep(0.1)

    async def _dequeue_batch(
        self, instance_name: str, batch_size: int
    ) -> List[Dict[str, Any]]:
        """Dequeue a batch of messages using atomic Redis move+metadata update."""
        queue_key = self._queue_key(instance_name)
        processing_key = self._processing_key(instance_name)
        now = now_sao_paulo().isoformat()
        batch: List[Dict[str, Any]] = []

        for _ in range(batch_size):
            raw_message = await self._atomic_dequeue_to_processing(
                queue_key=queue_key,
                processing_key=processing_key,
                processing_started_at=now,
            )
            if not raw_message:
                break

            if isinstance(raw_message, bytes):
                raw_message = raw_message.decode("utf-8")

            payload = json.loads(raw_message)
            batch.append({"raw": raw_message, "payload": payload})

        return batch

    async def _atomic_dequeue_to_processing(
        self, queue_key: str, processing_key: str, processing_started_at: str
    ) -> Optional[str]:
        """
        Atomically move one payload to processing queue and stamp processing time.

        Uses Lua to avoid non-atomic RPOPLPUSH + LREM/LPUSH sequences that can
        race with watchdog requeue and cause duplicate processing.
        """
        lua = """
        local moved = redis.call('RPOPLPUSH', KEYS[1], KEYS[2])
        if not moved then
            return nil
        end
        local payload = cjson.decode(moved)
        payload['processing_started_at'] = ARGV[1]
        local updated = cjson.encode(payload)
        redis.call('LSET', KEYS[2], 0, updated)
        return updated
        """
        return await self.redis_client.eval(
            lua, 2, queue_key, processing_key, processing_started_at
        )

    def _calculate_retry_backoff(self, retry_count: int) -> int:
        """Exponential backoff in seconds (1m, 2m, 4m...)."""
        return 60 * (2 ** (retry_count - 1))

    async def _schedule_retry(
        self, instance_name: str, payload: Dict[str, Any], delay_seconds: int
    ) -> None:
        """
        Persist retry schedule in Redis sorted set.

        This avoids in-memory sleep-only scheduling, so retries survive worker restarts.
        """
        retry_at = now_sao_paulo().timestamp() + max(0, int(delay_seconds))
        await self.redis_client.zadd(
            self._delayed_key(instance_name),
            {json.dumps(payload, default=str): retry_at},
        )

    async def _drain_due_retries(self, instance_name: str, max_items: int = 100) -> int:
        """Move due delayed retries back to the main queue."""
        delayed_key = self._delayed_key(instance_name)
        queue_key = self._queue_key(instance_name)
        now_ts = now_sao_paulo().timestamp()
        moved = 0

        for _ in range(max_items):
            popped = await self.redis_client.zpopmin(delayed_key, 1)
            if not popped:
                break

            value, score = popped[0]
            score_val = float(score)

            if score_val > now_ts:
                await self.redis_client.zadd(delayed_key, {value: score_val})
                break

            await self.redis_client.lpush(queue_key, value)
            moved += 1

        return moved

    async def _process_payload(self, instance_name: str, item: Dict[str, Any]) -> None:
        """Process a queued message payload."""
        payload = item["payload"]
        raw = item["raw"]

        message_id = payload.get("message_id") or payload.get("request", {}).get(
            "message_id"
        )
        if not message_id:
            message_id = str(uuid.uuid4())
            payload["message_id"] = message_id

        request = MessageRequest(**payload["request"])
        idempotency_key = self._idempotency_key(instance_name, message_id)

        if await self.redis_client.exists(idempotency_key):
            await self._ack_processing(instance_name, raw)
            return

        try:
            response = await self._send_with_handler(request)
            await self._ack_processing(instance_name, raw)
            await self.redis_client.set(idempotency_key, "1", ex=86400)
            self._stats["messages_sent"] += 1
            self._stats["last_activity"] = now_sao_paulo()
            whatsapp_metrics.record_message_sent(instance_name, "sent")
            logger.info(
                "Message processed successfully",
                extra={"message_id": response.message_id, "instance": instance_name},
            )
        except Exception as exc:
            await self._handle_failure(instance_name, payload, raw, exc)

    async def _send_with_handler(self, request: MessageRequest) -> MessageResponse:
        """Send message using the provided handler or fallback stub."""
        if self.message_sender:
            return await self.message_sender(request)

        # Fallback stub for testing environments
        await asyncio.sleep(0.01)
        return MessageResponse(
            success=True,
            message_id=request.message_id or str(uuid.uuid4()),
            timestamp=now_sao_paulo(),
            instance_name=request.instance_name,
        )

    async def _handle_failure(
        self,
        instance_name: str,
        payload: Dict[str, Any],
        raw: str,
        error: Exception,
    ) -> None:
        """Handle message processing failure with retry and DLQ."""
        retry_count = payload.get("retry_count", 0) + 1
        payload["retry_count"] = retry_count
        payload.setdefault("retry_timestamps", []).append(
            now_sao_paulo().isoformat()
        )

        await self._ack_processing(instance_name, raw)
        self._stats["messages_failed"] += 1

        if retry_count < 3:
            backoff_seconds = self._calculate_retry_backoff(retry_count)
            await self._schedule_retry(instance_name, payload, backoff_seconds)
            logger.warning(
                "Message scheduled for retry",
                extra={
                    "instance": instance_name,
                    "retry_count": retry_count,
                    "backoff_seconds": backoff_seconds,
                },
            )
            return

        failure_reason = self._categorize_failure(error)
        await self.redis_client.lpush(
            self._failed_key(instance_name), json.dumps(payload, default=str)
        )
        whatsapp_metrics.record_message_failed(
            instance_name, failure_reason.value
        )

        if self.dlq_handler:
            await self._route_to_dlq(payload, failure_reason, error)

        logger.error(
            "Message moved to DLQ after max retries",
            extra={
                "instance": instance_name,
                "retry_count": retry_count,
                "failure_reason": failure_reason.value,
            },
        )

    async def _requeue_with_delay(
        self, instance_name: str, payload: Dict[str, Any], delay_seconds: int
    ) -> None:
        """Backward-compatible wrapper for durable retry scheduling."""
        await self._schedule_retry(instance_name, payload, delay_seconds)

    async def _ack_processing(self, instance_name: str, raw: str) -> None:
        """Remove a message from the processing list."""
        await self.redis_client.lrem(self._processing_key(instance_name), 0, raw)

    async def _watchdog_loop(self, instance_name: str) -> None:
        """Watchdog to reprocess stuck messages in processing list."""
        await self.connect()
        processing_key = self._processing_key(instance_name)
        while self._is_running:
            try:
                now = now_sao_paulo()
                entries = await self.redis_client.lrange(processing_key, 0, -1)
                for entry in entries:
                    if isinstance(entry, bytes):
                        entry = entry.decode("utf-8")
                    payload = json.loads(entry)
                    started_at = payload.get("processing_started_at")
                    if not started_at:
                        continue
                    started_dt = datetime.fromisoformat(started_at)
                    if (now - started_dt).total_seconds() > 300:
                        await self.redis_client.lrem(processing_key, 1, entry)
                        payload["processing_started_at"] = None
                        await self.redis_client.lpush(
                            self._queue_key(instance_name),
                            json.dumps(payload, default=str),
                        )
                        logger.warning(
                            "Requeued stuck message",
                            extra={"instance": instance_name},
                        )
            except Exception as e:
                logger.error(f"Watchdog error: {e}")

            await asyncio.sleep(30)

    def _categorize_failure(self, error: Exception) -> FailureReason:
        """Categorize failures for DLQ routing."""
        if isinstance(error, asyncio.TimeoutError):
            return FailureReason.TIMEOUT
        if isinstance(error, ValueError) and "phone" in str(error).lower():
            return FailureReason.INVALID_PHONE
        if isinstance(error, WuzAPIError) and error.status == 429:
            return FailureReason.RATE_LIMIT
        if isinstance(error, WuzAPIError):
            return FailureReason.API_ERROR
        if "rate" in str(error).lower() and "limit" in str(error).lower():
            return FailureReason.RATE_LIMIT
        return FailureReason.API_ERROR

    async def _route_to_dlq(
        self, payload: Dict[str, Any], failure_reason: FailureReason, error: Exception
    ) -> None:
        """Route message to DLQ handler, preserving metadata."""
        from uuid import UUID

        request = MessageRequest(**payload["request"])
        metadata = request.metadata or {}
        patient_id = metadata.get("patient_id") or request.patient_id
        message_uuid = (
            metadata.get("message_uuid")
            or metadata.get("message_id")
            or request.message_id
        )

        if not patient_id:
            logger.error("Missing patient_id for DLQ routing")
            return

        try:
            patient_id = UUID(str(patient_id))
        except Exception:
            logger.error("Invalid patient_id for DLQ routing")
            return

        if message_uuid:
            try:
                message_uuid = UUID(str(message_uuid))
            except Exception:
                message_uuid = None

        await self.dlq_handler.route_to_dlq(
            message_id=message_uuid,
            patient_id=patient_id,
            content=request.text or "",
            whatsapp_phone=request.to,
            failure_reason=failure_reason,
            failure_details={"error": str(error)},
            retry_count=payload.get("retry_count", 0),
            metadata=metadata,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            **self._stats,
            "is_running": self._is_running,
            "default_instance": self.default_instance,
        }


# Global queue manager instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager(default_instance: str = "primary") -> QueueManager:
    """
    Get or create the global queue manager instance.

    Args:
        default_instance: Default instance name

    Returns:
        QueueManager instance
    """
    global _queue_manager

    if _queue_manager is None:
        _queue_manager = QueueManager(default_instance=default_instance)

    return _queue_manager


def reset_queue_manager() -> None:
    """Reset the global queue manager (for testing)."""
    global _queue_manager
    _queue_manager = None
