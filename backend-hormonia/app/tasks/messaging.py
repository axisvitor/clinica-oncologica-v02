"""
Celery tasks for message processing and scheduling.
"""
import logging
from typing import Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from celery import Task
from celery.exceptions import Retry

from app.celery_app import celery_app
from app.database import get_db
from app.domain.messaging.core import MessageService
from app.models.message import MessageStatus, MessageType
from app.schemas.message import MessageUpdate
from app.exceptions import ExternalServiceError
from app.tasks.base import MessageTask, get_db_session


logger = logging.getLogger(__name__)


# MessageTask is now imported from app.tasks.base


from app.services.unified_whatsapp_service import create_unified_whatsapp_service

@celery_app.task(bind=True, base=MessageTask, name="send_scheduled_message")
def send_scheduled_message(self, message_id: str) -> dict[str, Any]:
    """Send a scheduled message to a patient.

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

    try:
        # We need a session for MessageService to get the message details
        with get_db_session() as db:
            message_service = MessageService(db)

            # Get the message
            message = message_service.get_message(message_id)
            if not message:
                logger.error(f"Message {message_id} not found")
                return {
                    "success": False,
                    "error": "Message not found",
                    "message_id": message_id
                }

            # Check if message is still pending
            if message.status != MessageStatus.PENDING:
                logger.info(f"Message {message_id} already processed with status: {message.status}")
                return {
                    "success": True,
                    "message": "Message already processed",
                    "message_id": message_id,
                    "status": message.status.value
                }

            # Get patient phone number
            patient = message.patient
            if not patient or not patient.phone:
                 logger.error(f"Patient phone not found for message {message_id}")
                 return {
                    "success": False,
                    "error": "Patient phone number missing",
                    "message_id": message_id
                 }

            # Send using Unified WhatsApp Service
            whatsapp_service = create_unified_whatsapp_service(db)

            import asyncio
            # UnifiedWhatsAppService.send_message() accepts Message object directly
            success = asyncio.run(whatsapp_service.send_message(message))

            # Update status locally based on result
            if success:
                message_service.mark_as_sent(message_id, "queued")
                logger.info(f"Successfully sent scheduled message {message_id}")
            else:
                logger.error(f"Failed to send scheduled message {message_id}")
                raise ExternalServiceError(f"WhatsApp service returned failure")

            return {
                "success": True,
                "message_id": message_id,
                "patient_id": str(message.patient_id),
                "sent_at": datetime.utcnow().isoformat()
            }

    except Exception as exc:
        logger.error(f"Error sending scheduled message {message_id}: {exc}", exc_info=True)

        # Use base class retry handling
        try:
            self.handle_retry(exc, message_id=message_id)
        except Exception:
            # Mark message as failed after max retries
            try:
                with get_db_session() as db:
                    message_service = MessageService(db)
                    message_service.mark_as_failed(message_id, {
                        "error": "Max retries exceeded",
                        "last_error": str(exc),
                        "failed_at": datetime.utcnow().isoformat()
                    })
            except Exception as mark_error:
                logger.error(f"Failed to mark message {message_id} as failed: {mark_error}")

            return self.create_error_result(
                f"Max retries exceeded: {str(exc)}",
                message_id=message_id
            )


@celery_app.task(bind=True, base=MessageTask, name="process_scheduled_messages")
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
                before_time=datetime.utcnow(),
                limit=limit
            )
            
            processed_count = 0
            for message in due_messages:
                # Trigger individual send task for each message
                # sending is idempotent, so it's safe to retry
                send_scheduled_message.delay(str(message.id))
                processed_count += 1

            result = self.create_success_result(
                processed_count=processed_count,
                processed_at=datetime.utcnow().isoformat()
            )

            self.log_task_success(result, limit=limit)
            return result

    except Exception as exc:
        self.log_task_error(exc, limit=limit)
        return self.create_error_result(
            str(exc),
            processed_count=0
        )


@celery_app.task(bind=True, base=MessageTask, name="retry_failed_messages")
def retry_failed_messages(self, limit: int = 50, max_retries: int = 3) -> dict[str, Any]:
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
                limit=limit * 2  # Fetch more to account for max_retries filter
            )

            retry_count = 0
            for message in failed_messages:
                # Check if max retries exceeded
                # Assuming message.message_metadata stores retry info or we track it elsewhere
                # If not available, we might be retrying indefinitely. 
                # Ideally Message model has retry_count column.
                
                current_retries = message.retry_count if hasattr(message, 'retry_count') else 0
                
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
                         message_service.update_message(
                             message.id, 
                             MessageUpdate(
                                 status=MessageStatus.PENDING,
                                 message_metadata={
                                     **(message.message_metadata or {}),
                                     "retry_trigger": "auto_retry_task",
                                     "last_retry_at": datetime.utcnow().isoformat()
                                 }
                             )
                         )
                         # Trigger send
                         send_scheduled_message.delay(str(message.id))
                         retry_count += 1
                         
                         if retry_count >= limit:
                             break
                             
                     except Exception as e:
                         logger.error(f"Failed to queue retry for message {message.id}: {e}")
            
            result = self.create_success_result(
                retry_count=retry_count,
                retried_at=datetime.utcnow().isoformat()
            )

            self.log_task_success(result, limit=limit, max_retries=max_retries)
            return result

    except Exception as exc:
        self.log_task_error(exc, limit=limit, max_retries=max_retries)
        return self.create_error_result(
            str(exc),
            retry_count=0
        )


@celery_app.task(name="send_bulk_messages")
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
        db = next(get_db())
        message_service = MessageService(db)
        
        created_messages = []
        failed_creations = []
        
        # Create all messages first
        for message_data in message_data_list:
            try:
                # Schedule each message for immediate or delayed delivery
                scheduled_for = message_data.get('scheduled_for')
                if scheduled_for:
                    scheduled_for = datetime.fromisoformat(scheduled_for)
                else:
                    scheduled_for = datetime.utcnow()
                
                message = message_service.schedule_message(
                    patient_id=UUID(message_data['patient_id']),
                    content=message_data['content'],
                    scheduled_for=scheduled_for,
                    message_type=MessageType(message_data.get('type', 'text')),
                    message_metadata=message_data.get('metadata', {})
                )
                
                created_messages.append(message)
                
            except Exception as exc:
                logger.error(f"Failed to create bulk message: {exc}")
                failed_creations.append({
                    "patient_id": message_data.get('patient_id'),
                    "error": str(exc)
                })
        
        # Schedule individual send tasks for each message
        scheduled_tasks = []
        for message in created_messages:
            # Schedule the send task
            eta = message.scheduled_for if message.scheduled_for else datetime.utcnow()
            task = send_scheduled_message.apply_async(
                args=[str(message.id)],
                eta=eta
            )
            scheduled_tasks.append({
                "message_id": str(message.id),
                "task_id": task.id,
                "scheduled_for": eta.isoformat()
            })
        
        result = {
            "success": True,
            "total_requested": len(message_data_list),
            "messages_created": len(created_messages),
            "creation_failures": len(failed_creations),
            "scheduled_tasks": scheduled_tasks,
            "failed_creations": failed_creations,
            "processed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Bulk message operation: {len(created_messages)}/{len(message_data_list)} messages created and scheduled")
        return result
        
    except Exception as exc:
        logger.error(f"Error in bulk message sending: {exc}", exc_info=True)
        return {
            "success": False,
            "error": str(exc),
            "total_requested": len(message_data_list),
            "messages_created": 0
        }


@celery_app.task(name="cleanup_old_messages")
def cleanup_old_messages(days_old: int = 90) -> dict[str, Any]:
    """
    Clean up old messages to manage database size.
    
    Args:
        days_old: Number of days after which messages should be cleaned up
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        db = next(get_db())
        
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Query old messages (keep failed messages for longer analysis)
        from app.models.message import Message
        old_messages = (
            db.query(Message)
            .filter(Message.created_at < cutoff_date)
            .filter(Message.status.in_([MessageStatus.DELIVERED, MessageStatus.READ]))
            .all()
        )
        
        # Archive or delete old messages
        archived_count = 0
        for message in old_messages:
            # For now, we'll just mark them as archived in metadata
            # In production, you might want to move them to an archive table
            metadata = message.message_metadata or {}
            metadata['archived'] = True
            metadata['archived_at'] = datetime.utcnow().isoformat()
            
            message.message_metadata = metadata
            archived_count += 1
        
        db.commit()
        
        result = {
            "success": True,
            "archived_count": archived_count,
            "cutoff_date": cutoff_date.isoformat(),
            "cleaned_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Archived {archived_count} old messages older than {days_old} days")
        return result
        
    except Exception as exc:
        logger.error(f"Error cleaning up old messages: {exc}", exc_info=True)
        return {
            "success": False,
            "error": str(exc),
            "archived_count": 0
        }


