# DDD service agent - no LLM calls, not a pydantic-ai migration target.
"""
Alert Analyzer Agent

Responsible for intelligent analysis, prioritization, and triaging of system
and patient alerts to ensure critical issues are addressed promptly.
"""

from typing import Dict, List, Any

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, AgentCapabilities
from app.agents.registry import ALERT_ANALYZER_ID
from app.utils.logging import get_logger


class AlertAnalyzerAgent(BaseAgent):
    """
    Agent specialized in analyzing and prioritizing alerts.

    Capabilities:
    - Analyze alert patterns
    - Prioritize based on severity and context
    - Recommend actions
    - Learn from past alert resolutions
    """

    def __init__(self, db_session: Session):
        """Initialize Alert Analyzer Agent."""
        super().__init__(
            agent_id=ALERT_ANALYZER_ID,
            agent_type="analytics",
            specialization="alert_analyzer",
            db_session=db_session,
            capabilities=[
                AgentCapabilities.DECISION_MAKING,
                AgentCapabilities.LEARNING,
            ],
        )

        self.logger = get_logger(f"agent.{self.agent_id}")

        # Analysis configuration
        self.analysis_config = {
            "high_priority_keywords": ["critical", "emergency", "failure", "error"],
            "escalation_threshold": 3,  # Escalate after 3 similar alerts
            "learning_rate": 0.1,
        }

        self.register_message_handler("analyze_escalation", self._handle_analyze_escalation)
        self.register_message_handler("escalation_alert", self._handle_escalation_alert)

        self.logger.info("Alert Analyzer Agent initialized")

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process alert analysis task."""
        try:
            task_type = task.get("task_type")
            payload = task.get("payload", {})

            if task_type == "analyze_alert":
                return await self._analyze_alert(payload)
            elif task_type == "prioritize_queue":
                return await self._prioritize_queue(payload)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}

        except Exception as e:
            self.logger.error(f"Task processing failed: {e}")
            return {"success": False, "error": str(e)}

    async def _analyze_alert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single alert."""
        try:
            alert_text = payload.get("text", "")
            source = payload.get("source", "unknown")

            # Basic keyword analysis
            severity = "low"
            for keyword in self.analysis_config["high_priority_keywords"]:
                if keyword in alert_text.lower():
                    severity = "high"
                    break

            return {
                "success": True,
                "analysis": {
                    "severity": severity,
                    "source": source,
                    "recommended_action": "notify_admin"
                    if severity == "high"
                    else "log_only",
                },
            }

        except Exception as e:
            self.logger.error(f"Alert analysis failed: {e}")
            return {"success": False, "error": str(e)}

    async def _prioritize_queue(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Prioritize a queue of alerts."""
        # Placeholder for queue prioritization logic
        return {
            "success": True,
            "message": "Queue prioritization not fully implemented yet",
        }

    async def _handle_analyze_escalation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle escalation analysis requests from message processing."""
        reason = str(payload.get("reason") or "").strip()
        structured_response = payload.get("structured_response")

        synthesized_text_parts = [reason]
        if isinstance(structured_response, dict):
            synthesized_text_parts.extend(str(value) for value in structured_response.values())
        elif structured_response is not None:
            synthesized_text_parts.append(str(structured_response))
        synthesized_text = " ".join(part for part in synthesized_text_parts if part).strip()

        analysis_result = await self._analyze_alert(
            {
                "text": synthesized_text,
                "source": "response_processor",
            }
        )
        analysis_payload = analysis_result.get("analysis", {}) if analysis_result.get("success") else {}
        severity = str(analysis_payload.get("severity", "low")).lower()

        return {
            "success": True,
            "patient_id": payload.get("patient_id"),
            "analysis": analysis_payload,
            "needs_medical_review": severity == "high",
            "reason": reason or "unspecified",
        }

    async def _handle_escalation_alert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle escalation alerts emitted by the flow coordinator path."""
        risk_factors = payload.get("risk_factors")
        if not isinstance(risk_factors, list):
            risk_factors = []

        synthesized_text = " ".join(
            [
                str(payload.get("priority") or ""),
                " ".join(str(item) for item in risk_factors),
            ]
        ).strip()

        analysis_result = await self._analyze_alert(
            {
                "text": synthesized_text,
                "source": "flow_coordinator",
            }
        )
        analysis_payload = analysis_result.get("analysis", {}) if analysis_result.get("success") else {}

        recommended_actions = payload.get("recommended_actions")
        if not isinstance(recommended_actions, list):
            recommended_actions = []

        return {
            "success": True,
            "patient_id": payload.get("patient_id"),
            "analysis": analysis_payload,
            "recommended_actions": recommended_actions,
            "escalated_by": payload.get("escalated_by"),
            "escalated_at": payload.get("escalated_at"),
        }

    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities."""
        return [AgentCapabilities.DECISION_MAKING, AgentCapabilities.LEARNING]

    async def validate_task(self, task_data: Dict[str, Any]) -> bool:
        """Validate if task can be handled."""
        valid_types = ["analyze_alert", "prioritize_queue"]
        return task_data.get("task_type") in valid_types
