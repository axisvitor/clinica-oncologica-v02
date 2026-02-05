"""
Idempotency Middleware for Webhook Processing

Prevents duplicate processing of webhook events by tracking event IDs
and enforcing idempotent behavior within a 24-hour window.
"""

import logging
import hashlib
import json
from typing import Callable
from datetime import datetime, timezone
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.webhook_event import WebhookEvent
from app.database import get_db

logger = logging.getLogger(__name__)


class IdempotencyMiddleware:
    """
    Middleware to ensure idempotent webhook processing.

    Tracks webhook events by ID and prevents duplicate processing within
    the idempotency window (24 hours by default).
    """

    def __init__(
        self, app, ttl_hours: int = 24, enabled_paths: list[str] | None = None
    ):
        """
        Initialize idempotency middleware.

        Args:
            app: FastAPI application
            ttl_hours: Time-to-live for idempotency records in hours
            enabled_paths: List of URL paths where idempotency is enforced
                          (None = all paths)
        """
        self.app = app
        self.ttl_hours = ttl_hours
        self.enabled_paths = enabled_paths or [
            "/api/v2/webhooks/whatsapp",
            "/api/v2/webhooks/twilio",
            "/webhooks/",
        ]

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with idempotency checking.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response from handler or cached response for duplicates
        """
        # Check if idempotency should be enforced for this path
        if not self._should_check_idempotency(request):
            return await call_next(request)

        # Extract event ID from request
        event_id = await self._extract_event_id(request)
        if not event_id:
            # No event ID found, process normally
            logger.warning(
                "No event ID found for idempotent webhook",
                extra={"path": request.url.path},
            )
            return await call_next(request)

        # Determine provider and event type
        provider = self._extract_provider(request)
        event_type = self._extract_event_type(request)

        # Check idempotency
        db: Session = next(get_db())
        try:
            webhook_event = await self._check_idempotency(
                db=db,
                event_id=event_id,
                provider=provider,
                event_type=event_type,
                request=request,
            )

            if webhook_event.status == "completed":
                # Event already processed, return cached response
                logger.info(
                    "Duplicate webhook detected, returning cached response",
                    extra={
                        "event_id": event_id,
                        "provider": provider,
                        "retry_count": webhook_event.retry_count,
                    },
                )
                webhook_event.increment_retry()
                db.commit()

                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "status": "duplicate",
                        "message": "Event already processed",
                        "event_id": event_id,
                        "processed_at": webhook_event.processed_at.isoformat(),
                        "response": webhook_event.response_data,
                    },
                    headers={
                        "X-Idempotency-Status": "duplicate",
                        "X-Event-ID": event_id,
                        "X-Retry-Count": str(webhook_event.retry_count),
                    },
                )

            # Process the webhook
            try:
                response = await call_next(request)

                # Mark as completed
                webhook_event.mark_completed(
                    {
                        "status_code": response.status_code,
                        "processed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                db.commit()

                # Add idempotency headers
                response.headers["X-Idempotency-Status"] = "processed"
                response.headers["X-Event-ID"] = event_id

                return response

            except Exception as e:
                # Mark as failed
                webhook_event.mark_failed(
                    {"error": str(e), "error_type": type(e).__name__}
                )
                db.commit()
                raise

        finally:
            db.close()

    def _should_check_idempotency(self, request: Request) -> bool:
        """Check if idempotency should be enforced for this request."""
        # Only check POST requests (webhooks)
        if request.method != "POST":
            return False

        # Check if path matches enabled paths
        path = request.url.path
        return any(enabled_path in path for enabled_path in self.enabled_paths)

    async def _extract_event_id(self, request: Request) -> str | None:
        """
        Extract event ID from webhook request.

        Tries multiple strategies:
        1. X-Event-ID header
        2. X-Webhook-ID header
        3. event_id in JSON body
        4. id in JSON body
        5. Generate from payload hash (last resort)
        """
        # Check headers
        event_id = request.headers.get("X-Event-ID")
        if event_id:
            return event_id

        event_id = request.headers.get("X-Webhook-ID")
        if event_id:
            return event_id

        # Check body
        try:
            body = await request.body()
            if body:
                payload = json.loads(body)

                # Try common event ID fields
                event_id = payload.get("event_id") or payload.get("id")
                if event_id:
                    return str(event_id)

                # WhatsApp specific
                if "entry" in payload:
                    entries = payload.get("entry", [])
                    if entries and len(entries) > 0:
                        entry = entries[0]
                        changes = entry.get("changes", [])
                        if changes and len(changes) > 0:
                            change = changes[0]
                            value = change.get("value", {})
                            messages = value.get("messages", [])
                            if messages and len(messages) > 0:
                                return messages[0].get("id")

                # Generate hash from payload as last resort
                payload_str = json.dumps(payload, sort_keys=True)
                return hashlib.sha256(payload_str.encode()).hexdigest()[:32]

        except Exception as e:
            logger.error(f"Error extracting event ID: {e}")

        return None

    def _extract_provider(self, request: Request) -> str:
        """Extract provider name from request path."""
        path = request.url.path.lower()

        if "whatsapp" in path:
            return "whatsapp"
        elif "twilio" in path:
            return "twilio"
        elif "webhook" in path:
            return "generic"

        return "unknown"

    def _extract_event_type(self, request: Request) -> str:
        """Extract event type from request."""
        # Could be enhanced to parse from webhook payload
        return "webhook.received"

    async def _check_idempotency(
        self,
        db: Session,
        event_id: str,
        provider: str,
        event_type: str,
        request: Request,
    ) -> WebhookEvent:
        """
        Check if event has been processed before.

        Returns:
            WebhookEvent instance (existing or new)
        """
        # Check for existing event
        existing_event = (
            db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
        )

        if existing_event:
            # Check if expired
            if existing_event.is_expired():
                logger.info(
                    "Expired idempotency record found, allowing reprocessing",
                    extra={"event_id": event_id},
                )
                # Delete expired record and create new one
                db.delete(existing_event)
                db.commit()
            else:
                return existing_event

        # Create new event record
        try:
            body = await request.body()
            payload = json.loads(body) if body else None
        except Exception:
            payload = None

        new_event = WebhookEvent.create_event(
            event_id=event_id,
            provider=provider,
            event_type=event_type,
            payload=payload,
            ttl_hours=self.ttl_hours,
        )

        try:
            db.add(new_event)
            db.commit()
            db.refresh(new_event)
            return new_event

        except IntegrityError:
            # Race condition - another request created the record
            db.rollback()
            existing_event = (
                db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
            )
            if existing_event:
                return existing_event
            raise


async def cleanup_expired_events(db: Session, batch_size: int = 1000) -> int:
    """
    Cleanup expired idempotency records.

    Args:
        db: Database session
        batch_size: Number of records to delete per batch

    Returns:
        Number of records deleted
    """
    deleted_count = 0

    try:
        while True:
            # Find expired events
            expired_events = (
                db.query(WebhookEvent)
                .filter(WebhookEvent.expires_at < datetime.now(timezone.utc))
                .limit(batch_size)
                .all()
            )

            if not expired_events:
                break

            # Delete batch
            for event in expired_events:
                db.delete(event)

            db.commit()
            deleted_count += len(expired_events)

            logger.info(
                f"Deleted {len(expired_events)} expired idempotency records",
                extra={"batch_size": batch_size, "total_deleted": deleted_count},
            )

        return deleted_count

    except Exception as e:
        logger.error(f"Error cleaning up expired events: {e}")
        db.rollback()
        raise
