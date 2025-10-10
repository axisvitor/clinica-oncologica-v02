"""
Idempotency Cleanup Service

Background job to clean up expired webhook idempotency records.
Runs periodically to prevent unbounded table growth.
"""

import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.webhook_event import WebhookEvent
from app.middleware.idempotency import cleanup_expired_events

logger = logging.getLogger(__name__)


class IdempotencyCleanupService:
    """Service for cleaning up expired idempotency records."""

    def __init__(self, batch_size: int = 1000):
        """
        Initialize cleanup service.

        Args:
            batch_size: Number of records to delete per batch
        """
        self.batch_size = batch_size

    async def run_cleanup(self, db: Session) -> Dict[str, Any]:
        """
        Run cleanup job to remove expired records.

        Args:
            db: Database session

        Returns:
            Dictionary with cleanup statistics
        """
        start_time = datetime.utcnow()

        try:
            # Get statistics before cleanup
            total_events = db.query(func.count(WebhookEvent.event_id)).scalar()
            expired_count = db.query(func.count(WebhookEvent.event_id)).filter(
                WebhookEvent.expires_at < datetime.utcnow()
            ).scalar()

            logger.info(
                "Starting idempotency cleanup",
                extra={
                    "total_events": total_events,
                    "expired_events": expired_count,
                    "batch_size": self.batch_size
                }
            )

            # Run cleanup
            deleted_count = await cleanup_expired_events(
                db=db,
                batch_size=self.batch_size
            )

            # Get statistics after cleanup
            remaining_events = db.query(func.count(WebhookEvent.event_id)).scalar()

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            result = {
                "status": "success",
                "deleted_count": deleted_count,
                "before_count": total_events,
                "after_count": remaining_events,
                "execution_time_seconds": execution_time,
                "timestamp": start_time.isoformat()
            }

            logger.info(
                "Idempotency cleanup completed",
                extra=result
            )

            return result

        except Exception as e:
            logger.error(
                "Idempotency cleanup failed",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise

    async def get_cleanup_stats(self, db: Session) -> Dict[str, Any]:
        """
        Get current idempotency statistics.

        Args:
            db: Database session

        Returns:
            Dictionary with current statistics
        """
        try:
            total_events = db.query(func.count(WebhookEvent.event_id)).scalar()

            expired_events = db.query(func.count(WebhookEvent.event_id)).filter(
                WebhookEvent.expires_at < datetime.utcnow()
            ).scalar()

            active_events = db.query(func.count(WebhookEvent.event_id)).filter(
                WebhookEvent.expires_at >= datetime.utcnow()
            ).scalar()

            # Get events by status
            processing_events = db.query(func.count(WebhookEvent.event_id)).filter(
                WebhookEvent.status == "processing"
            ).scalar()

            completed_events = db.query(func.count(WebhookEvent.event_id)).filter(
                WebhookEvent.status == "completed"
            ).scalar()

            failed_events = db.query(func.count(WebhookEvent.event_id)).filter(
                WebhookEvent.status == "failed"
            ).scalar()

            # Get events with retries (duplicates detected)
            duplicate_events = db.query(func.count(WebhookEvent.event_id)).filter(
                WebhookEvent.retry_count > 0
            ).scalar()

            total_retries = db.query(func.sum(WebhookEvent.retry_count)).scalar() or 0

            # Get events by provider
            provider_stats = db.query(
                WebhookEvent.provider,
                func.count(WebhookEvent.event_id).label('count')
            ).group_by(WebhookEvent.provider).all()

            return {
                "total_events": total_events,
                "active_events": active_events,
                "expired_events": expired_events,
                "processing_events": processing_events,
                "completed_events": completed_events,
                "failed_events": failed_events,
                "duplicate_events": duplicate_events,
                "total_retries": total_retries,
                "provider_breakdown": {
                    provider: count for provider, count in provider_stats
                },
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(
                "Error getting cleanup stats",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise


# Singleton instance
_cleanup_service: IdempotencyCleanupService | None = None


def get_cleanup_service() -> IdempotencyCleanupService:
    """Get or create cleanup service singleton."""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = IdempotencyCleanupService()
    return _cleanup_service
