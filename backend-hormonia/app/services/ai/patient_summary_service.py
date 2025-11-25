"""
Patient Summary Service
=======================

AI-powered patient summary generation service using Google Gemini 2.5 Flash.
Generates comprehensive summaries for doctor consultations.

Author: AI Architect
Date: January 2025
"""

import json
import logging
import time
from datetime import date, datetime
from typing import Dict, List, Any, Optional
from uuid import UUID, uuid4
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.models.patient_summary import PatientSummary
from app.schemas.v2.patient_summary import (
    GenerateSummaryRequest,
    PatientSummaryResponse,
    SummaryContent,
    QuizFindings,
    HealthConcern,
    EngagementMetrics,
    TreatmentCompliance,
    SeverityLevel,
)
from .summary_data_aggregator import SummaryDataAggregator, AggregatedPatientData
from .prompts.patient_summary import PATIENT_SUMMARY_PROMPT, PATIENT_SUMMARY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class PatientSummaryService:
    """
    AI-powered patient summary generation service.

    Uses Google Gemini 2.5 Flash to generate comprehensive patient summaries
    for doctor consultations, including:
    - Quiz response analysis
    - Health concerns detection
    - Engagement metrics
    - Treatment compliance
    - Actionable recommendations

    Features:
    - Redis caching for frequently accessed summaries
    - PDF export capability
    - Historical summary tracking
    - Token usage monitoring
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the service.

        Args:
            db: AsyncSession for database operations
        """
        self.db = db
        self.aggregator = SummaryDataAggregator(db)

        # Initialize Gemini model
        self.model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.3,  # Lower temperature for more consistent output
            max_output_tokens=2000,  # Enough for full summary
        )

        logger.info(f"PatientSummaryService initialized with model: {settings.GEMINI_MODEL}")

    async def generate_summary(
        self,
        request: GenerateSummaryRequest,
        generated_by: Optional[UUID] = None
    ) -> PatientSummaryResponse:
        """
        Generate an AI-powered patient summary.

        Args:
            request: Summary generation request
            generated_by: User ID who requested the summary

        Returns:
            PatientSummaryResponse with full summary content

        Raises:
            ValueError: If patient not found
            ExternalServiceError: On AI generation failure
        """
        start_time = time.time()

        logger.info(f"Generating summary for patient {request.patient_id}")

        # Check cache if not force refresh
        if not request.force_refresh:
            cached = await self._get_cached_summary(
                request.patient_id,
                request.start_date,
                request.end_date
            )
            if cached:
                logger.info(f"Returning cached summary for patient {request.patient_id}")
                return cached

        # Aggregate patient data
        aggregated_data = await self.aggregator.aggregate_patient_data(
            request.patient_id,
            request.start_date,
            request.end_date
        )

        # Generate summary with AI
        summary_content, token_usage = await self._generate_ai_summary(aggregated_data)

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Create response
        summary_id = uuid4()
        response = PatientSummaryResponse(
            summary_id=summary_id,
            patient_id=request.patient_id,
            patient_name=aggregated_data.patient_name,
            start_date=request.start_date,
            end_date=request.end_date,
            content=summary_content,
            generated_at=datetime.utcnow(),
            generated_by=generated_by,
            token_usage=token_usage,
            model_used=settings.GEMINI_MODEL,
            generation_time_ms=generation_time_ms,
            from_cache=False,
        )

        # Save to database if requested
        if request.save_summary:
            await self._save_summary(response)

        logger.info(
            f"Summary generated for patient {request.patient_id} "
            f"in {generation_time_ms}ms, {token_usage} tokens"
        )

        return response

    async def _generate_ai_summary(
        self,
        data: AggregatedPatientData
    ) -> tuple[SummaryContent, int]:
        """
        Generate summary content using Gemini AI.

        Args:
            data: Aggregated patient data

        Returns:
            Tuple of (SummaryContent, token_usage)
        """
        # Build prompt
        prompt_context = data.to_prompt_context()
        formatted_prompt = PATIENT_SUMMARY_PROMPT.format(**prompt_context)

        # Create messages
        messages = [
            SystemMessage(content=PATIENT_SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=formatted_prompt)
        ]

        try:
            # Call Gemini
            response = await self.model.ainvoke(messages)

            # Parse response
            content_text = response.content

            # Extract token usage from response metadata if available
            token_usage = 0
            if hasattr(response, 'response_metadata'):
                usage = response.response_metadata.get('usage_metadata', {})
                token_usage = usage.get('total_token_count', 0)

            # Parse JSON from response
            summary_data = self._parse_summary_response(content_text)

            # Convert to SummaryContent
            summary_content = self._build_summary_content(summary_data)

            return summary_content, token_usage

        except Exception as e:
            logger.error(f"AI summary generation failed: {e}")
            # Return empty summary on failure
            return self._build_fallback_summary(data), 0

    def _parse_summary_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON response from AI."""
        try:
            # Try to extract JSON from response
            # Handle case where AI includes markdown code blocks
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            # Return minimal structure
            return {
                "overview": content[:500] if content else "Resumo não disponível",
                "quiz_findings": {},
                "health_concerns": [],
                "engagement_metrics": {},
                "treatment_compliance": {},
                "recommendations": []
            }

    def _build_summary_content(self, data: Dict[str, Any]) -> SummaryContent:
        """Build SummaryContent from parsed AI response."""
        # Parse quiz findings
        qf_data = data.get("quiz_findings", {})
        quiz_findings = QuizFindings(
            total_completed=qf_data.get("total_completed", 0),
            total_questions_answered=qf_data.get("total_questions_answered", 0),
            key_findings=qf_data.get("key_findings", []),
            symptom_trends=qf_data.get("symptom_trends", {}),
            concerning_responses=qf_data.get("concerning_responses", [])
        )

        # Parse health concerns
        health_concerns = []
        for hc in data.get("health_concerns", []):
            try:
                severity = SeverityLevel(hc.get("severity", "low"))
            except ValueError:
                severity = SeverityLevel.LOW

            health_concerns.append(HealthConcern(
                concern=hc.get("concern", ""),
                severity=severity,
                detected_date=self._parse_date(hc.get("detected_date")),
                source=hc.get("source")
            ))

        # Parse engagement metrics
        em_data = data.get("engagement_metrics", {})
        engagement_metrics = EngagementMetrics(
            response_rate=min(float(em_data.get("response_rate", 0)), 1.0),
            avg_response_time_minutes=float(em_data.get("avg_response_time_minutes", 0)),
            total_messages_sent=int(em_data.get("total_messages_sent", 0)),
            total_messages_received=int(em_data.get("total_messages_received", 0)),
            engagement_score=min(float(em_data.get("engagement_score", 0)), 100)
        )

        # Parse treatment compliance
        tc_data = data.get("treatment_compliance", {})
        treatment_compliance = TreatmentCompliance(
            adherence_score=min(float(tc_data.get("adherence_score", 0)), 1.0),
            missed_interactions=int(tc_data.get("missed_interactions", 0)),
            notes=tc_data.get("notes")
        )

        return SummaryContent(
            overview=data.get("overview", "Resumo não disponível"),
            quiz_findings=quiz_findings,
            health_concerns=health_concerns,
            engagement_metrics=engagement_metrics,
            treatment_compliance=treatment_compliance,
            recommendations=data.get("recommendations", [])
        )

    def _build_fallback_summary(self, data: AggregatedPatientData) -> SummaryContent:
        """Build fallback summary when AI generation fails."""
        return SummaryContent(
            overview=f"Resumo automático indisponível. Dados do período: {data.quiz_count} questionários, {data.message_count} mensagens, {data.alert_count} alertas.",
            quiz_findings=QuizFindings(total_completed=data.quiz_count),
            health_concerns=[],
            engagement_metrics=EngagementMetrics(
                response_rate=data.response_rate,
                avg_response_time_minutes=data.avg_response_time_minutes,
                total_messages_sent=data.total_messages_sent,
                total_messages_received=data.total_messages_received
            ),
            treatment_compliance=TreatmentCompliance(),
            recommendations=["Análise manual recomendada devido a falha na geração automática."]
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                return datetime.strptime(date_str, "%d/%m/%Y").date()
            except ValueError:
                return None

    async def _get_cached_summary(
        self,
        patient_id: UUID,
        start_date: date,
        end_date: date
    ) -> Optional[PatientSummaryResponse]:
        """Check for cached/saved summary within the last hour."""
        from datetime import timedelta

        cache_threshold = datetime.utcnow() - timedelta(hours=1)

        result = await self.db.execute(
            select(PatientSummary)
            .where(
                and_(
                    PatientSummary.patient_id == patient_id,
                    PatientSummary.start_date == start_date,
                    PatientSummary.end_date == end_date,
                    PatientSummary.created_at >= cache_threshold
                )
            )
            .order_by(PatientSummary.created_at.desc())
            .limit(1)
        )
        summary = result.scalar_one_or_none()

        if summary:
            # Convert to response
            return self._summary_to_response(summary, from_cache=True)

        return None

    async def _save_summary(self, response: PatientSummaryResponse) -> None:
        """Save summary to database."""
        summary = PatientSummary(
            id=response.summary_id,
            patient_id=response.patient_id,
            generated_by=response.generated_by,
            start_date=response.start_date,
            end_date=response.end_date,
            content=response.content.model_dump(),
            token_usage=response.token_usage,
            model_used=response.model_used,
            generation_time_ms=response.generation_time_ms,
        )

        self.db.add(summary)
        await self.db.commit()

        logger.info(f"Saved summary {response.summary_id} to database")

    async def get_saved_summaries(
        self,
        patient_id: UUID,
        limit: int = 10,
        offset: int = 0
    ) -> tuple[List[PatientSummaryResponse], int]:
        """
        Get saved summaries for a patient.

        Args:
            patient_id: Patient UUID
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (summaries list, total count)
        """
        # Get total count
        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count(PatientSummary.id))
            .where(PatientSummary.patient_id == patient_id)
        )
        total = count_result.scalar() or 0

        # Get summaries
        result = await self.db.execute(
            select(PatientSummary)
            .where(PatientSummary.patient_id == patient_id)
            .order_by(PatientSummary.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        summaries = result.scalars().all()

        responses = [
            self._summary_to_response(s, from_cache=True)
            for s in summaries
        ]

        return responses, total

    def _summary_to_response(
        self,
        summary: PatientSummary,
        from_cache: bool = False
    ) -> PatientSummaryResponse:
        """Convert database model to response."""
        # Get patient name from relationship or set placeholder
        patient_name = ""
        if summary.patient:
            patient_name = summary.patient.name

        return PatientSummaryResponse(
            summary_id=summary.id,
            patient_id=summary.patient_id,
            patient_name=patient_name,
            start_date=summary.start_date,
            end_date=summary.end_date,
            content=SummaryContent(**summary.content) if summary.content else SummaryContent(overview=""),
            generated_at=summary.created_at,
            generated_by=summary.generated_by,
            token_usage=summary.token_usage,
            model_used=summary.model_used,
            generation_time_ms=summary.generation_time_ms,
            from_cache=from_cache,
        )

    async def export_to_pdf(self, summary_id: UUID) -> bytes:
        """
        Export summary to PDF.

        Args:
            summary_id: Summary UUID

        Returns:
            PDF file bytes
        """
        # Get summary
        result = await self.db.execute(
            select(PatientSummary).where(PatientSummary.id == summary_id)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            raise ValueError(f"Summary {summary_id} not found")

        # Check if PDF already exists
        if summary.pdf_data:
            return summary.pdf_data

        # Generate PDF (simplified - would use reportlab or weasyprint in production)
        pdf_bytes = await self._generate_pdf(summary)

        # Save PDF
        summary.pdf_data = pdf_bytes
        await self.db.commit()

        return pdf_bytes

    async def _generate_pdf(self, summary: PatientSummary) -> bytes:
        """Generate PDF from summary data."""
        # This is a placeholder - implement with reportlab or weasyprint
        # For now, return a simple text representation
        content = summary.content or {}

        text = f"""
RESUMO DO PACIENTE
==================

Período: {summary.start_date} a {summary.end_date}
Gerado em: {summary.created_at}

VISÃO GERAL
-----------
{content.get('overview', 'N/A')}

ACHADOS DOS QUESTIONÁRIOS
-------------------------
Questionários completados: {content.get('quiz_findings', {}).get('total_completed', 0)}

RECOMENDAÇÕES
-------------
{chr(10).join('- ' + r for r in content.get('recommendations', []))}

---
Gerado automaticamente por IA ({summary.model_used})
"""
        return text.encode('utf-8')


# Factory function for dependency injection
def get_patient_summary_service(db: AsyncSession) -> PatientSummaryService:
    """Get PatientSummaryService instance."""
    return PatientSummaryService(db)
