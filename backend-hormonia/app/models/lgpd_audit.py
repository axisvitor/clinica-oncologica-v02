"""
LGPD Audit Log model for tracking access to sensitive data.

QW-005: Implements LGPD (Brazilian Data Protection Law) compliance
by logging all access to personally identifiable information (PII).
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID
import enum

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, INET
from sqlalchemy.orm import relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class LGPDActionType(str, enum.Enum):
    """Types of actions that trigger LGPD audit logging."""
    # Data Access
    VIEW = "view"                           # Viewed sensitive data
    SEARCH = "search"                       # Searched for patient data
    EXPORT = "export"                       # Exported data
    DOWNLOAD = "download"                   # Downloaded files

    # Data Modification
    CREATE = "create"                       # Created new record with PII
    UPDATE = "update"                       # Updated PII
    DELETE = "delete"                       # Deleted PII (soft or hard)
    ANONYMIZE = "anonymize"                 # Anonymized data

    # Consent Operations
    CONSENT_GRANTED = "consent_granted"     # Consent given by patient
    CONSENT_REVOKED = "consent_revoked"     # Consent revoked by patient
    CONSENT_EXPIRED = "consent_expired"     # Consent expired

    # Data Sharing
    SHARE_INTERNAL = "share_internal"       # Shared with internal user
    SHARE_EXTERNAL = "share_external"       # Shared with external entity
    TRANSFER = "transfer"                   # Transferred to another system

    # Special Operations
    DECRYPT = "decrypt"                     # Decrypted encrypted data
    BACKUP = "backup"                       # Data backed up
    RESTORE = "restore"                     # Data restored from backup
    ACCESS_DENIED = "access_denied"         # Attempted unauthorized access


class LGPDDataCategory(str, enum.Enum):
    """Categories of data as per LGPD classification."""
    # Regular Personal Data
    PERSONAL_BASIC = "personal_basic"       # Name, address, phone
    PERSONAL_CONTACT = "personal_contact"   # Email, phone numbers
    PERSONAL_IDENTITY = "personal_identity" # CPF, RG, documents

    # Sensitive Personal Data (requires explicit consent)
    HEALTH = "health"                       # Medical records, conditions
    GENETIC = "genetic"                     # Genetic information
    BIOMETRIC = "biometric"                 # Fingerprints, facial recognition
    ETHNIC = "ethnic"                       # Ethnic origin
    RELIGIOUS = "religious"                 # Religious beliefs
    POLITICAL = "political"                 # Political opinions
    SEXUAL = "sexual"                       # Sexual orientation
    UNION = "union"                         # Union membership

    # System Data
    AUTHENTICATION = "authentication"       # Login credentials
    FINANCIAL = "financial"                 # Payment information


class LGPDAuditLog(BaseModel):
    """
    LGPD Audit Log for tracking access to sensitive data.

    This model is designed for high-volume insert operations
    and efficient querying by patient, user, and time range.

    All PII access MUST be logged here for LGPD compliance.
    """
    __tablename__ = "lgpd_audit_logs"

    # Actor Information
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)  # Denormalized for when user is deleted
    user_role = Column(String(50), nullable=True)

    # Subject Information (whose data was accessed)
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True)
    patient_identifier = Column(String(255), nullable=True)  # Anonymized identifier for audit trail

    # Action Details
    action = Column(String(50), nullable=False, index=True)  # LGPDActionType value
    data_category = Column(String(50), nullable=False, index=True)  # LGPDDataCategory value
    resource_type = Column(String(100), nullable=False)  # Table/resource accessed
    resource_id = Column(String(255), nullable=True)  # ID of specific resource

    # Fields Accessed (for granular tracking)
    fields_accessed = Column(JSONB, nullable=True)  # List of field names accessed
    fields_modified = Column(JSONB, nullable=True)  # Dict of old -> new values (hashed)

    # Context
    purpose = Column(String(255), nullable=True)  # Purpose of access (from consent)
    legal_basis = Column(String(100), nullable=True)  # Legal basis for processing

    # Request Information
    ip_address = Column(INET, nullable=True)
    user_agent = Column(String(500), nullable=True)
    session_id = Column(String(255), nullable=True, index=True)
    request_id = Column(String(255), nullable=True)  # Correlation ID

    # Additional Context
    additional_data = Column(JSONB, nullable=True)

    # Result
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)

    # Retention (LGPD requires retention tracking)
    retention_until = Column(DateTime(timezone=True), nullable=True)
    can_be_deleted = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], lazy="select")
    patient = relationship("Patient", foreign_keys=[patient_id], lazy="select")

    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_lgpd_audit_patient_time', 'patient_id', 'created_at'),
        Index('ix_lgpd_audit_user_time', 'user_id', 'created_at'),
        Index('ix_lgpd_audit_action_time', 'action', 'created_at'),
        Index('ix_lgpd_audit_session', 'session_id', 'created_at'),
        # Partial index for failed accesses
        Index('ix_lgpd_audit_failures', 'created_at', postgresql_where=(~Column('success'))),
    )

    def __repr__(self) -> str:
        return (
            f"<LGPDAuditLog(id={self.id}, action={self.action}, "
            f"user_id={self.user_id}, patient_id={self.patient_id})>"
        )


class DataAccessRequest(BaseModel):
    """
    LGPD Data Access Request (DSAR) tracking.

    Tracks requests from data subjects for access, correction,
    deletion, or portability of their personal data.
    """
    __tablename__ = "lgpd_data_access_requests"

    # Requester Information
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by = Column(String(255), nullable=True)  # If different from patient
    verified = Column(Boolean, default=False, nullable=False)  # Identity verified

    # Request Details
    request_type = Column(String(50), nullable=False, index=True)  # access, rectification, erasure, portability
    description = Column(Text, nullable=True)

    # Status
    status = Column(String(50), default="pending", nullable=False, index=True)
    # pending, in_progress, completed, rejected, expired

    # Deadlines (LGPD requires 15-day response)
    received_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    deadline_at = Column(DateTime(timezone=True), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Handling
    assigned_to_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    response = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Evidence
    evidence_url = Column(String(500), nullable=True)  # Link to exported data
    evidence_hash = Column(String(64), nullable=True)  # SHA256 of exported data

    # Metadata
    request_metadata = Column(JSONB, nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="data_access_requests", lazy="select")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], lazy="select")

    __table_args__ = (
        Index('ix_dsar_status_deadline', 'status', 'deadline_at'),
    )

    def __repr__(self) -> str:
        return (
            f"<DataAccessRequest(id={self.id}, type={self.request_type}, "
            f"status={self.status}, patient_id={self.patient_id})>"
        )


__all__ = [
    "LGPDActionType",
    "LGPDDataCategory",
    "LGPDAuditLog",
    "DataAccessRequest"
]
