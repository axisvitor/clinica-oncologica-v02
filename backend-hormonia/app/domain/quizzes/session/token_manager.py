"""Token management for quiz sessions."""

from __future__ import annotations

import secrets
import hashlib
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from uuid import UUID

from app.core.monthly_quiz_config import get_monthly_quiz_config

import logging
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class TokenManager:
    """Handles JWT token generation and verification for quiz sessions."""

    def __init__(self):
        self.config = get_monthly_quiz_config()

    def generate_token(
        self,
        patient_id: UUID,
        quiz_template_id: UUID,
        expires_at: datetime,
        rotation_count: int = 0,
        session_id: Optional[UUID] = None,
        token_type: str = "quiz_access",
    ) -> str:
        """Generate a JWT token for quiz session access.

        Args:
            patient_id: Patient identifier
            quiz_template_id: Quiz template identifier
            expires_at: Token expiration datetime
            rotation_count: Number of times token has been rotated
            session_id: Optional quiz session identifier
            token_type: Token usage type (default: quiz_access)

        Returns:
            JWT token string
        """
        payload = {
            "patient_id": str(patient_id),
            "quiz_template_id": str(quiz_template_id),
            "exp": int(expires_at.timestamp()),
            "iat": int(now_sao_paulo().timestamp()),
            "rotation": rotation_count,
            "jti": secrets.token_urlsafe(16),  # Unique token ID
            "type": token_type,
        }
        if session_id:
            payload["session_id"] = str(session_id)

        token = jwt.encode(
            payload, self.config.MONTHLY_QUIZ_TOKEN_SECRET, algorithm="HS256"
        )

        return token

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload

        Raises:
            jwt.ExpiredSignatureError: Token has expired
            jwt.InvalidTokenError: Token is invalid
        """
        try:
            payload = jwt.decode(
                token, self.config.MONTHLY_QUIZ_TOKEN_SECRET, algorithms=["HS256"]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning(
                "Quiz token verification failed", extra={"reason": "expired_token"}
            )
            raise
        except jwt.InvalidTokenError:
            logger.warning(
                "Quiz token verification failed", extra={"reason": "invalid_token"}
            )
            raise

    def hash_token(self, token: str) -> str:
        """Generate SHA256 hash of token for storage.

        Args:
            token: Token string to hash

        Returns:
            Hex digest of SHA256 hash
        """
        return hashlib.sha256(token.encode()).hexdigest()

    def generate_expiry(self, hours: Optional[int] = None) -> datetime:
        """Calculate token expiration datetime.

        Args:
            hours: Hours until expiration (uses config default if None)

        Returns:
            Expiration datetime
        """
        expiry_hours = hours or self.config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS
        return now_sao_paulo() + timedelta(hours=expiry_hours)
