"""
Medical insight generation and concern flag identification.
Handles AI-powered analysis of quiz responses and trend patterns.
"""

from __future__ import annotations

import logging
from typing import Any, List
from uuid import UUID
import json

from app.models.quiz import QuizSession, QuizResponse
from app.repositories.patient import PatientRepository
from app.integrations.gemini_client import get_gemini_client
from app.services.reporting.quiz_report_generator.models import (
    ResponseTrend,
    MedicalInsight,
    ConcernLevel,
)

logger = logging.getLogger(__name__)


class QuizAnalyzer:
    """Analyzes quiz responses to generate medical insights and identify concerns."""

    def __init__(self, db: Any):
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.gemini_client = get_gemini_client()

    async def generate_medical_insights(
        self,
        session: QuizSession,
        responses: List[QuizResponse],
        trends: List[ResponseTrend],
    ) -> List[MedicalInsight]:
        """Generate medical insights from quiz responses and trends."""
        try:
            insights: list[MedicalInsight] = []

            # Get patient information
            patient = self.patient_repo.get(session.patient_id)  # type: ignore[arg-type]
            if not patient:
                return insights

            # Prepare context for AI analysis
            response_data = []
            for response in responses:
                response_data.append(
                    {
                        "question_id": response.question_id,
                        "question": response.question_text,
                        "answer": response.response_value,
                        "type": response.response_type,
                    }
                )

            trend_data = []
            for trend in trends:
                trend_data.append(
                    {
                        "question_id": trend.question_id,
                        "question": trend.question_text,
                        "current_value": trend.current_value,
                        "trend_direction": trend.trend_direction.value,
                        "change_percentage": trend.change_percentage,
                        "significance": trend.significance_score,
                    }
                )

            # Generate insights using AI
            prompt = f"""
            Analise as seguintes respostas de questionário médico e tendências para gerar insights médicos:

            Paciente: {patient.name}
            Idade: {getattr(patient, "age", "N/A")}
            Tipo de tratamento: {getattr(patient, "treatment_type", "Terapia hormonal")}

            Respostas atuais:
            {json.dumps(response_data, indent=2, ensure_ascii=False)}

            Tendências identificadas:
            {json.dumps(trend_data, indent=2, ensure_ascii=False)}

            Gere insights médicos no seguinte formato JSON:
            [
                {{
                    "insight_type": "mood_assessment|energy_levels|sleep_quality|side_effects|overall_progress",
                    "description": "Descrição detalhada do insight",
                    "concern_level": "low|medium|high|critical",
                    "recommendations": ["Recomendação 1", "Recomendação 2"],
                    "supporting_data": {{"key": "value"}},
                    "confidence_score": 0.0-1.0
                }}
            ]

            Foque em:
            - Padrões preocupantes ou positivos
            - Mudanças significativas nas tendências
            - Correlações entre diferentes aspectos da saúde
            - Recomendações práticas e específicas
            """

            response = await self.gemini_client.generate_content(prompt)  # type: ignore[assignment]

            try:
                insights_data = json.loads(response)

                for insight_data in insights_data:
                    insight = MedicalInsight(
                        insight_type=insight_data.get("insight_type", "general"),
                        description=insight_data.get("description", ""),
                        concern_level=ConcernLevel(
                            insight_data.get("concern_level", "low")
                        ),
                        recommendations=insight_data.get("recommendations", []),
                        supporting_data=insight_data.get("supporting_data", {}),
                        confidence_score=float(
                            insight_data.get("confidence_score", 0.5)
                        ),
                    )
                    insights.append(insight)

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Could not parse AI insights response: {e}")
                # Create fallback insight
                insights.append(
                    MedicalInsight(
                        insight_type="general",
                        description="Questionário completado com sucesso. Respostas registradas para análise médica.",
                        concern_level=ConcernLevel.LOW,
                        recommendations=["Continue seguindo as orientações médicas"],
                        supporting_data={"responses_count": len(responses)},
                        confidence_score=0.5,
                    )
                )

            return insights

        except Exception as e:
            logger.error(f"Error generating medical insights: {e}")
            return []

    async def identify_concern_flags(
        self, responses: List[QuizResponse], insights: List[MedicalInsight]
    ) -> List[str]:
        """Identify concern flags from responses and insights."""
        try:
            flags = []

            # Check for critical insights
            critical_insights = [
                i for i in insights if i.concern_level == ConcernLevel.CRITICAL
            ]
            if critical_insights:
                flags.append("critical_medical_concerns")

            # Check for high concern insights
            high_concern_insights = [
                i for i in insights if i.concern_level == ConcernLevel.HIGH
            ]
            if high_concern_insights:
                flags.append("high_concern_indicators")

            # Check for declining trends
            declining_trends = [
                i for i in insights if "declining" in i.description.lower()
            ]
            if declining_trends:
                flags.append("declining_health_trends")

            # Check for specific response patterns
            for response in responses:
                if response.response_type == "scale":
                    try:
                        value = float(response.response_value)
                        if value <= 2 and any(
                            keyword in response.question_text.lower()
                            for keyword in ["mood", "energy", "quality", "satisfaction"]
                        ):
                            flags.append("low_wellbeing_scores")
                        elif value >= 4 and any(
                            keyword in response.question_text.lower()
                            for keyword in ["pain", "side_effects", "problems"]
                        ):
                            flags.append("high_symptom_scores")
                    except (ValueError, TypeError):
                        continue

                elif response.response_type == "open_text":
                    text_lower = response.response_value.lower()
                    if any(
                        keyword in text_lower
                        for keyword in [
                            "dor",
                            "pain",
                            "preocupação",
                            "worry",
                            "problema",
                            "problem",
                        ]
                    ):
                        flags.append("concerning_text_responses")

            return list(set(flags))  # Remove duplicates

        except Exception as e:
            logger.error(f"Error identifying concern flags: {e}")
            return []

    async def generate_recommendations(
        self, insights: List[MedicalInsight], concern_flags: List[str], patient_id: UUID
    ) -> List[str]:
        """Generate personalized recommendations."""
        try:
            recommendations = []

            # Collect recommendations from insights
            for insight in insights:
                recommendations.extend(insight.recommendations)

            # Add general recommendations based on concern flags
            if "critical_medical_concerns" in concern_flags:
                recommendations.append(
                    "Agende uma consulta médica urgente para discutir os resultados"
                )

            if "high_concern_indicators" in concern_flags:
                recommendations.append(
                    "Entre em contato com sua equipe médica para avaliação"
                )

            if "declining_health_trends" in concern_flags:
                recommendations.append(
                    "Monitore de perto os sintomas e mantenha comunicação regular com o médico"
                )

            if "low_wellbeing_scores" in concern_flags:
                recommendations.extend(
                    [
                        "Considere atividades que promovam bem-estar mental",
                        "Mantenha uma rotina de exercícios leves, se aprovado pelo médico",
                        "Pratique técnicas de relaxamento e mindfulness",
                    ]
                )

            if "high_symptom_scores" in concern_flags:
                recommendations.extend(
                    [
                        "Documente os sintomas e sua frequência",
                        "Discuta opções de manejo de sintomas com sua equipe médica",
                    ]
                )

            # Remove duplicates and limit to most important
            unique_recommendations = list(set(recommendations))
            return unique_recommendations[:8]  # Limit to 8 most important

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return [
                "Continue seguindo as orientações médicas e mantenha comunicação regular com sua equipe de saúde"
            ]
