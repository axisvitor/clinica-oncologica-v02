"""Authentication Dependencies - Firebase Authentication + Redis Sessions

Dual authentication system:
1. Session-based auth (RECOMMENDED): Ultra-fast Redis sessions (~2-5ms)
2. Firebase token auth (DEPRECATED): Backward compatibility only

All Supabase fallback code has been removed.
"""
"""
MIGRATION STATUS: Phase 1 - Async Database Operations with Timeouts
- ✅ _get_user_from_db_async() - New async function with timeout support
- ✅ get_current_user_from_session() - Migrated to async DB with 5s timeout
- ✅ get_current_user() - Migrated to async DB with 5s timeout
- ⚠️  _get_user_from_db() - DEPRECATED, will be removed in Phase 2
- 🔜 Phase 2: Migrate other endpoints (user_repository, etc.)
- 🔜 Phase 3: Remove deprecated sync functions
"""

from fastapi import Depends, HTTPException, status, Header, Cookie, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, List, Any, TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import logging
import asyncio
import re

if TYPE_CHECKING:
    from app.core.redis_manager import FirebaseRedisCache

from app.models.user import User, UserRole
if TYPE_CHECKING:
    from app.services import ServiceProvider
from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# In-memory registry used by test fixtures to bypass Firebase validation.
# SECURITY: This registry is ONLY used when APP_ENABLE_DEBUG=True
# In production, test tokens are NEVER accepted

def _is_test_mode_enabled() -> bool:
    """Check if test/debug mode is enabled (NEVER in production)."""
    app_env = getattr(settings, "APP_ENVIRONMENT", "development").lower()
    debug_enabled = getattr(settings, "APP_ENABLE_DEBUG", False)
    # SECURITY: Never allow test tokens in production
    if app_env in ("production", "prod"):
        return False
    return debug_enabled

# SECURITY: Disable TEST_TOKEN_REGISTRY in production environments
_app_environment = getattr(settings, "APP_ENVIRONMENT", "development").lower()
if _app_environment in ("production", "prod"):
    logger.critical(
        "SECURITY NOTICE: TEST_TOKEN_REGISTRY is disabled in production. "
        "This authentication bypass mechanism must not exist in production deployments."
    )
    TEST_TOKEN_REGISTRY: Optional[Dict[str, User]] = None
else:
    # Only create registry in development/test environments
    TEST_TOKEN_REGISTRY = {} if _app_environment in ("development", "test", "dev", "testing") else None

security = HTTPBearer(auto_error=False)

# Initialize Firebase Auth Service if configured
_firebase_service = None
try:
    from app.services.firebase_auth_service import get_firebase_auth_service

    # Check if Firebase credentials are configured
    firebase_project_id = getattr(settings, "FIREBASE_ADMIN_PROJECT_ID", None)
    firebase_private_key = getattr(settings, "FIREBASE_ADMIN_PRIVATE_KEY", None)
    firebase_client_email = getattr(settings, "FIREBASE_ADMIN_CLIENT_EMAIL", None)

    if firebase_project_id and firebase_private_key and firebase_client_email:
        _firebase_service = get_firebase_auth_service(
            project_id=firebase_project_id,
            private_key=firebase_private_key,
            client_email=firebase_client_email,
        )
        logger.info("Firebase Authentication enabled")
    else:
        logger.error(
            "Firebase credentials not configured - authentication will not work"
        )
        _firebase_service = None
except Exception as e:
    logger.error(f"Failed to initialize Firebase Auth: {str(e)}")
    _firebase_service = None

# =============================================================================
# CORE AUTHENTICATION DEPENDENCIES
# =============================================================================

# Firebase UID validation patterns
_FIREBASE_UID_PATTERN = re.compile(r"^[A-Za-z0-9]{20,128}$")
_FIREBASE_UID_STRICT_PATTERN = re.compile(r"^[A-Za-z0-9]{28}$")

# Email validation pattern: basic RFC 5322 compliant pattern
_EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def _validate_email(email: str) -> None:
    """
    Validate email format.

    Args:
        email: The email address to validate

    Raises:
        HTTPException: If the email format is invalid
    """
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )

    if not isinstance(email, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email must be a string"
        )

    if len(email) > 254:  # RFC 5321
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email exceeds maximum length of 254 characters"
        )

    if not _EMAIL_PATTERN.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )


def _validate_firebase_uid(firebase_uid: str) -> None:
    """
    Validate Firebase UID format to prevent injection attacks (SECURITY CRITICAL).

    Firebase UIDs are typically 28 alphanumeric characters. Validation mode is
    controlled by ENABLE_STRICT_UID_VALIDATION for safe rollout.

    Args:
        firebase_uid: The Firebase UID to validate

    Raises:
        HTTPException: If the UID format is invalid
    """
    if not firebase_uid or not isinstance(firebase_uid, str):
        logger.error(
            "SECURITY: Invalid Firebase UID type or empty value (type=%s)",
            type(firebase_uid).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase UID (audit_id: firebase_uid_invalid)",
        )

    validation_mode = (
        "strict" if settings.ENABLE_STRICT_UID_VALIDATION else "relaxed"
    )
    pattern = (
        _FIREBASE_UID_STRICT_PATTERN
        if settings.ENABLE_STRICT_UID_VALIDATION
        else _FIREBASE_UID_PATTERN
    )

    if not pattern.match(firebase_uid):
        logger.error(
            "SECURITY: Invalid Firebase UID format (%s) uid_prefix=%s length=%s",
            validation_mode,
            firebase_uid[:8],
            len(firebase_uid),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase UID format (audit_id: firebase_uid_format)",
        )


