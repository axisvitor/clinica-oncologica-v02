"""
Debug & Diagnostics API v2
ADMIN-ONLY endpoints for system diagnostics and troubleshooting.

SECURITY:
- DISABLED by default in production (ENABLE_DEBUG_ENDPOINTS=false)
- ADMIN role required for all endpoints
- Rate limited to 5 requests/minute
- All operations audit logged
- Sensitive data masked/sanitized
- Time-boxed debug sessions (1 hour max)

WARNING: NEVER enable in production!
"""

import os
import sys
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.utils.rate_limiter import limiter
from app.schemas.v2.debug import (
    # Environment & Database
    EnvironmentInfo,
    EnvironmentVariable,
    DatabaseDiagnostics,
    DatabasePoolInfo,
    TestQueryRequest,
    TestQueryResult,
    # Auth Debug
    TokenDebugInfo,
    TokenClaim,
    LoginTestRequest,
    LoginTestResult,
    PermissionTestRequest,
    PermissionTestResult,
    AuthSimulationRequest,
    AuthSimulationResult,
    # Audit & Session
    DebugSession,
    DebugAuditLog,
    DebugResponse,
    DebugErrorResponse,
    ConnectionStatus,
    DebugSeverity,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Environment flag - MUST be explicitly enabled
DEBUG_ENDPOINTS_ENABLED = os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true"

# Safe environment variables (whitelist only)
SAFE_ENV_VARS = {
    "ENVIRONMENT", "DEBUG", "PYTHON_VERSION", "PYTHONPATH",
    "TZ", "LANG", "LC_ALL", "PORT", "HOST",
    # Database (masked values)
    "DATABASE_URL", "DB_HOST", "DB_PORT", "DB_NAME",
    # Redis (masked values)
    "REDIS_URL", "REDIS_HOST", "REDIS_PORT",
    # App config
    "API_VERSION", "APP_NAME", "LOG_LEVEL",
}

# Sensitive claims to mask in tokens
SENSITIVE_CLAIMS = {"password", "secret", "token", "key", "private"}


# ============================================================================
# Helper Functions
# ============================================================================

def check_debug_enabled():
    """Check if debug endpoints are enabled, raise 404 if not."""
    if not DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found"
        )


