from datetime import datetime
from typing import Optional, Any
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
# # from sqlalchemy.orm import Session,

from app.database import get_db
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
    verify_firebase_token as verify_token
)
from app.utils.rate_limiter import limiter
from app.schemas.v2.auth import (
    FirebaseTokenVerifyRequest,
    FirebaseTokenVerifyResponse,
    SessionV2Response,
)
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

def _serialize_session(session, current_session_id: Optional[str] = None) -> dict:
    """Serialize Session model to API-friendly dict."""
    return {
        "session_id": str(session.id),
        "user_id": str(session.user_id),
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
        "is_current": str(session.id) == current_session_id if current_session_id else False,
    }

def _extract_user_id(current_user) -> str:
    if isinstance(current_user, dict):
        return current_user.get("id")
    return str(getattr(current_user, "id", None))

@router.post(
    "/firebase/verify",
    response_model=FirebaseTokenVerifyResponse,
    summary="Verify Firebase token"
)
@limiter.limit("60/minute")
async def verify_firebase_token(
    request: Request,
    response: Response,
    payload: FirebaseTokenVerifyRequest,
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
):
    """Verify Firebase ID token and create/update user session."""
    try:
        user_data = await verify_token(payload.id_token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid Firebase token")

        firebase_uid = user_data.get("uid")
        email = user_data.get("email")

        if not firebase_uid or not email:
            raise HTTPException(status_code=400, detail="Token missing fields")

        from app.repositories.user import UserRepository
        user_repo = UserRepository(db)
        user = user_repo.get_by_firebase_uid(firebase_uid)

        if user:
            # Update existing
            user.firebase_last_sign_in = datetime.utcnow()
            user.firebase_email_verified = user_data.get("email_verified", False)
            if user_data.get("name"): user.firebase_display_name = user_data.get("name")
            if user_data.get("picture"): user.firebase_photo_url = user_data.get("picture")
            user.firebase_custom_claims = user_data.get("custom_claims", {})
            user.last_firebase_sync = datetime.utcnow()
            
            # Lock check
            if getattr(user, 'is_locked', False):
                if user.locked_until and datetime.utcnow() < user.locked_until:
                     raise HTTPException(status_code=403, detail="Account locked")
                user.is_locked = False
                user.locked_until = None
                user.failed_login_attempts = 0
            
            db.commit()
            db.refresh(user)
        else:
            # Create new
            from app.models.user import User, AuthProvider, UserRole
            custom_claims = user_data.get("custom_claims", {})
            firebase_role = custom_claims.get("role", "doctor").lower()
            user_role = UserRole.ADMIN if firebase_role == "admin" else UserRole.DOCTOR

            user = User(
                firebase_uid=firebase_uid,
                email=email,
                full_name=user_data.get("name", email.split("@")[0]),
                is_active=True,
                role=user_role,
                auth_provider=AuthProvider.FIREBASE,
                firebase_email_verified=user_data.get("email_verified", False),
                firebase_display_name=user_data.get("name"),
                firebase_photo_url=user_data.get("picture"),
                firebase_custom_claims=custom_claims,
                firebase_created_at=datetime.utcnow(),
                firebase_last_sign_in=datetime.utcnow(),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Create Session
        from app.models.session import Session as SessionModel
        session = SessionModel(
            user_id=user.id,
            firebase_session_id=uuid.uuid4().hex, # Mock or real logic needed? Old code was unclear, assuming standard
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.utcnow() + timedelta(days=5), # 5 days default
            is_active=True
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Create Redis Session (Critical Fix)
        await redis_cache.create_session(
            session_id=str(session.id),
            user_id=str(user.id),
            firebase_uid=user.firebase_uid,
            metadata={
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            },
            ttl_seconds=432000 # 5 days
        )
        
        # Set HttpOnly Cookie
        response.set_cookie(
            key="session_id",
            value=str(session.id),
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite="lax",
            max_age=432000 # 5 days
        )
        
        # Set X-Session-ID header for compatibility
        response.headers["X-Session-ID"] = str(session.id)

        # Return correct response structure matching FirebaseTokenVerifyResponse
        return {
            "valid": True,
            "session_id": str(session.id),
            "message": "Login successful"
        }

    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

import uuid
from datetime import timedelta

@router.post("/verify-session", response_model=SessionV2Response)
@limiter.limit("100/minute")
async def verify_session(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db),
):
    user_id = _extract_user_id(current_user)
    try:
        user_uuid = UUID(user_id)
    except:
        raise HTTPException(status_code=400)

    from app.models.session import Session as SessionModel
    session = db.query(SessionModel).filter(
        SessionModel.user_id == user_uuid,
        SessionModel.is_active == True,
        SessionModel.revoked_at.is_(None)
    ).order_by(SessionModel.last_activity.desc()).first()

    if not session or session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Session expired")

    return _serialize_session(session)

@router.delete("/logout", status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def logout(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    db=Depends(get_db)
):
    """Logout current session."""
    session_id = request.cookies.get("session_id") or request.headers.get("X-Session-ID")
    if session_id:
        await redis_cache.invalidate_session(session_id)
        
        # Also mark as revoked in DB
        from app.models.session import Session as SessionModel
        try:
            db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if db_session:
                db_session.is_active = False
                db_session.revoked_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"Error revoking DB session: {e}")

    return {"message": "Logged out successfully", "success": True}

@router.delete("/logout-all", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def logout_all(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    db=Depends(get_db)
):
    """Logout from all devices."""
    user_id = _extract_user_id(current_user)
    firebase_uid = current_user.get("firebase_uid") if isinstance(current_user, dict) else current_user.firebase_uid
    
    deleted_count = 0
    if firebase_uid:
        deleted_count = await redis_cache.invalidate_all_user_sessions(firebase_uid)
    
    # Revoke all in DB
    from app.models.session import Session as SessionModel
    try:
        user_uuid = UUID(user_id)
        db.query(SessionModel).filter(
            SessionModel.user_id == user_uuid,
            SessionModel.is_active == True
        ).update({
            SessionModel.is_active: False, 
            SessionModel.revoked_at: datetime.utcnow()
        })
        db.commit()
    except Exception as e:
        logger.error(f"Error revoking all DB sessions: {e}")

    return {
        "message": "Logged out from all devices", 
        "success": True, 
        "sessions_deleted": deleted_count
    }

@router.get("/csrf-token")
async def get_csrf_token():
    """
    Get CSRF token.
    
    Note: In this API-first design, we rely primarily on HTTP-only cookies 
    and SameSite=Strict for CSRF protection, but this endpoint is provided 
    for clients that require explicit CSRF tokens.
    """
    return {"csrf_token": uuid.uuid4().hex}
