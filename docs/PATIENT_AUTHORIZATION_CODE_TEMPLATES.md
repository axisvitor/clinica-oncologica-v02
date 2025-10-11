# Patient Authorization Implementation Code Templates

## 1. Patient Authorization Middleware

```python
# File: app/middleware/patient_authorization.py
"""
Patient Authorization Middleware for WhatsApp Security

Enforces strict patient-only access by validating phone numbers
against registered patients before processing any WhatsApp communication.
"""
import logging
import time
from typing import Optional, Callable, Awaitable, Set
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.patient_phone_security import PhoneNumberSecurityService
from app.services.whatsapp_security_audit import WhatsAppSecurityAuditService
from app.config import settings

logger = logging.getLogger(__name__)

class PatientAuthorizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce patient-only WhatsApp access.

    Security Features:
    - Validates phone numbers against registered patients
    - Blocks all non-patient communications
    - Comprehensive security logging
    - Rate limiting per phone number
    - Real-time security monitoring
    """

    def __init__(
        self,
        app: ASGIApp,
        enabled: bool = True,
        whatsapp_paths: Optional[list[str]] = None,
        rate_limit_per_phone: int = 10,  # requests per minute
        security_mode: str = "strict"  # "strict" | "permissive" | "disabled"
    ):
        super().__init__(app)
        self.enabled = enabled
        self.whatsapp_paths = whatsapp_paths or ["/webhooks/evolution/"]
        self.rate_limit_per_phone = rate_limit_per_phone
        self.security_mode = security_mode

        # Rate limiting tracking
        self.phone_requests: dict[str, list[float]] = {}

        logger.info(
            f"Patient Authorization Middleware initialized: "
            f"enabled={enabled}, mode={security_mode}, "
            f"rate_limit={rate_limit_per_phone}/min"
        )

    def _is_whatsapp_path(self, path: str) -> bool:
        """Check if path requires patient authorization."""
        return any(path.startswith(wp) for wp in self.whatsapp_paths)

    def _extract_phone_from_webhook(self, webhook_data: dict) -> Optional[str]:
        """Extract phone number from webhook data safely."""
        try:
            # Handle Evolution API webhook format
            data = webhook_data.get("data", {})
            key = data.get("key", {})
            remote_jid = key.get("remoteJid", "")

            if "@" in remote_jid:
                phone = remote_jid.split("@")[0]
                return phone

            return None
        except Exception as e:
            logger.error(f"Error extracting phone from webhook: {e}")
            return None

    def _check_rate_limit(self, phone: str) -> bool:
        """Check rate limit for specific phone number."""
        current_time = time.time()

        # Initialize or clean old requests
        if phone not in self.phone_requests:
            self.phone_requests[phone] = []

        # Remove requests older than 1 minute
        self.phone_requests[phone] = [
            req_time for req_time in self.phone_requests[phone]
            if current_time - req_time < 60
        ]

        # Check rate limit
        if len(self.phone_requests[phone]) >= self.rate_limit_per_phone:
            return False

        # Record this request
        self.phone_requests[phone].append(current_time)
        return True

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and enforce patient authorization."""

        # Skip if middleware disabled or not WhatsApp path
        if not self.enabled or not self._is_whatsapp_path(request.url.path):
            return await call_next(request)

        # Skip for non-POST requests (health checks, etc.)
        if request.method != "POST":
            return await call_next(request)

        try:
            # Parse webhook data
            webhook_data = await request.json()
            phone = self._extract_phone_from_webhook(webhook_data)

            if not phone:
                logger.warning("Could not extract phone number from webhook")
                return await self._security_block_response(
                    "Invalid webhook format",
                    request.url.path,
                    None,
                    "INVALID_FORMAT"
                )

            # Check rate limit for this phone
            if not self._check_rate_limit(phone):
                logger.warning(f"Rate limit exceeded for phone: {phone}")
                return await self._security_block_response(
                    "Rate limit exceeded",
                    request.url.path,
                    phone,
                    "RATE_LIMITED"
                )

            # Get database session
            db = next(get_db())

            try:
                # Validate patient authorization
                phone_security = PhoneNumberSecurityService(db)
                security_audit = WhatsAppSecurityAuditService(db)

                # Normalize and validate phone
                normalized_phone = phone_security.normalize_phone_secure(phone)
                patient = await phone_security.get_authorized_patient(normalized_phone)

                if patient:
                    # AUTHORIZED: Patient found
                    logger.info(f"Patient authorized: {patient.id} for phone {normalized_phone}")

                    # Log successful authorization
                    await security_audit.log_authorization_event(
                        phone_number=normalized_phone,
                        patient_id=patient.id,
                        event_type="AUTHORIZED",
                        webhook_path=request.url.path,
                        metadata={"patient_name": patient.name}
                    )

                    # Add patient context to request
                    request.state.authorized_patient = patient
                    request.state.normalized_phone = normalized_phone

                    # Recreate request with body for next handler
                    async def receive():
                        return {"type": "http.request", "body": await request.body()}
                    request._receive = receive

                    return await call_next(request)

                else:
                    # BLOCKED: No patient found
                    return await self._security_block_response(
                        "Unauthorized phone number",
                        request.url.path,
                        normalized_phone,
                        "UNAUTHORIZED_PHONE",
                        db
                    )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error in patient authorization middleware: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal security error"}
            )

    async def _security_block_response(
        self,
        reason: str,
        path: str,
        phone: Optional[str],
        event_type: str,
        db: Optional[Session] = None
    ) -> JSONResponse:
        """Generate security block response and log event."""

        logger.warning(
            f"WhatsApp access BLOCKED: {reason} "
            f"(phone={phone}, path={path}, type={event_type})"
        )

        # Log security event if database available
        if db and phone:
            try:
                security_audit = WhatsAppSecurityAuditService(db)
                await security_audit.log_authorization_event(
                    phone_number=phone,
                    patient_id=None,
                    event_type=event_type,
                    webhook_path=path,
                    metadata={
                        "reason": reason,
                        "blocked": True,
                        "ip_address": getattr(request, "client", {}).get("host"),
                        "user_agent": request.headers.get("user-agent")
                    }
                )
            except Exception as e:
                logger.error(f"Failed to log security event: {e}")

        # Return security block response
        if self.security_mode == "strict":
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Access denied",
                    "code": "UNAUTHORIZED_PHONE",
                    "message": "This phone number is not authorized for WhatsApp communication"
                }
            )
        else:
            # In permissive mode, log but allow (for testing)
            return JSONResponse(
                status_code=200,
                content={
                    "status": "blocked_in_strict_mode",
                    "message": f"Would be blocked in strict mode: {reason}"
                }
            )
```

