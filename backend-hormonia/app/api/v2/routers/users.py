from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, and_
from pydantic import ValidationError as PydanticValidationError

from app.database import get_db
from app.models.user import User
from app.models.session import Session as SessionModel
from app.api.v2.dependencies import (
    get_pagination_params_async,
    get_field_selection_async,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.core.redis_manager import get_async_redis_client
from app.utils.rate_limiter import limiter
from app.schemas.v2.auth import (
    UserV2Response,
    UserPreferencesV2,
    UserPreferencesV2Update,
    UserPreferencesV2Response,
    SessionV2List,
    SessionRevokeResponse,
)
from app.utils.auth_helpers import extract_user_id as _extract_user_id
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)

CACHE_TTL_USER_PROFILE = 300
CACHE_TTL_PREFERENCES = 600
REQUIRED_USER_PROFILE_FIELDS = {
    "id",
    "email",
    "full_name",
    "role",
    "is_active",
    "created_at",
    "updated_at",
}


async def _get_redis_client():
    try:
        return await get_async_redis_client()
    except Exception as redis_err:
        logger.debug(f"Redis client unavailable (non-critical): {redis_err}")
        return None


def _serialize_user(user: User, include_relationships: bool = False) -> dict:
    data = {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": getattr(user, "firebase_last_sign_in", None),
        "photo_url": getattr(user, "firebase_photo_url", None),
    }
    if include_relationships:
        if hasattr(user, "patients"):
            data["patient_count"] = len(user.patients) if user.patients else 0
        if hasattr(user, "notifications"):
            unread = [n for n in user.notifications if not n.is_read]
            data["notification_count"] = len(unread)
    return data


def _apply_profile_field_selection(user_data: dict, fields: Optional[List[str]]) -> dict:
    """Apply sparse fieldset while preserving required response-model fields."""
    if not fields:
        return user_data
    selected_fields = list(set(fields) | REQUIRED_USER_PROFILE_FIELDS)
    return apply_field_selection(user_data, selected_fields)


def _get_user_preferences(user: User) -> UserPreferencesV2:
    """Get user preferences from firebase_custom_claims or return defaults."""
    # Note: "metadata" is a reserved SQLAlchemy attribute, so we check firebase_custom_claims instead
    if hasattr(user, "firebase_custom_claims") and user.firebase_custom_claims:
        prefs = user.firebase_custom_claims.get("preferences", {})
        if prefs:
            return UserPreferencesV2(**prefs)
    return UserPreferencesV2()


def _serialize_session(sessionModel) -> dict:
    return {
        "session_id": str(sessionModel.id),
        "user_id": str(sessionModel.user_id),
        "created_at": sessionModel.created_at,
        "expires_at": sessionModel.expires_at,
        "ip_address": sessionModel.ip_address,
        "user_agent": sessionModel.user_agent,
        "is_current": False,  # Logic simplified for now
    }


@router.get("/me", response_model=UserV2Response)
@limiter.limit("100/minute")
async def get_current_user_profile(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
    fields: Optional[List[str]] = Depends(get_field_selection_async),
):
    user_id = _extract_user_id(current_user)
    redis = await _get_redis_client()
    cache_key = f"user:profile:{user_id}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                user_data = json.loads(cached)
                if REQUIRED_USER_PROFILE_FIELDS.issubset(user_data.keys()):
                    return _apply_profile_field_selection(user_data, fields)
                logger.warning(
                    "Ignoring stale profile cache with missing required fields for user %s",
                    user_id,
                )
        except Exception as cache_err:
            logger.debug(f"Cache read failed (non-critical): {cache_err}")

    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = (
        db.query(User)
        .options(joinedload(User.patients), joinedload(User.notifications))
        .filter(User.id == user_uuid)
        .first()
    )

    if not user:
        raise HTTPException(status_code=404)

    user_data = _serialize_user(user, include_relationships=True)
    user_data["preferences"] = _get_user_preferences(user).dict()

    if redis:
        try:
            await redis.setex(
                cache_key, CACHE_TTL_USER_PROFILE, json.dumps(user_data, default=str)
            )
        except Exception as cache_err:
            logger.debug(f"Cache write failed (non-critical): {cache_err}")

    return _apply_profile_field_selection(user_data, fields)


