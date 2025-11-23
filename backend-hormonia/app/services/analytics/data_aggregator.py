"""
Data aggregation service for medical reports.
Compiles patient data from multiple sources for report generation.
"""
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import  joinedload
from sqlalchemy import func, and_, or_

from app.models.patient import Patient
from app.models.message import Message, MessageDirection, MessageStatus
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.models.report import MedicalReport
from app.models.alert import Alert
from app.models.user import User
from app.repositories.patient import PatientRepository
from app.repositories.message import MessageRepository
from app.repositories.quiz import QuizResponseRepository
from app.repositories.alert import AlertRepository
from app.schemas.report import PatientAnalytics, SystemAnalytics
from app.utils.db_retry import with_db_retry


logger = logging.getLogger(__name__)


class DataAggregationError(Exception):
    """Data aggregation specific error."""
    pass


class DataAggregator:
    """
    Data aggregation service for medical reports.
    
    Compiles patient data from multiple sources including messages,
    quiz responses, alerts, and treatment information.
    """
    
    def __init__(self, db: Any):
        """Initialize data aggregator with database session."""
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.message_repo = MessageRepository(db)
        self.quiz_repo = QuizResponseRepository(db)
        self.alert_repo = AlertRepository(db)
        
        logger.info("Data aggregator initialized")
    
    @with_db_retry(max_retries=3)
    def get_patient_data_summary(
        self,
        patient_id: UUID,
        period_start: date,
        period_end: date
    ) -> dict[str, Any]:
        """
        Get comprehensive patient data summary for report period.
        
        Args:
            patient_id: Patient ID
            period_start: Start date for data collection
            period_end: End date for data collection
            
        Returns:
            Dictionary containing patient data summary
            
        Raises:
            DataAggregationError: On data collection failures
        """
        try:
            logger.info(f"Aggregating data for patient {patient_id} from {period_start} to {period_end}")
            
            # Get patient basic info with eager-loaded doctor to prevent N+1 query
            # OPTIMIZATION: Use joinedload to load doctor in same query
            patient = (
                self.db.query(Patient)
                .options(joinedload(Patient.doctor))
                .filter(Patient.id == patient_id)
                .first()
            )
            if not patient:
                raise DataAggregationError(f"Patient {patient_id} not found")

            # Doctor is already loaded via joinedload
            doctor = patient.doctor
            
            # Aggregate data from different sources
            message_data = self._aggregate_message_data(patient_id, period_start, period_end)
            quiz_data = self._aggregate_quiz_data(patient_id, period_start, period_end)
            alert_data = self._aggregate_alert_data(patient_id, period_start, period_end)
            treatment_data = self._aggregate_treatment_data(patient, period_start, period_end)
            
            summary = {
                # Patient info
                "patient_id": str(patient_id),
                "patient_name": patient.name,
                "patient_phone": patient.phone,
                "patient_email": patient.email,
                "doctor_name": doctor.full_name if doctor else "Unknown",
                "doctor_id": str(patient.doctor_id),
                
                # Period info
                "period_start": period_start,
                "period_end": period_end,
                "period_days": (period_end - period_start).days + 1,
                
                # Treatment info
                "treatment_type": patient.treatment_type,
                "treatment_start_date": patient.treatment_start_date,
                "current_day": patient.current_day,
                "flow_state": patient.flow_state.value if patient.flow_state else None,
                
                # Aggregated data
                "message_data": message_data,
                "quiz_data": quiz_data,
                "alert_data": alert_data,
                "treatment_data": treatment_data,
                
                # Generated timestamp
                "generated_at": datetime.utcnow()
            }
            
            logger.info(f"Successfully aggregated data for patient {patient_id}")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to aggregate patient data: {e}")
            raise DataAggregationError(f"Data aggregation failed: {str(e)}")
    
    def _aggregate_message_data(
        self,
        patient_id: UUID,
        period_start: date,
        period_end: date
    ) -> dict[str, Any]:
        """Aggregate message data for the patient."""
        try:
            # Convert dates to datetime for filtering
            start_datetime = datetime.combine(period_start, datetime.min.time())
            end_datetime = datetime.combine(period_end, datetime.max.time())
            
            # Get all messages in period
            messages = (
                self.db.query(Message)
                .filter(
                    Message.patient_id == patient_id,
                    Message.created_at >= start_datetime,
                    Message.created_at <= end_datetime
                )
                .all()
            )
            
            # Calculate statistics
            total_messages = len(messages)
            outbound_messages = [m for m in messages if m.direction == MessageDirection.OUTBOUND]
            inbound_messages = [m for m in messages if m.direction == MessageDirection.INBOUND]
            
            # Response rate calculation
            response_rate = 0.0
            if outbound_messages:
                responses = len(inbound_messages)
                response_rate = (responses / len(outbound_messages)) * 100
            
            # Average response time calculation
            avg_response_time_hours = None
            response_times = []
            
            for outbound in outbound_messages:
                # Find next inbound message after this outbound
                next_inbound = next(
                    (m for m in inbound_messages if m.created_at > outbound.created_at),
                    None
                )
                if next_inbound:
                    response_time = (next_inbound.created_at - outbound.created_at).total_seconds() / 3600
                    response_times.append(response_time)
            
            if response_times:
                avg_response_time_hours = sum(response_times) / len(response_times)
            
            # Message status distribution
            status_distribution = {}
            for status in MessageStatus:
                count = len([m for m in messages if m.status == status])
                status_distribution[status.value] = count
            
            # Daily message counts
            daily_counts = {}
            for message in messages:
                day = message.created_at.date()
                daily_counts[str(day)] = daily_counts.get(str(day), 0) + 1
            
            return {
                "total_messages": total_messages,
                "outbound_messages": len(outbound_messages),
                "inbound_messages": len(inbound_messages),
                "response_rate": round(response_rate, 2),
                "avg_response_time_hours": round(avg_response_time_hours, 2) if avg_response_time_hours else None,
                "status_distribution": status_distribution,
                "daily_counts": daily_counts,
                "most_active_day": max(daily_counts.items(), key=lambda x: x[1])[0] if daily_counts else None
            }
            
        except Exception as e:
            logger.error(f"Failed to aggregate message data: {e}")
            return {}
    
    def _aggregate_quiz_data(
        self,
        patient_id: UUID,
        period_start: date,
        period_end: date
    ) -> dict[str, Any]:
        """Aggregate quiz data for the patient."""
        try:
            # Convert dates to datetime for filtering
            start_datetime = datetime.combine(period_start, datetime.min.time())
            end_datetime = datetime.combine(period_end, datetime.max.time())
            
            # Get quiz responses in period
            responses = (
                self.db.query(QuizResponse)
                .filter(
                    QuizResponse.patient_id == patient_id,
                    QuizResponse.responded_at >= start_datetime,
                    QuizResponse.responded_at <= end_datetime
                )
                .all()
            )
            
            # Get quiz sessions in period
            sessions = (
                self.db.query(QuizSession)
                .filter(
                    QuizSession.patient_id == patient_id,
                    QuizSession.started_at >= start_datetime,
                    QuizSession.started_at <= end_datetime
                )
                .all()
            )
            
            # Calculate statistics
            total_responses = len(responses)
            completed_sessions = len([s for s in sessions if s.status == 'completed'])
            total_sessions = len(sessions)
            
            completion_rate = 0.0
            if total_sessions > 0:
                completion_rate = (completed_sessions / total_sessions) * 100
            
            # Group responses by quiz template
            responses_by_template = {}
            for response in responses:
                template_id = str(response.quiz_template_id)
                if template_id not in responses_by_template:
                    responses_by_template[template_id] = []
                responses_by_template[template_id].append(response)
            
            # Calculate average scores (if numeric responses exist)
            avg_scores = {}
            for template_id, template_responses in responses_by_template.items():
                numeric_responses = []
                for resp in template_responses:
                    try:
                        # Try to extract numeric value from response
                        if resp.response_type == 'scale':
                            numeric_responses.append(float(resp.response_value))
                    except (ValueError, TypeError):
                        continue
                
                if numeric_responses:
                    avg_scores[template_id] = sum(numeric_responses) / len(numeric_responses)
            
            # Recent quiz responses for report
            recent_responses = []
            for response in responses[-10:]:  # Last 10 responses
                template = self.db.query(QuizTemplate).filter(
                    QuizTemplate.id == response.quiz_template_id
                ).first()
                
                recent_responses.append({
                    "date": response.responded_at.strftime("%Y-%m-%d"),
                    "quiz_type": template.name if template else "Unknown",
                    "question": response.question_text[:100] + "..." if len(response.question_text) > 100 else response.question_text,
                    "response": response.response_value[:100] + "..." if len(response.response_value) > 100 else response.response_value,
                    "response_type": response.response_type
                })
            
            return {
                "total_responses": total_responses,
                "completed_sessions": completed_sessions,
                "total_sessions": total_sessions,
                "completion_rate": round(completion_rate, 2),
                "responses_by_template": {k: len(v) for k, v in responses_by_template.items()},
                "avg_scores": {k: round(v, 2) for k, v in avg_scores.items()},
                "recent_responses": recent_responses
            }
            
        except Exception as e:
            logger.error(f"Failed to aggregate quiz data: {e}")
            return {}
    
    def _aggregate_alert_data(
        self,
        patient_id: UUID,
        period_start: date,
        period_end: date
    ) -> dict[str, Any]:
        """Aggregate alert data for the patient."""
        try:
            # Convert dates to datetime for filtering
            start_datetime = datetime.combine(period_start, datetime.min.time())
            end_datetime = datetime.combine(period_end, datetime.max.time())
            
            # Get alerts in period
            alerts = (
                self.db.query(Alert)
                .filter(
                    Alert.patient_id == patient_id,
                    Alert.created_at >= start_datetime,
                    Alert.created_at <= end_datetime
                )
                .all()
            )
            
            # Calculate statistics
            total_alerts = len(alerts)
            
            # Group by severity
            severity_counts = {}
            for alert in alerts:
                severity = alert.severity.value if alert.severity else 'unknown'
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Group by type
            type_counts = {}
            for alert in alerts:
                alert_type = alert.alert_type or 'unknown'
                type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
            
            # Recent alerts for report
            recent_alerts = []
            for alert in alerts[-5:]:  # Last 5 alerts
                recent_alerts.append({
                    "date": alert.created_at.strftime("%Y-%m-%d %H:%M"),
                    "severity": alert.severity.value if alert.severity else "unknown",
                    "type": alert.alert_type or "unknown",
                    "description": alert.description[:100] + "..." if len(alert.description) > 100 else alert.description,
                    "status": alert.status.value if alert.status else "unknown"
                })
            
            return {
                "total_alerts": total_alerts,
                "severity_counts": severity_counts,
                "type_counts": type_counts,
                "recent_alerts": recent_alerts,
                "high_priority_count": severity_counts.get('high', 0) + severity_counts.get('critical', 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to aggregate alert data: {e}")
            return {}
    
    def _aggregate_treatment_data(
        self,
        patient: Patient,
        period_start: date,
        period_end: date
    ) -> dict[str, Any]:
        """Aggregate treatment-related data for the patient."""
        try:
            # Calculate treatment duration
            treatment_duration_days = None
            if patient.treatment_start_date:
                treatment_duration_days = (period_end - patient.treatment_start_date).days
            
            # Calculate period progress
            period_duration = (period_end - period_start).days + 1
            
            # Extract relevant metadata
            metadata = patient.patient_metadata or {}
            
            return {
                "treatment_type": patient.treatment_type,
                "treatment_start_date": patient.treatment_start_date.isoformat() if patient.treatment_start_date else None,
                "treatment_duration_days": treatment_duration_days,
                "current_day": patient.current_day,
                "flow_state": patient.flow_state.value if patient.flow_state else None,
                "period_duration_days": period_duration,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to aggregate treatment data: {e}")
            return {}
    
    @with_db_retry(max_retries=3)
    def get_patient_analytics(
        self,
        patient_id: UUID,
        days_back: int = 30
    ) -> PatientAnalytics:
        """
        Get patient analytics for dashboard/reporting.

        OPTIMIZATION: Added eager loading for doctor relationship.

        Args:
            patient_id: Patient ID
            days_back: Number of days to look back for analytics

        Returns:
            PatientAnalytics object
        """
        try:
            # Get patient with eager-loaded doctor
            patient = (
                self.db.query(Patient)
                .options(joinedload(Patient.doctor))
                .filter(Patient.id == patient_id)
                .first()
            )
            if not patient:
                raise DataAggregationError(f"Patient {patient_id} not found")
            
            # Calculate date range
            end_date = date.today()
            start_date = end_date - timedelta(days=days_back)
            
            # Get aggregated data
            data_summary = self.get_patient_data_summary(patient_id, start_date, end_date)
            
            # Extract analytics
            message_data = data_summary.get("message_data", {})
            quiz_data = data_summary.get("quiz_data", {})
            alert_data = data_summary.get("alert_data", {})
            
            return PatientAnalytics(
                patient_id=patient_id,
                patient_name=patient.name,
                treatment_type=patient.treatment_type,
                current_day=patient.current_day,
                total_messages_sent=message_data.get("outbound_messages", 0),
                total_messages_received=message_data.get("inbound_messages", 0),
                response_rate=message_data.get("response_rate", 0.0),
                avg_response_time_hours=message_data.get("avg_response_time_hours"),
                quizzes_completed=quiz_data.get("completed_sessions", 0),
                quiz_completion_rate=quiz_data.get("completion_rate", 0.0),
                total_alerts=alert_data.get("total_alerts", 0),
                high_priority_alerts=alert_data.get("high_priority_count", 0)
            )
            
        except Exception as e:
            logger.error(f"Failed to get patient analytics: {e}")
            raise DataAggregationError(f"Patient analytics failed: {str(e)}")
    
    @with_db_retry(max_retries=3)
    def get_system_analytics(self) -> SystemAnalytics:
        """
        Get system-wide analytics.
        
        Returns:
            SystemAnalytics object
        """
        try:
            # Get basic counts
            total_patients = self.db.query(Patient).count()
            active_patients = self.db.query(Patient).filter(
                Patient.flow_state.in_(['active', 'onboarding'])
            ).count()
            total_doctors = self.db.query(User).filter(User.role == 'doctor').count()
            
            # Get today's date range
            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())
            
            # Get week date range
            week_start = today_start - timedelta(days=7)
            
            # Get month date range
            month_start = today_start - timedelta(days=30)
            
            # Message counts
            messages_today = self.db.query(Message).filter(
                Message.created_at >= today_start,
                Message.created_at <= today_end
            ).count()
            
            messages_week = self.db.query(Message).filter(
                Message.created_at >= week_start
            ).count()
            
            messages_month = self.db.query(Message).filter(
                Message.created_at >= month_start
            ).count()
            
            # Quiz counts
            quizzes_today = self.db.query(QuizSession).filter(
                QuizSession.completed_at >= today_start,
                QuizSession.completed_at <= today_end,
                QuizSession.status == 'completed'
            ).count()
            
            quizzes_week = self.db.query(QuizSession).filter(
                QuizSession.completed_at >= week_start,
                QuizSession.status == 'completed'
            ).count()
            
            # Alert counts
            alerts_today = self.db.query(Alert).filter(
                Alert.created_at >= today_start,
                Alert.created_at <= today_end
            ).count()
            
            unresolved_alerts = self.db.query(Alert).filter(
                Alert.status.in_(['pending', 'acknowledged'])
            ).count()
            
            return SystemAnalytics(
                total_patients=total_patients,
                active_patients=active_patients,
                total_doctors=total_doctors,
                total_messages_today=messages_today,
                total_messages_week=messages_week,
                total_messages_month=messages_month,
                quizzes_completed_today=quizzes_today,
                quizzes_completed_week=quizzes_week,
                alerts_generated_today=alerts_today,
                unresolved_alerts=unresolved_alerts,
                avg_response_time_ms=0.0,  # Would need performance monitoring
                system_uptime_hours=0.0    # Would need system monitoring
            )
            
        except Exception as e:
            logger.error(f"Failed to get system analytics: {e}")
            raise DataAggregationError(f"System analytics failed: {str(e)}")
