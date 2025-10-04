"""
Quiz response processing and medical report generation service.
Handles quiz response collection, validation, trend analysis, and automated report generation.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum
import json
import statistics
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.quiz import QuizSession, QuizResponse, QuizTemplate
from app.models.patient import Patient
from app.models.report import Report, ReportType, ReportStatus
from app.repositories.quiz import QuizSessionRepository, QuizResponseRepository
from app.repositories.patient import PatientRepository
from app.repositories.report import ReportRepository
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
from app.integrations.gemini_client import get_gemini_client
from app.integrations.pdf_generator import PDFGenerator
from app.exceptions import NotFoundError, ValidationError
from app.utils.constants import MEDICAL_CONCERN_THRESHOLDS

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Trend direction indicators."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    INSUFFICIENT_DATA = "insufficient_data"


class ConcernLevel(Enum):
    """Medical concern levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QuizMetrics:
    """Quiz response metrics."""
    session_id: UUID
    patient_id: UUID
    template_id: UUID
    completion_date: datetime
    total_questions: int
    answered_questions: int
    completion_rate: float
    average_response_time: Optional[float] = None
    response_quality_score: float = 0.0


@dataclass
class ResponseTrend:
    """Response trend analysis."""
    question_id: str
    question_text: str
    current_value: Any
    previous_values: List[Any]
    trend_direction: TrendDirection
    change_percentage: Optional[float] = None
    significance_score: float = 0.0


@dataclass
class MedicalInsight:
    """Medical insight from quiz analysis."""
    insight_type: str
    description: str
    concern_level: ConcernLevel
    recommendations: List[str]
    supporting_data: dict[str, Any]
    confidence_score: float


@dataclass
class QuizAnalysisResult:
    """Complete quiz analysis result."""
    session_id: UUID
    patient_id: UUID
    metrics: QuizMetrics
    response_trends: List[ResponseTrend]
    medical_insights: List[MedicalInsight]
    overall_health_score: float
    concern_flags: List[str]
    recommendations: List[str]
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)


