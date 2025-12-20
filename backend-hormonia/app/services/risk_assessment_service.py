"""
Risk Assessment Service for calculating patient risk scores.

This service provides optimized bulk risk assessment calculations to replace
N+1 query patterns with efficient JOIN queries.

Performance target: < 200ms for 50 patients
"""

import logging
from sqlalchemy import func, and_
from datetime import datetime, timedelta, timezone
from typing import Any, List, Dict, Optional
from uuid import UUID

from app.models.patient import Patient
from app.models.alert import Alert, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)


class RiskAssessmentService:
    """
    Service for calculating and aggregating patient risk assessments.

    This service uses optimized database queries to avoid N+1 problems
    and provides bulk operations for physician dashboard views.
    """

    def __init__(self, db: Any):
        """
        Initialize risk assessment service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def calculate_risk_score(
        self, alerts: List[Alert], patient_metadata: Optional[Dict] = None
    ) -> float:
        """
        Calculate risk score from alerts and patient metadata.

        Algorithm:
        - Critical alerts: +0.4 per alert (max 2 alerts = 0.8)
        - High alerts: +0.2 per alert (max 3 alerts = 0.6)
        - Medium alerts: +0.1 per alert (max 4 alerts = 0.4)
        - Low alerts: +0.05 per alert (max 4 alerts = 0.2)
        - Low adherence (<70%): +0.3
        - Medium adherence (70-85%): +0.15
        - Recent symptoms: +0.2

        Args:
            alerts: List of Alert objects for the patient
            patient_metadata: Optional patient metadata containing AI insights

        Returns:
            float: Risk score from 0.0 (no risk) to 1.0 (critical)
        """
        score = 0.0

        # Alert severity scoring with caps to prevent overflow
        alert_weights = {
            AlertSeverity.CRITICAL: (0.4, 2),  # (weight, max_count)
            AlertSeverity.HIGH: (0.2, 3),
            AlertSeverity.MEDIUM: (0.1, 4),
            AlertSeverity.LOW: (0.05, 4),
        }

        # Count alerts by severity
        severity_counts: Dict[AlertSeverity, int] = {}
        for alert in alerts:
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1

        # Apply weighted scores with caps
        for severity, (weight, max_count) in alert_weights.items():
            count = min(severity_counts.get(severity, 0), max_count)
            score += count * weight

        # AI insights scoring (replace hardcoded adherence_score = 0.85)
        if patient_metadata:
            # Medication adherence from AI analysis
            adherence = patient_metadata.get("adherence_score")
            if adherence is not None:
                if adherence < 0.7:
                    score += 0.3
                elif adherence < 0.85:
                    score += 0.15

            # Symptom severity from AI analysis
            symptom_severity = patient_metadata.get("symptom_severity", 0)
            if isinstance(symptom_severity, (int, float)):
                score += min(symptom_severity, 1.0) * 0.2

            # Treatment compliance
            treatment_compliance = patient_metadata.get("treatment_compliance")
            if treatment_compliance is not None and treatment_compliance < 0.7:
                score += 0.15

        # Cap at 1.0
        return min(score, 1.0)

    def score_to_level(self, score: float) -> str:
        """
        Convert numeric risk score to categorical risk level.

        Args:
            score: Risk score from 0.0 to 1.0

        Returns:
            str: Risk level (low, medium, high, critical)
        """
        if score >= 0.7:
            return "critical"
        elif score >= 0.5:
            return "high"
        elif score >= 0.3:
            return "medium"
        else:
            return "low"

    def get_patient_risk_assessments(
        self,
        physician_id: UUID,
        patient_id: Optional[UUID] = None,
        days_lookback: int = 30,
    ) -> List[Dict]:
        """
        Get aggregated risk assessments for physician's patients.

        OPTIMIZED: Single query with JOINs instead of N+1 individual queries.
        This replaces the pattern of 1 patient list query + N individual /ai/insights queries.

        Args:
            physician_id: UUID of the physician
            patient_id: Optional UUID to filter for a single patient
            days_lookback: Number of days to look back for alerts (default: 30)

        Returns:
            List[Dict]: List of patient risk profiles

        Performance:
            Target: < 200ms for 50 patients
            Queries: 3-4 total (not N+1)
        """
        start_time = datetime.now(timezone.utc)

        try:
            # === QUERY 1: Get patients with alert counts (single JOIN) ===
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)

            query = self.db.query(
                Patient.id,
                Patient.name,
                Patient.patient_data,  # JSONB metadata
                func.count(Alert.id).label("alert_count"),
                func.max(Alert.created_at).label("last_alert"),
            ).outerjoin(
                Alert,
                and_(
                    Alert.patient_id == Patient.id,
                    Alert.status.in_([AlertStatus.PENDING, AlertStatus.ACTIVE]),
                    Alert.created_at >= cutoff_date,
                ),
            )

            # Filter by physician
            query = query.filter(Patient.doctor_id == physician_id)

            # Optional: single patient filter
            if patient_id:
                query = query.filter(Patient.id == patient_id)

            # Group by patient
            query = query.group_by(Patient.id, Patient.name, Patient.patient_data)

            # Execute query
            patient_rows = query.all()

            if not patient_rows:
                logger.info(f"No patients found for physician {physician_id}")
                return []

            # Extract patient IDs for bulk queries
            patient_ids = [row.id for row in patient_rows]

            # === QUERY 2: Get all alerts for these patients (bulk) ===
            alerts_query = (
                self.db.query(Alert)
                .filter(
                    Alert.patient_id.in_(patient_ids),
                    Alert.status.in_([AlertStatus.PENDING, AlertStatus.ACTIVE]),
                    Alert.created_at >= cutoff_date,
                )
                .order_by(Alert.severity.desc(), Alert.created_at.desc())
            )

            # Group alerts by patient
            alerts_by_patient: Dict[UUID, List[Alert]] = {}
            for alert in alerts_query.all():
                if alert.patient_id not in alerts_by_patient:
                    alerts_by_patient[alert.patient_id] = []
                alerts_by_patient[alert.patient_id].append(alert)

            # === QUERY 3 (Optional): Get AI insights if available ===
            # Note: Since AIInsight table doesn't exist yet, we'll use patient metadata
            # This can be replaced with actual AI insights query when implemented

            # === Build risk profiles ===
            risk_profiles = []

            for row in patient_rows:
                patient_alerts = alerts_by_patient.get(row.id, [])
                patient_metadata = row.patient_data or {}

                # Calculate risk score
                risk_score = self.calculate_risk_score(
                    alerts=patient_alerts, patient_metadata=patient_metadata
                )

                # Build individual assessments from alerts
                assessments = []

                # Group alerts by type/category
                alert_categories: Dict[str, List[Alert]] = {}
                for alert in patient_alerts[:10]:  # Top 10 most severe
                    category = alert.alert_type or "general"
                    if category not in alert_categories:
                        alert_categories[category] = []
                    alert_categories[category].append(alert)

                # Create assessment for each category
                severity_map = {
                    AlertSeverity.CRITICAL: (1.0, "critical"),
                    AlertSeverity.HIGH: (0.75, "high"),
                    AlertSeverity.MEDIUM: (0.5, "medium"),
                    AlertSeverity.LOW: (0.25, "low"),
                }

                for category, category_alerts in alert_categories.items():
                    # Use the highest severity alert for this category
                    top_alert = max(
                        category_alerts,
                        key=lambda a: severity_map.get(a.severity, (0, "low"))[0],
                    )

                    severity_score, risk_level = severity_map.get(
                        top_alert.severity, (0.25, "low")
                    )

                    assessments.append(
                        {
                            "category": category,
                            "risk_level": risk_level,
                            "severity_score": severity_score,
                            "last_updated": top_alert.created_at,
                            "description": top_alert.description
                            or f"{len(category_alerts)} active alerts",
                        }
                    )

                # Add medication adherence assessment if available
                if patient_metadata.get("adherence_score") is not None:
                    adherence = patient_metadata["adherence_score"]
                    assessments.append(
                        {
                            "category": "medication_adherence",
                            "risk_level": "high"
                            if adherence < 0.7
                            else "medium"
                            if adherence < 0.85
                            else "low",
                            "severity_score": max(0, min(1, 1.0 - adherence)),
                            "last_updated": datetime.now(timezone.utc),
                            "description": f"Adherence: {adherence * 100:.0f}%",
                        }
                    )

                # Build profile
                risk_profiles.append(
                    {
                        "patient_id": str(row.id),
                        "patient_name": row.name,
                        "overall_risk": self.score_to_level(risk_score),
                        "risk_score": round(risk_score, 2),
                        "assessments": assessments,
                        "alert_count": row.alert_count or 0,
                        "last_assessment": row.last_alert or datetime.now(timezone.utc),
                    }
                )

            # Log performance
            elapsed_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            logger.info(
                f"Risk assessment completed in {elapsed_ms:.0f}ms for "
                f"{len(risk_profiles)} patients (target: <200ms)"
            )

            if elapsed_ms > 200:
                logger.warning(
                    f"Performance target exceeded: {elapsed_ms:.0f}ms > 200ms. "
                    f"Consider adding indexes or optimizing queries."
                )

            return risk_profiles

        except Exception as e:
            logger.error(f"Error calculating risk assessments: {e}", exc_info=True)
            raise
