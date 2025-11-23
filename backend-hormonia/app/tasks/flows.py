"""
Celery tasks for flow processing with Redis broker integration.
"""
import asyncio
import logging
from typing import Any, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
from celery import Task
from celery.exceptions import Retry, MaxRetriesExceededError
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import get_db
from app.services.enhanced_flow_engine import get_enhanced_flow_engine, FlowType, MessageTemplate
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.repositories.message import MessageRepository
from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.models.flow import PatientFlowState
from app.exceptions import NotFoundError, ValidationError
from app.integrations.gemini_client import get_gemini_client
from app.services.conversation_memory import get_conversation_memory

logger = logging.getLogger(__name__)


def send_critical_alert_sync(task_name: str, error: str, context: dict = None):
    """
    Helper to send critical alerts synchronously from Celery tasks.
    Uses AlertManager to process the alert.
    """
    try:
        from app.services.alerts import get_alert_manager, AlertRuleType, AlertSeverity, Alert
        
        # Create alert object
        alert = Alert(
            severity=AlertSeverity.CRITICAL,
            rule_type=AlertRuleType.CUSTOM,
            message=f"Critical failure in task {task_name}: {error}",
            context=context or {},
            timestamp=datetime.utcnow()
        )
        
        # Get manager and process
        # Note: AlertManager methods are async, so we need to run them in a loop
        # But since we are in a sync Celery task (or one that might be sync), 
        # we need to be careful about the event loop.
        
        manager = get_alert_manager()
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            # If loop is running, we can't use run_until_complete
            # This happens if the task is async but called synchronously?
            # For safety in Celery, we usually want a fresh loop if possible or use thread pool
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(manager.process_alert(alert))
                )
                future.result(timeout=10)
        else:
            loop.run_until_complete(manager.process_alert(alert))
            
    except Exception as e:
        logger.error(f"Failed to send critical alert for {task_name}: {e}")


