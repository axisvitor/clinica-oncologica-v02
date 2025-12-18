"""
Patient Monitor Agent

Responsible for continuous monitoring of patient status, adherence to treatment,
and detection of potential issues requiring intervention.
"""

from typing import Dict, List, Any
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, AgentCapabilities
from app.repositories.patient import PatientRepository
from app.utils.logging import get_logger


class PatientMonitorAgent(BaseAgent):
    """
    Agent specialized in monitoring patient status and adherence.

    Capabilities:
    - Monitor treatment adherence
    - Detect missed check-ins
    - Track patient engagement
    - Trigger reminders and alerts
    """

    def __init__(self, db_session: Session):
        """Initialize Patient Monitor Agent."""
        super().__init__(
            agent_id="patient_monitor",
            agent_type="patient",
            specialization="patient_monitor",
            db_session=db_session,
            capabilities=[
                AgentCapabilities.PATIENT_ADAPTATION,
                AgentCapabilities.FLOW_COORDINATION,
            ],
        )

        self.patient_repo = PatientRepository(db_session)
        self.logger = get_logger(f"agent.{self.agent_id}")

        # Monitoring configuration
        self.monitoring_config = {
            "check_in_window_hours": 24,
            "max_missed_checkins": 2,
            "engagement_threshold_days": 7,
            "adherence_alert_threshold": 0.7,  # 70% adherence
        }

        self.logger.info("Patient Monitor Agent initialized")

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process monitoring task."""
        try:
            task_type = task.get("task_type")
            payload = task.get("payload", {})

            if task_type == "check_patient_status":
                return await self._check_patient_status(payload)
            elif task_type == "monitor_adherence":
                return await self._monitor_adherence(payload)
            elif task_type == "detect_engagement_drop":
                return await self._detect_engagement_drop(payload)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}

        except Exception as e:
            self.logger.error(f"Task processing failed: {e}")
            return {"success": False, "error": str(e)}

    async def _check_patient_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Check status of a specific patient."""
        try:
            patient_id_str = payload.get("patient_id")
            if not patient_id_str:
                return {"success": False, "error": "Missing patient_id"}

            patient_id = UUID(patient_id_str)
            patient = self.patient_repo.get(patient_id)

            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Perform status checks
            last_interaction = patient.updated_at or patient.created_at
            days_since_interaction = (datetime.utcnow() - last_interaction).days

            status_report = {
                "patient_id": str(patient.id),
                "status": patient.status,
                "days_since_interaction": days_since_interaction,
                "needs_attention": days_since_interaction
                > self.monitoring_config["engagement_threshold_days"],
                "alerts": [],
            }

            if status_report["needs_attention"]:
                status_report["alerts"].append("Low engagement detected")

            return {"success": True, "report": status_report}

        except Exception as e:
            self.logger.error(f"Patient status check failed: {e}")
            return {"success": False, "error": str(e)}

    async def _monitor_adherence(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor treatment adherence for a patient."""
        # Placeholder for adherence logic
        # In a real implementation, this would check quiz completions vs expected schedule
        return {
            "success": True,
            "message": "Adherence monitoring not fully implemented yet",
        }

    async def _detect_engagement_drop(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Detect drops in patient engagement."""
        # Placeholder for engagement drop logic
        return {
            "success": True,
            "message": "Engagement drop detection not fully implemented yet",
        }

    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities."""
        return [
            AgentCapabilities.PATIENT_ADAPTATION,
            AgentCapabilities.FLOW_COORDINATION,
        ]

    async def validate_task(self, task_data: Dict[str, Any]) -> bool:
        """Validate if task can be handled."""
        valid_types = [
            "check_patient_status",
            "monitor_adherence",
            "detect_engagement_drop",
        ]
        return task_data.get("task_type") in valid_types
