from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.repositories.base import BaseRepository
from app.exceptions import ValidationError, DatabaseError
from app.utils.timezone import now_sao_paulo


class AlertRepository(BaseRepository[Alert]):
    """
    Repository for Alert model with optimized query methods.

    Recommended database indexes for optimal performance:
    - CREATE INDEX idx_alerts_status ON alerts(status);
    - CREATE INDEX idx_alerts_patient_status ON alerts(patient_id, status);
    - CREATE INDEX idx_alerts_severity_status ON alerts(severity, status);
    - CREATE INDEX idx_alerts_type_created ON alerts(alert_type, created_at DESC);
    - CREATE INDEX idx_alerts_patient_type_created ON alerts(patient_id, alert_type, created_at DESC);
    - CREATE INDEX idx_alerts_created_id ON alerts(created_at DESC, id);
    """

    def __init__(self, db: Session):
        super().__init__(db, Alert)

    def _bulk_update_acknowledged(
        self,
        *,
        alert_ids: List[UUID],
        acknowledged: bool,
        acknowledged_by: Optional[UUID] = None,
    ) -> int:
        """Apply a bulk acknowledged-status update with shared persistence logic."""
        if not alert_ids:
            raise ValidationError("Alert IDs list cannot be empty")

        update_data = {
            "acknowledged": acknowledged,
            "updated_at": now_sao_paulo(),
        }
        if acknowledged_by and acknowledged:
            update_data["acknowledged_by"] = acknowledged_by
            update_data["acknowledged_at"] = now_sao_paulo()

        result = (
            self.db.query(Alert)
            .filter(Alert.id.in_(alert_ids))
            .update(update_data, synchronize_session=False)
        )
        self.db.commit()
        return result

    def get_by_patient(
        self, patient_id: UUID, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[Alert]:
        """
        Get alerts by patient with pagination and eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default to prevent N+1 queries.

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)

        Args:
            patient_id: UUID of the patient
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of alerts for the patient ordered by creation time (newest first)
        """
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(Alert)
            .filter(Alert.patient_id == patient_id)
            .order_by(Alert.created_at.desc(), Alert.id)
        )

        if eager_load:
            query = query.options(joinedload(Alert.patient))

        return query.offset(skip).limit(limit).all()

    def get_unacknowledged(
        self, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[Alert]:
        """
        Get unacknowledged alerts with pagination and eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.
        SCHEMA COMPATIBILITY: Uses acknowledged boolean field instead of status enum.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of unacknowledged alerts ordered by creation time (newest first)
        """
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(Alert)
            .filter(
                Alert.acknowledged.is_(False)
            )  # Use boolean field instead of status enum
            .order_by(Alert.created_at.desc(), Alert.id)
        )

        if eager_load:
            query = query.options(joinedload(Alert.patient))

        return query.offset(skip).limit(limit).all()

    def get_by_severity(
        self,
        severity: AlertSeverity,
        skip: int = 0,
        limit: int = 100,
        eager_load: bool = True,
    ) -> List[Alert]:
        """
        Get alerts by severity level with pagination and eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)
        - patient.doctor: Doctor information via patient (nested joinedload - 1:1)

        Args:
            severity: AlertSeverity enum value to filter by
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of alerts with specified severity ordered by creation time
        """
        from sqlalchemy.orm import joinedload
        from app.models.patient import Patient

        query = (
            self.db.query(Alert)
            .filter(Alert.severity == severity)
            .order_by(Alert.created_at.desc(), Alert.id)
        )

        if eager_load:
            # PERFORMANCE: Nested eager loading for patient and doctor relationships
            query = query.options(joinedload(Alert.patient).joinedload(Patient.doctor))

        return query.offset(skip).limit(limit).all()

    def get_critical_unacknowledged(
        self, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[Alert]:
        """
        Get critical unacknowledged alerts with compound filter and eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.
        SCHEMA COMPATIBILITY: Uses acknowledged boolean field instead of status enum.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of critical unacknowledged alerts ordered by creation time
        """
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(Alert)
            .filter(
                and_(
                    Alert.severity == AlertSeverity.CRITICAL,
                    Alert.acknowledged.is_(
                        False
                    ),  # Use boolean field instead of status enum
                )
            )
            .order_by(Alert.created_at.desc(), Alert.id)
        )

        if eager_load:
            query = query.options(joinedload(Alert.patient))

        return query.offset(skip).limit(limit).all()

    def get_by_type(
        self, alert_type: str, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[Alert]:
        """
        Get alerts by type with pagination and eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)
        - patient.doctor: Doctor information via patient (nested joinedload - 1:1)

        Args:
            alert_type: Type of alert to filter by
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of alerts of specified type ordered by creation time
        """
        from sqlalchemy.orm import joinedload
        from app.models.patient import Patient

        query = (
            self.db.query(Alert)
            .filter(Alert.alert_type == alert_type)
            .order_by(Alert.created_at.desc(), Alert.id)
        )

        if eager_load:
            # PERFORMANCE: Nested eager loading for patient and doctor relationships
            query = query.options(joinedload(Alert.patient).joinedload(Patient.doctor))

        return query.offset(skip).limit(limit).all()

    def get_recent_alerts(
        self, patient_id: UUID, alert_type: str, hours: int = 24
    ) -> List[Alert]:
        """
        Get recent alerts of specific type for a patient within time window.

        Args:
            patient_id: UUID of the patient
            alert_type: Type of alert to filter by
            hours: Time window in hours (default: 24)

        Returns:
            List of alerts matching criteria, ordered by creation time (newest first)

        Raises:
            ValidationError: If hours is not positive or exceeds reasonable limits
        """
        if hours <= 0:
            raise ValidationError("Hours must be positive")

        if hours > 8760:  # More than a year
            raise ValidationError("Hours cannot exceed 8760 (1 year)")

        try:
            cutoff_time = now_sao_paulo() - timedelta(hours=hours)
            return (
                self.db.query(Alert)
                .filter(
                    and_(
                        Alert.patient_id == patient_id,
                        Alert.alert_type == alert_type,
                        Alert.created_at >= cutoff_time,
                    )
                )
                .order_by(Alert.created_at.desc(), Alert.id)
                .limit(100)  # FIX: Prevent unbounded query
                .all()
            )
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve recent alerts: {str(e)}")

    def get_active_alerts(self, skip: int = 0, limit: int = 100) -> List[Alert]:
        """
        Get active (unacknowledged) alerts with pagination.
        SCHEMA COMPATIBILITY: Uses acknowledged boolean field. Active = not acknowledged.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of active alerts ordered by creation time (newest first)
        """
        return (
            self.db.query(Alert)
            .filter(Alert.acknowledged.is_(False))  # Active = not acknowledged
            .order_by(Alert.created_at.desc(), Alert.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_severity(self, severity: AlertSeverity) -> int:
        """
        Count total alerts by severity level.

        Args:
            severity: AlertSeverity enum value

        Returns:
            Integer count of alerts with specified severity
        """
        return self.db.query(Alert).filter(Alert.severity == severity).count()

    def count_unacknowledged(self) -> int:
        """
        Count unacknowledged alerts.
        SCHEMA COMPATIBILITY: Uses acknowledged boolean field instead of status enum.

        Returns:
            Integer count of alerts with acknowledged=false
        """
        return self.db.query(Alert).filter(Alert.acknowledged.is_(False)).count()

    def get_alerts_by_patient_and_status(
        self, patient_id: UUID, status: AlertStatus, skip: int = 0, limit: int = 100
    ) -> List[Alert]:
        """
        Get alerts for a patient filtered by status.
        SCHEMA COMPATIBILITY: Maps status enum to acknowledged boolean field.

        Args:
            patient_id: UUID of the patient
            status: AlertStatus to filter by
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of alerts matching criteria
        """
        # Map status enum to acknowledged boolean
        if status == AlertStatus.ACKNOWLEDGED:
            acknowledged = True
        else:
            acknowledged = False

        return (
            self.db.query(Alert)
            .filter(
                and_(Alert.patient_id == patient_id, Alert.acknowledged == acknowledged)
            )
            .order_by(Alert.created_at.desc(), Alert.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_alerts_summary(self) -> dict:
        """
        Get comprehensive alert statistics.
        SCHEMA COMPATIBILITY: Uses acknowledged boolean field to derive status.

        Returns:
            Dictionary containing alert counts by status, severity, and total
        """
        try:
            result = (
                self.db.query(
                    Alert.acknowledged,
                    Alert.severity,
                    func.count(Alert.id).label("count"),
                )
                .group_by(Alert.acknowledged, Alert.severity)
                .all()
            )

            summary = {"by_status": {}, "by_severity": {}, "total": 0}

            for acknowledged, severity, count in result:
                # Map acknowledged boolean to status string
                status_str = "acknowledged" if acknowledged else "pending"
                summary["by_status"][status_str] = (
                    summary["by_status"].get(status_str, 0) + count
                )
                summary["by_severity"][severity.value] = (
                    summary["by_severity"].get(severity.value, 0) + count
                )
                summary["total"] += count

            return summary
        except Exception as e:
            raise DatabaseError(f"Failed to generate alerts summary: {str(e)}")

    def bulk_update_status(
        self,
        alert_ids: List[UUID],
        new_status: AlertStatus,
        acknowledged_by: Optional[UUID] = None,
    ) -> int:
        """
        Bulk update status for multiple alerts.
        SCHEMA COMPATIBILITY: Maps status enum to acknowledged boolean field.

        Args:
            alert_ids: List of alert IDs to update
            new_status: New status to set
            acknowledged_by: User ID who acknowledged (if applicable)

        Returns:
            Number of alerts updated

        Raises:
            ValidationError: If alert_ids is empty
            DatabaseError: If update operation fails
        """
        if not alert_ids:
            raise ValidationError("Alert IDs list cannot be empty")

        try:
            return self._bulk_update_acknowledged(
                alert_ids=alert_ids,
                acknowledged=(new_status == AlertStatus.ACKNOWLEDGED),
                acknowledged_by=acknowledged_by,
            )
        except Exception as e:
            self.db.rollback()
            raise DatabaseError(f"Failed to bulk update alert status: {str(e)}")

    def delete_old_resolved_alerts(self, days_old: int = 90) -> int:
        """
        Delete resolved alerts older than specified days.

        Args:
            days_old: Number of days to keep resolved alerts (default: 90)

        Returns:
            Number of alerts deleted

        Raises:
            ValidationError: If days_old is not positive
            DatabaseError: If delete operation fails
        """
        if days_old <= 0:
            raise ValidationError("Days old must be positive")

        try:
            cutoff_date = now_sao_paulo() - timedelta(days=days_old)

            # Note: Using acknowledged field since status is virtual property
            result = (
                self.db.query(Alert)
                .filter(
                    and_(
                        Alert.acknowledged,  # Resolved alerts are acknowledged
                        Alert.updated_at < cutoff_date,
                    )
                )
                .delete(synchronize_session=False)
            )

            self.db.commit()
            return result
        except Exception as e:
            self.db.rollback()
            raise DatabaseError(f"Failed to delete old resolved alerts: {str(e)}")

    def get_by_quiz_session(self, quiz_session_id: UUID) -> List[Alert]:
        """
        Get alerts by quiz session ID stored in data JSONB field.

        Args:
            quiz_session_id: UUID of the quiz session

        Returns:
            List of alerts related to the quiz session
        """
        try:
            return (
                self.db.query(Alert)
                .filter(Alert.data.op("->>")("quiz_session_id") == str(quiz_session_id))
                .order_by(Alert.created_at.desc(), Alert.id)
                .limit(100)  # FIX: Prevent unbounded query
                .all()
            )
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve alerts by quiz session: {str(e)}")

    def get_by_status(self, status: str) -> List[Alert]:
        """
        Get alerts by status (maps to acknowledged field).

        Args:
            status: Status string ('acknowledged', 'pending', etc.)

        Returns:
            List of alerts with the specified status
        """
        try:
            # Map status to acknowledged boolean
            if status == "acknowledged":
                acknowledged = True
            else:
                acknowledged = False

            return (
                self.db.query(Alert)
                .filter(Alert.acknowledged == acknowledged)
                .order_by(Alert.created_at.desc(), Alert.id)
                .limit(100)  # FIX: Prevent unbounded query
                .all()
            )
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve alerts by status: {str(e)}")

    def update_get_unacknowledged(
        self, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[Alert]:
        """
        Updated version of get_unacknowledged using acknowledged boolean field.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of unacknowledged alerts ordered by creation time (newest first)
        """
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(Alert)
            .filter(
                Alert.acknowledged.is_(False)
            )  # Use boolean field instead of status enum
            .order_by(Alert.created_at.desc(), Alert.id)
        )

        if eager_load:
            query = query.options(joinedload(Alert.patient))

        return query.offset(skip).limit(limit).all()

    def update_count_unacknowledged(self) -> int:
        """
        Updated version of count_unacknowledged using acknowledged boolean field.

        Returns:
            Integer count of alerts with acknowledged=false
        """
        return self.db.query(Alert).filter(Alert.acknowledged.is_(False)).count()

    def update_get_active_alerts(self, skip: int = 0, limit: int = 100) -> List[Alert]:
        """
        Updated version of get_active_alerts using acknowledged boolean field.
        Active alerts are those that are not acknowledged.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of active (unacknowledged) alerts ordered by creation time (newest first)
        """
        return (
            self.db.query(Alert)
            .filter(Alert.acknowledged.is_(False))
            .order_by(Alert.created_at.desc(), Alert.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_get_alerts_by_patient_and_status(
        self, patient_id: UUID, status: str, skip: int = 0, limit: int = 100
    ) -> List[Alert]:
        """
        Updated version using acknowledged boolean field instead of status enum.

        Args:
            patient_id: UUID of the patient
            status: Status string ('acknowledged', 'pending', etc.)
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of alerts matching criteria
        """
        # Map status to acknowledged boolean
        if status == "acknowledged":
            acknowledged = True
        else:
            acknowledged = False

        return (
            self.db.query(Alert)
            .filter(
                and_(Alert.patient_id == patient_id, Alert.acknowledged == acknowledged)
            )
            .order_by(Alert.created_at.desc(), Alert.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_bulk_update_status(
        self,
        alert_ids: List[UUID],
        new_status: str,
        acknowledged_by: Optional[UUID] = None,
    ) -> int:
        """
        Updated bulk update using acknowledged boolean field.

        Args:
            alert_ids: List of alert IDs to update
            new_status: New status to set ('acknowledged', 'pending', etc.)
            acknowledged_by: User ID who acknowledged (if applicable)

        Returns:
            Number of alerts updated

        Raises:
            ValidationError: If alert_ids is empty
            DatabaseError: If update operation fails
        """
        if not alert_ids:
            raise ValidationError("Alert IDs list cannot be empty")

        try:
            return self._bulk_update_acknowledged(
                alert_ids=alert_ids,
                acknowledged=(new_status == "acknowledged"),
                acknowledged_by=acknowledged_by,
            )
        except Exception as e:
            self.db.rollback()
            raise DatabaseError(f"Failed to bulk update alert status: {str(e)}")
