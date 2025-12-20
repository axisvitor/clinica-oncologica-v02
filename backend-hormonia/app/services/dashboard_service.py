"""
Dashboard Service
Business logic for dashboard metrics and data aggregation.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, text, case, extract

from app.models.patient import Patient
from app.models.alert import Alert, AlertSeverity
from app.models.message import Message
from app.models.flow import PatientFlowState as PatientFlow
from app.schemas.v2.dashboard import TimeRangeEnum

logger = logging.getLogger(__name__)

MAX_PATIENT_IDS_LIMIT = 1000


class DashboardService:
    """Service for dashboard data aggregation and metrics."""

    def __init__(self, db: Any):
        self.db = db

    def validate_patient_ids(
        self, patient_ids: Optional[List[UUID]]
    ) -> Optional[List[str]]:
        """
        Validate and sanitize patient IDs to prevent SQL injection.
        """
        if patient_ids is None:
            return None

        # Check length limit to prevent DoS
        if len(patient_ids) > MAX_PATIENT_IDS_LIMIT:
            logger.warning(
                f"Attempted to query {len(patient_ids)} patient IDs (limit: {MAX_PATIENT_IDS_LIMIT})"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Too many patient IDs. Maximum allowed: {MAX_PATIENT_IDS_LIMIT}",
            )

        validated_ids = []
        suspicious_patterns = [
            "DROP",
            "INSERT",
            "DELETE",
            "UPDATE",
            "EXEC",
            "EXECUTE",
            "UNION",
            "SELECT",
            "--",
            "/*",
            "*/",
            ";",
            "xp_",
            "sp_",
        ]

        for pid in patient_ids:
            try:
                # Convert UUID to string and validate format
                pid_str = str(pid)

                # Check for SQL injection patterns
                pid_upper = pid_str.upper()
                for pattern in suspicious_patterns:
                    if pattern in pid_upper:
                        logger.error(
                            f"Suspicious SQL pattern detected in patient_id: {pid_str}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid patient_id format detected",
                        )

                # Validate UUID format (36 characters with hyphens)
                if len(pid_str) != 36 or pid_str.count("-") != 4:
                    logger.error(f"Invalid UUID format: {pid_str}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid patient_id format",
                    )

                validated_ids.append(pid_str)

            except (ValueError, AttributeError) as e:
                logger.error(f"Invalid patient_id format: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid patient_id format",
                )

        return validated_ids

    def calculate_date_range(
        self,
        time_range: TimeRangeEnum,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None,
    ) -> Tuple[datetime, datetime]:
        """Calculate start and end dates based on time range enum."""
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if time_range == TimeRangeEnum.TODAY:
            return today, now
        elif time_range == TimeRangeEnum.WEEK:
            return now - timedelta(days=7), now
        elif time_range == TimeRangeEnum.MONTH:
            return now - timedelta(days=30), now
        elif time_range == TimeRangeEnum.QUARTER:
            return now - timedelta(days=90), now
        elif time_range == TimeRangeEnum.YEAR:
            return now - timedelta(days=365), now
        elif time_range == TimeRangeEnum.CUSTOM:
            if not custom_start or not custom_end:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="custom_start and custom_end required for CUSTOM time range",
                )
            return custom_start, custom_end
        else:
            return now - timedelta(days=7), now

    def get_patient_metrics(
        self,
        patient_ids: Optional[List[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculate patient metrics for dashboard widgets."""
        query = self.db.query(Patient)

        if patient_ids:
            query = query.filter(Patient.id.in_(patient_ids))

        # Total patients
        total_patients = query.count()

        # Active patients
        active_patients = query.filter(Patient.is_active).count()

        # New patients in time range
        new_patients = 0
        if start_date:
            new_patients = query.filter(Patient.created_at >= start_date).count()

        # High-risk patients (based on recent alerts)
        high_risk_count = 0
        if patient_ids:
            high_risk_count = (
                self.db.query(Patient)
                .join(Alert)
                .filter(
                    Patient.id.in_(patient_ids),
                    Alert.severity.in_([AlertSeverity.CRITICAL, AlertSeverity.HIGH]),
                    not Alert.acknowledged,
                )
                .distinct()
                .count()
            )

        return {
            "total_patients": total_patients,
            "active_patients": active_patients,
            "inactive_patients": total_patients - active_patients,
            "new_patients": new_patients,
            "high_risk_patients": high_risk_count,
        }

    def get_message_metrics(
        self,
        patient_ids: Optional[List[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculate message metrics."""
        query = self.db.query(
            func.count(Message.id).label("total_messages"),
            func.count(case((Message.status == "sent", 1))).label("sent_count"),
            func.count(case((Message.status == "delivered", 1))).label(
                "delivered_count"
            ),
            func.count(case((Message.status == "failed", 1))).label("failed_count"),
            func.count(case((Message.patient_response_received, 1))).label(
                "response_count"
            ),
        )

        if patient_ids:
            query = query.filter(Message.patient_id.in_(patient_ids))

        if start_date:
            query = query.filter(Message.created_at >= start_date)

        if end_date:
            query = query.filter(Message.created_at <= end_date)

        result = query.one()

        total = result.total_messages or 0
        responses = result.response_count or 0
        response_rate = round((responses / total * 100), 1) if total > 0 else 0

        return {
            "total_messages": total,
            "sent_count": result.sent_count or 0,
            "delivered_count": result.delivered_count or 0,
            "failed_count": result.failed_count or 0,
            "response_count": responses,
            "response_rate": response_rate,
        }

    def get_alert_metrics(
        self,
        patient_ids: Optional[List[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculate alert metrics."""
        query = self.db.query(Alert)

        if patient_ids:
            query = query.filter(Alert.patient_id.in_(patient_ids))

        if start_date:
            query = query.filter(Alert.created_at >= start_date)

        if end_date:
            query = query.filter(Alert.created_at <= end_date)

        alerts = query.all()

        total_alerts = len(alerts)
        pending_alerts = len([a for a in alerts if not a.acknowledged])
        critical_alerts = len(
            [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        )
        high_alerts = len([a for a in alerts if a.severity == AlertSeverity.HIGH])

        return {
            "total_alerts": total_alerts,
            "pending_alerts": pending_alerts,
            "acknowledged_alerts": total_alerts - pending_alerts,
            "critical_alerts": critical_alerts,
            "high_alerts": high_alerts,
            "medium_alerts": len(
                [a for a in alerts if a.severity == AlertSeverity.MEDIUM]
            ),
            "low_alerts": len([a for a in alerts if a.severity == AlertSeverity.LOW]),
        }

    def get_flow_metrics(
        self,
        patient_ids: Optional[List[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculate flow metrics."""
        avg_days_expr = func.avg(
            case(
                (
                    and_(
                        PatientFlow.status == "completed",
                        PatientFlow.updated_at.isnot(None),
                    ),
                    extract("epoch", PatientFlow.updated_at - PatientFlow.created_at)
                    / 86400,
                ),
                else_=None,
            )
        )

        query = self.db.query(
            func.count(PatientFlow.id).label("total_flows"),
            func.count(case((PatientFlow.status == "active", 1))).label("active_flows"),
            func.count(case((PatientFlow.status == "completed", 1))).label(
                "completed_flows"
            ),
            func.count(case((PatientFlow.status == "paused", 1))).label("paused_flows"),
            avg_days_expr.label("avg_completion_days"),
        )

        if patient_ids:
            query = query.filter(PatientFlow.patient_id.in_(patient_ids))

        if start_date:
            query = query.filter(PatientFlow.created_at >= start_date)

        if end_date:
            query = query.filter(PatientFlow.created_at <= end_date)

        result = query.one()

        total = result.total_flows or 0
        completed = result.completed_flows or 0
        completion_rate = round((completed / total * 100), 1) if total > 0 else 0

        return {
            "total_flows": total,
            "active_flows": result.active_flows or 0,
            "completed_flows": completed,
            "paused_flows": result.paused_flows or 0,
            "completion_rate": completion_rate,
            "avg_completion_days": round(result.avg_completion_days or 0, 1),
        }

    def get_recent_activity(
        self, patient_ids: Optional[List[UUID]] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent activity for dashboard feed."""
        activities = []

        params = {"limit": limit // 3}
        patient_filter = ""

        if patient_ids:
            validated_ids = self.validate_patient_ids(patient_ids)
            patient_filter = "AND m.patient_id = ANY(:patient_ids)"
            params["patient_ids"] = validated_ids

        # Recent messages
        message_query_sql = f"""
            SELECT
                'message_sent' as type,
                CONCAT('Mensagem enviada para ', p.full_name) as description,
                p.full_name as entity_name,
                m.created_at as timestamp,
                m.id::text as reference_id
            FROM messages m
            JOIN patients p ON m.patient_id = p.id
            WHERE m.created_at >= NOW() - INTERVAL '24 hours'
            {patient_filter}
            ORDER BY m.created_at DESC
            LIMIT :limit
        """

        message_results = self.db.execute(text(message_query_sql), params).fetchall()
        for row in message_results:
            activities.append(
                {
                    "id": f"msg_{row.reference_id}",
                    "type": row.type,
                    "description": row.description,
                    "entity_name": row.entity_name,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                }
            )

        # Recent alerts
        alert_patient_filter = (
            patient_filter.replace("m.patient_id", "a.patient_id")
            if patient_filter
            else ""
        )

        alert_params = {"limit": limit // 3}
        if patient_ids:
            alert_params["patient_ids"] = params["patient_ids"]

        alert_query_sql = f"""
            SELECT
                'alert_created' as type,
                CONCAT('Alerta: ', a.description) as description,
                p.full_name as entity_name,
                a.created_at as timestamp,
                a.id::text as reference_id
            FROM alerts a
            JOIN patients p ON a.patient_id = p.id
            WHERE a.created_at >= NOW() - INTERVAL '24 hours'
            {alert_patient_filter}
            ORDER BY a.created_at DESC
            LIMIT :limit
        """

        alert_results = self.db.execute(text(alert_query_sql), alert_params).fetchall()
        for row in alert_results:
            activities.append(
                {
                    "id": f"alert_{row.reference_id}",
                    "type": row.type,
                    "description": row.description,
                    "entity_name": row.entity_name,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                }
            )

        activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return activities[:limit]

    def get_engagement_chart_data(
        self, patient_ids: Optional[List[UUID]] = None, days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get engagement chart data (messages sent vs responses)."""
        start_date = datetime.now(timezone.utc).date() - timedelta(days=days - 1)

        params = {"start_date": start_date}
        patient_filter = ""

        if patient_ids:
            validated_ids = self.validate_patient_ids(patient_ids)
            patient_filter = "AND patient_id = ANY(:patient_ids)"
            params["patient_ids"] = validated_ids

        query_sql = f"""
            WITH date_series AS (
                SELECT generate_series(
                    :start_date::date,
                    CURRENT_DATE,
                    '1 day'::interval
                )::date AS date
            ),
            daily_messages AS (
                SELECT DATE(created_at) as date,
                   COUNT(*) as messages_sent,
                   COUNT(CASE WHEN patient_response_received = true THEN 1 END) as responses_received
                FROM messages
                WHERE DATE(created_at) >= :start_date
                {patient_filter}
                GROUP BY DATE(created_at)
            )
            SELECT ds.date,
               COALESCE(dm.messages_sent, 0) as messages_sent,
               COALESCE(dm.responses_received, 0) as responses_received,
               CASE
                   WHEN COALESCE(dm.messages_sent, 0) = 0 THEN 0
                   ELSE ROUND((COALESCE(dm.responses_received, 0)::float / dm.messages_sent) * 100, 1)
               END as response_rate
            FROM date_series ds
            LEFT JOIN daily_messages dm ON ds.date = dm.date
            ORDER BY ds.date
        """

        results = self.db.execute(text(query_sql), params).fetchall()

        return [
            {
                "date": row.date.strftime("%Y-%m-%d"),
                "messages_sent": row.messages_sent,
                "responses_received": row.responses_received,
                "response_rate": row.response_rate,
            }
            for row in results
        ]
