"""
Summary Data Aggregator
=======================

Aggregates patient data from multiple sources for AI summary generation.
Collects quiz responses, messages, alerts, and engagement metrics.

Author: AI Architect
Date: January 2025
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Any, Optional
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models import Patient, QuizResponse, Message, Alert
from app.models.patient_flow_response import PatientFlowResponse
from app.models.message import MessageDirection

logger = logging.getLogger(__name__)


@dataclass
class AggregatedPatientData:
    """Aggregated patient data for summary generation."""

    # Patient info
    patient_id: UUID
    patient_name: str
    treatment_type: Optional[str]
    treatment_phase: Optional[str]
    current_day: int

    # Period
    start_date: date
    end_date: date

    # Quiz data
    quiz_count: int
    quiz_responses: List[Dict[str, Any]]

    # Messages
    message_count: int
    messages_summary: List[Dict[str, Any]]

    # Alerts
    alert_count: int
    alerts: List[Dict[str, Any]]

    # Flow responses (patient free-text replies from daily check-ins)
    flow_response_count: int
    flow_responses: List[Dict[str, Any]]

    # Engagement metrics
    response_rate: float
    avg_response_time_minutes: float
    total_messages_sent: int
    total_messages_received: int

    def to_prompt_context(self) -> Dict[str, Any]:
        """Convert to prompt template context."""
        return {
            "patient_name": self.patient_name,
            "treatment_type": self.treatment_type or "Não especificado",
            "treatment_phase": self.treatment_phase or "Não especificada",
            "current_day": self.current_day,
            "start_date": self.start_date.strftime("%d/%m/%Y"),
            "end_date": self.end_date.strftime("%d/%m/%Y"),
            "quiz_count": self.quiz_count,
            "quiz_responses": self._format_quiz_responses(),
            "message_count": self.message_count,
            "messages_summary": self._format_messages(),
            "alert_count": self.alert_count,
            "alerts": self._format_alerts(),
            "flow_response_count": self.flow_response_count,
            "flow_responses": self._format_flow_responses(),
            "response_rate": round(self.response_rate * 100, 1),
            "avg_response_time": self._format_response_time(),
            "total_messages_sent": self.total_messages_sent,
            "total_messages_received": self.total_messages_received,
        }

    def _format_quiz_responses(self) -> str:
        """Format quiz responses for prompt."""
        if not self.quiz_responses:
            return "Nenhum questionário completado no período."

        lines = []
        for resp in self.quiz_responses[:10]:  # Limit to 10 most recent
            date_str = resp.get("date", "")
            question = resp.get("question", "Pergunta não especificada")
            answer = resp.get("answer", "")
            lines.append(f"- [{date_str}] {question}: {answer}")

        if len(self.quiz_responses) > 10:
            lines.append(f"... e mais {len(self.quiz_responses) - 10} respostas")

        return "\n".join(lines)

    def _format_messages(self) -> str:
        """Format messages for prompt."""
        if not self.messages_summary:
            return "Nenhuma mensagem relevante no período."

        lines = []
        for msg in self.messages_summary[:5]:  # Limit to 5 most relevant
            date_str = msg.get("date", "")
            direction = (
                "→ Paciente" if msg.get("direction") == "outbound" else "← Paciente"
            )
            content = msg.get("content", "")[:100]  # Truncate
            lines.append(f"- [{date_str}] {direction}: {content}")

        return "\n".join(lines)

    def _format_alerts(self) -> str:
        """Format alerts for prompt."""
        if not self.alerts:
            return "Nenhum alerta no período."

        lines = []
        for alert in self.alerts:
            date_str = alert.get("date", "")
            severity = alert.get("severity", "unknown").upper()
            title = alert.get("title", "Alerta")
            description = alert.get("description", "")
            recommendation = alert.get("recommendation", "")
            line = f"- [{date_str}] [{severity}] {title}: {description}"
            if recommendation:
                line += f" (Recomendação: {recommendation})"
            lines.append(line)

        return "\n".join(lines)

    def _format_flow_responses(self) -> str:
        """Format flow responses for the prompt.

        Each entry: "- [DD/MM/YYYY] Dia {day_number}: {response_text}"
        Limited to 20 most recent. If empty, returns fallback text.
        """
        if not self.flow_responses:
            return "Nenhuma resposta de acompanhamento no período."

        # Take 20 most recent (list is already sorted by responded_at ASC)
        recent = self.flow_responses[-20:] if len(self.flow_responses) > 20 else self.flow_responses

        lines = []
        for resp in recent:
            date_str = resp.get("date", "")
            day_number = resp.get("day_number", "?")
            response_text = resp.get("response_text", "")
            lines.append(f"- [{date_str}] Dia {day_number}: {response_text}")

        if len(self.flow_responses) > 20:
            lines.append(f"... e mais {len(self.flow_responses) - 20} respostas anteriores")

        logger.info(f"Formatted {len(recent)} flow responses for prompt (total: {len(self.flow_responses)})")
        return "\n".join(lines)

    def _format_response_time(self) -> str:
        """Format average response time."""
        if self.avg_response_time_minutes == 0:
            return "N/A"
        if self.avg_response_time_minutes < 60:
            return f"{int(self.avg_response_time_minutes)} minutos"
        hours = self.avg_response_time_minutes / 60
        return f"{hours:.1f} horas"


class SummaryDataAggregator:
    """
    Aggregates patient data from multiple sources for AI summary generation.

    Collects data from:
    - QuizResponse: Quiz answers and completion status
    - Message: Patient communications
    - Alert: Health alerts triggered
    - FlowAnalytics: Engagement metrics
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize aggregator.

        Args:
            db: AsyncSession for database queries
        """
        self.db = db

    async def aggregate_patient_data(
        self, patient_id: UUID, start_date: date, end_date: date
    ) -> AggregatedPatientData:
        """
        Aggregate all patient data for the specified period.

        Args:
            patient_id: Patient UUID
            start_date: Start of period
            end_date: End of period

        Returns:
            AggregatedPatientData with all collected data
        """
        logger.info(
            f"Aggregating data for patient {patient_id} from {start_date} to {end_date}"
        )

        # Fetch patient info
        patient = await self._get_patient(patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        # Run aggregations in parallel using asyncio.gather for better performance
        import asyncio

        quiz_data, message_data, alert_data, engagement, flow_data = await asyncio.gather(
            self._aggregate_quiz_responses(patient_id, start_date, end_date),
            self._aggregate_messages(patient_id, start_date, end_date),
            self._aggregate_alerts(patient_id, start_date, end_date),
            self._calculate_engagement_metrics(patient_id, start_date, end_date),
            self._aggregate_flow_responses(patient_id, start_date, end_date),
        )

        return AggregatedPatientData(
            patient_id=patient_id,
            patient_name=patient.name,
            treatment_type=patient.treatment_type,
            treatment_phase=patient.treatment_phase,
            current_day=patient.current_day,
            start_date=start_date,
            end_date=end_date,
            quiz_count=quiz_data["count"],
            quiz_responses=quiz_data["responses"],
            message_count=message_data["count"],
            messages_summary=message_data["messages"],
            alert_count=alert_data["count"],
            alerts=alert_data["alerts"],
            flow_response_count=flow_data["count"],
            flow_responses=flow_data["responses"],
            response_rate=engagement["response_rate"],
            avg_response_time_minutes=engagement["avg_response_time"],
            total_messages_sent=engagement["sent"],
            total_messages_received=engagement["received"],
        )

    async def _get_patient(self, patient_id: UUID) -> Optional[Patient]:
        """Get patient by ID."""
        result = await self.db.execute(select(Patient).where(Patient.id == patient_id))
        return result.scalar_one_or_none()

    async def _aggregate_quiz_responses(
        self, patient_id: UUID, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Aggregate quiz responses for the period."""
        # Convert dates to datetime for comparison
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        result = await self.db.execute(
            select(QuizResponse)
            .where(
                and_(
                    QuizResponse.patient_id == patient_id,
                    QuizResponse.created_at >= start_dt,
                    QuizResponse.created_at <= end_dt,
                )
            )
            .order_by(QuizResponse.created_at.desc())
        )
        responses = result.scalars().all()

        formatted = []
        for resp in responses:
            formatted.append(
                {
                    "date": resp.created_at.strftime("%d/%m/%Y"),
                    "question": resp.question_text
                    if hasattr(resp, "question_text")
                    else "Pergunta",
                    "answer": str(resp.response_value) if resp.response_value else "",
                }
            )

        return {"count": len(responses), "responses": formatted}

    async def _aggregate_messages(
        self, patient_id: UUID, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Aggregate messages for the period."""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        result = await self.db.execute(
            select(Message)
            .where(
                and_(
                    Message.patient_id == patient_id,
                    Message.created_at >= start_dt,
                    Message.created_at <= end_dt,
                )
            )
            .order_by(Message.created_at.desc())
            .limit(50)  # Limit to avoid overwhelming the prompt
        )
        messages = result.scalars().all()

        formatted = []
        for msg in messages:
            formatted.append(
                {
                    "date": msg.created_at.strftime("%d/%m/%Y %H:%M"),
                    "direction": msg.direction.value if msg.direction else "unknown",
                    "content": msg.content[:200] if msg.content else "",
                }
            )

        return {
            "count": len(messages),
            "messages": formatted[:10],  # Only include 10 in summary
        }

    async def _aggregate_alerts(
        self, patient_id: UUID, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Aggregate alerts for the period."""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        result = await self.db.execute(
            select(Alert)
            .where(
                and_(
                    Alert.patient_id == patient_id,
                    Alert.created_at >= start_dt,
                    Alert.created_at <= end_dt,
                )
            )
            .order_by(Alert.created_at.desc())
        )
        alerts = result.scalars().all()

        formatted = []
        for alert in alerts:
            alert_data = alert.data or {}
            formatted.append(
                {
                    "date": alert.created_at.strftime("%d/%m/%Y"),
                    "severity": alert.severity.value if alert.severity else "unknown",
                    "description": alert.description,
                    "title": alert_data.get("rule_name", alert.alert_type if hasattr(alert, "alert_type") else "Alerta"),
                    "recommendation": alert_data.get("recommendation", ""),
                }
            )

        return {"count": len(alerts), "alerts": formatted}

    async def _aggregate_flow_responses(
        self, patient_id: UUID, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Aggregate patient flow responses (free-text daily check-in replies) for the period.

        Uses the composite index ix_pfr_patient_responded on (patient_id, responded_at).
        """
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        result = await self.db.execute(
            select(PatientFlowResponse)
            .where(
                and_(
                    PatientFlowResponse.patient_id == patient_id,
                    PatientFlowResponse.responded_at >= start_dt,
                    PatientFlowResponse.responded_at <= end_dt,
                )
            )
            .order_by(PatientFlowResponse.responded_at.asc())
        )
        responses = result.scalars().all()

        logger.info(f"Aggregated {len(responses)} flow responses for patient {patient_id}")

        formatted = []
        for resp in responses:
            formatted.append(
                {
                    "day_number": resp.day_number,
                    "response_text": resp.response_text,
                    "date": resp.responded_at.strftime("%d/%m/%Y"),
                    "message_index": resp.message_index,
                }
            )

        return {"count": len(responses), "responses": formatted}

    async def _calculate_engagement_metrics(
        self, patient_id: UUID, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Calculate engagement metrics for the period."""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        # Count sent messages
        sent_result = await self.db.execute(
            select(func.count(Message.id)).where(
                and_(
                    Message.patient_id == patient_id,
                    Message.direction == MessageDirection.OUTBOUND,
                    Message.created_at >= start_dt,
                    Message.created_at <= end_dt,
                )
            )
        )
        sent_count = sent_result.scalar() or 0

        # Count received messages
        received_result = await self.db.execute(
            select(func.count(Message.id)).where(
                and_(
                    Message.patient_id == patient_id,
                    Message.direction == MessageDirection.INBOUND,
                    Message.created_at >= start_dt,
                    Message.created_at <= end_dt,
                )
            )
        )
        received_count = received_result.scalar() or 0

        # Calculate response rate
        response_rate = 0.0
        if sent_count > 0:
            response_rate = min(received_count / sent_count, 1.0)

        # Average response time (simplified - would need message threading for accurate calculation)
        avg_response_time = 0.0
        if received_count > 0:
            # Estimate based on total period / responses
            total_minutes = (end_dt - start_dt).total_seconds() / 60
            avg_response_time = (
                total_minutes / received_count if received_count > 0 else 0
            )

        return {
            "response_rate": response_rate,
            "avg_response_time": min(avg_response_time, 1440),  # Cap at 24 hours
            "sent": sent_count,
            "received": received_count,
        }
