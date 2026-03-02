"""
WhatsApp monitoring endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.database import get_db
from app.integrations.whatsapp.metrics import whatsapp_metrics
from app.integrations.whatsapp.queue.manager import QueueManager
from app.integrations.whatsapp.queue.dlq import DLQHandler
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.utils.timezone import now_sao_paulo

router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse)
async def get_whatsapp_metrics():
    """Expose WhatsApp Prometheus metrics."""
    return PlainTextResponse(
        content=whatsapp_metrics.render_prometheus(),
        media_type=whatsapp_metrics.content_type,
    )


@router.get("/health")
async def get_whatsapp_health(db=Depends(get_db)):
    """Detailed health check for WhatsApp integration."""
    service = UnifiedWhatsAppService(
        db,
        default_instance_name="wuzapi",
    )
    return await service.health_check()


@router.get("/queue-stats")
async def get_queue_stats(
    instance_name: Optional[str] = Query(None),
):
    """Queue statistics for WhatsApp message processing."""
    manager = QueueManager(
        default_instance="wuzapi",
        redis_url=settings.REDIS_URL,
    )
    try:
        status = await manager.get_queue_status(instance_name)
        return {
            "queue": status.model_dump(),
            "timestamp": now_sao_paulo().isoformat(),
        }
    finally:
        await manager.disconnect()


@router.get("/dlq-stats")
async def get_dlq_stats(
    days_back: int = Query(7, ge=1, le=90),
    db=Depends(get_db),
):
    """DLQ statistics for WhatsApp failed messages."""
    handler = DLQHandler(db)
    metrics = await handler.get_dlq_metrics(days_back=days_back)
    return {
        "dlq": metrics,
        "timestamp": now_sao_paulo().isoformat(),
    }
