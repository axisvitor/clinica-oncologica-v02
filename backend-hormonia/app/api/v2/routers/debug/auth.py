"""
Authentication & Authorization Debug Endpoints

Endpoints:
- POST /auth/token - Decode and validate JWT token
- POST /auth/test-login - Test login flow
- POST /auth/permissions - Test permission checks
- POST /auth/simulate - Simulate user authentication
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.models.user import User
from app.utils.rate_limiter import limiter
from app.schemas.v2.debug import (
    TokenDebugInfo,
    LoginTestRequest,
    LoginTestResult,
    PermissionTestRequest,
    PermissionTestResult,
    AuthSimulationRequest,
    AuthSimulationResult,
    DebugResponse,
    DebugSeverity,
)

from .common import (
    check_debug_enabled,
    require_debug_enabled,
    get_admin_user,
    log_debug_operation,
)
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Auth Debug Endpoints
# ============================================================================


@router.post(
    "/token",
    dependencies=[Depends(require_debug_enabled)],
    response_model=DebugResponse,
    summary="Decode and validate JWT token",
    description="""
    Decode JWT token and validate claims (sensitive data masked).

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Security:
    - Sensitive claims masked
    - Token signature validated
    - Full audit trail
    """,
)
@limiter.limit("5/minute")
async def debug_token_decode(
    request: Request,
    token: str,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Decode and validate JWT token with sensitive data masking.

    Implements JWT token decoding with:
    - Firebase ID token validation
    - JWT structure analysis
    - Claims extraction with sensitive data masking
    - Expiration checking
    """
    check_debug_enabled()

    import jwt
    from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

    token_value = token.strip()
    token_info = None

    try:
        # First try to decode without verification to get token structure
        unverified_payload = jwt.decode(
            token_value, options={"verify_signature": False}
        )

        # Extract claims with sensitive data masking
        claims = []
        sensitive_keys = {"email", "phone_number", "name", "picture", "sub", "uid"}

        for key, value in unverified_payload.items():
            if key in sensitive_keys and value:
                # Mask sensitive data
                if isinstance(value, str):
                    if "@" in value:  # Email
                        masked_value = value[:2] + "***@" + value.split("@")[1]
                    else:
                        masked_value = value[:4] + "***" if len(value) > 4 else "***"
                else:
                    masked_value = "***"
                claims.append(f"{key}: {masked_value}")
            else:
                claims.append(f"{key}: {value}")

        # Check if token is expired
        import time

        exp_timestamp = unverified_payload.get("exp", 0)
        is_expired = exp_timestamp < time.time() if exp_timestamp else False

        # Try to verify with Firebase (if it's a Firebase token)
        is_valid = False
        try:
            from app.dependencies.auth_dependencies import verify_firebase_token

            firebase_data = await verify_firebase_token(token_value)
            if firebase_data:
                is_valid = True
        except Exception:
            # Not a valid Firebase token, but we still have the decoded data
            pass

        token_info = TokenDebugInfo(
            valid=is_valid, expired=is_expired, claims=claims, error=None
        )

        logger.info(
            f"JWT token decoded successfully. Valid: {is_valid}, Expired: {is_expired}"
        )

    except ExpiredSignatureError:
        token_info = TokenDebugInfo(
            valid=False, expired=True, claims=[], error="Token has expired"
        )

    except InvalidTokenError as e:
        token_info = TokenDebugInfo(
            valid=False,
            expired=False,
            claims=[],
            error=f"Invalid token format: {str(e)}",
        )
        f"Invalid token: {str(e)}"

    except Exception as e:
        token_info = TokenDebugInfo(
            valid=False,
            expired=False,
            claims=[],
            error=f"Token decode failed: {str(e)}",
        )
        str(e)

    # Audit log
    await log_debug_operation(
        db=db,
        admin_user=admin_user,
        endpoint="/auth/token",
        parameters={"token": "***"},
        result_summary=f"Token decoded. Valid: {token_info.valid}, Expired: {token_info.expired}",
        request=request,
    )

    return DebugResponse(
        success=token_info.valid or not token_info.error,
        data=token_info.dict(),
        audit_logged=True,
        timestamp=now_sao_paulo(),
        warning="JWT decoding not yet implemented",
    )


