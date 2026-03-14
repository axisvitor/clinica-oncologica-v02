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
- 🔜 Phase 2: Migrate other endpoints (user_repository, etc.)
- 🔜 Phase 3: Remove deprecated sync functions
"""

from fastapi import Depends, HTTPException, status, Header, Cookie, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, List, Any, TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import importlib
import logging
import asyncio
import inspect
import re

if TYPE_CHECKING:
    from app.core.redis_manager import FirebaseRedisCache

from app.models.user import User, UserRole
if TYPE_CHECKING:
    from app.service_provider import ServiceProvider
from app.config import settings
from app.utils.timezone import now_sao_paulo

from . import (
    auth_role_dependencies,
    auth_session_contract,
    auth_user_adapter,
)

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

_legacy_auth_module = None
_firebase_service = None
_firebase_service_initialized = False


def _get_auth_legacy_firebase():
    """Import the legacy Firebase compatibility seam only when a legacy path needs it."""
    global _legacy_auth_module
    if _legacy_auth_module is None:
        _legacy_auth_module = importlib.import_module("app.dependencies.auth_legacy_firebase")
    return _legacy_auth_module


def _get_firebase_service():
    """Lazily initialize the optional Firebase Admin service for legacy compatibility."""
    global _firebase_service, _firebase_service_initialized
    if not _firebase_service_initialized:
        _firebase_service = _get_auth_legacy_firebase().initialize_firebase_service(
            settings_obj=settings
        )
        _firebase_service_initialized = True
    return _firebase_service

# =============================================================================
# CORE AUTHENTICATION DEPENDENCIES
# =============================================================================

# Firebase UID validation pattern (definitive contract)
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

    Definitive contract: Firebase UID must be exactly 28 alphanumeric characters.

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

    if _FIREBASE_UID_STRICT_PATTERN.match(firebase_uid):
        return

    logger.error(
        "SECURITY: Invalid Firebase UID format (strict) uid_prefix=%s length=%s",
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
    """Resolve user role via the extracted auth user adapter seam."""
    return auth_user_adapter.resolve_user_role(
        firebase_custom_claims=firebase_custom_claims,
        db_role=db_role,
        default_role=default_role,
    )


def user_to_cache_dict(user: User) -> Dict[str, Any]:
    """Convert ``User`` models via the extracted auth user adapter seam."""
    return auth_user_adapter.user_to_cache_dict(user)


async def _get_service_provider():
    """Lazy loader for ServiceProvider to avoid circular imports."""
    from app.dependencies import get_thread_safe_service_provider

    provider_stream = get_thread_safe_service_provider()
    if inspect.isasyncgen(provider_stream):
        async for provider in provider_stream:
            yield provider
    else:
        for provider in provider_stream:
            yield provider


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


class RedisAuthCacheAdapter:
    """
    Bridge object that preserves FirebaseRedisCache behavior while delegating
    critical auth lookups to RedisManager methods.

    This keeps legacy patch points used by tests that mock
    RedisManager.get_session/get_user_by_uid.
    """

    def __init__(self, redis_manager, firebase_cache):
        self._redis_manager = redis_manager
        self._firebase_cache = firebase_cache
        self.session_ttl = getattr(firebase_cache, "session_ttl", 86400)

    async def get_session(self, session_id: str):
        return await self._redis_manager.get_session(session_id)

    async def get_user_by_uid(self, firebase_uid: str):
        return await self._redis_manager.get_user_by_uid(firebase_uid)

    async def get_user_by_id(self, user_id: str):
        return await self._redis_manager.get_user_by_id(user_id)

    async def create_session(self, *args, **kwargs):
        return await self._redis_manager.create_session(*args, **kwargs)

    async def cache_user_data(self, *args, **kwargs):
        return await self._redis_manager.cache_user_data(*args, **kwargs)

    async def cache_user_data_by_user_id(self, *args, **kwargs):
        return await self._redis_manager.cache_user_data_by_user_id(*args, **kwargs)

    async def update_session_activity(self, *args, **kwargs):
        return await self._redis_manager.update_session_activity(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._firebase_cache, item)


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
        firebase_cache = FirebaseRedisCache(redis_client)
        return RedisAuthCacheAdapter(redis_manager, firebase_cache)
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
            batch = []
            for key in self._client.scan_iter(match=pattern, count=100):
                batch.append(key)
                if len(batch) >= 100:
                    try:
                        self._client.delete(*batch)
                    except TypeError:
                        for batch_key in batch:
                            self._client.delete(batch_key)
                    batch.clear()
            if batch:
                try:
                    self._client.delete(*batch)
                except TypeError:
                    for batch_key in batch:
                        self._client.delete(batch_key)
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


def _get_user_from_db_sync(firebase_uid: str, db: Session) -> Optional[User]:
    """Fetch a user using an existing synchronous session."""
    from sqlalchemy import select

    stmt = select(User).where(User.firebase_uid == firebase_uid)
    result = db.execute(stmt)
    return result.scalar_one_or_none()


def _should_use_sync_db(services: "ServiceProvider") -> bool:
    db = getattr(services, "db", None)
    if db is None:
        return False
    if isinstance(db, AsyncSession):
        return False
    if isinstance(db, Session):
        return True

    try:
        bind = db.get_bind()
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

    if not session_id or not isinstance(session_id, str):
        logger.warning("Invalid session ID value for fallback lookup")
        return None

    base_stmt = (
        select(User)
        .join(SessionModel, SessionModel.user_id == User.id)
        .where(SessionModel.is_active.is_(True))
        .where(SessionModel.revoked_at.is_(None))
        .where(SessionModel.expires_at > now_sao_paulo())
    )

    try:
        session_uuid = UUID(session_id)
        stmt = base_stmt.where(SessionModel.id == session_uuid)
    except (ValueError, TypeError):
        # Compatibility path for legacy callers that still pass session_token.
        stmt = base_stmt.where(SessionModel.session_token == session_id)

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

    Happy path accepts canonical session payloads keyed by user_id and only falls
    back to firebase_uid compatibility when the canonical payload is incomplete.
    """
    from uuid import UUID

    async def _load_user_from_db_by_user_id(user_id_value: str) -> Optional[User]:
        try:
            user_uuid = UUID(str(user_id_value))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session data",
                headers={"WWW-Authenticate": "Session"},
            )

        from sqlalchemy import select
        from app.database import get_async_session_factory

        async_session_factory = get_async_session_factory()
        async with async_session_factory() as async_session:
            try:
                result = await asyncio.wait_for(
                    async_session.execute(select(User).where(User.id == user_uuid)),
                    timeout=settings.DB_QUERY_TIMEOUT_READ,
                )
                return result.scalar_one_or_none()
            except Exception:
                await async_session.rollback()
                raise

    async def _load_user_from_db_by_firebase_uid(firebase_uid: str) -> Optional[User]:
        from app.database import get_async_session_factory

        async_session_factory = get_async_session_factory()
        async with async_session_factory() as async_session:
            try:
                return await _get_user_from_db_async(firebase_uid, async_session)
            except Exception:
                await async_session.rollback()
                raise

    async def _load_user_from_db_by_session_id(session_id: str) -> Optional[User]:
        from app.database import get_async_session_factory

        async_session_factory = get_async_session_factory()
        async with async_session_factory() as async_session:
            try:
                return await asyncio.wait_for(
                    _get_user_from_db_by_session(session_id, async_session),
                    timeout=settings.DB_QUERY_TIMEOUT_READ,
                )
            except Exception:
                await async_session.rollback()
                raise

    return await auth_session_contract.resolve_authenticated_session_user(
        request=request,
        session_cookie_id=session_cookie_id,
        x_session_id=x_session_id,
        authorization=authorization,
        redis_cache=redis_cache,
        get_permissions_for_role=get_permissions_for_role,
        validate_firebase_uid=_validate_firebase_uid,
        load_user_from_db_by_user_id=_load_user_from_db_by_user_id,
        load_user_from_db_by_firebase_uid=_load_user_from_db_by_firebase_uid,
        load_user_from_db_by_session=_load_user_from_db_by_session_id,
        serialize_user=user_to_cache_dict,
    )


