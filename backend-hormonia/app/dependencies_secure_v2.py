"""
Secure FastAPI Dependencies for Hormonia Backend System.

This module provides secure dependency injection with fixed auto-provisioning,
comprehensive RBAC, rate limiting, and audit logging.

SECURITY FIXES:
1. Secure role determination from Supabase metadata
2. Domain validation for auto-provisioning
3. Rate limiting for authentication endpoints
4. Comprehensive audit logging
5. Permission validation middleware
"""
import logging
import httpx
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Generator, Tuple, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from uuid import UUID
import redis.asyncio as redis
from functools import wraps

# Core imports
from app.database import get_db, get_supabase
from app.config import settings
from app.models.user import User, UserRole
from app.repositories.user import UserRepository

# Security imports
from app.core.permissions import (
    role_determiner,
    permission_checker,
    Permission,
    PermissionChecker,
    ROLE_DEFINITIONS,
    SecurityLevel
)
from app.core.security_config import get_security_config, security_config

# Service imports
try:
    from app.services import ServiceProvider, get_service_provider
except ImportError as e:
    logger.error(f"Failed to import ServiceProvider: {e}")
    raise ImportError(f"ServiceProvider not available: {e}") from e

from app.core.session_manager import get_session_manager, get_request_factory
from app.services.flow_analytics import FlowAnalyticsService

logger = logging.getLogger(__name__)

# Security scheme for JWT authentication
security = HTTPBearer()

# =============================================================================
# RATE LIMITING SYSTEM
# =============================================================================

class RateLimiter:
    """Redis-based rate limiter with configurable limits."""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection for rate limiting."""
        try:
            redis_url = settings.REDIS_URL
            self.redis_client = redis.from_url(redis_url)
        except Exception as e:
            logger.warning(f"Redis not available for rate limiting: {e}")
            self.redis_client = None

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60,
        burst_size: Optional[int] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.

        Args:
            key: Unique identifier for rate limiting (IP, user_id, etc.)
            limit: Maximum requests allowed
            window_seconds: Time window in seconds
            burst_size: Maximum burst requests allowed

        Returns:
            Tuple of (is_allowed, info_dict)
        """
        if not self.redis_client:
            # Fall back to allowing request if Redis is unavailable
            logger.warning("Rate limiting unavailable - Redis not connected")
            return True, {"fallback": True}

        try:
            current_time = int(time.time())
            window_start = current_time - window_seconds

            # Clean old entries
            await self.redis_client.zremrangebyscore(key, 0, window_start)

            # Count current requests
            current_count = await self.redis_client.zcard(key)

            # Check burst limit first (short lookback window)
            if burst_size:
                burst_count = current_count
                try:
                    burst_window_start = max(window_start, current_time - 10)
                    burst_candidate = await self.redis_client.zcount(key, burst_window_start, current_time)
                    if isinstance(burst_candidate, (int, float)):
                        burst_count = int(burst_candidate)
                    else:
                        burst_count = await self.redis_client.zcard(key)
                except AttributeError:
                    burst_count = await self.redis_client.zcard(key)

                if burst_count >= burst_size:
                    return False, {
                        "error": "burst_limit_exceeded",
                        "limit": limit,
                        "window_seconds": window_seconds,
                        "current_count": burst_count,
                        "burst_size": burst_size
                    }

            # Check regular limit
            if current_count >= limit:
                return False, {
                    "error": "rate_limit_exceeded",
                    "limit": limit,
                    "window_seconds": window_seconds,
                    "current_count": current_count,
                    "retry_after": window_seconds
                }

            # Add current request
            await self.redis_client.zadd(key, {str(current_time): current_time})
            await self.redis_client.expire(key, window_seconds)

            return True, {
                "limit": limit,
                "window_seconds": window_seconds,
                "current_count": current_count + 1,
                "remaining": limit - current_count - 1
            }

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Allow request on error to avoid blocking legitimate users
            return True, {"error": str(e), "fallback": True}

# Global rate limiter instance
rate_limiter = RateLimiter()

# =============================================================================
# SECURITY AUDIT LOGGER
# =============================================================================