def _resolve_user_role(
    firebase_custom_claims: Optional[Dict[str, Any]] = None,
    db_role: Optional[UserRole] = None,
    default_role: UserRole = UserRole.DOCTOR,
) -> UserRole:
    """
    Resolve user role from multiple sources with priority hierarchy.

    Priority:
    1. Firebase custom claims (role or roles field)
    2. Database role
    3. Default role (DOCTOR)

    Args:
        firebase_custom_claims: Custom claims from Firebase token
        db_role: Role from database User model
        default_role: Fallback role if no other source available

    Returns:
        Resolved UserRole enum value
    """
    claims = firebase_custom_claims or {}
    role_value = None

    if isinstance(claims, dict):
        if "role" in claims:
            role_value = claims.get("role")
        elif "roles" in claims:
            role_value = claims.get("roles")

    def _normalize_role(candidate: Any) -> Optional[UserRole]:
        if isinstance(candidate, UserRole):
            return candidate
        if isinstance(candidate, str):
            normalized = candidate.strip().lower()
            if not normalized:
                return None
            try:
                return UserRole(normalized)
            except ValueError:
                logger.warning(
                    "Invalid role '%s' in Firebase custom claims", candidate
                )
                return None
        return None

    if role_value is not None:
        if isinstance(role_value, (list, tuple, set)):
            for entry in role_value:
                resolved = _normalize_role(entry)
                if resolved:
                    logger.debug(
                        "Resolved role from Firebase custom claims: %s",
                        resolved.value,
                    )
                    return resolved
            logger.warning(
                "No valid roles found in Firebase custom claims list: %s", role_value
            )
        else:
            resolved = _normalize_role(role_value)
            if resolved:
                logger.debug(
                    "Resolved role from Firebase custom claims: %s",
                    resolved.value,
                )
                return resolved

    if db_role is not None:
        if isinstance(db_role, UserRole):
            logger.debug("Resolved role from database: %s", db_role.value)
            return db_role
        if isinstance(db_role, str):
            try:
                normalized_db_role = UserRole(db_role.lower())
                logger.debug(
                    "Resolved role from database: %s", normalized_db_role.value
                )
                return normalized_db_role
            except ValueError:
                logger.warning("Invalid database role '%s'", db_role)

    logger.debug("Defaulting role to: %s", default_role.value)
    return default_role


def user_to_cache_dict(user: User) -> Dict[str, Any]:
    """
    Convert User model to cacheable dictionary.

    Converts SQLAlchemy User model to a JSON-serializable dict suitable
    for Redis caching. Handles enum conversion, timestamp formatting,
    and field mapping.

    Args:
        user: User model instance from database

    Returns:
        Dict with serialized user data including:
        - id (str): UUID converted to string
        - firebase_uid (str): Firebase user identifier
        - email (str): User email address
        - full_name (str): User's full name
        - role (str): User role as string value
        - is_active (bool): Account active status
        - created_at (str|None): ISO formatted creation timestamp
        - updated_at (str|None): ISO formatted update timestamp
        - last_login (str|None): ISO formatted last login timestamp

    Example:
        >>> user = User(id=uuid4(), email="doc@example.com", role=UserRole.DOCTOR)
        >>> cache_dict = user_to_cache_dict(user)
        >>> cache_dict["role"]
        'doctor'
    """
    return {
        "id": str(user.id),
        "firebase_uid": user.firebase_uid,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login": user.firebase_last_sign_in.isoformat()
        if user.firebase_last_sign_in
        else None,
    }


def _get_service_provider():
    """Lazy loader for ServiceProvider to avoid circular imports."""
    from app.dependencies import get_thread_safe_service_provider

    # Yield from the actual generator function
    yield from get_thread_safe_service_provider()


