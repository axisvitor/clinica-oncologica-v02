from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID
import logging
import uuid

from fastapi import APIRouter, Depends, status, Request, Response

from app.core.exceptions import (
    BusinessRuleError,
    ForbiddenError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)
from app.database import get_db
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
    verify_firebase_token as verify_token,
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
SESSION_COOKIE_NAME = settings.SESSION_COOKIE_NAME


def _serialize_session(
    session, current_user=None, current_session_id: Optional[str] = None
) -> dict:
    """
    Serialize Session model to API-friendly dict matching SessionV2Response schema.

    Args:
        session: Session database model
        current_user: User data dict from auth (with id, email, role, etc.)
        current_session_id: Optional session ID to mark as current

    Returns:
        Dict matching SessionV2Response schema
    """
    from datetime import datetime as dt

    # Helper to parse ISO string or pass through datetime objects
    def _parse_datetime(value):
        if value is None:
            return None
        if isinstance(value, str):
            # Parse ISO format string from cache
            try:
                return dt.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None
        return value  # Already a datetime object

    # Format user data to match UserV2Response schema if provided
    user_data = None
    if current_user:
        # Extract user fields - current_user is a dict from get_current_user_from_session
        user_data = {
            "id": current_user.get("id"),
            "email": current_user.get("email"),
            "full_name": current_user.get("full_name"),
            "role": current_user.get("role", "doctor"),
            "is_active": current_user.get("is_active", True),
            # Parse timestamps (may be ISO strings from cache or datetime objects from DB)
            "created_at": _parse_datetime(current_user.get("created_at"))
            or session.created_at,
            "updated_at": _parse_datetime(current_user.get("updated_at"))
            or session.last_activity,
            "last_login": _parse_datetime(current_user.get("last_login")),
        }

    return {
        "session_id": str(session.id),
        "user_id": str(session.user_id),
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
        "is_current": str(session.id) == current_session_id
        if current_session_id
        else False,
        "valid": True,
        "user": user_data,
    }


def _extract_user_id(current_user) -> str:
    if isinstance(current_user, dict):
        return current_user.get("id")
    return str(getattr(current_user, "id", None))


