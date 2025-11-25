"""
Quiz Cleanup Tasks.

Handles expired quiz session cleanup and flow resumption.
"""

import logging
from typing import Any
from uuid import UUID
from datetime import datetime, timezone
from celery import current_app as celery_app
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def cleanup_expired_quiz_sessions_task(self, max_age_hours: int = 48) -> dict[str, Any]:
    """
    Clean up expired quiz sessions that were never completed.

    HIGH-004: Implements timeout and cleanup for abandoned quiz sessions.
    - Marks sessions as 'expired' after expiration_date
    - Sends notifications to doctors about expired sessions
    - Triggers flow resumption for affected patients

    Args:
        max_age_hours (int, optional): Maximum age in hours for incomplete sessions. Defaults to 48.

    Returns:
        dict[str, Any]: Dictionary with cleanup results containing:
            - success: Whether cleanup succeeded
            - cleaned_sessions: Number of sessions marked as expired
            - notifications_sent: Number of doctor notifications sent
            - flows_resumed: Number of patient flows resumed
            - errors: Number of errors encountered
            - session_details: List of expired session details

    Raises:
        Exception: If cleanup fails after all retries
    """
    try:
        with next(get_db()) as db:
            from app.models.quiz import QuizSession
            from app.models.patient import Patient

            current_time = datetime.now(timezone.utc)

            # Query sessions that are expired
            expired_sessions = db.query(QuizSession).filter(
                QuizSession.status == 'started',
                QuizSession.expiration_date.isnot(None),
                QuizSession.expiration_date <= current_time
            ).all()

            cleanup_count = 0
            notifications_sent = 0
            flows_resumed = 0
            errors = 0
            session_details = []

            for session in expired_sessions:
                try:
                    # Get patient info for notification
                    patient = db.query(Patient).filter(Patient.id == session.patient_id).first()

                    # Mark session as expired (SQLAlchemy handles Column[T] to T conversion)
                    session.status = 'expired'  # type: ignore[assignment]
                    session.completed_at = current_time  # type: ignore[assignment]

                    # Update session metadata with expiration info
                    if session.session_metadata is None:
                        session.session_metadata = {}
                    session.session_metadata.update({
                        'expired_at': current_time.isoformat(),
                        'expiration_reason': 'timeout',
                        'original_expiration_date': session.expiration_date.isoformat() if session.expiration_date else None,
                        'questions_answered': session.answered_questions or 0,
                        'total_questions': session.total_questions or 0
                    })

                    cleanup_count += 1

                    # Notify doctor about expired session
                    notification_sent = _notify_doctor_of_expired_session(
                        db=db,
                        session=session,
                        patient=patient
                    )

                    if notification_sent:
                        notifications_sent += 1

                    # Resume patient flow (SQLAlchemy Column[UUID] converts to UUID at runtime)
                    flow_resumed = _resume_patient_flow_after_expiration(
                        db=db,
                        patient_id=session.patient_id,  # type: ignore[arg-type]
                        quiz_session_id=session.id  # type: ignore[arg-type]
                    )

                    if flow_resumed:
                        flows_resumed += 1

                    # Track session details
                    session_details.append({
                        'session_id': str(session.id),
                        'patient_id': str(session.patient_id),
                        'patient_name': f"{patient.first_name} {patient.last_name}" if patient else "Unknown",
                        'started_at': session.started_at.isoformat(),
                        'expired_at': current_time.isoformat(),
                        'questions_answered': session.answered_questions or 0,
                        'notification_sent': notification_sent,
                        'flow_resumed': flow_resumed
                    })

                except Exception as e:
                    logger.error(f"Error cleaning up session {session.id}: {e}", exc_info=True)
                    errors += 1
                    session_details.append({
                        'session_id': str(session.id),
                        'error': str(e)
                    })

            db.commit()

            logger.info(
                f"Quiz session cleanup completed: {cleanup_count} sessions expired, "
                f"{notifications_sent} notifications sent, {flows_resumed} flows resumed, "
                f"{errors} errors"
            )

            return {
                "success": True,
                "cleaned_sessions": cleanup_count,
                "notifications_sent": notifications_sent,
                "flows_resumed": flows_resumed,
                "errors": errors,
                "session_details": session_details
            }

    except Exception as exc:
        logger.error(f"Error in cleanup_expired_quiz_sessions_task: {exc}", exc_info=True)

        if self.request.retries < self.max_retries:
            delay = 60 * (self.request.retries + 1)
            raise self.retry(countdown=delay, exc=exc)
        else:
            logger.error(f"Quiz cleanup failed after {self.max_retries} retries: {exc}")
            return {"success": False, "error": str(exc), "final_failure": True}


