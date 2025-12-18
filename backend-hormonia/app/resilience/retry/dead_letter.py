"""
Dead Letter Queue Implementation

Handles persistent failures with retry and recovery mechanisms.
"""

import time
import threading
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from queue import Queue, Empty
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MessageStatus(Enum):
    """Dead letter message status"""

    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    REQUEUED = "requeued"
    DISCARDED = "discarded"


@dataclass
class DeadLetterMessage:
    """Dead letter queue message"""

    id: str
    content: Dict[str, Any]
    status: MessageStatus = MessageStatus.PENDING
    created_at: float = field(default_factory=time.time)
    attempts: int = 0
    last_attempt: Optional[float] = None
    last_error: Optional[str] = None
    requeue_count: int = 0

    @property
    def age(self) -> float:
        """Get message age in seconds"""
        return time.time() - self.created_at

    @property
    def time_since_last_attempt(self) -> Optional[float]:
        """Get time since last processing attempt"""
        if self.last_attempt:
            return time.time() - self.last_attempt
        return None


class DeadLetterQueue:
    """
    Dead letter queue for handling persistent failures

    Features:
    - Message persistence and retry
    - Configurable retry limits
    - Automatic requeuing with backoff
    - Message aging and cleanup
    - Processing callbacks
    """

    def __init__(
        self,
        max_size: int = 10000,
        max_age_hours: int = 24,
        max_retries: int = 3,
        retry_backoff: float = 300.0,  # 5 minutes
        cleanup_interval: float = 3600.0,
    ):  # 1 hour
        self.max_size = max_size
        self.max_age_hours = max_age_hours
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.cleanup_interval = cleanup_interval

        # Storage
        self._messages: Dict[str, DeadLetterMessage] = {}
        self._queue: Queue = Queue(maxsize=max_size)
        self._lock = threading.Lock()

        # Processing
        self._processors: List[Callable] = []
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_processing = threading.Event()

        # Metrics
        self._total_messages = 0
        self._processed_messages = 0
        self._failed_messages = 0
        self._discarded_messages = 0
        self._requeued_messages = 0

        # Cleanup
        self._last_cleanup = time.time()

        logger.info(
            f"Dead letter queue initialized "
            f"(max_size={max_size}, max_age={max_age_hours}h, "
            f"max_retries={max_retries})"
        )

    def add_message(self, content: Dict[str, Any]) -> str:
        """Add message to dead letter queue"""
        message_id = self._generate_message_id()

        message = DeadLetterMessage(id=message_id, content=content)

        with self._lock:
            # Check size limit
            if len(self._messages) >= self.max_size:
                self._evict_oldest_message()

            self._messages[message_id] = message

            try:
                self._queue.put_nowait(message_id)
                self._total_messages += 1

                logger.info(f"Added message to dead letter queue: {message_id}")
                return message_id

            except Exception as e:
                # Queue is full, remove from messages
                del self._messages[message_id]
                logger.error(f"Failed to queue message {message_id}: {str(e)}")
                raise

    def get_message(
        self, timeout: Optional[float] = None
    ) -> Optional[DeadLetterMessage]:
        """Get next message for processing"""
        try:
            message_id = self._queue.get(timeout=timeout)

            with self._lock:
                message = self._messages.get(message_id)
                if message:
                    message.status = MessageStatus.PROCESSING
                    message.attempts += 1
                    message.last_attempt = time.time()

                return message

        except Empty:
            return None

    def mark_processed(self, message_id: str) -> bool:
        """Mark message as successfully processed"""
        with self._lock:
            message = self._messages.get(message_id)
            if not message:
                return False

            # Remove from storage
            del self._messages[message_id]
            self._processed_messages += 1

            logger.debug(f"Message {message_id} processed successfully")
            return True

    def mark_failed(self, message_id: str, error: str) -> bool:
        """Mark message as failed"""
        with self._lock:
            message = self._messages.get(message_id)
            if not message:
                return False

            message.status = MessageStatus.FAILED
            message.last_error = error

            # Check if should requeue or discard
            if message.requeue_count < self.max_retries:
                self._requeue_message(message)
            else:
                self._discard_message(message)

            logger.warning(
                f"Message {message_id} failed (attempt {message.attempts}): {error}"
            )
            return True

    def _requeue_message(self, message: DeadLetterMessage):
        """Requeue message for retry"""
        message.status = MessageStatus.REQUEUED
        message.requeue_count += 1

        # Add back to queue after backoff delay
        def requeue_after_delay():
            time.sleep(self.retry_backoff)
            try:
                self._queue.put_nowait(message.id)
                self._requeued_messages += 1
                logger.info(
                    f"Requeued message {message.id} "
                    f"(attempt {message.requeue_count}/{self.max_retries})"
                )
            except Exception as e:
                logger.error(f"Failed to requeue message {message.id}: {str(e)}")
                self._discard_message(message)

        # Start requeue thread
        thread = threading.Thread(target=requeue_after_delay, daemon=True)
        thread.start()

    def _discard_message(self, message: DeadLetterMessage):
        """Discard message permanently"""
        message.status = MessageStatus.DISCARDED

        # Keep for audit trail but don't process again
        self._discarded_messages += 1
        self._failed_messages += 1

        logger.warning(
            f"Discarded message {message.id} after {message.requeue_count} retries"
        )

    def _evict_oldest_message(self):
        """Evict oldest message to make space"""
        if not self._messages:
            return

        oldest_id = min(
            self._messages.keys(), key=lambda k: self._messages[k].created_at
        )

        message = self._messages[oldest_id]
        del self._messages[oldest_id]

        logger.warning(f"Evicted oldest message {oldest_id} (age={message.age:.1f}s)")

    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        import uuid

        return f"dlq_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    def add_processor(self, processor: Callable[[DeadLetterMessage], bool]):
        """
        Add message processor function

        Processor should return True on success, False on failure
        """
        self._processors.append(processor)
        logger.info(f"Added dead letter queue processor: {processor.__name__}")

    def start_processing(self):
        """Start background processing thread"""
        if self._processing_thread and self._processing_thread.is_alive():
            logger.warning("Dead letter queue processing already started")
            return

        self._stop_processing.clear()
        self._processing_thread = threading.Thread(
            target=self._process_messages, daemon=True
        )
        self._processing_thread.start()

        logger.info("Started dead letter queue processing")

    def stop_processing(self):
        """Stop background processing thread"""
        self._stop_processing.set()

        if self._processing_thread:
            self._processing_thread.join(timeout=5.0)

        logger.info("Stopped dead letter queue processing")

    def _process_messages(self):
        """Background message processing"""
        while not self._stop_processing.is_set():
            try:
                # Get next message
                message = self.get_message(timeout=1.0)
                if not message:
                    continue

                # Process with registered processors
                success = False
                for processor in self._processors:
                    try:
                        if processor(message):
                            success = True
                            break
                    except Exception as e:
                        logger.error(
                            f"Processor {processor.__name__} failed "
                            f"for message {message.id}: {str(e)}"
                        )

                # Mark result
                if success:
                    self.mark_processed(message.id)
                else:
                    self.mark_failed(message.id, "All processors failed")

                # Cleanup if needed
                self._cleanup_if_needed()

            except Exception as e:
                logger.error(f"Error in dead letter queue processing: {str(e)}")
                time.sleep(1.0)

    def _cleanup_if_needed(self):
        """Cleanup old messages if needed"""
        current_time = time.time()
        if current_time - self._last_cleanup < self.cleanup_interval:
            return

        max_age_seconds = self.max_age_hours * 3600
        expired_ids = []

        with self._lock:
            for message_id, message in self._messages.items():
                if message.age > max_age_seconds:
                    expired_ids.append(message_id)

            for message_id in expired_ids:
                del self._messages[message_id]

        self._last_cleanup = current_time

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired messages")

    def get_metrics(self) -> Dict:
        """Get dead letter queue metrics"""
        with self._lock:
            pending_count = sum(
                1 for m in self._messages.values() if m.status == MessageStatus.PENDING
            )
            processing_count = sum(
                1
                for m in self._messages.values()
                if m.status == MessageStatus.PROCESSING
            )
            failed_count = sum(
                1 for m in self._messages.values() if m.status == MessageStatus.FAILED
            )
            discarded_count = sum(
                1
                for m in self._messages.values()
                if m.status == MessageStatus.DISCARDED
            )

        return {
            "total_messages": self._total_messages,
            "processed_messages": self._processed_messages,
            "failed_messages": self._failed_messages,
            "discarded_messages": self._discarded_messages,
            "requeued_messages": self._requeued_messages,
            "current_size": len(self._messages),
            "max_size": self.max_size,
            "queue_size": self._queue.qsize(),
            "pending_count": pending_count,
            "processing_count": processing_count,
            "failed_count": failed_count,
            "discarded_count": discarded_count,
            "processors_count": len(self._processors),
            "processing_active": (
                self._processing_thread and self._processing_thread.is_alive()
            ),
        }

    def get_messages(
        self, status: Optional[MessageStatus] = None, limit: int = 100
    ) -> List[Dict]:
        """Get messages with optional status filter"""
        with self._lock:
            messages = []
            for message in self._messages.values():
                if status is None or message.status == status:
                    messages.append(
                        {
                            "id": message.id,
                            "status": message.status.value,
                            "age": message.age,
                            "attempts": message.attempts,
                            "requeue_count": message.requeue_count,
                            "last_error": message.last_error,
                            "content": message.content,
                        }
                    )

                if len(messages) >= limit:
                    break

        return messages

    def clear(self):
        """Clear all messages"""
        with self._lock:
            self._messages.clear()

            # Clear queue
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except Empty:
                    break

        logger.info("Dead letter queue cleared")

    def size(self) -> int:
        """Get current queue size"""
        return len(self._messages)

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return len(self._messages) == 0
