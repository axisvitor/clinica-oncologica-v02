"""
V2 Webhooks API
Enhanced webhook management with modern patterns.
Delegates logic to WebhookService.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Request, Depends, status, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.utils.rate_limiter import limiter, multi_layer_rate_limit
from app.core.redis_manager import get_async_redis_client
from app.services.webhook.idempotency import AtomicWebhookIdempotency
from app.schemas.v2.webhooks import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookList,
    WebhookTestRequest,
    WebhookTestResponse,
    WebhookDeliveryList,
    WebhookRetryRequest,
    WebhookRetryResponse,
    WebhookSecretRotate,
    WebhookSecretResponse,
    WebhookLogList,
    WebhookStats,
    WebhookHealth,
    WebhookInboundEvent,
    WebhookInboundResponse,
    WebhookEventTypeList,
    FailedWebhookList,
    WebhookStatus,
    WebhookEventTypeInfo,
    WebhookEventType,
)
from app.api.v2.dependencies import get_pagination_params_async
from app.services.webhook_service import WebhookService
from app.dependencies.auth_dependencies import get_current_active_admin

logger = logging.getLogger(__name__)
router = APIRouter()

RATE_LIMIT_WEBHOOKS_PER_HOUR = 10


async def get_webhook_service(
    db: AsyncSession = Depends(get_async_db),
) -> WebhookService:
    return WebhookService(db)


async def verify_webhook_signature_v2(
    request: Request,
    x_webhook_signature: str = Header(..., alias="X-Webhook-Signature"),
    x_webhook_timestamp: Optional[str] = Header(None, alias="X-Webhook-Timestamp"),
    x_webhook_id: Optional[str] = Header(None, alias="X-Webhook-Id"),
    service: WebhookService = Depends(get_webhook_service),
):
    payload = await request.body()
    return await service.verify_webhook_signature(
        payload, x_webhook_signature, x_webhook_timestamp, x_webhook_id
    )


@router.get("", response_model=WebhookList)
@limiter.limit("100/minute")
async def list_webhooks(
    request: Request,
    pagination: dict = Depends(get_pagination_params_async),
    status_filter: Optional[WebhookStatus] = None,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.list_webhooks(pagination, status_filter)


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{RATE_LIMIT_WEBHOOKS_PER_HOUR}/hour")
async def create_webhook(
    request: Request,
    webhook_data: WebhookCreate,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.create_webhook(webhook_data)


@router.get("/{webhook_id:uuid}", response_model=WebhookResponse)
@limiter.limit("100/minute")
async def get_webhook(
    request: Request,
    webhook_id: UUID,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.get_webhook(webhook_id)


@router.put("/{webhook_id:uuid}", response_model=WebhookResponse)
@limiter.limit("60/minute")
async def update_webhook(
    request: Request,
    webhook_id: UUID,
    webhook_data: WebhookUpdate,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.update_webhook(webhook_id, webhook_data)


@router.delete("/{webhook_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_webhook(
    request: Request,
    webhook_id: UUID,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.delete_webhook(webhook_id)


@router.post("/inbound", response_model=WebhookInboundResponse)
@multi_layer_rate_limit(
    global_limit=1000,
    global_window=60,
    identifier_limit=100,
    identifier_window=60,
    identifier_key="data.key.remoteJid",
)
async def receive_inbound_webhook(
    request: Request,
    event_data: WebhookInboundEvent,
    verification: dict = Depends(verify_webhook_signature_v2),
    service: WebhookService = Depends(get_webhook_service),
):
    return await service.process_inbound_webhook(event_data, verification)


@router.post("/whatsapp", response_model=WebhookInboundResponse)
@multi_layer_rate_limit(
    global_limit=1000,
    global_window=60,
    identifier_limit=100,
    identifier_window=60,
    identifier_key="data.key.remoteJid",
)
async def receive_whatsapp_webhook(
    request: Request,
    event_data: WebhookInboundEvent,
    verification: dict = Depends(verify_webhook_signature_v2),
    service: WebhookService = Depends(get_webhook_service),
):
    return await service.process_inbound_webhook(event_data, verification)


@router.get("/events", response_model=WebhookEventTypeList)
@limiter.limit("100/minute")
async def get_event_types(
    request: Request, current_user=Depends(get_current_active_admin)
):
    # Static data, no service needed
    event_types = [
        WebhookEventTypeInfo(
            event=WebhookEventType.MESSAGE_RECEIVED.value,
            description="New message received",
            payload_schema={"message_id": "string"},
        ),
        WebhookEventTypeInfo(
            event=WebhookEventType.MESSAGE_SENT.value,
            description="Message sent",
            payload_schema={"message_id": "string"},
        ),
        # Add other events as needed...
    ]
    return WebhookEventTypeList(events=event_types, total=len(event_types))


@router.put("/{webhook_id:uuid}/secret", response_model=WebhookSecretResponse)
@limiter.limit("5/hour")
async def rotate_webhook_secret(
    request: Request,
    webhook_id: UUID,
    secret_data: WebhookSecretRotate,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.rotate_webhook_secret(webhook_id, secret_data)


@router.get("/stats", response_model=WebhookStats)
@limiter.limit("100/minute")
async def get_webhook_stats(
    request: Request,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.get_webhook_stats()


@router.get("/whatsapp/idempotency/stats")
@limiter.limit("60/minute")
async def get_whatsapp_idempotency_stats(request: Request):
    """Get WhatsApp webhook idempotency metrics and cleanup stats."""
    redis_client = await get_async_redis_client()
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    idempotency = AtomicWebhookIdempotency(redis_client)
    metrics = await idempotency.get_metrics()
    processing_stats = await idempotency.get_processing_stats()
    cleanup_stats = await idempotency.cleanup_expired_keys()

    duplicate_rate = metrics.get("cache_hit_rate", 0.0)
    alert_triggered = duplicate_rate > 0.05
    if alert_triggered:
        logger.warning(
            "Webhook duplicate rate exceeded threshold",
            extra={
                "duplicate_rate": duplicate_rate,
                "threshold": 0.05,
            },
        )

    return {
        "metrics": metrics,
        "processing": processing_stats,
        "cleanup": cleanup_stats,
        "alerts": [
            {
                "type": "duplicate_rate_high",
                "threshold": 0.05,
                "current": duplicate_rate,
            }
        ]
        if alert_triggered
        else [],
    }


@router.get("/{webhook_id:uuid}/health", response_model=WebhookHealth)
@limiter.limit("100/minute")
async def get_webhook_health(
    request: Request,
    webhook_id: UUID,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.get_webhook_health(webhook_id)


@router.get("/failed", response_model=FailedWebhookList)
@limiter.limit("100/minute")
async def get_failed_webhooks(
    request: Request,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.get_failed_webhooks()


# Stubs for other endpoints to maintain interface compatibility
@router.get("/{webhook_id:uuid}/deliveries", response_model=WebhookDeliveryList)
@limiter.limit("100/minute")
async def get_webhook_deliveries(
    request: Request,
    webhook_id: UUID,
    pagination: dict = Depends(get_pagination_params_async),
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.get_webhook_deliveries(webhook_id, pagination)


@router.post(
    "/{webhook_id:uuid}/deliveries/{delivery_id:uuid}/retry",
    response_model=WebhookRetryResponse,
)
@limiter.limit("10/minute")
async def retry_webhook_delivery(
    request: Request,
    webhook_id: UUID,
    delivery_id: UUID,
    retry_data: WebhookRetryRequest,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.retry_webhook_delivery(
        webhook_id, delivery_id, retry_data.force
    )


@router.get("/{webhook_id:uuid}/logs", response_model=WebhookLogList)
@limiter.limit("100/minute")
async def get_webhook_logs(
    request: Request,
    webhook_id: UUID,
    pagination: dict = Depends(get_pagination_params_async),
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.get_webhook_logs(webhook_id, pagination)


@router.post("/{webhook_id:uuid}/test", response_model=WebhookTestResponse)
@limiter.limit("5/minute")
async def test_webhook(
    request: Request,
    webhook_id: UUID,
    test_data: WebhookTestRequest,
    service: WebhookService = Depends(get_webhook_service),
    current_user=Depends(get_current_active_admin),
):
    return await service.test_webhook(webhook_id, test_data)
