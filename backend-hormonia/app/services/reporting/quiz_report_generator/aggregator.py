"""
Data aggregation and analysis for quiz responses.
Handles metrics calculation, trend analysis, and health score computation.
"""

import logging
import statistics
from typing import Any, List, Optional, Tuple
from uuid import UUID
import json

from app.models.quiz import QuizSession, QuizResponse
from app.repositories.quiz import QuizSessionRepository, QuizResponseRepository
from app.integrations.gemini_client import get_gemini_client
from app.services.reporting.quiz_report_generator.models import (
    QuizMetrics,
    ResponseTrend,
    TrendDirection,
    MedicalInsight,
    ConcernLevel,
)

logger = logging.getLogger(__name__)


class QuizDataAggregator:
    """Aggregates and analyzes quiz response data."""

    def __init__(self, db: Any):
        self.db = db
        self.session_repo = QuizSessionRepository(db)
        self.response_repo = QuizResponseRepository(db)
        self.gemini_client = get_gemini_client()

    async def calculate_quiz_metrics(
        self, session: QuizSession, responses: List[QuizResponse]
    ) -> QuizMetrics:
        """Calculate basic quiz metrics."""
        try:
            # Get template to count total questions
            from app.services.quiz import QuizTemplateService

            template_service = QuizTemplateService(self.db)
            template = template_service.get_template(session.quiz_template_id)

            total_questions = len(template.questions)
            answered_questions = len(responses)
            completion_rate = (
                (answered_questions / total_questions) * 100
                if total_questions > 0
                else 0
            )

            # Calculate average response time
            response_times = []
            if session.started_at and responses:
                for i, response in enumerate(
                    sorted(responses, key=lambda r: r.responded_at)
                ):  # type: ignore[arg-type,return-value]
                    if i == 0:
                        # First response time from session start
                        time_diff = (
                            response.responded_at - session.started_at
                        ).total_seconds()
                    else:
                        # Time between responses
                        prev_response = sorted(responses, key=lambda r: r.responded_at)[
                            i - 1
                        ]  # type: ignore[arg-type,return-value]
                        time_diff = (
                            response.responded_at - prev_response.responded_at
                        ).total_seconds()

                    response_times.append(time_diff)

            average_response_time = (
                statistics.mean(response_times) if response_times else None
            )

            # Calculate response quality score (based on completeness and consistency)
            quality_score = await self.calculate_response_quality_score(responses)

            # Convert SQLAlchemy Column types to UUID (ORM handles at runtime)
            session_id: UUID = session.id  # type: ignore[assignment]
            patient_id: UUID = session.patient_id  # type: ignore[assignment]
            template_id: UUID = session.quiz_template_id  # type: ignore[assignment]

            return QuizMetrics(
                session_id=session_id,
                patient_id=patient_id,
                template_id=template_id,
                completion_date=session.completed_at,  # type: ignore[arg-type]
                total_questions=total_questions,
                answered_questions=answered_questions,
                completion_rate=completion_rate,
                average_response_time=average_response_time,
                response_quality_score=quality_score,
            )

        except Exception as e:
            logger.error(f"Error calculating quiz metrics: {e}")
            raise

    async def calculate_response_quality_score(
        self, responses: List[QuizResponse]
    ) -> float:
        """Calculate response quality score based on completeness and consistency."""
        try:
            if not responses:
                return 0.0

            quality_factors = []

            # Completeness factor
            non_empty_responses = [
                r for r in responses if r.response_value and r.response_value.strip()
            ]
            completeness = len(non_empty_responses) / len(responses)
            quality_factors.append(completeness)

            # Response length factor (for text responses)
            text_responses = [r for r in responses if r.response_type == "open_text"]
            if text_responses:
                avg_length = statistics.mean(
                    [len(r.response_value) for r in text_responses]
                )
                length_score = min(
                    avg_length / 50, 1.0
                )  # Normalize to 0-1, 50 chars = 1.0
                quality_factors.append(length_score)

            # Consistency factor (responses that make sense in context)
            consistency_score = await self._assess_response_consistency(responses)
            quality_factors.append(consistency_score)

            # Overall quality score
            return statistics.mean(quality_factors) if quality_factors else 0.0

        except Exception as e:
            logger.error(f"Error calculating response quality score: {e}")
            return 0.0

    async def _assess_response_consistency(
        self, responses: List[QuizResponse]
    ) -> float:
        """Assess consistency of responses using AI."""
        try:
            if len(responses) < 2:
                return 1.0  # Single response is always consistent

            # Create context for AI analysis
            response_context = []
            for response in responses:
                response_context.append(
                    {
                        "question": response.question_text,
                        "answer": response.response_value,
                        "type": response.response_type,
                    }
                )

            prompt = f"""
            Analise a consistência das seguintes respostas de um questionário médico:

            {json.dumps(response_context, indent=2, ensure_ascii=False)}

            Avalie se as respostas são consistentes entre si e fazem sentido no contexto médico.
            Considere:
            - Contradições entre respostas
            - Coerência emocional
            - Lógica médica

            Retorne apenas um número de 0.0 a 1.0 representando o nível de consistência:
            - 1.0 = Totalmente consistente
            - 0.5 = Moderadamente consistente
            - 0.0 = Inconsistente
            """

            response = await self.gemini_client.generate_content(prompt)  # type: ignore[assignment]

            try:
                consistency_score = float(response.strip())
                return max(0.0, min(1.0, consistency_score))  # Clamp to 0-1
            except (ValueError, AttributeError):
                logger.warning("Could not parse consistency score from AI response")
                return 0.7  # Default moderate consistency

        except Exception as e:
            logger.error(f"Error assessing response consistency: {e}")
            return 0.7  # Default moderate consistency

    async def analyze_response_trends(
        self, patient_id: UUID, template_id: UUID, current_responses: List[QuizResponse]
    ) -> List[ResponseTrend]:
        """Analyze trends in patient responses over time."""
        try:
            trends = []

            # Get historical responses for the same template
            historical_sessions = self.session_repo.get_patient_template_sessions(  # type: ignore[attr-defined]
                patient_id, template_id, limit=5
            )

            if len(historical_sessions) < 2:
                # Not enough data for trend analysis
                return []

            # Group responses by question
            question_responses = {}

            for session in historical_sessions:
                session_responses = self.response_repo.get_by_session(session.id)  # type: ignore[attr-defined]
                for response in session_responses:
                    question_id = response.question_id
                    if question_id not in question_responses:
                        question_responses[question_id] = {
                            "question_text": response.question_text,
                            "responses": [],
                        }

                    question_responses[question_id]["responses"].append(
                        {
                            "value": response.response_value,
                            "date": session.completed_at,
                            "session_id": session.id,
                        }
                    )

            # Analyze trends for each question
            for question_id, data in question_responses.items():
                if len(data["responses"]) < 2:
                    continue

                # Sort by date
                sorted_responses = sorted(data["responses"], key=lambda x: x["date"])

                # Get current and previous values
                current_value = sorted_responses[-1]["value"]
                previous_values = [r["value"] for r in sorted_responses[:-1]]

                # Determine trend direction
                (
                    trend_direction,
                    change_percentage,
                ) = await self._calculate_trend_direction(
                    current_value, previous_values, question_id
                )

                # Calculate significance score
                significance_score = await self._calculate_trend_significance(
                    current_value, previous_values, trend_direction
                )

                trend = ResponseTrend(
                    question_id=question_id,
                    question_text=data["question_text"],
                    current_value=current_value,
                    previous_values=previous_values,
                    trend_direction=trend_direction,
                    change_percentage=change_percentage,
                    significance_score=significance_score,
                )

                trends.append(trend)

            return trends

        except Exception as e:
            logger.error(f"Error analyzing response trends: {e}")
            return []

    async def _calculate_trend_direction(
        self, current_value: Any, previous_values: List[Any], question_id: str
    ) -> Tuple[TrendDirection, Optional[float]]:
        """Calculate trend direction and change percentage."""
        try:
            if not previous_values:
                return TrendDirection.INSUFFICIENT_DATA, None

            # Handle numeric values (scale questions)
            if self._is_numeric_response(current_value) and all(
                self._is_numeric_response(v) for v in previous_values
            ):
                current_num = float(current_value)
                previous_nums = [float(v) for v in previous_values]

                # Calculate average of previous values
                avg_previous = statistics.mean(previous_nums)

                # Calculate change percentage
                if avg_previous != 0:
                    change_percentage = (
                        (current_num - avg_previous) / avg_previous
                    ) * 100
                else:
                    change_percentage = 0.0

                # Determine trend direction based on question type
                if self._is_positive_scale_question(question_id):
                    # Higher values are better (mood, energy, satisfaction)
                    if change_percentage > 10:
                        return TrendDirection.IMPROVING, change_percentage
                    elif change_percentage < -10:
                        return TrendDirection.DECLINING, change_percentage
                    else:
                        return TrendDirection.STABLE, change_percentage
                else:
                    # Lower values are better (pain, side effects)
                    if change_percentage > 10:
                        return TrendDirection.DECLINING, change_percentage
                    elif change_percentage < -10:
                        return TrendDirection.IMPROVING, change_percentage
                    else:
                        return TrendDirection.STABLE, change_percentage

            # Handle categorical responses
            else:
                # Use AI to assess trend for non-numeric responses
                trend_direction = await self._assess_categorical_trend(
                    current_value, previous_values, question_id
                )
                return trend_direction, None

        except Exception as e:
            logger.error(f"Error calculating trend direction: {e}")
            return TrendDirection.INSUFFICIENT_DATA, None

    def _is_numeric_response(self, value: Any) -> bool:
        """Check if response value is numeric."""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def _is_positive_scale_question(self, question_id: str) -> bool:
        """Determine if higher values are positive for this question."""
        positive_indicators = [
            "mood",
            "energy",
            "satisfaction",
            "quality",
            "well",
            "good",
            "happy",
            "confident",
            "motivated",
            "progress",
            "improvement",
        ]

        question_id_lower = question_id.lower()
        return any(indicator in question_id_lower for indicator in positive_indicators)

    async def _assess_categorical_trend(
        self, current_value: str, previous_values: List[str], question_id: str
    ) -> TrendDirection:
        """Use AI to assess trend for categorical responses."""
        try:
            prompt = f"""
            Analise a tendência nas seguintes respostas para a pergunta "{question_id}":

            Respostas anteriores: {previous_values}
            Resposta atual: {current_value}

            Determine se a tendência é:
            - IMPROVING (melhorando)
            - STABLE (estável)
            - DECLINING (piorando)
            - INSUFFICIENT_DATA (dados insuficientes)

            Considere o contexto médico e se a mudança representa melhora ou piora na condição do paciente.

            Retorne apenas uma das palavras: IMPROVING, STABLE, DECLINING, ou INSUFFICIENT_DATA
            """

            response = await self.gemini_client.generate_content(prompt)

            trend_str = response.strip().upper()
            if trend_str in ["IMPROVING", "STABLE", "DECLINING", "INSUFFICIENT_DATA"]:
                return TrendDirection(trend_str.lower())
            else:
                return TrendDirection.INSUFFICIENT_DATA

        except Exception as e:
            logger.error(f"Error assessing categorical trend: {e}")
            return TrendDirection.INSUFFICIENT_DATA

    async def _calculate_trend_significance(
        self,
        current_value: Any,
        previous_values: List[Any],
        trend_direction: TrendDirection,
    ) -> float:
        """Calculate significance score for trend."""
        try:
            if trend_direction == TrendDirection.INSUFFICIENT_DATA:
                return 0.0

            # Base significance on trend direction
            if trend_direction == TrendDirection.STABLE:
                return 0.3
            elif trend_direction in [
                TrendDirection.IMPROVING,
                TrendDirection.DECLINING,
            ]:
                # Higher significance for consistent trends
                if len(previous_values) >= 3:
                    return 0.8
                else:
                    return 0.6

            return 0.0

        except Exception as e:
            logger.error(f"Error calculating trend significance: {e}")
            return 0.0

    async def calculate_health_score(
        self, responses: List[QuizResponse], insights: List[MedicalInsight]
    ) -> float:
        """Calculate overall health score based on responses and insights."""
        try:
            if not responses:
                return 0.0

            score_factors = []

            # Factor 1: Response completeness
            completeness = len(
                [r for r in responses if r.response_value and r.response_value.strip()]
            ) / len(responses)
            score_factors.append(completeness * 100)

            # Factor 2: Positive responses in scale questions
            scale_responses = [r for r in responses if r.response_type == "scale"]
            if scale_responses:
                scale_scores = []
                for response in scale_responses:
                    try:
                        value = float(response.response_value)
                        # Normalize to 0-100 scale (assuming 1-5 scale)
                        normalized_score = ((value - 1) / 4) * 100
                        scale_scores.append(normalized_score)
                    except (ValueError, TypeError):
                        continue

                if scale_scores:
                    avg_scale_score = statistics.mean(scale_scores)
                    score_factors.append(avg_scale_score)

            # Factor 3: Concern level from insights
            concern_penalty = 0
            for insight in insights:
                if insight.concern_level == ConcernLevel.CRITICAL:
                    concern_penalty += 30
                elif insight.concern_level == ConcernLevel.HIGH:
                    concern_penalty += 20
                elif insight.concern_level == ConcernLevel.MEDIUM:
                    concern_penalty += 10

            # Calculate overall score
            base_score = statistics.mean(score_factors) if score_factors else 50
            final_score = max(0, min(100, base_score - concern_penalty))

            return final_score

        except Exception as e:
            logger.error(f"Error calculating health score: {e}")
            return 50.0  # Default neutral score