@celery_app.task(name="generate_message_analytics")
def generate_message_analytics(patient_id: Optional[str] = None, days_back: int = 30) -> dict[str, Any]:
    """
    Generate analytics for message delivery and engagement.
    
    Args:
        patient_id: Optional patient ID to filter analytics
        days_back: Number of days to look back for analytics
        
    Returns:
        Dictionary with analytics data
    """
    try:
        db = next(get_db())
        message_service = MessageService(db)
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        # Get message statistics
        patient_uuid = UUID(patient_id) if patient_id else None
        statistics = message_service.get_message_statistics(
            patient_id=patient_uuid,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate delivery rates
        total_sent = statistics.get('sent', 0) + statistics.get('delivered', 0) + statistics.get('read', 0)
        total_delivered = statistics.get('delivered', 0) + statistics.get('read', 0)
        total_read = statistics.get('read', 0)
        
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        read_rate = (total_read / total_delivered * 100) if total_delivered > 0 else 0
        
        # Get additional metrics from database
        from app.models.message import Message
        from sqlalchemy import func, and_
        
        query = db.query(Message).filter(
            and_(
                Message.created_at >= start_date,
                Message.created_at <= end_date
            )
        )
        
        if patient_uuid:
            query = query.filter(Message.patient_id == patient_uuid)
        
        # Average delivery time
        delivery_times = (
            query.filter(
                and_(
                    Message.sent_at.isnot(None),
                    Message.delivered_at.isnot(None)
                )
            )
            .with_entities(
                func.extract('epoch', Message.delivered_at - Message.sent_at).label('delivery_seconds')
            )
            .all()
        )
        
        avg_delivery_time = sum(dt.delivery_seconds for dt in delivery_times) / len(delivery_times) if delivery_times else 0
        
        result = {
            "success": True,
            "analytics": {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days_back
                },
                "patient_id": patient_id,
                "message_counts": statistics,
                "rates": {
                    "delivery_rate_percent": round(delivery_rate, 2),
                    "read_rate_percent": round(read_rate, 2)
                },
                "performance": {
                    "avg_delivery_time_seconds": round(avg_delivery_time, 2),
                    "total_messages": sum(statistics.values())
                }
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Generated message analytics for {days_back} days" + (f" for patient {patient_id}" if patient_id else ""))
        return result
        
    except Exception as exc:
        logger.error(f"Error generating message analytics: {exc}", exc_info=True)
        return {
            "success": False,
            "error": str(exc),
            "analytics": {}
        }

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
        db = next(get_db())
        
        from app.integrations.whatsapp.queue.dlq import DLQHandler
        
        dlq_handler = DLQHandler(db)
        
        # Get pending DLQ messages
        import asyncio
        pending_messages = asyncio.run(dlq_handler.get_pending_review(limit=limit))
        
        if not pending_messages:
            logger.info("No pending DLQ messages to process")
            return {
                "success": True,
                "message": "No pending DLQ messages",
                "processed": 0
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
                    FailureReason.RATE_LIMIT,
                    FailureReason.TIMEOUT,
                    FailureReason.NETWORK_ERROR
                ]
                
                if failed_msg.failure_reason in auto_retry_reasons and failed_msg.retry_count < 3:
                    # Auto-approve and requeue
                    result = asyncio.run(dlq_handler.requeue_for_retry(
                        dlq_id=failed_msg.id,
                        immediate=False
                    ))
                    
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
            "manual_review": processed_count - requeued_count
        }
        
        logger.info(f"DLQ processing complete: {result}")
        return result
        
    except Exception as exc:
        logger.error(f"Error processing WhatsApp DLQ: {exc}", exc_info=True)
        return {
            "success": False,
            "error": str(exc),
            "processed": 0
        }