def get_permissions_for_role(role: str) -> List[str]:
    """
    Get permissions list for user role.

    Args:
        role: User role (admin, doctor, etc.)

    Returns:
        List of permission strings
    """
    role = role.upper() if role else ""

    # Admin has all permissions (using dot notation for frontend compatibility)
    if role == "ADMIN":
        return [
            # Core admin permissions
            "admin.read",
            "admin.write",
            "admin.delete",
            "admin.templates.read",
            "admin.templates.write",
            # User management
            "users.read",
            "users.write",
            "users.delete",
            # Security and monitoring
            "security.read",
            "security.write",
            # Reports and analytics
            "reports.read",
            "reports.write",
            "reports.delete",
            "analytics.read",
            "analytics.write",
            # Settings and configuration
            "settings.read",
            "settings.write",
            # Clinical data
            "patients.read",
            "patients.write",
            "patients.delete",
            "appointments.read",
            "appointments.write",
            "appointments.delete",
            "treatments.read",
            "treatments.write",
            "treatments.delete",
            # Billing
            "billing.read",
            "billing.write",
        ]

    # Doctor has clinical permissions
    elif role == "DOCTOR":
        return [
            "patients.read",
            "patients.write",
            "appointments.read",
            "appointments.write",
            "treatments.read",
            "treatments.write",
            "reports.read",
            "reports.write",
        ]

    # Default: minimal read permissions
    return ["patients.read", "appointments.read"]


async def get_redis_cache() -> "FirebaseRedisCache":
    """
    Dependency injection for FirebaseRedisCache with Redis client.

    Returns:
        FirebaseRedisCache instance with initialized Redis client
    """
    try:
        from app.core.redis_manager import get_redis_manager, FirebaseRedisCache

        redis_manager = get_redis_manager()
        # Use sync client for FirebaseRedisCache as it mostly uses run_in_executor/to_thread
        redis_client = redis_manager.get_compatible_client("sync")
        return FirebaseRedisCache(redis_client)
    except Exception as e:
        import traceback
        import logging

        logger = logging.getLogger(__name__)
        logger.error(
            f"❌ Failed to initialize Redis cache dependency: {e}\n{traceback.format_exc()}"
        )
        raise


class GenericRedisCache:
    """Generic Redis cache wrapper with standard get/set interface for general caching needs."""

    def __init__(self, redis_client):
        self._client = redis_client

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value by key."""
        import json
        try:
            value = self._client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set cached value with TTL."""
        import json
        try:
            self._client.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """Delete cached value by key."""
        try:
            self._client.delete(key)
            return True
        except Exception:
            return False

    async def delete_pattern(self, pattern: str) -> bool:
        """Delete all keys matching pattern."""
        try:
            keys = self._client.keys(pattern)
            if keys:
                self._client.delete(*keys)
            return True
        except Exception:
            return False


async def get_generic_cache() -> GenericRedisCache:
    """
    Dependency injection for generic Redis cache with standard get/set interface.

    Returns:
        GenericRedisCache instance with initialized Redis client
    """
    try:
        from app.core.redis_manager import get_redis_manager

        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_sync_client()
        return GenericRedisCache(redis_client)
    except Exception as e:
        import traceback
        import logging

        logger = logging.getLogger(__name__)
        logger.error(
            f"❌ Failed to initialize generic Redis cache: {e}\n{traceback.format_exc()}"
        )
        raise


