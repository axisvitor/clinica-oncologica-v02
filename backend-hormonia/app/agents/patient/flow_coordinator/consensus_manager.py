"""Consensus Manager - Handles agent consensus and coordination."""

from __future__ import annotations

# Standard library
import inspect
import logging
from typing import Any, Callable, Dict, Optional

# Local
from app.agents.base import MessagePriority
from app.agents.registry import ALERT_ANALYZER_ID, PATIENT_MONITOR_ID
from app.ai.langgraph.runtime import build_graph_config

from .models import FlowContext
from app.utils.timezone import now_sao_paulo


class ConsensusManager:
    """
    Manages agent consensus for critical decisions.

    Coordinates with other agents to reach consensus on
    important decisions and escalates interventions when needed.

    Attributes:
        agent_id: Unique agent identifier.
        logger: Logger instance.
        send_message_fn: Function to send messages to other agents.
        consensus_threshold: Threshold for consensus approval.
    """

    def __init__(
        self,
        agent_id: str,
        logger: logging.Logger,
        send_message_fn: Callable,
        consensus_threshold: float = 0.7,
        fetch_votes_fn: Optional[Callable[..., Any]] = None,
        prepare_vote_collection_fn: Optional[Callable[..., Any]] = None,
    ):
        self.agent_id = agent_id
        self.logger = logger
        self.send_message_fn = send_message_fn
        self.consensus_threshold = consensus_threshold
        self.fetch_votes_fn = fetch_votes_fn
        self.prepare_vote_collection_fn = prepare_vote_collection_fn

    def _build_consensus_thread_id(
        self, decision_topic: str, decision_data: Dict[str, Any]
    ) -> str:
        topic_key = str(decision_topic or "unknown").strip().lower().replace(" ", "_")
        patient_scope = ""
        if isinstance(decision_data, dict):
            patient_id = decision_data.get("patient_id") or decision_data.get("patientId")
            if patient_id is not None:
                patient_scope = str(patient_id).strip()
        if patient_scope:
            return f"consensus:{self.agent_id}:{topic_key}:{patient_scope}"
        return f"consensus:{self.agent_id}:{topic_key}"

    async def seek_agent_consensus(
        self,
        decision_topic: str,
        decision_data: Dict[str, Any],
        fetch_votes_fn: Optional[Callable[..., Any]] = None,
        max_poll_attempts: int = 1,
        poll_delay_seconds: float = 0.0,
    ) -> Dict[str, Any]:
        """Seek consensus from other agents on important decisions."""
        try:
            from app.ai.langgraph.consensus import get_consensus_graph

            consensus_agents = [ALERT_ANALYZER_ID, PATIENT_MONITOR_ID]
            effective_fetch_votes_fn = fetch_votes_fn or self.fetch_votes_fn
            if self.prepare_vote_collection_fn is not None:
                maybe_prepared = self.prepare_vote_collection_fn(consensus_agents)
                if inspect.isawaitable(maybe_prepared):
                    await maybe_prepared

            graph = get_consensus_graph()
            state = await graph.ainvoke(
                {
                    "send_message_fn": self.send_message_fn,
                    "fetch_votes_fn": effective_fetch_votes_fn,
                    "decision_topic": decision_topic,
                    "decision_data": decision_data,
                    "agents": consensus_agents,
                    "min_participants": len(consensus_agents),
                    "consensus_threshold": self.consensus_threshold,
                    "max_poll_attempts": max_poll_attempts,
                    "poll_delay_seconds": poll_delay_seconds,
                },
                config=build_graph_config(
                    thread_id=self._build_consensus_thread_id(
                        decision_topic=decision_topic,
                        decision_data=decision_data,
                    )
                ),
            )
            result = state.get("result")
            if not isinstance(result, dict):
                return {
                    "consensus_reached": False,
                    "error": "Invalid consensus result",
                }
            return result

        except (RuntimeError, TypeError, ValueError) as e:
            self.logger.exception("Consensus seeking failed")
            return {"consensus_reached": False, "error": str(e)}
        except Exception as e:
            self.logger.exception("Unexpected consensus seeking failure")
            return {"consensus_reached": False, "error": str(e)}

    async def escalate_intervention(self, context: FlowContext):
        """Escalate situation for medical intervention."""
        # Create alert for medical team
        alert_data = {
            "patient_id": str(context.patient_id),
            "risk_factors": context.risk_factors,
            "escalated_by": self.agent_id,
            "escalated_at": now_sao_paulo().isoformat(),
            "priority": "high",
            "recommended_actions": [
                "schedule_medical_consultation",
                "increase_monitoring_frequency",
                "review_treatment_plan",
            ],
        }

        # Send alert to alert analyzer agent
        await self.send_message_fn(
            ALERT_ANALYZER_ID,
            "escalation_alert",
            alert_data,
            MessagePriority.CRITICAL,
        )
