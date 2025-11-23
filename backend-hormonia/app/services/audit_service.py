"""
Audit Service for LGPD Compliance and Security Logging.

This service provides comprehensive audit logging for all security-relevant
events in the monthly quiz system, ensuring LGPD compliance and traceability.

ADAPTER VERSION: Compatible with new AuditLog model schema.
"""

import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List, Union
from uuid import UUID, uuid4
# from sqlalchemy.orm import
from sqlalchemy import Column, String, DateTime, JSON, Integer, func
from sqlalchemy.ext.declarative import declarative_base

from app.database import Base
from app.utils.security import mask_sensitive_url, mask_dict_secrets
from app.models.audit_log import AuditLog, AuditEventType  # Import existing model

logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for comprehensive audit logging with LGPD compliance.
    
    ADAPTER: Adapts legacy method calls to the new AuditLog schema.
    """

    def __init__(self, db: Any):
        self.db = db
        self.logger = logging.getLogger(__name__)

    def log_event(
        self,
        event_type: str,
        event_category: str,
        severity: str = "info",
        actor_id: Optional[UUID] = None,
        subject_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        result: str = "success",
        data_subject_id: Optional[UUID] = None,
        legal_basis: Optional[str] = None,
        retention_days: int = 365,
        # Legacy parameters for backward compatibility
        user_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None
    ) -> AuditLog:
        """
        Log an audit event (Legacy Adapter).
        Maps legacy arguments to the new AuditLog model schema.
        """
        # Handle backward compatibility for IDs
        final_user_id = actor_id if actor_id else user_id
        
        # Prepare metadata with fields that no longer have dedicated columns
        metadata = event_data or {}
        metadata.update({
            "event_category": event_category,
            "severity": severity,
            "subject_id": str(subject_id) if subject_id else (str(patient_id) if patient_id else None),
            "session_id": str(session_id) if session_id else None,
            "data_subject_id": str(data_subject_id) if data_subject_id else None,
            "legal_basis": legal_basis,
            "retention_days": retention_days,
            "adapter_version": "legacy_v2"
        })

        # Sanitize metadata
        sanitized_metadata = mask_dict_secrets(metadata)

        # Map event_type to Enum if possible, otherwise use a default or try to coerce
        # This is critical because the new model enforces Enum
        try:
            # Try direct mapping if string matches enum value
            mapped_event_type = AuditEventType(event_type)
        except ValueError:
            # Fallback mapping for known legacy events
            if "login" in event_type:
                mapped_event_type = AuditEventType.LOGIN_SUCCESS if result == "success" else AuditEventType.LOGIN_FAILURE
            elif "access" in event_type:
                mapped_event_type = AuditEventType.ACCESS_DENIED if result != "success" else AuditEventType.SUSPICIOUS_ACTIVITY
            elif "quiz" in event_type:
                # Generic mapping for quiz events not in Enum
                mapped_event_type = AuditEventType.SUSPICIOUS_ACTIVITY 
                sanitized_metadata["original_event_type"] = event_type
            else:
                # Default fallback
                mapped_event_type = AuditEventType.SUSPICIOUS_ACTIVITY
                sanitized_metadata["original_event_type"] = event_type

        audit_log = AuditLog(
            event_type=mapped_event_type,
            event_status=result,
            user_id=final_user_id,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            event_metadata=sanitized_metadata,
            message=f"{event_category}: {event_type}",
            created_at=datetime.utcnow()
        )

        self.db.add(audit_log)
        self.db.commit()

        # Also log to application logger
        self.logger.info(
            f"Audit (Legacy): {event_type}",
            extra={
                'audit_id': getattr(audit_log, 'id', 'unknown'),
                'category': event_category,
                'result': result,
                'user_id': str(final_user_id) if final_user_id else None
            }
        )

        return audit_log

    def log_link_created(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        delivery_method: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log quiz link creation."""
        return self.log_event(
            event_type="monthly_quiz_link_created",
            event_category="access",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "delivery_method": delivery_method,
                "expires_at": expires_at.isoformat()
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_accessed(
        self,
        patient_id: UUID,
        session_id: UUID,
        ip_address: str,
        user_agent: str,
        token_prefix: str
    ) -> AuditLog:
        """Log quiz link access."""
        return self.log_event(
            event_type="monthly_quiz_link_accessed",
            event_category="access",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "token_prefix": token_prefix
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent"
        )

    def log_response_submitted(
        self,
        patient_id: UUID,
        session_id: UUID,
        question_id: str,
        response_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log quiz response submission."""
        return self.log_event(
            event_type="monthly_quiz_response_submitted",
            event_category="data_change",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "question_id": question_id,
                "response_id": str(response_id)
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent"
        )

    def log_invalid_access_attempt(
        self,
        ip_address: str,
        user_agent: str,
        reason: str,
        token_prefix: Optional[str] = None
    ) -> AuditLog:
        """Log invalid access attempt."""
        return self.log_event(
            event_type="monthly_quiz_invalid_access",
            event_category="security",
            severity="warning",
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "reason": reason,
                "token_prefix": token_prefix
            },
            result="blocked"
        )

    def log_token_expired(
        self,
        patient_id: UUID,
        session_id: UUID
    ) -> AuditLog:
        """Log token expiration."""
        return self.log_event(
            event_type="monthly_quiz_token_expired",
            event_category="security",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            result="expired"
        )

    def log_link_resent(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        delivery_method: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log quiz link resend action."""
        return self.log_event(
            event_type="monthly_quiz_link_resent",
            event_category="access",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "delivery_method": delivery_method
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_regenerated(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        regeneration_count: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log quiz link regeneration action."""
        return self.log_event(
            event_type="monthly_quiz_link_regenerated",
            event_category="security",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "regeneration_count": regeneration_count
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_cancelled(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log quiz link cancellation action."""
        return self.log_event(
            event_type="monthly_quiz_link_cancelled",
            event_category="access",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={},
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_expired(
        self,
        patient_id: UUID,
        session_id: UUID,
        fallback_activated: bool = False
    ) -> AuditLog:
        """Log quiz link expiration."""
        return self.log_event(
            event_type="monthly_quiz_link_expired",
            event_category="security",
            severity="warning" if not fallback_activated else "info",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "fallback_activated": fallback_activated
            },
            result="expired",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_fallback_activated(
        self,
        patient_id: UUID,
        session_id: UUID,
        fallback_reason: str,
        fallback_method: str = "whatsapp_conversational"
    ) -> AuditLog:
        """Log fallback to WhatsApp conversational flow."""
        return self.log_event(
            event_type="monthly_quiz_fallback_activated",
            event_category="access",
            severity="warning",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "fallback_reason": fallback_reason,
                "fallback_method": fallback_method
            },
            result="fallback",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_reminder_sent(
        self,
        patient_id: UUID,
        session_id: UUID,
        delivery_channel: str,
        is_retry: bool = False,
        retry_count: int = 0
    ) -> AuditLog:
        """Log quiz reminder sent."""
        return self.log_event(
            event_type="monthly_quiz_reminder_sent",
            event_category="access",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "delivery_channel": delivery_channel,
                "is_retry": is_retry,
                "retry_count": retry_count
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_reminder_failed(
        self,
        patient_id: UUID,
        session_id: UUID,
        delivery_channel: str,
        failure_reason: str,
        retry_count: int = 0
    ) -> AuditLog:
        """Log quiz reminder failure."""
        return self.log_event(
            event_type="monthly_quiz_reminder_failed",
            event_category="access",
            severity="error",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "delivery_channel": delivery_channel,
                "failure_reason": failure_reason,
                "retry_count": retry_count
            },
            result="failure",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_consent_given(
        self,
        patient_id: UUID,
        consent_type: str,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """Log LGPD consent given."""
        return self.log_event(
            event_type="lgpd_consent_given",
            event_category="consent",
            severity="info",
            patient_id=patient_id,
            ip_address=ip_address,
            event_data={
                "consent_type": consent_type
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent",
            retention_days=2555  # 7 years for LGPD compliance
        )

    def log_data_deletion(
        self,
        patient_id: UUID,
        user_id: UUID,
        deletion_scope: str,
        reason: str
    ) -> AuditLog:
        """Log data deletion (right to be forgotten)."""
        return self.log_event(
            event_type="lgpd_data_deleted",
            event_category="data_change",
            severity="warning",
            actor_id=user_id,
            subject_id=patient_id,
            event_data={
                "deletion_scope": deletion_scope,
                "reason": reason
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legal_obligation",
            retention_days=2555  # 7 years retention
        )

    def get_patient_audit_trail(
        self,
        patient_id: UUID,
        limit: int = 100
    ) -> list[AuditLog]:
        """Get audit trail for a specific patient (for LGPD export)."""
        # This query might need adjustment if patient_id is not directly in AuditLog
        # For now, assume we filter by metadata subject_id which is safer
        from sqlalchemy import text
        return self.db.query(AuditLog).filter(
            AuditLog.event_metadata['subject_id'].astext == str(patient_id)
        ).order_by(
            AuditLog.created_at.desc()
        ).limit(limit).all()

    def cleanup_expired_logs(self) -> int:
        """Clean up logs past retention period."""
        # Retention is now handled by metadata or dedicated job, this is a placeholder
        # that logs intent but does nothing to avoid accidental deletion with new schema
        self.logger.info("Cleanup called on legacy adapter - deferring to system retention policy")
        return 0

    # ========================================================================
    # AI-Specific Audit Methods (HIPAA Compliant)
    # ========================================================================

    def log_ai_chat_request(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: Optional[UUID],
        message: str,
        response: str,
        response_time_ms: float,
        cache_hit: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI chat request with HIPAA compliance."""
        # Hash message for privacy (don't store full patient data)
        message_hash = hashlib.sha256(message.encode()).hexdigest()[:16]
        response_summary = response[:100] + "..." if len(response) > 100 else response

        return self.log_event(
            event_type="ai_chat_request",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "message_hash": message_hash,
                "message_length": len(message),
                "response_summary": response_summary,
                "response_length": len(response),
                "response_time_ms": response_time_ms,
                "cache_hit": cache_hit,
                "has_patient_context": patient_id is not None
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90  # HIPAA: 90 days for access logs
        )

    def log_ai_chat_error(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: Optional[UUID],
        error_type: str,
        error_message: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI chat error."""
        return self.log_event(
            event_type="ai_chat_error",
            event_category="security",
            severity="error",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "error_type": error_type,
                "error_message": error_message[:200]  # Truncate for privacy
            },
            result="failure",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_insights_generation(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: UUID,
        timeframe_days: int,
        insights_count: int,
        risk_level: str,
        response_time_ms: float,
        cache_hit: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI insights generation."""
        return self.log_event(
            event_type="ai_insights_generated",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "timeframe_days": timeframe_days,
                "insights_count": insights_count,
                "risk_level": risk_level,
                "response_time_ms": response_time_ms,
                "cache_hit": cache_hit
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_recommendations_generation(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: UUID,
        recommendations_count: int,
        action_items_count: int,
        confidence_level: float,
        response_time_ms: float,
        cache_hit: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI recommendations generation."""
        return self.log_event(
            event_type="ai_recommendations_generated",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "recommendations_count": recommendations_count,
                "action_items_count": action_items_count,
                "confidence_level": confidence_level,
                "response_time_ms": response_time_ms,
                "cache_hit": cache_hit
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_analysis_request(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: UUID,
        analysis_type: str,
        date_range_days: int,
        include_messages: bool,
        include_medical_history: bool,
        response_time_ms: float,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI analysis request."""
        return self.log_event(
            event_type="ai_analysis_request",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "analysis_type": analysis_type,
                "date_range_days": date_range_days,
                "include_messages": include_messages,
                "include_medical_history": include_medical_history,
                "response_time_ms": response_time_ms
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_sentiment_analysis(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: Optional[UUID],
        message: str,
        sentiment: str,
        concern_level: str,
        confidence: float,
        response_time_ms: float,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI sentiment analysis."""
        message_hash = hashlib.sha256(message.encode()).hexdigest()[:16]

        return self.log_event(
            event_type="ai_sentiment_analysis",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "message_hash": message_hash,
                "message_length": len(message),
                "sentiment": sentiment,
                "concern_level": concern_level,
                "confidence": confidence,
                "response_time_ms": response_time_ms
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_response_generation(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: UUID,
        message_type: str,
        template_length: int,
        generated_length: int,
        readability_score: float,
        response_time_ms: float,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI response generation."""
        return self.log_event(
            event_type="ai_response_generated",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "message_type": message_type,
                "template_length": template_length,
                "generated_length": generated_length,
                "readability_score": readability_score,
                "response_time_ms": response_time_ms
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_cache_hit(
        self,
        cache_key: str,
        endpoint: str,
        response_time_ms: float,
        user_id: Optional[UUID] = None
    ) -> AuditLog:
        """Log AI cache hit for performance tracking."""
        # Hash cache key to avoid exposing sensitive data
        key_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:16]

        return self.log_event(
            event_type="ai_cache_hit",
            event_category="access",
            severity="info",
            actor_id=user_id,
            event_data={
                "cache_key_hash": key_hash,
                "endpoint": endpoint,
                "response_time_ms": response_time_ms
            },
            result="success",
            retention_days=30  # Shorter retention for performance logs
        )

    def log_ai_cache_miss(
        self,
        cache_key: str,
        endpoint: str,
        response_time_ms: float,
        user_id: Optional[UUID] = None
    ) -> AuditLog:
        """Log AI cache miss for performance tracking."""
        key_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:16]

        return self.log_event(
            event_type="ai_cache_miss",
            event_category="access",
            severity="info",
            actor_id=user_id,
            event_data={
                "cache_key_hash": key_hash,
                "endpoint": endpoint,
                "response_time_ms": response_time_ms
            },
            result="success",
            retention_days=30
        )

    def log_ai_cache_invalidation(
        self,
        user_id: UUID,
        patient_id: UUID,
        invalidated_count: int,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """Log AI cache invalidation."""
        return self.log_event(
            event_type="ai_cache_invalidated",
            event_category="data_change",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            event_data={
                "invalidated_count": invalidated_count
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    # ========================================================================
    # Query Methods for Compliance Reporting
    # ========================================================================

    def get_ai_audit_report(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]] = None,
        user_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None
    ) -> List[AuditLog]:
        """Get AI audit report for compliance."""
        # Query modified to work with new schema structure (no specific AI methods in core AuditLog)
        # We filter by event_type pattern or list
        query = self.db.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )

        # Attempt to filter by AI events (legacy check)
        # Ideally, event_type would be checked against Enum values
        # but here we use a broad filter assuming legacy event types were strings
        # The new Enum doesn't have AI events explicitly defined yet, so we rely on metadata
        
        # TODO: Add AI event types to AuditEventType Enum in future migration
        
        if event_types:
            # This might fail if event_types are strings and DB expects Enums
            # We skip for now as this is a legacy report method
            pass
            
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        # For patient_id, we check metadata as it's not a top-level column anymore
        if patient_id:
            query = query.filter(AuditLog.event_metadata['subject_id'].astext == str(patient_id))

        return query.order_by(AuditLog.created_at.desc()).all()

    def get_ai_performance_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get AI performance metrics from audit logs."""
        # Placeholder implementation
        return {
            "total_requests": 0,
            "cache_hit_rate": 0,
            "error_rate": 0,
            "average_response_time_ms": 0
        }

    def get_patient_ai_access_history(
        self,
        patient_id: UUID,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get AI access history for a patient (HIPAA compliance)."""
        # Filter by metadata subject_id
        return self.db.query(AuditLog).filter(
            AuditLog.event_metadata['subject_id'].astext == str(patient_id)
        ).order_by(
            AuditLog.created_at.desc()
        ).limit(limit).all()

    def get_user_ai_activity(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[AuditLog]:
        """Get user AI activity for audit purposes."""
        return self.db.query(AuditLog).filter(
            AuditLog.user_id == user_id,
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        ).order_by(
            AuditLog.created_at.desc()
        ).all()

    def get_ai_security_events(
        self,
        start_date: datetime,
        end_date: datetime,
        severity: Optional[str] = None
    ) -> List[AuditLog]:
        """Get AI security events for monitoring."""
        # Severity is now in metadata
        query = self.db.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )

        if severity:
            query = query.filter(AuditLog.event_metadata['severity'].astext == severity)

        return query.order_by(AuditLog.created_at.desc()).all()

    def export_ai_audit_data(
        self,
        patient_id: UUID,
        format: str = 'json'
    ) -> Dict[str, Any]:
        """Export AI audit data for a patient (HIPAA compliance)."""
        logs = self.get_patient_ai_access_history(patient_id, limit=1000)

        export_data = {
            "patient_id": str(patient_id),
            "export_date": datetime.utcnow().isoformat(),
            "total_logs": len(logs),
            "logs": [
                {
                    "timestamp": log.created_at.isoformat(),
                    "event_type": log.event_type.value if hasattr(log.event_type, 'value') else str(log.event_type),
                    "actor_id": str(log.user_id),
                    "result": log.event_status,
                    "event_data": log.event_metadata
                }
                for log in logs
            ]
        }

        return export_data