@router.post(
    "/firebase/verify",
    response_model=FirebaseTokenVerifyResponse,
    summary="Verify Firebase token",
)
@limiter.limit("60/minute")
async def verify_firebase_token(
    request: Request,
    response: Response,
    payload: FirebaseTokenVerifyRequest,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """Verify Firebase ID token and create/update user session."""
    logger.info("Firebase login request received: Starting processing")

    try:
        # Standard Firebase Verification
        # Use dependency helper which handles service initialization and validation
        user_data = await verify_token(payload.id_token)
        logger.info(f"Token verified for user: {user_data.get('email')}")

        if not user_data:
            raise UnauthorizedError("Invalid Firebase token")

        firebase_uid = user_data.get("uid")
        email = user_data.get("email")

        if not firebase_uid or not email:
            raise ValidationError("Token missing required fields", details={"missing": "firebase_uid or email"})



        # Use FirebaseUserSyncService for secure synchronization and domain validation
        from app.services.firebase_user_sync_service import FirebaseUserSyncService
        from app.dependencies.auth_dependencies import _firebase_service

        sync_service = FirebaseUserSyncService(db, _firebase_service)
        try:
            user, created = await sync_service.sync_firebase_user(
                firebase_uid=firebase_uid,
                firebase_data=user_data,
                auto_create=True
            )
        except ValueError as e:
            # Handle unauthorized domain or invalid claims
            logger.warning(f"Firebase sync validation failed: {str(e)}")
            raise ForbiddenError("Access denied: Invalid user configuration")

        # Check account lock status with proper transaction handling
        if getattr(user, "is_locked", False):
            if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
                raise ForbiddenError("Account locked")
            # Use update query to avoid race conditions
            from app.models.user import User
            db.query(User).filter(User.id == user.id).update({
                "is_locked": False,
                "locked_until": None,
                "failed_login_attempts": 0
            })
            db.commit()
            db.refresh(user)



        # Create Session
        from app.models.session import Session as SessionModel

        session_id_hex = uuid.uuid4().hex
        session = SessionModel(
            user_id=user.id,
            session_token=session_id_hex,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            last_activity=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=5),  # 5 days default
            is_active=True,
        )
        db.add(session)

        # CRITICAL FIX: Use flush() instead of commit() to get session ID without persisting
        # This allows us to rollback if Redis creation fails
        db.flush()
        db.refresh(session)

        try:
            # Create Redis Session (Critical Fix)
            redis_result = await redis_cache.create_session(
                session_id=str(session.id),
                user_id=str(user.id),
                firebase_uid=user.firebase_uid,
                metadata={
                    "ip_address": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                },
                ttl_seconds=432000,  # 5 days
            )

            if not redis_result:
                print("Redis create_session FAILED (returned False)")
                # Rollback DB session since Redis failed
                db.rollback()
                raise ServiceUnavailableError("Failed to create Redis session")

            print(
                f"Redis Session created: session_id={session.id}, result={redis_result}"
            )

            # CRITICAL FIX: Only commit DB after Redis succeeds
            db.commit()

        except (ServiceUnavailableError, UnauthorizedError, ForbiddenError, ValidationError):
            # Re-raise domain exceptions (already logged and rolled back)
            raise
        except Exception as e:
            # Unexpected error during Redis creation - rollback DB and cleanup
            logger.error(f"Unexpected error during session creation: {e}")
            db.rollback()

            # Attempt to cleanup Redis session if it was partially created
            try:
                await redis_cache.invalidate_session(str(session.id))
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup Redis session: {cleanup_error}")

            raise ServiceUnavailableError("Failed to create session - transaction rolled back")

        # Set HttpOnly Cookie
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=str(session.id),
            httponly=True,
            secure=settings.SESSION_ENABLE_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            path="/",  # Important: ensure cookie is sent on all routes
            max_age=432000,  # 5 days
        )
        logger.info("Cookie set: %s=%s, path=/", SESSION_COOKIE_NAME, session.id)

        # Set X-Session-ID header for compatibility
        if (
            settings.APP_ENABLE_DEBUG
            and settings.APP_ENVIRONMENT.lower() != "production"
        ):
            response.headers["X-Session-ID"] = str(session.id)

        return {
            "valid": True,
            "session_id": str(session.id),
            "message": "Login successful",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                "is_active": getattr(user, 'is_active', True),
                "created_at": user.created_at or datetime.now(timezone.utc),
                "updated_at": user.updated_at or datetime.now(timezone.utc),
                "last_login": getattr(user, 'firebase_last_sign_in', None),
            },
        }

    except ValueError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        raise UnauthorizedError("Invalid or expired authentication token")
    except (ServiceUnavailableError, UnauthorizedError, ForbiddenError, ValidationError):
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()

        logger.error(f"Auth error: {e}\n{tb}")
        # Improve reliability by rolling back if session is active
        try:
            db.rollback()
        except Exception as rollback_err:
            logger.warning(f"Rollback failed during auth error recovery: {rollback_err}")

        raise ServiceUnavailableError("Authentication failed. Please try again later.")


@router.get("/verify-session", response_model=SessionV2Response)
@limiter.limit("100/minute")
async def verify_session(
    request: Request,
    response: Response,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Verify current session and return session + user details.

    Returns:
        SessionV2Response with full user data including timestamps
    """
    user_id = _extract_user_id(current_user)
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise ValidationError("Invalid user_id UUID", field="user_id")

    from app.models.session import Session as SessionModel
    from app.models.user import User

    # Get active session with user data
    session = (
        db.query(SessionModel)
        .filter(
            SessionModel.user_id == user_uuid,
            SessionModel.is_active,
            SessionModel.revoked_at.is_(None),
        )
        .order_by(SessionModel.last_activity.desc())
        .first()
    )

    if not session or session.expires_at < datetime.now(timezone.utc):
        raise UnauthorizedError("Session expired")

    # Enrich user data with database timestamps if not in cache
    # The current_user dict from cache might not have created_at/updated_at
    if not current_user.get("created_at") or not current_user.get("updated_at"):
        db_user = db.query(User).filter(User.id == user_uuid).first()
        if db_user:
            current_user["created_at"] = db_user.created_at
            current_user["updated_at"] = db_user.updated_at
            current_user["last_login"] = db_user.firebase_last_sign_in

    # Get session_id from cookie or header for is_current check
    session_id_from_request = request.cookies.get(SESSION_COOKIE_NAME) or request.headers.get(
        "X-Session-ID"
    )

    return _serialize_session(
        session, current_user=current_user, current_session_id=session_id_from_request
    )


@router.delete("/logout", status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def logout(
    request: Request,
    response: Response,
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    db=Depends(get_db),
):
    """Logout current session."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME) or request.headers.get(
        "X-Session-ID"
    )
    if session_id:
        # Validate session_id is a valid UUID before using in query
        try:
            session_uuid = UUID(session_id)
        except (ValueError, TypeError):
            logger.warning(f"Invalid session_id format: {session_id}")
            raise ValidationError("Invalid session ID", field="session_id")

        await redis_cache.invalidate_session(session_id)

        # Also mark as revoked in DB with proper error handling
        from app.models.session import Session as SessionModel

        try:
            db_session = (
                db.query(SessionModel).filter(SessionModel.id == session_uuid).first()
            )
            if db_session:
                db_session.is_active = False
                db_session.revoked_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as e:
            logger.error(f"Error revoking DB session: {e}")
            db.rollback()
            raise BusinessRuleError("Failed to revoke session")

    # Clear session cookie
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.SESSION_ENABLE_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    return {"message": "Logged out successfully", "success": True}


