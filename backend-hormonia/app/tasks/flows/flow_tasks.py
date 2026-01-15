"""
Core flow processing tasks.

This module contains the main Celery tasks for processing daily flows,
sending flow messages, and managing patient flow advancement.
"""

import asyncio
import logging
from typing import Any
from datetime import datetime, timezone
from uuid import UUID
from celery.exceptions import MaxRetriesExceededError

from app.task_queue import task_queue as celery_app
from app.database import get_db, get_scoped_session
from app.services.enhanced_flow_engine import get_enhanced_flow_engine
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.repositories.message import MessageRepository
from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.exceptions import NotFoundError

from .base import FlowTaskBase, send_critical_alert_sync
from .batch_tasks import _process_single_patient_flow_safe, _process_single_patient_flow_by_id

logger = logging.getLogger(__name__)


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

    # Use context manager for database
    with get_scoped_session() as db:
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
            "start_time": datetime.now(timezone.utc).isoformat(),
        }

        # Filter out paused flows
        active_flows = [
            flow
            for flow in active_flows
            if not (flow.step_data and flow.step_data.get("paused"))
        ]

        logger.info(
            f"Processing {len(active_flows)} active flows in batches of {FLOW_BATCH_SIZE}"
        )

        # Process in batches for parallel execution
        batch_size = FLOW_BATCH_SIZE

        for i in range(0, len(active_flows), batch_size):
            batch = active_flows[i : i + batch_size]

            logger.info(
                f"Processing batch {i // batch_size + 1}: {len(batch)} patients"
            )

            # Create tasks for the batch with timeout
            # CRITICAL FIX: Pass only patient_id (UUID) so each coroutine creates
            # its own isolated session, engine, and re-fetches flow_state
            # This prevents "detached" object errors and concurrent commit issues
            patient_ids = [flow.patient_id for flow in batch]
            
            # Limit concurrent DB connections to prevent pool exhaustion
            MAX_CONCURRENT_DB = 10
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_DB)
            
            async def limited_process(patient_id):
                async with semaphore:
                    return await _process_single_patient_flow_by_id(patient_id)
            
            tasks = [
                asyncio.wait_for(
                    limited_process(patient_id),
                    timeout=FLOW_PROCESSING_TIMEOUT,
                )
                for patient_id in patient_ids
            ]

            # Execute in parallel with exception handling
            batch_results = await asyncio.gather(
                *tasks,
                return_exceptions=True,  # Don't fail entire batch if one fails
            )

            # Process results
            for flow, result in zip(batch, batch_results):
                results["processed_count"] += 1

                if isinstance(result, Exception):
                    # Error occurred (including timeout)
                    results["error_count"] += 1
                    error_msg = str(result)

                    if isinstance(result, asyncio.TimeoutError):
                        error_msg = (
                            f"Processing timeout after {FLOW_PROCESSING_TIMEOUT}s"
                        )

                    results["errors"].append(
                        {"patient_id": str(flow.patient_id), "error": error_msg}
                    )
                    results["patients_processed"].append(
                        {
                            "patient_id": str(flow.patient_id),
                            "status": "error",
                            "error": error_msg,
                        }
                    )

                    logger.error(
                        f"Flow processing failed for patient {flow.patient_id}: {error_msg}"
                    )

                elif result.get("status") == "success":
                    results["success_count"] += 1
                    results["patients_processed"].append(
                        {
                            "patient_id": str(flow.patient_id),
                            "status": "success",
                            "result": result,
                        }
                    )
                else:
                    results["error_count"] += 1
                    results["errors"].append(
                        {
                            "patient_id": str(flow.patient_id),
                            "error": result.get("error", "Unknown error"),
                        }
                    )
                    results["patients_processed"].append(
                        {
                            "patient_id": str(flow.patient_id),
                            "status": "error",
                            "result": result,
                        }
                    )

        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["duration_seconds"] = (
            datetime.fromisoformat(results["end_time"])
            - datetime.fromisoformat(results["start_time"])
        ).total_seconds()

        logger.info(
            f"Async daily flow processing completed: "
            f"{results['success_count']}/{results['processed_count']} successful "
            f"in {results['duration_seconds']:.2f} seconds"
        )

        return results


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
    from app.config.settings.tasks import (
        FLOW_MAX_RETRIES,
        TASK_TIME_LIMIT,
        TASK_SOFT_TIME_LIMIT,
    )

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
            logger.error(
                f"Daily flow processing failed after {self.max_retries} attempts"
            )

            try:
                from app.config.settings.tasks import ENABLE_ADMIN_ALERTS

                if ENABLE_ADMIN_ALERTS:
                    # Use synchronous helper for critical alerts
                    send_critical_alert_sync(
                        task_name="process_daily_flows",
                        error=str(e),
                        context={"retries": self.request.retries, "limit": limit},
                    )
            except Exception as alert_error:
                logger.error(f"Failed to send admin alert: {alert_error}")

            raise MaxRetriesExceededError(
                f"Task failed after {self.max_retries} retries: {e}"
            )


