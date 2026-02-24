"""
Core flow processing tasks.

This module contains the main Celery tasks for processing daily flows,
sending flow messages, and managing patient flow advancement.
"""

import asyncio
import logging
from typing import Any
from datetime import datetime
from asgiref.sync import async_to_sync
from celery.exceptions import MaxRetriesExceededError

from app.task_queue import task_queue as celery_app
from app.database import get_scoped_session
from app.repositories.flow import FlowStateRepository

from .base import FlowTaskBase, send_critical_alert_sync
from .batch_tasks import _process_single_patient_flow_by_id
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

_MAX_SAFE_DAILY_FLOW_LIMIT = 5000
_MAX_BATCH_CONCURRENCY_CAP = 10
_BATCH_STAGGER_SECONDS = 0.15
_MAX_BATCH_STAGGER_SECONDS = 2.0
_ERROR_COOLDOWN_SECONDS = 0.75
_THROTTLE_ERROR_RATE_THRESHOLD = 0.50


async def process_daily_flows_async(limit: int = 1000) -> dict[str, Any]:
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
    from app.config.settings.tasks import (
        FLOW_BATCH_SIZE,
        FLOW_PROCESSING_TIMEOUT,
        FLOW_MAX_CONCURRENT,
    )

    try:
        requested_limit = int(limit)
    except (TypeError, ValueError):
        requested_limit = 1000

    safe_limit = max(0, min(requested_limit, _MAX_SAFE_DAILY_FLOW_LIMIT))
    if safe_limit != requested_limit:
        logger.warning(
            "Adjusted process_daily_flows limit from %s to %s for safe execution",
            requested_limit,
            safe_limit,
        )

    logger.info(
        "Starting async daily flow processing for up to %s patients",
        safe_limit,
    )

    # Use context manager for database
    with get_scoped_session() as db:
        # Initialize services
        flow_repo = FlowStateRepository(db)

        # Get due active flow states only.
        active_flows = flow_repo.get_active_flows(
            limit=safe_limit,
            due_before=now_sao_paulo(),
        )

        results = {
            "processed_count": 0,
            "success_count": 0,
            "error_count": 0,
            "errors": [],
            "patients_processed": [],
            "start_time": now_sao_paulo().isoformat(),
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
        batch_size = max(1, FLOW_BATCH_SIZE)
        base_concurrency = max(
            1,
            min(FLOW_MAX_CONCURRENT, batch_size, _MAX_BATCH_CONCURRENCY_CAP),
        )
        current_concurrency = base_concurrency

        for i in range(0, len(active_flows), batch_size):
            batch = active_flows[i : i + batch_size]
            batch_number = i // batch_size + 1

            logger.info(
                "Processing batch %s: %s patients (concurrency=%s)",
                batch_number,
                len(batch),
                current_concurrency,
            )

            # Create tasks for the batch with timeout
            # CRITICAL FIX: Pass only patient_id (UUID) so each coroutine creates
            # its own isolated session, engine, and re-fetches flow_state
            # This prevents "detached" object errors and concurrent commit issues
            patient_ids = [flow.patient_id for flow in batch]

            # Limit concurrent DB connections to prevent pool exhaustion
            semaphore = asyncio.Semaphore(current_concurrency)

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
            batch_error_count = 0
            processed_in_batch = 0

            for flow, result in zip(batch, batch_results):
                results["processed_count"] += 1
                processed_in_batch += 1

                if isinstance(result, Exception):
                    # Error occurred (including timeout)
                    results["error_count"] += 1
                    batch_error_count += 1
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

                elif isinstance(result, dict) and result.get("status") == "success":
                    results["success_count"] += 1
                    results["patients_processed"].append(
                        {
                            "patient_id": str(flow.patient_id),
                            "status": "success",
                            "result": result,
                        }
                    )
                else:
                    batch_error_count += 1
                    results["error_count"] += 1
                    if isinstance(result, dict):
                        error_msg = result.get("error") or result.get(
                            "reason", "Unknown error"
                        )
                    else:
                        error_msg = (
                            f"Unexpected result type {type(result).__name__} "
                            f"for patient {flow.patient_id}"
                        )
                        result = {
                            "status": "error",
                            "error": error_msg,
                        }

                    results["errors"].append(
                        {
                            "patient_id": str(flow.patient_id),
                            "error": error_msg,
                        }
                    )
                    results["patients_processed"].append(
                        {
                            "patient_id": str(flow.patient_id),
                            "status": "error",
                            "result": result,
                        }
                    )

            batch_error_rate = (
                batch_error_count / processed_in_batch if processed_in_batch else 0.0
            )
            stagger_delay = _BATCH_STAGGER_SECONDS

            if batch_error_rate >= _THROTTLE_ERROR_RATE_THRESHOLD:
                previous_concurrency = current_concurrency
                current_concurrency = max(1, current_concurrency // 2)
                stagger_delay += _ERROR_COOLDOWN_SECONDS
                logger.warning(
                    "High batch error rate detected (%.2f). Throttling concurrency "
                    "from %s to %s and applying %.2fs cooldown.",
                    batch_error_rate,
                    previous_concurrency,
                    current_concurrency,
                    stagger_delay,
                )
            elif current_concurrency < base_concurrency:
                current_concurrency += 1

            has_more_batches = i + batch_size < len(active_flows)
            if has_more_batches:
                await asyncio.sleep(min(stagger_delay, _MAX_BATCH_STAGGER_SECONDS))

        results["end_time"] = now_sao_paulo().isoformat()
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
    name="app.tasks.flows.flow_tasks.process_daily_flows",
    max_retries=None,  # Set dynamically from settings
    default_retry_delay=None,  # Set dynamically from settings
    time_limit=None,  # Set dynamically from settings
    soft_time_limit=None,  # Set dynamically from settings
)
def process_daily_flows(self, limit: int = 1000) -> dict[str, Any]:
    """
    Process daily flows for all active patients using EnhancedFlowEngine.

    This is a wrapper task that delegates to the async implementation to prevent
    event loop memory leaks. It remains a non-AI async_to_sync bridge only; Celery
    AI run_sync wiring is enforced in batch processing paths.

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
        FLOW_RETRY_DELAY,
        TASK_TIME_LIMIT,
        TASK_SOFT_TIME_LIMIT,
    )

    # Apply task limits from settings if not already set
    if self.time_limit is None:
        self.time_limit = TASK_TIME_LIMIT
    if self.soft_time_limit is None:
        self.soft_time_limit = TASK_SOFT_TIME_LIMIT
    if self.max_retries is None:
        self.max_retries = FLOW_MAX_RETRIES
    if self.default_retry_delay is None:
        self.default_retry_delay = FLOW_RETRY_DELAY

    max_retries = self.max_retries if self.max_retries is not None else FLOW_MAX_RETRIES

    try:
        logger.info(f"Starting daily flow processing task for up to {limit} patients")

        # Execute async version via async_to_sync (avoids per-call event loop creation)
        results = async_to_sync(process_daily_flows_async)(limit)

        return results

    except Exception as e:
        logger.error(f"Daily flow processing failed: {e}", exc_info=True)

        # Retry with exponential backoff
        if self.request.retries < max_retries:
            from app.config.settings.tasks import get_retry_countdown

            retry_delay = get_retry_countdown(self.request.retries, FLOW_RETRY_DELAY)

            logger.warning(
                f"Retrying daily flow processing in {retry_delay} seconds "
                f"(attempt {self.request.retries + 1}/{max_retries})"
            )
            raise self.retry(countdown=retry_delay, exc=e)
        else:
            # Max retries reached - alert admin
            logger.error(
                f"Daily flow processing failed after {max_retries} attempts"
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
                f"Task failed after {max_retries} retries: {e}"
            )
