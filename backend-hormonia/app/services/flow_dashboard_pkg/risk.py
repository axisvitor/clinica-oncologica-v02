import logging
from typing import Any, Dict, List, Optional

from app.services.analytics import PatientRisk, RiskLevel
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class FlowDashboardRiskMixin:
    async def get_at_risk_patient_dashboard(
        self,
        risk_levels: Optional[List[RiskLevel]] = None,
        flow_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive at-risk patient dashboard.

        Args:
            risk_levels: Optional risk level filters
            flow_type: Optional flow type filter

        Returns:
            At-risk patient dashboard data
        """
        try:
            all_at_risk = await self.analytics_service.identify_at_risk_patients(
                flow_type=flow_type, lookback_days=14
            )

            if risk_levels:
                at_risk_patients = [p for p in all_at_risk if p.risk_level in risk_levels]
            else:
                at_risk_patients = all_at_risk

            risk_groups = {
                RiskLevel.CRITICAL: [],
                RiskLevel.HIGH: [],
                RiskLevel.MEDIUM: [],
                RiskLevel.LOW: [],
            }

            for patient in at_risk_patients:
                risk_groups[patient.risk_level].append(patient)

            risk_factor_analysis = self._analyze_risk_factors(at_risk_patients)
            interventions = await self._generate_intervention_recommendations(
                at_risk_patients
            )
            risk_trends = await self._get_risk_trends()

            return {
                "summary": {
                    "total_at_risk": len(at_risk_patients),
                    "by_risk_level": {
                        level.value: len(patients)
                        for level, patients in risk_groups.items()
                    },
                    "flow_type_filter": flow_type,
                },
                "risk_groups": {
                    level.value: [
                        {
                            "patient_id": str(p.patient_id),
                            "risk_factors": p.risk_factors,
                            "last_response": p.last_response.isoformat()
                            if p.last_response
                            else None,
                            "recommended_actions": p.recommended_actions,
                        }
                        for p in patients
                    ]
                    for level, patients in risk_groups.items()
                },
                "risk_factor_analysis": risk_factor_analysis,
                "intervention_recommendations": interventions,
                "risk_trends": risk_trends,
                "generated_at": now_sao_paulo().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get at-risk patient dashboard: {e}")
            raise

    def _analyze_risk_factors(
        self, at_risk_patients: List[PatientRisk]
    ) -> Dict[str, Any]:
        """Analyze common risk factors."""
        all_factors = []
        for patient in at_risk_patients:
            all_factors.extend(patient.risk_factors)

        factor_counts = {}
        for factor in all_factors:
            normalized = factor.lower()
            if "no response" in normalized:
                key = "no_response"
            elif "low engagement" in normalized:
                key = "low_engagement"
            elif "negative sentiment" in normalized:
                key = "negative_sentiment"
            elif "concerning events" in normalized:
                key = "concerning_events"
            else:
                key = "other"

            factor_counts[key] = factor_counts.get(key, 0) + 1

        return {
            "most_common_factors": factor_counts,
            "total_risk_factors": len(all_factors),
            "patients_analyzed": len(at_risk_patients),
        }

    async def _generate_intervention_recommendations(
        self, at_risk_patients: List[PatientRisk]
    ) -> List[Dict[str, Any]]:
        """Generate intervention recommendations for at-risk patients."""
        recommendations = []

        critical_patients = [
            p for p in at_risk_patients if p.risk_level == RiskLevel.CRITICAL
        ]
        high_risk_patients = [
            p for p in at_risk_patients if p.risk_level == RiskLevel.HIGH
        ]

        if critical_patients:
            recommendations.append(
                {
                    "priority": "immediate",
                    "action": "Healthcare provider outreach",
                    "description": f"Contact {len(critical_patients)} critical risk patients immediately",
                    "patient_count": len(critical_patients),
                    "estimated_time": "2-4 hours",
                }
            )

        if high_risk_patients:
            recommendations.append(
                {
                    "priority": "high",
                    "action": "Personalized re-engagement",
                    "description": f"Send personalized messages to {len(high_risk_patients)} high-risk patients",
                    "patient_count": len(high_risk_patients),
                    "estimated_time": "1-2 hours",
                }
            )

        return recommendations

    async def _get_risk_trends(self) -> Dict[str, Any]:
        """Get historical risk trends."""
        return {
            "trend_direction": "stable",
            "weekly_risk_counts": [],
            "risk_level_changes": {},
        }


__all__ = ["FlowDashboardRiskMixin"]
