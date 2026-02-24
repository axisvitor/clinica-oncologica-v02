"""
Patient Summary Service
=======================

AI-powered patient summary generation service using Google Gemini 2.5 Flash.
Generates comprehensive summaries for doctor consultations.

Author: AI Architect
Date: January 2025
"""

import asyncio
import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Dict, List, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from google import genai
from google.genai import types

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
from .prompts.patient_summary import (
    PATIENT_SUMMARY_PROMPT,
    PATIENT_SUMMARY_SYSTEM_PROMPT,
)
from app.utils.timezone import now_sao_paulo

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
        self._genai_client = genai.Client(api_key=settings.AI_GEMINI_API_KEY)
        self._genai_config = types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=2000,
        )
        self.model = self._genai_client

        logger.info(
            f"PatientSummaryService initialized with model: {settings.AI_GEMINI_MODEL}"
        )

    async def generate_summary(
        self, request: GenerateSummaryRequest, generated_by: Optional[UUID] = None
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
                request.patient_id, request.start_date, request.end_date
            )
            if cached:
                logger.info(
                    f"Returning cached summary for patient {request.patient_id}"
                )
                return cached

        # Aggregate patient data
        aggregated_data = await self.aggregator.aggregate_patient_data(
            request.patient_id, request.start_date, request.end_date
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
            generated_at=now_sao_paulo(),
            generated_by=generated_by,
            token_usage=token_usage,
            model_used=settings.AI_GEMINI_MODEL,
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
        self, data: AggregatedPatientData
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

        try:
            # FIX: Add timeout to prevent hanging indefinitely on network issues
            # Call Gemini with timeout protection
            config_with_system = types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=2000,
                system_instruction=PATIENT_SUMMARY_SYSTEM_PROMPT,
            )
            response = await asyncio.wait_for(
                self._genai_client.aio.models.generate_content(
                    model=settings.AI_GEMINI_MODEL,
                    contents=formatted_prompt,
                    config=config_with_system,
                ),
                timeout=settings.AI_GEMINI_TIMEOUT_SECONDS
            )

            # Parse response
            content_text = str(response.text or "").strip()

            # Extract token usage from SDK metadata if available
            token_usage = 0
            if response.usage_metadata:
                token_usage = response.usage_metadata.total_token_count or 0

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
                "recommendations": [],
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
            concerning_responses=qf_data.get("concerning_responses", []),
        )

        # Parse health concerns
        health_concerns = []
        for hc in data.get("health_concerns", []):
            try:
                severity = SeverityLevel(hc.get("severity", "low"))
            except ValueError:
                severity = SeverityLevel.LOW

            health_concerns.append(
                HealthConcern(
                    concern=hc.get("concern", ""),
                    severity=severity,
                    detected_date=self._parse_date(hc.get("detected_date")),
                    source=hc.get("source"),
                )
            )

        # Parse engagement metrics
        em_data = data.get("engagement_metrics", {})
        engagement_metrics = EngagementMetrics(
            response_rate=min(float(em_data.get("response_rate", 0)), 1.0),
            avg_response_time_minutes=float(
                em_data.get("avg_response_time_minutes", 0)
            ),
            total_messages_sent=int(em_data.get("total_messages_sent", 0)),
            total_messages_received=int(em_data.get("total_messages_received", 0)),
            engagement_score=min(float(em_data.get("engagement_score", 0)), 100),
        )

        # Parse treatment compliance
        tc_data = data.get("treatment_compliance", {})
        treatment_compliance = TreatmentCompliance(
            adherence_score=min(float(tc_data.get("adherence_score", 0)), 1.0),
            missed_interactions=int(tc_data.get("missed_interactions", 0)),
            notes=tc_data.get("notes"),
        )

        return SummaryContent(
            overview=data.get("overview", "Resumo não disponível"),
            quiz_findings=quiz_findings,
            health_concerns=health_concerns,
            engagement_metrics=engagement_metrics,
            treatment_compliance=treatment_compliance,
            recommendations=data.get("recommendations", []),
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
                total_messages_received=data.total_messages_received,
            ),
            treatment_compliance=TreatmentCompliance(),
            recommendations=[
                "Análise manual recomendada devido a falha na geração automática."
            ],
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
        self, patient_id: UUID, start_date: date, end_date: date
    ) -> Optional[PatientSummaryResponse]:
        """Check for cached/saved summary within the last hour."""
        from datetime import timedelta

        cache_threshold = now_sao_paulo() - timedelta(hours=1)

        result = await self.db.execute(
            select(PatientSummary)
            .where(
                and_(
                    PatientSummary.patient_id == patient_id,
                    PatientSummary.start_date == start_date,
                    PatientSummary.end_date == end_date,
                    PatientSummary.created_at >= cache_threshold,
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
        """Save summary to database with transaction management."""
        from app.utils.transaction_manager import async_transaction

        async with async_transaction(self.db):
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
            # Transaction manager handles commit/rollback automatically

        logger.info(f"Saved summary {response.summary_id} to database")

    async def get_saved_summaries(
        self, patient_id: UUID, limit: int = 10, offset: int = 0
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
            select(func.count(PatientSummary.id)).where(
                PatientSummary.patient_id == patient_id
            )
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

        responses = [self._summary_to_response(s, from_cache=True) for s in summaries]

        return responses, total

    def _summary_to_response(
        self, summary: PatientSummary, from_cache: bool = False
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
            content=SummaryContent(**summary.content)
            if summary.content
            else SummaryContent(overview=""),
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
        """Generate professional PDF from summary data using ReportLab."""
        from io import BytesIO
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
        )
        from reportlab.lib.enums import TA_CENTER

        content = summary.content or {}
        buffer = BytesIO()

        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        # Styles
        styles = getSampleStyleSheet()
        
        # Helper to safely add style
        def add_style(name, parent, **kwargs):
            if name not in styles:
                styles.add(ParagraphStyle(name=name, parent=parent, **kwargs))
            return styles[name]

        title_style = add_style(
            'ReportTitle',
            styles['Heading1'],
            fontSize=18,
            spaceAfter=12,
            textColor=colors.HexColor('#4A148C'),
            alignment=TA_CENTER,
        )
        
        section_style = add_style(
            'SectionTitle',
            styles['Heading2'],
            fontSize=14,
            spaceBefore=16,
            spaceAfter=8,
            textColor=colors.HexColor('#7B1FA2'),
        )
        
        body_style = add_style(
            'BodyText',
            styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            leading=14,
        )
        
        rec_style = add_style(
            'Recommendation',
            styles['Normal'],
            fontSize=10,
            leftIndent=20,
            spaceAfter=4,
            bulletIndent=10,
        )

        elements = []

        # Title
        elements.append(Paragraph("RESUMO DO PACIENTE", styles['ReportTitle']))
        elements.append(Spacer(1, 0.5 * cm))

        # Patient info
        patient_name = summary.patient.name if summary.patient else "Paciente"
        period_text = f"<b>Paciente:</b> {patient_name}<br/>"
        period_text += f"<b>Período:</b> {summary.start_date.strftime('%d/%m/%Y')} a {summary.end_date.strftime('%d/%m/%Y')}<br/>"
        period_text += f"<b>Gerado em:</b> {summary.created_at.strftime('%d/%m/%Y às %H:%M')}"
        elements.append(Paragraph(period_text, styles['BodyText']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceBefore=10, spaceAfter=10))

        # Overview section
        elements.append(Paragraph("Visão Geral", styles['SectionTitle']))
        overview = content.get("overview", "Sem dados disponíveis")
        # Split into paragraphs
        for para in overview.split("\n\n"):
            if para.strip():
                elements.append(Paragraph(para.strip(), styles['BodyText']))
        elements.append(Spacer(1, 0.3 * cm))

        # Quiz Findings
        quiz_findings = content.get("quiz_findings", {})
        elements.append(Paragraph("Achados dos Questionários", styles['SectionTitle']))

        quiz_data = [
            ["Questionários Completados", str(quiz_findings.get("total_completed", 0))],
            ["Perguntas Respondidas", str(quiz_findings.get("total_questions_answered", 0))],
        ]
        quiz_table = Table(quiz_data, colWidths=[10 * cm, 4 * cm])
        quiz_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3E5F5')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(quiz_table)
        elements.append(Spacer(1, 0.3 * cm))

        # Key Findings
        key_findings = quiz_findings.get("key_findings", [])
        if key_findings:
            elements.append(Paragraph("<b>Principais Achados:</b>", styles['BodyText']))
            for finding in key_findings[:5]:
                elements.append(Paragraph(f"• {finding}", styles['Recommendation']))

        # Health Concerns
        concerns = content.get("health_concerns", [])
        if concerns:
            elements.append(Paragraph("Preocupações de Saúde", styles['SectionTitle']))
            for concern in concerns:
                severity = concern.get("severity", "low").upper()
                concern_text = concern.get("concern", "")
                color = {
                    "LOW": "#4CAF50",
                    "MEDIUM": "#FF9800",
                    "HIGH": "#F44336",
                    "CRITICAL": "#B71C1C",
                }.get(severity, "#757575")
                elements.append(Paragraph(
                    f"<font color='{color}'>[{severity}]</font> {concern_text}",
                    styles['BodyText']
                ))

        # Engagement Metrics
        engagement = content.get("engagement_metrics", {})
        elements.append(Paragraph("Métricas de Engajamento", styles['SectionTitle']))
        response_rate = engagement.get("response_rate", 0)
        engagement_data = [
            ["Taxa de Resposta", f"{round(response_rate * 100)}%"],
            ["Mensagens Enviadas", str(engagement.get("total_messages_sent", 0))],
            ["Mensagens Recebidas", str(engagement.get("total_messages_received", 0))],
            ["Score de Engajamento", f"{round(engagement.get('engagement_score', 0))}/100"],
        ]
        eng_table = Table(engagement_data, colWidths=[10 * cm, 4 * cm])
        eng_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E8F5E9')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(eng_table)
        elements.append(Spacer(1, 0.3 * cm))

        # Recommendations
        recommendations = content.get("recommendations", [])
        if recommendations:
            elements.append(Paragraph("Recomendações", styles['SectionTitle']))
            for i, rec in enumerate(recommendations, 1):
                elements.append(Paragraph(f"{i}. {rec}", styles['Recommendation']))

        # Footer
        elements.append(Spacer(1, 1 * cm))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceBefore=10, spaceAfter=10))
        footer_text = f"Gerado automaticamente por IA ({summary.model_used or 'Gemini'})"
        elements.append(Paragraph(footer_text, ParagraphStyle(
            name='Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER,
        )))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer.read()


# Factory function for dependency injection
def get_patient_summary_service(db: AsyncSession) -> PatientSummaryService:
    """Get PatientSummaryService instance."""
    return PatientSummaryService(db)
