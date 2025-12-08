from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session,  joinedload
from sqlalchemy import or_, and_

from app.database import get_db
from app.models.user import User
from app.models.session import Session as SessionModel
from app.api.v2.dependencies import get_pagination_params, get_field_selection, apply_field_selection
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.core.redis_client import get_async_redis_client
from app.utils.rate_limiter import limiter
from app.schemas.v2.auth import (
    UserV2Response,
    UserPreferencesV2,
    UserPreferencesV2Update,
    UserPreferencesV2Response,
    SessionV2List,
    SessionRevokeResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

CACHE_TTL_USER_PROFILE = 300
CACHE_TTL_PREFERENCES = 600

async def _get_redis_client():
    try:
        return await get_async_redis_client()
    except Exception as redis_err:
        logger.debug(f"Redis client unavailable (non-critical): {redis_err}")
        return None

def _extract_user_id(current_user) -> str:
    if isinstance(current_user, dict):
        return current_user.get("id")
    return str(getattr(current_user, "id", None))

def _serialize_user(user: User, include_relationships: bool = False) -> dict:
    data = {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": getattr(user, 'firebase_last_sign_in', None),
    }
    if include_relationships:
        if hasattr(user, 'patients'):
            data["patient_count"] = len(user.patients) if user.patients else 0
        if hasattr(user, 'notifications'):
            unread = [n for n in user.notifications if not n.is_read]
            data["notification_count"] = len(unread)
    return data

def _get_user_preferences(user: User) -> UserPreferencesV2:
    if hasattr(user, 'metadata') and user.metadata:
        prefs = user.metadata.get('preferences', {})
        return UserPreferencesV2(**prefs)
    return UserPreferencesV2()

def _serialize_session(sessionModel) -> dict:
    return {
        "session_id": str(session.id),
        "user_id": str(session.user_id),
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
        "is_current": False # Logic simplified for now
    }

@router.get("/me", response_model=UserV2Response)
@limiter.limit("100/minute")
async def get_current_user_profile(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db),
    fields: Optional[List[str]] = Depends(get_field_selection),
):
    user_id = _extract_user_id(current_user)
    redis = await _get_redis_client()
    cache_key = f"user:profile:{user_id}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                user_data = json.loads(cached)
                if fields: user_data = apply_field_selection(user_data, fields)
                return user_data
        except Exception as cache_err:
            logger.debug(f"Cache read failed (non-critical): {cache_err}")

    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = db.query(User).options(
        joinedload(User.patients),
        joinedload(User.notifications)
    ).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(status_code=404)

    user_data = _serialize_user(user, include_relationships=True)
    user_data["preferences"] = _get_user_preferences(user).dict()

    if redis:
        try:
            await redis.setex(cache_key, CACHE_TTL_USER_PROFILE, json.dumps(user_data, default=str))
        except Exception as cache_err:
            logger.debug(f"Cache write failed (non-critical): {cache_err}")

    if fields:
        user_data = apply_field_selection(user_data, fields)

    return user_data

@router.get("/preferences", response_model=UserPreferencesV2Response)
@limiter.limit("100/minute")
async def get_preferences(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db),
):
    user_id = _extract_user_id(current_user)
    redis = await _get_redis_client()
    cache_key = f"user:preferences:{user_id}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached: return json.loads(cached)
        except Exception as cache_err:
            logger.debug(f"Cache read failed (non-critical): {cache_err}")

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user: raise HTTPException(status_code=404)

    prefs = _get_user_preferences(user)
    resp = {
        "user_id": user_id,
        "preferences": prefs.dict(),
        "updated_at": user.updated_at.isoformat() if user.updated_at else None
    }

    if redis:
        try:
            await redis.setex(cache_key, CACHE_TTL_PREFERENCES, json.dumps(resp, default=str))
        except Exception as cache_err:
            logger.debug(f"Cache write failed (non-critical): {cache_err}")

    return resp

@router.patch("/preferences", response_model=UserPreferencesV2Response)
@limiter.limit("20/hour")
async def patch_preferences(
    request: Request,
    updates: UserPreferencesV2Update,
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db),
):
    user_id = _extract_user_id(current_user)
    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user: raise HTTPException(status_code=404)

    current = _get_user_preferences(user).dict()
    update_data = updates.dict(exclude_unset=True)
    current.update(update_data)
    
    if not user.metadata: user.metadata = {}
    user.metadata['preferences'] = current
    user.updated_at = datetime.utcnow()
    
    db.commit()
    
    # Invalidate cache
    redis = await _get_redis_client()
    if redis:
        await redis.delete(f"user:preferences:{user_id}")
        await redis.delete(f"user:profile:{user_id}")

    return {
        "user_id": user_id,
        "preferences": current,
        "updated_at": user.updated_at.isoformat()
    }

@router.get("/sessions", response_model=SessionV2List)
@limiter.limit("60/minute")
async def list_sessions(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db),
    pagination=Depends(get_pagination_params),
):
    user_id = _extract_user_id(current_user)
    limit = pagination["limit"]
    cursor_data = pagination["cursor_data"]
    
    query = db.query(SessionModel).filter(
        SessionModel.user_id == UUID(user_id),
        SessionModel.is_active == True,
        SessionModel.revoked_at.is_(None)
    )
    
    if cursor_data and "id" in cursor_data:
        cid = UUID(cursor_data["id"])
        cdate = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        query = query.filter(or_(
            SessionModel.created_at < cdate,
            and_(SessionModel.created_at == cdate, SessionModel.id > cid)
        ))
        
    query = query.order_by(SessionModel.created_at.desc(), SessionModel.id)
    sessions = query.limit(limit + 1).all()
    
    has_more = len(sessions) > limit
    if has_more: sessions = sessions[:limit]
    
    serialized = [_serialize_session(s) for s in sessions]
    
    return {
        "sessions": serialized,
        "total": len(serialized) # Simplified
    }

@router.delete("/sessions/{session_id}", response_model=SessionRevokeResponse)
async def revoke_session(
    session_id: str,
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db),
):
    user_id = _extract_user_id(current_user)
    session = db.query(SessionModel).filter(
        SessionModel.id == UUID(session_id),
        SessionModel.user_id == UUID(user_id)
    ).first()
    
    if not session: raise HTTPException(status_code=404)
    
    session.is_active = False
    session.revoked_at = datetime.utcnow()
    db.commit()
    
    return {"session_id": session_id, "revoked": True, "message": "Revoked"}
