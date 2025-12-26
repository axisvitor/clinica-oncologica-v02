"""State Manager - Manages flow context and patient state."""

from __future__ import annotations

# Standard library
import logging
from typing import Any, Dict, List
from uuid import UUID

# Third-party
from sqlalchemy.orm import Session

# Local
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository

from .models import FlowContext


def _get_knowledge_graph():
    """Lazy import for KnowledgeGraph to prevent startup failures."""
    try:
        from app.memory.knowledge_graph import KnowledgeGraph

        return KnowledgeGraph
    except ImportError as e:
        logging.warning(f"KnowledgeGraph import failed: {e}")
        return None


class StateManager:
    """
    Manages flow state and context building.

    Builds comprehensive context for flow decision making
    by aggregating patient data, flow states, interactions,
    and knowledge graph insights.

    Attributes:
        db_session: Database session.
        agent_id: Unique agent identifier.
        logger: Logger instance.
        patient_repo: Patient repository.
        flow_repo: Flow state repository.
        knowledge_graph: Knowledge graph instance (optional).
    """

    def __init__(self, db_session: Session, agent_id: str, logger: logging.Logger):
        self.db_session = db_session
        self.agent_id = agent_id
        self.logger = logger
        self.patient_repo = PatientRepository(db_session)
        self.flow_repo = FlowStateRepository(db_session)
        self.knowledge_graph = None

    async def initialize_knowledge_graph(self):
        """Initialize knowledge graph with lazy loading."""
        KnowledgeGraph = _get_knowledge_graph()
        if KnowledgeGraph:
            self.knowledge_graph = KnowledgeGraph(self.db_session)
            await self.knowledge_graph.initialize()
        else:
            self.knowledge_graph = None
            self.logger.warning(
                "Knowledge graph not available - some features may be limited"
            )

    async def build_flow_context(
        self, patient_id: UUID, current_day: int
    ) -> FlowContext:
        """Build comprehensive context for flow decision making."""
        context = FlowContext()
        context.patient_id = patient_id
        context.current_day = current_day

        # Get patient data
        context.patient_data = self.patient_repo.get(patient_id)

        # Get flow state
        flow_states = self.flow_repo.get_by_patient_id(patient_id)
        context.flow_state = flow_states[0] if flow_states else None

        # Get knowledge graph context
        if self.knowledge_graph:
            context.knowledge_context = await self.knowledge_graph.get_patient_context(
                patient_id
            )

        # Analyze recent interactions
        context.recent_interactions = await self._get_recent_interactions(patient_id)

        # Calculate mood indicators
        context.mood_indicators = await self._analyze_mood_indicators(context)

        # Calculate adherence metrics
        context.adherence_metrics = await self._calculate_adherence_metrics(context)

        # Identify risk factors
        context.risk_factors = await self._identify_risk_factors(context)

        return context

    async def _get_recent_interactions(self, patient_id: UUID) -> List[Dict]:
        """Get recent patient interactions."""
        # This would query the message history
        # For now, return placeholder
        return []

    async def _analyze_mood_indicators(self, context: FlowContext) -> Dict[str, Any]:
        """Analyze mood indicators from patient context."""
        mood_data = {"trend": 0.0, "current_level": 3.0, "confidence": 0.5}

        # Extract mood data from knowledge graph
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                if "mood" in pattern.get("pattern_type", ""):
                    if "improvement" in pattern["pattern_type"]:
                        mood_data["trend"] = 0.7
                    elif "decline" in pattern["pattern_type"]:
                        mood_data["trend"] = -0.7

                    mood_data["confidence"] = pattern.get("confidence", 0.5)
                    break

        return mood_data

    async def _calculate_adherence_metrics(
        self, context: FlowContext
    ) -> Dict[str, float]:
        """Calculate patient adherence metrics."""
        # Placeholder - would analyze actual interaction data
        return {
            "message_response_rate": 0.8,
            "quiz_completion_rate": 0.9,
            "scheduled_engagement_rate": 0.7,
        }

    async def _identify_risk_factors(self, context: FlowContext) -> List[str]:
        """Identify risk factors from patient context."""
        risk_factors = []

        # Check mood decline
        if context.mood_indicators.get("trend", 0) < -0.6:
            risk_factors.append("mood_decline")

        # Check low engagement
        if context.adherence_metrics.get("message_response_rate", 1.0) < 0.3:
            risk_factors.append("low_engagement")

        # Check recurring symptoms from patterns
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                if pattern.get("pattern_type") == "recurring_symptom":
                    risk_factors.append(
                        f"recurring_{pattern.get('description', 'symptom')}"
                    )

        return risk_factors

    async def close(self):
        """Cleanup resources."""
        if self.knowledge_graph:
            await self.knowledge_graph.close()
