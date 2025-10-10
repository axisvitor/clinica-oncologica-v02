from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.repositories.base import BaseRepository
from app.exceptions import ValidationError, DatabaseError


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
    
    def get_by_patient(self, patient_id: UUID, skip: int = 0, limit: int = 100, eager_load: bool = True) -> List[Alert]:
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
    
    def get_unacknowledged(self, skip: int = 0, limit: int = 100, eager_load: bool = True) -> List[Alert]:
        """
        Get unacknowledged alerts with pagination and eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

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
            .filter(Alert.status == AlertStatus.PENDING)
            .order_by(Alert.created_at.desc(), Alert.id)
        )

        if eager_load:
            query = query.options(joinedload(Alert.patient))

        return query.offset(skip).limit(limit).all()
    
    def get_by_severity(self, severity: AlertSeverity, skip: int = 0, limit: int = 100, eager_load: bool = True) -> List[Alert]:
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
            query = query.options(
                joinedload(Alert.patient).joinedload(Patient.doctor)
            )

        return query.offset(skip).limit(limit).all()
    
    def get_critical_unacknowledged(self, skip: int = 0, limit: int = 100, eager_load: bool = True) -> List[Alert]:
        """
        Get critical unacknowledged alerts with compound filter and eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

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
                    Alert.status == AlertStatus.PENDING
                )
            )
            .order_by(Alert.created_at.desc(), Alert.id)
        )

        if eager_load:
            query = query.options(joinedload(Alert.patient))

        return query.offset(skip).limit(limit).all()
    
    def get_by_type(self, alert_type: str, skip: int = 0, limit: int = 100, eager_load: bool = True) -> List[Alert]:
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
            query = query.options(
                joinedload(Alert.patient).joinedload(Patient.doctor)
            )

        return query.offset(skip).limit(limit).all()
    
    def get_recent_alerts(self, patient_id: UUID, alert_type: str, hours: int = 24) -> List[Alert]:
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
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            return (
                self.db.query(Alert)
                .filter(
                    and_(
                        Alert.patient_id == patient_id,
                        Alert.alert_type == alert_type,
                        Alert.created_at >= cutoff_time
                    )
                )
                .order_by(Alert.created_at.desc(), Alert.id)
                .all()
            )
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve recent alerts: {str(e)}")
    
    def get_active_alerts(self, skip: int = 0, limit: int = 100) -> List[Alert]:
        """
        Get active (pending or acknowledged) alerts with pagination.
        
        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            
        Returns:
            List of active alerts ordered by creation time (newest first)
        """
        return (
            self.db.query(Alert)
            .filter(
                or_(
                    Alert.status == AlertStatus.PENDING,
                    Alert.status == AlertStatus.ACKNOWLEDGED
                )
            )
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
        return (
            self.db.query(Alert)
            .filter(Alert.severity == severity)
            .count()
        )
    
    def count_unacknowledged(self) -> int:
        """
        Count unacknowledged alerts.
        
        Returns:
            Integer count of alerts with PENDING status
        """
        return (
            self.db.query(Alert)
            .filter(Alert.status == AlertStatus.PENDING)
            .count()
        )
    
    def get_alerts_by_patient_and_status(
        self, 
        patient_id: UUID, 
        status: AlertStatus,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Alert]:
        """
        Get alerts for a patient filtered by status.
        
        Args:
            patient_id: UUID of the patient
            status: AlertStatus to filter by
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            
        Returns:
            List of alerts matching criteria
        """
        return (
            self.db.query(Alert)
            .filter(
                and_(
                    Alert.patient_id == patient_id,
                    Alert.status == status
                )
            )
            .order_by(Alert.created_at.desc(), Alert.id)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_alerts_summary(self) -> dict:
        """
        Get comprehensive alert statistics.
        
        Returns:
            Dictionary containing alert counts by status, severity, and total
        """
        try:
            result = (
                self.db.query(
                    Alert.status,
                    Alert.severity,
                    func.count(Alert.id).label('count')
                )
                .group_by(Alert.status, Alert.severity)
                .all()
            )
            
            summary = {
                'by_status': {},
                'by_severity': {},
                'total': 0
            }
            
            for status, severity, count in result:
                summary['by_status'][status.value] = summary['by_status'].get(status.value, 0) + count
                summary['by_severity'][severity.value] = summary['by_severity'].get(severity.value, 0) + count
                summary['total'] += count
            
            return summary
        except Exception as e:
            raise DatabaseError(f"Failed to generate alerts summary: {str(e)}")
    
    def bulk_update_status(
        self, 
        alert_ids: List[UUID], 
        new_status: AlertStatus,
        acknowledged_by: Optional[UUID] = None
    ) -> int:
        """
        Bulk update status for multiple alerts.
        
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
            update_data = {
                'status': new_status,
                'updated_at': datetime.utcnow()
            }
            
            if acknowledged_by and new_status == AlertStatus.ACKNOWLEDGED:
                update_data['acknowledged_by'] = acknowledged_by
                update_data['acknowledged_at'] = datetime.utcnow()
            
            result = (
                self.db.query(Alert)
                .filter(Alert.id.in_(alert_ids))
                .update(update_data, synchronize_session=False)
            )
            
            self.db.commit()
            return result
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
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            result = (
                self.db.query(Alert)
                .filter(
                    and_(
                        Alert.status == AlertStatus.RESOLVED,
                        Alert.updated_at < cutoff_date
                    )
                )
                .delete(synchronize_session=False)
            )
            
            self.db.commit()
            return result
        except Exception as e:
            self.db.rollback()
            raise DatabaseError(f"Failed to delete old resolved alerts: {str(e)}")