"""Legacy Firebase, bearer-token, and websocket compatibility helpers."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.models.user import User, UserRole

if TYPE_CHECKING:
    from app.service_provider import ServiceProvider

logger = logging.getLogger(__name__)


def initialize_firebase_service(*, settings_obj=settings) -> Any:
    """Initialize optional Firebase Admin auth for compatibility-only flows."""
    firebase_service = None

    try:
        from app.services.firebase_auth_service import get_firebase_auth_service

        firebase_project_id = getattr(settings_obj, "FIREBASE_ADMIN_PROJECT_ID", None)
        firebase_private_key = getattr(settings_obj, "FIREBASE_ADMIN_PRIVATE_KEY", None)
        firebase_client_email = getattr(settings_obj, "FIREBASE_ADMIN_CLIENT_EMAIL", None)

        if firebase_project_id and firebase_private_key and firebase_client_email:
            firebase_service = get_firebase_auth_service(
                project_id=firebase_project_id,
                private_key=firebase_private_key,
                client_email=firebase_client_email,
            )
            logger.info("Optional Firebase authentication compatibility enabled")
        else:
            logger.info(
                "Firebase admin credentials absent; session-first staff authentication remains available"
            )
    except Exception as exc:
        logger.warning(
            "Failed to initialize optional Firebase auth compatibility: %s",
            str(exc),
        )
        firebase_service = None

    return firebase_service


<<<<<<< HEAD
<<<<<<< HEAD
=======
async def verify_firebase_token(
    id_token: str,
    *,
    firebase_service: Any,
) -> Optional[Dict[str, Any]]:
    """Verify a Firebase ID token via the isolated compatibility seam."""
    if firebase_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured",
        )

    try:
        return await firebase_service.verify_token(id_token)
    except Exception as exc:
        logger.error("Firebase token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase token: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


>>>>>>> gsd/M003/S02
=======
>>>>>>> gsd/M003/S04
def _cached_user_to_model(cached_user: Dict[str, Any]) -> User:
    """Convert cached bearer-auth user data into a ``User`` model."""
    cached_payload = dict(cached_user)
    cached_payload.pop("cached_at", None)

    role_value = cached_payload.get("role")
    if isinstance(role_value, str):
        normalized_role = role_value.lower()
        try:
            cached_payload["role"] = UserRole(normalized_role)
        except ValueError:
            logger.warning(
                "Unexpected cached user role '%s'. Falling back to doctor role.",
                role_value,
            )
            cached_payload["role"] = UserRole.DOCTOR

    return User(**cached_payload)


def _apply_request_user_state(request: Any, user: User) -> None:
    request.state.user_id = str(user.id)
    request.state.user_role = (
        user.role.value if hasattr(user.role, "value") else str(user.role)
    )


async def authenticate_legacy_bearer_user(
    *,
    request: Any,
    credentials: Optional[HTTPAuthorizationCredentials],
    services: "ServiceProvider",
    firebase_service: Any,
    validate_firebase_uid: Callable[[str], None],
    validate_email: Callable[[str], None],
    resolve_user_role: Callable[..., UserRole],
    should_use_sync_db: Callable[["ServiceProvider"], bool],
    get_user_from_db_sync: Callable[[str, Any], Optional[User]],
    get_user_from_db_async: Callable[[str, Any], Awaitable[Optional[User]]],
    serialize_user: Callable[[User], Dict[str, Any]],
) -> User:
    """Authenticate a user via the legacy Firebase bearer-token compatibility path."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    if not hasattr(credentials, "credentials"):
        logger.error(
            "get_current_user received wrong type: %s",
            type(credentials).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    if firebase_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured",
        )

    token_value = credentials.credentials

    try:
        from app.core.redis_manager import FirebaseRedisCache, get_redis_manager

        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_compatible_client("sync")
        firebase_cache = FirebaseRedisCache(redis_client)

        cached_token = firebase_cache.get_cached_token(token_value)

        if cached_token:
            logger.debug("✅ Token cache HIT for %s", cached_token.get("email"))
            firebase_uid = cached_token["firebase_uid"]
            validate_firebase_uid(firebase_uid)
            user_data = cached_token
        else:
            logger.debug("❌ Token cache MISS - validating with Firebase")
            user_data = await firebase_service.verify_token(token_value)
            firebase_uid = user_data["uid"]
            validate_firebase_uid(firebase_uid)
            firebase_cache.cache_validated_token(token_value, user_data)
            logger.info("💾 Token cached for %s", user_data.get("email"))

        cached_user = firebase_cache.get_cached_user(firebase_uid)

        if cached_user:
            logger.debug("✅ User cache HIT for %s", firebase_uid)
            user = _cached_user_to_model(cached_user)
            _apply_request_user_state(request, user)
            return user

        logger.debug(
            "❌ User cache MISS - querying PostgreSQL for %s with %ss timeout",
            firebase_uid,
            settings.DB_QUERY_TIMEOUT_READ,
        )

        try:
            if should_use_sync_db(services):
                user = get_user_from_db_sync(firebase_uid, services.db)
            else:
                from app.database import get_async_session_factory

                async_session_factory = get_async_session_factory()
                async with async_session_factory() as async_session:
                    try:
                        user = await get_user_from_db_async(firebase_uid, async_session)
                    except Exception:
                        await async_session.rollback()
                        raise
        except asyncio.CancelledError:
            logger.warning(
                "Database query cancelled for firebase_uid=%s...",
                firebase_uid[:8],
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable. Please try again.",
            )
        except Exception as exc:
            logger.error(
                "Database error for firebase_uid=%s...: %s",
                firebase_uid[:8],
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable. Please try again.",
            )

        if user:
            logger.debug("User found in database: %s", user.email)
            user_dict = serialize_user(user)
            firebase_cache.cache_user(firebase_uid, user_dict)
            logger.info("💾 User cached for %s", firebase_uid)

            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

            _apply_request_user_state(request, user)
            return user

        logger.info(
            "User not found in database, creating minimal record for: %s",
            user_data.get("email"),
        )

        email = user_data.get("email")
        if email:
            validate_email(email)

        firebase_custom_claims = user_data.get("custom_claims", {})
        user_role = resolve_user_role(
            firebase_custom_claims=firebase_custom_claims,
            db_role=None,
            default_role=UserRole.DOCTOR,
        )

        user = User(
            firebase_uid=firebase_uid,
            email=email,
            full_name=user_data.get("name", email.split("@")[0] if email else "Unknown"),
            is_active=True,
            role=user_role,
        )
        try:
            bind = services.db.get_bind()
            if bind and getattr(bind.dialect, "name", None) == "postgresql":
                timeout_ms = max(1, int(settings.DB_QUERY_TIMEOUT_WRITE * 1000))
                services.db.execute(
                    text(
                        "SELECT set_config('statement_timeout', :statement_timeout, true)"
                    ),
                    {"statement_timeout": f"{timeout_ms}ms"},
                )
            services.db.add(user)
            services.db.commit()
            services.db.refresh(user)
        except DBAPIError as exc:
            services.db.rollback()
            if "statement timeout" in str(exc).lower():
                logger.error(
                    "Database write timeout after %ss for firebase_uid=%s...",
                    settings.DB_QUERY_TIMEOUT_WRITE,
                    firebase_uid[:8],
                )
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=f"Database operation timed out after {settings.DB_QUERY_TIMEOUT_WRITE}s. Please try again.",
                )
            raise
        except Exception:
            services.db.rollback()
            raise

        user_dict = serialize_user(user)
        firebase_cache.cache_user(firebase_uid, user_dict)
        logger.info("✅ New user created and cached: %s", user.email)

        _apply_request_user_state(request, user)
        return user

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Firebase authentication failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firebase authentication failed: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


<<<<<<< HEAD
<<<<<<< HEAD
__all__ = [
    "authenticate_legacy_bearer_user",
    "initialize_firebase_service",
=======
async def get_current_user_websocket(
    websocket: Any,
    *,
    services: "ServiceProvider",
    firebase_service: Any,
) -> Optional[User]:
    """Authenticate a websocket connection through the legacy Firebase bearer path."""
    try:
        if firebase_service is None:
            logger.error("Firebase authentication not configured for WebSocket")
            return None

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

        user_data = await firebase_service.verify_token(token)
        email = user_data.get("email")
        if not email:
            return None

        user = services.user_repository.get_by_email(email.strip().lower())
        if user is None or not user.is_active:
            return None

        return user
    except Exception as exc:
        logger.error("WebSocket authentication failed: %s", exc)
        return None


=======
>>>>>>> gsd/M003/S04
__all__ = [
    "authenticate_legacy_bearer_user",
    "initialize_firebase_service",
<<<<<<< HEAD
    "verify_firebase_token",
>>>>>>> gsd/M003/S02
=======
>>>>>>> gsd/M003/S04
]
