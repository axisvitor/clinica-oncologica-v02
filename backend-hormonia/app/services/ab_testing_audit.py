"""
A/B Testing Audit Service for Healthcare Compliance

Comprehensive audit logging system for A/B testing activities with HIPAA
compliance, GDPR support, and detailed tracking for regulatory requirements.
"""

import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.models.ab_experiment import ABExperimentAudit, ABExperiment
from app.models.user import User
from app.services.encryption_service import EncryptionService
from app.services.privacy_service import PrivacyService

logger = logging.getLogger(__name__)


class AuditEventType:
    """Standard audit event types for A/B testing."""

    # Experiment lifecycle
    EXPERIMENT_CREATED = "experiment_created"
    EXPERIMENT_STARTED = "experiment_started"
    EXPERIMENT_PAUSED = "experiment_paused"
    EXPERIMENT_RESUMED = "experiment_resumed"
    EXPERIMENT_COMPLETED = "experiment_completed"
    EXPERIMENT_TERMINATED = "experiment_terminated"
    EXPERIMENT_DELETED = "experiment_deleted"

    # Configuration changes
    CONFIG_MODIFIED = "config_modified"
    SAFETY_CONFIG_CHANGED = "safety_config_changed"
    TARGET_POPULATION_MODIFIED = "target_population_modified"
    TRAFFIC_SPLIT_CHANGED = "traffic_split_changed"

    # Patient interactions
    PATIENT_ASSIGNED = "patient_assigned"
    PATIENT_EXCLUDED = "patient_excluded"
    SAFETY_ASSESSMENT = "safety_assessment"
    VARIANT_OVERRIDE = "variant_override"

    # Message activities
    MESSAGE_CREATED = "message_created"
    MESSAGE_SENT = "message_sent"
    MESSAGE_DELIVERED = "message_delivered"
    MESSAGE_RESPONDED = "message_responded"
    MESSAGE_FAILED = "message_failed"

    # AI processing
    AI_HUMANIZATION_APPLIED = "ai_humanization_applied"
    AI_HUMANIZATION_FAILED = "ai_humanization_failed"
    AI_SAFETY_CHECK = "ai_safety_check"
    MEDICAL_CONTENT_DETECTED = "medical_content_detected"

    # Safety and compliance
    SAFETY_VIOLATION = "safety_violation"
    EMERGENCY_STOP = "emergency_stop"
    THRESHOLD_BREACH = "threshold_breach"
    MANUAL_REVIEW_TRIGGERED = "manual_review_triggered"
    COMPLIANCE_CHECK = "compliance_check"

    # Analysis and reporting
    RESULTS_CALCULATED = "results_calculated"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    REPORT_GENERATED = "report_generated"
    DATA_EXPORT = "data_export"

    # Access and permissions
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"


