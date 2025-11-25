"""
Audit Trail Service for Platform Integration.

Provides comprehensive audit logging that integrates with the main Hormonia
platform logging system, ensuring complete traceability of all flow interactions.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass, field
# from sqlalchemy.orm import
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from app.models.base import BaseModel
from app.models.user import User
from app.models.patient import Patient
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""
    PATIENT_INTERACTION = "patient_interaction"
    FLOW_STATE_CHANGE = "flow_state_change"
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    ALERT_CREATED = "alert_created"
    ALERT_RESOLVED = "alert_resolved"
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    DATA_SYNC = "data_sync"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    ERROR_EVENT = "error_event"


class AuditSeverity(Enum):
    """Audit event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditContext:
    """Context information for audit events."""
    user_id: Optional[UUID] = None
    patient_id: Optional[UUID] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    flow_context: Optional[Dict[str, Any]] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


class AuditLogEntry(BaseModel):
    """Audit log entry model for database storage."""
    __tablename__ = "audit_log_entries"
    __table_args__ = {'extend_existing': True}
    
    # Event identification
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="medium")
    
    # Entity references
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id"), nullable=True, index=True)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    
    # Event details
    action = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Context and metadata
    context_data = Column(JSONB, nullable=True, default=dict)
    changes = Column(JSONB, nullable=True, default=dict)
    audit_metadata = Column(JSONB, nullable=True, default=dict)
    
    # Request tracking
    session_id = Column(String(255), nullable=True, index=True)
    request_id = Column(String(255), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    
    # Timing
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<AuditLogEntry(event_type='{self.event_type}', action='{self.action}', timestamp='{self.timestamp}')>"


class AuditTrailService:
    """
    Comprehensive audit trail service for platform integration.
    
    Provides:
    - Complete audit logging for all flow interactions
    - Integration with main platform logging system
    - Searchable audit trail with filtering capabilities
    - Compliance-ready audit reports
    - Real-time audit event streaming
    """
    
    def __init__(self, db: Any):
        """
        Initialize audit trail service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.user_repo = UserRepository(db)
        
        logger.info("Audit Trail Service initialized")
    
    async def log_patient_interaction(self,
                                    patient_id: UUID,
                                    interaction_type: str,
                                    details: Dict[str, Any],
                                    context: Optional[AuditContext] = None,
                                    severity: AuditSeverity = AuditSeverity.MEDIUM) -> AuditLogEntry:
        """
        Log patient interaction event.
        
        Args:
            patient_id: Patient UUID
            interaction_type: Type of interaction (message_sent, response_received, etc.)
            details: Interaction details
            context: Audit context
            severity: Event severity
            
        Returns:
            Created audit log entry
        """
        return await self._create_audit_entry(
            event_type=AuditEventType.PATIENT_INTERACTION,
            action=interaction_type,
            entity_type="patient",
            entity_id=patient_id,
            patient_id=patient_id,
            changes=details,
            context=context,
            severity=severity,
            description=f"Patient interaction: {interaction_type}"
        )
    
    async def log_flow_state_change(self,
                                  patient_id: UUID,
                                  flow_state_id: UUID,
                                  old_state: Dict[str, Any],
                                  new_state: Dict[str, Any],
                                  context: Optional[AuditContext] = None) -> AuditLogEntry:
        """
        Log flow state change event.
        
        Args:
            patient_id: Patient UUID
            flow_state_id: Flow state UUID
            old_state: Previous state data
            new_state: New state data
            context: Audit context
            
        Returns:
            Created audit log entry
        """
        changes = {
            "old_state": old_state,
            "new_state": new_state,
            "changed_fields": self._calculate_changed_fields(old_state, new_state)
        }
        
        return await self._create_audit_entry(
            event_type=AuditEventType.FLOW_STATE_CHANGE,
            action="state_changed",
            entity_type="flow_state",
            entity_id=flow_state_id,
            patient_id=patient_id,
            changes=changes,
            context=context,
            description=f"Flow state changed for patient {patient_id}"
        )
    
    async def log_message_event(self,
                              message_id: UUID,
                              patient_id: UUID,
                              event_type: str,
                              message_data: Dict[str, Any],
                              context: Optional[AuditContext] = None,
                              severity: AuditSeverity = AuditSeverity.LOW) -> AuditLogEntry:
        """
        Log message-related event.
        
        Args:
            message_id: Message UUID
            patient_id: Patient UUID
            event_type: Type of message event (sent, received, failed, etc.)
            message_data: Message details
            context: Audit context
            severity: Event severity
            
        Returns:
            Created audit log entry
        """
        audit_event_type = (AuditEventType.MESSAGE_SENT 
                           if event_type in ["sent", "delivered", "read"] 
                           else AuditEventType.MESSAGE_RECEIVED)
        
        return await self._create_audit_entry(
            event_type=audit_event_type,
            action=event_type,
            entity_type="message",
            entity_id=message_id,
            patient_id=patient_id,
            changes=message_data,
            context=context,
            severity=severity,
            description=f"Message {event_type}: {message_data.get('content', '')[:100]}"
        )
    
    async def log_user_action(self,
                            user_id: UUID,
                            action: str,
                            target_entity_type: Optional[str] = None,
                            target_entity_id: Optional[UUID] = None,
                            action_data: Optional[Dict[str, Any]] = None,
                            context: Optional[AuditContext] = None,
                            severity: AuditSeverity = AuditSeverity.MEDIUM) -> AuditLogEntry:
        """
        Log user action event.
        
        Args:
            user_id: User UUID
            action: Action performed
            target_entity_type: Type of target entity (optional)
            target_entity_id: Target entity UUID (optional)
            action_data: Action details
            context: Audit context
            severity: Event severity
            
        Returns:
            Created audit log entry
        """
        return await self._create_audit_entry(
            event_type=AuditEventType.USER_ACTION,
            action=action,
            entity_type=target_entity_type,
            entity_id=target_entity_id,
            user_id=user_id,
            changes=action_data or {},
            context=context,
            severity=severity,
            description=f"User action: {action}"
        )
    
    async def log_authentication_event(self,
                                     user_id: Optional[UUID],
                                     event_type: str,
                                     success: bool,
                                     details: Dict[str, Any],
                                     context: Optional[AuditContext] = None) -> AuditLogEntry:
        """
        Log authentication event.
        
        Args:
            user_id: User UUID (if known)
            event_type: Type of auth event (login, logout, token_refresh, etc.)
            success: Whether the authentication was successful
            details: Authentication details
            context: Audit context
            
        Returns:
            Created audit log entry
        """
        severity = AuditSeverity.LOW if success else AuditSeverity.HIGH
        
        return await self._create_audit_entry(
            event_type=AuditEventType.AUTHENTICATION,
            action=event_type,
            entity_type="user",
            entity_id=user_id,
            user_id=user_id,
            changes=details,
            context=context,
            severity=severity,
            description=f"Authentication {event_type}: {'success' if success else 'failed'}"
        )
    
    async def log_system_event(self,
                             event_type: str,
                             details: Dict[str, Any],
                             severity: AuditSeverity = AuditSeverity.MEDIUM,
                             context: Optional[AuditContext] = None) -> AuditLogEntry:
        """
        Log system event.
        
        Args:
            event_type: Type of system event
            details: Event details
            severity: Event severity
            context: Audit context
            
        Returns:
            Created audit log entry
        """
        return await self._create_audit_entry(
            event_type=AuditEventType.SYSTEM_EVENT,
            action=event_type,
            changes=details,
            context=context,
            severity=severity,
            description=f"System event: {event_type}"
        )
    
    async def log_error_event(self,
                            error_type: str,
                            error_message: str,
                            error_details: Dict[str, Any],
                            context: Optional[AuditContext] = None,
                            severity: AuditSeverity = AuditSeverity.HIGH) -> AuditLogEntry:
        """
        Log error event.
        
        Args:
            error_type: Type of error
            error_message: Error message
            error_details: Error details
            context: Audit context
            severity: Error severity
            
        Returns:
            Created audit log entry
        """
        return await self._create_audit_entry(
            event_type=AuditEventType.ERROR_EVENT,
            action=error_type,
            changes=error_details,
            context=context,
            severity=severity,
            description=f"Error: {error_message}"
        )
    
    async def _create_audit_entry(self,
                                event_type: AuditEventType,
                                action: str,
                                entity_type: Optional[str] = None,
                                entity_id: Optional[UUID] = None,
                                user_id: Optional[UUID] = None,
                                patient_id: Optional[UUID] = None,
                                changes: Optional[Dict[str, Any]] = None,
                                context: Optional[AuditContext] = None,
                                severity: AuditSeverity = AuditSeverity.MEDIUM,
                                description: Optional[str] = None) -> AuditLogEntry:
        """Create audit log entry in database."""
        try:
            # Create audit entry
            audit_entry = AuditLogEntry(
                event_type=event_type.value,
                severity=severity.value,
                user_id=user_id or (context.user_id if context else None),
                patient_id=patient_id or (context.patient_id if context else None),
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                description=description,
                changes=changes or {},
                context_data=context.additional_data if context else {},
                audit_metadata={
                    "source": "flow_system",
                    "version": "1.0.0",
                    "timestamp": datetime.utcnow().isoformat()
                },
                session_id=context.session_id if context else None,
                request_id=context.request_id if context else None,
                ip_address=context.ip_address if context else None,
                user_agent=context.user_agent if context else None
            )
            
            # Save to database
            self.db.add(audit_entry)
            self.db.commit()
            self.db.refresh(audit_entry)
            
            # Log to application logger for immediate visibility
            log_level = self._get_log_level(severity)
            logger.log(log_level, f"AUDIT: {event_type.value} - {action} - {description}")
            
            # TODO: Integrate with main platform audit system
            # await self._send_to_platform_audit_system(audit_entry)
            
            return audit_entry
            
        except Exception as e:
            logger.error(f"Failed to create audit entry: {e}")
            self.db.rollback()
            raise
    
    def _get_log_level(self, severity: AuditSeverity) -> int:
        """Get logging level for severity."""
        severity_map = {
            AuditSeverity.LOW: logging.DEBUG,
            AuditSeverity.MEDIUM: logging.INFO,
            AuditSeverity.HIGH: logging.WARNING,
            AuditSeverity.CRITICAL: logging.ERROR
        }
        return severity_map.get(severity, logging.INFO)
    
    def _calculate_changed_fields(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> List[str]:
        """Calculate which fields changed between old and new data."""
        changed_fields = []
        
        # Check for changed values
        for key, new_value in new_data.items():
            old_value = old_data.get(key)
            if old_value != new_value:
                changed_fields.append(key)
        
        # Check for removed fields
        for key in old_data.keys():
            if key not in new_data:
                changed_fields.append(f"-{key}")  # Prefix with - to indicate removal
        
        return changed_fields
    
    async def get_audit_trail(self,
                            entity_type: Optional[str] = None,
                            entity_id: Optional[UUID] = None,
                            user_id: Optional[UUID] = None,
                            patient_id: Optional[UUID] = None,
                            event_types: Optional[List[AuditEventType]] = None,
                            start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None,
                            limit: int = 100,
                            offset: int = 0) -> List[AuditLogEntry]:
        """
        Get audit trail entries with filtering.
        
        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            user_id: Filter by user ID
            patient_id: Filter by patient ID
            event_types: Filter by event types
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of entries
            offset: Offset for pagination
            
        Returns:
            List of audit log entries
        """
        try:
            query = self.db.query(AuditLogEntry)
            
            # Apply filters
            if entity_type:
                query = query.filter(AuditLogEntry.entity_type == entity_type)
            
            if entity_id:
                query = query.filter(AuditLogEntry.entity_id == entity_id)
            
            if user_id:
                query = query.filter(AuditLogEntry.user_id == user_id)
            
            if patient_id:
                query = query.filter(AuditLogEntry.patient_id == patient_id)
            
            if event_types:
                event_type_values = [et.value for et in event_types]
                query = query.filter(AuditLogEntry.event_type.in_(event_type_values))
            
            if start_date:
                query = query.filter(AuditLogEntry.timestamp >= start_date)
            
            if end_date:
                query = query.filter(AuditLogEntry.timestamp <= end_date)
            
            # Order by timestamp descending (most recent first)
            query = query.order_by(AuditLogEntry.timestamp.desc())
            
            # Apply pagination
            query = query.offset(offset).limit(limit)
            
            return query.all()
            
        except Exception as e:
            logger.error(f"Failed to get audit trail: {e}")
            return []
    
    async def get_audit_summary(self,
                              start_date: Optional[datetime] = None,
                              end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get audit trail summary statistics.
        
        Args:
            start_date: Start date for summary
            end_date: End date for summary
            
        Returns:
            Audit summary statistics
        """
        try:
            query = self.db.query(AuditLogEntry)
            
            if start_date:
                query = query.filter(AuditLogEntry.timestamp >= start_date)
            
            if end_date:
                query = query.filter(AuditLogEntry.timestamp <= end_date)
            
            # Get total count
            total_entries = query.count()
            
            # Get counts by event type
            event_type_counts = {}
            for event_type in AuditEventType:
                count = query.filter(AuditLogEntry.event_type == event_type.value).count()
                event_type_counts[event_type.value] = count
            
            # Get counts by severity
            severity_counts = {}
            for severity in AuditSeverity:
                count = query.filter(AuditLogEntry.severity == severity.value).count()
                severity_counts[severity.value] = count
            
            # Get recent activity (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_activity = query.filter(AuditLogEntry.timestamp >= recent_cutoff).count()
            
            return {
                "total_entries": total_entries,
                "event_type_counts": event_type_counts,
                "severity_counts": severity_counts,
                "recent_activity_24h": recent_activity,
                "date_range": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get audit summary: {e}")
            return {}


# Global audit trail service instance
_audit_trail_service = None

def get_audit_trail_service(db: Any) -> AuditTrailService:
    """Get audit trail service instance."""
    global _audit_trail_service
    if _audit_trail_service is None:
        _audit_trail_service = AuditTrailService(db)
    return _audit_trail_service
