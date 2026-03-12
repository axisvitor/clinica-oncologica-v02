from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlencode
import logging

from fastapi import HTTPException, status

from app.config import settings
from app.core.security import create_password_reset_token, verify_password_reset_token
from app.models.user import AuthProvider, User
from app.repositories.session import SessionRepository
from app.repositories.user import UserRepository
from app.schemas.admin_validation import validate_password_strength
from app.services.auth import AuthService
from app.services.notification_service import NotificationService, get_notification_service
from app.utils.security import get_password_hash
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

RESET_REQUEST_SUCCESS_MESSAGE = "If the account exists, a recovery email has been sent."
RESET_CONFIRM_SUCCESS_MESSAGE = "Password reset successful"
RESET_DELIVERY_ERROR = "AUTH_PASSWORD_RESET_DELIVERY_FAILED"
RESET_WEAK_PASSWORD_ERROR = "AUTH_PASSWORD_WEAK"
RESET_TOKEN_ERROR = "AUTH_RESET_TOKEN_INVALID_OR_EXPIRED"
RESET_SERVICE_ERROR = "AUTH_PASSWORD_RESET_SERVICE_UNAVAILABLE"
RESET_SESSION_REVOCATION_ERROR = "AUTH_PASSWORD_RESET_SESSION_REVOCATION_FAILED"


@dataclass(slots=True)
class PasswordResetFailure(Exception):
    """Structured password-reset failure surfaced to the API layer."""

    error_code: str
    message: str
    status_code: int

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


@dataclass(slots=True)
class PasswordResetDeliveryResult:
    """Redacted delivery metadata for reset and first-access email dispatch."""

    channel: str
    status: str
    first_access: bool
    message_id: Optional[str] = None