async def verify_firebase_token(id_token: str) -> Optional[Dict[str, Any]]:
    """
    Verify Firebase ID token and return user data.

    Args:
        id_token: Firebase ID token

    Returns:
        User data dict or None if invalid

    Raises:
        HTTPException: If token is invalid
    """
    if _firebase_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured",
        )

    try:
        user_data = await _firebase_service.verify_token(id_token)
        return user_data
    except Exception as e:
        logger.error(f"Firebase token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# DEPRECATED: Use _get_user_from_db_async() instead
# This function will be removed in Phase 2 of async migration
def _get_user_from_db(firebase_uid: str) -> Optional[User]:
    """
    Synchronous function to fetch a user from the database in a thread-safe manner.
    Creates its own database session to avoid sharing sessions across threads.
    """
    with SessionLocal() as db:
        from app.models.user import User
        from sqlalchemy import select

        stmt = select(User).where(User.firebase_uid == firebase_uid)
        result = db.execute(stmt)
        return result.scalar_one_or_none()


def _get_user_from_db_sync(firebase_uid: str, db: Session) -> Optional[User]:
    """Fetch a user using an existing synchronous session."""
    from sqlalchemy import select

    stmt = select(User).where(User.firebase_uid == firebase_uid)
    result = db.execute(stmt)
    return result.scalar_one_or_none()


def _should_use_sync_db(services: "ServiceProvider") -> bool:
    try:
        bind = services.db.get_bind()
    except Exception:
        return False
    return bind is not None and getattr(bind.dialect, "name", None) == "sqlite"


async def _get_user_from_db_async(
    firebase_uid: str, session: AsyncSession
) -> Optional[User]:
    """
    Async function to fetch user from database with retry on timeout.

    Args:
        firebase_uid: Firebase UID to search for
        session: AsyncSession instance

    Returns:
        User model or None if not found
    """
    from sqlalchemy import select

    stmt = select(User).where(User.firebase_uid == firebase_uid)

    try:
        result = await asyncio.wait_for(
            session.execute(stmt),
            timeout=settings.DB_QUERY_TIMEOUT_READ,
        )
        return result.scalar_one_or_none()
    except asyncio.TimeoutError:
        await session.rollback()
        logger.warning(
            "Database query timeout for UID %s..., retrying with longer timeout",
            firebase_uid[:8],
        )

        try:
            result = await asyncio.wait_for(
                session.execute(stmt),
                timeout=settings.DB_QUERY_TIMEOUT_READ * 2,
            )
            logger.info(
                "Database query succeeded on retry for UID %s...", firebase_uid[:8]
            )
            return result.scalar_one_or_none()
        except asyncio.TimeoutError:
            await session.rollback()
            logger.error(
                "Database query timeout after retry for UID %s...", firebase_uid[:8]
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Database query timeout after retry",
            )


async def _get_user_from_db_by_session(
    session_id: str, session: AsyncSession
) -> Optional[User]:
    """Fetch user from database by session ID (fallback path)."""
    from uuid import UUID
    from sqlalchemy import select
    from app.models.session import Session as SessionModel

    try:
        session_uuid = UUID(session_id)
    except (ValueError, TypeError):
        logger.warning("Invalid session ID format for fallback lookup")
        return None

    stmt = (
        select(User)
        .join(SessionModel, SessionModel.user_id == User.id)
        .where(SessionModel.id == session_uuid)
        .where(SessionModel.is_active.is_(True))
        .where(SessionModel.expires_at > datetime.now(timezone.utc))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_current_user_from_session(
    request: Request,
    session_cookie_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    authorization: Optional[str] = Header(None),
    redis_cache: "FirebaseRedisCache" = Depends(get_redis_cache),
) -> Dict:
    """
    Get current authenticated user by validating Redis session (RECOMMENDED).

    Ultra-fast authentication using Redis sessions with multi-layer caching:
    - Cache hit (Layer 1): ~2-5ms
    - Cache miss (Layer 2): ~50-100ms (PostgreSQL + cache write)

    Authentication flow:
    1. Validate session_id exists in Redis (Layer 1 cache)
    2. Get user data from Layer 2 cache (user:{uid})
    3. If cache miss: Query PostgreSQL and repopulate cache
    4. Validate user is_active
    5. Return user dict with permissions
    
    Session ID priority (default):
    1. Cookie (httpOnly)
    2. X-Session-ID header
    3. Authorization Bearer (fallback)

    Args:
        request: FastAPI request object
        session_cookie_id: Session ID from session_id cookie
        x_session_id: Session ID from X-Session-ID header
        authorization: Bearer token from Authorization header
        redis_cache: Redis cache instance (injected)

    Returns:
        User dict with permissions

    Raises:
        HTTPException 401: Invalid or expired session
        HTTPException 403: User account is inactive
    """
    try:
        final_session_id = None
        
        # DEBUG: Log what we received
        logger.debug(
            f"Auth check - cookie: {session_cookie_id[:8] if session_cookie_id else 'None'}..., "
            f"x_session_id: {x_session_id[:8] if x_session_id else 'None'}..., "
            f"auth_header: {'Bearer' if authorization and authorization.startswith('Bearer') else 'None'}"
        )

        session_source = None

        if settings.ENABLE_COOKIE_PRIORITY:
            # Priority 1: Cookie (httpOnly) - most secure for HTTP
            if session_cookie_id:
                final_session_id = session_cookie_id
                session_source = "cookie"
                logger.debug("Session ID from cookie (httpOnly)")
            # Priority 2: X-Session-ID header - needed for WebSocket
            elif x_session_id:
                final_session_id = x_session_id
                session_source = "x-session-id"
                logger.debug("Session ID from X-Session-ID header")
            # Priority 3: Authorization Bearer - fallback
            elif authorization and authorization.startswith("Bearer "):
                final_session_id = authorization.split(" ")[1]
                session_source = "authorization"
                logger.debug("Session ID from Authorization Bearer (fallback)")
        else:
            # Legacy priority: Authorization -> Header -> Cookie
            if authorization and authorization.startswith("Bearer "):
                final_session_id = authorization.split(" ")[1]
                session_source = "authorization"
                logger.debug("Session ID from Authorization Bearer")
            elif x_session_id:
                final_session_id = x_session_id
                session_source = "x-session-id"
                logger.debug("Session ID from X-Session-ID header")
            elif session_cookie_id:
                final_session_id = session_cookie_id
                session_source = "cookie"
                logger.debug("Session ID from cookie (httpOnly)")

        if final_session_id:
            logger.debug("Session ID resolved from %s", session_source)

        if not final_session_id:
            logger.warning("No session ID provided in any auth method (cookie, header, or Authorization)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session ID not provided",
                headers={"WWW-Authenticate": "Session"},
            )

        # Layer 1: Get session from Redis with timeout (~2-5ms)
        session_data = None
        use_fallback = False
        try:
            session_data = await asyncio.wait_for(
                redis_cache.get_session(final_session_id),
                timeout=settings.REDIS_OPERATION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Redis timeout for session %s..., falling back to PostgreSQL",
                final_session_id[:8],
            )
            use_fallback = True
        except Exception as e:
            logger.error(
                "Redis error for session %s...: %s. Falling back to PostgreSQL",
                final_session_id[:8],
                str(e),
            )
            use_fallback = True

        if use_fallback:
            try:
                from app.database import get_async_session_factory

                async_session_factory = get_async_session_factory()
                async with async_session_factory() as async_session:
                    try:
                        fallback_user = await asyncio.wait_for(
                            _get_user_from_db_by_session(final_session_id, async_session),
                            timeout=settings.DB_QUERY_TIMEOUT_READ,
                        )
                    except Exception:
                        await async_session.rollback()
                        raise
            except asyncio.TimeoutError:
                logger.error(
                    "Database timeout during fallback for session %s...",
                    final_session_id[:8],
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database temporarily unavailable. Please try again.",
                )
            except Exception as e:
                logger.error(
                    "Database error during fallback for session %s...: %s",
                    final_session_id[:8],
                    str(e),
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database temporarily unavailable. Please try again.",
                )

            if not fallback_user:
                logger.warning(
                    "Invalid or expired session during fallback: %s...",
                    final_session_id[:8],
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired session. Please login again.",
                    headers={"WWW-Authenticate": "Session"},
                )

            user_data = user_to_cache_dict(fallback_user)
            if not user_data.get("is_active", False):
                logger.warning(
                    "Inactive user attempted access (fallback): %s",
                    user_data.get("email"),
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

            firebase_uid = user_data.get("firebase_uid")
            user_id = user_data.get("id")
            if firebase_uid and user_id:
                user_cache_ttl = 900
                session_ttl = (
                    getattr(settings, "SESSION_TTL_SECONDS", None)
                    or getattr(settings, "FIREBASE_SESSION_TTL_SECONDS", None)
                    or getattr(redis_cache, "session_ttl", 86400)
                )
                try:
                    await asyncio.wait_for(
                        redis_cache.cache_user_data(
                            firebase_uid, user_data, ttl=user_cache_ttl
                        ),
                        timeout=settings.REDIS_OPERATION_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Redis timeout rehydrating user cache for fallback session %s...",
                        final_session_id[:8],
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to rehydrate user cache for fallback session %s...: %s",
                        final_session_id[:8],
                        str(e),
                    )

                try:
                    created = await asyncio.wait_for(
                        redis_cache.create_session(
                            session_id=final_session_id,
                            user_id=user_id,
                            firebase_uid=firebase_uid,
                            ttl=session_ttl,
                        ),
                        timeout=settings.REDIS_OPERATION_TIMEOUT,
                    )
                    if not created:
                        logger.warning(
                            "Failed to rehydrate session cache for fallback session %s...",
                            final_session_id[:8],
                        )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Redis timeout rehydrating session cache for fallback session %s...",
                        final_session_id[:8],
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to rehydrate session cache for fallback session %s...: %s",
                        final_session_id[:8],
                        str(e),
                    )

                try:
                    await asyncio.wait_for(
                        redis_cache.update_session_activity(
                            session_id=final_session_id,
                            extend_ttl=True,
                            custom_ttl=session_ttl,
                        ),
                        timeout=settings.REDIS_OPERATION_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Redis timeout extending session TTL for fallback session %s...",
                        final_session_id[:8],
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to extend session TTL for fallback session %s...: %s",
                        final_session_id[:8],
                        str(e),
                    )

            role = user_data.get("role", "doctor")
            user_data["permissions"] = get_permissions_for_role(role)

            request.state.user_id = user_data.get("id")
            request.state.user_role = user_data.get("role")

            logger.debug(
                "Session validated via PostgreSQL fallback for user: %s (role: %s)",
                user_data.get("email"),
                role,
            )
            return user_data

        if not session_data:
            logger.warning(f"Invalid or expired session: {final_session_id[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session. Please login again.",
                headers={"WWW-Authenticate": "Session"},
            )

        # Update session activity to prevent expiration during active use
        # This extends the TTL and updates last_activity timestamp
        try:
            await asyncio.wait_for(
                redis_cache.update_session_activity(
                    session_id=final_session_id,
                    extend_ttl=True,  # Reset Redis TTL to keep active users logged in
                ),
                timeout=settings.REDIS_OPERATION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Redis timeout updating session activity for %s... (non-critical, continuing)",
                final_session_id[:8],
            )
        except Exception as e:
            logger.warning(
                "Failed to update session activity for %s...: %s (non-critical, continuing)",
                final_session_id[:8],
                str(e),
            )

        firebase_uid = session_data.get("firebase_uid")
        if not firebase_uid:
            logger.error(f"Session missing firebase_uid: {final_session_id[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session data",
                headers={"WWW-Authenticate": "Session"},
            )

        # SECURITY CRITICAL: Validate Firebase UID BEFORE any cache/DB operation
        # This prevents session hijacking if Redis is compromised
        # Malformed UIDs could be used for cache poisoning or SQL injection
        _validate_firebase_uid(firebase_uid)

        # Layer 2: Get user from cache (~2-5ms on hit, ~50-100ms on miss)
        # UID already validated above before any cache/DB access
        try:
            user_data = await asyncio.wait_for(
                redis_cache.get_user_by_uid(firebase_uid),
                timeout=settings.REDIS_OPERATION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Redis operation timeout after {settings.REDIS_OPERATION_TIMEOUT}s"
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="User cache lookup timed out. Please try again.",
            )

        if not user_data:
            # Cache miss: Query PostgreSQL with timeout protection
            logger.info(
                f"Cache miss for user: {firebase_uid[:8]}... Querying database with {settings.DB_QUERY_TIMEOUT_READ}s timeout."
            )

            try:
                # Get async session
                from app.database import get_async_session_factory

                async_session_factory = get_async_session_factory()
                async with async_session_factory() as async_session:
                    try:
                        user = await _get_user_from_db_async(
                            firebase_uid, async_session
                        )
                    except Exception:
                        await async_session.rollback()
                        raise
            except asyncio.CancelledError:
                logger.warning(
                    f"Database query cancelled for firebase_uid={firebase_uid[:8]}..."
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database temporarily unavailable. Please try again.",
                )
            except Exception as e:
                logger.error(
                    f"Database error for firebase_uid={firebase_uid[:8]}...: {e}"
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database temporarily unavailable. Please try again.",
                )

            if not user:
                logger.error(f"User not found in database: {firebase_uid[:8]}...")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Session"},
                )

            # Convert SQLAlchemy model to dict and cache
            user_data = user_to_cache_dict(user)

            # Cache for 15 minutes
            try:
                await asyncio.wait_for(
                    redis_cache.cache_user_data(firebase_uid, user_data, ttl=900),
                    timeout=settings.REDIS_OPERATION_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Redis operation timeout after {settings.REDIS_OPERATION_TIMEOUT}s"
                )
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="User cache write timed out. Please try again.",
                )
            logger.debug(f"Cached user data for: {firebase_uid[:8]}...")

        # Validate user is active
        if not user_data.get("is_active", False):
            logger.warning(f"Inactive user attempted access: {user_data.get('email')}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
            )

        # Add permissions to user data
        role = user_data.get("role", "doctor")
        user_data["permissions"] = get_permissions_for_role(role)

        # Set request state for middleware access (LGPD, Audit, etc.)
        request.state.user_id = user_data.get("id")
        request.state.user_role = user_data.get("role")

        logger.debug(
            f"Session validated for user: {user_data.get('email')} (role: {role})"
        )
        return user_data

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Session validation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Session validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Session"},
        )