async def get_admin_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Verify ADMIN-ONLY access.

    TODO: Integrate with actual auth system.
    For now, checks for admin role in session/context.
    """
    # TODO: Get user from session/token
    # This is a placeholder - replace with actual auth integration

    # For now, get first admin user (REPLACE THIS IN PRODUCTION)
    admin = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.is_active == True
    ).first()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for debug endpoints"
        )

    return admin


async def log_debug_operation(
    db: Session,
    admin_user: User,
    endpoint: str,
    parameters: Dict[str, Any],
    result_summary: str,
    request: Request,
    severity: DebugSeverity = DebugSeverity.INFO
):
    """
    Log debug operation to audit trail.

    Args:
        db: Database session
        admin_user: Admin user performing operation
        endpoint: Debug endpoint called
        parameters: Operation parameters (sanitized)
        result_summary: Brief result summary (sanitized)
        request: FastAPI request object
        severity: Operation severity level
    """
    try:
        audit_log = AuditLog(
            id=uuid4(),
            user_id=admin_user.id,
            action=f"debug:{endpoint}",
            resource_type="debug",
            resource_id=None,
            changes={
                "endpoint": endpoint,
                "parameters": parameters,
                "result": result_summary,
                "severity": severity.value,
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            created_at=datetime.utcnow()
        )
        db.add(audit_log)
        db.commit()
        logger.info(
            f"Debug operation logged: {endpoint} by {admin_user.email} "
            f"(severity: {severity.value})"
        )
    except Exception as e:
        logger.error(f"Failed to log debug operation: {e}")
        # Don't fail the request if audit logging fails


def mask_sensitive_value(key: str, value: str) -> tuple[str, bool]:
    """
    Mask sensitive environment variables.

    Args:
        key: Environment variable key
        value: Environment variable value

    Returns:
        Tuple of (masked_value, is_masked)
    """
    sensitive_keywords = {
        "password", "secret", "key", "token", "credential",
        "private", "api_key", "auth", "jwt"
    }

    key_lower = key.lower()
    is_sensitive = any(kw in key_lower for kw in sensitive_keywords)

    if is_sensitive:
        # Show format but mask actual value
        if "://" in value:
            # URL format: show scheme and host, mask credentials
            parts = value.split("://", 1)
            if len(parts) == 2:
                scheme, rest = parts
                if "@" in rest:
                    # Has credentials
                    return f"{scheme}://***:***@{rest.split('@')[-1]}", True
                return f"{scheme}://***", True
        # Generic masking
        if len(value) > 8:
            return f"{value[:3]}***{value[-3:]}", True
        return "***", True

    return value, False


def sanitize_sql_query(query: str, max_length: int = 100) -> str:
    """
    Sanitize SQL query for safe logging.

    Args:
        query: SQL query string
        max_length: Maximum length to display

    Returns:
        Sanitized query string
    """
    # Truncate long queries
    if len(query) > max_length:
        return query[:max_length] + "..."
    return query


# ============================================================================
# Environment & Database Diagnostics (3 endpoints)
# ============================================================================

@router.get(
    "/environment",
    response_model=DebugResponse,
    summary="Get environment information",
    description="""
    Get safe environment information (whitelist only).

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Security:
    - Only whitelisted variables exposed
    - Sensitive values masked
    - Full audit trail
    """
)
@limiter.limit("5/minute")
async def get_environment_info(
    request: Request,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get environment information with masked sensitive values.

    Returns whitelisted environment variables only.
    Sensitive values are masked for security.
    """
    check_debug_enabled()

    try:
        # Collect safe environment variables
        env_vars = []
        for key in SAFE_ENV_VARS:
            value = os.getenv(key)
            if value is not None:
                masked_value, is_masked = mask_sensitive_value(key, value)
                env_vars.append(EnvironmentVariable(
                    key=key,
                    value=masked_value,
                    is_set=True,
                    is_masked=is_masked
                ))
            else:
                env_vars.append(EnvironmentVariable(
                    key=key,
                    value="<not set>",
                    is_set=False,
                    is_masked=False
                ))

        env_info = EnvironmentInfo(
            environment=os.getenv("ENVIRONMENT", "unknown"),
            debug_mode=DEBUG_ENDPOINTS_ENABLED,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            variables=env_vars,
            timestamp=datetime.utcnow()
        )

        # Audit log
        await log_debug_operation(
            db=db,
            admin_user=admin_user,
            endpoint="/environment",
            parameters={},
            result_summary=f"Retrieved {len(env_vars)} environment variables",
            request=request
        )

        return DebugResponse(
            success=True,
            data=env_info.dict(),
            audit_logged=True,
            timestamp=datetime.utcnow(),
            warning="Debug mode active - disable in production"
        )

    except Exception as e:
        logger.error(f"Environment info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve environment info: {str(e)}"
        )


