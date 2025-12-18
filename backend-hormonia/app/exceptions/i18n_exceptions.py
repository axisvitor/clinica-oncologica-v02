"""
Internationalized Exception Classes

Custom HTTPException classes that use i18n for error messages.
Messages are automatically translated based on the current locale.

Usage:
    from app.exceptions.i18n_exceptions import PatientNotFoundException

    raise PatientNotFoundException(patient_id="123e4567-e89b-12d3-a456-426614174000")
"""

from fastapi import HTTPException
from typing import Optional, Dict
import logging

from app.config.i18n import t

logger = logging.getLogger(__name__)


class TranslatableHTTPException(HTTPException):
    """
    HTTPException with i18n support.

    Translates error messages using the current locale.
    """

    def __init__(
        self,
        status_code: int,
        translation_key: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """
        Initialize translatable exception.

        Args:
            status_code: HTTP status code
            translation_key: Key for translation (e.g., 'errors.patient.not_found')
            headers: Optional HTTP headers
            **kwargs: Variables for translation substitution
        """
        # Translate the error message
        detail = t(translation_key, **kwargs)

        # Log the error with translation key for debugging
        logger.debug(
            f"TranslatableHTTPException: {translation_key} → {detail} "
            f"(status={status_code}, kwargs={kwargs})"
        )

        super().__init__(status_code=status_code, detail=detail, headers=headers)


# ===============================
# Patient-related exceptions
# ===============================


class PatientNotFoundException(TranslatableHTTPException):
    """Raised when patient is not found."""

    def __init__(self, patient_id: Optional[str] = None):
        super().__init__(
            status_code=404,
            translation_key="errors.patient.not_found",
            patient_id=patient_id or "",
        )


class DuplicateCPFException(TranslatableHTTPException):
    """Raised when CPF is already registered."""

    def __init__(self, cpf: str):
        super().__init__(
            status_code=409, translation_key="errors.patient.duplicate_cpf", cpf=cpf
        )


class DuplicateEmailException(TranslatableHTTPException):
    """Raised when email is already in use."""

    def __init__(self, email: str):
        super().__init__(
            status_code=409,
            translation_key="errors.patient.duplicate_email",
            email=email,
        )


class DuplicatePhoneException(TranslatableHTTPException):
    """Raised when phone number is already registered."""

    def __init__(self, phone: str):
        super().__init__(
            status_code=409,
            translation_key="errors.patient.duplicate_phone",
            phone=phone,
        )


class InvalidCPFException(TranslatableHTTPException):
    """Raised when CPF format is invalid."""

    def __init__(self):
        super().__init__(status_code=400, translation_key="errors.patient.invalid_cpf")


class InvalidPhoneException(TranslatableHTTPException):
    """Raised when phone number format is invalid."""

    def __init__(self, phone: str):
        super().__init__(
            status_code=400, translation_key="errors.patient.invalid_phone", phone=phone
        )


class PatientAccessDeniedException(TranslatableHTTPException):
    """Raised when user doesn't have access to patient."""

    def __init__(self):
        super().__init__(
            status_code=403, translation_key="errors.patient.access_denied"
        )


# ===============================
# Authentication exceptions
# ===============================


class InvalidCredentialsException(TranslatableHTTPException):
    """Raised when login credentials are invalid."""

    def __init__(self):
        super().__init__(
            status_code=401, translation_key="errors.auth.invalid_credentials"
        )


class TokenExpiredException(TranslatableHTTPException):
    """Raised when authentication token has expired."""

    def __init__(self):
        super().__init__(status_code=401, translation_key="errors.auth.token_expired")


class SessionExpiredException(TranslatableHTTPException):
    """Raised when session has expired."""

    def __init__(self):
        super().__init__(status_code=401, translation_key="errors.auth.session_expired")


class UnauthorizedException(TranslatableHTTPException):
    """Raised when user is not authenticated."""

    def __init__(self):
        super().__init__(status_code=401, translation_key="errors.auth.unauthorized")


class ForbiddenException(TranslatableHTTPException):
    """Raised when user doesn't have permission."""

    def __init__(self):
        super().__init__(status_code=403, translation_key="errors.auth.forbidden")


# ===============================
# Quiz exceptions
# ===============================


class QuizSessionNotFoundException(TranslatableHTTPException):
    """Raised when quiz session is not found."""

    def __init__(self):
        super().__init__(
            status_code=404, translation_key="errors.quiz.session_not_found"
        )


class QuizSessionExpiredException(TranslatableHTTPException):
    """Raised when quiz session has expired."""

    def __init__(self):
        super().__init__(status_code=410, translation_key="errors.quiz.session_expired")


class QuizAlreadyCompletedException(TranslatableHTTPException):
    """Raised when quiz has already been completed."""

    def __init__(self):
        super().__init__(
            status_code=409, translation_key="errors.quiz.already_completed"
        )


class InvalidQuizAnswerException(TranslatableHTTPException):
    """Raised when quiz answer is invalid."""

    def __init__(self, question_id: str):
        super().__init__(
            status_code=400,
            translation_key="errors.quiz.invalid_answer",
            question_id=question_id,
        )


# ===============================
# Webhook exceptions
# ===============================


class InvalidWebhookSignatureException(TranslatableHTTPException):
    """Raised when webhook signature is invalid."""

    def __init__(self):
        super().__init__(
            status_code=401, translation_key="errors.webhook.invalid_signature"
        )


class WebhookRateLimitException(TranslatableHTTPException):
    """Raised when webhook rate limit is exceeded."""

    def __init__(self, retry_after: int):
        super().__init__(
            status_code=429,
            translation_key="errors.webhook.rate_limit_exceeded",
            retry_after=retry_after,
            headers={"Retry-After": str(retry_after)},
        )


# ===============================
# Saga exceptions
# ===============================


class SagaExecutionFailedException(TranslatableHTTPException):
    """Raised when saga execution fails."""

    def __init__(self, saga_id: str):
        super().__init__(
            status_code=500,
            translation_key="errors.saga.execution_failed",
            saga_id=saga_id,
        )


class SagaCompensationFailedException(TranslatableHTTPException):
    """Raised when saga compensation fails."""

    def __init__(self, step: str):
        super().__init__(
            status_code=500,
            translation_key="errors.saga.compensation_failed",
            step=step,
        )


class SagaTimeoutException(TranslatableHTTPException):
    """Raised when saga operation times out."""

    def __init__(self, timeout: int):
        super().__init__(
            status_code=408, translation_key="errors.saga.timeout", timeout=timeout
        )


# ===============================
# Flow exceptions
# ===============================


class FlowNotFoundException(TranslatableHTTPException):
    """Raised when flow is not found."""

    def __init__(self, patient_id: str):
        super().__init__(
            status_code=404,
            translation_key="errors.flow.not_found",
            patient_id=patient_id,
        )


class InvalidFlowStateException(TranslatableHTTPException):
    """Raised when flow state is invalid."""

    def __init__(self, state: str):
        super().__init__(
            status_code=400, translation_key="errors.flow.invalid_state", state=state
        )


# ===============================
# Validation exceptions
# ===============================


class RequiredFieldException(TranslatableHTTPException):
    """Raised when required field is missing."""

    def __init__(self, field: str):
        super().__init__(
            status_code=422,
            translation_key="errors.validation.required_field",
            field=field,
        )


class InvalidFormatException(TranslatableHTTPException):
    """Raised when field format is invalid."""

    def __init__(self, field: str):
        super().__init__(
            status_code=422,
            translation_key="errors.validation.invalid_format",
            field=field,
        )


# ===============================
# Server exceptions
# ===============================


class InternalServerErrorException(TranslatableHTTPException):
    """Raised for internal server errors."""

    def __init__(self):
        super().__init__(
            status_code=500, translation_key="errors.server.internal_error"
        )


class ServiceUnavailableException(TranslatableHTTPException):
    """Raised when service is unavailable."""

    def __init__(self):
        super().__init__(
            status_code=503, translation_key="errors.server.service_unavailable"
        )


class DatabaseErrorException(TranslatableHTTPException):
    """Raised when database error occurs."""

    def __init__(self):
        super().__init__(
            status_code=500, translation_key="errors.server.database_error"
        )
