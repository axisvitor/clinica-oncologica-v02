"""
Patient Authorization Middleware for WhatsApp Access Control.

Provides comprehensive patient validation and security monitoring for
all WhatsApp-related operations with proper logging and rate limiting.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import status
from fastapi.responses import JSONResponse

from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.core.security_config import get_security_config
from app.services.security_monitor import SecurityMonitor

logger = logging.getLogger(__name__)


class PatientAuthorizationMiddleware:
    """
    Middleware for validating patient authorization for WhatsApp access.

    Features:
    - Multi-strategy phone number validation
    - Rate limiting for unauthorized attempts
    - Security event logging and monitoring
    - Phone number blocking after repeated violations
    - Backwards compatibility with existing validation logic
    """

    def __init__(self, db: Session):
        """Initialize middleware with database session."""
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.security_monitor = SecurityMonitor(db)
        self.security_config = get_security_config()

        # Rate limiting configuration
        self.max_attempts_per_hour = 5
        self.max_attempts_per_day = 15
        self.block_duration_hours = 24

        logger.info("PatientAuthorizationMiddleware initialized")

    async def validate_patient_access(
        self, phone: str, request_context: Optional[Dict[str, Any]] = None
    ) -> tuple[Optional[Patient], Dict[str, Any]]:
        """
        Validate patient access with comprehensive security checks.

        Args:
            phone: Phone number to validate
            request_context: Additional context (message content, metadata)

        Returns:
            Tuple of (Patient object if authorized, validation result dict)
        """
        validation_result = {
            "authorized": False,
            "patient": None,
            "reason": None,
            "attempt_count": 0,
            "should_block": False,
            "security_level": "low",
        }

        try:
            # Step 1: Normalize phone number
            normalized_phone = self._normalize_phone_comprehensive(phone)
            if not normalized_phone:
                validation_result.update(
                    {"reason": "invalid_phone_format", "security_level": "medium"}
                )
                await self._log_validation_attempt(
                    phone, validation_result, request_context
                )
                return None, validation_result

            # Step 2: Check if phone is already blocked
            is_blocked = await self.security_monitor.is_phone_blocked(normalized_phone)
            if is_blocked:
                validation_result.update(
                    {
                        "reason": "phone_blocked",
                        "should_block": True,
                        "security_level": "high",
                    }
                )
                await self._log_validation_attempt(
                    phone, validation_result, request_context
                )
                return None, validation_result

            # Step 3: Multi-strategy patient lookup
            patient = await self._find_patient_multi_strategy(normalized_phone)

            if patient:
                # Patient found - authorize access
                validation_result.update(
                    {
                        "authorized": True,
                        "patient": patient,
                        "reason": "patient_found",
                        "security_level": "low",
                    }
                )

                # Log successful authorization (for audit trail)
                await self.security_monitor.log_authorized_access(
                    phone=normalized_phone,
                    patient_id=patient.id,
                    source_metadata=request_context or {},
                )

                logger.info(
                    f"Patient access authorized for {normalized_phone} (patient_id: {patient.id})"
                )
                return patient, validation_result

            # Step 4: Patient not found - security checks
            attempt_count = await self.security_monitor.get_attempt_count(
                normalized_phone
            )
            should_block = await self.security_monitor.should_block_phone(
                normalized_phone
            )

            validation_result.update(
                {
                    "reason": "patient_not_found",
                    "attempt_count": attempt_count,
                    "should_block": should_block,
                    "security_level": "high" if attempt_count > 3 else "medium",
                }
            )

            # Log unauthorized attempt
            await self.security_monitor.log_unauthorized_access(
                phone=normalized_phone,
                message_content=request_context.get("message_content", "")
                if request_context
                else "",
                source_metadata=request_context or {},
            )

            # Block phone if threshold exceeded
            if should_block:
                await self.security_monitor.block_phone(
                    phone=normalized_phone,
                    reason=f"Exceeded unauthorized attempt threshold ({attempt_count} attempts)",
                    duration_hours=self.block_duration_hours,
                )
                logger.warning(
                    f"Phone {normalized_phone} blocked after {attempt_count} unauthorized attempts"
                )

            logger.warning(
                f"Patient access denied for {normalized_phone} "
                f"(attempt #{attempt_count}, blocked={should_block})"
            )

            return None, validation_result

        except Exception as e:
            logger.error(
                f"Error validating patient access for {phone}: {e}", exc_info=True
            )
            validation_result.update(
                {"reason": "validation_error", "security_level": "high"}
            )
            return None, validation_result

    async def _find_patient_multi_strategy(self, phone: str) -> Optional[Patient]:
        """
        Find patient using multiple phone format strategies for maximum compatibility.

        Strategies:
        1. E.164 format with + prefix (+55...)
        2. Without + prefix (55...)
        3. Add country code if missing (+55{phone})
        4. Remove country code (last 10-11 digits)
        5. Alternative format variations

        Args:
            phone: Normalized phone number

        Returns:
            Patient object if found, None otherwise
        """
        search_attempts = []

        try:
            # Strategy 1: E.164 format with +
            e164_phone = self._to_e164_format(phone)
            search_attempts.append(("e164_with_plus", e164_phone))
            patient = await self._safe_patient_lookup(e164_phone)
            if patient:
                logger.debug(f"Patient found with E.164 format: {e164_phone}")
                return patient

            # Strategy 2: Without + prefix
            without_plus = e164_phone.lstrip("+")
            search_attempts.append(("without_plus", without_plus))
            patient = await self._safe_patient_lookup(without_plus)
            if patient:
                logger.debug(f"Patient found without + prefix: {without_plus}")
                return patient

            # Strategy 3: Add country code if not present
            if not phone.startswith("55") and not phone.startswith("+55"):
                with_country = f"+55{phone}"
                search_attempts.append(("with_country_plus", with_country))
                patient = await self._safe_patient_lookup(with_country)
                if patient:
                    logger.debug(
                        f"Patient found with added country code: {with_country}"
                    )
                    return patient

                # Also try without +
                with_country_no_plus = f"55{phone}"
                search_attempts.append(("with_country_no_plus", with_country_no_plus))
                patient = await self._safe_patient_lookup(with_country_no_plus)
                if patient:
                    logger.debug(
                        f"Patient found with country code (no +): {with_country_no_plus}"
                    )
                    return patient

            # Strategy 4: Remove country code (last 10-11 digits for Brazilian numbers)
            if len(without_plus) > 11:
                local_11 = without_plus[-11:]
                local_10 = without_plus[-10:]

                search_attempts.extend([("local_11", local_11), ("local_10", local_10)])

                for local_number in [local_11, local_10]:
                    patient = await self._safe_patient_lookup(local_number)
                    if patient:
                        logger.debug(f"Patient found with local format: {local_number}")
                        return patient

            # Strategy 5: Alternative formatting (remove common prefixes)
            alternatives = self._generate_phone_alternatives(phone)
            for alt_desc, alt_phone in alternatives:
                search_attempts.append((alt_desc, alt_phone))
                patient = await self._safe_patient_lookup(alt_phone)
                if patient:
                    logger.debug(
                        f"Patient found with alternative format ({alt_desc}): {alt_phone}"
                    )
                    return patient

            # Log all search attempts for debugging
            logger.debug(
                f"Patient not found after comprehensive search. Attempts: "
                f"{[(desc, num) for desc, num in search_attempts]}"
            )

            return None

        except Exception as e:
            logger.error(
                f"Error in multi-strategy patient lookup for {phone}: {e}",
                exc_info=True,
            )
            return None

    async def _safe_patient_lookup(self, phone: str) -> Optional[Patient]:
        """Safely lookup patient with error handling."""
        try:
            return self.patient_repo.get_by_phone(phone)
        except Exception as e:
            logger.debug(f"Patient lookup failed for {phone}: {e}")
            return None

    def _normalize_phone_comprehensive(self, phone: str) -> Optional[str]:
        """
        Comprehensive phone number normalization with validation.

        Args:
            phone: Raw phone number

        Returns:
            Normalized phone number or None if invalid
        """
        if not phone:
            return None

        # Remove WhatsApp suffix
        if "@" in phone:
            phone = phone.split("@")[0]

        # Remove all non-digit characters except +
        cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

        # Validate minimum length (Brazilian numbers: 10-11 digits + country code)
        if len(cleaned.replace("+", "").replace("55", "", 1)) < 10:
            logger.debug(f"Phone too short after normalization: {cleaned}")
            return None

        # Remove leading zeros (but preserve +)
        if cleaned.startswith("+"):
            cleaned = "+" + cleaned[1:].lstrip("0")
        else:
            cleaned = cleaned.lstrip("0")

        logger.debug(f"Phone normalized: '{phone}' -> '{cleaned}'")
        return cleaned

    def _to_e164_format(self, phone: str) -> str:
        """Convert phone to E.164 format (+55...)."""
        cleaned = phone.lstrip("+")

        # Add country code if missing
        if not cleaned.startswith("55"):
            cleaned = f"55{cleaned}"

        return f"+{cleaned}"

    def _generate_phone_alternatives(self, phone: str) -> List[tuple[str, str]]:
        """Generate alternative phone number formats."""
        alternatives = []

        # Remove common prefixes/suffixes
        patterns_to_try = [
            ("no_leading_9", phone.lstrip("9")),
            ("no_leading_0", phone.lstrip("0")),
            (
                "no_country_prefix_55",
                phone.replace("55", "", 1) if phone.startswith("55") else phone,
            ),
        ]

        for desc, alt_phone in patterns_to_try:
            if alt_phone != phone and len(alt_phone) >= 10:
                alternatives.append((desc, alt_phone))

        return alternatives

    async def _log_validation_attempt(
        self,
        phone: str,
        validation_result: Dict[str, Any],
        request_context: Optional[Dict[str, Any]],
    ) -> None:
        """Log validation attempt for audit and monitoring."""
        try:
            log_data = {
                "phone": phone,
                "authorized": validation_result["authorized"],
                "reason": validation_result["reason"],
                "attempt_count": validation_result.get("attempt_count", 0),
                "security_level": validation_result["security_level"],
                "timestamp": datetime.utcnow().isoformat(),
                "context": request_context or {},
            }

            # Log at appropriate level based on security level
            if validation_result["security_level"] == "high":
                logger.warning(f"High-security validation event: {log_data}")
            elif validation_result["security_level"] == "medium":
                logger.info(f"Medium-security validation event: {log_data}")
            else:
                logger.debug(f"Low-security validation event: {log_data}")

        except Exception as e:
            logger.error(f"Failed to log validation attempt: {e}")

    async def create_authorization_response(
        self, validation_result: Dict[str, Any]
    ) -> JSONResponse:
        """
        Create appropriate HTTP response for authorization result.

        Args:
            validation_result: Result from validate_patient_access

        Returns:
            JSONResponse with appropriate status and message
        """
        if validation_result["authorized"]:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "Access authorized", "status": "success"},
            )

        # Determine response based on reason
        reason = validation_result["reason"]
        attempt_count = validation_result.get("attempt_count", 0)

        if reason == "phone_blocked":
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "message": "Phone number temporarily blocked due to security violations",
                    "status": "blocked",
                    "retry_after": "24 hours",
                },
            )
        elif reason == "patient_not_found":
            if attempt_count > 3:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "message": "Access denied - multiple unauthorized attempts detected",
                        "status": "security_violation",
                        "attempt_count": attempt_count,
                    },
                )
            else:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "message": "Phone number not registered for clinical follow-up",
                        "status": "unauthorized",
                        "attempt_count": attempt_count,
                    },
                )
        elif reason == "invalid_phone_format":
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message": "Invalid phone number format",
                    "status": "invalid_input",
                },
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "message": "Authorization validation error",
                    "status": "error",
                },
            )


# Utility functions for use in other services
async def validate_whatsapp_access(
    db: Session, phone: str, message_content: str = ""
) -> tuple[Optional[Patient], Dict[str, Any]]:
    """
    Standalone function for validating WhatsApp access.

    Args:
        db: Database session
        phone: Phone number to validate
        message_content: Message content for context

    Returns:
        Tuple of (Patient if authorized, validation result)
    """
    middleware = PatientAuthorizationMiddleware(db)

    request_context = {
        "message_content": message_content[:100],  # First 100 chars
        "source": "whatsapp",
        "timestamp": datetime.utcnow().isoformat(),
    }

    return await middleware.validate_patient_access(phone, request_context)


async def is_phone_blocked(db: Session, phone: str) -> bool:
    """
    Quick check if phone number is blocked.

    Args:
        db: Database session
        phone: Phone number to check

    Returns:
        True if phone is blocked
    """
    security_monitor = SecurityMonitor(db)
    return await security_monitor.is_phone_blocked(phone)