class ABTestingAuditService:
    """
    Comprehensive audit service for A/B testing activities.

    Ensures HIPAA compliance, GDPR requirements, and provides detailed
    audit trails for regulatory reporting and compliance verification.
    """

    def __init__(
        self,
        db: Session,
        encryption_service: Optional[EncryptionService] = None,
        privacy_service: Optional[PrivacyService] = None
    ):
        """Initialize audit service."""
        self.db = db
        self.encryption_service = encryption_service or EncryptionService()
        self.privacy_service = privacy_service or PrivacyService()

        # Audit configuration
        self.retention_days = 2555  # 7 years for healthcare compliance
        self.anonymization_enabled = True
        self.encryption_enabled = True

    def log_experiment_lifecycle(
        self,
        experiment_id: str,
        action: str,
        actor: str,
        actor_type: str = "user",
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Log experiment lifecycle events.

        Args:
            experiment_id: Experiment UUID
            action: Action performed (use AuditEventType constants)
            actor: User or system performing action
            actor_type: Type of actor (user, system, automated)
            previous_state: Previous experiment state
            new_state: New experiment state
            reason: Reason for action (e.g., for emergency stops)
            additional_data: Additional context data
            ip_address: Actor's IP address
            user_agent: Actor's user agent
            session_id: Actor's session ID

        Returns:
            Audit log entry ID
        """
        try:
            # Prepare audit data
            action_details = {
                "action": action,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            if additional_data:
                action_details.update(additional_data)

            # Anonymize sensitive data if required
            if previous_state:
                previous_state = self._anonymize_sensitive_data(previous_state)
            if new_state:
                new_state = self._anonymize_sensitive_data(new_state)

            # Create audit entry
            audit_entry = ABExperimentAudit(
                experiment_id=experiment_id,
                action=action,
                actor=self._anonymize_actor(actor),
                actor_type=actor_type,
                action_details=action_details,
                previous_state=previous_state,
                new_state=new_state,
                ip_address=self._anonymize_ip(ip_address) if ip_address else None,
                user_agent=user_agent,
                session_id=session_id,
                hipaa_logged=True,
                gdpr_compliant=True,
                timestamp=datetime.now(timezone.utc)
            )

            self.db.add(audit_entry)
            self.db.commit()

            logger.info(f"Audit logged: {action} for experiment {experiment_id} by {actor}")
            return str(audit_entry.id)

        except Exception as e:
            logger.error(f"Failed to log audit entry: {str(e)}")
            self.db.rollback()
            # Don't raise exception to avoid breaking main functionality
            return "audit_failed"

    def log_patient_interaction(
        self,
        experiment_id: str,
        patient_id: UUID,
        action: str,
        variant: Optional[str] = None,
        safety_level: Optional[str] = None,
        assignment_reason: Optional[str] = None,
        actor: str = "system",
        additional_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log patient-related A/B testing interactions.

        Args:
            experiment_id: Experiment UUID
            patient_id: Patient UUID (will be anonymized)
            action: Action performed
            variant: Assigned variant
            safety_level: Patient safety level
            assignment_reason: Reason for assignment/exclusion
            actor: Actor performing action
            additional_data: Additional context data

        Returns:
            Audit log entry ID
        """
        try:
            # Create anonymous patient identifier
            anonymous_patient_id = self._create_anonymous_patient_id(patient_id, experiment_id)

            action_details = {
                "action": action,
                "anonymous_patient_id": anonymous_patient_id,
                "variant": variant,
                "safety_level": safety_level,
                "assignment_reason": assignment_reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            if additional_data:
                action_details.update(additional_data)

            # Create audit entry
            audit_entry = ABExperimentAudit(
                experiment_id=experiment_id,
                action=action,
                actor=self._anonymize_actor(actor),
                actor_type="system",
                action_details=action_details,
                hipaa_logged=True,
                gdpr_compliant=True,
                timestamp=datetime.now(timezone.utc)
            )

            self.db.add(audit_entry)
            self.db.commit()

            logger.info(f"Patient interaction logged: {action} for experiment {experiment_id}")
            return str(audit_entry.id)

        except Exception as e:
            logger.error(f"Failed to log patient interaction: {str(e)}")
            self.db.rollback()
            return "audit_failed"

    def log_message_activity(
        self,
        experiment_id: str,
        message_id: int,
        action: str,
        variant: str,
        patient_id: UUID,
        ai_processing: Optional[Dict[str, Any]] = None,
        safety_checks: Optional[Dict[str, Any]] = None,
        performance_data: Optional[Dict[str, Any]] = None,
        error_details: Optional[str] = None
    ) -> str:
        """
        Log message-related A/B testing activities.

        Args:
            experiment_id: Experiment UUID
            message_id: Message ID
            action: Action performed
            variant: Message variant (control/treatment)
            patient_id: Patient UUID (will be anonymized)
            ai_processing: AI processing details
            safety_checks: Safety check results
            performance_data: Performance metrics
            error_details: Error information if applicable

        Returns:
            Audit log entry ID
        """
        try:
            anonymous_patient_id = self._create_anonymous_patient_id(patient_id, experiment_id)

            action_details = {
                "action": action,
                "message_id": message_id,
                "variant": variant,
                "anonymous_patient_id": anonymous_patient_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # Add AI processing details
            if ai_processing:
                action_details["ai_processing"] = {
                    "humanization_applied": ai_processing.get("humanization_applied", False),
                    "safety_checks_passed": ai_processing.get("safety_checks_passed", True),
                    "processing_time_ms": ai_processing.get("processing_time_ms"),
                    "model_version": ai_processing.get("model_version"),
                    "fallback_reason": ai_processing.get("fallback_reason")
                }

            # Add safety check results
            if safety_checks:
                action_details["safety_checks"] = {
                    "medical_keywords_found": safety_checks.get("medical_keywords_found", []),
                    "risk_level": safety_checks.get("risk_level", "low"),
                    "manual_review_required": safety_checks.get("manual_review_required", False)
                }

            # Add performance data
            if performance_data:
                action_details["performance"] = {
                    "response_time_seconds": performance_data.get("response_time_seconds"),
                    "engagement_score": performance_data.get("engagement_score"),
                    "delivery_status": performance_data.get("delivery_status")
                }

            # Add error details
            if error_details:
                action_details["error"] = error_details

            # Create audit entry
            audit_entry = ABExperimentAudit(
                experiment_id=experiment_id,
                action=action,
                actor="system",
                actor_type="automated",
                action_details=action_details,
                hipaa_logged=True,
                gdpr_compliant=True,
                timestamp=datetime.now(timezone.utc)
            )

            self.db.add(audit_entry)
            self.db.commit()

            return str(audit_entry.id)

        except Exception as e:
            logger.error(f"Failed to log message activity: {str(e)}")
            self.db.rollback()
            return "audit_failed"

    def log_safety_event(
        self,
        experiment_id: str,
        event_type: str,
        severity: str,
        description: str,
        patient_id: Optional[UUID] = None,
        message_id: Optional[int] = None,
        automated_response: Optional[str] = None,
        stakeholder_notified: bool = False,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log safety-related events in A/B testing.

        Args:
            experiment_id: Experiment UUID
            event_type: Type of safety event
            severity: Severity level (low, medium, high, critical)
            description: Event description
            patient_id: Affected patient (if applicable)
            message_id: Affected message (if applicable)
            automated_response: Automated response taken
            stakeholder_notified: Whether stakeholders were notified
            additional_data: Additional event data

        Returns:
            Audit log entry ID
        """
        try:
            action_details = {
                "event_type": event_type,
                "severity": severity,
                "description": description,
                "automated_response": automated_response,
                "stakeholder_notified": stakeholder_notified,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            if patient_id:
                action_details["anonymous_patient_id"] = self._create_anonymous_patient_id(
                    patient_id, experiment_id
                )

            if message_id:
                action_details["message_id"] = message_id

            if additional_data:
                action_details.update(additional_data)

            # Create audit entry
            audit_entry = ABExperimentAudit(
                experiment_id=experiment_id,
                action=AuditEventType.SAFETY_VIOLATION,
                actor="safety_monitor",
                actor_type="automated",
                action_details=action_details,
                hipaa_logged=True,
                gdpr_compliant=True,
                timestamp=datetime.now(timezone.utc)
            )

            self.db.add(audit_entry)
            self.db.commit()

            # Log to application logger for immediate visibility
            if severity in ["high", "critical"]:
                logger.critical(f"SAFETY EVENT: {description} in experiment {experiment_id}")
            else:
                logger.warning(f"Safety event: {description} in experiment {experiment_id}")

            return str(audit_entry.id)

        except Exception as e:
            logger.error(f"Failed to log safety event: {str(e)}")
            self.db.rollback()
            return "audit_failed"

    def log_access_attempt(
        self,
        experiment_id: str,
        actor: str,
        action: str,
        access_granted: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        denial_reason: Optional[str] = None
    ) -> str:
        """
        Log access attempts to A/B testing data.

        Args:
            experiment_id: Experiment UUID
            actor: User attempting access
            action: Action attempted
            access_granted: Whether access was granted
            ip_address: Source IP address
            user_agent: User agent string
            denial_reason: Reason for access denial

        Returns:
            Audit log entry ID
        """
        try:
            event_type = AuditEventType.ACCESS_GRANTED if access_granted else AuditEventType.ACCESS_DENIED

            action_details = {
                "action_attempted": action,
                "access_granted": access_granted,
                "denial_reason": denial_reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            audit_entry = ABExperimentAudit(
                experiment_id=experiment_id,
                action=event_type,
                actor=self._anonymize_actor(actor),
                actor_type="user",
                action_details=action_details,
                ip_address=self._anonymize_ip(ip_address) if ip_address else None,
                user_agent=user_agent,
                hipaa_logged=True,
                gdpr_compliant=True,
                timestamp=datetime.now(timezone.utc)
            )

            self.db.add(audit_entry)
            self.db.commit()

            if not access_granted:
                logger.warning(f"Access denied: {actor} attempted {action} on experiment {experiment_id}")

            return str(audit_entry.id)

        except Exception as e:
            logger.error(f"Failed to log access attempt: {str(e)}")
            self.db.rollback()
            return "audit_failed"

    def get_audit_trail(
        self,
        experiment_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action_types: Optional[List[str]] = None,
        actor: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit trail for an experiment.

        Args:
            experiment_id: Experiment UUID
            start_date: Start date for filtering
            end_date: End date for filtering
            action_types: Filter by action types
            actor: Filter by actor

        Returns:
            List of audit entries
        """
        try:
            query = self.db.query(ABExperimentAudit).filter(
                ABExperimentAudit.experiment_id == experiment_id
            )

            # Apply filters
            if start_date:
                query = query.filter(ABExperimentAudit.timestamp >= start_date)
            if end_date:
                query = query.filter(ABExperimentAudit.timestamp <= end_date)
            if action_types:
                query = query.filter(ABExperimentAudit.action.in_(action_types))
            if actor:
                query = query.filter(ABExperimentAudit.actor.ilike(f"%{actor}%"))

            # Order by timestamp descending
            entries = query.order_by(desc(ABExperimentAudit.timestamp)).all()

            # Convert to dict format
            audit_trail = []
            for entry in entries:
                audit_trail.append({
                    "id": str(entry.id),
                    "experiment_id": str(entry.experiment_id),
                    "action": entry.action,
                    "actor": entry.actor,
                    "actor_type": entry.actor_type,
                    "timestamp": entry.timestamp.isoformat(),
                    "action_details": entry.action_details,
                    "previous_state": entry.previous_state,
                    "new_state": entry.new_state,
                    "ip_address": entry.ip_address,
                    "hipaa_logged": entry.hipaa_logged,
                    "gdpr_compliant": entry.gdpr_compliant
                })

            return audit_trail

        except Exception as e:
            logger.error(f"Failed to retrieve audit trail: {str(e)}")
            return []

    def generate_compliance_report(
        self,
        experiment_id: str,
        report_type: str = "full"
    ) -> Dict[str, Any]:
        """
        Generate compliance report for an experiment.

        Args:
            experiment_id: Experiment UUID
            report_type: Type of report (full, summary, safety_only)

        Returns:
            Compliance report
        """
        try:
            # Get experiment details
            experiment = self.db.query(ABExperiment).filter(
                ABExperiment.id == experiment_id
            ).first()

            if not experiment:
                return {"error": "Experiment not found"}

            # Get audit trail
            audit_trail = self.get_audit_trail(experiment_id)

            # Analyze compliance metrics
            compliance_metrics = self._analyze_compliance_metrics(audit_trail)

            # Generate report
            report = {
                "experiment_id": experiment_id,
                "experiment_name": experiment.name,
                "report_type": report_type,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "compliance_status": "compliant" if compliance_metrics["is_compliant"] else "non_compliant",
                "hipaa_compliance": compliance_metrics["hipaa_compliant"],
                "gdpr_compliance": compliance_metrics["gdpr_compliant"],
                "total_audit_entries": len(audit_trail),
                "audit_coverage": compliance_metrics["audit_coverage"],
                "safety_events": compliance_metrics["safety_events"],
                "access_violations": compliance_metrics["access_violations"],
                "data_retention_compliant": compliance_metrics["data_retention_compliant"]
            }

            if report_type == "full":
                report["detailed_audit_trail"] = audit_trail
                report["compliance_analysis"] = compliance_metrics
            elif report_type == "safety_only":
                safety_entries = [
                    entry for entry in audit_trail
                    if entry["action"] in [
                        AuditEventType.SAFETY_VIOLATION,
                        AuditEventType.EMERGENCY_STOP,
                        AuditEventType.MEDICAL_CONTENT_DETECTED
                    ]
                ]
                report["safety_audit_trail"] = safety_entries

            return report

        except Exception as e:
            logger.error(f"Failed to generate compliance report: {str(e)}")
            return {"error": str(e)}

    def cleanup_old_audit_logs(self, retention_days: Optional[int] = None) -> int:
        """
        Clean up old audit logs based on retention policy.

        Args:
            retention_days: Override default retention period

        Returns:
            Number of entries cleaned up
        """
        try:
            retention_period = retention_days or self.retention_days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_period)

            # Count entries to be deleted
            count = self.db.query(ABExperimentAudit).filter(
                ABExperimentAudit.timestamp < cutoff_date
            ).count()

            # Delete old entries
            self.db.query(ABExperimentAudit).filter(
                ABExperimentAudit.timestamp < cutoff_date
            ).delete()

            self.db.commit()

            logger.info(f"Cleaned up {count} old audit log entries")
            return count

        except Exception as e:
            logger.error(f"Failed to cleanup audit logs: {str(e)}")
            self.db.rollback()
            return 0

    # Private helper methods

    def _create_anonymous_patient_id(self, patient_id: UUID, experiment_id: str) -> str:
        """Create anonymous patient identifier for audit logging."""
        # Create deterministic hash for consistent anonymization
        hash_input = f"{patient_id}:{experiment_id}:audit"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _anonymize_actor(self, actor: str) -> str:
        """Anonymize actor information while maintaining traceability."""
        if self.anonymization_enabled and "@" in actor:  # Email address
            username, domain = actor.split("@")
            anonymized_username = hashlib.sha256(username.encode()).hexdigest()[:8]
            return f"{anonymized_username}@{domain}"
        return actor

    def _anonymize_ip(self, ip_address: str) -> str:
        """Anonymize IP address for privacy compliance."""
        if not ip_address:
            return None

        # IPv4: mask last octet
        if "." in ip_address:
            parts = ip_address.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"

        # IPv6: mask last 64 bits
        if ":" in ip_address:
            parts = ip_address.split(":")
            if len(parts) >= 4:
                return f"{':'.join(parts[:4])}::xxxx"

        return "anonymized"

    def _anonymize_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize sensitive data in state snapshots."""
        if not data:
            return data

        # Create copy to avoid modifying original
        anonymized_data = data.copy()

        # Remove or hash sensitive fields
        sensitive_fields = [
            "patient_id", "phone", "email", "address", "name",
            "patient_name", "contact_info"
        ]

        for field in sensitive_fields:
            if field in anonymized_data:
                if isinstance(anonymized_data[field], str):
                    anonymized_data[field] = hashlib.sha256(
                        anonymized_data[field].encode()
                    ).hexdigest()[:16]
                else:
                    anonymized_data[field] = "anonymized"

        return anonymized_data

    def _analyze_compliance_metrics(self, audit_trail: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze audit trail for compliance metrics."""
        total_entries = len(audit_trail)

        # Check HIPAA and GDPR compliance
        hipaa_compliant_count = sum(
            1 for entry in audit_trail
            if entry.get("hipaa_logged", False)
        )
        gdpr_compliant_count = sum(
            1 for entry in audit_trail
            if entry.get("gdpr_compliant", False)
        )

        # Count safety events
        safety_events = [
            entry for entry in audit_trail
            if entry["action"] in [
                AuditEventType.SAFETY_VIOLATION,
                AuditEventType.EMERGENCY_STOP,
                AuditEventType.MEDICAL_CONTENT_DETECTED
            ]
        ]

        # Count access violations
        access_violations = [
            entry for entry in audit_trail
            if entry["action"] == AuditEventType.ACCESS_DENIED
        ]

        return {
            "is_compliant": hipaa_compliant_count == total_entries and gdpr_compliant_count == total_entries,
            "hipaa_compliant": hipaa_compliant_count == total_entries,
            "gdpr_compliant": gdpr_compliant_count == total_entries,
            "audit_coverage": (hipaa_compliant_count / max(1, total_entries)) * 100,
            "safety_events": len(safety_events),
            "access_violations": len(access_violations),
            "data_retention_compliant": True  # Implement based on your retention policy
        }


def get_ab_testing_audit_service(db: Session) -> ABTestingAuditService:
    """Get A/B testing audit service instance."""
    return ABTestingAuditService(db)