"""
Dashboard Service
Business logic for dashboard metrics and data aggregation.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, case, extract

from app.models.patient import Patient
from app.models.alert import Alert, AlertSeverity
from app.models.message import Message, MessageDirection
from app.models.flow import PatientFlowState as PatientFlow
from app.models.enums import FlowState
from app.schemas.v2.dashboard import TimeRangeEnum
from app.utils.query_cache import get_query_cache
from app.utils.timezone import now_sao_paulo

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
        now = now_sao_paulo()
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
        try:
            cache = get_query_cache()

            # Generate cache key
            cache_key = cache.generate_cache_key(
                "dashboard:patient_metrics",
                patient_ids=str(sorted(patient_ids)) if patient_ids else "all",
                start=str(start_date) if start_date else "none",
                end=str(end_date) if end_date else "none"
            )

            # Try cache
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception as e:
            logger.warning(f"Cache GET failed in get_patient_metrics: {e}")

        # Execute query
        query = self.db.query(Patient)

        if patient_ids:
            query = query.filter(Patient.id.in_(patient_ids))

        # Total patients
        total_patients = query.count()

        # Active patients
        active_patients = query.filter(Patient.flow_state == FlowState.ACTIVE).count()

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
                    Alert.acknowledged == False,  # noqa: E712
                )
                .distinct()
                .count()
            )

        result = {
            "total_patients": total_patients,
            "active_patients": active_patients,
            "inactive_patients": total_patients - active_patients,
            "new_patients": new_patients,
            "high_risk_patients": high_risk_count,
        }

        # Save to cache
        try:
            cache.set(cache_key, result, ttl=600, tags=["metrics:patients"])
        except Exception as e:
            logger.warning(f"Cache SET failed in get_patient_metrics: {e}")

        return result

    def get_message_metrics(
        self,
        patient_ids: Optional[List[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculate message metrics."""
        try:
            cache = get_query_cache()

            # Generate cache key
            cache_key = cache.generate_cache_key(
                "dashboard:message_metrics",
                patient_ids=str(sorted(patient_ids)) if patient_ids else "all",
                start=str(start_date) if start_date else "none",
                end=str(end_date) if end_date else "none"
            )

            # Try cache
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception as e:
            logger.warning(f"Cache GET failed in get_message_metrics: {e}")

        # Execute query
        query = self.db.query(
            func.count(Message.id).label("total_messages"),
            func.count(case((Message.status == "sent", 1))).label("sent_count"),
            func.count(case((Message.status == "delivered", 1))).label(
                "delivered_count"
            ),
            func.count(case((Message.status == "failed", 1))).label("failed_count"),
            func.count(case((Message.direction == MessageDirection.INBOUND, 1))).label(
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

        result_dict = {
            "total_messages": total,
            "sent_count": result.sent_count or 0,
            "delivered_count": result.delivered_count or 0,
            "failed_count": result.failed_count or 0,
            "response_count": responses,
            "response_rate": response_rate,
        }

        # Save to cache with dynamic tags
        try:
            tags = ["metrics:messages"]
            if patient_ids:
                # Add patient-specific tags for granular invalidation
                tags.extend([f"patient:{pid}" for pid in patient_ids])
            cache.set(cache_key, result_dict, ttl=180, tags=tags)
        except Exception as e:
            logger.warning(f"Cache SET failed in get_message_metrics: {e}")

        return result_dict

    def get_alert_metrics(
        self,
        patient_ids: Optional[List[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculate alert metrics."""
        try:
            cache = get_query_cache()

            # Generate cache key
            cache_key = cache.generate_cache_key(
                "dashboard:alert_metrics",
                patient_ids=str(sorted(patient_ids)) if patient_ids else "all",
                start=str(start_date) if start_date else "none",
                end=str(end_date) if end_date else "none"
            )

            # Try cache
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception as e:
            logger.warning(f"Cache GET failed in get_alert_metrics: {e}")

        # Execute query
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

        result = {
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

        # Save to cache with dynamic tags
        try:
            tags = ["metrics:alerts"]
            if patient_ids:
                # Add patient-specific tags for granular invalidation
                tags.extend([f"patient:{pid}" for pid in patient_ids])
            cache.set(cache_key, result, ttl=120, tags=tags)
        except Exception as e:
            logger.warning(f"Cache SET failed in get_alert_metrics: {e}")

        return result

    def get_flow_metrics(
        self,
        patient_ids: Optional[List[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculate flow metrics."""
        try:
            cache = get_query_cache()

            # Generate cache key
            cache_key = cache.generate_cache_key(
                "dashboard:flow_metrics",
                patient_ids=str(sorted(patient_ids)) if patient_ids else "all",
                start=str(start_date) if start_date else "none",
                end=str(end_date) if end_date else "none"
            )

            # Try cache
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception as e:
            logger.warning(f"Cache GET failed in get_flow_metrics: {e}")

        # Execute query
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

        result_dict = {
            "total_flows": total,
            "active_flows": result.active_flows or 0,
            "completed_flows": completed,
            "paused_flows": result.paused_flows or 0,
            "completion_rate": completion_rate,
            "avg_completion_days": round(result.avg_completion_days or 0, 1),
        }

        # Save to cache
        try:
            cache.set(cache_key, result_dict, ttl=300, tags=["metrics:flows"])
        except Exception as e:
            logger.warning(f"Cache SET failed in get_flow_metrics: {e}")

        return result_dict

    def get_recent_activity(
        self, patient_ids: Optional[List[UUID]] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent activity for dashboard feed."""
        try:
            cache = get_query_cache()

            # Generate cache key
            cache_key = cache.generate_cache_key(
                "dashboard:recent_activity",
                patient_ids=str(sorted(patient_ids)) if patient_ids else "all",
                limit=str(limit)
            )

            # Try cache
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception as e:
            logger.warning(f"Cache GET failed in get_recent_activity: {e}")

        # Execute query
        activities: List[Dict[str, Any]] = []
        item_limit = max(1, limit // 3)
        cutoff = now_sao_paulo() - timedelta(hours=24)
        validated_ids = None
        if patient_ids:
            validated_ids = [UUID(pid) for pid in self.validate_patient_ids(patient_ids)]

        try:
            # Recent messages
            message_query = (
                self.db.query(
                    Message.id.label("reference_id"),
                    Message.created_at.label("timestamp"),
                    Patient.name.label("entity_name"),
                )
                .join(Patient, Message.patient_id == Patient.id)
                .filter(Message.created_at >= cutoff)
            )
            if validated_ids:
                message_query = message_query.filter(
                    Message.patient_id.in_(validated_ids)
                )

            message_results = (
                message_query.order_by(Message.created_at.desc())
                .limit(item_limit)
                .all()
            )
            for row in message_results:
                activities.append(
                    {
                        "id": f"msg_{row.reference_id}",
                        "type": "message_sent",
                        "description": f"Mensagem enviada para {row.entity_name}",
                        "entity_name": row.entity_name,
                        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    }
                )

            # Recent alerts
            alert_query = (
                self.db.query(
                    Alert.id.label("reference_id"),
                    Alert.created_at.label("timestamp"),
                    Alert.description.label("alert_description"),
                    Patient.name.label("entity_name"),
                )
                .join(Patient, Alert.patient_id == Patient.id)
                .filter(Alert.created_at >= cutoff)
            )
            if validated_ids:
                alert_query = alert_query.filter(Alert.patient_id.in_(validated_ids))

            alert_results = (
                alert_query.order_by(Alert.created_at.desc())
                .limit(item_limit)
                .all()
            )
            for row in alert_results:
                activities.append(
                    {
                        "id": f"alert_{row.reference_id}",
                        "type": "alert_created",
                        "description": f"Alerta: {row.alert_description}",
                        "entity_name": row.entity_name,
                        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    }
                )
        except Exception as e:
            # Be resilient in dashboard widgets when DB dialect differences
            # or optional tables/features are unavailable.
            logger.warning(f"Failed to build recent activity feed: {e}")
            activities = []

        activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        result = activities[:limit]

        # Save to cache
        try:
            cache.set(cache_key, result, ttl=60, tags=["activity"])
        except Exception as e:
            logger.warning(f"Cache SET failed in get_recent_activity: {e}")

        return result

    def get_engagement_chart_data(
        self, patient_ids: Optional[List[UUID]] = None, days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get engagement chart data (messages sent vs responses)."""
        start_date = now_sao_paulo().date() - timedelta(days=days - 1)
        validated_ids = None
        if patient_ids:
            validated_ids = [UUID(pid) for pid in self.validate_patient_ids(patient_ids)]
        daily_map: Dict[Any, Dict[str, int]] = {}

        try:
            query = self.db.query(
                func.date(Message.created_at).label("date"),
                func.count(
                    case((Message.direction == MessageDirection.OUTBOUND, 1))
                ).label("messages_sent"),
                func.count(
                    case((Message.direction == MessageDirection.INBOUND, 1))
                ).label("responses_received"),
            ).filter(func.date(Message.created_at) >= start_date)

            if validated_ids:
                query = query.filter(Message.patient_id.in_(validated_ids))

            rows = query.group_by(func.date(Message.created_at)).all()
            for row in rows:
                row_date = row.date
                if isinstance(row_date, str):
                    row_date = datetime.fromisoformat(row_date).date()
                daily_map[row_date] = {
                    "messages_sent": int(row.messages_sent or 0),
                    "responses_received": int(row.responses_received or 0),
                }
        except Exception as e:
            logger.warning(f"Failed to build engagement chart data: {e}")

        result: List[Dict[str, Any]] = []
        for offset in range(days):
            day = start_date + timedelta(days=offset)
            metrics = daily_map.get(day, {"messages_sent": 0, "responses_received": 0})
            messages_sent = metrics["messages_sent"]
            responses_received = metrics["responses_received"]
            response_rate = (
                round((responses_received / messages_sent) * 100, 1)
                if messages_sent > 0
                else 0
            )
            result.append(
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "messages_sent": messages_sent,
                    "responses_received": responses_received,
                    "response_rate": response_rate,
                }
            )

        return result
