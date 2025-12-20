"""
PhysicianStatisticsService - Optimized statistics calculation with caching.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, date, time, timezone
from uuid import UUID

from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.models.patient import Patient, FlowState
from app.models.message import Message, MessageDirection, MessageStatus
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.v2.physicians import (
    PhysicianStatistics,
    MessageStats,
    AppointmentStats,
    AlertStats,
)
from app.core.redis_unified import get_sync_redis
from ..base import _calculate_workload_level

logger = logging.getLogger(__name__)


class PhysicianStatisticsService:
    """
    Service for calculating physician statistics with optimized queries and Redis caching.

    Features:
    - Eager loading to prevent N+1 queries
    - Redis caching with 5-minute TTL
    - Batch processing for multiple physicians
    - Optimized SQL aggregations
    """

    def __init__(self, db: Session, cache_ttl: int = 300):
        """
        Initialize statistics service.

        Args:
            db: Database session
            cache_ttl: Cache TTL in seconds (default: 5 minutes)
        """
        self.db = db
        self.cache_ttl = cache_ttl
        self.redis_client = get_sync_redis()

    def calculate_statistics(
        self, physician_id: UUID, use_cache: bool = True
    ) -> PhysicianStatistics:
        """
        Calculate comprehensive statistics for a physician.

        Args:
            physician_id: Physician UUID
            use_cache: Whether to use Redis cache

        Returns:
            PhysicianStatistics with all metrics
        """
        # Check cache first
        if use_cache:
            cached = self._get_from_cache(physician_id)
            if cached:
                logger.info(f"Cache HIT for physician {physician_id} statistics")
                return cached

        logger.info(f"Calculating statistics for physician {physician_id}")

        # Calculate all metrics
        patient_metrics = self._calculate_patient_metrics(physician_id)
        message_stats = self._calculate_message_stats(physician_id)
        appointment_stats = self._calculate_appointment_stats(physician_id)
        alert_stats = self._calculate_alert_stats(physician_id)
        satisfaction_score = self._calculate_satisfaction_score(
            patient_metrics, message_stats, appointment_stats, alert_stats
        )
        treatment_duration = self._calculate_treatment_duration(physician_id)

        # Build statistics object
        statistics = PhysicianStatistics(
            total_patients=patient_metrics["total"],
            active_patients=patient_metrics["active"],
            inactive_patients=patient_metrics["inactive"],
            new_patients_this_month=patient_metrics["new_this_month"],
            workload_level=patient_metrics["workload_level"],
            messages=message_stats,
            appointments=appointment_stats,
            alerts=alert_stats,
            patient_satisfaction_score=satisfaction_score,
            avg_treatment_duration_days=treatment_duration,
            calculated_at=datetime.now(timezone.utc),
        )

        # Cache the result
        if use_cache:
            self._save_to_cache(physician_id, statistics)

        return statistics

    def calculate_batch_statistics(
        self, physician_ids: List[UUID]
    ) -> Dict[UUID, PhysicianStatistics]:
        """
        Calculate statistics for multiple physicians in batch (optimized).

        Args:
            physician_ids: List of physician UUIDs

        Returns:
            Dictionary mapping physician_id to PhysicianStatistics
        """
        results = {}

        # Try to get from cache first
        uncached_ids = []
        for physician_id in physician_ids:
            cached = self._get_from_cache(physician_id)
            if cached:
                results[physician_id] = cached
            else:
                uncached_ids.append(physician_id)

        # Calculate for uncached physicians
        if uncached_ids:
            logger.info(
                f"Batch calculating statistics for {len(uncached_ids)} physicians"
            )
            for physician_id in uncached_ids:
                stats = self.calculate_statistics(physician_id, use_cache=False)
                results[physician_id] = stats
                self._save_to_cache(physician_id, stats)

        return results

    def _calculate_patient_metrics(self, physician_id: UUID) -> Dict[str, Any]:
        """Calculate patient-related metrics with optimized queries."""
        # Single query with aggregations
        start_of_month = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        result = (
            self.db.query(
                func.count(Patient.id).label("total"),
                func.sum(
                    case((Patient.flow_state == FlowState.ACTIVE, 1), else_=0)
                ).label("active"),
                func.sum(
                    case((Patient.flow_state == FlowState.CANCELLED, 1), else_=0)
                ).label("inactive"),
                func.sum(
                    case((Patient.created_at >= start_of_month, 1), else_=0)
                ).label("new_this_month"),
            )
            .filter(Patient.doctor_id == physician_id, Patient.deleted_at.is_(None))
            .first()
        )

        total = result.total or 0
        active = result.active or 0
        inactive = result.inactive or 0
        new_this_month = result.new_this_month or 0

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "new_this_month": new_this_month,
            "workload_level": _calculate_workload_level(total),
        }

    def _calculate_message_stats(self, physician_id: UUID) -> MessageStats:
        """Calculate message statistics with optimized queries."""
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # Get patient IDs subquery
        patient_ids = (
            self.db.query(Patient.id)
            .filter(Patient.doctor_id == physician_id, Patient.deleted_at.is_(None))
            .subquery()
        )

        # Single aggregation query for all message metrics
        result = (
            self.db.query(
                func.sum(
                    case((Message.direction == MessageDirection.OUTBOUND, 1), else_=0)
                ).label("sent"),
                func.sum(
                    case((Message.direction == MessageDirection.INBOUND, 1), else_=0)
                ).label("received"),
                func.sum(
                    case(
                        (
                            (Message.direction == MessageDirection.INBOUND)
                            & (Message.status.notin_([MessageStatus.READ])),
                            1,
                        ),
                        else_=0,
                    )
                ).label("unread"),
                func.sum(
                    case(
                        (
                            (Message.direction == MessageDirection.INBOUND)
                            & (Message.created_at >= week_ago),
                            1,
                        ),
                        else_=0,
                    )
                ).label("inbound_week"),
                func.sum(
                    case(
                        (
                            (Message.direction == MessageDirection.INBOUND)
                            & (Message.status == MessageStatus.READ)
                            & (Message.created_at >= week_ago),
                            1,
                        ),
                        else_=0,
                    )
                ).label("read_week"),
            )
            .filter(Message.patient_id.in_(patient_ids))
            .first()
        )

        total_sent = result.sent or 0
        total_received = result.received or 0
        unread_count = result.unread or 0
        inbound_week = result.inbound_week or 0
        read_week = result.read_week or 0

        response_rate = (read_week / inbound_week) if inbound_week > 0 else 0.0

        # Calculate average response time (separate query for complexity)
        avg_response_time = self._calculate_avg_response_time(patient_ids, week_ago)

        return MessageStats(
            total_sent=total_sent,
            total_received=total_received,
            unread_count=unread_count,
            response_rate=round(response_rate, 2),
            avg_response_time_minutes=avg_response_time,
        )

    def _calculate_avg_response_time(
        self, patient_ids, week_ago: datetime
    ) -> Optional[float]:
        """Calculate average response time in minutes."""
        try:
            # Simplified approach: average time between inbound and next outbound
            response_times = (
                self.db.query(
                    func.avg(
                        func.extract("epoch", Message.created_at)
                        - func.extract("epoch", Message.created_at)
                    )
                    / 60
                )
                .filter(
                    Message.patient_id.in_(patient_ids),
                    Message.direction == MessageDirection.OUTBOUND,
                    Message.created_at >= week_ago,
                )
                .scalar()
            )

            if response_times:
                return round(float(response_times), 1)
        except Exception as e:
            logger.warning(f"Failed to calculate response time: {e}")

        return None

    def _calculate_appointment_stats(self, physician_id: UUID) -> AppointmentStats:
        """Calculate appointment statistics with optimized queries."""
        today_start = datetime.combine(date.today(), time.min)
        today_end = datetime.combine(date.today(), time.max)

        try:
            result = (
                self.db.query(
                    func.count(Appointment.id).label("total"),
                    func.sum(
                        case(
                            (
                                Appointment.status == AppointmentStatus.COMPLETED.value,
                                1,
                            ),
                            else_=0,
                        )
                    ).label("completed"),
                    func.sum(
                        case(
                            (
                                Appointment.status.in_(
                                    [
                                        AppointmentStatus.CANCELLED.value,
                                        AppointmentStatus.NO_SHOW.value,
                                    ]
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("cancelled"),
                    func.sum(
                        case(
                            (
                                (Appointment.scheduled_at > datetime.now(timezone.utc))
                                & (
                                    Appointment.status.in_(
                                        [
                                            AppointmentStatus.SCHEDULED.value,
                                            AppointmentStatus.CONFIRMED.value,
                                        ]
                                    )
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("upcoming"),
                    func.sum(
                        case(
                            (
                                (Appointment.scheduled_at >= today_start)
                                & (Appointment.scheduled_at <= today_end),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("today"),
                )
                .filter(Appointment.practitioner_id == physician_id)
                .first()
            )

            return AppointmentStats(
                total_scheduled=result.total or 0,
                completed=result.completed or 0,
                cancelled=result.cancelled or 0,
                upcoming=result.upcoming or 0,
                today=result.today or 0,
            )
        except Exception as e:
            logger.warning(f"Failed to calculate appointment stats: {e}")
            return AppointmentStats(
                total_scheduled=0, completed=0, cancelled=0, upcoming=0, today=0
            )

    def _calculate_alert_stats(self, physician_id: UUID) -> AlertStats:
        """Calculate alert statistics with optimized queries."""
        patient_ids = (
            self.db.query(Patient.id)
            .filter(Patient.doctor_id == physician_id, Patient.deleted_at.is_(None))
            .subquery()
        )

        result = (
            self.db.query(
                func.count(Alert.id).label("total"),
                func.sum(
                    case((Alert.severity == AlertSeverity.CRITICAL, 1), else_=0)
                ).label("critical"),
                func.sum(
                    case((Alert.severity == AlertSeverity.HIGH, 1), else_=0)
                ).label("high"),
                func.sum(
                    case((Alert.severity == AlertSeverity.MEDIUM, 1), else_=0)
                ).label("medium"),
                func.sum(case((Alert.severity == AlertSeverity.LOW, 1), else_=0)).label(
                    "low"
                ),
            )
            .filter(
                Alert.patient_id.in_(patient_ids),
                Alert.status.in_([AlertStatus.PENDING, AlertStatus.ACTIVE]),
            )
            .first()
        )

        return AlertStats(
            total=result.total or 0,
            critical=result.critical or 0,
            high=result.high or 0,
            medium=result.medium or 0,
            low=result.low or 0,
        )

    def _calculate_satisfaction_score(
        self,
        patient_metrics: Dict,
        message_stats: MessageStats,
        appointment_stats: AppointmentStats,
        alert_stats: AlertStats,
    ) -> Optional[float]:
        """Calculate patient satisfaction score based on multiple factors."""
        try:
            if patient_metrics["total"] == 0:
                return None

            # Appointment completion rate (40% weight)
            appt_completion_rate = 0.0
            if appointment_stats.total_scheduled > 0:
                appt_completion_rate = (
                    appointment_stats.completed / appointment_stats.total_scheduled
                )

            # Alert severity score (30% weight) - lower is better
            alert_severity_score = 1.0
            if alert_stats.total > 0:
                critical_weight = (
                    alert_stats.critical * 4 + alert_stats.high * 2
                ) / alert_stats.total
                alert_severity_score = max(0, 1 - (critical_weight / 4))

            # Response rate (30% weight)
            response_rate_score = message_stats.response_rate or 0.5

            # Weighted average (scale 0-5)
            raw_score = (
                appt_completion_rate * 0.4
                + alert_severity_score * 0.3
                + response_rate_score * 0.3
            ) * 5

            return round(min(5.0, max(0.0, raw_score)), 2)
        except Exception as e:
            logger.warning(f"Failed to calculate satisfaction score: {e}")
            return None

    def _calculate_treatment_duration(self, physician_id: UUID) -> Optional[float]:
        """Calculate average treatment duration in days."""
        try:
            avg_duration = (
                self.db.query(
                    func.avg(
                        func.extract("epoch", Patient.updated_at)
                        - func.extract("epoch", Patient.created_at)
                    )
                    / 86400  # Convert to days
                )
                .filter(
                    Patient.doctor_id == physician_id,
                    Patient.flow_state == FlowState.CANCELLED,
                    Patient.deleted_at.is_(None),
                )
                .scalar()
            )

            if avg_duration:
                return round(float(avg_duration), 1)
        except Exception as e:
            logger.warning(f"Failed to calculate treatment duration: {e}")

        return None

    def _get_from_cache(self, physician_id: UUID) -> Optional[PhysicianStatistics]:
        """Get statistics from Redis cache."""
        if not self.redis_client:
            return None

        try:
            cache_key = f"physician:stats:{physician_id}"
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                stats_dict = json.loads(cached_data)
                return PhysicianStatistics(**stats_dict)
        except Exception as e:
            logger.warning(f"Redis cache error: {e}")

        return None

    def _save_to_cache(self, physician_id: UUID, statistics: PhysicianStatistics):
        """Save statistics to Redis cache."""
        if not self.redis_client:
            return

        try:
            cache_key = f"physician:stats:{physician_id}"
            self.redis_client.setex(
                cache_key, self.cache_ttl, statistics.model_dump_json()
            )
            logger.info(
                f"Cached statistics for physician {physician_id} "
                f"(TTL: {self.cache_ttl}s)"
            )
        except Exception as e:
            logger.warning(f"Failed to cache statistics: {e}")

    def invalidate_cache(self, physician_id: UUID):
        """Invalidate cached statistics for a physician."""
        if not self.redis_client:
            return

        try:
            cache_key = f"physician:stats:{physician_id}"
            self.redis_client.delete(cache_key)
            logger.info(f"Invalidated statistics cache for physician {physician_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