@celery_app.task(
    bind=True, base=FlowTaskBase, max_retries=None, default_retry_delay=None
)
def send_flow_message(
    self, patient_id: str, message_data: dict[str, Any], message_id: str = None
) -> dict[str, Any]:
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
        logger.info(
            f"Sending flow message to patient {patient_id}, message_id: {message_id}"
        )

        from app.database import get_async_session_factory
        from app.services.unified_whatsapp_service import (
            create_unified_whatsapp_service,
        )
        from app.utils.async_helpers import run_async
        from app.models.patient import Patient

        async def _send_flow_message_async() -> dict[str, Any]:
            async_session_factory = get_async_session_factory()

            async with async_session_factory() as db:
                patient = await db.get(Patient, UUID(patient_id))
                if not patient:
                    raise NotFoundError(f"Patient {patient_id} not found")

                if message_id:
                    message = await db.get(Message, UUID(message_id))
                    if not message:
                        raise NotFoundError(f"Scheduled message {message_id} not found")

                    if message.status not in [
                        MessageStatus.SCHEDULED,
                        MessageStatus.PENDING,
                    ]:
                        logger.warning(
                            f"Message {message_id} has unexpected status {message.status}, proceeding anyway"
                        )

                    message.status = MessageStatus.SENDING
                    message.message_metadata = message.message_metadata or {}
                    message.message_metadata["celery_execution_started"] = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    message.message_metadata["task_id"] = self.request.id
                else:
                    logger.warning(
                        f"Creating new message for patient {patient_id} - this may indicate message_id was not passed"
                    )
                    metadata = message_data.get("metadata") or {}
                    message = Message(
                        patient_id=UUID(patient_id),
                        direction=MessageDirection.OUTBOUND,
                        type=MessageType(message_data.get("type", "text")),
                        content=message_data.get("content", ""),
                        message_metadata=metadata,
                        status=MessageStatus.SENDING,
                        scheduled_for=datetime.now(timezone.utc),
                    )
                    db.add(message)

                message.message_metadata = message.message_metadata or {}
                message.message_metadata.setdefault("flow_context", {})
                message.message_metadata["flow_context"].update(
                    {
                        "flow_day": message_data.get("flow_day"),
                        "flow_type": message_data.get("flow_type"),
                        "template_id": message_data.get("template_id"),
                        "personalized": message_data.get("personalized", False),
                        "sent_via_celery": True,
                        "task_id": self.request.id,
                    }
                )

                await db.commit()
                await db.refresh(message)

                message_sender = create_unified_whatsapp_service(db)
                success = await message_sender.send_message(message)

                message.message_metadata["celery_execution_completed"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                message.message_metadata["execution_status"] = (
                    "success" if success else "failed"
                )

                if success:
                    message.status = MessageStatus.SENT
                    message.sent_at = datetime.now(timezone.utc)
                    logger.info(
                        f"Flow message sent successfully to patient {patient_id}, message_id: {message.id}"
                    )
                else:
                    message.status = MessageStatus.FAILED
                    message.message_metadata["failure_reason"] = (
                        "Message sending failed"
                    )
                    logger.error(
                        f"Failed to send flow message to patient {patient_id}, message_id: {message.id}"
                    )

                await db.commit()

                result = {
                    "status": "success" if success else "failed",
                    "patient_id": patient_id,
                    "message_id": str(message.id),
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "whatsapp_id": message.whatsapp_id,
                    "updated_existing": bool(message_id),
                }

                if not success:
                    result["error"] = "Message sending failed"

                return result

        return run_async(_send_flow_message_async())

    except Exception as e:
        logger.error(f"Error sending flow message to patient {patient_id}: {e}")

        # Try to mark message as failed if message_id was provided
        if message_id:
            try:
                with get_scoped_session() as db:
                    message_repo = MessageRepository(db)
                    message = message_repo.get(UUID(message_id))
                    if message:
                        message.status = MessageStatus.FAILED
                        message.message_metadata["celery_execution_error"] = str(e)
                        message.message_metadata["celery_execution_failed_at"] = (
                            datetime.now(timezone.utc).isoformat()
                        )
                        message.message_metadata["retry_count"] = self.request.retries
                        db.commit()
                        logger.info(
                            f"Marked message {message_id} as FAILED after exception"
                        )
            except Exception as update_error:
                logger.error(
                    f"Failed to update message status after exception: {update_error}"
                )

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            from app.config.settings.tasks import get_retry_countdown

            retry_delay = get_retry_countdown(self.request.retries, MESSAGE_RETRY_DELAY)
            logger.info(
                f"Retrying flow message send in {retry_delay} seconds (attempt {self.request.retries + 1})"
            )
            raise self.retry(countdown=retry_delay, exc=e)
        else:
            logger.error(f"Flow message send failed after {self.max_retries} attempts")
            return {
                "status": "failed",
                "patient_id": patient_id,
                "message_id": message_id,
                "error": f"Failed after {self.max_retries} retries: {str(e)}",
                "final_attempt": True,
            }
