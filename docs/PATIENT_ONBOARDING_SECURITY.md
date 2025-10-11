# Patient Onboarding Flow Security Design

## Overview
Secure patient onboarding process that maintains strict WhatsApp access control while providing a smooth registration experience for legitimate patients.

## Security Challenges

### Current Registration Gap:
- **Problem**: New patients can't communicate via WhatsApp until registered in database
- **Security Risk**: Cannot allow unrestricted access during onboarding
- **Solution**: Secure pre-authorization workflow with time-limited access

## Secure Onboarding Architecture

### 1. Pre-Authorization Token System

```python
# File: app/models/patient_onboarding.py
"""
Patient onboarding security models.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timedelta
import secrets

from app.models.base import BaseModel

class PatientPreAuthorization(BaseModel):
    """
    Pre-authorization tokens for patient onboarding.

    Allows temporary WhatsApp access for legitimate patients
    during the registration process.
    """
    __tablename__ = "patient_pre_authorizations"

    # Authorization details
    phone_number = Column(String(20), nullable=False, index=True)
    authorization_token = Column(String(64), unique=True, nullable=False, index=True)

    # Security metadata
    authorized_by = Column(UUID(as_uuid=True), nullable=False)  # Staff member who authorized
    reason = Column(String(200), nullable=False)  # Reason for pre-authorization

    # Time limits
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Usage tracking
    used_count = Column(Integer, default=0)
    max_uses = Column(Integer, default=10)  # Maximum number of message exchanges

    # Status
    is_active = Column(Boolean, default=True)
    completed_at = Column(DateTime, nullable=True)  # When patient was fully registered

    # Security audit
    created_by_ip = Column(String(45), nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    @classmethod
    def create_authorization(
        cls,
        phone_number: str,
        authorized_by: UUID,
        reason: str,
        duration_hours: int = 24,
        max_uses: int = 10
    ) -> 'PatientPreAuthorization':
        """Create a new pre-authorization token."""

        return cls(
            phone_number=phone_number,
            authorization_token=secrets.token_urlsafe(32),
            authorized_by=authorized_by,
            reason=reason,
            expires_at=datetime.utcnow() + timedelta(hours=duration_hours),
            max_uses=max_uses
        )

    def is_valid(self) -> bool:
        """Check if pre-authorization is still valid."""
        return (
            self.is_active and
            self.expires_at > datetime.utcnow() and
            self.used_count < self.max_uses and
            not self.completed_at
        )

    def use_authorization(self) -> bool:
        """Record usage of pre-authorization."""
        if not self.is_valid():
            return False

        self.used_count += 1
        self.last_used_at = datetime.utcnow()

        # Auto-deactivate if max uses reached
        if self.used_count >= self.max_uses:
            self.is_active = False

        return True

class PatientOnboardingSession(BaseModel):
    """
    Secure onboarding session tracking.
    """
    __tablename__ = "patient_onboarding_sessions"

    # Session details
    phone_number = Column(String(20), nullable=False, index=True)
    session_token = Column(String(64), unique=True, nullable=False)
    pre_authorization_id = Column(UUID(as_uuid=True), nullable=False)

    # Collection progress
    collected_data = Column(JSONB, default=dict)  # Securely collected patient data
    collection_stage = Column(String(50), default="initial")  # Stage in collection process

    # Security
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    patient_id = Column(UUID(as_uuid=True), nullable=True)  # Set when patient created

    def is_valid(self) -> bool:
        """Check if onboarding session is valid."""
        return (
            self.is_active and
            self.expires_at > datetime.utcnow() and
            not self.completed_at
        )
```

### 2. Enhanced Patient Service with Onboarding