@router.post(
    "/test-login",
    dependencies=[Depends(require_debug_enabled)],
    response_model=DebugResponse,
    summary="Test login flow",
    description="""
    Test complete login flow with diagnostics.

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Tests:
    - User lookup
    - Password validation
    - Account status
    - Session creation
    """,
)
@limiter.limit("5/minute")
async def test_login_flow(
    request: Request,
    login_request: LoginTestRequest,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Test login flow with step-by-step diagnostics.

    Tests each step of authentication without creating actual session.
    """
    check_debug_enabled()

    steps_completed = []

    try:
        normalized_email = login_request.email.strip().lower()

        # Step 1: User lookup
        query_result = await db.execute(select(User).where(User.email == normalized_email))
        user = query_result.scalar_one_or_none()
        user_found = user is not None
        steps_completed.append("user_lookup")

        if not user:
            result = LoginTestResult(
                success=False,
                user_found=False,
                password_valid=False,
                account_active=False,
                account_locked=False,
                session_created=False,
                error="Invalid credentials",
                error_code="AUTH_INVALID_CREDENTIALS",
                steps_completed=steps_completed,
            )
        else:
            from app.utils.security import verify_password

            # Step 2: Password validation
            password_valid = bool(
                user.hashed_password and verify_password(login_request.password, user.hashed_password)
            )
            steps_completed.append("password_verify")

            # Step 3: Account status
            account_active = bool(user.is_active)
            account_locked = bool(user.is_locked)
            locked_until = getattr(user, "locked_until", None)
            if account_locked and locked_until is not None:
                current_time = now_sao_paulo()
                if locked_until.tzinfo is None:
                    locked_until = locked_until.replace(tzinfo=current_time.tzinfo)
                else:
                    locked_until = locked_until.astimezone(current_time.tzinfo)
                account_locked = current_time < locked_until
            steps_completed.append("account_status_check")

            error_code = None
            error = None
            if not password_valid:
                error_code = "AUTH_INVALID_CREDENTIALS"
                error = "Invalid credentials"
            elif account_locked:
                error_code = "AUTH_ACCOUNT_LOCKED"
                error = "Account is locked"
            elif not account_active:
                error_code = "AUTH_ACCOUNT_INACTIVE"
                error = "Account is inactive"

            # Step 4: Session creation (simulated)
            session_created = error_code is None
            if session_created:
                steps_completed.append("session_create_simulated")

            result = LoginTestResult(
                success=session_created,
                user_found=True,
                password_valid=password_valid,
                account_active=account_active,
                account_locked=account_locked,
                session_created=session_created,
                token_generated="session_***" if session_created else None,
                error=error,
                error_code=error_code,
                steps_completed=steps_completed,
            )

        # Audit log
        await log_debug_operation(
            db=db,
            admin_user=admin_user,
            endpoint="/auth/test-login",
            parameters={"email": normalized_email},
            result_summary=(
                f"Login test: {'success' if result.success else 'failed'} "
                f"error={result.error_code or 'none'} steps={','.join(steps_completed)}"
            ),
            request=request,
        )

        return DebugResponse(
            success=True,
            data=result.dict(),
            audit_logged=True,
            timestamp=now_sao_paulo(),
        )

    except Exception as e:
        logger.error(f"Login test error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test login: {str(e)}",
        )


@router.post(
    "/permissions",
    dependencies=[Depends(require_debug_enabled)],
    response_model=DebugResponse,
    summary="Test permission checks",
    description="""
    Test permission checking for user and resource.

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Tests:
    - User role lookup
    - Permission grants
    - Resource-level permissions
    """,
)
@limiter.limit("5/minute")
async def test_permissions(
    request: Request,
    perm_request: PermissionTestRequest,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Test permission checking for user.

    TODO: Integrate with actual RBAC system.
    """
    check_debug_enabled()

    try:
        # Look up user
        from uuid import UUID

        user_uuid = UUID(perm_request.user_id)
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Implement actual RBAC permission checking
        from app.dependencies.auth_dependencies import get_permissions_for_role

        user_role = user.role.value if hasattr(user.role, "value") else str(user.role)

        # Get all permissions for user's role
        permissions_granted = get_permissions_for_role(user_role)

        # Check if user has the requested permission
        has_permission = perm_request.permission in permissions_granted

        # Check for wildcard/hierarchical permissions
        if not has_permission and "." in perm_request.permission:
            permission_parts = perm_request.permission.split(".")
            for i in range(len(permission_parts)):
                # Check parent permissions (e.g., "admin.*" grants "admin.read")
                parent_perm = ".".join(permission_parts[: i + 1])
                if any(p.startswith(parent_perm) for p in permissions_granted):
                    has_permission = True
                    break

        result = PermissionTestResult(
            has_permission=has_permission,
            user_role=user_role,
            permissions_granted=permissions_granted,
            reason=f"User role '{user_role}' {'grants' if has_permission else 'does not grant'} permission '{perm_request.permission}' (checked against {len(permissions_granted)} permissions)",
        )

        # Audit log
        await log_debug_operation(
            db=db,
            admin_user=admin_user,
            endpoint="/auth/permissions",
            parameters={
                "user_id": perm_request.user_id,
                "permission": perm_request.permission,
            },
            result_summary=f"Permission check: {perm_request.permission} = {has_permission}",
            request=request,
        )

        return DebugResponse(
            success=True,
            data=result.dict(),
            audit_logged=True,
            timestamp=now_sao_paulo(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Permission test error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test permissions: {str(e)}",
        )


@router.post(
    "/simulate",
    dependencies=[Depends(require_debug_enabled)],
    response_model=DebugResponse,
    summary="Simulate user authentication",
    description="""
    Simulate user authentication with temporary session.

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Creates temporary debug session (max 60 minutes).
    Session is clearly marked as debug/temporary.
    """,
)
@limiter.limit("5/minute")
async def simulate_authentication(
    request: Request,
    sim_request: AuthSimulationRequest,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Simulate user authentication for testing.

    Creates temporary debug session with clear markers.
    """
    check_debug_enabled()

    try:
        # Look up user
        from uuid import UUID

        user_uuid = UUID(sim_request.user_id)
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Create temporary debug session
        if sim_request.simulate_session:
            session_id = f"debug_sess_{uuid4().hex[:12]}"
            expires_at = now_sao_paulo() + timedelta(
                minutes=sim_request.duration_minutes
            )

            result = AuthSimulationResult(
                success=True,
                session_id=session_id,
                token=f"debug_{uuid4().hex[:16]}***",
                expires_at=expires_at,
                user_info={
                    "id": str(user.id),
                    "email": user.email,
                    "role": user.role.value
                    if hasattr(user.role, "value")
                    else str(user.role),
                    "is_active": user.is_active,
                },
            )
        else:
            result = AuthSimulationResult(
                success=True,
                session_id=None,
                token=None,
                expires_at=None,
                user_info={
                    "id": str(user.id),
                    "email": user.email,
                    "role": user.role.value
                    if hasattr(user.role, "value")
                    else str(user.role),
                },
            )

        # Audit log
        await log_debug_operation(
            db=db,
            admin_user=admin_user,
            endpoint="/auth/simulate",
            parameters={
                "user_id": sim_request.user_id,
                "duration_minutes": sim_request.duration_minutes,
            },
            result_summary=f"Auth simulation for user {user.email}",
            request=request,
            severity=DebugSeverity.WARNING,  # Important security event
        )

        return DebugResponse(
            success=True,
            data=result.dict(),
            audit_logged=True,
            timestamp=now_sao_paulo(),
            warning="Debug session created - temporary use only",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth simulation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to simulate authentication: {str(e)}",
        )