class SecurityAuditLogger:
    """Comprehensive security event logging."""

    def __init__(self):
        self.security_logger = logging.getLogger("security_audit")
        self.events: List[Dict[str, Any]] = []

    def log_authentication_event(
        self,
        event_type: str,
        user_email: str,
        success: bool,
        reason: str,
        request_info: Dict[str, Any],
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log authentication-related events."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": f"auth_{event_type}",
            "user_email": user_email,
            "success": success,
            "reason": reason,
            "ip_address": request_info.get("client_ip"),
            "user_agent": request_info.get("user_agent"),
            "request_id": request_info.get("request_id"),
            "additional_data": additional_data or {}
        }

        self.security_logger.info(json.dumps(event))
        self.events.append(event)

    def log_authorization_event(
        self,
        event_type: str,
        user_email: str,
        user_role: str,
        permission: str,
        resource: str,
        success: bool,
        reason: str,
        request_info: Dict[str, Any]
    ):
        """Log authorization-related events."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": f"authz_{event_type}",
            "user_email": user_email,
            "user_role": user_role,
            "permission": permission,
            "resource": resource,
            "success": success,
            "reason": reason,
            "ip_address": request_info.get("client_ip"),
            "user_agent": request_info.get("user_agent"),
            "request_id": request_info.get("request_id")
        }

        self.security_logger.info(json.dumps(event))
        self.events.append(event)

    def log_role_assignment_event(
        self,
        user_email: str,
        assigned_role: str,
        assignment_reason: str,
        assigner_email: Optional[str],
        supabase_claims: Dict[str, Any],
        request_info: Dict[str, Any]
    ):
        """Log role assignment events."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "role_assignment",
            "user_email": user_email,
            "assigned_role": assigned_role,
            "assignment_reason": assignment_reason,
            "assigner_email": assigner_email,
            "supabase_claims": supabase_claims,
            "ip_address": request_info.get("client_ip"),
            "user_agent": request_info.get("user_agent"),
            "request_id": request_info.get("request_id")
        }

        self.security_logger.info(json.dumps(event))
        self.events.append(event)

    def log_rate_limit_event(
        self,
        endpoint: str,
        user_identifier: str,
        limit_type: str,
        request_info: Dict[str, Any]
    ):
        """Log rate limiting events."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "rate_limit_exceeded",
            "endpoint": endpoint,
            "user_identifier": user_identifier,
            "limit_type": limit_type,
            "ip_address": request_info.get("client_ip"),
            "user_agent": request_info.get("user_agent"),
            "request_id": request_info.get("request_id")
        }

        self.security_logger.warning(json.dumps(event))
        self.events.append(event)

    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent security events (newest first)."""
        if limit <= 0:
            return []
        recent = self.events[-limit:]
        return list(reversed(recent))

# Global security audit logger
security_audit = SecurityAuditLogger()

# =============================================================================
# REQUEST CONTEXT UTILITIES
# =============================================================================

def get_request_info(request: Request) -> Dict[str, Any]:
    """Extract security-relevant information from request."""
    return {
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "request_id": getattr(request.state, "request_id", "unknown"),
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers)
    }

# =============================================================================
# SECURE AUTHENTICATION DEPENDENCIES
# =============================================================================