@router.delete("/logout-all", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def logout_all(
    request: Request,
    response: Response,
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    db=Depends(get_db),
):
    """Logout from all devices."""
    user_id = _extract_user_id(current_user)
    firebase_uid = (
        current_user.get("firebase_uid")
        if isinstance(current_user, dict)
        else current_user.firebase_uid
    )

    deleted_count = 0
    if firebase_uid:
        deleted_count = await redis_cache.invalidate_all_user_sessions(firebase_uid)

    # Revoke all in DB with proper error handling
    from app.models.session import Session as SessionModel

    try:
        user_uuid = UUID(user_id)
        db.query(SessionModel).filter(
            SessionModel.user_id == user_uuid, SessionModel.is_active
        ).update(
            {SessionModel.is_active: False, SessionModel.revoked_at: datetime.now(timezone.utc)}
        )
        db.commit()
    except Exception as e:
        logger.error(f"Error revoking all DB sessions: {e}")
        db.rollback()
        raise BusinessRuleError("Failed to revoke all sessions")

    # Clear session cookie
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.SESSION_ENABLE_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    return {
        "message": "Logged out from all devices",
        "success": True,
        "sessions_deleted": deleted_count,
    }


@router.get("/csrf-token")
@limiter.limit("100/minute")
async def get_csrf_token_endpoint(request: Request, response: Response):
    """
    Generate and return a cryptographically signed CSRF token.

    Security Model (Double Submit Cookie Pattern):
        1. Server generates signed token with HMAC-SHA256
        2. Token stored in httpOnly cookie (automatic browser management)
        3. Token returned in response body (for header inclusion)
        4. Client sends token in X-CSRF-Token header for protected requests

    Token Properties:
        - Format: {timestamp}.{random_hex}.{hmac_signature}
        - Encoding: Hexadecimal (URL-safe, auditable)
        - Entropy: 256 bits of cryptographically secure randomness
        - Signature: HMAC-SHA256 (prevents tampering)
        - Expiration: 1 hour (configurable)

    Response Format:
        {
            "csrf_token": "1734695123.a1b2c3d4e5f6...signature"
        }

    Cookie Configuration:
        - Name: csrf_token
        - Flags: httpOnly, secure (production), SameSite=Strict
        - Max-Age: 3600 seconds (1 hour)

    Usage Example:
        1. GET /api/v2/auth/csrf-token
        2. Extract token from response body
        3. Include in header: X-CSRF-Token: {token}
        4. Make state-changing request (POST, PUT, DELETE, PATCH)

    Rate Limiting:
        100 requests per minute per IP address

    Security Notes:
        - Token is cryptographically signed (prevents forgery)
        - Token expires after 1 hour (prevents replay attacks)
        - Cookie is httpOnly (prevents XSS token theft)
        - SameSite=Strict (prevents CSRF from external sites)

    Returns:
        dict: Response containing the CSRF token

    Raises:
        BusinessRuleError: If token generation fails
    """
    from app.middleware.csrf import get_csrf_token, set_csrf_cookie

    try:
        # Generate cryptographically secure CSRF token
        token = get_csrf_token()

        # Set token in httpOnly cookie (returns token for convenience)
        set_csrf_cookie(response, token)

        # Log token generation (without exposing token value)
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f"CSRF token generated for client: {client_ip}")

        # Return token in response body for client-side storage
        return {"csrf_token": token}

    except ValueError as e:
        # Handle invalid secret key or configuration errors
        logger.error(f"CSRF token generation failed: {str(e)}")
        raise BusinessRuleError("CSRF token generation failed. Please contact administrator.")
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error generating CSRF token: {str(e)}")
        raise BusinessRuleError("Internal server error")


# ============================================================================
# Profile Management Endpoints
# ============================================================================