class PasswordResetService:
    """Reusable orchestration for public recovery and first-access flows."""

    def __init__(
        self,
        db: Any,
        *,
        redis_cache: Any = None,
        user_repository: Optional[UserRepository] = None,
        session_repository: Optional[SessionRepository] = None,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.db = db
        self.redis_cache = redis_cache
        self.user_repository = user_repository or UserRepository(db)
        self.session_repository = session_repository or SessionRepository(db)
        self.notification_service = notification_service or get_notification_service()
        self.auth_service = AuthService(db, self.user_repository, redis_cache)

    @staticmethod
    def normalize_email(email: str) -> str:
        return (email or "").strip().lower()

    @staticmethod
    def is_first_access_user(user: User) -> bool:
        return bool(getattr(user, "force_change_password", False) or not getattr(user, "hashed_password", None))

    def _build_reset_link(self, token: str, *, first_access: bool) -> str:
        base_url = settings.AUTH_RESET_BASE_URL.rstrip("/")
        path = settings.AUTH_FIRST_ACCESS_PATH if first_access else settings.AUTH_RESET_PATH
        normalized_path = path if path.startswith("/") else f"/{path}"
        query = urlencode({"token": token})
        return f"{base_url}{normalized_path}?{query}"

    def _create_reset_token(self, user: User) -> str:
        return create_password_reset_token(self.normalize_email(user.email))

    def _validate_new_password(self, password: str) -> None:
        try:
            validate_password_strength(password)
            return
        except ValueError as exc:
            logger.info(
                "Password reset rejected due to weak password",
                extra={"error_type": type(exc).__name__},
            )
            raise PasswordResetFailure(
                error_code=RESET_WEAK_PASSWORD_ERROR,
                message="Password does not meet security requirements.",
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc

    def _resolve_user_from_token(self, token: str) -> User:
        try:
            token_email = verify_password_reset_token(token)
        except HTTPException as exc:
            raise PasswordResetFailure(
                error_code=RESET_TOKEN_ERROR,
                message="Invalid or expired reset token.",
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc
        except Exception as exc:
            raise PasswordResetFailure(
                error_code=RESET_TOKEN_ERROR,
                message="Invalid or expired reset token.",
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc

        user = self.user_repository.get_by_email(self.normalize_email(token_email))
        if user is None:
            raise PasswordResetFailure(
                error_code=RESET_TOKEN_ERROR,
                message="Invalid or expired reset token.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return user

    async def _dispatch_reset_email(self, user: User) -> PasswordResetDeliveryResult:
        first_access = self.is_first_access_user(user)
        token = self._create_reset_token(user)
        reset_url = self._build_reset_link(token, first_access=first_access)

        try:
            result = await self.notification_service.send_password_reset_email(
                email=user.email,
                full_name=getattr(user, "full_name", None),
                reset_url=reset_url,
                expires_in_hours=settings.AUTH_RESET_TOKEN_EXPIRE_HOURS,
                first_access=first_access,
            )
        except Exception as exc:
            logger.warning(
                "Password reset delivery failed",
                extra={
                    "error_type": type(exc).__name__,
                    "user_id": str(getattr(user, "id", "")),
                    "first_access": first_access,
                },
            )
            raise PasswordResetFailure(
                error_code=RESET_DELIVERY_ERROR,
                message="Unable to send recovery email at this time.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc

        message_id = getattr(result, "message_id", None)
        logger.info(
            "Password reset email queued",
            extra={
                "user_id": str(user.id),
                "first_access": first_access,
                "delivery_channel": getattr(getattr(result, "channel", None), "value", "email"),
                "delivery_message_id": message_id,
            },
        )
        return PasswordResetDeliveryResult(
            channel=getattr(getattr(result, "channel", None), "value", "email"),
            status="sent",
            first_access=first_access,
            message_id=message_id,
        )

    async def request_password_reset(self, email: str) -> bool:
        """Attempt a password reset email without enumerating accounts."""
        normalized_email = self.normalize_email(email)
        user = self.user_repository.get_by_email(normalized_email)
        if user is None:
            logger.info("Password reset requested for unknown account")
            return False

        await self._dispatch_reset_email(user)
        return True

    async def request_password_reset_for_user(
        self,
        user: User,
    ) -> PasswordResetDeliveryResult:
        """Trigger the shared email-backed recovery flow for a known user."""
        return await self._dispatch_reset_email(user)

    async def confirm_password_reset(self, token: str, new_password: str) -> User:
        """Validate a reset token, update credentials, and revoke active sessions."""
        self._validate_new_password(new_password)
        user = self._resolve_user_from_token(token)
        normalized_email = self.normalize_email(user.email)
        now = now_sao_paulo()

        user.hashed_password = get_password_hash(new_password)
        user.auth_provider = AuthProvider.LOCAL
        user.force_change_password = False
        user.last_password_change = now
        user.failed_login_attempts = 0
        user.is_locked = False
        user.locked_until = None
        user.updated_at = now
        self.db.add(user)
        self.db.flush()

        self.session_repository.revoke_all_user_sessions(
            user.id,
            reason="password_reset",
            commit=False,
        )

        try:
            await self._invalidate_active_sessions(str(user.id))
            await self.auth_service._clear_failed_attempts(normalized_email)
        except PasswordResetFailure:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise PasswordResetFailure(
                error_code=RESET_SERVICE_ERROR,
                message="Password reset failed. Please try again later.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc

        self.db.commit()
        self.db.refresh(user)

        logger.info(
            "Password reset completed",
            extra={
                "user_id": str(user.id),
                "auth_provider": user.auth_provider.value,
            },
        )
        return user

    async def _invalidate_active_sessions(self, identity: str) -> int:
        if self.redis_cache is None:
            return 0

        invalidate_all = getattr(self.redis_cache, "invalidate_all_user_sessions", None)
        if callable(invalidate_all):
            try:
                result = invalidate_all(identity)
                if hasattr(result, "__await__"):
                    result = await result
                return int(result or 0)
            except Exception as exc:
                logger.warning(
                    "Password reset session invalidation failed",
                    extra={
                        "identity": identity,
                        "error_type": type(exc).__name__,
                    },
                )
                raise PasswordResetFailure(
                    error_code=RESET_SESSION_REVOCATION_ERROR,
                    message="Password reset could not revoke active sessions.",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                ) from exc

        logger.debug("Redis cache does not expose invalidate_all_user_sessions")
        return 0