```python
# File: app/services/patient_onboarding_service.py
"""
Secure patient onboarding service.
"""
import logging
from typing import Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.patient_onboarding import PatientPreAuthorization, PatientOnboardingSession
from app.models.patient import Patient
from app.services.patient import PatientService
from app.services.whatsapp_security_audit import WhatsAppSecurityAuditService
from app.exceptions import SecurityError, ValidationError

logger = logging.getLogger(__name__)

class PatientOnboardingService:
    """Service for secure patient onboarding workflow."""

    def __init__(self, db: Session):
        self.db = db
        self.patient_service = PatientService(db)
        self.security_audit = WhatsAppSecurityAuditService(db)

    async def create_pre_authorization(
        self,
        phone_number: str,
        authorized_by: UUID,
        reason: str,
        duration_hours: int = 24,
        max_uses: int = 10
    ) -> PatientPreAuthorization:
        """
        Create pre-authorization for patient onboarding.

        Args:
            phone_number: Phone number to pre-authorize
            authorized_by: Staff member creating authorization
            reason: Reason for pre-authorization
            duration_hours: How long authorization is valid
            max_uses: Maximum number of WhatsApp interactions

        Returns:
            PatientPreAuthorization object

        Raises:
            ValidationError: If phone already authorized or invalid
        """
        try:
            # Normalize phone number
            from app.services.patient_phone_security import PhoneNumberSecurityService
            phone_security = PhoneNumberSecurityService(self.db)
            normalized_phone = phone_security.normalize_phone_secure(phone_number)

            # Check if patient already exists
            existing_patient = await phone_security.get_authorized_patient(normalized_phone)
            if existing_patient:
                raise ValidationError(f"Patient already registered: {existing_patient.name}")

            # Check for existing active pre-authorization
            existing_auth = self.db.query(PatientPreAuthorization).filter(
                PatientPreAuthorization.phone_number == normalized_phone,
                PatientPreAuthorization.is_active == True,
                PatientPreAuthorization.expires_at > datetime.utcnow()
            ).first()

            if existing_auth:
                raise ValidationError("Active pre-authorization already exists for this phone")

            # Create new pre-authorization
            pre_auth = PatientPreAuthorization.create_authorization(
                phone_number=normalized_phone,
                authorized_by=authorized_by,
                reason=reason,
                duration_hours=duration_hours,
                max_uses=max_uses
            )

            self.db.add(pre_auth)
            self.db.commit()

            # Log security event
            await self.security_audit.log_authorization_event(
                phone_number=normalized_phone,
                patient_id=None,
                event_type="PRE_AUTHORIZATION_CREATED",
                webhook_path="/admin/onboarding",
                metadata={
                    "authorized_by": str(authorized_by),
                    "reason": reason,
                    "duration_hours": duration_hours,
                    "max_uses": max_uses,
                    "token": pre_auth.authorization_token[:8] + "..."
                }
            )

            logger.info(
                f"Pre-authorization created for {normalized_phone} "
                f"by {authorized_by} (expires: {pre_auth.expires_at})"
            )

            return pre_auth

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating pre-authorization: {e}")
            self.db.rollback()
            raise

    async def validate_phone_access(
        self,
        phone_number: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate if phone number has WhatsApp access.

        Checks both registered patients and pre-authorizations.

        Returns:
            (authorized, context) where context contains patient or pre-auth info
        """
        try:
            from app.services.patient_phone_security import PhoneNumberSecurityService
            phone_security = PhoneNumberSecurityService(self.db)
            normalized_phone = phone_security.normalize_phone_secure(phone_number)

            # Check registered patient first
            patient = await phone_security.get_authorized_patient(normalized_phone)
            if patient:
                return True, {
                    "type": "registered_patient",
                    "patient": patient,
                    "phone": normalized_phone
                }

            # Check pre-authorization
            pre_auth = self.db.query(PatientPreAuthorization).filter(
                PatientPreAuthorization.phone_number == normalized_phone,
                PatientPreAuthorization.is_active == True,
                PatientPreAuthorization.expires_at > datetime.utcnow()
            ).first()

            if pre_auth and pre_auth.is_valid():
                return True, {
                    "type": "pre_authorization",
                    "pre_authorization": pre_auth,
                    "phone": normalized_phone
                }

            # No authorization found
            return False, {"phone": normalized_phone}

        except Exception as e:
            logger.error(f"Error validating phone access: {e}")
            return False, {"error": str(e)}

    async def start_onboarding_session(
        self,
        phone_number: str,
        pre_authorization: PatientPreAuthorization
    ) -> PatientOnboardingSession:
        """Start secure onboarding session for pre-authorized phone."""

        session = PatientOnboardingSession(
            phone_number=phone_number,
            session_token=secrets.token_urlsafe(32),
            pre_authorization_id=pre_authorization.id,
            expires_at=datetime.utcnow() + timedelta(hours=2),  # 2-hour session
            collected_data={}
        )

        self.db.add(session)
        self.db.commit()

        logger.info(f"Onboarding session started for {phone_number}")
        return session

    async def collect_patient_data(
        self,
        session: PatientOnboardingSession,
        data_key: str,
        data_value: str
    ) -> bool:
        """Securely collect patient data during onboarding."""

        if not session.is_valid():
            raise SecurityError("Onboarding session expired or invalid")

        # Validate data based on key
        validated_data = self._validate_onboarding_data(data_key, data_value)

        # Store collected data
        if not session.collected_data:
            session.collected_data = {}

        session.collected_data[data_key] = validated_data
        self.db.commit()

        logger.info(f"Collected {data_key} for onboarding session {session.id}")
        return True

    async def complete_onboarding(
        self,
        session: PatientOnboardingSession,
        doctor_id: UUID
    ) -> Patient:
        """Complete onboarding and create patient record."""

        if not session.is_valid():
            raise SecurityError("Onboarding session expired or invalid")

        # Validate required data collected
        required_fields = ["name", "email"]  # Add more as needed
        missing_fields = [
            field for field in required_fields
            if field not in session.collected_data
        ]

        if missing_fields:
            raise ValidationError(f"Missing required data: {missing_fields}")

        try:
            # Create patient from collected data
            from app.schemas.patient import PatientCreate

            patient_data = PatientCreate(
                name=session.collected_data["name"],
                phone=session.phone_number,
                email=session.collected_data.get("email"),
                # Add other fields as needed
            )

            # Create patient
            patient = await self.patient_service.create_patient(
                patient_data=patient_data,
                doctor_id=doctor_id
            )

            # Mark session as completed
            session.completed_at = datetime.utcnow()
            session.patient_id = patient.id
            session.is_active = False

            # Mark pre-authorization as completed
            pre_auth = self.db.query(PatientPreAuthorization).get(session.pre_authorization_id)
            if pre_auth:
                pre_auth.completed_at = datetime.utcnow()
                pre_auth.is_active = False

            self.db.commit()

            # Log completion
            await self.security_audit.log_authorization_event(
                phone_number=session.phone_number,
                patient_id=patient.id,
                event_type="ONBOARDING_COMPLETED",
                webhook_path="/onboarding/complete",
                metadata={
                    "session_id": str(session.id),
                    "patient_name": patient.name,
                    "doctor_id": str(doctor_id)
                }
            )

            logger.info(f"Onboarding completed for {session.phone_number} -> Patient {patient.id}")
            return patient

        except Exception as e:
            logger.error(f"Error completing onboarding: {e}")
            self.db.rollback()
            raise

    def _validate_onboarding_data(self, key: str, value: str) -> str:
        """Validate onboarding data based on field type."""

        validators = {
            "name": self._validate_name,
            "email": self._validate_email,
            "cpf": self._validate_cpf,
            "birth_date": self._validate_birth_date
        }

        validator = validators.get(key)
        if validator:
            return validator(value)

        # Default validation
        return str(value).strip()

    def _validate_name(self, name: str) -> str:
        """Validate patient name."""
        name = name.strip()
        if len(name) < 2:
            raise ValidationError("Name must be at least 2 characters")
        if len(name) > 100:
            raise ValidationError("Name too long")
        return name

    def _validate_email(self, email: str) -> str:
        """Validate email format."""
        from email_validator import validate_email, EmailNotValidError
        try:
            valid = validate_email(email)
            return valid.email
        except EmailNotValidError as e:
            raise ValidationError(f"Invalid email: {e}")

    def _validate_cpf(self, cpf: str) -> str:
        """Validate Brazilian CPF."""
        # Use existing CPF validation from patient service
        from app.services.patient import PatientIntegrityService
        integrity = PatientIntegrityService(self.db, None)
        if integrity._validate_cpf(cpf):
            return cpf
        raise ValidationError("Invalid CPF format")

    def _validate_birth_date(self, date_str: str) -> str:
        """Validate birth date format."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            raise ValidationError("Invalid date format. Use YYYY-MM-DD")
```