class QuizResponseProcessor:
    """Service for processing quiz responses and generating insights."""
    
    def __init__(self, db: Session):
        self.db = db
        self.session_repo = QuizSessionRepository(db)
        self.response_repo = QuizResponseRepository(db)
        self.patient_repo = PatientRepository(db)
        self.report_repo = ReportRepository(db)
        self.gemini_client = get_gemini_client()
        self.pdf_generator = PDFGenerator()
    
    async def process_completed_quiz(self, session_id: UUID) -> QuizAnalysisResult:
        """
        Process completed quiz session and generate comprehensive analysis.
        
        Args:
            session_id: Quiz session ID
            
        Returns:
            Complete quiz analysis result
        """
        try:
            logger.info(f"Processing completed quiz session {session_id}")
            
            # Get quiz session
            session = self.session_repo.get(session_id)
            if not session:
                raise NotFoundError(f"Quiz session {session_id} not found")
            
            if session.status != 'completed':
                raise ValidationError(f"Quiz session {session_id} is not completed")
            
            # Get quiz responses
            responses = self.response_repo.get_by_session(session_id)
            
            # Calculate basic metrics
            metrics = await self._calculate_quiz_metrics(session, responses)
            
            # Analyze response trends
            response_trends = await self._analyze_response_trends(
                session.patient_id, session.quiz_template_id, responses
            )
            
            # Generate medical insights
            medical_insights = await self._generate_medical_insights(
                session, responses, response_trends
            )
            
            # Calculate overall health score
            overall_health_score = await self._calculate_health_score(
                responses, medical_insights
            )
            
            # Identify concern flags
            concern_flags = await self._identify_concern_flags(
                responses, medical_insights
            )
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                medical_insights, concern_flags, session.patient_id
            )
            
            # Create analysis result
            analysis_result = QuizAnalysisResult(
                session_id=session_id,
                patient_id=session.patient_id,
                metrics=metrics,
                response_trends=response_trends,
                medical_insights=medical_insights,
                overall_health_score=overall_health_score,
                concern_flags=concern_flags,
                recommendations=recommendations
            )
            
            logger.info(f"Quiz analysis completed for session {session_id}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error processing completed quiz: {e}")
            raise
    
    async def _calculate_quiz_metrics(self, 
                                    session: QuizSession, 
                                    responses: List[QuizResponse]) -> QuizMetrics:
        """Calculate basic quiz metrics."""
        try:
            # Get template to count total questions
            from app.services.quiz import QuizTemplateService
            template_service = QuizTemplateService(self.db)
            template = template_service.get_template(session.quiz_template_id)
            
            total_questions = len(template.questions)
            answered_questions = len(responses)
            completion_rate = (answered_questions / total_questions) * 100 if total_questions > 0 else 0
            
            # Calculate average response time
            response_times = []
            if session.started_at and responses:
                for i, response in enumerate(sorted(responses, key=lambda r: r.responded_at)):
                    if i == 0:
                        # First response time from session start
                        time_diff = (response.responded_at - session.started_at).total_seconds()
                    else:
                        # Time between responses
                        prev_response = sorted(responses, key=lambda r: r.responded_at)[i-1]
                        time_diff = (response.responded_at - prev_response.responded_at).total_seconds()
                    
                    response_times.append(time_diff)
            
            average_response_time = statistics.mean(response_times) if response_times else None
            
            # Calculate response quality score (based on completeness and consistency)
            quality_score = await self._calculate_response_quality_score(responses)
            
            return QuizMetrics(
                session_id=session.id,
                patient_id=session.patient_id,
                template_id=session.quiz_template_id,
                completion_date=session.completed_at,
                total_questions=total_questions,
                answered_questions=answered_questions,
                completion_rate=completion_rate,
                average_response_time=average_response_time,
                response_quality_score=quality_score
            )
            
        except Exception as e:
            logger.error(f"Error calculating quiz metrics: {e}")
            raise
    
    async def _calculate_response_quality_score(self, responses: List[QuizResponse]) -> float:
        """Calculate response quality score based on completeness and consistency."""
        try:
            if not responses:
                return 0.0
            
            quality_factors = []
            
            # Completeness factor
            non_empty_responses = [r for r in responses if r.response_value and r.response_value.strip()]
            completeness = len(non_empty_responses) / len(responses)
            quality_factors.append(completeness)
            
            # Response length factor (for text responses)
            text_responses = [r for r in responses if r.response_type == "open_text"]
            if text_responses:
                avg_length = statistics.mean([len(r.response_value) for r in text_responses])
                length_score = min(avg_length / 50, 1.0)  # Normalize to 0-1, 50 chars = 1.0
                quality_factors.append(length_score)
            
            # Consistency factor (responses that make sense in context)
            consistency_score = await self._assess_response_consistency(responses)
            quality_factors.append(consistency_score)
            
            # Overall quality score
            return statistics.mean(quality_factors) if quality_factors else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating response quality score: {e}")
            return 0.0
    
    async def _assess_response_consistency(self, responses: List[QuizResponse]) -> float:
        """Assess consistency of responses using AI."""
        try:
            if len(responses) < 2:
                return 1.0  # Single response is always consistent
            
            # Create context for AI analysis
            response_context = []
            for response in responses:
                response_context.append({
                    "question": response.question_text,
                    "answer": response.response_value,
                    "type": response.response_type
                })
            
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
            
            response = await self.gemini_client.generate_content(prompt)
            
            try:
                consistency_score = float(response.strip())
                return max(0.0, min(1.0, consistency_score))  # Clamp to 0-1
            except (ValueError, AttributeError):
                logger.warning("Could not parse consistency score from AI response")
                return 0.7  # Default moderate consistency
            
        except Exception as e:
            logger.error(f"Error assessing response consistency: {e}")
            return 0.7  # Default moderate consistency
    
    async def _analyze_response_trends(self, 
                                     patient_id: UUID, 
                                     template_id: UUID,
                                     current_responses: List[QuizResponse]) -> List[ResponseTrend]:
        """Analyze trends in patient responses over time."""
        try:
            trends = []
            
            # Get historical responses for the same template
            historical_sessions = self.session_repo.get_patient_template_sessions(
                patient_id, template_id, limit=5
            )
            
            if len(historical_sessions) < 2:
                # Not enough data for trend analysis
                return []
            
            # Group responses by question
            question_responses = {}
            
            for session in historical_sessions:
                session_responses = self.response_repo.get_by_session(session.id)
                for response in session_responses:
                    question_id = response.question_id
                    if question_id not in question_responses:
                        question_responses[question_id] = {
                            "question_text": response.question_text,
                            "responses": []
                        }
                    
                    question_responses[question_id]["responses"].append({
                        "value": response.response_value,
                        "date": session.completed_at,
                        "session_id": session.id
                    })
            
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
                trend_direction, change_percentage = await self._calculate_trend_direction(
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
                    significance_score=significance_score
                )
                
                trends.append(trend)
            
            return trends
            
        except Exception as e:
            logger.error(f"Error analyzing response trends: {e}")
            return []
    
    async def _calculate_trend_direction(self, 
                                       current_value: Any, 
                                       previous_values: List[Any],
                                       question_id: str) -> Tuple[TrendDirection, Optional[float]]:
        """Calculate trend direction and change percentage."""
        try:
            if not previous_values:
                return TrendDirection.INSUFFICIENT_DATA, None
            
            # Handle numeric values (scale questions)
            if self._is_numeric_response(current_value) and all(self._is_numeric_response(v) for v in previous_values):
                current_num = float(current_value)
                previous_nums = [float(v) for v in previous_values]
                
                # Calculate average of previous values
                avg_previous = statistics.mean(previous_nums)
                
                # Calculate change percentage
                if avg_previous != 0:
                    change_percentage = ((current_num - avg_previous) / avg_previous) * 100
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
            "mood", "energy", "satisfaction", "quality", "well", "good", "happy",
            "confident", "motivated", "progress", "improvement"
        ]
        
        question_id_lower = question_id.lower()
        return any(indicator in question_id_lower for indicator in positive_indicators)
    
    async def _assess_categorical_trend(self, 
                                      current_value: str, 
                                      previous_values: List[str],
                                      question_id: str) -> TrendDirection:
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
    
    async def _calculate_trend_significance(self, 
                                          current_value: Any, 
                                          previous_values: List[Any],
                                          trend_direction: TrendDirection) -> float:
        """Calculate significance score for trend."""
        try:
            if trend_direction == TrendDirection.INSUFFICIENT_DATA:
                return 0.0
            
            # Base significance on trend direction
            if trend_direction == TrendDirection.STABLE:
                return 0.3
            elif trend_direction in [TrendDirection.IMPROVING, TrendDirection.DECLINING]:
                # Higher significance for consistent trends
                if len(previous_values) >= 3:
                    return 0.8
                else:
                    return 0.6
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating trend significance: {e}")
            return 0.0
    
    async def _generate_medical_insights(self, 
                                       session: QuizSession,
                                       responses: List[QuizResponse],
                                       trends: List[ResponseTrend]) -> List[MedicalInsight]:
        """Generate medical insights from quiz responses and trends."""
        try:
            insights = []
            
            # Get patient information
            patient = self.patient_repo.get(session.patient_id)
            if not patient:
                return insights
            
            # Prepare context for AI analysis
            response_data = []
            for response in responses:
                response_data.append({
                    "question_id": response.question_id,
                    "question": response.question_text,
                    "answer": response.response_value,
                    "type": response.response_type
                })
            
            trend_data = []
            for trend in trends:
                trend_data.append({
                    "question_id": trend.question_id,
                    "question": trend.question_text,
                    "current_value": trend.current_value,
                    "trend_direction": trend.trend_direction.value,
                    "change_percentage": trend.change_percentage,
                    "significance": trend.significance_score
                })
            
            # Generate insights using AI
            prompt = f"""
            Analise as seguintes respostas de questionário médico e tendências para gerar insights médicos:
            
            Paciente: {patient.name}
            Idade: {getattr(patient, 'age', 'N/A')}
            Tipo de tratamento: {getattr(patient, 'treatment_type', 'Terapia hormonal')}
            
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
            
            response = await self.gemini_client.generate_content(prompt)
            
            try:
                insights_data = json.loads(response)
                
                for insight_data in insights_data:
                    insight = MedicalInsight(
                        insight_type=insight_data.get("insight_type", "general"),
                        description=insight_data.get("description", ""),
                        concern_level=ConcernLevel(insight_data.get("concern_level", "low")),
                        recommendations=insight_data.get("recommendations", []),
                        supporting_data=insight_data.get("supporting_data", {}),
                        confidence_score=float(insight_data.get("confidence_score", 0.5))
                    )
                    insights.append(insight)
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Could not parse AI insights response: {e}")
                # Create fallback insight
                insights.append(MedicalInsight(
                    insight_type="general",
                    description="Questionário completado com sucesso. Respostas registradas para análise médica.",
                    concern_level=ConcernLevel.LOW,
                    recommendations=["Continue seguindo as orientações médicas"],
                    supporting_data={"responses_count": len(responses)},
                    confidence_score=0.5
                ))
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating medical insights: {e}")
            return []
    
    async def _calculate_health_score(self, 
                                    responses: List[QuizResponse],
                                    insights: List[MedicalInsight]) -> float:
        """Calculate overall health score based on responses and insights."""
        try:
            if not responses:
                return 0.0
            
            score_factors = []
            
            # Factor 1: Response completeness
            completeness = len([r for r in responses if r.response_value and r.response_value.strip()]) / len(responses)
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
    
    async def _identify_concern_flags(self, 
                                    responses: List[QuizResponse],
                                    insights: List[MedicalInsight]) -> List[str]:
        """Identify concern flags from responses and insights."""
        try:
            flags = []
            
            # Check for critical insights
            critical_insights = [i for i in insights if i.concern_level == ConcernLevel.CRITICAL]
            if critical_insights:
                flags.append("critical_medical_concerns")
            
            # Check for high concern insights
            high_concern_insights = [i for i in insights if i.concern_level == ConcernLevel.HIGH]
            if high_concern_insights:
                flags.append("high_concern_indicators")
            
            # Check for declining trends
            declining_trends = [i for i in insights if "declining" in i.description.lower()]
            if declining_trends:
                flags.append("declining_health_trends")
            
            # Check for specific response patterns
            for response in responses:
                if response.response_type == "scale":
                    try:
                        value = float(response.response_value)
                        if value <= 2 and any(keyword in response.question_text.lower() 
                                            for keyword in ["mood", "energy", "quality", "satisfaction"]):
                            flags.append("low_wellbeing_scores")
                        elif value >= 4 and any(keyword in response.question_text.lower() 
                                              for keyword in ["pain", "side_effects", "problems"]):
                            flags.append("high_symptom_scores")
                    except (ValueError, TypeError):
                        continue
                
                elif response.response_type == "open_text":
                    text_lower = response.response_value.lower()
                    if any(keyword in text_lower for keyword in ["dor", "pain", "preocupação", "worry", "problema", "problem"]):
                        flags.append("concerning_text_responses")
            
            return list(set(flags))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error identifying concern flags: {e}")
            return []
    
    async def _generate_recommendations(self, 
                                      insights: List[MedicalInsight],
                                      concern_flags: List[str],
                                      patient_id: UUID) -> List[str]:
        """Generate personalized recommendations."""
        try:
            recommendations = []
            
            # Collect recommendations from insights
            for insight in insights:
                recommendations.extend(insight.recommendations)
            
            # Add general recommendations based on concern flags
            if "critical_medical_concerns" in concern_flags:
                recommendations.append("Agende uma consulta médica urgente para discutir os resultados")
            
            if "high_concern_indicators" in concern_flags:
                recommendations.append("Entre em contato com sua equipe médica para avaliação")
            
            if "declining_health_trends" in concern_flags:
                recommendations.append("Monitore de perto os sintomas e mantenha comunicação regular com o médico")
            
            if "low_wellbeing_scores" in concern_flags:
                recommendations.extend([
                    "Considere atividades que promovam bem-estar mental",
                    "Mantenha uma rotina de exercícios leves, se aprovado pelo médico",
                    "Pratique técnicas de relaxamento e mindfulness"
                ])
            
            if "high_symptom_scores" in concern_flags:
                recommendations.extend([
                    "Documente os sintomas e sua frequência",
                    "Discuta opções de manejo de sintomas com sua equipe médica"
                ])
            
            # Remove duplicates and limit to most important
            unique_recommendations = list(set(recommendations))
            return unique_recommendations[:8]  # Limit to 8 most important
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["Continue seguindo as orientações médicas e mantenha comunicação regular com sua equipe de saúde"]


class QuizReportGenerator:
    """Service for generating medical reports from quiz analysis."""
    
    def __init__(self, db: Session):
        self.db = db
        self.report_repo = ReportRepository(db)
        self.patient_repo = PatientRepository(db)
        self.pdf_generator = PDFGenerator()
        self.response_processor = QuizResponseProcessor(db)
    
    async def generate_quiz_report(self, session_id: UUID) -> UUID:
        """
        Generate comprehensive medical report from quiz session.
        
        Args:
            session_id: Quiz session ID
            
        Returns:
            Generated report ID
        """
        try:
            logger.info(f"Generating quiz report for session {session_id}")
            
            # Process quiz analysis
            analysis_result = await self.response_processor.process_completed_quiz(session_id)
            
            # Get patient information
            patient = self.patient_repo.get(analysis_result.patient_id)
            if not patient:
                raise NotFoundError(f"Patient {analysis_result.patient_id} not found")
            
            # Generate report content
            report_content = await self._generate_report_content(analysis_result, patient)
            
            # Generate PDF
            pdf_data = await self._generate_pdf_report(analysis_result, patient, report_content)
            
            # Create report record
            report = Report(
                patient_id=analysis_result.patient_id,
                type=ReportType.QUIZ_ANALYSIS,
                title=f"Análise de Questionário - {datetime.now().strftime('%d/%m/%Y')}",
                content=report_content,
                pdf_data=pdf_data,
                status=ReportStatus.COMPLETED,
                generated_at=datetime.utcnow(),
                metadata={
                    "quiz_session_id": str(session_id),
                    "analysis_timestamp": analysis_result.analysis_timestamp.isoformat(),
                    "health_score": analysis_result.overall_health_score,
                    "concern_flags": analysis_result.concern_flags,
                    "insights_count": len(analysis_result.medical_insights)
                }
            )
            
            created_report = self.report_repo.create(report)
            self.db.commit()
            
            # Publish WebSocket event
            await websocket_events.publish_report_event(
                event_type=WebSocketEventType.REPORT_GENERATED,
                patient_id=analysis_result.patient_id,
                report_id=created_report.id,
                report_type=ReportType.QUIZ_ANALYSIS.value,
                title=created_report.title
            )
            
            # Notify healthcare providers if concerns identified
            if analysis_result.concern_flags:
                await self._notify_healthcare_providers(created_report, analysis_result)
            
            logger.info(f"Quiz report generated successfully: {created_report.id}")
            return created_report.id
            
        except Exception as e:
            logger.error(f"Error generating quiz report: {e}")
            raise
    
    async def _generate_report_content(self, 
                                     analysis_result: QuizAnalysisResult,
                                     patient: Patient) -> dict[str, Any]:
        """Generate structured report content."""
        try:
            content = {
                "patient_info": {
                    "name": patient.name,
                    "age": getattr(patient, 'age', None),
                    "treatment_type": getattr(patient, 'treatment_type', 'Terapia hormonal'),
                    "enrollment_date": patient.enrollment_date.isoformat() if patient.enrollment_date else None
                },
                "quiz_metrics": {
                    "completion_date": analysis_result.metrics.completion_date.isoformat(),
                    "completion_rate": analysis_result.metrics.completion_rate,
                    "total_questions": analysis_result.metrics.total_questions,
                    "answered_questions": analysis_result.metrics.answered_questions,
                    "response_quality_score": analysis_result.metrics.response_quality_score,
                    "average_response_time": analysis_result.metrics.average_response_time
                },
                "health_assessment": {
                    "overall_health_score": analysis_result.overall_health_score,
                    "concern_flags": analysis_result.concern_flags,
                    "recommendations": analysis_result.recommendations
                },
                "medical_insights": [
                    {
                        "type": insight.insight_type,
                        "description": insight.description,
                        "concern_level": insight.concern_level.value,
                        "recommendations": insight.recommendations,
                        "confidence_score": insight.confidence_score
                    }
                    for insight in analysis_result.medical_insights
                ],
                "response_trends": [
                    {
                        "question_id": trend.question_id,
                        "question_text": trend.question_text,
                        "current_value": trend.current_value,
                        "trend_direction": trend.trend_direction.value,
                        "change_percentage": trend.change_percentage,
                        "significance_score": trend.significance_score
                    }
                    for trend in analysis_result.response_trends
                ],
                "analysis_metadata": {
                    "analysis_timestamp": analysis_result.analysis_timestamp.isoformat(),
                    "session_id": str(analysis_result.session_id)
                }
            }
            
            return content
            
        except Exception as e:
            logger.error(f"Error generating report content: {e}")
            raise
    
    async def _generate_pdf_report(self, 
                                 analysis_result: QuizAnalysisResult,
                                 patient: Patient,
                                 content: dict[str, Any]) -> bytes:
        """Generate PDF report."""
        try:
            # Prepare data for PDF generation
            pdf_data = {
                "title": f"Relatório de Análise de Questionário - {patient.name}",
                "subtitle": f"Data: {analysis_result.metrics.completion_date.strftime('%d/%m/%Y')}",
                "patient_name": patient.name,
                "health_score": analysis_result.overall_health_score,
                "insights": analysis_result.medical_insights,
                "trends": analysis_result.response_trends,
                "recommendations": analysis_result.recommendations,
                "concern_flags": analysis_result.concern_flags,
                "metrics": analysis_result.metrics
            }
            
            # Generate PDF using PDF generator service
            pdf_bytes = await self.pdf_generator.generate_quiz_report(pdf_data)
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            raise
    
    async def _notify_healthcare_providers(self, 
                                         report: Report,
                                         analysis_result: QuizAnalysisResult):
        """Notify healthcare providers about concerning findings."""
        try:
            # Determine notification priority
            priority = "normal"
            if "critical_medical_concerns" in analysis_result.concern_flags:
                priority = "critical"
            elif "high_concern_indicators" in analysis_result.concern_flags:
                priority = "high"
            
            # Create notification data
            notification_data = {
                "patient_id": str(analysis_result.patient_id),
                "report_id": str(report.id),
                "concern_flags": analysis_result.concern_flags,
                "health_score": analysis_result.overall_health_score,
                "priority": priority,
                "summary": f"Questionário completado com {len(analysis_result.concern_flags)} indicadores de atenção"
            }
            
            # Publish notification event
            await websocket_events.publish_alert_event(
                event_type=WebSocketEventType.ALERT_CREATED,
                patient_id=analysis_result.patient_id,
                alert_type="quiz_concerns",
                priority=priority,
                message=notification_data["summary"],
                metadata=notification_data
            )
            
            logger.info(f"Healthcare providers notified about quiz concerns for patient {analysis_result.patient_id}")
            
        except Exception as e:
            logger.error(f"Error notifying healthcare providers: {e}")


def get_quiz_response_processor(db: Session) -> QuizResponseProcessor:
    """Get quiz response processor instance."""
    return QuizResponseProcessor(db)


def get_quiz_report_generator(db: Session) -> QuizReportGenerator:
    """Get quiz report generator instance."""
    return QuizReportGenerator(db)