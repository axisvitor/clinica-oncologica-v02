"""
Webhook Service
Business logic for webhook management, event processing, and delivery.

QW-006: Enhanced with atomic idempotency using Redis SET NX EX.
"""

import hmac
import hashlib
import time
import secrets
import json
import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.models.webhook import WebhookEndpoint, WebhookDelivery, WebhookLog
from app.models.webhook_event import WebhookEvent  # For idempotency
from app.schemas.v2.webhooks import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookList,
    WebhookDeliveryList,
    WebhookRetryResponse,
    WebhookSecretRotate,
    WebhookSecretResponse,
    WebhookLogList,
    WebhookStats,
    WebhookHealth,
    WebhookInboundEvent,
    WebhookInboundResponse,
    FailedWebhookList,
    FailedWebhook,
    WebhookStatus,
    WebhookTestRequest,
    WebhookTestResponse,
    WebhookDelivery as WebhookDeliverySchema,
    WebhookLog as WebhookLogSchema,
)
from app.config import settings
from app.services.webhook_processor import WebhookProcessor
from app.core.redis_unified import get_async_redis
from app.utils.logging import get_logger
from app.schemas.v2.common import CursorEncoder
from app.services.webhook.idempotency import AtomicWebhookIdempotency

logger = get_logger(__name__)

# Configuration
MAX_TIMESTAMP_AGE_SECONDS = 300
# WA-005 FIX: Reduced from 24h to 2h to prevent Redis memory growth
IDEMPOTENCY_WINDOW_HOURS = 2  # 2 hours is sufficient for retry windows
REDIS_TTL_WEBHOOK_CONFIG = 600
REDIS_TTL_WEBHOOK_STATS = 900
REDIS_TTL_IDEMPOTENCY = 86400
RETRY_BASE_DELAY = 2
RETRY_MAX_DELAY = 300