async def get_current_user_object_from_session(
    user_data: Dict = Depends(get_current_user_from_session),
) -> User:
    """
    Get current authenticated user as a User model object from session.

    Useful for endpoints that require a User object (like upload.py)
    but need to support session-based authentication.
    """
    return auth_user_adapter.session_user_data_to_user(user_data)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: "ServiceProvider" = Depends(_get_service_provider),
) -> User:
    """Resolve the current user via session-first auth with legacy bearer fallback."""
    request_cookies = getattr(request, "cookies", {}) or {}
    request_headers = getattr(request, "headers", {}) or {}
    session_cookie_id = None
    x_session_id = None
    authorization_header = None

    try:
        session_cookie_id = request_cookies.get(settings.SESSION_COOKIE_NAME)
    except Exception:
        session_cookie_id = None

    try:
        x_session_id = request_headers.get("X-Session-ID")
        authorization_header = request_headers.get("Authorization")
    except Exception:
        x_session_id = None
        authorization_header = None

    if session_cookie_id or x_session_id:
        session_user_data = await get_current_user_from_session(
            request=request,
            session_cookie_id=session_cookie_id,
            x_session_id=x_session_id,
            authorization=authorization_header,
        )
        request.state.user_id = session_user_data.get("id") or session_user_data.get(
            "user_id"
        )
        request.state.user_role = session_user_data.get("role")
        return await get_current_user_object_from_session(session_user_data)

    legacy_auth = _get_auth_legacy_firebase()
    return await legacy_auth.authenticate_legacy_bearer_user(
        request=request,
        credentials=credentials,
        services=services,
        firebase_service=_get_firebase_service(),
        validate_firebase_uid=_validate_firebase_uid,
        validate_email=_validate_email,
        resolve_user_role=_resolve_user_role,
        should_use_sync_db=_should_use_sync_db,
        get_user_from_db_sync=_get_user_from_db_sync,
        get_user_from_db_async=_get_user_from_db_async,
        serialize_user=user_to_cache_dict,
    )


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user (additional validation)."""
    return await auth_role_dependencies.require_active_user(current_user)


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
    """Get current user with admin privileges."""
    return await auth_role_dependencies.require_admin_user(current_user)


async def get_current_active_admin(
    current_user: Dict = Depends(get_current_user_from_session),
) -> Dict:
    """Get current active admin user from session."""
    return await auth_role_dependencies.require_admin_session_user(current_user)
