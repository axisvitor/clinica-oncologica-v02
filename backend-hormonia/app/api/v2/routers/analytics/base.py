"""
Base module for analytics - Common utilities and types.
"""

from typing import Optional, Tuple, Dict, Any
import json
import hashlib
from uuid import UUID
from fastapi import APIRouter

from app.models.user import UserRole
from app.models.patient import Patient
from app.services.analytics import RiskLevel, PatientRisk
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Cache TTL in seconds (15 minutes for analytics)
ANALYTICS_CACHE_TTL = 900
COLOR_PALETTE = [
    "#2563eb",  # blue
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#8b5cf6",  # violet
    "#0ea5e9",  # sky
]


def get_role_and_user(current_user) -> Tuple[UserRole, Optional[UUID]]:
    """
    Extract role and user UUID from current_user which can be model or dict.

    Args:
        current_user: User object or dict containing role and id

    Returns:
        Tuple of (UserRole, Optional[UUID])
    """
    if isinstance(current_user, dict):
        role_value = current_user.get("role", "doctor")
        user_id = current_user.get("id")
    else:
        role_value = getattr(current_user, "role", "doctor")
        user_id = getattr(current_user, "id", None)

    # Optimize role conversion
    if isinstance(role_value, UserRole):
        role = role_value
    elif isinstance(role_value, str):
        role_lower = role_value.lower()
        if role_lower == "admin":
            role = UserRole.ADMIN
        else:
            role = UserRole.DOCTOR
    else:
        role = UserRole.DOCTOR

    # Optimize UUID conversion
    if user_id:
        try:
            user_uuid = UUID(str(user_id))
        except (TypeError, ValueError):
            user_uuid = None
    else:
        user_uuid = None

    return role, user_uuid


def serialize_patient_risk(
    patient_risk: PatientRisk,
    patient_lookup: Optional[Dict[UUID, Patient]] = None,
) -> Dict[str, Any]:
    """
    Convert PatientRisk objects into JSON-serializable dicts.

    Args:
        patient_risk: PatientRisk object to serialize
        patient_lookup: Optional lookup dict for patient names

    Returns:
        Dict with serialized patient risk data
    """
    if patient_risk is None:
        return {}

    last_response = (
        patient_risk.last_response.isoformat() if patient_risk.last_response else None
    )
    patient_obj = (
        patient_lookup.get(patient_risk.patient_id)
        if patient_lookup and patient_risk.patient_id in patient_lookup
        else None
    )
    patient_name = patient_obj.name if patient_obj else None

    return {
        "id": str(patient_risk.patient_id),
        "patient_id": str(patient_risk.patient_id),
        "name": patient_name,
        "risk_level": patient_risk.risk_level.value
        if isinstance(patient_risk.risk_level, RiskLevel)
        else patient_risk.risk_level,
        "risk_factors": patient_risk.risk_factors,
        "last_response": last_response,
        "recommended_actions": patient_risk.recommended_actions,
    }


def get_cache_key(endpoint: str, **params) -> str:
    """
    Generate cache key from endpoint and parameters.

    Args:
        endpoint: Endpoint name
        **params: Query parameters

    Returns:
        Cache key string
    """
    param_str = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()
    return f"analytics:v2:{endpoint}:{param_hash}"


async def get_cached_result(cache_key: str):
    """
    Get cached result from Redis.

    Args:
        cache_key: Cache key to lookup

    Returns:
        Cached data dict or None if not found
    """
    try:
        from app.core.redis_unified import get_async_redis

        redis_client = await get_async_redis()
        if redis_client is None:
            logger.debug("Redis not available, skipping cache read")
            return None
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT: {cache_key}")
            return json.loads(cached)
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
        return None


async def set_cached_result(cache_key: str, data: dict, ttl: int = ANALYTICS_CACHE_TTL):
    """
    Set cached result in Redis.

    Args:
        cache_key: Cache key
        data: Data to cache
        ttl: Time to live in seconds
    """
    try:
        from app.core.redis_unified import get_async_redis

        redis_client = await get_async_redis()
        if redis_client is None:
            logger.debug("Redis not available, skipping cache write")
            return
        await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")
