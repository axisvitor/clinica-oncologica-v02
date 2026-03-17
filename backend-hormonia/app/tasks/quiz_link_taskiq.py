"""
Taskiq quiz link tasks — async-native replacements for Celery quiz_link_tasks (M009-S04).

6 tasks migrated from Celery to Taskiq:
  1. check_expired_links         — interval 1800s (periodic expired link scanning)
  2. rotate_expired_token        — on-demand (generates new token for expired link)
  3. send_quiz_reminder          — on-demand with SmartRetryMiddleware (resilient delivery)
  4. fallback_to_whatsapp        — on-demand (WhatsApp conversational fallback)
  5. process_dead_letter_queue   — interval 7200s (periodic DLQ processing)
  6. monitor_resilience_metrics  — interval 3600s (periodic resilience health check)

Key translation patterns from Celery → Taskiq:
  - QuizLinkTask base class removed: SmartRetryMiddleware handles retries externally
  - self (bind=True) removed: no Celery task instance
  - get_db_session() (Celery base) → get_scoped_session() (sync ORM)
  - async_to_sync(quiz_service.method)() → await quiz_service.method()
  - .delay() cross-dispatch → await .kiq() for Taskiq
  - Manual retry countdown [3600, 7200, 14400] → SmartRetryMiddleware exponential backoff
  - Distributed lock pattern preserved (not Celery-specific)
  - Pure helpers imported from Celery module to avoid duplication

Schedule labels (3 tasks are periodic):
  - check_expired_links: interval 1800s (every 30 minutes)
  - process_dead_letter_queue: interval 7200s (every 2 hours)
  - monitor_resilience_metrics: interval 3600s (every hour)
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict
from uuid import UUID

from app.core.distributed_lock import get_distributed_lock
from app.database import get_scoped_session
from app.domain.quizzes.delivery import LinkBuilder
from app.domain.quizzes.resilience import FailureReason, QuizLinkResilienceService
from app.domain.quizzes.session.factory import generate_unique_short_code
from app.services.monthly_quiz_message_integration import MonthlyQuizMessageIntegration
from app.taskiq_broker import broker
from app.tasks.quiz_link_tasks import (
    _sanitize_dlq_record,
    _sanitize_error_message,
    _sanitize_limit,
    _token_fingerprint,
)
from app.tasks.taskiq_base import log_task_error, log_task_start, log_task_success
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger("app.tasks.quiz_link_taskiq")


# ===========================================================================
# 1. check_expired_links — periodic (interval 1800s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 1800}}],
)
async def check_expired_links(limit: int = 100) -> Dict[str, Any]:
    """Periodic task to check expired quiz links and trigger regeneration.

    Scans for expired quiz links and dispatches rotate_expired_token tasks
    for each one found.

    Args:
        limit: Maximum number of expired links to process.

    Returns:
        Dict with expired_count, processed_count, results.
    """
    start_time = log_task_start("check_expired_links", limit=limit)
    limit = _sanitize_limit(limit)

    try:
        with get_scoped_session() as db:
            resilience_service = QuizLinkResilienceService(db)
            expired_links = resilience_service.check_expired_links(limit=limit)

            if not expired_links:
                log_task_success("check_expired_links", start_time, expired_count=0)
                return {"success": True, "expired_count": 0, "processed_count": 0}

            results: Dict[str, list] = {"regenerated": [], "failed": []}

            for link_info in expired_links:
                try:
                    await rotate_expired_token.kiq(
                        session_id=str(link_info["session_id"]),
                        patient_id=str(link_info["patient_id"]),
                        quiz_template_id=str(link_info["quiz_template_id"]),
                    )
                    results["regenerated"].append(str(link_info["session_id"]))
                except Exception as e:
                    logger.error(
                        "Failed to dispatch rotate_expired_token for session %s: %s",
                        link_info["session_id"],
                        e,
                    )
                    results["failed"].append(
                        {"session_id": str(link_info["session_id"]), "error": str(e)}
                    )

            log_task_success(
                "check_expired_links",
                start_time,
                expired_count=len(expired_links),
                processed_count=len(results["regenerated"]),
            )
            return {
                "success": True,
                "expired_count": len(expired_links),
                "processed_count": len(results["regenerated"]),
                "results": results,
            }

    except Exception as exc:
        log_task_error("check_expired_links", exc, start_time)
        raise


# ===========================================================================
# 2. rotate_expired_token — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def rotate_expired_token(
    session_id: str, patient_id: str, quiz_template_id: str
) -> Dict[str, Any]:
    """Generate new token for expired link with fallback logic.

    Args:
        session_id: Quiz session UUID string.
        patient_id: Patient UUID string.
        quiz_template_id: Quiz template UUID string.

    Returns:
        Dict with rotation action and result.
    """
    start_time = log_task_start("rotate_expired_token", session_id=session_id)

    try:
        with get_scoped_session() as db:
            resilience_service = QuizLinkResilienceService(db)

            result = resilience_service.handle_expired_token(
                session_id=UUID(session_id),
                patient_id=UUID(patient_id),
                quiz_template_id=UUID(quiz_template_id),
            )

            action = result.get("action")

            if action == "regenerated":
                await send_quiz_reminder.kiq(
                    session_id=session_id,
                    patient_id=patient_id,
                    is_regenerated=True,
                )
                logger.info("Token regenerated for session %s", session_id)

            elif action == "fallback_to_whatsapp":
                await fallback_to_whatsapp.kiq(
                    session_id=session_id,
                    patient_id=patient_id,
                    quiz_template_id=quiz_template_id,
                )
                logger.info("Fallback to WhatsApp triggered for session %s", session_id)

            log_task_success("rotate_expired_token", start_time, action=action)
            return {"success": True, **result}

    except Exception as exc:
        # Track failure before re-raising for SmartRetryMiddleware
        try:
            with get_scoped_session() as db:
                resilience_service = QuizLinkResilienceService(db)
                resilience_service.track_failure(
                    session_id=UUID(session_id),
                    reason=FailureReason.TOKEN_EXPIRED,
                    details={"error": _sanitize_error_message(exc)},
                )
        except Exception as track_error:
            logger.error("Failed to track failure: %s", track_error)

        log_task_error("rotate_expired_token", exc, start_time, session_id=session_id)
        raise


# ===========================================================================
# 3. send_quiz_reminder — on-demand with SmartRetryMiddleware
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=3600,
)
async def send_quiz_reminder(
    session_id: str,
    patient_id: str,
    token: str | None = None,
    is_regenerated: bool = False,
) -> Dict[str, Any]:
    """Send quiz reminder with distributed locking and circuit breaker.

    SmartRetryMiddleware handles retries with exponential backoff
    (base 3600s → ~7200s → ~14400s), replacing Celery's manual
    countdown pattern.

    Args:
        session_id: Quiz session UUID string.
        patient_id: Patient UUID string.
        token: Quiz access token (fetched internally when omitted).
        is_regenerated: Whether this is a regenerated link.

    Returns:
        Dict with delivery result.
    """
    start_time = log_task_start(
        "send_quiz_reminder",
        session_id=session_id,
        is_regenerated=is_regenerated,
    )

    lock = get_distributed_lock()
    lock_key = f"quiz:reminder:session:{session_id}"
    lock_id = None
    lock_guard_enabled = True
    delivery_channel = "unknown"

    try:
        # Acquire distributed lock for deduplication
        try:
            lock_id = lock.try_acquire_sync(lock_key, ttl=120)
        except Exception as lock_error:
            logger.warning(
                "Failed to acquire distributed reminder lock (%s), proceeding without lock",
                lock_error,
            )
            lock_guard_enabled = False

        if lock_guard_enabled and lock_id is None:
            log_task_success("send_quiz_reminder", start_time, status="skipped_locked")
            return {
                "success": True,
                "session_id": session_id,
                "status": "skipped_locked",
                "idempotent": True,
            }

        with get_scoped_session() as db:
            resilience_service = QuizLinkResilienceService(db)
            message_integration = MonthlyQuizMessageIntegration(db)

            session = resilience_service.session_repository.get(UUID(session_id))
            if not session:
                raise ValueError(f"Session {session_id} not found")
            if str(session.patient_id) != patient_id:
                raise ValueError(f"Session/patient mismatch for session {session_id}")

            # Fetch token if not provided — avoid carrying secret in task payload
            if not token:
                from app.services.quiz.quiz_service import MonthlyQuizService

                quiz_service = MonthlyQuizService(db)
                quiz_link = await quiz_service.get_quiz_link_status(UUID(session_id))
                if quiz_link.status.value != "active" or not quiz_link.token:
                    raise ValueError(
                        f"No active quiz token available for session {session_id}"
                    )
                token = quiz_link.token

            metadata = session.session_metadata or {}
            preferred_channel = metadata.get("delivery_method", "whatsapp")
            last_reminder_at = metadata.get("last_reminder_sent_at")
            last_reminder_hash = metadata.get("last_reminder_token_hash")
            current_token_hash = _token_fingerprint(token)

            # Duplicate detection — skip if same token reminder sent within 15 min
            if (
                not is_regenerated
                and isinstance(last_reminder_at, str)
                and last_reminder_hash == current_token_hash
            ):
                try:
                    last_reminder_dt = datetime.fromisoformat(last_reminder_at)
                    if last_reminder_dt.tzinfo is None:
                        last_reminder_dt = last_reminder_dt.replace(
                            tzinfo=now_sao_paulo().tzinfo
                        )
                    elapsed = now_sao_paulo() - last_reminder_dt
                    if elapsed.total_seconds() < 15 * 60:
                        logger.info(
                            "Skipping duplicate reminder for session %s (elapsed=%ss)",
                            session_id,
                            int(elapsed.total_seconds()),
                        )
                        log_task_success(
                            "send_quiz_reminder", start_time, status="duplicate_skipped"
                        )
                        return {
                            "success": True,
                            "session_id": session_id,
                            "status": "duplicate_skipped",
                            "idempotent": True,
                        }
                except ValueError:
                    pass

            # Circuit breaker — check if we should use alternative channel
            should_use_alt, alt_channel = (
                resilience_service.should_use_alternative_channel(preferred_channel)
            )
            delivery_channel = alt_channel if should_use_alt else preferred_channel

            # Build short link
            metadata = session.session_metadata or {}
            short_code = metadata.get("short_code")
            if not short_code:
                short_code = generate_unique_short_code(db)
                metadata["short_code"] = short_code
                session.session_metadata = metadata
                db.commit()
                db.refresh(session)

            link_builder = LinkBuilder()
            link_url = link_builder.build_preferred_link(token, short_code)

            message_type = "regenerated_reminder" if is_regenerated else "reminder"

            if is_regenerated:
                message_text = (
                    f"Seu link do quiz mensal foi renovado! 🔄\n\n"
                    f"Acesse aqui: {link_url}\n\n"
                    f"O link anterior expirou, mas você ainda pode responder o quiz."
                )
            else:
                message_text = (
                    f"Lembrete: Seu quiz mensal está aguardando! 📋\n\n"
                    f"Acesse aqui: {link_url}\n\n"
                    f"Por favor, responda antes que o link expire."
                )

            # Send message via appropriate channel
            result = message_integration.send_quiz_link_message(
                patient_id=UUID(patient_id),
                link_url=link_url,
                custom_message=message_text,
                delivery_method=delivery_channel,
            )

            if not result.get("success"):
                raise Exception(f"Failed to send message: {result.get('error')}")

            # Update session metadata with reminder info
            metadata = dict(session.session_metadata or {})
            sent_at = now_sao_paulo()
            metadata.update(
                {
                    "last_reminder_sent_at": sent_at.isoformat(),
                    "last_reminder_token_hash": current_token_hash,
                    "last_reminder_type": message_type,
                    "last_reminder_channel": delivery_channel,
                    "last_link_reminder_at": sent_at.isoformat(),
                    "last_link_reminder_type": message_type,
                }
            )
            session.session_metadata = metadata
            db.commit()

            log_task_success(
                "send_quiz_reminder",
                start_time,
                session_id=session_id,
                delivery_channel=delivery_channel,
            )
            return {
                "success": True,
                "session_id": session_id,
                "delivery_channel": delivery_channel,
                "used_alternative": should_use_alt,
            }

    except Exception as exc:
        # Track failure for resilience metrics before re-raising
        try:
            with get_scoped_session() as db:
                resilience_service = QuizLinkResilienceService(db)
                resilience_service.track_failure(
                    session_id=UUID(session_id),
                    reason=FailureReason.DELIVERY_FAILED,
                    details={
                        "error": _sanitize_error_message(exc),
                        "channel": delivery_channel,
                    },
                )
        except Exception as track_error:
            logger.error("Failed to track failure: %s", track_error)

        log_task_error("send_quiz_reminder", exc, start_time, session_id=session_id)
        raise

    finally:
        if lock_guard_enabled and lock_id:
            try:
                lock.release_sync(lock_key, lock_id)
            except Exception as release_error:
                logger.warning(
                    "Failed to release distributed reminder lock for session %s: %s",
                    session_id,
                    release_error,
                )


# ===========================================================================
# 4. fallback_to_whatsapp — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def fallback_to_whatsapp(
    session_id: str, patient_id: str, quiz_template_id: str
) -> Dict[str, Any]:
    """Switch to WhatsApp conversational flow when link-based approach fails.

    Args:
        session_id: Quiz session UUID string.
        patient_id: Patient UUID string.
        quiz_template_id: Quiz template UUID string.

    Returns:
        Dict with fallback result.
    """
    start_time = log_task_start("fallback_to_whatsapp", session_id=session_id)

    try:
        with get_scoped_session() as db:
            from app.domain.quizzes.integration.flow_integration_service import (
                QuizFlowIntegrationService,
            )

            flow_service = QuizFlowIntegrationService(db)

            result = flow_service.initiate_monthly_quiz_flow(
                patient_id=UUID(patient_id),
                quiz_template_id=UUID(quiz_template_id),
            )

            logger.info(
                "Successfully initiated WhatsApp conversational flow for session %s",
                session_id,
            )
            log_task_success("fallback_to_whatsapp", start_time, session_id=session_id)
            return {
                "success": True,
                "session_id": session_id,
                "fallback_method": "whatsapp_conversational",
                "flow_initiated": True,
                "flow_result": result,
            }

    except Exception as exc:
        log_task_error("fallback_to_whatsapp", exc, start_time, session_id=session_id)
        raise


# ===========================================================================
# 5. process_dead_letter_queue — periodic (interval 7200s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=120,
    schedule=[{"interval": {"seconds": 7200}}],
)
async def process_dead_letter_queue(limit: int = 50) -> Dict[str, Any]:
    """Process items from dead letter queue for manual intervention.

    Args:
        limit: Maximum number of DLQ items to process.

    Returns:
        Dict with DLQ processing results.
    """
    start_time = log_task_start("process_dead_letter_queue", limit=limit)
    limit = _sanitize_limit(limit)

    try:
        with get_scoped_session() as db:
            from app.models.quiz import QuizSession

            sessions = (
                db.query(QuizSession)
                .filter(
                    QuizSession.session_metadata["dead_letter_queue"].astext.isnot(None)
                )
                .limit(limit)
                .all()
            )

            processed = []
            for session in sessions:
                metadata = session.session_metadata or {}
                dlq_records = metadata.get("dead_letter_queue", [])

                if dlq_records:
                    logger.warning(
                        "Session %s has %d DLQ records. Manual intervention required.",
                        session.id,
                        len(dlq_records),
                    )
                    processed.append(
                        {
                            "session_id": str(session.id),
                            "patient_id": str(session.patient_id),
                            "dlq_count": len(dlq_records),
                            "latest_failure": _sanitize_dlq_record(
                                dlq_records[-1] if dlq_records else None
                            ),
                        }
                    )

            log_task_success(
                "process_dead_letter_queue",
                start_time,
                dlq_sessions_count=len(processed),
            )
            return {
                "success": True,
                "dlq_sessions_count": len(processed),
                "sessions_needing_intervention": processed,
            }

    except Exception as exc:
        log_task_error("process_dead_letter_queue", exc, start_time)
        raise


# ===========================================================================
# 6. monitor_resilience_metrics — periodic (interval 3600s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=60,
    schedule=[{"interval": {"seconds": 3600}}],
)
async def monitor_resilience_metrics() -> Dict[str, Any]:
    """Monitor and report quiz link resilience metrics (last 24h).

    Returns:
        Dict with resilience metrics snapshot.
    """
    start_time = log_task_start("monitor_resilience_metrics")

    try:
        with get_scoped_session() as db:
            resilience_service = QuizLinkResilienceService(db)

            end_date = now_sao_paulo()
            start_date = end_date - timedelta(hours=24)

            metrics = resilience_service.get_resilience_metrics(
                start_date=start_date, end_date=end_date
            )

            logger.info(
                "Resilience metrics (24h): Expiry rate: %.2f%%, "
                "Success rate: %.2f%%, Fallback rate: %.2f%%",
                metrics.link_expiry_rate * 100,
                metrics.reminder_success_rate * 100,
                metrics.fallback_activation_rate * 100,
            )

            # Alert on high failure rates
            if metrics.link_expiry_rate > 0.3:
                logger.warning(
                    "HIGH LINK EXPIRY RATE: %.2f%%", metrics.link_expiry_rate * 100
                )

            if metrics.reminder_success_rate < 0.7:
                logger.warning(
                    "LOW REMINDER SUCCESS RATE: %.2f%%",
                    metrics.reminder_success_rate * 100,
                )

            result_metrics = {
                "total_links_created": metrics.total_links_created,
                "expired_links_count": metrics.expired_links_count,
                "regenerated_links_count": metrics.regenerated_links_count,
                "fallback_activations": metrics.fallback_activations,
                "reminder_success_count": metrics.reminder_success_count,
                "reminder_failure_count": metrics.reminder_failure_count,
                "link_expiry_rate": metrics.link_expiry_rate,
                "reminder_success_rate": metrics.reminder_success_rate,
                "fallback_activation_rate": metrics.fallback_activation_rate,
                "average_completion_time_minutes": metrics.average_completion_time_minutes,
                "channel_health": metrics.channel_health,
            }

            log_task_success(
                "monitor_resilience_metrics",
                start_time,
                link_expiry_rate=metrics.link_expiry_rate,
            )
            return {"success": True, "metrics": result_metrics}

    except Exception as exc:
        log_task_error("monitor_resilience_metrics", exc, start_time)
        raise


__all__ = [
    "check_expired_links",
    "rotate_expired_token",
    "send_quiz_reminder",
    "fallback_to_whatsapp",
    "process_dead_letter_queue",
    "monitor_resilience_metrics",
]