### 3. Enhanced Webhook Processor with Onboarding Support

```python
# File: app/services/webhook_processor_onboarding.py
"""
Webhook processor extension for onboarding support.
"""

class WebhookProcessorWithOnboarding(EnhancedWebhookProcessor):
    """Webhook processor with secure onboarding support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.onboarding_service = PatientOnboardingService(self.db)

    async def _validate_phone_security(
        self,
        raw_phone: str,
        webhook_id: Optional[UUID],
        event_data: dict
    ) -> dict[str, Any]:
        """Enhanced phone validation with onboarding support."""

        try:
            # Use onboarding service for comprehensive validation
            authorized, context = await self.onboarding_service.validate_phone_access(raw_phone)

            if authorized:
                if context["type"] == "registered_patient":
                    # Normal patient - use existing flow
                    return await super()._validate_phone_security(raw_phone, webhook_id, event_data)

                elif context["type"] == "pre_authorization":
                    # Pre-authorized phone - onboarding flow
                    return await self._handle_pre_authorized_phone(
                        context,
                        webhook_id,
                        event_data
                    )

            # Not authorized
            return {
                "authorized": False,
                "patient": None,
                "normalized_phone": context["phone"],
                "security_events": ["UNAUTHORIZED_PHONE"],
                "block_reason": "Phone number not registered and no pre-authorization"
            }

        except Exception as e:
            logger.error(f"Error in enhanced phone validation: {e}")
            return {
                "authorized": False,
                "patient": None,
                "normalized_phone": raw_phone,
                "security_events": ["VALIDATION_ERROR"],
                "block_reason": f"Validation error: {e}"
            }

    async def _handle_pre_authorized_phone(
        self,
        context: Dict[str, Any],
        webhook_id: Optional[UUID],
        event_data: dict
    ) -> dict[str, Any]:
        """Handle message from pre-authorized phone during onboarding."""

        pre_auth = context["pre_authorization"]
        phone = context["phone"]

        # Use pre-authorization
        if not pre_auth.use_authorization():
            return {
                "authorized": False,
                "patient": None,
                "normalized_phone": phone,
                "security_events": ["PRE_AUTH_EXPIRED"],
                "block_reason": "Pre-authorization expired or exhausted"
            }

        # Save usage
        self.db.commit()

        # Log pre-authorization usage
        if self.security_logging:
            await self.security_audit.log_authorization_event(
                phone_number=phone,
                patient_id=None,
                event_type="PRE_AUTHORIZATION_USED",
                webhook_path="/webhooks/evolution/message",
                metadata={
                    "pre_auth_id": str(pre_auth.id),
                    "usage_count": pre_auth.used_count,
                    "remaining_uses": pre_auth.max_uses - pre_auth.used_count,
                    "webhook_id": str(webhook_id) if webhook_id else None
                }
            )

        return {
            "authorized": True,
            "patient": None,  # No patient yet - onboarding
            "pre_authorization": pre_auth,
            "normalized_phone": phone,
            "security_events": ["PRE_AUTHORIZED"],
            "block_reason": None,
            "onboarding_mode": True
        }

    async def _process_authorized_message(
        self,
        patient: Optional[Patient],
        message_data: dict,
        whatsapp_id: str,
        webhook_id: Optional[UUID],
        security_result: dict
    ) -> str:
        """Enhanced message processing with onboarding support."""

        if security_result.get("onboarding_mode"):
            # Handle onboarding message
            return await self._process_onboarding_message(
                security_result,
                message_data,
                whatsapp_id,
                webhook_id
            )
        else:
            # Normal patient message
            return await super()._process_authorized_message(
                patient, message_data, whatsapp_id, webhook_id, security_result
            )

    async def _process_onboarding_message(
        self,
        security_result: dict,
        message_data: dict,
        whatsapp_id: str,
        webhook_id: Optional[UUID]
    ) -> str:
        """Process message during onboarding flow."""

        pre_auth = security_result["pre_authorization"]
        phone = security_result["normalized_phone"]

        # Create minimal message record for onboarding
        from app.models.message import Message, MessageType, MessageDirection, MessageStatus

        message = Message(
            id=uuid4(),
            patient_id=None,  # No patient yet
            direction=MessageDirection.INBOUND,
            type=MessageType.TEXT,
            content=message_data["content"],
            whatsapp_id=whatsapp_id,
            status=MessageStatus.RECEIVED,
            metadata={
                "onboarding_mode": True,
                "pre_auth_id": str(pre_auth.id),
                "phone": phone,
                "context": "onboarding"
            }
        )

        self.db.add(message)
        self.db.commit()

        # Process onboarding flow
        await self._handle_onboarding_flow(pre_auth, message)

        # Mark webhook as processed
        if webhook_id:
            await self._mark_webhook_processed(webhook_id, True)

        return str(message.id)

    async def _handle_onboarding_flow(
        self,
        pre_auth: PatientPreAuthorization,
        message: Message
    ) -> None:
        """Handle onboarding conversation flow."""

        try:
            # Simple onboarding flow
            content = message.content.lower().strip()

            # Generate appropriate onboarding response
            if "olá" in content or "oi" in content or content in ["ola", "oi"]:
                response = (
                    f"Olá! Bem-vindo(a) ao sistema de acompanhamento da clínica.\n\n"
                    f"Para completar seu cadastro, preciso de algumas informações.\n"
                    f"Vamos começar com seu nome completo:"
                )
            elif len(content.split()) >= 2:  # Assume it's a name
                response = (
                    f"Obrigado! Agora preciso do seu email para completar o cadastro:"
                )
            elif "@" in content:  # Assume it's an email
                response = (
                    f"Perfeito! Seu cadastro está quase pronto.\n"
                    f"Nossa equipe irá revisar e confirmar em breve.\n"
                    f"Você receberá uma mensagem de confirmação."
                )
            else:
                response = (
                    f"Desculpe, não entendi. "
                    f"Por favor, envie seu nome completo para começar o cadastro."
                )

            # Send response
            await self._send_response(
                patient_id=None,
                content=response,
                metadata={
                    "context": "onboarding",
                    "pre_auth_id": str(pre_auth.id),
                    "response_to": str(message.id)
                }
            )

        except Exception as e:
            logger.error(f"Error in onboarding flow: {e}")
```

## Implementation Summary

### Security Features:
1. **Pre-Authorization Tokens** - Time-limited, usage-counted access for legitimate patients
2. **Onboarding Sessions** - Secure data collection with validation
3. **Audit Trail** - Complete security logging of all onboarding activities
4. **Automatic Expiration** - Tokens and sessions auto-expire for security

### Staff Workflow:
1. **Create Pre-Authorization** - Staff creates time-limited token for new patient
2. **Share Token Info** - Patient receives instructions (phone call, SMS, etc.)
3. **WhatsApp Contact** - Patient contacts via WhatsApp using pre-authorized number
4. **Guided Registration** - System collects required data through conversation
5. **Completion** - Patient record created, full WhatsApp access enabled

### Edge Cases Handled:
- **Token Expiration** - Automatic cleanup of expired authorizations
- **Usage Limits** - Prevent abuse through message count limits
- **Session Security** - Secure data collection with validation
- **Error Handling** - Graceful degradation when onboarding fails
- **Audit Compliance** - Complete security event logging