async def get_current_user_object_from_session(
    user_data: Dict = Depends(get_current_user_from_session),
) -> User:
    """
    Get current authenticated user as a User model object from session.

    Useful for endpoints that require a User object (like upload.py)
    but need to support session-based authentication.
    """
    try:
        # Create a copy to avoid modifying the cached dict
        user_dict = user_data.copy()

        # Remove non-model fields or mismatched keys
        user_dict.pop("permissions", None)
        user_dict.pop("cached_at", None)

        # Map 'last_login' back to 'firebase_last_sign_in' if it exists
        if "last_login" in user_dict:
            last_login = user_dict.pop("last_login")
            if last_login and not user_dict.get("firebase_last_sign_in"):
                 user_dict["firebase_last_sign_in"] = last_login

        # Convert timestamps from string to datetime if necessary
        for ts_field in ["created_at", "updated_at", "firebase_last_sign_in"]:
            if user_dict.get(ts_field) and isinstance(user_dict[ts_field], str):
                try:
                    user_dict[ts_field] = datetime.fromisoformat(user_dict[ts_field])
                except ValueError:
                    pass # Keep as is or set to None

        # Handle role conversion
        role_value = user_dict.get("role")
        if isinstance(role_value, str):
            try:
                user_dict["role"] = UserRole(role_value.lower())
            except ValueError:
                logger.warning(f"Invalid role '{role_value}', defaulting to DOCTOR")
                user_dict["role"] = UserRole.DOCTOR
        elif not isinstance(role_value, UserRole):
            user_dict["role"] = UserRole.DOCTOR

        # Filter keys to match User model columns to prevent TypeError
        # This is CRITICAL because the cached user_dict might contain legacy keys
        # or keys from other contexts (like Firebase claims) that aren't in the model.
        from sqlalchemy import inspect
        mapper = inspect(User)
        allowed_keys = set(mapper.columns.keys())
        
        # Keep only keys that exist in the User model
        filtered_user_dict = {
            k: v for k, v in user_dict.items() 
            if k in allowed_keys
        }

        return User(**filtered_user_dict)
    except Exception as e:
        logger.error(f"Failed to convert session data to User object: {e}")
        # Log the keys that caused the issue for debugging
        try:
            logger.error(f"User dict keys: {list(user_data.keys())}")
        except:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session data error - please try logging out and back in",
        )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: "ServiceProvider" = Depends(_get_service_provider),
) -> User:
    """
    Get current authenticated user by validating Firebase Auth token with Redis cache.

    PERFORMANCE OPTIMIZED: Now uses 3-layer Redis cache for 40-90x speedup.
    DEPRECATED: Prefer get_current_user_from_session() for session-based auth.

    Authentication flow with Redis cache (3 layers):
    1. Layer 1 (Token Cache): Check if token is cached (~5ms hit, ~200ms miss)
    2. Layer 2 (User Cache): Check if user is cached (~5ms hit, ~100ms miss)
    3. Layer 3 (Session): Not used in Bearer token flow

    Performance comparison:
    - Cache hit (Layer 1+2): ~5ms (90x faster than cold request)
    - Cache hit (Layer 1 only): ~105ms (2x faster, skip Firebase validation)
    - Cache miss (cold): ~250ms (Firebase + PostgreSQL + cache write)

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer token from Authorization header
        services: Service provider with Redis and DB access

    Returns:
        Authenticated User model

    Raises:
        HTTPException 401: Invalid token or user not found
        HTTPException 403: User account is inactive
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    # Type guard: Ensure credentials is actually HTTPAuthorizationCredentials
    # This can fail if FastAPI dependency injection order is confused
    if not hasattr(credentials, 'credentials'):
        logger.error(f"get_current_user received wrong type: {type(credentials).__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    token_value = credentials.credentials

    allow_test_tokens = (
        getattr(settings, "APP_ENABLE_DEBUG", False)
        and getattr(settings, "APP_ENVIRONMENT", "development").lower() != "production"
    )

    # Check test token registry (only exists in non-production environments)
    cached_local = None
    if allow_test_tokens and TEST_TOKEN_REGISTRY is not None:
        cached_local = TEST_TOKEN_REGISTRY.get(token_value)
    if cached_local:
        return cached_local

    # Fast-path for local/testing tokens used by contract tests
    if allow_test_tokens and TEST_TOKEN_REGISTRY is not None and token_value.startswith(("admin_token_", "test_token_")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unregistered test token. Use TEST_TOKEN_REGISTRY in tests.",
        )

    # Check if Firebase is configured
    if _firebase_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured",
        )

    try:
        # Initialize 3-layer Redis cache
        from app.core.redis_manager import FirebaseRedisCache, get_redis_manager

        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_compatible_client("sync")
        firebase_cache = FirebaseRedisCache(redis_client)

        # === LAYER 1: TOKEN VALIDATION CACHE (5ms on hit, 200ms on miss) ===
        cached_token = firebase_cache.get_cached_token(token_value)

        if cached_token:
            logger.debug(f"✅ Token cache HIT for {cached_token.get('email')}")
            firebase_uid = cached_token["firebase_uid"]

            # SECURITY CRITICAL: Validate Firebase UID BEFORE any cache/DB operation
            # This prevents session hijacking if Redis is compromised
            # Malformed UIDs could be used for cache poisoning or SQL injection
            _validate_firebase_uid(firebase_uid)

            user_data = cached_token  # Temporary: will be replaced by Layer 2
        else:
            # MISS: Validate with Firebase Admin SDK (200ms)
            logger.debug("❌ Token cache MISS - validating with Firebase")
            user_data = await _firebase_service.verify_token(token_value)
            firebase_uid = user_data["uid"]

            # SECURITY CRITICAL: Validate Firebase UID BEFORE any cache/DB operation
            # This prevents session hijacking if Redis is compromised
            # Malformed UIDs could be used for cache poisoning or SQL injection
            _validate_firebase_uid(firebase_uid)

            # Cache validated token (1 hour TTL)
            firebase_cache.cache_validated_token(token_value, user_data)
            logger.info(f"💾 Token cached for {user_data.get('email')}")

        # === LAYER 2: USER OBJECT CACHE (5ms on hit, 100ms on miss) ===
        cached_user = firebase_cache.get_cached_user(firebase_uid)

        if cached_user:
            logger.debug(f"✅ User cache HIT for {firebase_uid}")
            # Convert dict to User model
            # FIX: Remove 'cached_at' before creating User model to prevent TypeError
            cached_user.pop("cached_at", None)
            role_value = cached_user.get("role")
            if isinstance(role_value, str):
                normalized_role = role_value.lower()
                try:
                    cached_user["role"] = UserRole(normalized_role)
                except ValueError:
                    logger.warning(
                        "Unexpected cached user role '%s'. Falling back to doctor role.",
                        role_value,
                    )
                    cached_user["role"] = UserRole.DOCTOR
            user = User(**cached_user)
            # Set request state for middleware access
            request.state.user_id = str(user.id)
            request.state.user_role = user.role.value if hasattr(user.role, "value") else str(user.role)
            return user

        # MISS: Query PostgreSQL with timeout protection (100ms)
        logger.debug(
            f"❌ User cache MISS - querying PostgreSQL for {firebase_uid} with {settings.DB_QUERY_TIMEOUT_READ}s timeout"
        )

        try:
            if _should_use_sync_db(services):
                user = _get_user_from_db_sync(firebase_uid, services.db)
            else:
                # Get async session
                from app.database import get_async_session_factory

                async_session_factory = get_async_session_factory()
                async with async_session_factory() as async_session:
                    try:
                        user = await _get_user_from_db_async(
                            firebase_uid, async_session
                        )
                    except Exception:
                        await async_session.rollback()
                        raise
        except asyncio.CancelledError:
            logger.warning(
                f"Database query cancelled for firebase_uid={firebase_uid[:8]}..."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable. Please try again.",
            )
        except Exception as e:
            logger.error(
                f"Database error for firebase_uid={firebase_uid[:8]}...: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable. Please try again.",
            )

        if user:
            # User exists - cache and return
            logger.debug(f"User found in database: {user.email}")

            # Cache user for 2 hours
            user_dict = user_to_cache_dict(user)
            firebase_cache.cache_user(firebase_uid, user_dict)
            logger.info(f"💾 User cached for {firebase_uid}")

            # Check if user is active
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

            # Set request state for middleware access
            request.state.user_id = str(user.id)
            request.state.user_role = user.role.value if hasattr(user.role, "value") else str(user.role)

            return user

        # User doesn't exist - create minimal record
        logger.info(
            f"User not found in database, creating minimal record for: {user_data.get('email')}"
        )

        # Validate email format
        email = user_data.get("email")
        if email:
            _validate_email(email)

        # Extract role from Firebase custom claims or default to DOCTOR
        firebase_custom_claims = user_data.get("custom_claims", {})
        user_role = _resolve_user_role(
            firebase_custom_claims=firebase_custom_claims,
            db_role=None,
            default_role=UserRole.DOCTOR,
        )

        user = User(
            firebase_uid=firebase_uid,
            email=email,
            full_name=user_data.get("name", email.split("@")[0] if email else "Unknown"),
            is_active=True,
            role=user_role,  # From Firebase custom claims
        )
        try:
            bind = services.db.get_bind()
            if bind and getattr(bind.dialect, "name", None) == "postgresql":
                services.db.execute(
                    text("SET LOCAL statement_timeout = :timeout_ms"),
                    {"timeout_ms": settings.DB_QUERY_TIMEOUT_WRITE * 1000},
                )
            services.db.add(user)
            services.db.commit()
            services.db.refresh(user)
        except DBAPIError as exc:
            services.db.rollback()
            if "statement timeout" in str(exc).lower():
                logger.error(
                    f"Database write timeout after {settings.DB_QUERY_TIMEOUT_WRITE}s for firebase_uid={firebase_uid[:8]}..."
                )
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=f"Database operation timed out after {settings.DB_QUERY_TIMEOUT_WRITE}s. Please try again.",
                )
            raise
        except Exception:
            services.db.rollback()
            raise

        # Cache new user
        user_dict = user_to_cache_dict(user)
        firebase_cache.cache_user(firebase_uid, user_dict)

        logger.info(f"✅ New user created and cached: {user.email}")

        # Set request state for middleware access
        request.state.user_id = str(user.id)
        request.state.user_role = user.role.value if hasattr(user.role, "value") else str(user.role)

        return user

    except HTTPException:
        # Re-raise HTTP exceptions (inactive user, etc.)
        raise
    except Exception as e:
        # Firebase authentication failed
        logger.error(f"Firebase authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firebase authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user (additional validation)"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    services: "ServiceProvider" = Depends(_get_service_provider),
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    if credentials is None:
        return None

    try:
        return await get_current_user(
            request=request,
            credentials=credentials,
            services=services,
        )
    except HTTPException:
        return None


# =============================================================================
# ROLE-BASED DEPENDENCIES
# =============================================================================


async def get_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Get current user with admin privileges"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user


async def get_doctor_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Get current user with doctor privileges"""
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user


