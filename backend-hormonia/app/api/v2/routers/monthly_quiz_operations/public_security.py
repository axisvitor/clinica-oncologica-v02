"""Security helpers for tokenized public monthly quiz access.

The public quiz endpoints must treat the stored quiz-session link metadata as
authoritative. A valid JWT proves only that the token is signed; access is allowed
only when that signed payload still matches the persisted session, stored token
hash, active link state, and effective expiration boundary.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.domain.quizzes.session import TokenManager
from app.models.quiz import QuizSession
from app.utils.timezone import now_sao_paulo, to_sao_paulo

logger = logging.getLogger(__name__)

_REQUIRED_TOKEN_CLAIMS = ("type", "patient_id", "quiz_template_id", "session_id", "exp")
_REQUIRED_STATE_CLAIMS = ("type", "patient_id", "quiz_template_id", "session_id", "exp")
_SESSION_STATE_TOKEN_TYPE = "quiz_session_state"
_TERMINAL_SESSION_STATUSES = {"completed", "cancelled", "expired"}
_TERMINAL_LINK_STATUSES = {"used", "cancelled", "expired", "revoked"}


@dataclass(frozen=True)
class PublicQuizAccess:
    """Validated public quiz access context."""

    payload: dict[str, Any]
    session: QuizSession
    patient_id: UUID
    quiz_template_id: UUID
    session_id: UUID
    token_expires_at: datetime
    metadata_expires_at: datetime
    session_expires_at: datetime
    effective_expires_at: datetime


def _safe_resource_ids(
    *,
    session: Optional[QuizSession] = None,
    patient_id: Optional[UUID] = None,
    quiz_template_id: Optional[UUID] = None,
    session_id: Optional[UUID] = None,
) -> dict[str, str]:
    ids: dict[str, str] = {}
    resolved_session_id = session_id or getattr(session, "id", None)
    resolved_patient_id = patient_id or getattr(session, "patient_id", None)
    resolved_template_id = quiz_template_id or getattr(session, "quiz_template_id", None)
    if resolved_session_id:
        ids["session_id"] = str(resolved_session_id)
    if resolved_patient_id:
        ids["patient_id"] = str(resolved_patient_id)
    if resolved_template_id:
        ids["quiz_template_id"] = str(resolved_template_id)
    return ids


def _deny(
    reason: str,
    status_code: int,
    *,
    session: Optional[QuizSession] = None,
    patient_id: Optional[UUID] = None,
    quiz_template_id: Optional[UUID] = None,
    session_id: Optional[UUID] = None,
) -> None:
    """Log a safe denial reason and raise a generic public error."""
    extra: dict[str, Any] = {"reason": reason}
    extra.update(
        _safe_resource_ids(
            session=session,
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            session_id=session_id,
        )
    )
    logger.warning("Public quiz link denied: %s", reason, extra=extra)

    detail_by_status = {
        status.HTTP_401_UNAUTHORIZED: "Invalid quiz link",
        status.HTTP_403_FORBIDDEN: "Quiz link is not available",
        status.HTTP_404_NOT_FOUND: "Quiz link not found",
        status.HTTP_410_GONE: "Quiz link expired",
    }
    raise HTTPException(
        status_code=status_code,
        detail=detail_by_status.get(status_code, "Quiz link is not available"),
    )


def _parse_uuid_claim(
    value: Any,
    claim_name: str,
    *,
    patient_id: Optional[UUID] = None,
    quiz_template_id: Optional[UUID] = None,
    session_id: Optional[UUID] = None,
) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        _deny(
            f"invalid_{claim_name}",
            status.HTTP_401_UNAUTHORIZED,
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            session_id=session_id,
        )


def _parse_exp_claim(value: Any) -> datetime:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        _deny("invalid_exp", status.HTTP_401_UNAUTHORIZED)
    try:
        return to_sao_paulo(datetime.fromtimestamp(timestamp, tz=timezone.utc))
    except (OverflowError, OSError, ValueError):
        _deny("invalid_exp", status.HTTP_401_UNAUTHORIZED)


def _parse_metadata_datetime(value: Any, field_name: str, session: QuizSession) -> datetime:
    if not isinstance(value, str) or not value.strip():
        _deny(
            f"missing_{field_name}",
            status.HTTP_403_FORBIDDEN,
            session=session,
        )
    try:
        normalized = value.strip().replace("Z", "+00:00")
        return to_sao_paulo(datetime.fromisoformat(normalized))
    except (TypeError, ValueError):
        _deny(
            f"malformed_{field_name}",
            status.HTTP_403_FORBIDDEN,
            session=session,
        )


def _require_session_expiration(session: QuizSession) -> datetime:
    if not session.expiration_date:
        _deny(
            "missing_session_expiration",
            status.HTTP_403_FORBIDDEN,
            session=session,
        )
    return to_sao_paulo(session.expiration_date)


def _same_uuid(left: Any, right: UUID) -> bool:
    try:
        return UUID(str(left)) == right
    except (TypeError, ValueError):
        return False


async def validate_public_quiz_link_token(
    token: str,
    db: AsyncSession,
    *,
    expected_quiz_id: Optional[UUID] = None,
    allowed_types: Iterable[str] = ("quiz_access",),
) -> PublicQuizAccess:
    """Validate a public quiz token against stored session/link state.

    Fail closed on malformed tokens, missing/mismatched claims, missing sessions,
    inactive/terminal link state, hash mismatch, and expiration at or after the
    earliest JWT/session/metadata boundary.
    """
    if not isinstance(token, str) or not token.strip():
        _deny("missing_token", status.HTTP_401_UNAUTHORIZED)

    token = token.strip()
    if token.count(".") != 2:
        _deny("malformed_token", status.HTTP_401_UNAUTHORIZED)

    token_manager = TokenManager()
    try:
        payload = token_manager.verify_token(token)
    except jwt.ExpiredSignatureError:
        _deny("jwt_expired", status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidTokenError:
        _deny("jwt_invalid", status.HTTP_401_UNAUTHORIZED)

    for claim in _REQUIRED_TOKEN_CLAIMS:
        if payload.get(claim) in (None, ""):
            _deny(f"missing_{claim}", status.HTTP_401_UNAUTHORIZED)

    token_type = str(payload.get("type"))
    if token_type not in set(allowed_types):
        _deny("invalid_token_type", status.HTTP_401_UNAUTHORIZED)

    patient_id = _parse_uuid_claim(payload.get("patient_id"), "patient_id")
    quiz_template_id = _parse_uuid_claim(
        payload.get("quiz_template_id"),
        "quiz_template_id",
        patient_id=patient_id,
    )
    session_id = _parse_uuid_claim(
        payload.get("session_id"),
        "session_id",
        patient_id=patient_id,
        quiz_template_id=quiz_template_id,
    )
    token_expires_at = _parse_exp_claim(payload.get("exp"))

    if expected_quiz_id is not None and expected_quiz_id != quiz_template_id:
        _deny(
            "path_quiz_mismatch",
            status.HTTP_401_UNAUTHORIZED,
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            session_id=session_id,
        )

    session_result = await db.execute(
        select(QuizSession).where(QuizSession.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        _deny(
            "session_not_found",
            status.HTTP_404_NOT_FOUND,
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            session_id=session_id,
        )

    if not _same_uuid(session.patient_id, patient_id):
        _deny(
            "patient_mismatch",
            status.HTTP_403_FORBIDDEN,
            session=session,
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
        )

    if not _same_uuid(session.quiz_template_id, quiz_template_id):
        _deny(
            "template_mismatch",
            status.HTTP_403_FORBIDDEN,
            session=session,
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
        )

    if session.status != "started":
        denial_status = (
            status.HTTP_410_GONE
            if session.status in _TERMINAL_SESSION_STATUSES
            else status.HTTP_403_FORBIDDEN
        )
        _deny(
            "session_not_started",
            denial_status,
            session=session,
        )

    if session.is_expired:
        _deny("session_expired", status.HTTP_410_GONE, session=session)

    metadata = session.session_metadata
    if not isinstance(metadata, dict):
        _deny("malformed_link_metadata", status.HTTP_403_FORBIDDEN, session=session)

    link_status = str(metadata.get("link_status", "")).strip().lower()
    if link_status != "active":
        denial_status = (
            status.HTTP_410_GONE
            if link_status in _TERMINAL_LINK_STATUSES
            else status.HTTP_403_FORBIDDEN
        )
        _deny(
            "link_status_inactive",
            denial_status,
            session=session,
        )

    stored_token_hash = metadata.get("token_hash")
    if not isinstance(stored_token_hash, str) or not stored_token_hash.strip():
        _deny("missing_token_hash", status.HTTP_403_FORBIDDEN, session=session)
    if stored_token_hash != token_manager.hash_token(token):
        _deny("token_hash_mismatch", status.HTTP_403_FORBIDDEN, session=session)

    metadata_expires_at = _parse_metadata_datetime(
        metadata.get("expires_at"),
        "expires_at",
        session,
    )
    session_expires_at = _require_session_expiration(session)
    effective_expires_at = min(token_expires_at, session_expires_at, metadata_expires_at)

    if now_sao_paulo() >= effective_expires_at:
        _deny("effective_expired", status.HTTP_410_GONE, session=session)

    return PublicQuizAccess(
        payload=payload,
        session=session,
        patient_id=patient_id,
        quiz_template_id=quiz_template_id,
        session_id=session_id,
        token_expires_at=token_expires_at,
        metadata_expires_at=metadata_expires_at,
        session_expires_at=session_expires_at,
        effective_expires_at=effective_expires_at,
    )


def sign_public_quiz_session_state(access: PublicQuizAccess) -> str:
    """Sign opaque compatibility-cookie state for a validated quiz link.

    The state token proves only the already-authorized session identity and is
    capped at the same effective expiration as the public link validator.
    """
    return TokenManager().generate_token(
        patient_id=access.patient_id,
        quiz_template_id=access.quiz_template_id,
        expires_at=access.effective_expires_at,
        session_id=access.session_id,
        token_type=_SESSION_STATE_TOKEN_TYPE,
    )


async def validate_public_quiz_session_state(
    state_token: Optional[str],
    db: AsyncSession,
    *,
    raw_session_id: Optional[str] = None,
    expected_quiz_id: Optional[UUID] = None,
) -> PublicQuizAccess:
    """Validate signed compatibility cookie state against active link state.

    Raw ``quiz_session_id`` cookies are treated as compatibility hints only. The
    signed state is the authorization proof; if both cookies are present their
    session IDs must match, and the stored session/link metadata must still be
    active and unexpired.
    """
    if not isinstance(state_token, str) or not state_token.strip():
        _deny("missing_session_state", status.HTTP_401_UNAUTHORIZED)

    state_token = state_token.strip()
    if state_token.count(".") != 2:
        _deny("malformed_session_state", status.HTTP_401_UNAUTHORIZED)

    token_manager = TokenManager()
    try:
        payload = token_manager.verify_token(state_token)
    except jwt.ExpiredSignatureError:
        _deny("session_state_expired", status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidTokenError:
        _deny("session_state_invalid", status.HTTP_401_UNAUTHORIZED)

    for claim in _REQUIRED_STATE_CLAIMS:
        if payload.get(claim) in (None, ""):
            _deny(f"missing_state_{claim}", status.HTTP_401_UNAUTHORIZED)

    if str(payload.get("type")) != _SESSION_STATE_TOKEN_TYPE:
        _deny("invalid_session_state_type", status.HTTP_401_UNAUTHORIZED)

    patient_id = _parse_uuid_claim(payload.get("patient_id"), "state_patient_id")
    quiz_template_id = _parse_uuid_claim(
        payload.get("quiz_template_id"),
        "state_quiz_template_id",
        patient_id=patient_id,
    )
    session_id = _parse_uuid_claim(
        payload.get("session_id"),
        "state_session_id",
        patient_id=patient_id,
        quiz_template_id=quiz_template_id,
    )
    state_expires_at = _parse_exp_claim(payload.get("exp"))

    if expected_quiz_id is not None and expected_quiz_id != quiz_template_id:
        _deny(
            "state_path_quiz_mismatch",
            status.HTTP_401_UNAUTHORIZED,
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            session_id=session_id,
        )

    if raw_session_id:
        try:
            raw_session_uuid = UUID(str(raw_session_id))
        except (TypeError, ValueError):
            _deny(
                "invalid_raw_session_cookie",
                status.HTTP_401_UNAUTHORIZED,
                patient_id=patient_id,
                quiz_template_id=quiz_template_id,
                session_id=session_id,
            )
        if raw_session_uuid != session_id:
            _deny(
                "raw_session_state_mismatch",
                status.HTTP_401_UNAUTHORIZED,
                patient_id=patient_id,
                quiz_template_id=quiz_template_id,
                session_id=session_id,
            )

    session_result = await db.execute(
        select(QuizSession).where(QuizSession.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        _deny(
            "state_session_not_found",
            status.HTTP_401_UNAUTHORIZED,
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            session_id=session_id,
        )

    if not _same_uuid(session.patient_id, patient_id):
        _deny(
            "state_patient_mismatch",
            status.HTTP_401_UNAUTHORIZED,
            session=session,
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
        )

    if not _same_uuid(session.quiz_template_id, quiz_template_id):
        _deny(
            "state_template_mismatch",
            status.HTTP_401_UNAUTHORIZED,
            session=session,
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
        )

    if session.status != "started":
        denial_status = (
            status.HTTP_410_GONE
            if session.status in _TERMINAL_SESSION_STATUSES
            else status.HTTP_403_FORBIDDEN
        )
        _deny("state_session_not_started", denial_status, session=session)

    if session.is_expired:
        _deny("state_session_expired", status.HTTP_410_GONE, session=session)

    metadata = session.session_metadata
    if not isinstance(metadata, dict):
        _deny("state_malformed_link_metadata", status.HTTP_403_FORBIDDEN, session=session)

    link_status = str(metadata.get("link_status", "")).strip().lower()
    if link_status != "active":
        denial_status = (
            status.HTTP_410_GONE
            if link_status in _TERMINAL_LINK_STATUSES
            else status.HTTP_403_FORBIDDEN
        )
        _deny("state_link_status_inactive", denial_status, session=session)

    stored_token_hash = metadata.get("token_hash")
    if not isinstance(stored_token_hash, str) or not stored_token_hash.strip():
        _deny("state_missing_token_hash", status.HTTP_403_FORBIDDEN, session=session)

    metadata_expires_at = _parse_metadata_datetime(
        metadata.get("expires_at"),
        "expires_at",
        session,
    )
    session_expires_at = _require_session_expiration(session)
    effective_expires_at = min(state_expires_at, session_expires_at, metadata_expires_at)

    if now_sao_paulo() >= effective_expires_at:
        _deny("state_effective_expired", status.HTTP_410_GONE, session=session)

    return PublicQuizAccess(
        payload=payload,
        session=session,
        patient_id=patient_id,
        quiz_template_id=quiz_template_id,
        session_id=session_id,
        token_expires_at=state_expires_at,
        metadata_expires_at=metadata_expires_at,
        session_expires_at=session_expires_at,
        effective_expires_at=effective_expires_at,
    )