## 2. Phone Number Security Service

```python
# File: app/services/patient_phone_security.py
"""
Phone Number Security Service

Provides secure phone number validation, normalization, and patient lookup
with comprehensive security features and caching.
"""
import logging
import hashlib
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.patient import Patient
from app.utils.unified_cache import cache
from app.exceptions import SecurityError

logger = logging.getLogger(__name__)

class PhoneNumberSecurityService:
    """Service for secure phone number handling and patient authorization."""

    def __init__(self, db: Session):
        self.db = db

    def normalize_phone_secure(self, phone: str) -> str:
        """
        Normalize phone number with security validation.

        Args:
            phone: Raw phone number from webhook

        Returns:
            Normalized E.164 format phone number

        Raises:
            SecurityError: If phone format is invalid or suspicious
        """
        try:
            # Remove WhatsApp suffix
            if "@" in phone:
                phone = phone.split("@")[0]

            # Remove all non-digit characters except +
            cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

            # Security validation
            if len(cleaned) < 10 or len(cleaned) > 15:
                raise SecurityError(f"Invalid phone length: {len(cleaned)}")

            # Normalize to E.164 format
            if cleaned.startswith("+"):
                normalized = cleaned
            elif cleaned.startswith("55"):
                normalized = f"+{cleaned}"
            elif len(cleaned) >= 10:
                normalized = f"+55{cleaned}"
            else:
                raise SecurityError(f"Cannot normalize phone: {phone}")

            # Additional security checks
            if normalized.count("+") > 1:
                raise SecurityError("Multiple + signs in phone number")

            # Check for suspicious patterns (all same digits, etc.)
            digits_only = normalized.replace("+", "")
            if len(set(digits_only)) == 1:
                raise SecurityError("Suspicious phone pattern detected")

            logger.debug(f"Phone normalized securely: {phone} -> {normalized}")
            return normalized

        except SecurityError:
            raise
        except Exception as e:
            logger.error(f"Phone normalization error: {e}")
            raise SecurityError(f"Phone normalization failed: {phone}")

    @cache(ttl=300, key_prefix="patient_auth")
    async def get_authorized_patient(self, normalized_phone: str) -> Optional[Patient]:
        """
        Get patient by phone with security validation and caching.

        Args:
            normalized_phone: E.164 normalized phone number

        Returns:
            Patient if authorized, None if not found
        """
        try:
            # Primary lookup by exact match
            patient = self.db.query(Patient).filter(
                Patient.phone == normalized_phone
            ).first()

            if patient:
                logger.info(f"Patient found by exact match: {patient.id}")
                return patient

            # Secondary lookup without country code (for legacy compatibility)
            if normalized_phone.startswith("+55"):
                legacy_phone = normalized_phone[3:]  # Remove +55
                patient = self.db.query(Patient).filter(
                    Patient.phone == legacy_phone
                ).first()

                if patient:
                    logger.info(f"Patient found by legacy format: {patient.id}")
                    return patient

            # No patient found
            logger.warning(f"No authorized patient found for phone: {normalized_phone}")
            return None

        except Exception as e:
            logger.error(f"Error in patient authorization lookup: {e}")
            return None

    def get_phone_hash(self, phone: str) -> str:
        """Generate hash for phone number (for security logging)."""
        return hashlib.sha256(phone.encode()).hexdigest()[:12]
```

