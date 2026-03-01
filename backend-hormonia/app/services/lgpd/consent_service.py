"""
LGPD Consent Management Service.

QW-005: Implements consent management for LGPD compliance,
including consent tracking, revocation, and audit logging.
"""

import logging
import inspect
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.consent import Consent, ConsentType, ConsentStatus
from app.models.lgpd_audit import LGPDAuditLog, LGPDActionType, LGPDDataCategory
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class ConsentService:
    """
    Service for managing patient consent for data processing.

    QW-005: Provides LGPD-compliant consent management including:
    - Consent creation and tracking
    - Consent revocation
    - Consent validation
    - Audit logging of consent operations
    """

    # Default consent expiration period (2 years as per LGPD best practices)
    DEFAULT_EXPIRATION_DAYS = 730

    def __init__(self, db: Session | AsyncSession):
        """
        Initialize consent service.

        Args:
            db: Database session
        """
        self.db = db

    async def _resolve(self, maybe_awaitable: Any) -> Any:
        if inspect.isawaitable(maybe_awaitable):
            return await maybe_awaitable
        return maybe_awaitable

    async def _get_consent_by_id(self, consent_id: UUID) -> Optional[Consent]:
        result = await self._resolve(
            self.db.execute(select(Consent).where(Consent.id == consent_id).limit(1))
        )
        return result.scalars().first()

    async def create_consent(
        self,
        patient_id: UUID,
        consent_type: ConsentType,
        title: str,
        description: str,
        legal_text: Optional[str] = None,
        user_id: Optional[UUID] = None,
        expires_in_days: Optional[int] = None,
        is_required: bool = False,
        signature_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_context: Optional[Dict[str, Any]] = None,
    ) -> Consent:
        """
        Create a new consent record.

        Args:
            patient_id: Patient UUID
            consent_type: Type of consent
            title: Consent title
            description: Consent description
            legal_text: Optional legal text
            user_id: User registering the consent
            expires_in_days: Days until expiration
            is_required: Whether consent is required
            signature_data: Digital signature information
            metadata: Additional metadata
            request_context: Request context for audit

        Returns:
            Created Consent object
        """
        expires_at = None
        if expires_in_days:
            expires_at = now_sao_paulo() + timedelta(days=expires_in_days)
        elif self.DEFAULT_EXPIRATION_DAYS:
            expires_at = now_sao_paulo() + timedelta(
                days=self.DEFAULT_EXPIRATION_DAYS
            )

        consent = Consent(
            patient_id=patient_id,
            consent_type=consent_type,
            status=ConsentStatus.PENDING,
            title=title,
            description=description,
            legal_text=legal_text,
            consented_by_id=user_id,
            expires_at=expires_at,
            is_required=is_required,
            signature_data=signature_data,
            consent_metadata=metadata,
            version="1.0",
        )

        self.db.add(consent)
        await self._resolve(self.db.commit())
        await self._resolve(self.db.refresh(consent))

        # Log consent creation
        await self._log_consent_operation(
            action=LGPDActionType.CREATE,
            patient_id=patient_id,
            user_id=user_id,
            consent_id=consent.id,
            consent_type=consent_type,
            request_context=request_context,
        )

        logger.info(f"Created consent {consent.id} for patient {patient_id}")
        return consent

    async def grant_consent(
        self,
        consent_id: UUID,
        user_id: Optional[UUID] = None,
        signature_data: Optional[Dict[str, Any]] = None,
        request_context: Optional[Dict[str, Any]] = None,
    ) -> Consent:
        """
        Grant (accept) a consent.

        Args:
            consent_id: Consent UUID
            user_id: User granting consent
            signature_data: Digital signature
            request_context: Request context for audit

        Returns:
            Updated Consent object

        Raises:
            ValueError: If consent not found or already processed
        """
        consent = await self._get_consent_by_id(consent_id)
        if not consent:
            raise ValueError(f"Consent {consent_id} not found")

        if consent.status not in [ConsentStatus.PENDING, ConsentStatus.DENIED]:
            raise ValueError(f"Consent {consent_id} is already {consent.status.value}")

        consent.status = ConsentStatus.GRANTED
        consent.granted_at = now_sao_paulo()
        consent.consented_by_id = user_id
        if signature_data:
            consent.signature_data = signature_data

        await self._resolve(self.db.commit())
        await self._resolve(self.db.refresh(consent))

        # Log consent grant
        await self._log_consent_operation(
            action=LGPDActionType.CONSENT_GRANTED,
            patient_id=consent.patient_id,
            user_id=user_id,
            consent_id=consent.id,
            consent_type=consent.consent_type,
            request_context=request_context,
        )

        logger.info(f"Consent {consent_id} granted for patient {consent.patient_id}")
        return consent

    async def revoke_consent(
        self,
        consent_id: UUID,
        user_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        request_context: Optional[Dict[str, Any]] = None,
    ) -> Consent:
        """
        Revoke a previously granted consent.

        Args:
            consent_id: Consent UUID
            user_id: User revoking consent
            reason: Reason for revocation
            request_context: Request context for audit

        Returns:
            Updated Consent object

        Raises:
            ValueError: If consent not found or not granted
        """
        consent = await self._get_consent_by_id(consent_id)
        if not consent:
            raise ValueError(f"Consent {consent_id} not found")

        if consent.status != ConsentStatus.GRANTED:
            raise ValueError(
                f"Consent {consent_id} is not granted (current: {consent.status.value})"
            )

        consent.status = ConsentStatus.REVOKED
        consent.revoked_at = now_sao_paulo()
        consent.revocation_reason = reason

        await self._resolve(self.db.commit())
        await self._resolve(self.db.refresh(consent))

        # Log consent revocation
        await self._log_consent_operation(
            action=LGPDActionType.CONSENT_REVOKED,
            patient_id=consent.patient_id,
            user_id=user_id,
            consent_id=consent.id,
            consent_type=consent.consent_type,
            additional_data={"reason": reason},
            request_context=request_context,
        )

        logger.info(f"Consent {consent_id} revoked for patient {consent.patient_id}")
        return consent

    async def check_consent(
        self, patient_id: UUID, consent_type: ConsentType, purpose: Optional[str] = None
    ) -> bool:
        """
        Check if patient has granted consent for a specific type.

        Args:
            patient_id: Patient UUID
            consent_type: Type of consent to check
            purpose: Optional purpose for logging

        Returns:
            True if consent is granted and valid
        """
        now = now_sao_paulo()

        stmt = (
            select(Consent)
            .where(
                and_(
                    Consent.patient_id == patient_id,
                    Consent.consent_type == consent_type,
                    Consent.status == ConsentStatus.GRANTED,
                    Consent.is_active,
                    or_(Consent.expires_at.is_(None), Consent.expires_at > now),
                )
            )
            .limit(1)
        )

        result = await self._resolve(self.db.execute(stmt))
        consent = result.scalars().first()

        return consent is not None

    async def get_patient_consents(
        self,
        patient_id: UUID,
        include_expired: bool = False,
        include_revoked: bool = False,
    ) -> List[Consent]:
        """
        Get all consents for a patient.

        Args:
            patient_id: Patient UUID
            include_expired: Include expired consents
            include_revoked: Include revoked consents

        Returns:
            List of Consent objects
        """
        stmt = select(Consent).where(Consent.patient_id == patient_id, Consent.is_active)

        if not include_expired:
            now = now_sao_paulo()
            stmt = stmt.where(
                or_(Consent.expires_at.is_(None), Consent.expires_at > now)
            )

        if not include_revoked:
            stmt = stmt.where(Consent.status != ConsentStatus.REVOKED)

        stmt = stmt.order_by(Consent.created_at.desc())

        result = await self._resolve(self.db.execute(stmt))
        return list(result.scalars().all())

    async def check_and_update_expired_consents(self) -> int:
        """
        Check and mark expired consents.

        Returns:
            Number of consents marked as expired
        """
        now = now_sao_paulo()

        stmt = select(Consent).where(
            and_(
                Consent.status == ConsentStatus.GRANTED,
                Consent.expires_at.isnot(None),
                Consent.expires_at < now,
            )
        )
        result = await self._resolve(self.db.execute(stmt))
        expired = result.scalars().all()

        count = 0
        for consent in expired:
            consent.status = ConsentStatus.EXPIRED

            # Log expiration
            await self._log_consent_operation(
                action=LGPDActionType.CONSENT_EXPIRED,
                patient_id=consent.patient_id,
                user_id=None,
                consent_id=consent.id,
                consent_type=consent.consent_type,
            )
            count += 1

        if count > 0:
            await self._resolve(self.db.commit())
            logger.info(f"Marked {count} consents as expired")

        return count

    async def _log_consent_operation(
        self,
        action: LGPDActionType,
        patient_id: UUID,
        consent_id: UUID,
        consent_type: ConsentType,
        user_id: Optional[UUID] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        request_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log consent operation for LGPD audit.

        Args:
            action: Type of action
            patient_id: Patient UUID
            consent_id: Consent UUID
            consent_type: Type of consent
            user_id: User performing action
            additional_data: Additional audit data
            request_context: Request context
        """
        # Determine data category based on consent type
        data_category_map = {
            ConsentType.TREATMENT: LGPDDataCategory.HEALTH,
            ConsentType.DATA_SHARING: LGPDDataCategory.PERSONAL_BASIC,
            ConsentType.RESEARCH: LGPDDataCategory.HEALTH,
            ConsentType.COMMUNICATION: LGPDDataCategory.PERSONAL_CONTACT,
            ConsentType.TELEMEDICINE: LGPDDataCategory.HEALTH,
            ConsentType.PHOTOGRAPHY: LGPDDataCategory.BIOMETRIC,
            ConsentType.GENERAL: LGPDDataCategory.PERSONAL_BASIC,
        }

        data_category = data_category_map.get(
            consent_type, LGPDDataCategory.PERSONAL_BASIC
        )

        audit_log = LGPDAuditLog(
            user_id=user_id,
            patient_id=patient_id,
            action=action.value,
            data_category=data_category.value,
            resource_type="consent",
            resource_id=str(consent_id),
            purpose=f"Consent operation: {consent_type.value}",
            legal_basis="consent",
            ip_address=request_context.get("ip_address") if request_context else None,
            user_agent=request_context.get("user_agent") if request_context else None,
            session_id=request_context.get("session_id") if request_context else None,
            request_id=request_context.get("request_id") if request_context else None,
            additional_data=additional_data,
            success=True,
        )

        self.db.add(audit_log)
        # Don't commit here - let caller manage transaction


class LGPDAuditService:
    """
    Service for LGPD audit logging and reporting.

    QW-005: Provides audit logging capabilities for all PII access.
    """

    def __init__(self, db: Session | AsyncSession):
        """
        Initialize audit service.

        Args:
            db: Database session
        """
        self.db = db

    async def _resolve(self, maybe_awaitable: Any) -> Any:
        if inspect.isawaitable(maybe_awaitable):
            return await maybe_awaitable
        return maybe_awaitable

    async def log_data_access(
        self,
        user_id: Optional[UUID],
        patient_id: Optional[UUID],
        action: LGPDActionType,
        data_category: LGPDDataCategory,
        resource_type: str,
        resource_id: Optional[str] = None,
        fields_accessed: Optional[List[str]] = None,
        fields_modified: Optional[Dict[str, Any]] = None,
        purpose: Optional[str] = None,
        legal_basis: Optional[str] = None,
        request_context: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> LGPDAuditLog:
        """
        Log access to personal data.

        Args:
            user_id: User performing access
            patient_id: Patient whose data was accessed
            action: Type of action
            data_category: Category of data accessed
            resource_type: Type of resource accessed
            resource_id: ID of specific resource
            fields_accessed: List of fields accessed
            fields_modified: Dict of field changes
            purpose: Purpose of access
            legal_basis: Legal basis for processing
            request_context: HTTP request context
            success: Whether operation succeeded
            error_message: Error message if failed

        Returns:
            Created LGPDAuditLog
        """
        ctx = request_context or {}

        audit_log = LGPDAuditLog(
            user_id=user_id,
            patient_id=patient_id,
            action=action.value,
            data_category=data_category.value,
            resource_type=resource_type,
            resource_id=resource_id,
            fields_accessed=fields_accessed,
            fields_modified=fields_modified,
            purpose=purpose,
            legal_basis=legal_basis,
            ip_address=ctx.get("ip_address"),
            user_agent=ctx.get("user_agent"),
            session_id=ctx.get("session_id"),
            request_id=ctx.get("request_id"),
            success=success,
            error_message=error_message,
        )

        self.db.add(audit_log)
        await self._resolve(self.db.commit())
        await self._resolve(self.db.refresh(audit_log))

        return audit_log

    async def get_patient_access_history(
        self,
        patient_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[LGPDAuditLog]:
        """
        Get access history for a patient's data.

        Args:
            patient_id: Patient UUID
            start_date: Filter from date
            end_date: Filter to date
            limit: Maximum records to return

        Returns:
            List of audit logs
        """
        stmt = select(LGPDAuditLog).where(LGPDAuditLog.patient_id == patient_id)

        if start_date:
            stmt = stmt.where(LGPDAuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(LGPDAuditLog.created_at <= end_date)

        stmt = stmt.order_by(LGPDAuditLog.created_at.desc()).limit(limit)
        result = await self._resolve(self.db.execute(stmt))
        return list(result.scalars().all())

    async def get_user_access_history(
        self,
        user_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[LGPDAuditLog]:
        """
        Get access history for a user.

        Args:
            user_id: User UUID
            start_date: Filter from date
            end_date: Filter to date
            limit: Maximum records to return

        Returns:
            List of audit logs
        """
        stmt = select(LGPDAuditLog).where(LGPDAuditLog.user_id == user_id)

        if start_date:
            stmt = stmt.where(LGPDAuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(LGPDAuditLog.created_at <= end_date)

        stmt = stmt.order_by(LGPDAuditLog.created_at.desc()).limit(limit)
        result = await self._resolve(self.db.execute(stmt))
        return list(result.scalars().all())

    async def get_failed_access_attempts(
        self, hours: int = 24, limit: int = 100
    ) -> List[LGPDAuditLog]:
        """
        Get failed access attempts for security review.

        Args:
            hours: Time window in hours
            limit: Maximum records

        Returns:
            List of failed access logs
        """
        since = now_sao_paulo() - timedelta(hours=hours)

        stmt = (
            select(LGPDAuditLog)
            .where(
                and_(
                    LGPDAuditLog.success.is_(False),
                    LGPDAuditLog.created_at >= since,
                )
            )
            .order_by(LGPDAuditLog.created_at.desc())
            .limit(limit)
        )

        result = await self._resolve(self.db.execute(stmt))
        return list(result.scalars().all())


__all__ = ["ConsentService", "LGPDAuditService"]