class FlowTaskBase(Task):
    """Base class for flow tasks with Redis tracking."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Flow task {task_id} completed successfully: {retval}")
        # Store success in Redis for monitoring
        self._store_task_result(task_id, "success", retval)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Flow task {task_id} failed: {exc}")
        # Store failure in Redis for monitoring
        self._store_task_result(task_id, "failure", {"error": str(exc), "traceback": str(einfo)})
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        logger.warning(f"Flow task {task_id} retrying: {exc}")
        # Store retry in Redis for monitoring
        self._store_task_result(task_id, "retry", {"error": str(exc), "attempt": self.request.retries + 1})
    
    def _store_task_result(self, task_id: str, status: str, data: Any):
        """Store task result in Redis for monitoring using synchronous operations."""
        try:
            import redis
            import json
            from app.config import settings

            # Use synchronous Redis client for Celery task context
            from app.config.settings.tasks import REDIS_SOCKET_TIMEOUT, REDIS_SOCKET_CONNECT_TIMEOUT
            redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
                retry_on_timeout=True
            )

            # Store task result with expiration
            result_data = {
                "task_id": task_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            }

            # Use synchronous Redis operations
            from app.config.settings.tasks import REDIS_TASK_RESULT_EXPIRY
            redis_client.setex(
                f"task_result:{task_id}",
                REDIS_TASK_RESULT_EXPIRY,
                json.dumps(result_data)
            )

            redis_client.close()

        except Exception as e:
            logger.error(f"Failed to store task result in Redis: {e}")


async def process_daily_flows_async(limit: int = 100) -> dict[str, Any]:
    """
    Async version that processes flows in parallel batches.

    This function prevents event loop memory leaks by using a single async context
    and processing patients in batches with asyncio.gather().

    Args:
        limit: Maximum number of patients to process

    Returns:
        dict[str, Any]: Processing results containing:
            - processed_count: Number of patients processed
            - success_count: Number of successful processes
            - error_count: Number of failed processes
            - errors: List of errors encountered
            - patients_processed: List of processed patient details
            - start_time: Processing start timestamp
            - end_time: Processing end timestamp
            - duration_seconds: Total processing duration

    Raises:
        Exception: If critical error occurs during processing
    """
    from app.config.settings.tasks import FLOW_BATCH_SIZE, FLOW_PROCESSING_TIMEOUT

    logger.info(f"Starting async daily flow processing for up to {limit} patients")

    # Use async context manager for database
    db = next(get_db())

    try:
        # Initialize services
        flow_engine = get_enhanced_flow_engine(db)
        flow_repo = FlowStateRepository(db)

        # Get active flow states
        active_flows = flow_repo.get_active_flows(limit=limit)

        results = {
            "processed_count": 0,
            "success_count": 0,
            "error_count": 0,
            "errors": [],
            "patients_processed": [],
            "start_time": datetime.utcnow().isoformat()
        }

        # Filter out paused flows
        active_flows = [
            flow for flow in active_flows
            if not (flow.state_data and flow.state_data.get("paused"))
        ]

        logger.info(f"Processing {len(active_flows)} active flows in batches of {FLOW_BATCH_SIZE}")

        # Process in batches for parallel execution
        batch_size = FLOW_BATCH_SIZE

        for i in range(0, len(active_flows), batch_size):
            batch = active_flows[i:i+batch_size]

            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} patients")

            # Create tasks for the batch with timeout
            tasks = [
                asyncio.wait_for(
                    _process_single_patient_flow_safe(flow_engine, flow, db),
                    timeout=FLOW_PROCESSING_TIMEOUT
                )
                for flow in batch
            ]

            # Execute in parallel with exception handling
            batch_results = await asyncio.gather(
                *tasks,
                return_exceptions=True  # Don't fail entire batch if one fails
            )

            # Process results
            for flow, result in zip(batch, batch_results):
                results["processed_count"] += 1

                if isinstance(result, Exception):
                    # Error occurred (including timeout)
                    results["error_count"] += 1
                    error_msg = str(result)

                    if isinstance(result, asyncio.TimeoutError):
                        error_msg = f"Processing timeout after {FLOW_PROCESSING_TIMEOUT}s"

                    results["errors"].append({
                        "patient_id": str(flow.patient_id),
                        "error": error_msg
                    })
                    results["patients_processed"].append({
                        "patient_id": str(flow.patient_id),
                        "status": "error",
                        "error": error_msg
                    })

                    logger.error(f"Flow processing failed for patient {flow.patient_id}: {error_msg}")

                elif result.get("status") == "success":
                    results["success_count"] += 1
                    results["patients_processed"].append({
                        "patient_id": str(flow.patient_id),
                        "status": "success",
                        "result": result
                    })
                else:
                    results["error_count"] += 1
                    results["errors"].append({
                        "patient_id": str(flow.patient_id),
                        "error": result.get("error", "Unknown error")
                    })
                    results["patients_processed"].append({
                        "patient_id": str(flow.patient_id),
                        "status": "error",
                        "result": result
                    })

        results["end_time"] = datetime.utcnow().isoformat()
        results["duration_seconds"] = (
            datetime.fromisoformat(results["end_time"]) -
            datetime.fromisoformat(results["start_time"])
        ).total_seconds()

        logger.info(
            f"Async daily flow processing completed: "
            f"{results['success_count']}/{results['processed_count']} successful "
            f"in {results['duration_seconds']:.2f} seconds"
        )

        return results

    finally:
        db.close()


async def _process_single_patient_flow_safe(
    engine,
    flow_state: PatientFlowState,
    db: Session
) -> dict[str, Any]:
    """
    Process flow for a single patient with error handling and timeout.

    This function wraps the original _process_single_patient_flow with
    additional safety measures to prevent crashes.

    Args:
        engine: Enhanced flow engine instance
        flow_state: Patient flow state object
        db: Database session

    Returns:
        dict[str, Any]: Processing result with status and details
    """
    try:
        result = await _process_single_patient_flow(engine, flow_state)
        return result
    except asyncio.TimeoutError:
        logger.error(f"Flow processing timeout for patient {flow_state.patient_id}")
        return {
            "status": "timeout",
            "patient_id": str(flow_state.patient_id),
            "error": "Processing timeout"
        }
    except Exception as e:
        logger.error(f"Flow processing error for patient {flow_state.patient_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "patient_id": str(flow_state.patient_id),
            "error": str(e)
        }


@celery_app.task(
    bind=True,
    base=FlowTaskBase,
    max_retries=None,  # Set dynamically from settings
    default_retry_delay=None,  # Set dynamically from settings
    time_limit=None,  # Set dynamically from settings
    soft_time_limit=None,  # Set dynamically from settings
)
def process_daily_flows(self, limit: int = 100) -> dict[str, Any]:
    """
    Process daily flows for all active patients using EnhancedFlowEngine.

    This is a wrapper task that delegates to the async implementation to prevent
    event loop memory leaks. Uses asyncio.run() ONCE to create and manage a single
    event loop for the entire batch processing.

    Args:
        limit: Maximum number of patients to process

    Returns:
        dict[str, Any]: Processing results containing:
            - processed_count: Number of patients processed
            - success_count: Number of successful processes
            - error_count: Number of failed processes
            - errors: List of errors encountered
            - patients_processed: List of processed patient details
            - start_time/end_time: Processing timestamps
            - duration_seconds: Total processing time

    Raises:
        MaxRetriesExceededError: If task fails after all retries
    """
    from app.config.settings.tasks import FLOW_MAX_RETRIES, TASK_TIME_LIMIT, TASK_SOFT_TIME_LIMIT

    # Apply task limits from settings if not already set
    if not self.time_limit:
        self.time_limit = TASK_TIME_LIMIT
    if not self.soft_time_limit:
        self.soft_time_limit = TASK_SOFT_TIME_LIMIT
    if not self.max_retries:
        self.max_retries = FLOW_MAX_RETRIES

    try:
        logger.info(f"Starting daily flow processing task for up to {limit} patients")

        # Execute async version ONCE with a single event loop
        results = asyncio.run(process_daily_flows_async(limit))

        return results

    except Exception as e:
        logger.error(f"Daily flow processing failed: {e}", exc_info=True)

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            from app.config.settings.tasks import get_retry_countdown, FLOW_RETRY_DELAY
            retry_delay = get_retry_countdown(self.request.retries, FLOW_RETRY_DELAY)

            logger.warning(
                f"Retrying daily flow processing in {retry_delay} seconds "
                f"(attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(countdown=retry_delay, exc=e)
        else:
            # Max retries reached - alert admin
            logger.error(f"Daily flow processing failed after {self.max_retries} attempts")

            try:
                from app.config.settings.tasks import ENABLE_ADMIN_ALERTS
                if ENABLE_ADMIN_ALERTS:
                    # Use synchronous helper for critical alerts
                    send_critical_alert_sync(
                        task_name="process_daily_flows",
                        error=str(e),
                        context={"retries": self.request.retries, "limit": limit}
                    )
            except Exception as alert_error:
                logger.error(f"Failed to send admin alert: {alert_error}")

            raise MaxRetriesExceededError(f"Task failed after {self.max_retries} retries: {e}")


@celery_app.task(bind=True, base=FlowTaskBase, max_retries=None, default_retry_delay=None)
def send_flow_message(self, patient_id: str, message_data: dict[str, Any], message_id: str = None) -> dict[str, Any]:
    """
    Send individual flow message with retry logic and exponential backoff.

    Args:
        patient_id (str): Patient UUID as string
        message_data (dict[str, Any]): Message data dictionary containing:
            - content: Message content
            - type: Message type
            - flow_day: Current flow day
            - flow_type: Flow type
            - template_id: Template identifier
            - personalized: Whether message is personalized
            - metadata: Additional metadata
        message_id (str, optional): Existing message UUID to update instead of creating new one

    Returns:
        dict[str, Any]: Message sending result containing:
            - status: Success or failure status
            - patient_id: Patient identifier
            - message_id: Message ID (existing or newly created)
            - sent_at: Timestamp when message was sent

    Raises:
        Exception: If message sending fails after all retries
    """
    from app.config.settings.tasks import MESSAGE_MAX_RETRIES, MESSAGE_RETRY_DELAY

    # Apply task limits from settings if not already set
    if not self.max_retries:
        self.max_retries = MESSAGE_MAX_RETRIES
    if not self.default_retry_delay:
        self.default_retry_delay = MESSAGE_RETRY_DELAY

    try:
        logger.info(f"Sending flow message to patient {patient_id}, message_id: {message_id}")

        # Get database session
        db = next(get_db())

        try:
            # Initialize services with QUEUE mode for retry/backoff policies
            from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
            message_sender = UnifiedWhatsAppService(db, messaging_mode=MessagingMode.QUEUE)
            patient_repo = PatientRepository(db)
            message_repo = MessageRepository(db)

            # Get patient
            patient = patient_repo.get(UUID(patient_id))
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            # Get or create message object
            if message_id:
                # UPDATE existing scheduled message
                message = message_repo.get(UUID(message_id))
                if not message:
                    raise NotFoundError(f"Scheduled message {message_id} not found")

                # Validate message state
                if message.status not in [MessageStatus.SCHEDULED, MessageStatus.PENDING]:
                    logger.warning(f"Message {message_id} has unexpected status {message.status}, proceeding anyway")

                # Update message status to SENDING
                message.status = MessageStatus.SENDING
                message.message_metadata["celery_execution_started"] = datetime.utcnow().isoformat()
                message.message_metadata["task_id"] = self.request.id

            else:
                # CREATE new message (backward compatibility for legacy calls)
                logger.warning(f"Creating new message for patient {patient_id} - this may indicate message_id was not passed")
                message = Message(
                    patient_id=UUID(patient_id),
                    direction=MessageDirection.OUTBOUND,
                    type=MessageType(message_data.get("type", "text")),
                    content=message_data.get("content", ""),
                    message_metadata=message_data.get("metadata", {}),
                    status=MessageStatus.SENDING,
                    scheduled_for=datetime.utcnow()
                )

                # Add to database
                db.add(message)

            # Add/update flow context in metadata
            if "flow_context" not in message.message_metadata:
                message.message_metadata["flow_context"] = {}

            message.message_metadata["flow_context"].update({
                "flow_day": message_data.get("flow_day"),
                "flow_type": message_data.get("flow_type"),
                "template_id": message_data.get("template_id"),
                "personalized": message_data.get("personalized", False),
                "sent_via_celery": True,
                "task_id": self.request.id
            })

            # Commit transaction before sending
            db.commit()
            db.refresh(message)
            
            # Send message using proper async handling
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success = loop.run_until_complete(message_sender.send_message(message))
                finally:
                    loop.close()
            except RuntimeError as e:
                if "cannot be called from a running event loop" in str(e):
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        from app.config.settings.tasks import MESSAGE_SEND_TIMEOUT
                        future = executor.submit(
                            lambda: asyncio.run(message_sender.send_message(message))
                        )
                        success = future.result(timeout=MESSAGE_SEND_TIMEOUT)
                else:
                    raise

            # Update message status based on send result
            if success:
                # MessageSender.send_message() already updates status to SENT
                # Just update metadata with final status
                message.message_metadata["celery_execution_completed"] = datetime.utcnow().isoformat()
                message.message_metadata["execution_status"] = "success"
                db.commit()

                logger.info(f"Flow message sent successfully to patient {patient_id}, message_id: {message.id}")
            else:
                # Update status to FAILED
                message.status = MessageStatus.FAILED
                message.message_metadata["celery_execution_completed"] = datetime.utcnow().isoformat()
                message.message_metadata["execution_status"] = "failed"
                message.message_metadata["failure_reason"] = "Message sending failed"
                db.commit()

                logger.error(f"Failed to send flow message to patient {patient_id}, message_id: {message.id}")

            result = {
                "status": "success" if success else "failed",
                "patient_id": patient_id,
                "message_id": str(message.id),
                "sent_at": datetime.utcnow().isoformat(),
                "whatsapp_id": message.whatsapp_id,
                "updated_existing": bool(message_id)
            }

            if not success:
                result["error"] = "Message sending failed"

            return result
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error sending flow message to patient {patient_id}: {e}")

        # Try to mark message as failed if message_id was provided
        if message_id:
            try:
                db = next(get_db())
                try:
                    message_repo = MessageRepository(db)
                    message = message_repo.get(UUID(message_id))
                    if message:
                        message.status = MessageStatus.FAILED
                        message.message_metadata["celery_execution_error"] = str(e)
                        message.message_metadata["celery_execution_failed_at"] = datetime.utcnow().isoformat()
                        message.message_metadata["retry_count"] = self.request.retries
                        db.commit()
                        logger.info(f"Marked message {message_id} as FAILED after exception")
                finally:
                    db.close()
            except Exception as update_error:
                logger.error(f"Failed to update message status after exception: {update_error}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            from app.config.settings.tasks import get_retry_countdown
            retry_delay = get_retry_countdown(self.request.retries, MESSAGE_RETRY_DELAY)
            logger.info(f"Retrying flow message send in {retry_delay} seconds (attempt {self.request.retries + 1})")
            raise self.retry(countdown=retry_delay, exc=e)
        else:
            logger.error(f"Flow message send failed after {self.max_retries} attempts")
            return {
                "status": "failed",
                "patient_id": patient_id,
                "message_id": message_id,
                "error": f"Failed after {self.max_retries} retries: {str(e)}",
                "final_attempt": True
            }


@celery_app.task(bind=True, base=FlowTaskBase)
def cleanup_old_flow_data(self, days_old: int = 90) -> dict[str, Any]:
    """
    Cleanup old flow data for maintenance.
    
    Args:
        days_old: Age threshold for cleanup in days
        
    Returns:
        dict[str, Any]: Cleanup results containing:
            - deleted_flows: Number of deleted flow states
            - deleted_messages: Number of deleted messages
            - deleted_analytics: Number of deleted analytics records
            - cleanup_date: Date of cleanup operation
    
    Raises:
        Exception: If cleanup operation fails
    """
    try:
        logger.info(f"Starting cleanup of flow data older than {days_old} days")
        
        # Get database session
        db = next(get_db())
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Initialize repositories
            flow_repo = FlowStateRepository(db)
            
            results = {
                "completed_flows_cleaned": 0,
                "old_messages_cleaned": 0,
                "analytics_cleaned": 0,
                "cutoff_date": cutoff_date.isoformat(),
                "start_time": datetime.utcnow().isoformat()
            }
            
            # Clean up completed flows older than threshold
            completed_flows = db.query(PatientFlowState).filter(
                PatientFlowState.completed_at < cutoff_date,
                PatientFlowState.completed_at.isnot(None)
            ).all()
            
            for flow in completed_flows:
                # Archive important data before deletion
                archive_data = {
                    "patient_id": str(flow.patient_id),
                    "flow_type": flow.flow_type,
                    "completed_at": flow.completed_at.isoformat(),
                    "final_state": flow.state_data
                }

                # Store in Redis for historical reference using synchronous client
                try:
                    import redis
                    from app.config import settings

                    redis_client = redis.from_url(
                        settings.REDIS_URL,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5
                    )

                    from app.config.settings.tasks import ARCHIVE_RETENTION_DAYS
                    redis_client.setex(
                        f"archived_flow:{flow.id}",
                        86400 * ARCHIVE_RETENTION_DAYS,
                        json.dumps(archive_data)
                    )

                    redis_client.close()

                except Exception as redis_error:
                    logger.warning(f"Failed to archive flow data to Redis: {redis_error}")
                
                db.delete(flow)
                results["completed_flows_cleaned"] += 1
            
            # Clean up old flow messages
            old_messages = db.query(Message).filter(
                Message.created_at < cutoff_date,
                Message.status.in_([MessageStatus.DELIVERED, MessageStatus.READ, MessageStatus.FAILED])
            ).all()
            
            for message in old_messages:
                db.delete(message)
                results["old_messages_cleaned"] += 1
            
            # Commit cleanup
            db.commit()
            
            results["end_time"] = datetime.utcnow().isoformat()
            
            logger.info(f"Flow data cleanup completed: {results}")
            return results
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Flow data cleanup failed: {e}")
        raise


@celery_app.task(bind=True, base=FlowTaskBase, max_retries=None, default_retry_delay=None)
def process_monthly_quizzes(self, limit: int = 50) -> dict[str, Any]:
    """
    Process monthly quiz triggers for eligible patients.
    
    Args:
        limit: Maximum number of patients to check
        
    Returns:
        dict[str, Any]: Quiz processing results containing:
            - total_patients: Number of patients eligible for quiz
            - quizzes_sent: Number of quizzes successfully sent
            - failed: Number of failed quiz sends
            - skipped: Number of skipped patients
            - results: List of individual processing results
    
    Raises:
        Exception: If quiz processing fails
    """
    from app.config.settings.tasks import QUIZ_MAX_RETRIES, QUIZ_PROCESSING_TIMEOUT

    # Apply task limits from settings if not already set
    if not self.max_retries:
        self.max_retries = QUIZ_MAX_RETRIES

    try:
        logger.info(f"Starting monthly quiz processing for up to {limit} patients")

        # Get database session
        db = next(get_db())

        try:
            # Initialize quiz trigger service
            from app.domain.quizzes.integration.flow_integration import get_quiz_trigger_service
            quiz_trigger_service = get_quiz_trigger_service(db)

            # Check and trigger monthly quizzes using proper async handling
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    results = loop.run_until_complete(
                        quiz_trigger_service.check_and_trigger_monthly_quizzes(limit=limit)
                    )
                finally:
                    loop.close()
            except RuntimeError as e:
                if "cannot be called from a running event loop" in str(e):
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(quiz_trigger_service.check_and_trigger_monthly_quizzes(limit=limit))
                        )
                        results = future.result(timeout=QUIZ_PROCESSING_TIMEOUT)
                else:
                    raise
            
            logger.info(f"Monthly quiz processing completed: {results}")
            return results
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Monthly quiz processing failed: {e}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            from app.config.settings.tasks import get_retry_countdown
            retry_delay = get_retry_countdown(self.request.retries, QUIZ_PROCESSING_TIMEOUT)
            logger.info(f"Retrying monthly quiz processing in {retry_delay} seconds (attempt {self.request.retries + 1})")
            raise self.retry(countdown=retry_delay, exc=e)
        else:
            logger.error(f"Monthly quiz processing failed after {self.max_retries} attempts")
            raise MaxRetriesExceededError(f"Task failed after {self.max_retries} retries: {e}")


@celery_app.task(bind=True, base=FlowTaskBase, max_retries=None, default_retry_delay=None)
def generate_quiz_report(self, session_id: str) -> dict[str, Any]:
    """
    Generate medical report from completed quiz session.
    
    Args:
        session_id (str): Quiz session ID as string
        
    Returns:
        dict[str, Any]: Report generation result containing:
            - status: Success or failure status
            - session_id: Quiz session identifier
            - report_id: Generated report identifier
            - generated_at: Timestamp when report was generated
    
    Raises:
        Exception: If report generation fails after all retries
    """
    from app.config.settings.tasks import QUIZ_MAX_RETRIES, QUIZ_REPORT_TIMEOUT, QUIZ_REPORT_RETRY_DELAY

    # Apply task limits from settings if not already set
    if not self.max_retries:
        self.max_retries = QUIZ_MAX_RETRIES

    try:
        logger.info(f"Generating quiz report for session {session_id}")

        # Get database session
        db = next(get_db())

        try:
            # Initialize quiz report generator
            from app.services.quiz_report_generator import get_quiz_report_generator
            report_generator = get_quiz_report_generator(db)

            # Generate report using proper async handling
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    report_id = loop.run_until_complete(
                        report_generator.generate_quiz_report(UUID(session_id))
                    )
                finally:
                    loop.close()
            except RuntimeError as e:
                if "cannot be called from a running event loop" in str(e):
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(report_generator.generate_quiz_report(UUID(session_id)))
                        )
                        report_id = future.result(timeout=QUIZ_REPORT_TIMEOUT)
                else:
                    raise
            
            result = {
                "status": "success",
                "session_id": session_id,
                "report_id": str(report_id),
                "generated_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Quiz report generated successfully: {result}")
            return result
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Quiz report generation failed: {e}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            from app.config.settings.tasks import get_retry_countdown
            retry_delay = get_retry_countdown(self.request.retries, QUIZ_REPORT_RETRY_DELAY)
            logger.info(f"Retrying quiz report generation in {retry_delay} seconds (attempt {self.request.retries + 1})")
            raise self.retry(countdown=retry_delay, exc=e)
        else:
            logger.error(f"Quiz report generation failed after {self.max_retries} attempts")
            return {
                "status": "failed",
                "session_id": session_id,
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat()
            }


@celery_app.task(bind=True, base=FlowTaskBase)
def monitor_flow_task_health(self) -> dict[str, Any]:
    """
    Monitor flow task health and Redis connection.
    
    Returns:
        dict[str, Any]: Health monitoring results containing:
            - database_connection: Database connection status
            - redis_connection: Redis connection status
            - gemini_client: Gemini client status
            - active_flows_count: Number of active flows
            - pending_messages_count: Number of pending messages
            - failed_tasks_count: Number of failed tasks
            - overall_healthy: Overall health status
            - timestamp: Monitoring timestamp
    
    Raises:
        Exception: If health monitoring fails
    """
    try:
        logger.info("Starting flow task health monitoring")
        
        # Get database session
        db = next(get_db())
        
        try:
            health_results = {
                "database_connection": False,
                "redis_connection": False,
                "gemini_client": False,
                "active_flows_count": 0,
                "pending_messages_count": 0,
                "failed_tasks_count": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Test database connection
            try:
                db.execute("SELECT 1")
                health_results["database_connection"] = True
            except Exception as e:
                logger.error(f"Database health check failed: {e}")
            
            # Test Redis connection using synchronous client
            try:
                import redis
                from app.config import settings

                redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )

                redis_client.ping()
                redis_client.close()
                health_results["redis_connection"] = True
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")
            
            # Test Gemini client using proper async handling
            try:
                gemini_client = get_gemini_client()
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        health_results["gemini_client"] = loop.run_until_complete(gemini_client.health_check())
                    finally:
                        loop.close()
                except RuntimeError as e:
                    if "cannot be called from a running event loop" in str(e):
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            from app.config.settings.tasks import HEALTH_CHECK_TIMEOUT
                            future = executor.submit(
                                lambda: asyncio.run(gemini_client.health_check())
                            )
                            health_results["gemini_client"] = future.result(timeout=HEALTH_CHECK_TIMEOUT)
                    else:
                        raise
            except Exception as e:
                logger.error(f"Gemini client health check failed: {e}")
            
            # Count active flows
            try:
                from app.config.settings.tasks import HEALTH_ACTIVE_FLOWS_LIMIT
                flow_repo = FlowStateRepository(db)
                active_flows = flow_repo.get_active_flows(limit=HEALTH_ACTIVE_FLOWS_LIMIT)
                health_results["active_flows_count"] = len(active_flows)
            except Exception as e:
                logger.error(f"Failed to count active flows: {e}")
            
            # Count pending messages
            try:
                pending_messages = db.query(Message).filter(
                    Message.status == MessageStatus.PENDING
                ).count()
                health_results["pending_messages_count"] = pending_messages
            except Exception as e:
                logger.error(f"Failed to count pending messages: {e}")
            
            # Check for failed tasks in Redis using synchronous client
            try:
                import redis
                from app.config import settings

                redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )

                failed_tasks = redis_client.keys("task_result:*")
                failed_count = 0

                for task_key in failed_tasks:
                    task_data = redis_client.get(task_key)
                    if task_data and "failure" in str(task_data):
                        failed_count += 1

                redis_client.close()
                health_results["failed_tasks_count"] = failed_count
            except Exception as e:
                logger.error(f"Failed to check task failures: {e}")
            
            # Overall health status
            health_results["overall_healthy"] = all([
                health_results["database_connection"],
                health_results["redis_connection"],
                health_results["gemini_client"]
            ])
            
            logger.info(f"Flow task health monitoring completed: {health_results}")
            return health_results
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Flow task health monitoring failed: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "overall_healthy": False
        }


async def _process_single_patient_flow(flow_engine, 
                                     flow_state: PatientFlowState) -> dict[str, Any]:
    """
    Process flow for a single patient.
    
    Args:
        flow_engine: Enhanced flow engine instance
        flow_state (PatientFlowState): Patient flow state object
        
    Returns:
        dict[str, Any]: Processing result containing:
            - status: Processing status (success, skipped, error)
            - patient_id: Patient identifier
            - current_day: Current flow day
            - flow_type: Flow type
            - message_scheduled: Whether message was scheduled
            - task_id: Celery task ID if message was scheduled
            - advancement_result: Flow advancement result
    
    Raises:
        Exception: If patient flow processing fails
    """
    # Get database session
    db = next(get_db())
    
    try:
        patient_id = flow_state.patient_id
        
        # Calculate current day
        current_day = await flow_engine.calculate_patient_day(patient_id)
        
        # Get patient timezone
        timezone_str = "America/Sao_Paulo"
        if flow_state.patient and hasattr(flow_state.patient, "timezone"):
             timezone_str = flow_state.patient.timezone
        
        try:
            import pytz
            tz = pytz.timezone(timezone_str)
        except Exception:
            logger.warning(f"Invalid timezone {timezone_str} for patient {patient_id}, defaulting to America/Sao_Paulo")
            import pytz
            tz = pytz.timezone("America/Sao_Paulo")

        # Check if message should be sent today (in patient's timezone)
        last_message_date = None
        if flow_state.state_data and "last_message_sent" in flow_state.state_data:
            last_message_date = datetime.fromisoformat(flow_state.state_data["last_message_sent"])
            # Ensure last_message_date is timezone aware
            if last_message_date.tzinfo is None:
                last_message_date = pytz.utc.localize(last_message_date)
            last_message_date = last_message_date.astimezone(tz)
        
        today_local = datetime.now(tz).date()
        
        # Skip if message already sent today (local time)
        if last_message_date and last_message_date.date() == today_local:
            return {
                "status": "skipped",
                "reason": "Message already sent today",
                "patient_id": str(patient_id),
                "current_day": current_day
            }
        
        # Advance patient flow
        advancement_result = await flow_engine.advance_patient_flow(patient_id)
        
    # Get message template for current day
        flow_type_enum = FlowType(flow_state.flow_type)
        message_template = _get_message_template_for_day(db, flow_type_enum, current_day)
        
        if not message_template:
            return {
                "status": "skipped",
                "reason": "No message template for current day",
                "patient_id": str(patient_id),
                "current_day": current_day,
                "flow_type": flow_type_enum.value
            }
        
        # Generate personalized message
        personalized_content = await flow_engine.generate_flow_message(patient_id, current_day, message_template)
        
        # Schedule message for sending
        message_data = {
            "content": personalized_content,
            "type": "text",
            "flow_day": current_day,
            "flow_type": flow_type_enum.value,
            "template_id": f"{flow_type_enum.value}_day_{current_day}",
            "personalized": True,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "template_intent": message_template.intent
            }
        }
        
        # Send message asynchronously
        send_task = send_flow_message.delay(str(patient_id), message_data)
        
        # Update flow state
        flow_state.state_data = flow_state.state_data or {}
        flow_state.state_data["last_message_sent"] = datetime.utcnow().isoformat()
        flow_state.state_data["last_task_id"] = send_task.id
        db.commit()
        
        return {
            "status": "success",
            "patient_id": str(patient_id),
            "current_day": current_day,
            "flow_type": flow_type_enum.value,
            "message_scheduled": True,
            "task_id": send_task.id,
            "advancement_result": advancement_result
        }
        
    except Exception as e:
        logger.error(f"Error processing patient flow {patient_id}: {e}")
        return {
            "status": "error",
            "patient_id": str(patient_id),
            "error": str(e)
        }
    finally:
        db.close()


def _get_message_template_for_day(db: Session, flow_type: FlowType, day: int) -> Optional[MessageTemplate]:
    """
    Get message template for specific flow type and day from database.
    
    Args:
        db (Session): Database session
        flow_type (FlowType): Flow type enum value
        day (int): Current day in the flow
        
    Returns:
        Optional[MessageTemplate]: Message template for the specified day or None if not found
    """
    try:
        from app.models.flow import FlowKind, FlowTemplateVersion
        
        # 1. Find the Flow Kind
        flow_kind = db.query(FlowKind).filter(
            FlowKind.flow_type == flow_type.value,
            FlowKind.is_active == True
        ).first()
        
        if not flow_kind:
            logger.warning(f"Flow kind not found or inactive: {flow_type.value}")
            return None

        # 2. Find the active Template Version for this kind
        active_version = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.kind_id == flow_kind.id,
            FlowTemplateVersion.is_active == True
        ).first()
        
        if not active_version:
            logger.warning(f"No active template version found for: {flow_type.value}")
            return None

        # 3. Extract steps/messages
        # The 'messages' column is mapped to 'steps' in DB (JSONB)
        steps = active_version.messages or []
        
        # 4. Find the specific day's step
        target_step = None
        for step in steps:
            # Check if this step corresponds to the requested day
            # The JSON structure might vary, checking common patterns
            step_day = step.get('day') or step.get('step_id')
            
            # Handle both string and int comparisons
            if str(step_day) == str(day):
                target_step = step
                break
        
        if not target_step:
            # Log verbose only if needed, as many days won't have messages
            # logger.debug(f"No step found for day {day} in flow {flow_type.value}")
            return None
            
        # 5. Convert to MessageTemplate object
        # Extract content and metadata
        content = target_step.get('message') or target_step.get('content') or ""
        if not content:
            return None
            
        intent = target_step.get('intent', 'daily_engagement')
        metadata = target_step.get('metadata', {})
        personalization = metadata.get('personalization_hints', [])
        ai_instructions = metadata.get('ai_instructions', '')
        
        return MessageTemplate(
            day=day,
            intent=intent,
            base_content=content,
            personalization_hints=personalization,
            ai_instructions=ai_instructions,
            variations=metadata.get('variations', [])
        )
        
    except Exception as e:
        logger.error(f"Error fetching template from DB for {flow_type.value} day {day}: {e}")
        # Fallback to hardcoded safety net only on critical DB error
        return _get_fallback_template(flow_type, day)

def _get_fallback_template(flow_type: FlowType, day: int) -> Optional[MessageTemplate]:
    """Fallback hardcoded templates in case of DB failure."""