@router.put("/profile")
@limiter.limit("10/minute")
async def update_profile(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Update current user's profile information.
    
    Accepts: full_name, email, phone, specialty
    """
    from app.models.user import User
    from pydantic import BaseModel, EmailStr
    from typing import Optional
    
    class ProfileUpdateRequest(BaseModel):
        email: Optional[EmailStr] = None
        full_name: Optional[str] = None
        phone: Optional[str] = None
        specialty: Optional[str] = None
    
    user_id = _extract_user_id(current_user)
    
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise ValidationError("Invalid user_id UUID", field="user_id")
    
    # Parse request body
    body = await request.json()
    update_data = ProfileUpdateRequest(**body)
    
    # Get user from database
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise BusinessRuleError("User not found")
    
    # Update fields
    updated = False
    if update_data.full_name is not None:
        user.full_name = update_data.full_name
        updated = True
    if update_data.email is not None:
        # Check if email is already taken
        existing = db.query(User).filter(User.email == update_data.email, User.id != user_uuid).first()
        if existing:
            raise ValidationError("Email already in use", field="email")
        user.email = update_data.email
        updated = True
    
    # Store phone and specialty in firebase_custom_claims (or a dedicated field)
    claims = user.firebase_custom_claims or {}
    if update_data.phone is not None:
        claims["phone"] = update_data.phone
        updated = True
    if update_data.specialty is not None:
        claims["specialty"] = update_data.specialty
        updated = True
    
    if updated:
        user.firebase_custom_claims = claims
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
    
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "phone": claims.get("phone"),
        "specialty": claims.get("specialty"),
        "avatar_url": claims.get("avatar_url"),
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.put("/password")
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    current_user=Depends(get_current_user_from_session),
):
    """
    Change user password via Firebase.
    
    Note: This endpoint delegates to Firebase for password management.
    The client should reauthenticate with Firebase before calling this.
    """
    from pydantic import BaseModel
    
    class PasswordChangeRequest(BaseModel):
        new_password: str
    
    body = await request.json()
    password_data = PasswordChangeRequest(**body)
    
    firebase_uid = (
        current_user.get("firebase_uid")
        if isinstance(current_user, dict)
        else getattr(current_user, "firebase_uid", None)
    )
    
    if not firebase_uid:
        raise ValidationError("Firebase UID not found", field="firebase_uid")
    
    # Update password in Firebase
    try:
        from app.dependencies.auth_dependencies import _firebase_service
        
        if _firebase_service and hasattr(_firebase_service, "update_user"):
            await _firebase_service.update_user(
                firebase_uid,
                password=password_data.new_password
            )
        else:
            # Fallback to Firebase Admin SDK directly
            import firebase_admin.auth as firebase_auth
            firebase_auth.update_user(firebase_uid, password=password_data.new_password)
        
        logger.info(f"Password changed for user: {firebase_uid}")
        return {"message": "Password changed successfully", "success": True}
    
    except Exception as e:
        logger.error(f"Password change failed: {e}")
        raise BusinessRuleError("Failed to change password. Please try again.")


@router.post("/avatar")
@limiter.limit("5/minute")
async def upload_avatar(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Upload user avatar image.
    
    Accepts multipart/form-data with 'file' field.
    Stores in local storage or cloud storage based on configuration.
    """
    from fastapi import UploadFile
    from app.models.user import User
    import os
    import hashlib
    
    user_id = _extract_user_id(current_user)
    
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise ValidationError("Invalid user_id UUID", field="user_id")
    
    # Parse multipart form data
    form = await request.form()
    file: UploadFile = form.get("file")
    
    if not file:
        raise ValidationError("No file provided", field="file")
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    content_type = file.content_type or ""
    if content_type not in allowed_types:
        raise ValidationError(
            f"Invalid file type. Allowed: {', '.join(allowed_types)}",
            field="file"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size (max 5MB)
    if len(content) > 5 * 1024 * 1024:
        raise ValidationError("File too large. Maximum size is 5MB", field="file")
    
    # Generate unique filename
    file_hash = hashlib.md5(content).hexdigest()[:12]
    ext = content_type.split("/")[-1]
    if ext == "jpeg":
        ext = "jpg"
    filename = f"avatar_{user_id}_{file_hash}.{ext}"
    
    # Save to uploads directory (create if needed)
    uploads_dir = os.path.join(settings.BASE_DIR if hasattr(settings, 'BASE_DIR') else ".", "uploads", "avatars")
    os.makedirs(uploads_dir, exist_ok=True)
    
    file_path = os.path.join(uploads_dir, filename)
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Generate URL (assuming static file serving is configured)
    avatar_url = f"/uploads/avatars/{filename}"
    
    # Update user's avatar_url in database
    user = db.query(User).filter(User.id == user_uuid).first()
    if user:
        claims = user.firebase_custom_claims or {}
        claims["avatar_url"] = avatar_url
        user.firebase_custom_claims = claims
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
    
    logger.info(f"Avatar uploaded for user: {user_id}")
    
    return {"avatar_url": avatar_url, "success": True}
