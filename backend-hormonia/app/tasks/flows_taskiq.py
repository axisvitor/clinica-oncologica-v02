"""
Taskiq flow tasks — async-native replacements for Celery flow/automation/monthly tasks (M009-S03).

All 14 flow-domain tasks migrated from Celery to Taskiq:
  1. process_daily_flows          — cron 08:00 BRT (11:00 UTC), batch flow processing
  2. check_and_start_pending_flows — 900s interval, enroll patients missing flows
  3. send_daily_reminders         — cron 09:00 BRT (12:00 UTC), quiz pending reminders
  4. resume_paused_flows          — 3600s interval, auto-resume expired pauses
  5. cleanup_expired_quiz_links   — 86400s interval, expire stale quiz sessions
  6. send_flow_day_for_patient    — on-demand with retry, send specific day messages
  7. process_monthly_quizzes      — 3600s interval, trigger monthly quizzes
  8. generate_quiz_report         — on-demand with retry, generate quiz report
  9. detect_stuck_flows           — 900s interval, find & recover stuck flows
  10. monitor_flow_task_health    — 300s interval, health checks (DB/Redis/Gemini)
  11. evaluate_flow_alerts        — 900s interval, evaluate flow analytics alerts
  12. cleanup_old_flow_data       — 86400s interval, archive & delete old flows/messages
  13. retry_failed_flow_send      — on-demand with retry, retry failed outbound messages
  14. retry_failed_followup_send  — on-demand with retry, retry failed follow-up sends

Key translation patterns from Celery → Taskiq:
  - async_to_sync() / run_async() bridges removed: task body is directly async
  - self.retry(countdown=) → raise exception, SmartRetryMiddleware handles retry
  - get_scoped_session() (sync) → AsyncSession via TaskiqDepends (main flow)
  - _process_single_patient_flow_by_id keeps its own sync session (no change)
  - send_scheduled_message.delay() → await send_scheduled_message.kiq()
  - Structured logging via log_task_start/success/error from taskiq_base

Schedule labels (10 of 14 tasks are periodic):
  - process_daily_flows:          cron 0 11 * * * (08:00 BRT)
  - check_and_start_pending_flows: interval 900s
  - send_daily_reminders:         cron 0 12 * * * (09:00 BRT)
  - resume_paused_flows:          interval 3600s
  - cleanup_expired_quiz_links:   interval 86400s
  - process_monthly_quizzes:      interval 3600s
  - detect_stuck_flows:           interval 900s
  - monitor_flow_task_health:     interval 300s
  - evaluate_flow_alerts:         interval 900s
  - cleanup_old_flow_data:        interval 86400s
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import Context, TaskiqDepends

from app.taskiq_broker import broker
from app.tasks.taskiq_base import (
    DbSession,
    log_task_error,
    log_task_start,
    log_task_success,
)
from app.utils.timezone import now_sao_paulo

# Cross-task dispatch — Taskiq equivalent of Celery's send_scheduled_message.delay()
from app.tasks.messaging_taskiq import send_scheduled_message

# Pure helpers extracted to shared helper package.
from app.tasks.helpers.flow_helpers import (
    _process_single_patient_flow_by_id,
    _determine_template_for_patient,
    _get_reminder_message,
    _is_auto_resume_due,
)

logger = logging.getLogger("app.tasks.flows_taskiq")

# ---------------------------------------------------------------------------
# Constants (from flow_tasks.py — kept local to avoid importing Celery module)
# ---------------------------------------------------------------------------
_MAX_SAFE_DAILY_FLOW_LIMIT = 5000
_MAX_BATCH_CONCURRENCY_CAP = 10
_BATCH_STAGGER_SECONDS = 0.15
_MAX_BATCH_STAGGER_SECONDS = 2.0
_ERROR_COOLDOWN_SECONDS = 0.75
_THROTTLE_ERROR_RATE_THRESHOLD = 0.50


# ===========================================================================
# 1. process_daily_flows — cron 08:00 BRT (11:00 UTC)
# ===========================================================================

@broker.task(
    schedule=[{"cron": "0 11 * * *", "kwargs": {"limit": 1000}}],
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def process_daily_flows(
    limit: int = 1000,
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Process daily flows for all active patients.

    Async-native Taskiq replacement for the Celery process_daily_flows task.
    The original Celery task wrapped ``process_daily_flows_async()`` via
    ``async_to_sync``. Here the async logic is inlined directly.

    Uses ``get_scoped_session()`` (sync) internally for the initial FlowStateRepository
    query, then delegates per-patient processing to ``_process_single_patient_flow_by_id``
    which creates its own isolated sync session.

    Args:
        limit: Maximum number of patients to process.
        db: Async database session (injected by TaskiqDepends).

    Returns:
        Dict with processing results (processed_count, success_count, errors, etc.).
    """
    start_time = log_task_start("process_daily_flows", limit=limit)

    try:
        from app.config.settings.tasks import (
            FLOW_BATCH_SIZE,
            FLOW_PROCESSING_TIMEOUT,
            FLOW_MAX_CONCURRENT,
        )
        from app.database import get_scoped_session
        from app.repositories.flow import FlowStateRepository

        requested_limit = int(limit)
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

        # Use sync session for FlowStateRepository (it uses sync ORM queries)
        with get_scoped_session() as sync_db:
            flow_repo = FlowStateRepository(sync_db)
            active_flows = flow_repo.get_active_flows(
                limit=safe_limit,
                due_before=now_sao_paulo(),
            )

            results: dict[str, Any] = {
                "processed_count": 0,
                "success_count": 0,
                "error_count": 0,
                "errors": [],
                "patients_processed": [],
                "start_time": now_sao_paulo().isoformat(),
            }

            # Filter out paused flows based on state_data
            paused_count = len(
                [f for f in active_flows if f.state_data and f.state_data.get("paused")]
            )
            active_flows = [
                f for f in active_flows
                if not (f.state_data and f.state_data.get("paused"))
            ]
            if paused_count:
                logger.info("Filtered out %s paused flows from daily processing", paused_count)

            logger.info(
                "Processing %s active flows in batches of %s",
                len(active_flows),
                FLOW_BATCH_SIZE,
            )

            # Batch processing with concurrency control
            batch_size = max(1, FLOW_BATCH_SIZE)
            base_concurrency = max(
                1, min(FLOW_MAX_CONCURRENT, batch_size, _MAX_BATCH_CONCURRENCY_CAP)
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

                patient_ids = [flow.patient_id for flow in batch]
                semaphore = asyncio.Semaphore(current_concurrency)

                async def limited_process(patient_id):
                    async with semaphore:
                        return await _process_single_patient_flow_by_id(patient_id)

                tasks = [
                    asyncio.wait_for(
                        limited_process(pid),
                        timeout=FLOW_PROCESSING_TIMEOUT,
                    )
                    for pid in patient_ids
                ]

                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Tally results
                batch_error_count = 0
                processed_in_batch = 0

                for flow, result in zip(batch, batch_results):
                    results["processed_count"] += 1
                    processed_in_batch += 1

                    if isinstance(result, Exception):
                        results["error_count"] += 1
                        batch_error_count += 1
                        error_msg = str(result)
                        if isinstance(result, asyncio.TimeoutError):
                            error_msg = f"Processing timeout after {FLOW_PROCESSING_TIMEOUT}s"
                        results["errors"].append(
                            {"patient_id": str(flow.patient_id), "error": error_msg}
                        )
                        results["patients_processed"].append(
                            {"patient_id": str(flow.patient_id), "status": "error", "error": error_msg}
                        )
                        logger.error(
                            "Flow processing failed for patient %s: %s",
                            flow.patient_id,
                            error_msg,
                        )
                    elif isinstance(result, dict) and result.get("status") == "success":
                        results["success_count"] += 1
                        results["patients_processed"].append(
                            {"patient_id": str(flow.patient_id), "status": "success", "result": result}
                        )
                    else:
                        batch_error_count += 1
                        results["error_count"] += 1
                        if isinstance(result, dict):
                            error_msg = result.get("error") or result.get("reason", "Unknown error")
                        else:
                            error_msg = (
                                f"Unexpected result type {type(result).__name__} "
                                f"for patient {flow.patient_id}"
                            )
                            result = {"status": "error", "error": error_msg}
                        results["errors"].append(
                            {"patient_id": str(flow.patient_id), "error": error_msg}
                        )
                        results["patients_processed"].append(
                            {"patient_id": str(flow.patient_id), "status": "error", "result": result}
                        )

                # Adaptive concurrency throttling
                batch_error_rate = (
                    batch_error_count / processed_in_batch if processed_in_batch else 0.0
                )
                stagger_delay = _BATCH_STAGGER_SECONDS

                if batch_error_rate >= _THROTTLE_ERROR_RATE_THRESHOLD:
                    previous_concurrency = current_concurrency
                    current_concurrency = max(1, current_concurrency // 2)
                    stagger_delay += _ERROR_COOLDOWN_SECONDS
                    logger.warning(
                        "High batch error rate (%.2f). Throttling concurrency %s→%s, cooldown %.2fs",
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

        log_task_success(
            "process_daily_flows",
            start_time,
            processed_count=results["processed_count"],
            success_count=results["success_count"],
            error_count=results["error_count"],
        )
        return results

    except Exception as exc:
        log_task_error("process_daily_flows", exc, start_time, limit=limit)
        raise


# ===========================================================================
# 2. check_and_start_pending_flows — periodic (900s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 900}}],
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def check_and_start_pending_flows(
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Check for patients without active flows and start them automatically.

    Async-native Taskiq replacement for the Celery check_and_start_pending_flows task.
    Uses direct async DB queries instead of the ``async_to_sync`` bridge.

    Runs every 15 minutes (900s). Queries patients created in the last 7 days
    without an active flow and enrolls them via EnhancedFlowEngine.

    Args:
        db: Async database session (injected by TaskiqDepends).

    Returns:
        Dict with flows_started count, errors, and timestamp.
    """
    start_time = log_task_start("check_and_start_pending_flows")

    try:
        from app.services.enhanced_flow_engine import get_enhanced_flow_engine

        flows_started = 0
        errors: list[str] = []

        # Query patients without active flows (raw SQL for complex NOT EXISTS)
        query = text("""
            SELECT p.id, p.treatment_type, p.name
            FROM patients p
            WHERE NOT EXISTS (
                SELECT 1
                FROM patient_flow_states pfs
                WHERE pfs.patient_id = p.id
                  AND pfs.status IN ('active', 'scheduled', 'in_progress')
            )
                AND p.created_at > NOW() - INTERVAL '7 days'
                AND p.flow_state = 'active'
                AND p.deleted_at IS NULL
            LIMIT 50
            FOR UPDATE SKIP LOCKED
        """)

        result = await db.execute(query)
        patients_without_flow = result.fetchall()

        logger.info("Found %s patients without active flows", len(patients_without_flow))

        flow_engine = get_enhanced_flow_engine(db)

        for patient_row in patients_without_flow:
            try:
                template_name = _determine_template_for_patient(patient_row)
                if template_name:
                    await flow_engine.enroll_patient(
                        patient_id=patient_row.id,
                        flow_type=template_name,
                    )
                    flows_started += 1
                    logger.info(
                        "Started automatic flow '%s' for patient_id=%s",
                        template_name,
                        patient_row.id,
                    )
                else:
                    logger.warning(
                        "Could not determine template for patient_id=%s",
                        patient_row.id,
                    )
            except Exception as e:
                error_msg = f"Failed to start flow for patient {patient_row.id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                await db.rollback()

        log_task_success(
            "check_and_start_pending_flows",
            start_time,
            flows_started=flows_started,
        )
        return {
            "flows_started": flows_started,
            "errors": errors,
            "timestamp": now_sao_paulo().isoformat(),
        }

    except Exception as exc:
        log_task_error("check_and_start_pending_flows", exc, start_time)
        raise


# ===========================================================================
# 3. send_daily_reminders — cron 09:00 BRT (12:00 UTC)
# ===========================================================================

@broker.task(
    schedule=[{"cron": "0 12 * * *"}],
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def send_daily_reminders(
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Send daily reminders to patients with pending quizzes.

    Async-native Taskiq replacement for the Celery send_daily_reminders task.
    Critical change: dispatches via ``await send_scheduled_message.kiq()``
    instead of ``send_scheduled_message.delay()``.

    Runs daily at 09:00 BRT (12:00 UTC). Finds patients with in-progress
    quiz sessions older than 24h but newer than 7 days and sends reminders.

    Args:
        db: Async database session (injected by TaskiqDepends).

    Returns:
        Dict with reminders_sent count, errors, and timestamp.
    """
    start_time = log_task_start("send_daily_reminders")

    try:
        from app.models.template import MessageTemplate
        from app.models.message import (
            Message,
            MessageType,
            MessageDirection,
            MessageStatus,
        )

        reminders_sent = 0
        errors: list[str] = []

        # Fetch reminder template
        template_query = select(MessageTemplate).where(
            MessageTemplate.name == "daily_reminder_generic",
            MessageTemplate.is_active,
        )
        template_result = await db.execute(template_query)
        template = template_result.scalar_one_or_none()

        # Query patients with pending quiz sessions
        query = text("""
            SELECT DISTINCT p.id, p.name, qs.id as session_id, qs.session_metadata
            FROM patients p
            INNER JOIN quiz_sessions qs
                ON p.id = qs.patient_id
            WHERE qs.status = 'in_progress'
                AND qs.created_at < NOW() - INTERVAL '24 hours'
                AND qs.created_at > NOW() - INTERVAL '7 days'
                AND p.flow_state = 'active'
                AND p.deleted_at IS NULL
            LIMIT 100
        """)

        result = await db.execute(query)
        patients_with_pending_quiz = result.fetchall()

        logger.info(
            "Found %s patients with pending quizzes",
            len(patients_with_pending_quiz),
        )

        for patient_row in patients_with_pending_quiz:
            try:
                # Format reminder content
                if template:
                    try:
                        reminder_content = template.content.format(
                            patient_name=patient_row.name,
                        )
                    except Exception as e:
                        logger.warning("Failed to format template: %s. Using fallback.", e)
                        reminder_content = _get_reminder_message(patient_row.name)
                else:
                    reminder_content = _get_reminder_message(patient_row.name)

                # Check cooldown — skip if reminder sent <20h ago
                session_metadata = dict(patient_row.session_metadata or {})
                last_daily_reminder_raw = session_metadata.get("last_daily_reminder_sent_at")
                if isinstance(last_daily_reminder_raw, str):
                    try:
                        last_daily_reminder = datetime.fromisoformat(last_daily_reminder_raw)
                        if last_daily_reminder.tzinfo is None:
                            last_daily_reminder = last_daily_reminder.replace(
                                tzinfo=now_sao_paulo().tzinfo,
                            )
                        if (now_sao_paulo() - last_daily_reminder).total_seconds() < 20 * 3600:
                            continue
                    except ValueError:
                        pass

                # Create message object
                message = Message(
                    patient_id=patient_row.id,
                    direction=MessageDirection.OUTBOUND,
                    type=MessageType.TEXT,
                    content=reminder_content,
                    status=MessageStatus.PENDING,
                    message_metadata={
                        "source": "automation_reminder",
                        "quiz_session_id": str(patient_row.session_id),
                    },
                )
                db.add(message)
                await db.commit()
                await db.refresh(message)

                # Update quiz session metadata with reminder timestamp
                await db.execute(
                    text("""
                        UPDATE quiz_sessions
                        SET session_metadata = jsonb_set(
                            COALESCE(session_metadata, '{}'::jsonb),
                            '{last_daily_reminder_sent_at}',
                            to_jsonb(:sent_at::text),
                            true
                        )
                        WHERE id = :session_id
                    """),
                    {
                        "session_id": patient_row.session_id,
                        "sent_at": now_sao_paulo().isoformat(),
                    },
                )
                await db.commit()

                # Dispatch via Taskiq (was: send_scheduled_message.delay())
                await send_scheduled_message.kiq(str(message.id))

                reminders_sent += 1
                logger.info("Sent reminder to patient_id=%s", patient_row.id)

            except Exception as e:
                error_msg = f"Failed to send reminder to patient {patient_row.id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                await db.rollback()

        log_task_success(
            "send_daily_reminders",
            start_time,
            reminders_sent=reminders_sent,
        )
        return {
            "reminders_sent": reminders_sent,
            "errors": errors,
            "timestamp": now_sao_paulo().isoformat(),
        }

    except Exception as exc:
        log_task_error("send_daily_reminders", exc, start_time)
        raise


# ===========================================================================
# 4. resume_paused_flows — periodic (3600s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 3600}}],
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def resume_paused_flows(
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Resume flows that have expired auto-resume timestamps.

    Async-native Taskiq replacement for the Celery resume_paused_flows task.
    Runs every hour (3600s). Finds paused flows where ``auto_resume_at`` has
    passed and resumes them via FlowManagementService.

    Args:
        db: Async database session (injected by TaskiqDepends).

    Returns:
        Dict with flows_resumed count, errors, and timestamp.
    """
    start_time = log_task_start("resume_paused_flows")

    try:
        from app.repositories.flow import FlowStateRepository
        from app.services.flow_management import FlowManagementService
        from app.exceptions import FlowStateConflictError

        flows_resumed = 0
        errors: list[str] = []

        # Query paused flows with expired auto-resume timestamps
        query = text("""
            SELECT pfs.id, pfs.patient_id, pfs.state_data
            FROM patient_flow_states pfs
            INNER JOIN patients p ON pfs.patient_id = p.id
            WHERE pfs.status = 'paused'
                AND pfs.state_data->>'auto_resume_at' IS NOT NULL
                AND (pfs.state_data->>'auto_resume_at')::timestamptz <= NOW()
                AND p.deleted_at IS NULL
            LIMIT 50
            FOR UPDATE OF pfs SKIP LOCKED
        """)

        result = await db.execute(query)
        paused_flows = result.fetchall()

        logger.info(
            "Found %s paused flows with expired auto-resume timestamps",
            len(paused_flows),
        )

        # FlowStateRepository and FlowManagementService expect sync session.
        # Use sync session for the resume operation.
        from app.database import get_scoped_session as get_sync_session

        with get_sync_session() as sync_db:
            flow_repo = FlowStateRepository(sync_db)
            mgmt_service = FlowManagementService(flow_repo, sync_db)

            for flow_row in paused_flows:
                try:
                    state_data = flow_row.state_data if hasattr(flow_row, "state_data") else None
                    auto_resume_at_raw = None
                    if state_data:
                        auto_resume_at_raw = state_data.get("auto_resume_at")

                    if not _is_auto_resume_due(auto_resume_at_raw):
                        continue

                    # FlowManagementService.resume_patient_flow is async in Celery version
                    # but the management service itself may use sync ORM.
                    await mgmt_service.resume_patient_flow(patient_id=flow_row.patient_id)

                    flows_resumed += 1
                    logger.info(
                        "Auto-resumed flow",
                        extra={
                            "patient_id": str(flow_row.patient_id),
                            "flow_id": str(flow_row.id),
                            "auto_resume_at": auto_resume_at_raw,
                            "action": "auto_resume",
                            "actor": "taskiq_scheduler",
                        },
                    )

                except FlowStateConflictError as exc:
                    logger.warning(
                        "Skipped auto-resume because flow is no longer paused",
                        extra={
                            "patient_id": str(flow_row.patient_id),
                            "flow_id": str(flow_row.id),
                            "reason": str(exc),
                            "action": "auto_resume_skip",
                            "actor": "taskiq_scheduler",
                        },
                    )

                except Exception as e:
                    error_msg = f"Failed to resume flow {flow_row.id}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    sync_db.rollback()

        log_task_success(
            "resume_paused_flows",
            start_time,
            flows_resumed=flows_resumed,
        )
        return {
            "flows_resumed": flows_resumed,
            "errors": errors,
            "timestamp": now_sao_paulo().isoformat(),
        }

    except Exception as exc:
        log_task_error("resume_paused_flows", exc, start_time)
        raise


# ===========================================================================
# 5. cleanup_expired_quiz_links — periodic (86400s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 86400}}],
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def cleanup_expired_quiz_links(
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Clean up expired quiz links and update their status.

    Async-native Taskiq replacement for the Celery cleanup_expired_quiz_links task.
    Runs daily (86400s). Pure SQL cleanup — updates expired quiz sessions.

    Args:
        db: Async database session (injected by TaskiqDepends).

    Returns:
        Dict with links_cleaned count, errors, and timestamp.
    """
    start_time = log_task_start("cleanup_expired_quiz_links")

    try:
        query = text("""
            UPDATE quiz_sessions
            SET status = 'expired',
                session_metadata = jsonb_set(
                    COALESCE(session_metadata, '{}'::jsonb),
                    '{link_status}',
                    '"expired"'
                )
            WHERE status = 'in_progress'
                AND session_metadata->>'expires_at' IS NOT NULL
                AND session_metadata->>'expires_at' ~ '^\\d{4}-\\d{2}-\\d{2}T'
                AND (session_metadata->>'expires_at')::timestamp < NOW()
            RETURNING id
        """)

        result = await db.execute(query)
        expired_sessions = result.fetchall()
        links_cleaned = len(expired_sessions)

        await db.commit()

        logger.info("Cleaned up %s expired quiz links", links_cleaned)

        log_task_success(
            "cleanup_expired_quiz_links",
            start_time,
            links_cleaned=links_cleaned,
        )
        return {
            "links_cleaned": links_cleaned,
            "errors": [],
            "timestamp": now_sao_paulo().isoformat(),
        }

    except Exception as exc:
        await db.rollback()
        log_task_error("cleanup_expired_quiz_links", exc, start_time)
        raise


# ===========================================================================
# 6. send_flow_day_for_patient — on-demand with retry
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=30,
)
async def send_flow_day_for_patient(
    patient_id: str,
    day_number: Optional[int] = None,
    flow_kind: Optional[str] = None,
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Send a specific flow day's messages for a single patient.

    Async-native Taskiq replacement for the Celery send_flow_day_for_patient task.
    On-demand (no schedule). Uses SmartRetryMiddleware for retry logic.

    Args:
        patient_id: Patient UUID string.
        day_number: Optional day number to send. If None, selects first multi-message day.
        flow_kind: Optional flow kind override (onboarding, daily_follow_up, quiz_mensal).
        db: Async database session (injected by TaskiqDepends).

    Returns:
        Dict with status, patient_id, flow_kind, day_number, and result.
    """
    start_time = log_task_start(
        "send_flow_day_for_patient",
        patient_id=patient_id,
        day_number=day_number,
        flow_kind=flow_kind,
    )

    try:
        from app.models.patient import Patient
        from app.models.flow import PatientFlowState
        from app.services.flow.sequential_message_handler import SequentialMessageHandler

        # Look up patient
        patient_result = await db.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        patient = patient_result.scalar_one_or_none()

        if not patient:
            log_task_success(
                "send_flow_day_for_patient",
                start_time,
                status="patient_not_found",
            )
            return {
                "status": "error",
                "message": "patient_not_found",
                "patient_id": patient_id,
            }

        # Find active flow state
        flow_state_result = await db.execute(
            select(PatientFlowState)
            .where(
                PatientFlowState.patient_id == patient.id,
                PatientFlowState.status == "active",
            )
            .order_by(PatientFlowState.updated_at.desc())
            .limit(1)
        )
        flow_state = flow_state_result.scalar_one_or_none()

        # Resolve flow kind
        resolved_flow_kind = flow_kind
        if not resolved_flow_kind and flow_state and flow_state.step_data:
            resolved_flow_kind = flow_state.step_data.get("flow_kind")
        if not resolved_flow_kind:
            current_day = getattr(patient, "current_day", None) or 1
            if current_day <= 15:
                resolved_flow_kind = "onboarding"
            elif current_day <= 45:
                resolved_flow_kind = "daily_follow_up"
            else:
                resolved_flow_kind = "quiz_mensal"

        # Load template steps for the flow kind
        row = await db.execute(
            text("""
                SELECT ftv.steps
                FROM flow_template_versions ftv
                JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
                WHERE fk.kind_key = :kind AND ftv.is_active = true
                ORDER BY ftv.updated_at DESC
                LIMIT 1
            """),
            {"kind": resolved_flow_kind},
        )
        row_result = row.fetchone()
        steps = row_result[0] if row_result and row_result[0] else []

        # Resolve day number
        resolved_day = day_number
        if resolved_day is None:
            for step in steps:
                messages = step.get("messages") or []
                if len(messages) > 1:
                    resolved_day = step.get("day")
                    break

        if resolved_day is None:
            log_task_success(
                "send_flow_day_for_patient",
                start_time,
                status="no_multi_message_day_found",
            )
            return {
                "status": "error",
                "message": "no_multi_message_day_found",
                "patient_id": str(patient.id),
                "flow_kind": resolved_flow_kind,
            }

        if not any((step or {}).get("day") == resolved_day for step in steps):
            log_task_success(
                "send_flow_day_for_patient",
                start_time,
                status="invalid_day_for_flow_template",
            )
            return {
                "status": "error",
                "message": "invalid_day_for_flow_template",
                "patient_id": str(patient.id),
                "flow_kind": resolved_flow_kind,
                "day_number": resolved_day,
            }

        # SequentialMessageHandler expects sync session — use sync context
        from app.database import get_scoped_session as get_sync_session

        with get_sync_session() as sync_db:
            handler = SequentialMessageHandler(sync_db, use_sync_agent_bridge=True)
            send_result = await handler.send_day_messages(
                patient_id=patient.id,
                day_number=resolved_day,
                flow_kind=resolved_flow_kind,
            )

        result = {
            "status": "ok",
            "patient_id": str(patient.id),
            "flow_kind": resolved_flow_kind,
            "day_number": resolved_day,
            "result": send_result,
        }

        log_task_success(
            "send_flow_day_for_patient",
            start_time,
            patient_id=str(patient.id),
            flow_kind=resolved_flow_kind,
            day_number=resolved_day,
        )
        return result

    except Exception as exc:
        log_task_error(
            "send_flow_day_for_patient",
            exc,
            start_time,
            patient_id=patient_id,
        )
        raise


# ===========================================================================
# 7. process_monthly_quizzes — periodic (3600s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 3600}, "kwargs": {"limit": 50}}],
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def process_monthly_quizzes(
    limit: int = 50,
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Process monthly quiz triggers for eligible patients.

    Async-native Taskiq replacement for the Celery process_monthly_quizzes task.
    The original used ``run_async()`` bridge to call the async quiz trigger service.
    Here the service is called directly.

    Runs every hour (3600s). Checks patients eligible for monthly quizzes
    and triggers quiz sessions for them.

    Args:
        limit: Maximum number of patients to check.
        db: Async database session (injected by TaskiqDepends).

    Returns:
        Dict with quiz processing results.
    """
    start_time = log_task_start("process_monthly_quizzes", limit=limit)

    try:
        from app.database import get_scoped_session
        from app.domain.quizzes.integration.flow_integration.utils import (
            get_quiz_trigger_service,
        )

        # Quiz trigger service uses sync ORM via get_scoped_session
        with get_scoped_session() as sync_db:
            quiz_trigger_service = get_quiz_trigger_service(sync_db)
            results = await quiz_trigger_service.check_and_trigger_monthly_quizzes(
                limit=limit,
            )

        logger.info("Monthly quiz processing completed: %s", results)

        log_task_success(
            "process_monthly_quizzes",
            start_time,
            results=str(results),
        )
        return results

    except Exception as exc:
        log_task_error("process_monthly_quizzes", exc, start_time, limit=limit)
        raise


# ===========================================================================
# 8. generate_quiz_report — on-demand with retry
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=30,
)
async def generate_quiz_report(
    session_id: str,
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Generate medical report from completed quiz session.

    Async-native Taskiq replacement for the Celery generate_quiz_report task.
    The original used ``run_async()`` bridge. Here the report generator
    is called directly as async.

    Args:
        session_id: Quiz session ID as string.
        db: Async database session (injected by TaskiqDepends).

    Returns:
        Dict with status, session_id, report_id, and generated_at.
    """
    start_time = log_task_start("generate_quiz_report", session_id=session_id)

    try:
        from app.services.reporting.quiz_report_generator import (
            get_quiz_report_generator,
        )
        from app.database import get_scoped_session

        # Report generator uses sync ORM via get_scoped_session
        with get_scoped_session() as sync_db:
            report_generator = get_quiz_report_generator(sync_db)
            report_id = await report_generator.generate_quiz_report(UUID(session_id))

        result = {
            "status": "success",
            "session_id": session_id,
            "report_id": str(report_id),
            "generated_at": now_sao_paulo().isoformat(),
        }

        logger.info("Quiz report generated successfully: %s", result)

        log_task_success(
            "generate_quiz_report",
            start_time,
            session_id=session_id,
            report_id=str(report_id),
        )
        return result

    except Exception as exc:
        log_task_error("generate_quiz_report", exc, start_time, session_id=session_id)
        raise


# ===========================================================================
# 9. detect_stuck_flows — periodic (900s)
# ===========================================================================

_SKIPPED_RECOVERY_STATUSES = {
    "already_recovering",
    "max_attempts_exceeded",
    "no_longer_stuck",
}


@broker.task(
    schedule=[{"interval": {"seconds": 900}}],
    retry_on_error=True,
    max_retries=1,
    delay=60,
)
async def detect_stuck_flows() -> dict[str, Any]:
    """Detect stuck flows and attempt bounded recovery for each one.

    Async-native Taskiq replacement for the Celery detect_stuck_flows task.
    Runs every 15 minutes (900s).

    Uses ``get_scoped_session()`` (sync) because ``find_stuck_flows``
    operates on sync ORM. ``attempt_recovery`` is async and must be awaited.

    Returns:
        Dict with detected_count, recovered_count, skipped_count, failed_count.
    """
    start_time = log_task_start("detect_stuck_flows")

    try:
        from app.core.redis_manager import get_redis_manager
        from app.database import get_scoped_session
        from app.services.flow.recovery import find_stuck_flows, attempt_recovery

        summary: dict[str, Any] = {
            "detected_count": 0,
            "recovered_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "timestamp": now_sao_paulo().isoformat(),
        }

        with get_scoped_session() as db:
            redis_client = get_redis_manager().get_sync_client()
            stuck_flows = find_stuck_flows(db)
            summary["detected_count"] = len(stuck_flows)

            if not stuck_flows:
                logger.info("No stuck flows detected", extra=summary)
                log_task_success("detect_stuck_flows", start_time, **summary)
                return summary

            for flow_state in stuck_flows:
                try:
                    result = await attempt_recovery(db, flow_state, redis_client)
                except Exception:
                    summary["failed_count"] += 1
                    logger.exception(
                        "Failed to recover stuck flow",
                        extra={
                            "flow_state_id": str(flow_state.id),
                            "patient_id": str(flow_state.patient_id),
                        },
                    )
                    continue

                status = result.get("status")
                if status == "recovered":
                    summary["recovered_count"] += 1
                elif status in _SKIPPED_RECOVERY_STATUSES:
                    summary["skipped_count"] += 1
                else:
                    summary["failed_count"] += 1
                    logger.warning(
                        "Stuck flow recovery returned unexpected status",
                        extra={
                            "flow_state_id": str(flow_state.id),
                            "patient_id": str(flow_state.patient_id),
                            "status": status,
                        },
                    )

        logger.info("Completed stuck flow detection run", extra=summary)
        log_task_success("detect_stuck_flows", start_time, **summary)
        return summary

    except Exception as exc:
        log_task_error("detect_stuck_flows", exc, start_time)
        raise


# ===========================================================================
# 10. monitor_flow_task_health — periodic (300s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 300}}],
    retry_on_error=True,
    max_retries=2,
    delay=30,
)
async def monitor_flow_task_health(
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Monitor flow task health and system connectivity.

    Async-native Taskiq replacement for the Celery monitor_flow_task_health task.
    Runs every 5 minutes (300s).

    The original Celery task used ``run_async_in_sync()`` / ``run_async_in_thread()``
    bridges for the Gemini health check. Here we call ``await`` directly.

    DB queries converted from sync ORM ``db.query()`` to async ``select()``.
    Redis operations remain sync (sync client from RedisManager).

    Returns:
        Dict with health check results (database, redis, gemini, counts, overall).
    """
    start_time = log_task_start("monitor_flow_task_health")

    try:
        from app.models.flow import PatientFlowState
        from app.models.message import Message, MessageStatus
        from app.models.patient import Patient
        from app.ai.client import get_gemini_client

        health_results: dict[str, Any] = {
            "database_connection": False,
            "redis_connection": False,
            "gemini_client": False,
            "active_flows_count": 0,
            "pending_messages_count": 0,
            "failed_tasks_count": 0,
            "timestamp": now_sao_paulo().isoformat(),
        }

        # Test database connection
        try:
            await db.execute(text("SELECT 1"))
            health_results["database_connection"] = True
        except Exception as e:
            logger.error("Database health check failed: %s", e)

        # Test Redis connection using centralized RedisManager
        try:
            from app.core.redis_manager import get_redis_manager

            manager = get_redis_manager()
            redis_client = manager.get_sync_client()
            redis_client.ping()
            health_results["redis_connection"] = True
        except Exception as e:
            logger.error("Redis health check failed: %s", e)

        # Test Gemini client — direct await, no run_async_in_sync bridge
        try:
            gemini_client = get_gemini_client()
            from app.config.settings.tasks import HEALTH_CHECK_TIMEOUT

            health_results["gemini_client"] = await asyncio.wait_for(
                gemini_client.health_check(),
                timeout=HEALTH_CHECK_TIMEOUT,
            )
        except Exception as e:
            logger.error("Gemini client health check failed: %s", e)

        # Count active flows (async select — replaces sync db.query())
        try:
            from app.config.settings.tasks import HEALTH_ACTIVE_FLOWS_LIMIT

            active_result = await db.execute(
                select(PatientFlowState.id)
                .join(Patient)
                .where(
                    PatientFlowState.completed_at.is_(None),
                    Patient.deleted_at.is_(None),
                )
                .limit(HEALTH_ACTIVE_FLOWS_LIMIT)
            )
            health_results["active_flows_count"] = len(active_result.all())
        except Exception as e:
            logger.error("Failed to count active flows: %s", e)

        # Count pending messages (async select — replaces sync db.query())
        try:
            from app.config.settings.tasks import HEALTH_ACTIVE_FLOWS_LIMIT as msg_limit

            pending_result = await db.execute(
                select(Message.id)
                .where(Message.status == MessageStatus.PENDING)
                .limit(msg_limit)
            )
            health_results["pending_messages_count"] = len(pending_result.all())
        except Exception as e:
            logger.error("Failed to count pending messages: %s", e)

        # Check for failed tasks in Redis using centralized RedisManager
        try:
            from app.core.redis_manager import get_redis_manager as _get_rm

            _manager = _get_rm()
            _redis = _manager.get_sync_client()

            failed_count = 0
            scanned_count = 0
            max_scan = 500

            for task_key in _redis.scan_iter(match="task_result:*", count=100):
                scanned_count += 1
                if scanned_count > max_scan:
                    break
                task_data = _redis.get(task_key)
                if task_data and "failure" in str(task_data):
                    failed_count += 1

            health_results["failed_tasks_count"] = failed_count
            health_results["failed_tasks_scanned"] = min(scanned_count, max_scan)
        except Exception as e:
            logger.error("Failed to check task failures: %s", e)

        # Overall health status
        health_results["overall_healthy"] = all([
            health_results["database_connection"],
            health_results["redis_connection"],
            health_results["gemini_client"],
        ])

        log_task_success("monitor_flow_task_health", start_time, **health_results)
        return health_results

    except Exception as exc:
        log_task_error("monitor_flow_task_health", exc, start_time)
        return {
            "error": str(exc),
            "timestamp": now_sao_paulo().isoformat(),
            "overall_healthy": False,
        }


# ===========================================================================
# 11. evaluate_flow_alerts — periodic (900s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 900}}],
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def evaluate_flow_alerts(
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Evaluate flow analytics alerts and dispatch notifications.

    Async-native Taskiq replacement for the Celery evaluate_flow_alerts task.
    Runs every 15 minutes (900s).

    The original Celery task used ``run_async_in_sync(service.evaluate_alerts())``
    as a bridge. Here we call ``await service.evaluate_alerts()`` directly.
    ``FlowAlertsService`` accepts ``Any`` session — DbSession (AsyncSession) works.

    Returns:
        Dict with alerts_created count and timestamp.
    """
    start_time = log_task_start("evaluate_flow_alerts")

    try:
        from app.services.flow_alerts import FlowAlertsService

        service = FlowAlertsService(db)
        alerts = await service.evaluate_alerts()

        result = {
            "alerts_created": len(alerts),
            "timestamp": now_sao_paulo().isoformat(),
        }

        log_task_success("evaluate_flow_alerts", start_time, **result)
        return result

    except Exception as exc:
        log_task_error("evaluate_flow_alerts", exc, start_time)
        raise


# ===========================================================================
# 12. cleanup_old_flow_data — periodic (86400s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 86400}, "kwargs": {"days_old": 90}}],
    retry_on_error=True,
    max_retries=2,
    delay=120,
)
async def cleanup_old_flow_data(
    days_old: int = 90,
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Clean up old flow data for maintenance.

    Async-native Taskiq replacement for the Celery cleanup_old_flow_data task.
    Runs daily (86400s). Translates sync ORM queries to async ``select()`` with
    DbSession (AsyncSession).

    Archives completed flows to Redis before deletion, then cleans up old
    messages in terminal states.

    Args:
        days_old: Age threshold for cleanup in days (default 90).
        db: Async database session (injected by TaskiqDepends).

    Returns:
        Dict with completed_flows_cleaned, old_messages_cleaned counts.
    """
    start_time = log_task_start("cleanup_old_flow_data", days_old=days_old)

    try:
        import json
        from datetime import timedelta

        from app.models.flow import PatientFlowState
        from app.models.message import Message, MessageStatus

        cutoff_date = now_sao_paulo() - timedelta(days=days_old)

        results: dict[str, Any] = {
            "completed_flows_cleaned": 0,
            "old_messages_cleaned": 0,
            "analytics_cleaned": 0,
            "cutoff_date": cutoff_date.isoformat(),
            "start_time": now_sao_paulo().isoformat(),
        }

        # Clean up completed flows older than threshold (async select)
        flow_result = await db.execute(
            select(PatientFlowState).where(
                PatientFlowState.completed_at < cutoff_date,
                PatientFlowState.completed_at.isnot(None),
            )
        )
        completed_flows = flow_result.scalars().all()

        for flow in completed_flows:
            # Archive important data before deletion
            archive_data = {
                "patient_id": str(flow.patient_id),
                "flow_type": flow.flow_type,
                "completed_at": (
                    flow.completed_at.isoformat() if flow.completed_at else None
                ),
                "final_state": flow.state_data,
            }

            # Store in Redis for historical reference
            try:
                from app.core.redis_manager import get_cache_redis_manager
                from app.config.settings.tasks import ARCHIVE_RETENTION_DAYS

                manager = get_cache_redis_manager()
                redis_client = manager.get_sync_client()
                redis_client.setex(
                    f"archived_flow:{flow.id}",
                    86400 * ARCHIVE_RETENTION_DAYS,
                    json.dumps(archive_data, default=str),
                )
            except Exception as redis_error:
                logger.warning("Failed to archive flow data to Redis: %s", redis_error)

            await db.delete(flow)
            results["completed_flows_cleaned"] += 1

        # Clean up old messages in terminal states (async select)
        msg_result = await db.execute(
            select(Message).where(
                Message.created_at < cutoff_date,
                Message.status.in_([
                    MessageStatus.DELIVERED,
                    MessageStatus.READ,
                    MessageStatus.FAILED,
                ]),
            )
        )
        old_messages = msg_result.scalars().all()

        for message in old_messages:
            await db.delete(message)
            results["old_messages_cleaned"] += 1

        await db.commit()
        results["end_time"] = now_sao_paulo().isoformat()

        logger.info("Flow data cleanup completed: %s", results)
        log_task_success("cleanup_old_flow_data", start_time, **results)
        return results

    except Exception as exc:
        await db.rollback()
        log_task_error("cleanup_old_flow_data", exc, start_time, days_old=days_old)
        raise


# ===========================================================================
# 13. retry_failed_flow_send — on-demand with retry (SmartRetryMiddleware)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=5,
    delay=60,
)
async def retry_failed_flow_send(
    message_id: str,
    flow_context: dict[str, Any] | None = None,
    context: Context = TaskiqDepends(),
) -> dict[str, Any]:
    """Retry a failed outbound flow message send with exponential backoff.

    Async-native Taskiq replacement for the Celery retry_failed_flow_send task.
    On-demand (no schedule). SmartRetryMiddleware replaces ``self.retry(countdown=)``.

    Translation:
      - ``self.request.retries`` → ``context.message.labels.get('_retries', 0)``
      - ``self.retry(countdown=)`` → raise exception, middleware applies backoff + jitter
      - ``MaxRetriesExceededError`` → check ``retries >= max_retries`` in task body
      - ``async_to_sync(whatsapp_service.send_message)`` → ``await ...`` directly
      - DLQ routing on permanent failure via structured return + log signal

    Uses ``get_scoped_session()`` for sync ORM operations (message queries,
    FlowStateRepository). WhatsApp send is awaited directly.

    Args:
        message_id: Message UUID string to retry.
        flow_context: Optional flow context dict for the send.
        context: Taskiq context (injected, provides retry count).

    Returns:
        Dict with status, message_id, attempt count, and DLQ info on failure.
    """
    retries = int(context.message.labels.get("_retries", 0))
    _max_retries = 5

    start_time = log_task_start(
        "retry_failed_flow_send",
        message_id=message_id,
        attempt=retries + 1,
    )

    try:
        message_uuid = UUID(str(message_id))
    except (TypeError, ValueError):
        return {"status": "invalid_message_id", "message_id": str(message_id)}

    from app.database import get_scoped_session
    from app.exceptions import ExternalServiceError
    from app.models.message import Message, MessageStatus
    from app.services.unified_whatsapp_service import UnifiedWhatsAppService
    from app.tasks.helpers.flow_helpers import (
        _TERMINAL_MESSAGE_STATUSES,
        _record_permanent_delivery_failure,
        _resolve_flow_context,
    )

    with get_scoped_session() as db:
        message = db.query(Message).filter(Message.id == message_uuid).first()
        if not message:
            return {"status": "message_not_found", "message_id": str(message_id)}

        if message.status in _TERMINAL_MESSAGE_STATUSES:
            return {
                "status": "already_finalized",
                "message_id": str(message.id),
                "message_status": message.status.value,
            }

        resolved_flow_context = _resolve_flow_context(message, flow_context)
        attempt = retries + 1

        if message.status == MessageStatus.FAILED:
            message.status = MessageStatus.PENDING

        message.retry_count = attempt
        message.last_retry_at = now_sao_paulo()
        message.next_retry_at = None
        message.failure_reason = None
        db.add(message)
        db.commit()

        whatsapp_service = UnifiedWhatsAppService(db)

        try:
            # Direct await — no async_to_sync bridge
            success = await whatsapp_service.send_message(
                message,
                flow_context=resolved_flow_context,
            )
            if not success:
                raise ExternalServiceError(
                    f"Flow message retry returned False for message {message.id}"
                )

            log_task_success(
                "retry_failed_flow_send",
                start_time,
                message_id=str(message.id),
                attempt=attempt,
            )
            return {
                "status": "ok",
                "message_id": str(message.id),
                "attempt": attempt,
            }

        except ExternalServiceError as exc:
            message.failure_reason = str(exc)
            db.add(message)
            db.commit()

            # Max retries reached → permanent failure + DLQ routing
            if retries >= _max_retries:
                message.status = MessageStatus.FAILED
                message.next_retry_at = None
                message.retry_count = attempt
                metadata = dict(message.message_metadata or {})
                metadata["permanently_failed_at"] = now_sao_paulo().isoformat()
                if resolved_flow_context is not None:
                    metadata["flow_context"] = resolved_flow_context
                message.message_metadata = metadata

                db.add(message)
                _record_permanent_delivery_failure(message, db)
                db.commit()

                logger.error(
                    "Flow message send permanently failed after retry exhaustion",
                    extra={
                        "message_id": str(message.id),
                        "patient_id": str(message.patient_id),
                        "attempts": _max_retries,
                        "dlq_routed": True,
                    },
                )
                log_task_error(
                    "retry_failed_flow_send",
                    exc,
                    start_time,
                    message_id=str(message.id),
                    permanently_failed=True,
                )
                return {
                    "status": "permanently_failed",
                    "message_id": str(message.id),
                    "attempts": _max_retries,
                    "permanently_failed": True,
                    "dlq_routed": True,
                }

            logger.warning(
                "Retrying failed flow message send",
                extra={
                    "message_id": str(message.id),
                    "patient_id": str(message.patient_id),
                    "attempt": attempt,
                },
            )

            # Raise to let SmartRetryMiddleware handle retry scheduling
            raise


# ===========================================================================
# 14. retry_failed_followup_send — on-demand with retry (SmartRetryMiddleware)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=30,
)
async def retry_failed_followup_send(
    action_id: str,
    patient_id: str,
    parameters: dict | None = None,
    follow_up_type: str = "conversation_continuation",
    priority: str = "normal",
    context: Context = TaskiqDepends(),
) -> dict[str, Any]:
    """Retry a failed deferred follow-up send with exponential backoff.

    Async-native Taskiq replacement for the Celery retry_failed_followup_send task.
    On-demand (no schedule). SmartRetryMiddleware replaces ``self.retry(countdown=)``.

    Translation:
      - ``self.request.retries`` → ``context.message.labels.get('_retries', 0)``
      - ``self.retry(countdown=)`` → raise exception, middleware applies backoff + jitter
      - ``MaxRetriesExceededError`` → check ``retries >= max_retries`` in task body
      - ``async_to_sync(service.method)`` → ``await service.method()`` directly
      - DLQ routing on permanent failure via structured return + log signal

    Uses ``get_scoped_session()`` for ``FollowUpSystemService`` (sync ORM).
    Async service methods are awaited directly.

    Args:
        action_id: Follow-up action UUID string.
        patient_id: Patient UUID string.
        parameters: Optional action parameters.
        follow_up_type: Follow-up type (default: conversation_continuation).
        priority: Priority level (default: normal).
        context: Taskiq context (injected, provides retry count).

    Returns:
        Dict with status, action_id, attempt count, and DLQ info on failure.
    """
    retries = int(context.message.labels.get("_retries", 0))
    _max_retries = 3

    start_time = log_task_start(
        "retry_failed_followup_send",
        action_id=action_id,
        patient_id=patient_id,
        attempt=retries + 1,
    )

    from app.tasks.helpers.flow_helpers import _build_retry_action

    try:
        retry_action = _build_retry_action(
            action_id=action_id,
            patient_id=patient_id,
            parameters=parameters,
            follow_up_type=follow_up_type,
            priority=priority,
        )
    except (TypeError, ValueError) as exc:
        return {
            "status": "invalid_action",
            "action_id": str(action_id),
            "error": str(exc),
        }

    if retry_action is None:
        return {"status": "action_not_found", "action_id": str(action_id)}

    from app.database import get_scoped_session

    with get_scoped_session() as db:
        from app.services.follow_up_system.service import FollowUpSystemService

        follow_up_service = FollowUpSystemService(db, auto_rehydrate=False)

        try:
            # Direct await — no async_to_sync bridge
            success = await follow_up_service.action_executor._schedule_message_action(
                retry_action,
            )
            if not success:
                raise RuntimeError(
                    f"Follow-up retry returned False for action {retry_action.action_id}"
                )

            executed_at = now_sao_paulo()
            await follow_up_service.redis_store.update_action_status(
                action_id=retry_action.action_id,
                status="executed",
                executed_at=executed_at,
                execution_result=retry_action.execution_result,
            )

            log_task_success(
                "retry_failed_followup_send",
                start_time,
                action_id=str(retry_action.action_id),
                attempt=retries + 1,
            )
            return {
                "status": "ok",
                "action_id": str(retry_action.action_id),
                "attempt": retries + 1,
            }

        except Exception as exc:
            # Max retries reached → permanent failure + DLQ routing
            if retries >= _max_retries:
                executed_at = now_sao_paulo()
                execution_result = {
                    "error": str(exc),
                    "retry_exhausted": True,
                    "attempts": _max_retries,
                }
                await follow_up_service.redis_store.update_action_status(
                    action_id=retry_action.action_id,
                    status="failed",
                    executed_at=executed_at,
                    execution_result=execution_result,
                )

                logger.error(
                    "Follow-up send permanently failed after retry exhaustion",
                    extra={
                        "action_id": str(retry_action.action_id),
                        "patient_id": str(retry_action.patient_id),
                        "attempts": _max_retries,
                        "dlq_routed": True,
                    },
                )
                log_task_error(
                    "retry_failed_followup_send",
                    exc,
                    start_time,
                    action_id=str(retry_action.action_id),
                    permanently_failed=True,
                )
                return {
                    "status": "permanently_failed",
                    "action_id": str(retry_action.action_id),
                    "attempts": _max_retries,
                    "dlq_routed": True,
                }

            logger.warning(
                "Retrying failed follow-up send",
                extra={
                    "action_id": str(retry_action.action_id),
                    "patient_id": str(retry_action.patient_id),
                    "attempt": retries + 1,
                },
            )

            # Raise to let SmartRetryMiddleware handle retry scheduling
            raise
ise
