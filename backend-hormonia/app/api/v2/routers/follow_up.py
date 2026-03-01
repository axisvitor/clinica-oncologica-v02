"""
Follow-up admin endpoints for deduplication management.
"""

import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.redis_manager import get_async_redis_client
from app.dependencies.auth_dependencies import get_current_active_admin
from app.services.follow_up_system.message_deduplication_service import (
    MessageDeduplicationService,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _count_dedup_keys(redis_client, key_prefix: str) -> int:
    count = 0
    async for _ in redis_client.scan_iter(match=f"{key_prefix}*"):
        count += 1
    return count


def _decode_payload(raw_value: Optional[bytes | str]) -> Optional[dict]:
    if not raw_value:
        return None
    if isinstance(raw_value, bytes):
        raw_value = raw_value.decode("utf-8")
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return None


@router.get("/deduplication/stats")
async def get_deduplication_stats(
    current_user=Depends(get_current_active_admin),
) -> dict:
    dedup_service = MessageDeduplicationService()
    health = await dedup_service.health_check()
    redis_healthy = bool(health.get("healthy"))
    total_keys = 0

    try:
        redis = await get_async_redis_client()
        if redis:
            total_keys = await _count_dedup_keys(redis, dedup_service.key_prefix)
        else:
            redis_healthy = False
    except Exception as e:
        logger.warning("Failed to fetch deduplication stats", extra={"error": str(e)})
        redis_healthy = False

    return {
        "window_seconds": dedup_service.window_seconds,
        "redis_healthy": redis_healthy,
        "total_keys": total_keys,
    }


@router.delete("/deduplication/clear/{patient_id}")
async def clear_deduplication_cache(
    patient_id: UUID,
    current_user=Depends(get_current_active_admin),
) -> dict:
    dedup_service = MessageDeduplicationService()
    redis = await get_async_redis_client()
    if not redis:
        return {"patient_id": str(patient_id), "cleared": 0, "redis_healthy": False}

    cleared = 0
    pattern = f"{dedup_service.key_prefix}*"
    try:
        async for key in redis.scan_iter(match=pattern):
            raw_value = await redis.get(key)
            payload = _decode_payload(raw_value)
            if payload and payload.get("patient_id") == str(patient_id):
                cleared += 1
                await redis.delete(key)
    except Exception as e:
        logger.warning(
            "Failed to clear deduplication cache for patient",
            extra={"patient_id": str(patient_id), "error": str(e)},
        )
        return {"patient_id": str(patient_id), "cleared": 0, "redis_healthy": False}

    return {"patient_id": str(patient_id), "cleared": cleared, "redis_healthy": True}