def _notify_doctor_of_expired_session(db: Session, session, patient) -> bool:
    """
    Notify doctor about an expired quiz session.

    Args:
        db: Database session
        session: QuizSession instance
        patient: Patient instance

    Returns:
        bool: True if notification was sent successfully
    """
    try:
        # Use consolidated alert system (QW-020: Legacy alert system archived)
        try:
            from app.services.alerts import AlertManagerAdapter
            alert_service = AlertManagerAdapter(db)
        except ImportError:
            from app.services.alert import AlertService
            alert_service = AlertService(db)

        # Create alert for healthcare providers
        patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Unknown Patient"
        questions_answered = session.answered_questions or 0
        total_questions = session.total_questions or 0
        completion_rate = (questions_answered / total_questions * 100) if total_questions > 0 else 0

        alert_data = {
            "patient_id": session.patient_id,
            "alert_type": "quiz_expired",
            "priority": "medium",
            "title": "Quiz Session Expired",
            "message": (
                f"Quiz session for {patient_name} has expired without completion. "
                f"Patient answered {questions_answered} of {total_questions} questions ({completion_rate:.0f}%). "
                f"Session started at {session.started_at.strftime('%Y-%m-%d %H:%M')}."
            ),
            "metadata": {
                "quiz_session_id": str(session.id),
                "quiz_template_id": str(session.quiz_template_id),
                "started_at": session.started_at.isoformat(),
                "expired_at": datetime.now(timezone.utc).isoformat(),
                "questions_answered": questions_answered,
                "total_questions": total_questions,
                "completion_rate": completion_rate,
                "requires_follow_up": completion_rate < 50  # Flag for follow-up if less than 50% complete
            }
        }

        alert_service.create_alert(alert_data)  # type: ignore[attr-defined]
        logger.info(f"Doctor notification sent for expired session {session.id}")
        return True

    except Exception as e:
        logger.error(f"Failed to notify doctor about expired session {session.id}: {e}")
        return False


def _resume_patient_flow_after_expiration(db: Session, patient_id: UUID, quiz_session_id: UUID) -> bool:
    """
    Resume patient flow after quiz session expires.

    Args:
        db: Database session
        patient_id: Patient UUID
        quiz_session_id: QuizSession UUID

    Returns:
        bool: True if flow was resumed successfully
    """
    try:
        from app.models.flow import PatientFlowState

        # Get patient's flow state
        flow_state = db.query(PatientFlowState).filter(
            PatientFlowState.patient_id == patient_id
        ).first()

        if not flow_state:
            logger.warning(f"No flow state found for patient {patient_id}")
            return False

        # Update flow state to resume normal flow
        if flow_state.state_data is None:
            flow_state.state_data = {}

        flow_state.state_data.update({
            'quiz_expired': True,
            'expired_quiz_session_id': str(quiz_session_id),
            'flow_resumed_at': datetime.now(timezone.utc).isoformat(),
            'waiting_for_quiz': False  # Clear quiz waiting flag
        })

        # Mark flow as ready to continue
        flow_state.last_message_at = datetime.now(timezone.utc)

        db.flush()
        logger.info(f"Patient flow resumed for patient {patient_id} after quiz expiration")
        return True

    except Exception as e:
        logger.error(f"Failed to resume flow for patient {patient_id}: {e}")
        return False