class WebhookService:
    """Service for webhook operations."""

    def __init__(self, db: Session):
        self.db = db
        self._idempotency_service: Optional[AtomicWebhookIdempotency] = None

    async def _get_redis(self):
        return await get_async_redis()

    async def _get_idempotency_service(self) -> Optional[AtomicWebhookIdempotency]:
        """Get or create atomic idempotency service."""
        if self._idempotency_service is None:
            redis = await self._get_redis()
            if redis:
                self._idempotency_service = AtomicWebhookIdempotency(redis, self.db)
        return self._idempotency_service

    def _generate_webhook_secret(self) -> str:
        return f"wh_secret_{secrets.token_urlsafe(32)}"

    def _compute_webhook_signature(
        self, payload: bytes, secret: str, timestamp: str = None
    ) -> str:
        if timestamp:
            signature_payload = f"{timestamp}.{payload.decode('utf-8')}"
            signature_bytes = signature_payload.encode("utf-8")
        else:
            signature_bytes = payload

        return hmac.new(
            secret.encode("utf-8"),
            signature_bytes,
            hashlib.sha256,
        ).hexdigest()

    async def verify_webhook_signature(
        self, payload: bytes, signature: str, timestamp: str, webhook_id: str
    ) -> Dict[str, Any]:
        if not settings.WHATSAPP_EVOLUTION_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=401, detail="Webhook authentication not configured"
            )

        if timestamp:
            try:
                webhook_time = int(timestamp)
                current_time = int(time.time())
                if abs(current_time - webhook_time) > MAX_TIMESTAMP_AGE_SECONDS:
                    raise HTTPException(
                        status_code=401, detail="Webhook timestamp expired"
                    )
            except ValueError:
                raise HTTPException(status_code=401, detail="Invalid webhook timestamp")

        expected_signature = self._compute_webhook_signature(
            payload, settings.WHATSAPP_EVOLUTION_WEBHOOK_SECRET, timestamp
        )
        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        return {"verified": True, "webhook_id": webhook_id, "timestamp": timestamp}

    async def check_idempotency(
        self, webhook_id: Optional[str], event_type: str
    ) -> bool:
        """
        Check if event was already processed using atomic idempotency.

        QW-006 FIX: Uses atomic SET NX EX to prevent race conditions.
        WA-006 FIX: DB fallback ensures idempotency even if Redis is unavailable.

        Returns:
            True if event should be processed (new event)
            False if event was already processed (duplicate)
        """
        if not webhook_id:
            return True

        # QW-006: Try atomic idempotency service first
        idempotency = await self._get_idempotency_service()
        if idempotency:
            try:
                acquired, reason = await idempotency.try_acquire(
                    event_type=event_type, event_id=webhook_id
                )

                if not acquired:
                    logger.debug(
                        f"Idempotency check (atomic): event {webhook_id} already processed",
                        extra={"reason": reason},
                    )
                    return False

                # Successfully acquired - this is a new event
                return True

            except Exception as e:
                logger.warning(
                    f"Atomic idempotency check failed, falling back to legacy: {e}"
                )

        # Legacy fallback: Try simple SET NX
        redis = await self._get_redis()
        if redis:
            try:
                cache_key = f"webhook:idempotency:{webhook_id}"
                # Use atomic SET NX EX even in fallback
                result = await redis.set(
                    cache_key, "1", nx=True, ex=REDIS_TTL_IDEMPOTENCY
                )
                if not result:
                    logger.debug(
                        f"Idempotency check (Redis fallback): event {webhook_id} already processed"
                    )
                    return False
                return True
            except Exception as e:
                logger.warning(
                    f"Redis idempotency check failed, falling back to DB: {e}"
                )

        # WA-006: DB fallback for reliability
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=IDEMPOTENCY_WINDOW_HOURS)
            existing = self.db.execute(
                select(WebhookEvent).where(
                    WebhookEvent.event_id == webhook_id,
                    WebhookEvent.created_at >= cutoff_time,
                )
            ).first()

            if existing:
                logger.debug(
                    f"Idempotency check (DB): event {webhook_id} already processed"
                )
                return False
        except Exception as e:
            logger.error(f"DB idempotency check failed: {e}")
            # Fail open: allow event if both Redis and DB fail
            return True

        return True

    async def list_webhooks(
        self, pagination: dict, status_filter: Optional[WebhookStatus]
    ) -> WebhookList:
        redis = await self._get_redis()
        cache_key = f"webhooks:list:{pagination.get('limit')}:{status_filter or 'all'}"
        if pagination.get("cursor_data"):
            cache_key += f":{pagination['cursor_data'].get('id', 0)}"

        if redis:
            cached = await redis.get(cache_key)
            if cached:
                return WebhookList(**json.loads(cached))

        query = select(WebhookEndpoint)
        if status_filter:
            query = query.where(WebhookEndpoint.status == status_filter.value)
        if pagination.get("cursor_data"):
            query = query.where(
                WebhookEndpoint.id > pagination["cursor_data"].get("id")
            )

        query = query.order_by(WebhookEndpoint.id).limit(pagination["limit"] + 1)
        results = self.db.execute(query).scalars().all()

        has_more = len(results) > pagination["limit"]
        webhooks = results[: pagination["limit"]]

        webhook_responses = [
            WebhookResponse(
                id=wh.id,
                url=wh.url,
                events=wh.events,
                description=wh.description,
                status=wh.status,
                secret_preview=(wh.secret or "")[:8] if wh.secret else "N/A",
                headers=wh.headers or {},
                timeout=wh.timeout,
                retry_enabled=wh.retry_enabled,
                max_retries=wh.max_retries,
                created_at=wh.created_at,
                updated_at=wh.updated_at,
                last_triggered_at=wh.last_triggered_at,
                success_count=wh.success_count,
                failure_count=wh.failure_count,
            )
            for wh in webhooks
        ]

        next_cursor = (
            CursorEncoder.encode(webhooks[-1].id, webhooks[-1].created_at)
            if has_more and webhooks
            else None
        )
        response = WebhookList(
            data=webhook_responses,
            next_cursor=next_cursor,
            has_more=has_more,
            total=None,
        )

        if redis:
            await redis.set(
                cache_key,
                json.dumps(response.dict(), default=str),
                expire=REDIS_TTL_WEBHOOK_CONFIG,
            )
        return response

    async def create_webhook(self, webhook_data: WebhookCreate) -> WebhookResponse:
        secret = webhook_data.secret or self._generate_webhook_secret()
        webhook = WebhookEndpoint(
            id=uuid4(),
            url=str(webhook_data.url),
            events=webhook_data.events,
            description=webhook_data.description,
            secret=secret,
            headers=webhook_data.headers or {},
            timeout=webhook_data.timeout,
            retry_enabled=webhook_data.retry_enabled,
            max_retries=webhook_data.max_retries,
            status="active",
        )

        self.db.add(webhook)
        self._log_activity(
            webhook.id, "created", "Webhook created", {"url": webhook.url}
        )
        self.db.commit()
        self.db.refresh(webhook)

        redis = await self._get_redis()
        if redis:
            await redis.delete_pattern("webhooks:list:*")

        return self._to_response(webhook)

    async def get_webhook(self, webhook_id: UUID) -> WebhookResponse:
        webhook = self._get_webhook_or_404(webhook_id)
        return self._to_response(webhook)

    async def update_webhook(
        self, webhook_id: UUID, webhook_data: WebhookUpdate
    ) -> WebhookResponse:
        webhook = self._get_webhook_or_404(webhook_id)

        if webhook_data.url is not None:
            webhook.url = str(webhook_data.url)
        if webhook_data.events is not None:
            webhook.events = webhook_data.events
        if webhook_data.description is not None:
            webhook.description = webhook_data.description
        if webhook_data.status is not None:
            webhook.status = webhook_data.status.value
        if webhook_data.headers is not None:
            webhook.headers = webhook_data.headers
        if webhook_data.timeout is not None:
            webhook.timeout = webhook_data.timeout
        if webhook_data.retry_enabled is not None:
            webhook.retry_enabled = webhook_data.retry_enabled
        if webhook_data.max_retries is not None:
            webhook.max_retries = webhook_data.max_retries

        self._log_activity(
            webhook.id,
            "updated",
            "Webhook updated",
            webhook_data.dict(exclude_unset=True),
        )
        self.db.commit()
        self.db.refresh(webhook)

        redis = await self._get_redis()
        if redis:
            await redis.delete(f"webhook:{webhook_id}")
            await redis.delete_pattern("webhooks:list:*")

        return self._to_response(webhook)

    async def delete_webhook(self, webhook_id: UUID) -> None:
        webhook = self._get_webhook_or_404(webhook_id)

        self.db.delete(webhook)
        self.db.commit()

        redis = await self._get_redis()
        if redis:
            await redis.delete(f"webhook:{webhook_id}")
            await redis.delete_pattern("webhooks:list:*")

    async def process_inbound_webhook(
        self, event_data: WebhookInboundEvent, verification: dict
    ) -> WebhookInboundResponse:
        # This handles INBOUND webhooks from Evolution API (WhatsApp)
        webhook_id = verification.get("webhook_id")
        event_type = event_data.event

        if not await self.check_idempotency(webhook_id, event_type):
            return WebhookInboundResponse(
                status="duplicate",
                message="Webhook already processed",
                webhook_id=webhook_id,
                message_id=None,
            )

        processor = WebhookProcessor(self.db)

        if "message" in event_type:
            msg_id = await processor.process_message_webhook(
                event_data.data, webhook_id=webhook_id
            )
            return WebhookInboundResponse(
                status="success" if msg_id else "ignored",
                message="Message processed" if msg_id else "Message ignored",
                webhook_id=webhook_id,
                message_id=msg_id,
            )
        elif "connection" in event_type:
            success = await processor.process_connection_webhook(
                event_data.data, webhook_id=webhook_id
            )
            return WebhookInboundResponse(
                status="success" if success else "error",
                message="Connection processed" if success else "Failed",
                webhook_id=webhook_id,
                message_id=None,
            )

        return WebhookInboundResponse(
            status="success",
            message="Event processed",
            webhook_id=webhook_id,
            message_id=None,
        )

    async def rotate_webhook_secret(
        self, webhook_id: UUID, secret_data: WebhookSecretRotate
    ) -> WebhookSecretResponse:
        webhook = self._get_webhook_or_404(webhook_id)

        new_secret = secret_data.new_secret or self._generate_webhook_secret()
        webhook.secret = new_secret

        self._log_activity(webhook.id, "secret_rotated", "Secret rotated")
        self.db.commit()

        redis = await self._get_redis()
        if redis:
            await redis.delete(f"webhook:{webhook_id}")

        return WebhookSecretResponse(
            secret_preview=new_secret[:8],
            rotated_at=webhook.updated_at,
            message="Secret rotated successfully",
        )

    async def get_webhook_stats(self) -> WebhookStats:
        total = self.db.query(func.count(WebhookEndpoint.id)).scalar() or 0
        active = (
            self.db.query(func.count(WebhookEndpoint.id))
            .filter(WebhookEndpoint.status == "active")
            .scalar()
            or 0
        )

        total_del = self.db.query(func.count(WebhookDelivery.id)).scalar() or 0
        success_del = (
            self.db.query(func.count(WebhookDelivery.id))
            .filter(WebhookDelivery.status == "success")
            .scalar()
            or 0
        )
        failed_del = (
            self.db.query(func.count(WebhookDelivery.id))
            .filter(WebhookDelivery.status == "failed")
            .scalar()
            or 0
        )
        pending_del = (
            self.db.query(func.count(WebhookDelivery.id))
            .filter(WebhookDelivery.status == "pending")
            .scalar()
            or 0
        )

        success_rate = (success_del / total_del * 100) if total_del > 0 else 0.0

        last_24h = (
            self.db.query(func.count(WebhookDelivery.id))
            .filter(
                WebhookDelivery.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)
            )
            .scalar()
            or 0
        )

        avg_time = (
            self.db.query(func.avg(WebhookDelivery.response_time_ms))
            .filter(WebhookDelivery.response_time_ms.isnot(None))
            .scalar()
            or 0.0
        )

        return WebhookStats(
            total_webhooks=total,
            active_webhooks=active,
            total_deliveries=total_del,
            successful_deliveries=success_del,
            failed_deliveries=failed_del,
            pending_deliveries=pending_del,
            average_response_time_ms=float(avg_time),
            success_rate=float(success_rate),
            last_24h_deliveries=last_24h,
        )

    async def get_webhook_health(self, webhook_id: UUID) -> WebhookHealth:
        webhook = self._get_webhook_or_404(webhook_id)

        # Calculate uptime based on success rate in last 24h
        last_24h_total = (
            self.db.query(func.count(WebhookDelivery.id))
            .filter(
                WebhookDelivery.webhook_id == webhook_id,
                WebhookDelivery.created_at >= datetime.now(timezone.utc) - timedelta(hours=24),
            )
            .scalar()
            or 0
        )

        last_24h_success = (
            self.db.query(func.count(WebhookDelivery.id))
            .filter(
                WebhookDelivery.webhook_id == webhook_id,
                WebhookDelivery.status == "success",
                WebhookDelivery.created_at >= datetime.now(timezone.utc) - timedelta(hours=24),
            )
            .scalar()
            or 0
        )

        uptime = (
            (last_24h_success / last_24h_total * 100) if last_24h_total > 0 else 100.0
        )

        recent_failures = (
            self.db.query(func.count(WebhookDelivery.id))
            .filter(
                WebhookDelivery.webhook_id == webhook_id,
                WebhookDelivery.status == "failed",
                WebhookDelivery.created_at >= datetime.now(timezone.utc) - timedelta(hours=1),
            )
            .scalar()
            or 0
        )

        avg_time = (
            self.db.query(func.avg(WebhookDelivery.response_time_ms))
            .filter(WebhookDelivery.webhook_id == webhook_id)
            .scalar()
            or 0.0
        )

        last_success = (
            self.db.query(WebhookDelivery.created_at)
            .filter(
                WebhookDelivery.webhook_id == webhook_id,
                WebhookDelivery.status == "success",
            )
            .order_by(desc(WebhookDelivery.created_at))
            .first()
        )

        last_failure = (
            self.db.query(WebhookDelivery.created_at)
            .filter(
                WebhookDelivery.webhook_id == webhook_id,
                WebhookDelivery.status == "failed",
            )
            .order_by(desc(WebhookDelivery.created_at))
            .first()
        )

        recommendations = []
        if uptime < 95:
            recommendations.append("Check endpoint availability")
        if recent_failures > 5:
            recommendations.append("High failure rate detected")
        if avg_time > 1000:
            recommendations.append("High latency detected")

        return WebhookHealth(
            webhook_id=webhook_id,
            status=webhook.status,
            uptime_percentage=float(uptime),
            recent_failures=recent_failures,
            average_response_time_ms=float(avg_time),
            last_success_at=last_success[0] if last_success else None,
            last_failure_at=last_failure[0] if last_failure else None,
            recommendations=recommendations,
        )

    async def get_failed_webhooks(self) -> FailedWebhookList:
        failed = (
            self.db.query(WebhookEndpoint)
            .filter(WebhookEndpoint.status == "error")
            .all()
        )
        failed_list = []
        for wh in failed:
            last_failure = (
                self.db.query(WebhookDelivery)
                .filter(
                    WebhookDelivery.webhook_id == wh.id,
                    WebhookDelivery.status == "failed",
                )
                .order_by(desc(WebhookDelivery.created_at))
                .first()
            )

            failed_list.append(
                FailedWebhook(
                    webhook_id=wh.id,
                    url=wh.url,
                    description=wh.description,
                    consecutive_failures=wh.failure_count,
                    last_failure_at=last_failure.created_at
                    if last_failure
                    else wh.updated_at,
                    last_error=last_failure.error if last_failure else "Unknown",
                    status=wh.status,
                )
            )

        return FailedWebhookList(data=failed_list, total=len(failed_list))

    # --- New Methods for Full Functionality ---

    async def get_webhook_deliveries(
        self, webhook_id: UUID, pagination: dict
    ) -> WebhookDeliveryList:
        query = select(WebhookDelivery).where(WebhookDelivery.webhook_id == webhook_id)
        if pagination.get("cursor_data"):
            query = query.where(
                WebhookDelivery.created_at < pagination["cursor_data"].get("created_at")
            )

        query = query.order_by(desc(WebhookDelivery.created_at)).limit(
            pagination["limit"] + 1
        )
        results = self.db.execute(query).scalars().all()

        has_more = len(results) > pagination["limit"]
        deliveries = results[: pagination["limit"]]

        data = [WebhookDeliverySchema.from_orm(d) for d in deliveries]
        next_cursor = (
            CursorEncoder.encode(str(deliveries[-1].id), deliveries[-1].created_at)
            if has_more and deliveries
            else None
        )

        return WebhookDeliveryList(
            data=data, next_cursor=next_cursor, has_more=has_more, total=None
        )

    async def get_webhook_logs(
        self, webhook_id: UUID, pagination: dict
    ) -> WebhookLogList:
        query = select(WebhookLog).where(WebhookLog.webhook_id == webhook_id)
        if pagination.get("cursor_data"):
            query = query.where(
                WebhookLog.created_at < pagination["cursor_data"].get("created_at")
            )

        query = query.order_by(desc(WebhookLog.created_at)).limit(
            pagination["limit"] + 1
        )
        results = self.db.execute(query).scalars().all()

        has_more = len(results) > pagination["limit"]
        logs = results[: pagination["limit"]]

        data = [WebhookLogSchema.from_orm(log) for log in logs]
        next_cursor = (
            CursorEncoder.encode(str(logs[-1].id), logs[-1].created_at)
            if has_more and logs
            else None
        )

        return WebhookLogList(
            data=data, next_cursor=next_cursor, has_more=has_more, total=None
        )

    async def retry_webhook_delivery(
        self, webhook_id: UUID, delivery_id: UUID, force: bool = False
    ) -> WebhookRetryResponse:
        original = (
            self.db.query(WebhookDelivery)
            .filter(WebhookDelivery.id == delivery_id)
            .first()
        )
        if not original:
            raise HTTPException(status_code=404, detail="Delivery not found")

        webhook = self._get_webhook_or_404(webhook_id)

        if not force and original.attempt >= webhook.max_retries:
            raise HTTPException(status_code=400, detail="Max retries reached")

        # Create new delivery attempt
        new_delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=webhook_id,
            event_type=original.event_type,
            payload=original.payload,
            status="pending",
            attempt=original.attempt + 1,
        )
        self.db.add(new_delivery)
        self.db.commit()

        # Trigger async delivery (mocked here, ideally use BackgroundTasks or Celery)
        # In a real scenario, this would push to a queue
        await self._execute_delivery(new_delivery, webhook)

        return WebhookRetryResponse(
            success=True,
            delivery_id=new_delivery.id,
            attempt=new_delivery.attempt,
            message="Retry initiated",
        )

    async def test_webhook(
        self, webhook_id: UUID, test_data: WebhookTestRequest
    ) -> WebhookTestResponse:
        webhook = self._get_webhook_or_404(webhook_id)

        delivery = WebhookDelivery(
            id=uuid4(),
            webhook_id=webhook_id,
            event_type=test_data.event_type,
            payload=test_data.payload,
            status="pending",
            attempt=1,
        )
        self.db.add(delivery)
        self.db.commit()

        success = await self._execute_delivery(delivery, webhook)

        return WebhookTestResponse(
            success=success,
            status_code=delivery.status_code,
            response_time_ms=delivery.response_time_ms or 0,
            response_body=delivery.response_body,
            error=delivery.error,
        )

    # --- Helpers ---

    def _get_webhook_or_404(self, webhook_id: UUID) -> WebhookEndpoint:
        webhook = (
            self.db.query(WebhookEndpoint)
            .filter(WebhookEndpoint.id == webhook_id)
            .first()
        )
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return webhook

    def _to_response(self, wh: WebhookEndpoint) -> WebhookResponse:
        return WebhookResponse(
            id=wh.id,
            url=wh.url,
            events=wh.events,
            description=wh.description,
            status=wh.status,
            secret_preview=(wh.secret or "")[:8] if wh.secret else "N/A",
            headers=wh.headers or {},
            timeout=wh.timeout,
            retry_enabled=wh.retry_enabled,
            max_retries=wh.max_retries,
            created_at=wh.created_at,
            updated_at=wh.updated_at,
            last_triggered_at=wh.last_triggered_at,
            success_count=wh.success_count,
            failure_count=wh.failure_count,
        )

    def _log_activity(
        self, webhook_id: UUID, action: str, event_type: str, details: dict = None
    ):
        log = WebhookLog(
            id=uuid4(),
            webhook_id=webhook_id,
            action=action,
            event_type=event_type,
            details=details,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(log)

    async def _execute_delivery(
        self, delivery: WebhookDelivery, webhook: WebhookEndpoint
    ) -> bool:
        """Execute the HTTP request for the webhook delivery."""
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=webhook.timeout) as client:
                # Compute signature if secret exists
                headers = webhook.headers.copy() if webhook.headers else {}
                if webhook.secret:
                    payload_bytes = json.dumps(delivery.payload).encode("utf-8")
                    signature = self._compute_webhook_signature(
                        payload_bytes, webhook.secret
                    )
                    headers["X-Webhook-Signature"] = signature

                response = await client.post(
                    webhook.url, json=delivery.payload, headers=headers
                )

                delivery.status_code = response.status_code
                delivery.response_body = response.text[:1000]  # Truncate
                delivery.response_time_ms = (time.time() - start_time) * 1000

                if response.is_success:
                    delivery.status = "success"
                    webhook.success_count += 1
                    webhook.last_triggered_at = datetime.now(timezone.utc)
                else:
                    delivery.status = "failed"
                    delivery.error = f"HTTP {response.status_code}"
                    webhook.failure_count += 1

        except Exception as e:
            delivery.status = "failed"
            delivery.error = str(e)
            delivery.response_time_ms = (time.time() - start_time) * 1000
            webhook.failure_count += 1

        delivery.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        return delivery.status == "success"
