"""
Quiz Flow Integration Service - Main service for quiz and flow integration.
"""
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.quiz_flow_integration import QuizTriggerService, ConversationalQuizService
from app.services.quiz import QuizTemplateService, QuizSessionService, QuizResponseService
from app.services.enhanced_flow_engine import get_enhanced_flow_engine
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.schemas.quiz import QuizSessionCreate, QuizResponseCreate

logger = logging.getLogger(__name__)


class QuizFlowIntegrationService:
    """
    Main service for integrating quiz functionality with patient flows.
    Coordinates between QuizTriggerService and ConversationalQuizService.
    """
    
    def __init__(self, db: Session):
        """
        Initialize Quiz Flow Integration Service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.quiz_trigger_service = QuizTriggerService(db)
        self.conversational_service = ConversationalQuizService(db)
        self.quiz_template_service = QuizTemplateService(db)
        self.quiz_session_service = QuizSessionService(db)
        self.quiz_response_service = QuizResponseService(db)
        self.flow_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self.flow_engine = get_enhanced_flow_engine(db)
        
        logger.info("QuizFlowIntegrationService initialized")
    
    async def trigger_monthly_quizzes(self, limit: int = 50) -> Dict[str, Any]:
        """
        Check and trigger monthly quizzes for eligible patients.
        
        Args:
            limit: Maximum number of patients to process
            
        Returns:
            Processing results with triggered quizzes
        """
        try:
            logger.info(f"Triggering monthly quizzes for up to {limit} patients")
            
            # Use quiz trigger service to check and trigger quizzes
            results = await self.quiz_trigger_service.check_and_trigger_monthly_quizzes(limit)
            
            # Log results
            logger.info(
                f"Quiz trigger results: {results['quizzes_triggered']} triggered, "
                f"{results['checked_patients']} checked, {len(results['errors'])} errors"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to trigger monthly quizzes: {e}")
            return {
                "error": str(e),
                "checked_patients": 0,
                "quizzes_triggered": 0,
                "errors": [str(e)]
            }
    
    async def process_quiz_response(
        self,
        patient_id: UUID,
        message_content: str,
        message_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Process a quiz response from a patient.
        
        Args:
            patient_id: Patient UUID
            message_content: Response message content
            message_id: Optional message ID for tracking
            
        Returns:
            Processing result with next action
        """
        try:
            logger.info(f"Processing quiz response for patient {patient_id}")
            
            # Use conversational service to process response
            result = await self.conversational_service.process_quiz_response(
                patient_id=patient_id,
                response_text=message_content,
                message_id=message_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process quiz response: {e}")
            return {
                "success": False,
                "error": str(e),
                "action": "error"
            }
    
    async def get_patient_quiz_status(self, patient_id: UUID) -> Dict[str, Any]:
        """
        Get current quiz status for a patient.
        
        Args:
            patient_id: Patient UUID
            
        Returns:
            Quiz status information
        """
        try:
            # Get active quiz session
            active_session = self.quiz_session_service.get_active_session(patient_id)
            
            if not active_session:
                # Check if patient is due for quiz
                flow_state = self.flow_repo.get_active_flow(patient_id)
                if flow_state:
                    is_due, quiz_info = await self.quiz_trigger_service._is_patient_due_for_quiz(
                        flow_state
                    )
                    
                    return {
                        "has_active_quiz": False,
                        "is_due_for_quiz": is_due,
                        "quiz_info": quiz_info if is_due else None,
                        "last_quiz_date": None
                    }
                
                return {
                    "has_active_quiz": False,
                    "is_due_for_quiz": False,
                    "quiz_info": None,
                    "last_quiz_date": None
                }
            
            # Get quiz progress
            total_questions = len(active_session.quiz_template.questions)
            answered_questions = len(active_session.responses)
            progress_percentage = (answered_questions / total_questions * 100) if total_questions > 0 else 0
            
            return {
                "has_active_quiz": True,
                "session_id": str(active_session.id),
                "template_name": active_session.quiz_template.name,
                "started_at": active_session.started_at.isoformat(),
                "progress": {
                    "answered": answered_questions,
                    "total": total_questions,
                    "percentage": round(progress_percentage, 2)
                },
                "current_question_index": active_session.current_question_index,
                "status": active_session.status
            }
            
        except Exception as e:
            logger.error(f"Failed to get quiz status for patient {patient_id}: {e}")
            return {
                "error": str(e),
                "has_active_quiz": False
            }
    
    async def cancel_active_quiz(self, patient_id: UUID) -> bool:
        """
        Cancel active quiz session for a patient.
        
        Args:
            patient_id: Patient UUID
            
        Returns:
            True if cancelled successfully
        """
        try:
            active_session = self.quiz_session_service.get_active_session(patient_id)
            
            if not active_session:
                logger.warning(f"No active quiz session for patient {patient_id}")
                return False
            
            # Update session status
            active_session.status = "cancelled"
            active_session.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Cancelled quiz session {active_session.id} for patient {patient_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel quiz for patient {patient_id}: {e}")
            return False
    
    async def get_quiz_history(
        self,
        patient_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get quiz history for a patient.
        
        Args:
            patient_id: Patient UUID
            limit: Maximum number of sessions to return
            
        Returns:
            List of quiz session summaries
        """
        try:
            sessions = self.quiz_session_service.get_patient_sessions(
                patient_id=patient_id,
                limit=limit
            )
            
            history = []
            for session in sessions:
                total_questions = len(session.quiz_template.questions)
                answered_questions = len(session.responses)
                
                history.append({
                    "session_id": str(session.id),
                    "template_name": session.quiz_template.name,
                    "started_at": session.started_at.isoformat(),
                    "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                    "status": session.status,
                    "progress": {
                        "answered": answered_questions,
                        "total": total_questions,
                        "percentage": round((answered_questions / total_questions * 100), 2) if total_questions > 0 else 0
                    },
                    "score": session.total_score
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get quiz history for patient {patient_id}: {e}")
            return []
    
    async def sync_quiz_templates(self) -> Dict[str, str]:
        """
        Synchronize quiz templates from YAML files to database.
        
        Returns:
            Synchronization results
        """
        try:
            from app.services.quiz_template_loader import QuizTemplateLoader
            
            loader = QuizTemplateLoader()
            templates = loader.load_all_quiz_templates()
            
            results = {}
            
            for template_name, template_data in templates.items():
                try:
                    # Check if template exists
                    existing = self.quiz_template_service.get_by_name(template_name)
                    
                    if existing:
                        # Update existing template
                        existing.version = template_data.get("version", "1.0.0")
                        existing.description = template_data.get("description", "")
                        existing.questions = template_data.get("questions", [])
                        existing.is_active = template_data.get("is_active", True)
                        self.db.commit()
                        results[template_name] = "updated"
                    else:
                        # Create new template
                        self.quiz_template_service.create_template(
                            name=template_name,
                            version=template_data.get("version", "1.0.0"),
                            description=template_data.get("description", ""),
                            questions=template_data.get("questions", []),
                            is_active=template_data.get("is_active", True)
                        )
                        results[template_name] = "created"
                        
                except Exception as e:
                    results[template_name] = f"error: {str(e)}"
            
            logger.info(f"Quiz template sync results: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to sync quiz templates: {e}")
            return {"error": str(e)}
    
    async def restart_quiz_session(self, patient_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Restart a quiz session for a patient (cancel current and start new).
        
        Args:
            patient_id: Patient UUID
            
        Returns:
            New session info if created
        """
        try:
            # Cancel active session if exists
            await self.cancel_active_quiz(patient_id)
            
            # Get flow state
            flow_state = self.flow_repo.get_active_flow(patient_id)
            if not flow_state:
                logger.warning(f"No active flow for patient {patient_id}")
                return None
            
            # Check if due for quiz
            is_due, quiz_info = await self.quiz_trigger_service._is_patient_due_for_quiz(flow_state)
            
            if not is_due:
                logger.info(f"Patient {patient_id} not due for quiz")
                return None
            
            # Trigger new quiz
            result = await self.quiz_trigger_service._trigger_patient_quiz(flow_state, quiz_info)
            
            if result["success"]:
                return {
                    "success": True,
                    "session_id": result.get("session_id"),
                    "template_name": quiz_info["template_name"],
                    "message": "Quiz session restarted successfully"
                }
            
            return {
                "success": False,
                "error": result.get("error", "Failed to restart quiz")
            }
            
        except Exception as e:
            logger.error(f"Failed to restart quiz for patient {patient_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Global instance getter
_quiz_flow_integration_service: Optional[QuizFlowIntegrationService] = None


def get_quiz_flow_integration_service(db: Session) -> QuizFlowIntegrationService:
    """
    Get or create quiz flow integration service instance.
    
    Args:
        db: Database session
        
    Returns:
        QuizFlowIntegrationService instance
    """
    global _quiz_flow_integration_service
    
    if _quiz_flow_integration_service is None:
        _quiz_flow_integration_service = QuizFlowIntegrationService(db)
    
    return _quiz_flow_integration_service