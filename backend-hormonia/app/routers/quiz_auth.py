"""
Quiz Authentication Router - Secure httpOnly cookie-based authentication
SECURITY FIX: Replaces localStorage token storage with secure cookies
CVSS 8.1 HIGH → RESOLVED
"""
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import timedelta

from app.core.security import verify_password, create_access_token
from app.services.session_service import get_session_service, SessionService
from app.models.user import User
from app.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/quiz/auth", tags=["Quiz Authentication"])
security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class LoginResponse(BaseModel):
    success: bool
    message: str
    user: Optional[dict] = None


class LogoutResponse(BaseModel):
    success: bool
    message: str


@router.post("/login", response_model=LoginResponse)
async def quiz_login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    session_service: SessionService = Depends(get_session_service)
):
    """
    Quiz login with httpOnly cookie session

    Security Features:
    - httpOnly cookie (prevents XSS)
    - Secure flag in production (HTTPS only)
    - SameSite=Lax (CSRF protection)
    - Redis-backed sessions
    - No token in response body

    Args:
        request: Login credentials
        response: FastAPI response to set cookies
        db: Database session
        session_service: Session management service

    Returns:
        LoginResponse with user info (NO TOKEN)
    """
    # Verify credentials
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # Create session
    session_id = session_service.create_session(
        user_id=str(user.id),
        metadata={
            "email": user.email,
            "role": user.role,
            "login_type": "quiz"
        }
    )

    # Set httpOnly cookie
    cookie_max_age = int(timedelta(days=30).total_seconds()) if request.remember_me else None

    response.set_cookie(
        key="quiz_session",
        value=session_id,
        httponly=True,  # ✅ Prevents JavaScript access
        secure=True,    # ✅ HTTPS only (production)
        samesite="lax", # ✅ CSRF protection
        max_age=cookie_max_age,
        path="/",
        domain=None     # Same domain only
    )

    return LoginResponse(
        success=True,
        message="Login successful",
        user={
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role
        }
    )


@router.post("/logout", response_model=LogoutResponse)
async def quiz_logout(
    response: Response,
    quiz_session: Optional[str] = Cookie(None),
    session_service: SessionService = Depends(get_session_service)
):
    """
    Quiz logout - Clear session and cookie

    Args:
        response: FastAPI response
        quiz_session: Session ID from cookie
        session_service: Session management service

    Returns:
        LogoutResponse
    """
    if quiz_session:
        session_service.delete_session(quiz_session)

    # Clear cookie
    response.delete_cookie(
        key="quiz_session",
        path="/",
        domain=None
    )

    return LogoutResponse(
        success=True,
        message="Logged out successfully"
    )


@router.get("/me")
async def get_current_quiz_user(
    quiz_session: Optional[str] = Cookie(None),
    session_service: SessionService = Depends(get_session_service),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user from cookie session

    Args:
        quiz_session: Session ID from httpOnly cookie
        session_service: Session management service
        db: Database session

    Returns:
        User information

    Raises:
        401: If session invalid or expired
    """
    if not quiz_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    # Get user_id from session
    user_id = session_service.get_user_id(quiz_session)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid"
        )

    # Refresh session if needed
    session_service.refresh_session(quiz_session)

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled"
        )

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": user.is_active
    }


@router.post("/refresh")
async def refresh_quiz_session(
    quiz_session: Optional[str] = Cookie(None),
    session_service: SessionService = Depends(get_session_service)
):
    """
    Manually refresh session TTL

    Args:
        quiz_session: Session ID from cookie
        session_service: Session management service

    Returns:
        Success message
    """
    if not quiz_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    refreshed = session_service.refresh_session(quiz_session)

    if not refreshed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid"
        )

    return {"success": True, "message": "Session refreshed"}