@router.get("/preferences", response_model=UserPreferencesV2Response)
@limiter.limit("100/minute")
async def get_preferences(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    user_id = _extract_user_id(current_user)
    redis = await _get_redis_client()
    cache_key = f"user:preferences:{user_id}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as cache_err:
            logger.debug(f"Cache read failed (non-critical): {cache_err}")

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404)

    prefs = _get_user_preferences(user)
    resp = {
        "user_id": user_id,
        "preferences": prefs.dict(),
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }

    if redis:
        try:
            await redis.setex(
                cache_key, CACHE_TTL_PREFERENCES, json.dumps(resp, default=str)
            )
        except Exception as cache_err:
            logger.debug(f"Cache write failed (non-critical): {cache_err}")

    return resp


@router.patch("/preferences", response_model=UserPreferencesV2Response)
@limiter.limit("20/hour")
async def patch_preferences(
    request: Request,
    updates: UserPreferencesV2Update,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    user_id = _extract_user_id(current_user)
    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404)

    current = _get_user_preferences(user).dict()
    update_data = updates.dict(exclude_unset=True)
    current.update(update_data)
    try:
        validated_preferences = UserPreferencesV2(**current).dict()
    except PydanticValidationError as exc:
        safe_errors = [
            {
                "loc": err.get("loc"),
                "msg": err.get("msg"),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=safe_errors)

    claims = dict(getattr(user, "firebase_custom_claims", {}) or {})
    claims["preferences"] = validated_preferences
    user.firebase_custom_claims = claims
    user.updated_at = now_sao_paulo()

    db.commit()

    # Invalidate cache
    redis = await _get_redis_client()
    if redis:
        await redis.delete(f"user:preferences:{user_id}")
        await redis.delete(f"user:profile:{user_id}")

    return {
        "user_id": user_id,
        "preferences": validated_preferences,
        "updated_at": user.updated_at.isoformat(),
    }


@router.put("/preferences", response_model=UserPreferencesV2Response, include_in_schema=False)
@limiter.limit("20/hour")
async def put_preferences(
    request: Request,
    updates: UserPreferencesV2,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """Backward-compatible full update endpoint for user preferences."""
    return await patch_preferences(
        request=request,
        updates=UserPreferencesV2Update(**updates.dict()),
        current_user=current_user,
        db=db,
    )


@router.get("/sessions", response_model=SessionV2List)
@limiter.limit("60/minute")
async def list_sessions(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
    pagination=Depends(get_pagination_params_async),
):
    user_id = _extract_user_id(current_user)
    limit = pagination["limit"]
    cursor_data = pagination["cursor_data"]

    query = db.query(SessionModel).filter(
        SessionModel.user_id == UUID(user_id),
        SessionModel.is_active,
        SessionModel.revoked_at.is_(None),
    )

    if cursor_data and "id" in cursor_data:
        cid = UUID(cursor_data["id"])
        cdate = datetime.fromisoformat(cursor_data["created_at"])
        query = query.filter(
            or_(
                SessionModel.created_at < cdate,
                and_(SessionModel.created_at == cdate, SessionModel.id > cid),
            )
        )

    query = query.order_by(SessionModel.created_at.desc(), SessionModel.id)
    sessions = query.limit(limit + 1).all()

    has_more = len(sessions) > limit
    if has_more:
        sessions = sessions[:limit]

    serialized = [_serialize_session(s) for s in sessions]

    return {
        "sessions": serialized,
        "total": len(serialized),  # Simplified
    }


@router.delete("/sessions/{session_id}", response_model=SessionRevokeResponse)
async def revoke_session(
    session_id: str,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    user_id = _extract_user_id(current_user)
    session = (
        db.query(SessionModel)
        .filter(
            SessionModel.id == UUID(session_id), SessionModel.user_id == UUID(user_id)
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=404)

    session.is_active = False
    session.revoked_at = now_sao_paulo()
    session.revocation_reason = "User requested revocation"
    db.commit()

    return {"session_id": session_id, "revoked": True, "message": "Revoked"}