## 3. WhatsApp Security Audit Service

```python
# File: app/services/whatsapp_security_audit.py
"""
WhatsApp Security Audit Service

Comprehensive security logging and monitoring for WhatsApp communications.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings

logger = logging.getLogger(__name__)

class WhatsAppSecurityAuditService:
    """Service for WhatsApp security event logging and monitoring."""

    def __init__(self, db: Session):
        self.db = db

    async def log_authorization_event(
        self,
        phone_number: str,
        patient_id: Optional[UUID],
        event_type: str,
        webhook_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Log WhatsApp authorization event for security monitoring.

        Args:
            phone_number: Phone number involved
            patient_id: Patient ID if authorized
            event_type: Type of security event
            webhook_path: Webhook endpoint path
            metadata: Additional event metadata

        Returns:
            Event ID
        """
        try:
            event_id = uuid4()

            # Create security event record
            insert_stmt = text("""
                INSERT INTO whatsapp_security_events (
                    id, phone_number, patient_id, event_type, webhook_path,
                    metadata, created_at, ip_address, user_agent
                )
                VALUES (
                    :id, :phone_number, :patient_id, :event_type, :webhook_path,
                    :metadata, NOW(), :ip_address, :user_agent
                )
                RETURNING id
            """)

            result = self.db.execute(insert_stmt, {
                "id": str(event_id),
                "phone_number": phone_number,
                "patient_id": str(patient_id) if patient_id else None,
                "event_type": event_type,
                "webhook_path": webhook_path,
                "metadata": metadata or {},
                "ip_address": metadata.get("ip_address") if metadata else None,
                "user_agent": metadata.get("user_agent") if metadata else None
            })

            self.db.commit()

            # Send real-time alert for security events
            if event_type in ["UNAUTHORIZED_PHONE", "RATE_LIMITED", "SUSPICIOUS_ACTIVITY"]:
                await self._send_security_alert(event_type, phone_number, metadata)

            logger.info(
                f"Security event logged: {event_type} for phone {phone_number} "
                f"(event_id={event_id})"
            )

            return event_id

        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
            self.db.rollback()
            raise

    async def _send_security_alert(
        self,
        event_type: str,
        phone_number: str,
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Send real-time security alert to monitoring systems."""
        try:
            # Integration with monitoring systems (Slack, email, etc.)
            alert_data = {
                "alert_type": "whatsapp_security",
                "severity": "high" if event_type == "UNAUTHORIZED_PHONE" else "medium",
                "event_type": event_type,
                "phone_number": phone_number,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata
            }

            # TODO: Implement actual alerting (Slack, email, monitoring dashboard)
            logger.warning(f"SECURITY ALERT: {alert_data}")

        except Exception as e:
            logger.error(f"Failed to send security alert: {e}")
```

## 4. Database Migration

```sql
-- File: migrations/add_whatsapp_security_tables.sql
-- WhatsApp Security Tables Migration

-- Table for WhatsApp security event logging
CREATE TABLE IF NOT EXISTS whatsapp_security_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(20) NOT NULL,
    patient_id UUID REFERENCES patients(id),
    event_type VARCHAR(50) NOT NULL, -- AUTHORIZED, UNAUTHORIZED_PHONE, RATE_LIMITED, etc.
    webhook_path VARCHAR(200) NOT NULL,
    metadata JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for security event queries
CREATE INDEX idx_whatsapp_security_events_phone ON whatsapp_security_events(phone_number);
CREATE INDEX idx_whatsapp_security_events_patient ON whatsapp_security_events(patient_id);
CREATE INDEX idx_whatsapp_security_events_type ON whatsapp_security_events(event_type);
CREATE INDEX idx_whatsapp_security_events_created ON whatsapp_security_events(created_at);

-- Table for patient phone authorization tracking
CREATE TABLE IF NOT EXISTS patient_phone_authorizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id),
    phone_number VARCHAR(20) NOT NULL,
    authorized_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    authorized_by UUID REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- active, suspended, revoked
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(patient_id, phone_number)
);

-- Indexes for authorization tracking
CREATE INDEX idx_patient_phone_auth_patient ON patient_phone_authorizations(patient_id);
CREATE INDEX idx_patient_phone_auth_phone ON patient_phone_authorizations(phone_number);
CREATE INDEX idx_patient_phone_auth_status ON patient_phone_authorizations(status);

-- Add security metadata to existing webhook_events table
ALTER TABLE webhook_events
ADD COLUMN IF NOT EXISTS security_validated BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS patient_authorized BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS security_metadata JSONB DEFAULT '{}';

-- Create index for security queries
CREATE INDEX IF NOT EXISTS idx_webhook_events_security ON webhook_events(security_validated, patient_authorized);
```