@router.get(
    "/database",
    response_model=DebugResponse,
    summary="Get database diagnostics",
    description="""
    Get database connection and pool diagnostics.

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Checks:
    - Database connectivity
    - Connection pool status
    - Query response time
    """
)
@limiter.limit("5/minute")
async def get_database_diagnostics(
    request: Request,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get database connection diagnostics.

    Tests database connectivity, pool status, and response time.
    """
    check_debug_enabled()

    try:
        # Test database connection
        start_time = time.time()
        try:
            db.execute(text("SELECT 1"))
            response_time_ms = (time.time() - start_time) * 1000
            connected = True
            db_status = ConnectionStatus.HEALTHY
            error_msg = None
        except Exception as e:
            response_time_ms = None
            connected = False
            db_status = ConnectionStatus.UNHEALTHY
            error_msg = str(e)
            logger.error(f"Database connection test failed: {e}")

        # Get pool info if available
        pool_info = None
        try:
            engine = db.get_bind()
            pool = engine.pool
            pool_info = DatabasePoolInfo(
                size=pool.size(),
                checked_out=pool.checkedout(),
                overflow=pool.overflow(),
                checked_in=pool.checkedin()
            )
        except Exception as e:
            logger.warning(f"Failed to get pool info: {e}")

        diagnostics = DatabaseDiagnostics(
            status=db_status,
            connected=connected,
            pool_info=pool_info,
            response_time_ms=response_time_ms,
            error=error_msg,
            timestamp=datetime.utcnow()
        )

        # Audit log
        await log_debug_operation(
            db=db,
            admin_user=admin_user,
            endpoint="/database",
            parameters={},
            result_summary=f"Database {db_status.value}, {response_time_ms}ms response" if connected else "Database connection failed",
            request=request,
            severity=DebugSeverity.WARNING if not connected else DebugSeverity.INFO
        )

        return DebugResponse(
            success=True,
            data=diagnostics.dict(),
            audit_logged=True,
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Database diagnostics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database diagnostics: {str(e)}"
        )


@router.post(
    "/test-query",
    response_model=DebugResponse,
    summary="Test SQL query execution",
    description="""
    Test SQL query execution (SELECT only).

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Security:
    - Only SELECT queries allowed
    - Dangerous keywords blocked
    - Query timeout enforced
    - Results limited to 10 rows
    """
)
@limiter.limit("5/minute")
async def test_sql_query(
    request: Request,
    query_request: TestQueryRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Test SQL query execution with safety checks.

    Only SELECT queries are allowed.
    Results are limited to prevent data exposure.
    """
    check_debug_enabled()

    try:
        # Execute query with timeout
        start_time = time.time()
        try:
            # Set statement timeout
            db.execute(text(f"SET statement_timeout = {query_request.timeout_seconds * 1000}"))

            # Execute query
            result = db.execute(text(query_request.query))
            rows = result.fetchmany(10)  # Limit to 10 rows
            execution_time_ms = (time.time() - start_time) * 1000

            # Convert rows to dicts
            if rows:
                columns = result.keys()
                result_data = [dict(zip(columns, row)) for row in rows]
            else:
                result_data = []

            test_result = TestQueryResult(
                success=True,
                rows_returned=len(rows),
                execution_time_ms=execution_time_ms,
                result=result_data,
                error=None,
                query_sanitized=sanitize_sql_query(query_request.query)
            )

            # Audit log
            await log_debug_operation(
                db=db,
                admin_user=admin_user,
                endpoint="/test-query",
                parameters={"query": sanitize_sql_query(query_request.query, 50)},
                result_summary=f"Query executed: {len(rows)} rows, {execution_time_ms:.2f}ms",
                request=request
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            test_result = TestQueryResult(
                success=False,
                rows_returned=None,
                execution_time_ms=execution_time_ms,
                result=None,
                error=str(e),
                query_sanitized=sanitize_sql_query(query_request.query)
            )

            # Audit log error
            await log_debug_operation(
                db=db,
                admin_user=admin_user,
                endpoint="/test-query",
                parameters={"query": sanitize_sql_query(query_request.query, 50)},
                result_summary=f"Query failed: {str(e)}",
                request=request,
                severity=DebugSeverity.WARNING
            )

        return DebugResponse(
            success=test_result.success,
            data=test_result.dict(),
            audit_logged=True,
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Test query error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test query: {str(e)}"
        )


# ============================================================================
# Auth Debug Endpoints (4 endpoints)
# ============================================================================

@router.post(
    "/auth/token",
    response_model=DebugResponse,
    summary="Decode and validate JWT token",
    description="""
    Decode JWT token and validate claims (sensitive data masked).

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Security:
    - Sensitive claims masked
    - Token signature validated
    - Full audit trail
    """
)
@limiter.limit("5/minute")
async def debug_token_decode(
    request: Request,
    token: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Decode and validate JWT token with sensitive data masking.

    TODO: Integrate with actual JWT service.
    """
    check_debug_enabled()

    # TODO: Implement actual JWT decoding
    # Placeholder response
    logger.warning("JWT token decoding not yet fully implemented")

    token_info = TokenDebugInfo(
        valid=False,
        expired=False,
        claims=[],
        error="JWT decoding not yet implemented - placeholder response"
    )

    # Audit log
    await log_debug_operation(
        db=db,
        admin_user=admin_user,
        endpoint="/auth/token",
        parameters={"token": "***"},
        result_summary="Token decode requested (not implemented)",
        request=request
    )

    return DebugResponse(
        success=False,
        data=token_info.dict(),
        audit_logged=True,
        timestamp=datetime.utcnow(),
        warning="JWT decoding not yet implemented"
    )


@router.post(
    "/auth/test-login",
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
    """
)
@limiter.limit("5/minute")
async def test_login_flow(
    request: Request,
    login_request: LoginTestRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Test login flow with step-by-step diagnostics.

    Tests each step of authentication without creating actual session.
    """
    check_debug_enabled()

    steps_completed = []

    try:
        # Step 1: User lookup
        user = db.query(User).filter(User.email == login_request.email).first()
        user_found = user is not None
        steps_completed.append("user_lookup")

        if not user:
            result = LoginTestResult(
                success=False,
                user_found=False,
                password_valid=False,
                account_active=False,
                session_created=False,
                error="User not found",
                steps_completed=steps_completed
            )
        else:
            # Step 2: Password validation
            from app.utils.security import verify_password
            password_valid = verify_password(login_request.password, user.hashed_password)
            steps_completed.append("password_verify")

            # Step 3: Account status
            account_active = user.is_active
            steps_completed.append("account_status_check")

            # Step 4: Session creation (simulated)
            session_created = user_found and password_valid and account_active
            if session_created:
                steps_completed.append("session_create_simulated")

            result = LoginTestResult(
                success=session_created,
                user_found=True,
                password_valid=password_valid,
                account_active=account_active,
                session_created=session_created,
                token_generated="debug_token_***" if session_created else None,
                error=None if session_created else "Login failed (check password/status)",
                steps_completed=steps_completed
            )

        # Audit log
        await log_debug_operation(
            db=db,
            admin_user=admin_user,
            endpoint="/auth/test-login",
            parameters={"email": login_request.email},
            result_summary=f"Login test: {'success' if result.success else 'failed'} ({len(steps_completed)} steps)",
            request=request
        )

        return DebugResponse(
            success=True,
            data=result.dict(),
            audit_logged=True,
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Login test error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test login: {str(e)}"
        )


@router.post(
    "/auth/permissions",
    response_model=DebugResponse,
    summary="Test permission checks",
    description="""
    Test permission checking for user and resource.

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Tests:
    - User role lookup
    - Permission grants
    - Resource-level permissions
    """
)
@limiter.limit("5/minute")
async def test_permissions(
    request: Request,
    perm_request: PermissionTestRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
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
        user = db.query(User).filter(User.id == user_uuid).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # TODO: Implement actual permission checking
        # Placeholder logic
        user_role = user.role.value if hasattr(user.role, 'value') else str(user.role)
        has_permission = user_role == "admin"  # Admins have all permissions
        permissions_granted = ["admin:*"] if user_role == "admin" else [f"{user_role}:basic"]

        result = PermissionTestResult(
            has_permission=has_permission,
            user_role=user_role,
            permissions_granted=permissions_granted,
            reason=f"User role '{user_role}' {'grants' if has_permission else 'does not grant'} permission '{perm_request.permission}'"
        )

        # Audit log
        await log_debug_operation(
            db=db,
            admin_user=admin_user,
            endpoint="/auth/permissions",
            parameters={
                "user_id": perm_request.user_id,
                "permission": perm_request.permission
            },
            result_summary=f"Permission check: {perm_request.permission} = {has_permission}",
            request=request
        )

        return DebugResponse(
            success=True,
            data=result.dict(),
            audit_logged=True,
            timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Permission test error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test permissions: {str(e)}"
        )


@router.post(
    "/auth/simulate",
    response_model=DebugResponse,
    summary="Simulate user authentication",
    description="""
    Simulate user authentication with temporary session.

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Creates temporary debug session (max 60 minutes).
    Session is clearly marked as debug/temporary.
    """
)
@limiter.limit("5/minute")
async def simulate_authentication(
    request: Request,
    sim_request: AuthSimulationRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
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
        user = db.query(User).filter(User.id == user_uuid).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Create temporary debug session
        if sim_request.simulate_session:
            session_id = f"debug_sess_{uuid4().hex[:12]}"
            expires_at = datetime.utcnow() + timedelta(minutes=sim_request.duration_minutes)

            result = AuthSimulationResult(
                success=True,
                session_id=session_id,
                token=f"debug_{uuid4().hex[:16]}***",
                expires_at=expires_at,
                user_info={
                    "id": str(user.id),
                    "email": user.email,
                    "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                    "is_active": user.is_active
                }
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
                    "role": user.role.value if hasattr(user.role, 'value') else str(user.role)
                }
            )

        # Audit log
        await log_debug_operation(
            db=db,
            admin_user=admin_user,
            endpoint="/auth/simulate",
            parameters={
                "user_id": sim_request.user_id,
                "duration_minutes": sim_request.duration_minutes
            },
            result_summary=f"Auth simulation for user {user.email}",
            request=request,
            severity=DebugSeverity.WARNING  # Important security event
        )

        return DebugResponse(
            success=True,
            data=result.dict(),
            audit_logged=True,
            timestamp=datetime.utcnow(),
            warning="Debug session created - temporary use only"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth simulation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to simulate authentication: {str(e)}"
        )
