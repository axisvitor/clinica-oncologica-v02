"""
Enhanced Report Service for comprehensive report generation.
Updated with FIX #13 - PROTEÇÃO DE DADOS SENSÍVEIS
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func, select

from app.models.patient import Patient
from app.models.message import Message
from app.utils.logging import get_logger
from app.security.data_protection import (
    get_data_protection_service,
    SensitiveDataType,
    AccessReason,
)

logger = get_logger(__name__)


class ReportGenerationError(Exception):
    """Custom exception for report generation failures."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self):
        return self.message


class ReportService:
    """Enhanced report service with data protection and FIX #6: N+1 query optimization."""

    def __init__(self, db: Any):
        self.db = db
        self.data_protection = get_data_protection_service()
        self._query_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL

    async def create_report(self, report_request, user_id: UUID):
        """Create a new report record with sensitive data protection."""
        try:
            # Log sensitive data access
            self.data_protection.log_sensitive_access(
                user_id=user_id,
                data_type=SensitiveDataType.MEDICAL_INFO,
                entity_id=uuid4(),
                access_reason=AccessReason.MEDICAL_TREATMENT,
                additional_context={"action": "create_report"},
            )

            # Sanitize report request data
            sanitized_title = self.data_protection.sanitize_for_logging(
                report_request.title
            )

            report_data = {
                "id": uuid4(),
                "title": sanitized_title,
                "report_type": report_request.report_type,
                "status": "generating",
                "format": report_request.format,
                "created_at": datetime.utcnow(),
                "user_id": user_id,
            }

            class MockReport:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)

                def dict(self):
                    data = {
                        key: getattr(self, key)
                        for key in dir(self)
                        if not key.startswith("_") and not callable(getattr(self, key))
                    }
                    protection_service = get_data_protection_service()
                    return protection_service.sanitize_for_logging(data)

            return MockReport(report_data)

        except Exception as e:
            logger.error(f"Error creating report: {str(e)}")
            raise

    async def generate_patient_report(
        self,
        patient_id: UUID,
        user_id: UUID,
        include_messages: bool = True,
        include_analytics: bool = True,
    ) -> Dict[str, Any]:
        """FIX #6: Generate comprehensive patient report with optimized queries."""
        try:
            # Log sensitive data access
            self.data_protection.log_sensitive_access(
                user_id=user_id,
                data_type=SensitiveDataType.MEDICAL_INFO,
                entity_id=patient_id,
                access_reason=AccessReason.MEDICAL_TREATMENT,
                additional_context={"action": "generate_patient_report"},
            )

            # FIX #6: Use eager loading to prevent N+1 queries
            patient_query = (
                select(Patient)
                .options(
                    joinedload(Patient.doctor),
                    selectinload(Patient.messages)
                    if include_messages
                    else selectinload(Patient.messages).selectinload(Message.id),
                    selectinload(Patient.flow_states),
                    selectinload(Patient.quiz_responses),
                    selectinload(Patient.medical_reports),
                )
                .where(Patient.id == patient_id)
            )

            result = self.db.execute(patient_query)
            patient = result.scalar_one_or_none()

            if not patient:
                raise ValueError(f"Patient {patient_id} not found")

            # Build report data with pre-loaded relationships
            report_data = {
                "patient_id": str(patient.id),
                "patient_name": self.data_protection.sanitize_for_logging(patient.name),
                "doctor_name": patient.doctor.full_name if patient.doctor else None,
                "flow_state": patient.flow_state.value,
                "current_day": patient.current_day,
                "treatment_type": patient.treatment_type,
                "created_at": patient.created_at.isoformat(),
                "updated_at": patient.updated_at.isoformat(),
            }

            if include_messages:
                # Messages are already loaded, no additional queries
                report_data["message_count"] = len(patient.messages)
                report_data["latest_message"] = {
                    "content": self.data_protection.sanitize_for_logging(
                        patient.messages[0].content
                    )
                    if patient.messages
                    else None,
                    "timestamp": patient.messages[0].created_at.isoformat()
                    if patient.messages
                    else None,
                    "direction": patient.messages[0].direction.value
                    if patient.messages
                    else None,
                }

            if include_analytics:
                # Analytics are already loaded, no additional queries
                report_data["flow_states_count"] = len(patient.flow_states)
                report_data["quiz_responses_count"] = len(patient.quiz_responses)
                report_data["medical_reports_count"] = len(patient.medical_reports)

            return report_data

        except Exception as e:
            logger.error(f"Error generating patient report: {str(e)}")
            raise

    async def generate_bulk_patient_reports(
        self, patient_ids: List[UUID], user_id: UUID, include_messages: bool = True
    ) -> List[Dict[str, Any]]:
        """FIX #6: Generate multiple patient reports with optimized bulk queries."""
        try:
            # Log bulk access
            self.data_protection.log_sensitive_access(
                user_id=user_id,
                data_type=SensitiveDataType.MEDICAL_INFO,
                entity_id=uuid4(),
                access_reason=AccessReason.MEDICAL_TREATMENT,
                additional_context={
                    "action": "bulk_patient_reports",
                    "patient_count": len(patient_ids),
                },
            )

            # FIX #6: Single query with eager loading for all patients
            patients_query = (
                select(Patient)
                .options(
                    joinedload(Patient.doctor),
                    selectinload(Patient.messages).selectinload(Message.patient)
                    if include_messages
                    else selectinload(Patient.messages).selectinload(Message.id),
                    selectinload(Patient.flow_states),
                )
                .where(Patient.id.in_(patient_ids))
            )

            result = self.db.execute(patients_query)
            patients = result.scalars().all()

            # Process all patients with pre-loaded data
            reports = []
            for patient in patients:
                report_data = {
                    "patient_id": str(patient.id),
                    "patient_name": self.data_protection.sanitize_for_logging(
                        patient.name
                    ),
                    "doctor_name": patient.doctor.full_name if patient.doctor else None,
                    "flow_state": patient.flow_state.value,
                    "current_day": patient.current_day,
                    "treatment_type": patient.treatment_type,
                }

                if include_messages:
                    # Pre-loaded, no additional query
                    report_data["message_count"] = len(patient.messages)

                reports.append(report_data)

            return reports

        except Exception as e:
            logger.error(f"Error generating bulk patient reports: {str(e)}")
            raise

    async def get_doctor_dashboard_data(
        self, doctor_id: UUID, user_id: UUID
    ) -> Dict[str, Any]:
        """FIX #6: Get doctor dashboard data with optimized aggregation queries."""
        try:
            # Log access
            self.data_protection.log_sensitive_access(
                user_id=user_id,
                data_type=SensitiveDataType.MEDICAL_INFO,
                entity_id=doctor_id,
                access_reason=AccessReason.MEDICAL_TREATMENT,
                additional_context={"action": "doctor_dashboard"},
            )

            # FIX #6: Use aggregation queries instead of loading all data

            # Patient statistics by flow state (single query)
            patient_stats_query = (
                select(Patient.flow_state, func.count(Patient.id).label("count"))
                .where(Patient.doctor_id == doctor_id)
                .group_by(Patient.flow_state)
            )

            patient_stats_result = self.db.execute(patient_stats_query)
            patient_stats = {
                row.flow_state.value: row.count for row in patient_stats_result
            }

            # Message statistics (aggregated query)
            message_stats_query = (
                select(
                    func.count(Message.id).label("total_messages"),
                    func.count(Message.id)
                    .filter(Message.direction == "outbound")
                    .label("outbound_count"),
                    func.count(Message.id)
                    .filter(Message.direction == "inbound")
                    .label("inbound_count"),
                    func.count(Message.id)
                    .filter(Message.status == "failed")
                    .label("failed_count"),
                )
                .select_from(Message.join(Patient, Message.patient_id == Patient.id))
                .where(Patient.doctor_id == doctor_id)
            )

            message_stats_result = self.db.execute(message_stats_query).first()

            # Recent patients with minimal data loading
            recent_patients_query = (
                select(Patient.id, Patient.name, Patient.flow_state, Patient.updated_at)
                .where(Patient.doctor_id == doctor_id)
                .order_by(Patient.updated_at.desc())
                .limit(10)
            )

            recent_patients_result = self.db.execute(recent_patients_query)
            recent_patients = [
                {
                    "id": str(row.id),
                    "name": self.data_protection.sanitize_for_logging(row.name),
                    "flow_state": row.flow_state.value,
                    "last_activity": row.updated_at.isoformat(),
                }
                for row in recent_patients_result
            ]

            return {
                "doctor_id": str(doctor_id),
                "patient_statistics": patient_stats,
                "message_statistics": {
                    "total_messages": message_stats_result.total_messages or 0,
                    "outbound_messages": message_stats_result.outbound_count or 0,
                    "inbound_messages": message_stats_result.inbound_count or 0,
                    "failed_messages": message_stats_result.failed_count or 0,
                },
                "recent_patients": recent_patients,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating doctor dashboard data: {str(e)}")
            raise

    async def get_system_analytics(
        self, user_id: UUID, days: int = 30
    ) -> Dict[str, Any]:
        """FIX #6: Get system-wide analytics with optimized aggregation queries."""
        try:
            # Log access
            self.data_protection.log_sensitive_access(
                user_id=user_id,
                data_type=SensitiveDataType.SYSTEM_ANALYTICS,
                entity_id=uuid4(),
                access_reason=AccessReason.SYSTEM_ADMINISTRATION,
                additional_context={"action": "system_analytics", "days": days},
            )

            start_date = datetime.utcnow() - timedelta(days=days)

            # FIX #6: Single aggregation query for multiple metrics
            analytics_query = select(
                func.count(Patient.id).label("total_patients"),
                func.count(Patient.id)
                .filter(Patient.created_at >= start_date)
                .label("new_patients"),
                func.count(Patient.id)
                .filter(Patient.flow_state == "active")
                .label("active_patients"),
                func.count(Message.id).label("total_messages"),
                func.count(Message.id)
                .filter(Message.created_at >= start_date)
                .label("recent_messages"),
                func.count(Message.id)
                .filter(Message.status == "failed")
                .label("failed_messages"),
                func.avg(Patient.current_day).label("avg_treatment_day"),
            ).select_from(Patient.outerjoin(Message, Patient.id == Message.patient_id))

            analytics_result = self.db.execute(analytics_query).first()

            # Flow state distribution (separate optimized query)
            flow_distribution_query = select(
                Patient.flow_state, func.count(Patient.id).label("count")
            ).group_by(Patient.flow_state)

            flow_distribution_result = self.db.execute(flow_distribution_query)
            flow_distribution = {
                row.flow_state.value: row.count for row in flow_distribution_result
            }

            return {
                "analytics_period_days": days,
                "total_patients": analytics_result.total_patients or 0,
                "new_patients_period": analytics_result.new_patients or 0,
                "active_patients": analytics_result.active_patients or 0,
                "total_messages": analytics_result.total_messages or 0,
                "recent_messages_period": analytics_result.recent_messages or 0,
                "failed_messages": analytics_result.failed_messages or 0,
                "average_treatment_day": float(analytics_result.avg_treatment_day or 0),
                "flow_state_distribution": flow_distribution,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating system analytics: {str(e)}")
            raise