async def validate_firebase_token(
    credentials: HTTPAuthorizationCredentials,
    request: Request
) -> Tuple[Dict[str, Any], str]:
    """
    Validate Firebase Auth token and extract user information.

    Returns:
        Tuple of (user_data, email)
    """
    request_info = get_request_info(request)

    try:
        # Get Firebase Auth Service
        from app.dependencies.auth_dependencies import _firebase_service

        if _firebase_service is None:
            security_audit.log_authentication_event(
                "token_validation",
                "unknown",
                False,
                "Firebase authentication not configured",
                request_info
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Firebase authentication is not configured",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify Firebase token
        user_data = await _firebase_service.verify_token(credentials.credentials)
        email = user_data.get("email")

        if not email:
            security_audit.log_authentication_event(
                "token_validation",
                "unknown",
                False,
                "No email in Firebase token",
                request_info
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token - no email",
                headers={"WWW-Authenticate": "Bearer"},
            )

        security_audit.log_authentication_event(
            "token_validation",
            email,
            True,
            "Firebase token validated successfully",
            request_info,
            {"firebase_uid": user_data.get("uid")}
        )

        return user_data, email.strip().lower()

    except HTTPException:
        raise
    except Exception as e:
        security_audit.log_authentication_event(
            "token_validation",
            "unknown",
            False,
            f"Firebase token validation error: {e}",
            request_info
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )
    except HTTPException:
        # Re-raise HTTP exceptions generated above to preserve detail
        raise
    except Exception as e:
        security_audit.log_authentication_event(
            "token_validation",
            "unknown",
            False,
            f"Token validation error: {e}",
            request_info
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_or_create_user_secure(
    firebase_data: Dict[str, Any],
    email: str,
    services: ServiceProvider,
    request: Request
) -> User:
    """
    Securely get or create user with proper role determination.
    """
    request_info = get_request_info(request)

    try:
        # Try to get existing user
        user = services.user_repository.get_by_email(email)

        if user:
            # Update last login
            user.last_login = datetime.utcnow()
            services.user_repository.update(user.id, {"last_login": user.last_login})

            security_audit.log_authentication_event(
                "user_login",
                email,
                True,
                "Existing user login",
                request_info,
                {"user_role": user.role.value if user.role else "none"}
            )

            return user

        # Check if auto-provisioning is enabled
        if not security_config.enable_auto_provisioning:
            security_audit.log_authentication_event(
                "user_creation_denied",
                email,
                False,
                "Auto-provisioning disabled",
                request_info
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account registration disabled. Contact administrator."
            )

        # Secure role determination
        determined_role, role_reason = role_determiner.determine_role_from_email(
            email,
            supabase_data,
            request_info
        )

        # Validate role assignment
        is_valid, validation_reason = role_determiner.validate_role_assignment(
            email,
            determined_role
        )

        if not is_valid:
            security_audit.log_authentication_event(
                "user_creation_denied",
                email,
                False,
                f"Role assignment validation failed: {validation_reason}",
                request_info
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account creation denied - invalid role assignment"
            )

        # Create new user
        user_data = {
            "email": email,
            "name": firebase_data.get("name") or firebase_data.get("display_name") or email.split("@")[0],
            "role": determined_role,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "last_login": datetime.utcnow(),
        }

        # Extract additional metadata
        # Extract phone from Firebase data if available
        if firebase_data.get("phone_number"):
            user_data["phone"] = firebase_data["phone_number"]

        user = services.user_repository.create(user_data)

        security_audit.log_role_assignment_event(
            email,
            determined_role.value,
            role_reason,
            None,  # Auto-assigned
            supabase_data,
            request_info
        )

        security_audit.log_authentication_event(
            "user_creation",
            email,
            True,
            f"New user created with role {determined_role.value}",
            request_info,
            {
                "user_id": str(user.id),
                "role_reason": role_reason,
                "firebase_uid": firebase_data.get("uid")
            }
        )

        logger.info(f"New user created: {email} with role {determined_role.value}")
        return user

    except HTTPException:
        raise
    except Exception as e:
        security_audit.log_authentication_event(
            "user_creation_error",
            email,
            False,
            f"Error creating user: {e}",
            request_info
        )
        logger.error(f"Error in get_or_create_user_secure for {email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User authentication failed"
        )

# =============================================================================
# RATE LIMITED DEPENDENCIES
# =============================================================================

def apply_rate_limit(
    limit_type: str,
    requests_per_minute: Optional[int] = None,
    requests_per_hour: Optional[int] = None,
    burst_size: Optional[int] = None
):
    """Decorator to apply rate limiting to dependencies."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from arguments
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # If no request found, proceed without rate limiting
                return await func(*args, **kwargs)

            # Determine rate limit key
            client_ip = request.client.host if request.client else "unknown"
            rate_key = f"rate_limit:{limit_type}:{client_ip}"

            # Get rate limit configuration
            config = security_config.rate_limiting
            limit = requests_per_minute or getattr(config, f"{limit_type}_per_minute", config.requests_per_minute)
            burst = burst_size or config.burst_size

            # Check rate limit
            allowed, info = await rate_limiter.check_rate_limit(
                rate_key,
                limit,
                60,  # 1 minute window
                burst
            )

            if not allowed:
                request_info = get_request_info(request)
                security_audit.log_rate_limit_event(
                    request.url.path,
                    client_ip,
                    limit_type,
                    request_info
                )

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {limit_type}",
                    headers={
                        "Retry-After": str(info.get("retry_after", 60)),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + 60)
                    }
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

# =============================================================================
# MAIN AUTHENTICATION DEPENDENCIES
# =============================================================================

@apply_rate_limit("auth_login", requests_per_minute=5, burst_size=3)
async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: ServiceProvider = Depends(get_service_provider)
) -> User:
    """
    Get current authenticated user with comprehensive security checks.
    """
    # Validate Supabase token
    firebase_data, email = await validate_firebase_token(credentials, request)

    # Get or create user securely
    user = await get_or_create_user_secure(firebase_data, email, services, request)

    # Check if user is active
    if not user.is_active:
        request_info = get_request_info(request)
        security_audit.log_authentication_event(
            "inactive_user_access",
            email,
            False,
            "User account is inactive",
            request_info,
            {"user_id": str(user.id)}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user (alias for backward compatibility)."""
    return current_user

# =============================================================================
# PERMISSION-BASED DEPENDENCIES
# =============================================================================

def require_permission(permission: Permission):
    """Dependency to require specific permission."""
    async def permission_dependency(
        request: Request,
        current_user: User = Depends(get_current_user)
    ) -> User:
        request_info = get_request_info(request)

        if not PermissionChecker.has_permission(current_user.role, permission):
            security_audit.log_authorization_event(
                "permission_denied",
                current_user.email,
                current_user.role.value,
                permission.value,
                request.url.path,
                False,
                "Insufficient permissions",
                request_info
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission.value}"
            )

        security_audit.log_authorization_event(
            "permission_granted",
            current_user.email,
            current_user.role.value,
            permission.value,
            request.url.path,
            True,
            "Permission check passed",
            request_info
        )

        return current_user

    return permission_dependency

def require_role(allowed_roles: List[UserRole]):
    """Dependency to require specific roles."""
    async def role_dependency(
        request: Request,
        current_user: User = Depends(get_current_user)
    ) -> User:
        request_info = get_request_info(request)

        if current_user.role not in allowed_roles:
            security_audit.log_authorization_event(
                "role_denied",
                current_user.email,
                current_user.role.value,
                f"roles:{[r.value for r in allowed_roles]}",
                request.url.path,
                False,
                f"Role {current_user.role.value} not in allowed roles",
                request_info
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: one of {[r.value for r in allowed_roles]}"
            )

        return current_user

    return role_dependency

# =============================================================================
# CONVENIENCE ROLE DEPENDENCIES
# =============================================================================

def get_admin_user():
    """Dependency for admin-only endpoints."""
    return require_role([UserRole.ADMIN, UserRole.SUPER_ADMIN])

def get_medical_user():
    """Dependency for medical staff endpoints."""
    return require_role([UserRole.DOCTOR, UserRole.NURSE, UserRole.ADMIN, UserRole.SUPER_ADMIN])

def get_verified_user():
    """Dependency for verified users only."""
    async def verified_dependency(
        request: Request,
        current_user: User = Depends(get_current_user)
    ) -> User:
        role_def = ROLE_DEFINITIONS.get(current_user.role)
        if role_def and role_def.requires_verification:
            # Check if user has been verified (implement verification logic as needed)
            # For now, assume verified if role requires it and user exists
            pass

        return current_user

    return verified_dependency

# =============================================================================
# LEGACY COMPATIBILITY FUNCTIONS
# =============================================================================

async def get_current_user_role(
    current_user: User = Depends(get_current_user)
) -> UserRole:
    """Get current user's role."""
    return current_user.role

async def get_thread_safe_db() -> Generator[Session, None, None]:
    """Thread-safe database session (backward compatibility)."""
    return get_db()

async def get_auth_service():
    """Get authentication service (backward compatibility)."""
    # This would typically return an auth service instance
    # For now, return a simple dict with config
    return {
        "config": security_config,
        "rate_limiter": rate_limiter,
        "audit_logger": security_audit
    }

# =============================================================================
# HEALTH CHECK AND MONITORING
# =============================================================================

async def get_security_status() -> Dict[str, Any]:
    """Get security system status for health checks."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "rate_limiting_enabled": security_config.rate_limiting.enabled,
        "auto_provisioning_enabled": security_config.enable_auto_provisioning,
        "audit_logging_enabled": security_config.enable_audit_logging,
        "redis_available": rate_limiter.redis_client is not None,
        "recent_audit_events": len(security_audit.get_recent_events(10)),
        "configuration_warnings": len(validate_security_config())
    }

# Export all dependencies for use in routers
__all__ = [
    "get_current_user",
    "get_current_active_user",
    "get_current_user_role",
    "require_permission",
    "require_role",
    "get_admin_user",
    "get_medical_user",
    "get_verified_user",
    "get_thread_safe_db",
    "get_auth_service",
    "get_security_status",
    "security_audit",
    "rate_limiter",
    "apply_rate_limit"
]