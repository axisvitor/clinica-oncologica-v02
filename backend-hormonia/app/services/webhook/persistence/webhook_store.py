"""
Webhook event persistence store.
Extracted from webhook_processor.py for modularity.
"""
import hashlib
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class WebhookEventStore:
    """
    Persistence layer for webhook events.
    
    Provides idempotent event storage, processing status tracking,
    and retry management for failed webhooks.
    """
    
    def __init__(self, db: Any):
        """
        Initialize webhook event store.
        
        Args:
            db: Database session
        """
        self.db = db
    
    async def persist_event(
        self,
        event_type: str,
        source: str,
        payload: Dict[str, Any],
        related_message_id: Optional[UUID] = None,
        related_patient_id: Optional[UUID] = None
    ) -> Optional[UUID]:
        """
        Persist webhook event to database with idempotency check.
        
        Uses SHA-256 hash of payload for duplicate detection.
        
        Args:
            event_type: Type of webhook event
            source: Source of webhook (e.g., 'evolution_api')
            payload: Raw webhook payload
            related_message_id: Optional related message ID
            related_patient_id: Optional related patient ID
            
        Returns:
            UUID of created event, or None if duplicate/failed
        """
        try:
            # Generate event hash for idempotency
            payload_str = str(sorted(payload.items()))
            event_hash = hashlib.sha256(payload_str.encode()).hexdigest()
            
            # Check if event already exists
            stmt = text("""
                SELECT id FROM webhook_events
                WHERE event_hash = :event_hash
                LIMIT 1
            """)
            result = self.db.execute(stmt, {"event_hash": event_hash}).fetchone()
            
            if result:
                logger.info(
                    f"Duplicate webhook event detected via hash",
                    extra={"event_hash": event_hash[:16], "event_type": event_type}
                )
                return UUID(result[0]) if result[0] else None
            
            # Create new webhook event record
            event_id = uuid4()
            insert_stmt = text("""
                INSERT INTO webhook_events (
                    id, event_type, source, payload, processed, retry_count, max_retries,
                    related_message_id, related_patient_id, event_hash, is_duplicate,
                    created_at
                )
                VALUES (
                    :id, :event_type, :source, :payload, :processed, :retry_count, :max_retries,
                    :related_message_id, :related_patient_id, :event_hash, :is_duplicate,
                    NOW()
                )
                RETURNING id
            """)
            
            self.db.execute(insert_stmt, {
                "id": str(event_id),
                "event_type": event_type,
                "source": source,
                "payload": payload,
                "processed": False,
                "retry_count": 0,
                "max_retries": 3,
                "related_message_id": str(related_message_id) if related_message_id else None,
                "related_patient_id": str(related_patient_id) if related_patient_id else None,
                "event_hash": event_hash,
                "is_duplicate": False
            })
            
            self.db.commit()
            
            logger.info(
                f"Persisted webhook event",
                extra={
                    "event_id": str(event_id),
                    "event_type": event_type,
                    "source": source,
                    "event_hash": event_hash[:16]
                }
            )
            
            return event_id
            
        except IntegrityError as e:
            self.db.rollback()
            logger.warning(f"Duplicate webhook event (integrity error): {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to persist webhook event: {e}", exc_info=True)
            return None
    
    async def mark_processed(
        self,
        event_id: UUID,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        Mark webhook event as processed.
        
        Args:
            event_id: Webhook event ID
            success: Whether processing succeeded
            error_message: Optional error message if failed
        """
        try:
            update_stmt = text("""
                UPDATE webhook_events
                SET processed = :processed,
                    processed_at = NOW(),
                    error_message = :error_message
                WHERE id = :event_id
            """)
            
            self.db.execute(update_stmt, {
                "event_id": str(event_id),
                "processed": success,
                "error_message": error_message
            })
            self.db.commit()
            
            logger.debug(
                f"Marked webhook as processed",
                extra={"event_id": str(event_id), "success": success}
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark webhook as processed: {e}")
    
    async def get_failed_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get failed webhook events eligible for retry.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        try:
            select_stmt = text("""
                SELECT id, event_type, payload, retry_count, max_retries,
                       related_message_id, related_patient_id, created_at
                FROM webhook_events
                WHERE processed = false
                  AND retry_count < max_retries
                  AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                ORDER BY created_at ASC
                LIMIT :limit
            """)
            
            results = self.db.execute(select_stmt, {"limit": limit}).fetchall()
            
            events = []
            for row in results:
                events.append({
                    "id": UUID(row[0]) if row[0] else None,
                    "event_type": row[1],
                    "payload": row[2],
                    "retry_count": row[3],
                    "max_retries": row[4],
                    "related_message_id": UUID(row[5]) if row[5] else None,
                    "related_patient_id": UUID(row[6]) if row[6] else None,
                    "created_at": row[7]
                })
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get failed events: {e}", exc_info=True)
            return []
    
    async def increment_retry_count(
        self,
        event_id: UUID,
        next_retry_at: datetime,
        error_message: Optional[str] = None
    ) -> None:
        """
        Increment retry count and schedule next retry.
        
        Args:
            event_id: Webhook event ID
            next_retry_at: When to retry next
            error_message: Optional error message from failed retry
        """
        try:
            update_stmt = text("""
                UPDATE webhook_events
                SET retry_count = retry_count + 1,
                    next_retry_at = :next_retry_at,
                    error_message = :error_message
                WHERE id = :event_id
            """)
            
            self.db.execute(update_stmt, {
                "event_id": str(event_id),
                "next_retry_at": next_retry_at,
                "error_message": error_message or "Retry failed, will retry again"
            })
            self.db.commit()
            
            logger.debug(
                f"Incremented retry count for webhook",
                extra={"event_id": str(event_id), "next_retry_at": next_retry_at.isoformat()}
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to increment retry count: {e}")
    
    async def get_event_stats(self) -> Dict[str, int]:
        """
        Get statistics about webhook events.
        
        Returns:
            Dictionary with event counts
        """
        try:
            stats_stmt = text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE processed = true) as processed,
                    COUNT(*) FILTER (WHERE processed = false AND retry_count < max_retries) as pending_retry,
                    COUNT(*) FILTER (WHERE processed = false AND retry_count >= max_retries) as max_retries_exceeded
                FROM webhook_events
            """)
            
            result = self.db.execute(stats_stmt).fetchone()
            
            return {
                "total": result[0] or 0,
                "processed": result[1] or 0,
                "pending_retry": result[2] or 0,
                "max_retries_exceeded": result[3] or 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get event stats: {e}", exc_info=True)
            return {"total": 0, "processed": 0, "pending_retry": 0, "max_retries_exceeded": 0}
    
    async def cleanup_old_events(self, days: int = 7) -> int:
        """
        Clean up old processed webhook events.
        
        Args:
            days: Delete events older than this many days
            
        Returns:
            Number of deleted events
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            delete_stmt = text("""
                DELETE FROM webhook_events
                WHERE processed = true
                  AND processed_at < :cutoff_date
            """)
            
            result = self.db.execute(delete_stmt, {"cutoff_date": cutoff_date})
            self.db.commit()
            
            deleted_count = result.rowcount
            logger.info(
                f"Cleaned up old webhook events",
                extra={"deleted_count": deleted_count, "older_than_days": days}
            )
            
            return deleted_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to cleanup old events: {e}", exc_info=True)
            return 0
