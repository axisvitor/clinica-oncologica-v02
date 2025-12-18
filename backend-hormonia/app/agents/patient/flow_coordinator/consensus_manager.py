"""
Consensus Manager - Handles agent consensus and coordination.
"""

import logging
from typing import Dict, Any, Callable

from app.agents.base import MessagePriority
from .models import FlowContext


class ConsensusManager:
    """Manages agent consensus for critical decisions."""

    def __init__(
        self,
        agent_id: str,
        logger: logging.Logger,
        send_message_fn: Callable,
        consensus_threshold: float = 0.7,
    ):
        self.agent_id = agent_id
        self.logger = logger
        self.send_message_fn = send_message_fn
        self.consensus_threshold = consensus_threshold

    async def seek_agent_consensus(
        self, decision_topic: str, decision_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Seek consensus from other agents on important decisions."""
        try:
            # Send consensus request to relevant agents
            consensus_agents = ["alert_analyzer", "quiz_conductor", "patient_monitor"]
            votes = {}

            # Send messages to agents
            for agent_type in consensus_agents:
                await self.send_message_fn(
                    f"{agent_type}_agent",  # Assuming agent naming convention
                    "consensus_request",
                    {
                        "decision_topic": decision_topic,
                        "decision_data": decision_data,
                        "requesting_agent": self.agent_id,
                    },
                    MessagePriority.HIGH,
                    requires_response=True,
                )

                # For now, simulate consensus (would wait for actual responses)
                votes[agent_type] = {"vote": "approve", "confidence": 0.8}

            # Calculate consensus
            approvals = sum(1 for vote in votes.values() if vote["vote"] == "approve")
            consensus_reached = approvals / len(votes) >= self.consensus_threshold

            return {
                "consensus_reached": consensus_reached,
                "votes": votes,
                "approval_rate": approvals / len(votes),
            }

        except Exception as e:
            self.logger.error(f"Consensus seeking failed: {e}")
            return {"consensus_reached": False, "error": str(e)}

    async def escalate_intervention(self, context: FlowContext):
        """Escalate situation for medical intervention."""
        # Create alert for medical team
        alert_data = {
            "patient_id": str(context.patient_id),
            "risk_factors": context.risk_factors,
            "escalated_by": self.agent_id,
            "escalated_at": datetime.utcnow().isoformat(),
            "priority": "high",
            "recommended_actions": [
                "schedule_medical_consultation",
                "increase_monitoring_frequency",
                "review_treatment_plan",
            ],
        }

        # Send alert to alert analyzer agent
        await self.send_message_fn(
            "alert_analyzer_agent",
            "escalation_alert",
            alert_data,
            MessagePriority.CRITICAL,
        )


# Import datetime for escalate_intervention
from datetime import datetime
