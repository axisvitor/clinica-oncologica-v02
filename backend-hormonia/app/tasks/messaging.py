"""
Celery tasks for message processing and scheduling.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from datetime import date, datetime, time, timedelta

from celery.exceptions import Retry

from app.task_queue import task_queue as celery_app
from app.database import get_scoped_session
from app.domain.messaging.core import MessageService
from app.models.message import (
    DeliveryStatus,
    Message,
    MessageDirection,
    MessageStatus,
    MessageType,
)
from app.exceptions import ExternalServiceError
from app.tasks.base import MessageTask, get_db_session


logger = logging.getLogger(__name__)


# MessageTask is now imported from app.tasks.base


from app.services.unified_whatsapp_service import create_unified_whatsapp_service
from app.utils.async_helpers import run_async

import pytz
from app.utils.date_math import add_months
from app.utils.idempotency import build_message_idempotency_key
from app.utils.timezone import SAO_PAULO_TZ, SAO_PAULO_TZ_NAME, now_sao_paulo
from pytz.exceptions import AmbiguousTimeError, NonExistentTimeError


def _build_idempotency_key(
    patient_id: UUID,
    content: str,
    scheduled_for: datetime,
    message_type: MessageType,
) -> str:
    return build_message_idempotency_key(
        patient_id=patient_id,
        content=content,
        scheduled_for=scheduled_for,
        message_type_value=message_type.value,
    )


def _parse_time_str(time_str: Optional[str]) -> Optional[Tuple[int, int]]:
    if not time_str:
        return None
    try:
        hour_str, minute_str = time_str.split(":")
        hour = int(hour_str)
        minute = int(minute_str)
    except (ValueError, AttributeError):
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def _add_months(base_date: date, months: int) -> date:
    return add_months(base_date, months)


def _compute_next_reminder_time(
    metadata: Dict[str, Any],
    current_scheduled_for: Optional[datetime],
) -> Optional[Tuple[datetime, date]]:
    recurrence = (metadata or {}).get("reminder_recurrence")
    if recurrence not in {"daily", "weekly", "monthly", "interval"}:
        return None

    tz_name = metadata.get("reminder_timezone") or SAO_PAULO_TZ_NAME
    try:
        tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone(SAO_PAULO_TZ_NAME)
        tz_name = SAO_PAULO_TZ_NAME

    base_dt = current_scheduled_for or now_sao_paulo()
    if base_dt.tzinfo is None:
        try:
            base_dt = tz.localize(base_dt, is_dst=None)
        except AmbiguousTimeError:
            base_dt = tz.localize(base_dt, is_dst=False)
        except NonExistentTimeError:
            base_dt = tz.localize(base_dt + timedelta(hours=1), is_dst=True)
    base_local = base_dt.astimezone(tz)

    time_local_str = metadata.get("reminder_time_local")
    parsed_time = _parse_time_str(time_local_str)
    if parsed_time:
        base_time = time(parsed_time[0], parsed_time[1])
    else:
        base_time = base_local.time().replace(microsecond=0)

    date_local_str = metadata.get("reminder_date_local")
    try:
        base_date = datetime.fromisoformat(date_local_str).date()
    except (TypeError, ValueError):
        base_date = base_local.date()

    if recurrence == "daily":
        next_date = base_date + timedelta(days=1)
    elif recurrence == "weekly":
        weekday = metadata.get("reminder_weekday")
        if weekday is not None:
            try:
                weekday = int(weekday)
            except (TypeError, ValueError):
                weekday = None
        if isinstance(weekday, int) and 0 <= weekday <= 6:
            days_ahead = (weekday - base_date.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            next_date = base_date + timedelta(days=days_ahead)
        else:
            next_date = base_date + timedelta(days=7)
    elif recurrence == "monthly":
        next_date = _add_months(base_date, 1)
    else:
        interval_days = metadata.get("reminder_interval_days")
        try:
            interval_days = int(interval_days)
        except (TypeError, ValueError):
            return None
        if interval_days <= 0:
            return None
        next_date = base_date + timedelta(days=interval_days)

    try:
        next_local = tz.localize(datetime.combine(next_date, base_time), is_dst=None)
    except AmbiguousTimeError:
        next_local = tz.localize(datetime.combine(next_date, base_time), is_dst=False)
    except NonExistentTimeError:
        shifted = datetime.combine(next_date, base_time) + timedelta(hours=1)
        next_local = tz.localize(shifted, is_dst=True)
    return next_local.astimezone(SAO_PAULO_TZ), next_date


async def _schedule_next_reminder(message, db) -> bool:
    metadata = message.message_metadata or {}
    recurrence = metadata.get("reminder_recurrence")
    if not recurrence or recurrence == "none":
        return False

    next_info = _compute_next_reminder_time(metadata, message.scheduled_for)
    if not next_info:
        return False

    next_utc, next_date = next_info
    end_at = metadata.get("reminder_end_at")
    if end_at:
        try:
            end_dt = datetime.fromisoformat(end_at)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=SAO_PAULO_TZ)
            if next_utc > end_dt:
                return False
        except ValueError:
            pass

    remaining = metadata.get("reminder_remaining")
    if remaining is not None:
        try:
            remaining = int(remaining)
        except (TypeError, ValueError):
            remaining = None
        if remaining is not None:
            if remaining <= 0:
                return False
            remaining -= 1

    new_metadata = dict(metadata)
    try:
        sequence = int(metadata.get("reminder_sequence", 1))
    except (TypeError, ValueError):
        sequence = 1
    new_metadata["reminder_sequence"] = sequence + 1
    new_metadata["reminder_date_local"] = next_date.isoformat()
    if remaining is not None:
        new_metadata["reminder_remaining"] = remaining

    new_message = Message(
        patient_id=message.patient_id,
        direction=MessageDirection.OUTBOUND,
        type=MessageType(message.type),
        content=message.content,
        status=MessageStatus.PENDING,
        scheduled_for=next_utc,
        message_metadata=new_metadata,
        idempotency_key=_build_idempotency_key(
            patient_id=message.patient_id,
            content=message.content,
            scheduled_for=next_utc,
            message_type=MessageType(message.type),
        ),
    )
    db.add(new_message)
    return True


@celery_app.task(
    bind=True,
    base=MessageTask,
    name="app.tasks.messaging.send_scheduled_message",
)
def send_scheduled_message(self, message_id: str) -> dict[str, Any]:
    """Send a scheduled message to a patient using AsyncSession.

    Args:
        message_id (str): UUID of the message to send

    Returns:
        dict[str, Any]: Dictionary containing:
            - success (bool): Whether the message was sent successfully
            - message_id (str): The message ID
            - patient_id (str): The patient ID (if successful)
            - sent_at (str): ISO timestamp of when sent (if successful)
            - error (str): Error message (if failed)
            - status (str): Message status (if already processed)

    Raises:
        Retry: If the task should be retried due to transient failures
    """
    self.log_task_start(message_id=message_id)

    async def _send_message_async():
        """Inner async function to send message with AsyncSession."""
        from app.database import get_async_session_factory
        from app.models.message import Message
        from sqlalchemy import select, update
        from sqlalchemy.orm import selectinload

        async_session_factory = get_async_session_factory()
        message_uuid = UUID(message_id)
        
        async with async_session_factory() as db:
            # Atomic claim: only one worker can transition eligible statuses to SENDING.
            # Accept SCHEDULED for backward compatibility with legacy rows.
            claim = await db.execute(
                update(Message)
                .where(
                    Message.id == message_uuid,
                    Message.status.in_([MessageStatus.PENDING, MessageStatus.SCHEDULED]),
                )
                .values(
                    status=MessageStatus.SENDING,
                    delivery_status=DeliveryStatus.SENDING,
                )
                .execution_options(synchronize_session=False)
            )
            await db.commit()

            if int(claim.rowcount or 0) == 0:
                # Message may not exist or may already be claimed/processed.
                status_stmt = select(Message.status).where(Message.id == message_uuid)
                status_result = await db.execute(status_stmt)
                current_status = status_result.scalar_one_or_none()
                if current_status is None:
                    return {
                        "found": False,
                        "retry": True,
                        "error": "Message not found",
                    }
                return {
                    "found": True,
                    "already_processed": True,
                    "status": current_status.value,
                }

            # Get message with patient relationship loaded
            stmt = (
                select(Message)
                .options(selectinload(Message.patient))
                .where(Message.id == message_uuid)
            )
            result = await db.execute(stmt)
            message = result.scalar_one_or_none()

            if not message:
                return {
                    "found": False,
                    "retry": True,
                    "error": "Message not found",
                }

            # Another process may have finalized status before we loaded the row.
            if message.status != MessageStatus.SENDING:
                return {
                    "found": True,
                    "already_processed": True,
                    "status": message.status.value,
                }

            # Get patient details
            patient = message.patient
            if not patient:
                message.status = MessageStatus.FAILED
                message.delivery_status = DeliveryStatus.FAILED
                message.failure_reason = "Patient not found"
                await db.commit()
                return {
                    "found": True,
                    "non_retriable": True,
                    "error": "Patient not found",
                }

            # SAFETY CHECK: Do not send messages to deleted patients
            if patient.deleted_at:
                message.status = MessageStatus.CANCELLED
                message.failure_reason = "Patient deleted"
                await db.commit()
                return {
                    "found": True,
                    "cancelled": True,
                    "error": "Patient deleted",
                }

            if not patient.phone:
                message.status = MessageStatus.FAILED
                message.delivery_status = DeliveryStatus.FAILED
                message.failure_reason = "Patient phone number missing"
                await db.commit()
                return {
                    "found": True,
                    "non_retriable": True,
                    "error": "Patient phone number missing",
                }

            # Send using Unified WhatsApp Service with AsyncSession
            whatsapp_service = create_unified_whatsapp_service(db)
            
            # send_message is async and works with AsyncSession
            success = await whatsapp_service.send_message(message)

            if success:
                # Mark as sent
                message.status = MessageStatus.SENT
                message.delivery_status = DeliveryStatus.SENT
                message.sent_at = now_sao_paulo()
                try:
                    await _schedule_next_reminder(message, db)
                except Exception as exc:
                    logger.warning(
                        "Failed to schedule next reminder message: %s",
                        exc,
                        extra={"message_id": str(message.id)},
                    )
                await db.commit()
                
                return {
                    "found": True,
                    "success": True,
                    "patient_id": str(message.patient_id),
                }
            else:
                message.status = MessageStatus.PENDING
                message.delivery_status = DeliveryStatus.QUEUED
                return {
                    "found": True,
                    "success": False,
                    "error": "WhatsApp service returned failure",
                }

    try:
        # Run the async function
        result = run_async(_send_message_async())

        # Handle retry for "message not found" (race condition with saga commit)
        if not result.get("found"):
            retry_count = self.request.retries
            if retry_count < 3:
                countdown = 2 ** (retry_count + 1)  # 2s, 4s, 8s
                logger.warning(
                    f"Message {message_id} not found (attempt {retry_count + 1}/3), "
                    f"retrying in {countdown}s"
                )
                raise self.retry(countdown=countdown, max_retries=3)
            
            logger.error(f"Message {message_id} not found after 3 retries")
            return {
                "success": False,
                "error": "Message not found after retries",
                "message_id": message_id,
            }

        # Handle already processed
        if result.get("already_processed"):
            logger.info(
                f"Message {message_id} already processed with status: {result['status']}"
            )
            return {
                "success": True,
                "message": "Message already processed",
                "message_id": message_id,
                "status": result["status"],
            }

        # Handle cancelled
        if result.get("cancelled"):
            logger.warning(f"Message {message_id} cancelled: {result['error']}")
            return {
                "success": False,
                "error": result["error"],
                "message_id": message_id,
                "status": "cancelled",
            }

        # Handle deterministic non-retriable failures
        if result.get("non_retriable"):
            return self.create_error_result(
                result["error"],
                message_id=message_id,
                status="failed",
            )

        # Handle other errors
        if result.get("error") and not result.get("success"):
            raise ExternalServiceError(result["error"])

        # Success!
        if result.get("success"):
            logger.info(f"Successfully sent scheduled message {message_id}")
            return {
                "success": True,
                "message_id": message_id,
                "patient_id": result.get("patient_id"),
                "sent_at": now_sao_paulo().isoformat(),
            }

        # Fallback
        raise ExternalServiceError("WhatsApp service returned failure")

    except Retry:
        # Re-raise Celery Retry exceptions
        raise
    except Exception as exc:
        logger.error(
            f"Error sending scheduled message {message_id}: {exc}", exc_info=True
        )
        max_retries = self.max_retries if self.max_retries is not None else 3

        # Reset claimed message back to pending for retry window.
        try:
            with get_db_session() as db:
                message = db.query(Message).filter(Message.id == UUID(message_id)).first()
                if message and message.status == MessageStatus.SENDING:
                    message.retry_count = int(message.retry_count or 0) + 1
                    message.last_retry_at = now_sao_paulo()
                    metadata = dict(message.message_metadata or {})
                    metadata["last_retry_error"] = str(exc)
                    metadata["last_retry_trigger"] = "send_scheduled_message"
                    message.message_metadata = metadata
                    if self.request.retries < max_retries:
                        message.status = MessageStatus.PENDING
                        message.delivery_status = DeliveryStatus.QUEUED
                    else:
                        message.status = MessageStatus.FAILED
                        message.delivery_status = DeliveryStatus.FAILED
                        message.failure_reason = str(exc)
                    db.commit()
        except Exception as sync_error:
            logger.error(
                "Failed to update retry state for message %s: %s",
                message_id,
                sync_error,
            )

        if self.request.retries < max_retries:
            self.handle_retry(exc, message_id=message_id)
            raise

        return self.create_error_result(
            f"Max retries exceeded: {str(exc)}", message_id=message_id
        )


@celery_app.task(
    bind=True,
    base=MessageTask,
    name="app.tasks.messaging.process_scheduled_messages",
)
def process_scheduled_messages(self, limit: int = 100) -> dict[str, Any]:
    """Process all scheduled messages that are due for delivery.

    Args:
        limit (int, optional): Maximum number of messages to process. Defaults to 100.

    Returns:
        dict[str, Any]: Dictionary containing:
            - success (bool): Whether the processing was successful
            - processed_count (int): Number of messages processed
            - processed_at (str): ISO timestamp of processing
            - error (str): Error message (if failed)
    """
    self.log_task_start(limit=limit)

    try:
        with get_db_session() as db:
            message_service = MessageService(db)

            # Get due messages
            due_messages = message_service.get_scheduled_messages(
                before_time=now_sao_paulo(), limit=limit
            )

            processed_count = 0
            for message in due_messages:
                # Trigger individual send task for each message
                # sending is idempotent, so it's safe to retry
                send_scheduled_message.delay(str(message.id))
                processed_count += 1

            result = self.create_success_result(
                processed_count=processed_count,
                processed_at=now_sao_paulo().isoformat(),
            )

            self.log_task_success(result, limit=limit)
            return result

    except Exception as exc:
        self.log_task_error(exc, limit=limit)
        self.handle_retry(exc, limit=limit)
        raise


@celery_app.task(
    bind=True,
    base=MessageTask,
    name="app.tasks.messaging.retry_failed_messages",
)
def retry_failed_messages(
    self, limit: int = 50, max_retries: int = 3
) -> dict[str, Any]:
    """Retry sending failed messages.

    Args:
        limit (int, optional): Maximum number of messages to retry. Defaults to 50.
        max_retries (int, optional): Maximum number of retry attempts per message. Defaults to 3.

    Returns:
        dict[str, Any]: Dictionary containing:
            - success (bool): Whether the retry process was successful
            - retry_count (int): Number of messages retried
            - retried_at (str): ISO timestamp of retry process
            - error (str): Error message (if failed)
    """
    self.log_task_start(limit=limit, max_retries=max_retries)

    try:
        with get_db_session() as db:
            message_service = MessageService(db)

            # Get failed messages that are candidates for retry
            # Note: filtering by retry count would be ideal here, but we'll filter in loop for now
            failed_messages = message_service.get_messages_with_filters(
                status=MessageStatus.FAILED,
                limit=limit * 2,  # Fetch more to account for max_retries filter
            )

            retry_count = 0
            for message in failed_messages:
                # Check if max retries exceeded
                # Assuming message.message_metadata stores retry info or we track it elsewhere
                # If not available, we might be retrying indefinitely.
                # Ideally Message model has retry_count column.

                current_retries = int(getattr(message, "retry_count", 0) or 0)

                if current_retries < max_retries:
                    # Increment retry count locally or let send_task handle it?
                    # send_scheduled_message handles the sending.
                    # We should probably update status to PENDING before triggering?
                    # Or just trigger it. send_scheduled_message checks for PENDING,
                    # so we might need to reset status first if it checks that strict.
                    # However, send_scheduled_message implementation I wrote:
                    # checks: if message.status != MessageStatus.PENDING: return "already processed"
                    # So we MUST reset status to PENDING.

                    # Update message status to PENDING to allow retry
                    try:
                        metadata = dict(message.message_metadata or {})
                        metadata["retry_trigger"] = "auto_retry_task"
                        metadata["last_retry_at"] = now_sao_paulo().isoformat()
                        message.status = MessageStatus.PENDING
                        message.last_retry_at = now_sao_paulo()
                        message.retry_count = current_retries + 1
                        message.message_metadata = metadata
                        db.commit()
                        # Trigger send
                        send_scheduled_message.delay(str(message.id))
                        retry_count += 1

                        if retry_count >= limit:
                            break

                    except Exception as e:
                        logger.error(
                            f"Failed to queue retry for message {message.id}: {e}"
                        )

            result = self.create_success_result(
                retry_count=retry_count, retried_at=now_sao_paulo().isoformat()
            )

            self.log_task_success(result, limit=limit, max_retries=max_retries)
            return result

    except Exception as exc:
        self.log_task_error(exc, limit=limit, max_retries=max_retries)
        self.handle_retry(exc, limit=limit, max_retries=max_retries)
        raise


@celery_app.task(name="app.tasks.messaging.send_bulk_messages")
def send_bulk_messages(message_data_list: List[dict[str, Any]]) -> dict[str, Any]:
    """Send multiple messages in bulk.

    Args:
        message_data_list (List[dict[str, Any]]): List of message data dictionaries,
            each containing message content, recipient, and scheduling information.

    Returns:
        dict[str, Any]: Dictionary containing:
            - success (bool): Whether the bulk sending was successful
            - total_messages (int): Total number of messages to send
            - sent_count (int): Number of messages successfully sent
            - failed_count (int): Number of messages that failed
            - sent_at (str): ISO timestamp of bulk sending
            - errors (List[str]): List of error messages (if any failures)
    """
    try:
        with get_scoped_session() as db:
            message_service = MessageService(db)

            created_messages = []
            failed_creations = []

            # Create all messages first
            for message_data in message_data_list:
                try:
                    # Schedule each message for immediate or delayed delivery
                    scheduled_for = message_data.get("scheduled_for")
                    if scheduled_for:
                        scheduled_for = datetime.fromisoformat(scheduled_for)
                    else:
                        scheduled_for = now_sao_paulo()

                    message = message_service.schedule_message(
                        patient_id=UUID(message_data["patient_id"]),
                        content=message_data["content"],
                        scheduled_for=scheduled_for,
                        message_type=MessageType(message_data.get("type", "text")),
                        message_metadata=message_data.get("metadata", {}),
                    )

                    created_messages.append(message)

                except Exception as exc:
                    logger.error(f"Failed to create bulk message: {exc}")
                    failed_creations.append(
                        {"patient_id": message_data.get("patient_id"), "error": str(exc)}
                    )

            # Schedule individual send tasks for each message
            scheduled_tasks = []
            for message in created_messages:
                # Schedule the send task
                eta = message.scheduled_for if message.scheduled_for else now_sao_paulo()
                task = send_scheduled_message.apply_async(args=[str(message.id)], eta=eta)
                scheduled_tasks.append(
                    {
                        "message_id": str(message.id),
                        "task_id": task.id,
                        "scheduled_for": eta.isoformat(),
                    }
                )

            result = {
                "success": True,
                "total_requested": len(message_data_list),
                "messages_created": len(created_messages),
                "creation_failures": len(failed_creations),
                "scheduled_tasks": scheduled_tasks,
                "failed_creations": failed_creations,
                "processed_at": now_sao_paulo().isoformat(),
            }

            logger.info(
                f"Bulk message operation: {len(created_messages)}/{len(message_data_list)} messages created and scheduled"
            )
            return result

    except Exception as exc:
        logger.error(f"Error in bulk message sending: {exc}", exc_info=True)
        return {
            "success": False,
            "error": str(exc),
            "total_requested": len(message_data_list),
            "messages_created": 0,
        }


@celery_app.task(name="app.tasks.messaging.cleanup_old_messages")
def cleanup_old_messages(days_old: int = 90) -> dict[str, Any]:
    """
    Clean up old messages to manage database size by archiving them.
    Moves messages older than 'days_old' to message_archives table.

    Args:
        days_old: Number of days after which messages should be archived

    Returns:
        Dictionary with cleanup results
    """
    try:
        with get_scoped_session() as db:
            # Calculate cutoff date
            cutoff_date = now_sao_paulo() - timedelta(days=days_old)

            # Query old messages (keep failed messages for longer analysis?)
            # Strategy: Archive DELIVERED, READ, CANCELLED. Keep FAILED for longer?
            # User request didn't specify, assumes all completed messages.
            from app.models.message import Message
            from app.models.message_archive import MessageArchive

            # Select messages to archive (completed ones)
            messages_to_archive = (
                db.query(Message)
                .filter(Message.created_at < cutoff_date)
                .filter(Message.status.in_([
                    MessageStatus.DELIVERED, 
                    MessageStatus.READ,
                    MessageStatus.CANCELLED
                ]))
                .limit(1000) # Process in batches
                .all()
            )

            if not messages_to_archive:
                return {
                    "success": True, 
                    "archived_count": 0,
                    "message": "No messages to archive"
                }

            archived_count = 0
            for msg in messages_to_archive:
                try:
                    # Create archive record
                    archive = MessageArchive(
                        original_id=msg.id,
                        patient_id=msg.patient_id,
                        direction=msg.direction,
                        type=msg.type,
                        content=msg.content,
                        message_metadata=msg.message_metadata,
                        priority=msg.priority,
                        idempotency_key=msg.idempotency_key,
                        whatsapp_id=msg.whatsapp_id,
                        status=msg.status,
                        scheduled_for=msg.scheduled_for,
                        sent_at=msg.sent_at,
                        delivered_at=msg.delivered_at,
                        read_at=msg.read_at,
                        delivery_status=msg.delivery_status,
                        retry_count=msg.retry_count,
                        last_retry_at=msg.last_retry_at,
                        failure_reason=msg.failure_reason,
                        archived_at=now_sao_paulo()
                    )
                    db.add(archive)
                    
                    # Delete original
                    db.delete(msg)
                    
                    archived_count += 1
                except Exception as e:
                    logger.error(f"Failed to archive message {msg.id}: {e}")
                    # Continue to next message, don't rollback entire batch if one fails?
                    # Ideally allow partial success or fail batch.
                    # Batch approach implies transaction.
                    continue

            db.commit()

            result = {
                "success": True,
                "archived_count": archived_count,
                "cutoff_date": cutoff_date.isoformat(),
                "cleaned_at": now_sao_paulo().isoformat(),
            }

            logger.info(
                f"Archived {archived_count} old messages older than {days_old} days"
            )
            return result

    except Exception as exc:
        logger.error(f"Error cleaning up old messages: {exc}", exc_info=True)
        return {"success": False, "error": str(exc), "archived_count": 0}


@celery_app.task(name="app.tasks.messaging.generate_message_analytics")
def generate_message_analytics(
    patient_id: Optional[str] = None, days_back: int = 30
) -> dict[str, Any]:
    """
    Generate analytics for message delivery and engagement.

    Args:
        patient_id: Optional patient ID to filter analytics
        days_back: Number of days to look back for analytics

    Returns:
        Dictionary with analytics data
    """
    try:
        with get_scoped_session() as db:
            message_service = MessageService(db)

            # Calculate date range
            end_date = now_sao_paulo()
            start_date = end_date - timedelta(days=days_back)

            # Get message statistics
            patient_uuid = UUID(patient_id) if patient_id else None
            statistics = message_service.get_message_statistics(
                patient_id=patient_uuid, start_date=start_date, end_date=end_date
            )

            # Calculate delivery rates
            total_sent = (
                statistics.get("sent", 0)
                + statistics.get("delivered", 0)
                + statistics.get("read", 0)
            )
            total_delivered = statistics.get("delivered", 0) + statistics.get("read", 0)
            total_read = statistics.get("read", 0)

            delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
            read_rate = (total_read / total_delivered * 100) if total_delivered > 0 else 0

            # Get additional metrics from database
            from app.models.message import Message
            from sqlalchemy import func, and_

            query = db.query(Message).filter(
                and_(Message.created_at >= start_date, Message.created_at <= end_date)
            )

            if patient_uuid:
                query = query.filter(Message.patient_id == patient_uuid)

            # Average delivery time
            delivery_times = (
                query.filter(
                    and_(Message.sent_at.isnot(None), Message.delivered_at.isnot(None))
                )
                .with_entities(
                    func.extract("epoch", Message.delivered_at - Message.sent_at).label(
                        "delivery_seconds"
                    )
                )
                .all()
            )

            avg_delivery_time = (
                sum(dt.delivery_seconds for dt in delivery_times) / len(delivery_times)
                if delivery_times
                else 0
            )

            result = {
                "success": True,
                "analytics": {
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "days": days_back,
                    },
                    "patient_id": patient_id,
                    "message_counts": statistics,
                    "rates": {
                        "delivery_rate_percent": round(delivery_rate, 2),
                        "read_rate_percent": round(read_rate, 2),
                    },
                    "performance": {
                        "avg_delivery_time_seconds": round(avg_delivery_time, 2),
                        "total_messages": sum(statistics.values()),
                    },
                },
                "generated_at": now_sao_paulo().isoformat(),
            }

            logger.info(
                f"Generated message analytics for {days_back} days"
                + (f" for patient {patient_id}" if patient_id else "")
            )
            return result

    except Exception as exc:
        logger.error(f"Error generating message analytics: {exc}", exc_info=True)
        return {"success": False, "error": str(exc), "analytics": {}}


@celery_app.task(name="app.tasks.messaging.process_whatsapp_dlq")
def process_whatsapp_dlq(limit: int = 50) -> dict[str, Any]:
    """
    Process Dead Letter Queue (DLQ) for WhatsApp messages.

    This task retrieves failed messages from the DLQ and attempts to review
    and potentially requeue them for retry.

    Args:
        limit: Maximum number of DLQ messages to process

    Returns:
        Dictionary with processing results
    """
    try:
        with get_scoped_session() as db:
            from app.integrations.whatsapp.queue.dlq import DLQHandler

            dlq_handler = DLQHandler(db)

            # Get pending DLQ messages (using run_async for event loop reuse)
            pending_messages = run_async(dlq_handler.get_pending_review(limit=limit))

            if not pending_messages:
                logger.info("No pending DLQ messages to process")
                return {
                    "success": True,
                    "message": "No pending DLQ messages",
                    "processed": 0,
                }

            logger.info(f"Processing {len(pending_messages)} DLQ messages")

            # Process each message (basic automatic retry for certain categories)
            processed_count = 0
            requeued_count = 0

            for failed_msg in pending_messages:
                try:
                    # Auto-approve retry for transient failures (rate limit, timeout)
                    from app.models.failed_message import FailureReason

                    auto_retry_reasons = [
                        FailureReason.RATE_LIMIT.value,
                        FailureReason.TIMEOUT.value,
                        FailureReason.NETWORK_ERROR.value,
                    ]

                    # Check error_code field (stores failure reason value)
                    if (
                        failed_msg.error_code in auto_retry_reasons
                        and failed_msg.retry_count < 3
                    ):
                        # Auto-approve and requeue (using run_async for event loop reuse)
                        result = run_async(
                            dlq_handler.requeue_for_retry(
                                dlq_id=failed_msg.id, immediate=False
                            )
                        )

                        requeued_count += 1
                        logger.info(f"Auto-requeued DLQ message {failed_msg.id}")
                    else:
                        # Leave for manual review
                        logger.info(f"DLQ message {failed_msg.id} requires manual review")

                    processed_count += 1

                except Exception as e:
                    logger.error(f"Failed to process DLQ message {failed_msg.id}: {e}")
                    continue

            result = {
                "success": True,
                "message": f"Processed {processed_count} DLQ messages",
                "processed": processed_count,
                "requeued": requeued_count,
                "manual_review": processed_count - requeued_count,
            }

            logger.info(f"DLQ processing complete: {result}")
            return result

    except Exception as exc:
        logger.error(f"Error processing WhatsApp DLQ: {exc}", exc_info=True)
        return {"success": False, "error": str(exc), "processed": 0}


@celery_app.task(
    bind=True,
    base=MessageTask,
    name="app.tasks.messaging.retry_pending_welcome_messages",
)
def retry_pending_welcome_messages(
    self, limit: int = 50, min_age_minutes: int = 5, max_age_hours: int = 24
) -> dict[str, Any]:
    """
    Retry welcome messages stuck in PENDING status.

    FIX: Welcome messages could get stuck in PENDING if WhatsApp API fails
    during patient registration. This task specifically targets welcome messages
    (identified by message_metadata['message_type'] == 'welcome') that have been
    pending for too long.

    Args:
        limit: Maximum number of messages to retry per run
        min_age_minutes: Minimum age in minutes before retrying (avoids race conditions)
        max_age_hours: Maximum age in hours to consider for retry (skip very old messages)

    Returns:
        dict with retry results
    """
    self.log_task_start(limit=limit, min_age_minutes=min_age_minutes)

    try:
        with get_db_session() as db:
            from app.models.message import Message

            # Calculate time window
            now = now_sao_paulo()
            min_created_at = now - timedelta(hours=max_age_hours)
            max_created_at = now - timedelta(minutes=min_age_minutes)

            # Find welcome messages stuck in PENDING
            # Uses JSONB query for message_metadata->>'message_type' == 'welcome'
            pending_welcome_messages = (
                db.query(Message)
                .filter(
                    Message.status == MessageStatus.PENDING,
                    Message.message_metadata["message_type"].astext == "welcome",
                    Message.created_at >= min_created_at,
                    Message.created_at <= max_created_at,
                )
                .limit(limit)
                .all()
            )

            if not pending_welcome_messages:
                logger.info("No pending welcome messages to retry")
                return self.create_success_result(
                    retry_count=0, message="No pending welcome messages found"
                )

            retry_count = 0
            failed_count = 0

            for message in pending_welcome_messages:
                try:
                    # Update metadata to track retry attempt
                    metadata = message.message_metadata or {}
                    retry_attempts = metadata.get("welcome_retry_attempts", 0)

                    if retry_attempts >= 3:
                        logger.warning(
                            f"Welcome message {message.id} exceeded max retries, marking as failed"
                        )
                        message.status = MessageStatus.FAILED
                        metadata["final_failure_reason"] = (
                            "max_welcome_retries_exceeded"
                        )
                        metadata["failed_at"] = now.isoformat()
                        message.message_metadata = metadata
                        failed_count += 1
                        continue

                    # Update retry tracking
                    metadata["welcome_retry_attempts"] = retry_attempts + 1
                    metadata["last_welcome_retry_at"] = now.isoformat()
                    message.message_metadata = metadata

                    db.commit()

                    # Trigger send task
                    send_scheduled_message.delay(str(message.id))
                    retry_count += 1

                    logger.info(
                        f"Queued welcome message {message.id} for retry "
                        f"(attempt {retry_attempts + 1})"
                    )

                except Exception as e:
                    logger.error(f"Failed to retry welcome message {message.id}: {e}")
                    failed_count += 1

            db.commit()

            result = self.create_success_result(
                retry_count=retry_count,
                failed_count=failed_count,
                total_found=len(pending_welcome_messages),
                retried_at=now.isoformat(),
            )

            self.log_task_success(result, limit=limit)
            return result

    except Exception as exc:
        self.log_task_error(exc, limit=limit)
        self.handle_retry(exc, limit=limit)
        raise