# =============================================================================
# WEBSOCKET AUTHENTICATION
# =============================================================================


async def get_current_user_websocket(
    websocket, services: "ServiceProvider" = Depends(_get_service_provider)
) -> Optional[User]:
    """Get current user from WebSocket connection validating Firebase token only"""
    try:
        # Check if Firebase is configured
        if _firebase_service is None:
            logger.error("Firebase authentication not configured for WebSocket")
            return None

        # Get token from query parameters or headers
        token = None
        if hasattr(websocket, "query_params") and "token" in websocket.query_params:
            token = websocket.query_params["token"]
        elif hasattr(websocket, "headers"):
            auth_header = None
            try:
                auth_header = websocket.headers.get("authorization")
            except Exception:
                if "authorization" in getattr(websocket, "headers", {}):
                    auth_header = websocket.headers["authorization"]
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            return None

        # Verify Firebase token
        user_data = await _firebase_service.verify_token(token)
        email = user_data.get("email")

        if not email:
            return None

        # Get user from database
        user = services.user_repository.get_by_email(email.strip().lower())
        if user is None or not user.is_active:
            return None

        return user

    except Exception as e:
        logger.error(f"WebSocket authentication failed: {str(e)}")
        return None


async def get_current_active_admin(
    current_user: Dict = Depends(get_current_user_from_session),
) -> Dict:
    """
    Get current active admin user from session.

    Validates that the session belongs to an active user with ADMIN role.
    """
    role = current_user.get("role", "").upper()
    if role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user
