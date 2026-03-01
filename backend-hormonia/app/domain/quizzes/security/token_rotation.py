"""
Token Rotation Implementation Patch for Monthly Quiz Service.

This module provides the token validation and rotation logic that should be
integrated into monthly_quiz_service.py.

INTEGRATION INSTRUCTIONS:
1. Add _validate_token_with_grace_period method to MonthlyQuizService class
2. Update submit_quiz_response method to use token validation and rotation
3. Verify access_quiz_via_token already has rotation (it does)
4. Update .env with token rotation settings
5. Update frontend to handle new_token in responses
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Tuple
from uuid import UUID
from sqlalchemy import and_

from app.models.quiz import QuizSession
from app.exceptions import NotFoundError, ValidationError
from app.utils.timezone import now_sao_paulo


# ============================================================================
# METHOD 1: Token Validation with Grace Period
# ============================================================================
# INSERT THIS METHOD INTO MonthlyQuizService CLASS (after line 50)


def _validate_token_with_grace_period(
    self, token: str, session: QuizSession
) -> Tuple[bool, str]:
    """
    Validate token against session with grace period support.

    This method checks if a token is valid by comparing its hash against:
    1. The current token hash (primary validation)
    2. The previous token hash within grace period (fallback)

    Args:
        token: The token string to validate
        session: The quiz session containing token metadata

    Returns:
        Tuple[bool, str]: (is_valid, reason)
            - is_valid: True if token is valid, False otherwise
            - reason: Validation result reason:
                "current_token" - Token matches current hash
                "grace_period" - Token matches previous hash within grace period
                "grace_period_expired" - Token matches previous but outside grace
                "token_mismatch" - Token doesn't match any hash
                "invalid_timestamp" - Malformed timestamp in metadata
                "previous_token_no_grace_period" - Previous token without timestamp
                "Session has no metadata" - Session metadata missing

    Examples:
        >>> is_valid, reason = service._validate_token_with_grace_period(token, session)
        >>> if not is_valid:
        >>>     raise ValidationError(f"Invalid token: {reason}")
        >>> if reason == "grace_period":
        >>>     logger.warning("Token accepted within grace period")
    """
    if not session.session_metadata:
        return (False, "Session has no metadata")

    # Calculate token hash
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Get current and previous token hashes from session metadata
    current_hash = session.session_metadata.get("token_hash")
    previous_hash = session.session_metadata.get("previous_token_hash")

    # PRIMARY CHECK: Does token match current hash?
    if token_hash == current_hash:
        return (True, "current_token")

    # SECONDARY CHECK: Does token match previous hash? (grace period)
    if token_hash == previous_hash:
        # Check if within grace period
        invalidated_at_str = session.session_metadata.get(
            "previous_token_invalidated_at"
        )

        if invalidated_at_str:
            try:
                invalidated_at = datetime.fromisoformat(invalidated_at_str)
                grace_period = timedelta(
                    seconds=self.config.MONTHLY_QUIZ_TOKEN_GRACE_PERIOD_SECONDS
                )

                # Calculate time since invalidation
                time_since_invalidation = now_sao_paulo() - invalidated_at

                if time_since_invalidation < grace_period:
                    # Token is within grace period - allow but log warning
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Token accepted within grace period for session {session.id} "
                        f"(age: {time_since_invalidation.total_seconds():.1f}s)"
                    )
                    return (True, "grace_period")
                else:
                    # Token expired outside grace period
                    return (False, "grace_period_expired")

            except ValueError as e:
                # Malformed timestamp in metadata
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Invalid timestamp in session metadata: {e}")
                return (False, "invalid_timestamp")

        # Previous token exists but no timestamp (shouldn't happen)
        return (False, "previous_token_no_grace_period")

    # Token doesn't match current or previous
    return (False, "token_mismatch")


# ============================================================================
# METHOD 2: Token Rotation on Submission
# ============================================================================
# REPLACE submit_quiz_response METHOD (lines 316-445) WITH THIS:


async def submit_quiz_response_with_rotation(
    self,
    submit_data,  # MonthlyQuizSubmitResponse
    ip_address=None,
    user_agent=None,
):
    """
    Submit a quiz response via token with automatic token rotation.

    This method:
    1. Validates the token (with grace period support)
    2. Stores the quiz response
    3. Rotates the token if rotation is enabled
    4. Returns success response with new token

    Token Rotation Flow:
    - Old token is moved to previous_token_hash
    - New token is generated and stored in token_hash
    - Old token remains valid for MONTHLY_QUIZ_TOKEN_GRACE_PERIOD_SECONDS
    - Rotation count is incremented

    Args:
        submit_data: Submission data containing token, question_id, response
        ip_address: Client IP address (for audit logging)
        user_agent: Client user agent (for audit logging)

    Returns:
        Dict containing:
            - response_id: UUID of stored response
            - success: True if submission succeeded
            - message: Success message
            - new_token: Rotated token (if rotation enabled)
            - next_question_index: Index of next question
            - is_completed: True if quiz is complete
            - total_questions: Total number of questions

    Raises:
        NotFoundError: If session or question not found
        ValidationError: If token invalid or response format invalid
    """
    # Verify token signature and expiry (JWT validation)
    payload = self._verify_token(submit_data.token)
    patient_id = UUID(payload["patient_id"])
    quiz_template_id = UUID(payload["quiz_template_id"])
    token_hash = hashlib.sha256(submit_data.token.encode()).hexdigest()

    # Find session by token/session binding (avoid picking unrelated historical sessions)
    session = None
    session_id_str = payload.get("session_id")
    if session_id_str:
        try:
            session_id = UUID(session_id_str)
            session = (
                self.db.query(QuizSession)
                .filter(
                    and_(
                        QuizSession.id == session_id,
                        QuizSession.patient_id == patient_id,
                        QuizSession.quiz_template_id == quiz_template_id,
                    )
                )
                .first()
            )
        except (ValueError, TypeError):
            session = None

    if not session:
        # Cross-dialect fallback: avoid JSONB-specific operators while matching
        # the expected token binding behavior.
        candidates = (
            self.db.query(QuizSession)
            .filter(
                and_(
                    QuizSession.patient_id == patient_id,
                    QuizSession.quiz_template_id == quiz_template_id,
                )
            )
            .all()
        )
        session = next(
            (
                item
                for item in candidates
                if isinstance(item.session_metadata, dict)
                and token_hash
                in {
                    item.session_metadata.get("token_hash"),
                    item.session_metadata.get("previous_token_hash"),
                }
            ),
            None,
        )

    if not session:
        raise NotFoundError("Quiz session not found for this token")

    # ========================================
    # TOKEN VALIDATION WITH GRACE PERIOD
    # ========================================
    is_valid, validation_reason = self._validate_token_with_grace_period(
        submit_data.token, session
    )

    if not is_valid:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Invalid token for session {session.id}: {validation_reason} "
            f"(patient: {patient_id}, IP: {ip_address})"
        )
        raise ValidationError(f"Invalid or expired token: {validation_reason}")

    if validation_reason == "grace_period":
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Token accepted within grace period for session {session.id} "
            f"(patient: {patient_id})"
        )

    # Get template to find question
    template = self.template_repository.get(quiz_template_id)
    question = next(
        (q for q in template.questions if q.get("id") == submit_data.question_id), None
    )

    if not question:
        raise NotFoundError(f"Question {submit_data.question_id} not found in template")

    # ========================================
    # RESPONSE VALUE NORMALIZATION
    # ========================================
    response_value = submit_data.response_value
    question_type = question.get("type", "open_text")

    def normalize_other_value(value):
        """Normalize various 'other' option aliases to match question options."""
        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in ["outra", "other", "outro", "otra", "autre", "altro"]:
                question_options = question.get("options", [])
                for opt in question_options:
                    if isinstance(opt, dict):
                        opt_value = opt.get("value", "")
                        if opt.get("allow_other") or opt_value.lower() in [
                            "outra",
                            "other",
                            "outro",
                            "otra",
                        ]:
                            return opt_value
                return "other"
        return value

    if question_type == "multiple_choice":
        if isinstance(response_value, str):
            try:
                import json

                response_value = json.loads(response_value)
            except (json.JSONDecodeError, ValueError):
                response_value = [normalize_other_value(response_value)]
        elif isinstance(response_value, list):
            response_value = [normalize_other_value(v) for v in response_value]
        else:
            raise ValidationError("Multiple choice requires array of values")
    elif question_type == "single_choice":
        if isinstance(response_value, str):
            response_value = normalize_other_value(response_value)

    # ========================================
    # ENCRYPTION (if enabled)
    # ========================================
    encrypted_response_value = response_value
    is_encrypted = False

    if self.config.MONTHLY_QUIZ_ENABLE_ENCRYPTION:
        if question.get("is_sensitive", False):
            import json

            value_to_encrypt = (
                json.dumps(response_value)
                if isinstance(response_value, list)
                else str(response_value)
            )
            encrypted_response_value = self.encryption_service.encrypt(value_to_encrypt)
            is_encrypted = True

    # ========================================
    # STORE RESPONSE
    # ========================================
    from app.schemas.quiz import QuizResponseCreate, QuestionType

    response_metadata = submit_data.response_metadata or {}
    response_metadata["is_encrypted"] = is_encrypted

    response_create = QuizResponseCreate(
        patient_id=patient_id,
        quiz_template_id=quiz_template_id,
        question_id=submit_data.question_id,
        question_text=question.get("text", ""),
        response_type=QuestionType(question.get("type", "open_text")),
        response_value=encrypted_response_value,
        response_metadata=response_metadata,
        responded_at=now_sao_paulo(),
    )

    response = await self.quiz_response_service.create_response(response_create)

    # ========================================
    # TOKEN ROTATION ON SUCCESSFUL SUBMISSION
    # ========================================
    new_token = None
    if self.config.MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION:
        try:
            # Get current rotation count
            rotation_count = session.session_metadata.get("rotation_count", 0)

            # Generate new token with incremented rotation count
            new_token_value = self._generate_token(
                patient_id=patient_id,
                quiz_template_id=quiz_template_id,
                expires_at=datetime.fromisoformat(payload["expires_at"]),
                rotation_count=rotation_count + 1,
            )
            new_token_hash = hashlib.sha256(new_token_value.encode()).hexdigest()

            # Update session metadata with new token
            metadata = session.session_metadata or {}

            # Store previous token hash for grace period
            metadata["previous_token_hash"] = metadata.get("token_hash")
            metadata["previous_token_invalidated_at"] = now_sao_paulo().isoformat()

            # Update to new token
            metadata["token_hash"] = new_token_hash
            metadata["token_rotated_at"] = now_sao_paulo().isoformat()
            metadata["rotation_count"] = rotation_count + 1

            session.session_metadata = metadata
            self.db.commit()

            new_token = new_token_value

            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"Token rotated on submission for session {session.id} "
                f"(rotation #{rotation_count + 1}, patient: {patient_id})"
            )

            # Record metrics for token rotation
            await self.metrics_collector.record_token_rotated(
                patient_id=str(patient_id),
                quiz_session_id=str(session.id),
                old_token_prefix=submit_data.token[:10],
                new_token_prefix=new_token[:10],
                rotation_count=rotation_count + 1,
            )

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Token rotation failed for session {session.id}: {e}", exc_info=True
            )
            # Continue without rotation (security degradation but functional)
            # Frontend will continue using old token

    # ========================================
    # METRICS & AUDIT
    # ========================================
    # Record metrics for successful submission
    await self.metrics_collector.record_quiz_submit_success(
        patient_id=str(patient_id),
        quiz_session_id=str(session.id),
        question_id=submit_data.question_id,
        response_id=str(response.id),
        is_encrypted=is_encrypted,
    )

    # Audit log response submission
    if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
        self.audit_service.log_response_submitted(
            patient_id=patient_id,
            session_id=session.id,
            question_id=submit_data.question_id,
            response_id=response.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # ========================================
    # UPDATE SESSION PROGRESS
    # ========================================
    session.current_question_index += 1
    if session.current_question_index >= len(template.questions):
        session.status = "completed"
        session.completed_at = now_sao_paulo()

    self.db.commit()

    # ========================================
    # RETURN RESPONSE WITH NEW TOKEN
    # ========================================
    return {
        "response_id": str(response.id),
        "success": True,
        "message": "Response submitted successfully",
        "new_token": new_token,  # ✅ Frontend will update token
        "next_question_index": session.current_question_index,
        "is_completed": session.status == "completed",
        "total_questions": len(template.questions),
    }


# ============================================================================
# INTEGRATION CHECKLIST
# ============================================================================
"""
STEP 1: Update monthly_quiz_config.py
□ Add MONTHLY_QUIZ_TOKEN_GRACE_PERIOD_SECONDS config (default: 30)
□ Update MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION description

STEP 2: Update monthly_quiz_service.py
□ Add _validate_token_with_grace_period method after line 50
□ Replace submit_quiz_response method (lines 316-445)
□ Verify access_quiz_via_token has rotation (it does - lines 209-310)

STEP 3: Update .env
□ Set MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION=true
□ Set MONTHLY_QUIZ_TOKEN_GRACE_PERIOD_SECONDS=30

STEP 4: Update Frontend (quiz-mensal-interface/lib/api.ts)
□ Update submitAnswer to handle new_token in response
□ Update component to store and use rotated tokens

STEP 5: Testing
□ Test normal submission flow with rotation
□ Test grace period (use old token within 30s)
□ Test expired grace period (use old token after 30s)
□ Test concurrent submissions
□ Test replay attack prevention

STEP 6: Monitoring
□ Monitor token rotation success rate (should be >99%)
□ Monitor grace period usage (should be <5%)
□ Monitor invalid token attempts (spike = possible attack)
□ Check logs for rotation failures

SECURITY NOTES:
- Token rotation ONLY on successful submission
- Grace period prevents race conditions (30s default)
- rotation_count tracks token lifecycle
- Audit logs all token events
- Backward compatible (works when rotation disabled)
"""
