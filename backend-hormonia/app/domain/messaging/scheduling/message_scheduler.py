"""
MessageScheduler service for time-based message delivery with timezone handling.
Integrates with Celery for reliable message scheduling and delivery tracking.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, time
from uuid import UUID
from enum import Enum
import pytz
from sqlalchemy.orm import Session

# Import models and repositories
from app.models.patient import Patient
from app.models.message import Message, MessageType, MessageDirection, MessageStatus, DeliveryStatus
from app.models.failed_message import FailureReason
from app.repositories.patient import PatientRepository
from app.repositories.message import MessageRepository
from app.domain.messaging.delivery import MessageSender
from app.exceptions import ValidationError, NotFoundError
from app.utils.db_retry import with_db_retry
from app.utils.distributed_lock import async_message_delivery_lock, LockAcquisitionError, LockTimeoutError


class MessageSchedulingError(Exception):
    """Base exception for message scheduling errors."""
    pass


class TimezoneError(MessageSchedulingError):
    """Exception for timezone-related errors."""
    pass


class TaskSchedulingError(MessageSchedulingError):
    """Exception for Celery task scheduling errors."""
    pass

logger = logging.getLogger(__name__)


class SchedulingWindow(Enum):
    """Predefined scheduling windows for message delivery."""
    MORNING = "morning"  # 9:00 - 12:00
    AFTERNOON = "afternoon"  # 12:00 - 17:00
    EVENING = "evening"  # 17:00 - 20:00
    BUSINESS_HOURS = "business_hours"  # 9:00 - 18:00
    EXTENDED_HOURS = "extended_hours"  # 8:00 - 21:00


class MessageSchedulerConfig:
    """Configuration constants for MessageScheduler."""
    
    # Scheduling windows (start_time, end_time)
    SCHEDULING_WINDOWS = {
        SchedulingWindow.MORNING: (time(9, 0), time(12, 0)),
        SchedulingWindow.AFTERNOON: (time(12, 0), time(17, 0)),
        SchedulingWindow.EVENING: (time(17, 0), time(20, 0)),
        SchedulingWindow.BUSINESS_HOURS: (time(9, 0), time(18, 0)),
        SchedulingWindow.EXTENDED_HOURS: (time(8, 0), time(21, 0))
    }
    
    # Message constraints
    MAX_MESSAGE_LENGTH = 4096  # WhatsApp message limit
    MIN_SCHEDULING_BUFFER_MINUTES = 15  # Minimum time before sending
    FALLBACK_DELAY_MINUTES = 30  # Fallback delay when calculation fails
    
    # Default timezone
    DEFAULT_TIMEZONE = "America/Sao_Paulo"
    
    # Retry configuration
    MAX_TASK_RETRIES = 3
    RETRY_DELAY_SECONDS = 60


class MessageScheduler:
    """
    Service for scheduling and managing time-based message delivery.
    Handles patient timezone preferences, appropriate sending hours, and Celery integration.
    """
    
    def __init__(self, db: Session, config: MessageSchedulerConfig = None):
        self.db = db
        self.config = config or MessageSchedulerConfig()
        
        if db:
            self.patient_repo = PatientRepository(db)
            self.message_repo = MessageRepository(db)
            self.message_sender = MessageSender(db)
        
        # Use configuration for scheduling windows
        self.scheduling_windows = self.config.SCHEDULING_WINDOWS
    
    def _get_patient_timezone(self, patient: Patient) -> str:
        """
        Get patient timezone from metadata or default to Brazil timezone.
        
        Args:
            patient: Patient object
            
        Returns:
            Timezone string
        """
        if (patient.patient_metadata and 
            "timezone" in patient.patient_metadata and 
            patient.patient_metadata["timezone"]):
            return patient.patient_metadata["timezone"]
        
        # Default to configured timezone
        return self.config.DEFAULT_TIMEZONE

    async def _schedule_celery_task(self, message: Message, delivery_time: datetime) -> Dict[str, Any]:
        """
        Schedule Celery task for message delivery with distributed locking.

        Uses distributed locks to ensure messages are scheduled in the correct order
        and prevent race conditions in message delivery.

        Args:
            message: Message to schedule (must have ID already)
            delivery_time: When to deliver the message

        Returns:
            Task scheduling result
        """
        try:
            # Acquire lock for message delivery ordering
            async with async_message_delivery_lock(message.patient_id, timeout=10) as lock:
                logger.debug(f"Acquired message delivery lock for patient {message.patient_id}")

                # Import here to avoid circular imports
                from app.tasks.flows import send_flow_message

                # Prepare message data for Celery task
                message_data = {
                    "content": message.content,
                    "type": message.type.value,
                    "metadata": message.message_metadata,
                    "flow_context": message.message_metadata.get("flow_context", {})
                }

                # Schedule task with ETA, passing message_id to UPDATE existing message
                task_result = send_flow_message.apply_async(
                    args=[str(message.patient_id), message_data, str(message.id)],
                    eta=delivery_time
                )

                logger.info(
                    f"Scheduled Celery task {task_result.id} for message {message.id} "
                    f"at {delivery_time.isoformat()}"
                )

                # Log lock metrics if contention occurred
                lock_metrics = lock.get_metrics()
                if lock_metrics.get("contention_count", 0) > 0:
                    logger.info(
                        f"Message delivery lock contention: "
                        f"{lock_metrics['contention_count']} contentions, "
                        f"avg wait: {lock_metrics['average_wait_time']:.3f}s"
                    )

                return {
                    "task_id": task_result.id,
                    "eta": delivery_time.isoformat(),
                    "status": "scheduled",
                    "message_id": str(message.id),
                    "lock_metrics": lock_metrics
                }

        except (LockTimeoutError, LockAcquisitionError) as e:
            logger.error(
                f"Failed to acquire lock for message {message.id} scheduling: {e}"
            )
            return {
                "task_id": None,
                "error": f"Lock error: {str(e)}",
                "status": "failed"
            }
        except Exception as e:
            logger.error(f"Failed to schedule Celery task for message {message.id}: {e}")
            return {
                "task_id": None,
                "error": str(e),
                "status": "failed"
            }

    @with_db_retry(max_retries=3)
    async def schedule_message(self, 
                             patient_id: UUID, 
                             message_content: str, 
                             scheduling_window: SchedulingWindow = SchedulingWindow.BUSINESS_HOURS,
                             message_type: str = "text",
                             metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Schedule a message for delivery to a patient.
        
        Args:
            patient_id: Patient UUID
            message_content: Message content to send
            scheduling_window: When to send the message
            message_type: Type of message (text, interactive, etc.)
            metadata: Additional message metadata
            
        Returns:
            Scheduling result with task information
        """
        # Input validation
        if not patient_id:
            raise ValidationError("Patient ID is required")
        
        if not message_content or not message_content.strip():
            raise ValidationError("Message content cannot be empty")
        
        if len(message_content) > self.config.MAX_MESSAGE_LENGTH:
            raise ValidationError(f"Message content exceeds maximum length ({self.config.MAX_MESSAGE_LENGTH} characters)")
        
        if not isinstance(scheduling_window, SchedulingWindow):
            raise ValidationError("Invalid scheduling window")
        
        try:
            # Get patient
            patient = self.patient_repo.get(patient_id)
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")
            
            # Calculate optimal delivery time
            delivery_time = await self._calculate_optimal_delivery_time(patient, scheduling_window)
            
            # Create message record
            message = Message(
                patient_id=patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType(message_type),
                content=message_content,
                status=MessageStatus.SCHEDULED,
                scheduled_for=delivery_time,
                message_metadata=metadata or {}
            )
            
            # Save to database
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            
            # Schedule Celery task
            task_result = await self._schedule_celery_task(message, delivery_time)
            
            # Update message with task ID
            message.message_metadata["celery_task_id"] = task_result.get("task_id")
            self.db.commit()
            
            return {
                "message_id": str(message.id),
                "patient_id": str(patient_id),
                "scheduled_for": delivery_time.isoformat(),
                "status": DeliveryStatus.SCHEDULED.value,
                "scheduling_window": scheduling_window.value,
                "task_id": task_result.get("task_id")
            }
            
        except Exception as e:
            logger.error(f"Failed to schedule message for patient {patient_id}: {e}")
            raise

    @with_db_retry(max_retries=3)
    async def schedule_flow_message(self,
                                  patient_id: UUID,
                                  flow_day: int,
                                  flow_type: str,
                                  template_id: str,
                                  personalized_content: str,
                                  scheduling_window: SchedulingWindow = SchedulingWindow.BUSINESS_HOURS) -> Dict[str, Any]:
        """
        Schedule a flow-specific message with flow context.
        
        Args:
            patient_id: Patient UUID
            flow_day: Current day in the flow
            flow_type: Type of flow (initial_15_days, etc.)
            template_id: Template identifier
            personalized_content: AI-personalized message content
            scheduling_window: When to send the message
            
        Returns:
            Scheduling result with flow context
        """
        flow_metadata = {
            "flow_context": {
                "flow_day": flow_day,
                "flow_type": flow_type,
                "template_id": template_id,
                "personalized": True,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        
        return await self.schedule_message(
            patient_id=patient_id,
            message_content=personalized_content,
            scheduling_window=scheduling_window,
            metadata=flow_metadata
        )

    @with_db_retry(max_retries=3)
    async def cancel_scheduled_message(self, message_id: UUID) -> bool:
        """
        Cancel a scheduled message.
        
        Args:
            message_id: Message UUID to cancel
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            message = self.message_repo.get(message_id)
            if not message:
                logger.warning(f"Message {message_id} not found for cancellation")
                return False
            
            if message.status not in [MessageStatus.SCHEDULED, MessageStatus.PENDING]:
                logger.warning(f"Cannot cancel message {message_id} with status {message.status}")
                return False
            
            # Cancel Celery task if exists
            task_id = message.message_metadata.get("celery_task_id")
            if task_id:
                try:
                    from app.celery_app import celery_app
                    celery_app.control.revoke(task_id, terminate=True)
                    logger.info(f"Cancelled Celery task {task_id} for message {message_id}")
                except Exception as e:
                    logger.error(f"Failed to cancel Celery task {task_id}: {e}")
            
            # Update message status
            message.status = MessageStatus.CANCELLED
            message.message_metadata["cancelled_at"] = datetime.utcnow().isoformat()
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel message {message_id}: {e}")
            return False

    @with_db_retry(max_retries=3)
    async def reschedule_message(self,
                               message_id: UUID,
                               new_delivery_time: datetime,
                               reason: str = "user_requested") -> Dict[str, Any]:
        """
        Reschedule a message to a new delivery time.
        
        Args:
            message_id: Message UUID to reschedule
            new_delivery_time: New delivery time
            reason: Reason for rescheduling
            
        Returns:
            Rescheduling result
        """
        try:
            if new_delivery_time <= datetime.utcnow():
                raise ValidationError("Cannot reschedule to past time")
            
            message = self.message_repo.get(message_id)
            if not message:
                raise NotFoundError(f"Message {message_id} not found")
            
            if message.status not in [MessageStatus.SCHEDULED, MessageStatus.PENDING]:
                raise ValidationError(f"Cannot reschedule message with status {message.status}")
            
            # Cancel old task
            old_task_id = message.message_metadata.get("celery_task_id")
            if old_task_id:
                try:
                    from app.celery_app import celery_app
                    celery_app.control.revoke(old_task_id, terminate=True)
                except Exception as e:
                    logger.error(f"Failed to cancel old task {old_task_id}: {e}")
            
            # Schedule new task
            task_result = await self._schedule_celery_task(message, new_delivery_time)
            
            # Update message
            message.scheduled_for = new_delivery_time
            message.status = MessageStatus.SCHEDULED
            message.message_metadata.update({
                "celery_task_id": task_result.get("task_id"),
                "rescheduled_at": datetime.utcnow().isoformat(),
                "reschedule_reason": reason,
                "previous_task_id": old_task_id
            })
            self.db.commit()
            
            return {
                "message_id": str(message_id),
                "new_delivery_time": new_delivery_time.isoformat(),
                "task_id": task_result.get("task_id"),
                "reason": reason
            }
            
        except Exception as e:
            logger.error(f"Failed to reschedule message {message_id}: {e}")
            raise

    @with_db_retry(max_retries=3)
    async def update_delivery_status(self,
                                   message_id: UUID,
                                   status: DeliveryStatus,
                                   whatsapp_id: str = None,
                                   delivery_info: Dict[str, Any] = None) -> bool:
        """
        Update message delivery status.
        
        Args:
            message_id: Message UUID
            status: New delivery status
            whatsapp_id: WhatsApp message ID
            delivery_info: Additional delivery information
            
        Returns:
            True if updated successfully
        """
        try:
            message = self.message_repo.get(message_id)
            if not message:
                logger.warning(f"Message {message_id} not found for status update")
                return False
            
            # Update message status
            if status == DeliveryStatus.SENT:
                message.status = MessageStatus.SENT
                message.sent_at = datetime.utcnow()
            elif status == DeliveryStatus.DELIVERED:
                message.status = MessageStatus.DELIVERED
                message.delivered_at = datetime.utcnow()
            elif status == DeliveryStatus.READ:
                message.status = MessageStatus.READ
                message.read_at = datetime.utcnow()
            elif status == DeliveryStatus.FAILED:
                message.status = MessageStatus.FAILED
            
            if whatsapp_id:
                message.whatsapp_id = whatsapp_id
            
            # Update metadata
            message.message_metadata.update({
                "status_updated_at": datetime.utcnow().isoformat(),
                "delivery_status": status.value
            })
            
            if delivery_info:
                message.message_metadata["delivery_tracking"] = delivery_info
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to update delivery status for message {message_id}: {e}")
            return False

    @with_db_retry(max_retries=3)
    async def get_scheduled_messages(self,
                                   patient_id: UUID = None,
                                   limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get scheduled messages with optional patient filter.
        
        Args:
            patient_id: Optional patient filter
            limit: Maximum number of messages to return
            
        Returns:
            List of scheduled messages with task status
        """
        try:
            query = self.db.query(Message).filter(
                Message.status == MessageStatus.SCHEDULED
            )
            
            if patient_id:
                query = query.filter(Message.patient_id == patient_id)
            
            messages = query.order_by(Message.scheduled_for).limit(limit).all()
            
            result = []
            for message in messages:
                task_id = message.message_metadata.get("celery_task_id")
                task_status = await self._get_task_status(task_id) if task_id else None
                
                result.append({
                    "message_id": str(message.id),
                    "patient_id": str(message.patient_id),
                    "content": message.content,
                    "scheduled_for": message.scheduled_for.isoformat(),
                    "created_at": message.created_at.isoformat(),
                    "task_id": task_id,
                    "task_status": task_status,
                    "metadata": message.message_metadata
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get scheduled messages: {e}")
            return []

    @with_db_retry(max_retries=3)
    async def get_delivery_metrics(self,
                                 patient_id: UUID = None,
                                 days_back: int = 7) -> Dict[str, Any]:
        """
        Get message delivery metrics.
        
        Args:
            patient_id: Optional patient filter
            days_back: Number of days to analyze
            
        Returns:
            Delivery metrics and statistics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            query = self.db.query(Message).filter(
                Message.created_at >= cutoff_date
            )
            
            if patient_id:
                query = query.filter(Message.patient_id == patient_id)
            
            messages = query.all()
            
            if not messages:
                return {
                    "total_messages": 0,
                    "status_distribution": {},
                    "success_rate": 0.0,
                    "read_rate": 0.0,
                    "avg_delivery_time": None,
                    "period_days": days_back
                }
            
            # Calculate metrics
            total_messages = len(messages)
            status_counts = {}
            delivery_times = []
            
            for message in messages:
                status = message.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
                
                if message.sent_at and message.delivered_at:
                    delivery_time = (message.delivered_at - message.sent_at).total_seconds()
                    delivery_times.append(delivery_time)
            
            successful_messages = sum(
                status_counts.get(status, 0) 
                for status in ["sent", "delivered", "read"]
            )
            delivered_messages = sum(
                status_counts.get(status, 0)
                for status in ["delivered", "read"]
            )
            read_messages = status_counts.get("read", 0)
            
            return {
                "total_messages": total_messages,
                "status_distribution": status_counts,
                "success_rate": (successful_messages / total_messages) * 100 if total_messages > 0 else 0,
                "read_rate": (read_messages / delivered_messages) * 100 if delivered_messages > 0 else 0,
                "avg_delivery_time": sum(delivery_times) / len(delivery_times) if delivery_times else None,
                "period_days": days_back,
                "analysis_date": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get delivery metrics: {e}")
            return {"error": str(e)}

    async def _calculate_optimal_delivery_time(self,
                                             patient: Patient,
                                             scheduling_window: SchedulingWindow) -> datetime:
        """
        Calculate optimal delivery time based on patient timezone and scheduling window.
        
        Args:
            patient: Patient object
            scheduling_window: Preferred scheduling window
            
        Returns:
            Optimal delivery time in UTC
        """
        try:
            # Get patient timezone with validation
            patient_tz_str = self._get_patient_timezone(patient)
            
            try:
                patient_tz = pytz.timezone(patient_tz_str)
            except pytz.UnknownTimeZoneError:
                logger.warning(f"Unknown timezone {patient_tz_str} for patient {patient.id}, using default")
                patient_tz = pytz.timezone(self.config.DEFAULT_TIMEZONE)
            
            # Get current time in patient timezone
            utc_now = datetime.utcnow()
            patient_now = pytz.UTC.localize(utc_now).astimezone(patient_tz)
            
            # Validate scheduling window
            if scheduling_window not in self.scheduling_windows:
                logger.warning(f"Invalid scheduling window {scheduling_window}, using BUSINESS_HOURS")
                scheduling_window = SchedulingWindow.BUSINESS_HOURS
            
            # Get scheduling window times
            window_start, window_end = self.scheduling_windows[scheduling_window]
            
            # Check if current time is within window
            current_time = patient_now.time()
            
            if window_start <= current_time <= window_end:
                # Schedule for configured buffer time from now
                delivery_time_patient = patient_now + timedelta(minutes=self.config.MIN_SCHEDULING_BUFFER_MINUTES)
            else:
                # Schedule for next occurrence of window start
                if current_time < window_start:
                    # Later today
                    delivery_date = patient_now.date()
                else:
                    # Tomorrow
                    delivery_date = patient_now.date() + timedelta(days=1)
                
                delivery_time_patient = patient_tz.localize(
                    datetime.combine(delivery_date, window_start)
                )
            
            # Convert back to UTC
            delivery_time_utc = delivery_time_patient.astimezone(pytz.UTC).replace(tzinfo=None)
            
            # Ensure delivery time is not in the past
            if delivery_time_utc <= datetime.utcnow():
                delivery_time_utc = datetime.utcnow() + timedelta(minutes=self.config.FALLBACK_DELAY_MINUTES)
                logger.warning(f"Calculated delivery time was in the past, adjusted to {self.config.FALLBACK_DELAY_MINUTES} minutes from now")
            
            return delivery_time_utc
            
        except Exception as e:
            logger.error(f"Failed to calculate optimal delivery time for patient {patient.id}: {e}")
            raise TimezoneError(f"Unable to calculate delivery time: {e}")

    @with_db_retry(max_retries=3)
    async def schedule_existing_message(self,
                                       message_id: UUID,
                                       send_time: datetime,
                                       priority: str = 'normal') -> bool:
        """
        Schedule an existing message that has already been created in the database.
        This method is used when the message record exists but needs to be scheduled for delivery.

        Args:
            message_id: UUID of the existing message
            send_time: When to send the message
            priority: Message priority ('low', 'normal', 'high', 'urgent')

        Returns:
            True if scheduled successfully, False otherwise

        Raises:
            NotFoundError: If message doesn't exist
            ValidationError: If message is in invalid state for scheduling
        """
        try:
            # Validate priority
            valid_priorities = ['low', 'normal', 'high', 'urgent']
            if priority not in valid_priorities:
                logger.warning(f"Invalid priority '{priority}', using 'normal'")
                priority = 'normal'

            # Get the existing message
            message = self.message_repo.get(message_id)
            if not message:
                raise NotFoundError(f"Message {message_id} not found")

            # Validate message state
            if message.status not in [MessageStatus.PENDING, MessageStatus.SCHEDULED]:
                raise ValidationError(
                    f"Cannot schedule message {message_id} with status {message.status}. "
                    f"Message must be in PENDING or SCHEDULED status."
                )

            # Validate send_time is in the future
            if send_time <= datetime.utcnow():
                logger.warning(f"Send time {send_time} is in the past, adjusting to 1 minute from now")
                send_time = datetime.utcnow() + timedelta(minutes=1)

            # Update message with scheduling information
            message.scheduled_for = send_time
            message.status = MessageStatus.SCHEDULED

            # Add priority to metadata
            if message.message_metadata is None:
                message.message_metadata = {}
            message.message_metadata['priority'] = priority
            message.message_metadata['scheduled_at'] = datetime.utcnow().isoformat()

            # Schedule Celery task
            task_result = await self._schedule_celery_task(message, send_time)

            if task_result.get('task_id'):
                # Update message with task ID
                message.message_metadata['celery_task_id'] = task_result.get('task_id')
                message.message_metadata['scheduling_status'] = 'success'
                self.db.commit()

                logger.info(
                    f"Successfully scheduled existing message {message_id} for {send_time.isoformat()} "
                    f"with priority {priority}, task_id: {task_result.get('task_id')}"
                )
                return True
            else:
                # Scheduling failed
                message.message_metadata['scheduling_status'] = 'failed'
                message.message_metadata['scheduling_error'] = task_result.get('error', 'Unknown error')
                message.status = MessageStatus.FAILED
                self.db.commit()

                logger.error(
                    f"Failed to schedule message {message_id}: {task_result.get('error', 'Unknown error')}"
                )
                return False

        except NotFoundError:
            logger.error(f"Message {message_id} not found for scheduling")
            raise
        except ValidationError:
            logger.error(f"Invalid message state for scheduling: {message_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to schedule existing message {message_id}: {e}", exc_info=True)
            self.db.rollback()
            return False

    async def _get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get Celery task status.

        Args:
            task_id: Celery task ID

        Returns:
            Task status information
        """
        try:
            from celery.result import AsyncResult

            result = AsyncResult(task_id)

            return {
                "task_id": task_id,
                "status": result.status,
                "result": result.result if result.ready() else None,
                "traceback": result.traceback if result.failed() else None,
                "date_done": result.date_done
            }

        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return {
                "task_id": task_id,
                "status": "UNKNOWN",
                "error": str(e)
            }

    @with_db_retry(max_retries=3)
    async def on_delivery_failure(
        self,
        message_id: UUID,
        failure_reason: str,
        whatsapp_error: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle message delivery failure with retry logic and flow state update.

        Args:
            message_id: Message UUID that failed to deliver
            failure_reason: Human-readable failure reason
            whatsapp_error: WhatsApp API error details

        Returns:
            Dict containing failure handling results
        """
        try:
            message = self.message_repo.get(message_id)
            if not message:
                logger.error(f"Message {message_id} not found for delivery failure handling")
                return {
                    "status": "error",
                    "message": "Message not found",
                    "message_id": str(message_id)
                }

            # Update delivery status
            message.delivery_status = DeliveryStatus.FAILED
            message.status = MessageStatus.FAILED
            message.failure_reason = failure_reason
            message.last_retry_at = datetime.utcnow()

            # Store WhatsApp error details in metadata
            if whatsapp_error:
                message.message_metadata = message.message_metadata or {}
                message.message_metadata["whatsapp_error"] = whatsapp_error
                message.message_metadata["failure_timestamp"] = datetime.utcnow().isoformat()

            # Check if we should retry
            if message.retry_count < self.config.MAX_DELIVERY_RETRIES:
                # Calculate exponential backoff
                retry_delay = self._calculate_retry_delay(message.retry_count)
                next_retry = datetime.utcnow() + retry_delay

                message.retry_count += 1
                message.next_retry_at = next_retry

                # Schedule retry task
                await self._schedule_retry(message, next_retry)

                self.db.commit()

                logger.info(
                    f"Scheduled retry {message.retry_count}/{self.config.MAX_DELIVERY_RETRIES} "
                    f"for message {message_id} at {next_retry.isoformat()}"
                )

                return {
                    "status": "retry_scheduled",
                    "message_id": str(message_id),
                    "retry_count": message.retry_count,
                    "next_retry_at": next_retry.isoformat(),
                    "failure_reason": failure_reason
                }
            else:
                # Max retries exceeded - route to DLQ and update flow state
                message.next_retry_at = None

                # Route to DLQ before committing
                await self._route_to_dlq_on_max_retries(message, failure_reason, whatsapp_error)

                self.db.commit()

                # Notify flow engine of permanent failure
                await self._notify_flow_engine_failure(message)

                logger.error(
                    f"Message {message_id} failed permanently after "
                    f"{message.retry_count} retries: {failure_reason}"
                )

                return {
                    "status": "permanent_failure",
                    "message_id": str(message_id),
                    "retry_count": message.retry_count,
                    "failure_reason": failure_reason,
                    "flow_notified": True,
                    "dlq_routed": True
                }

        except Exception as e:
            logger.error(f"Error handling delivery failure for message {message_id}: {e}")
            self.db.rollback()
            return {
                "status": "error",
                "message": str(e),
                "message_id": str(message_id)
            }

    def _calculate_retry_delay(self, retry_count: int) -> timedelta:
        """
        Calculate exponential backoff delay for retry.

        Args:
            retry_count: Current retry attempt number

        Returns:
            Timedelta for retry delay
        """
        # Exponential backoff: initial_delay * (base ^ retry_count)
        delay_minutes = self.config.RETRY_INITIAL_DELAY_MINUTES * (
            self.config.RETRY_BACKOFF_BASE ** retry_count
        )

        # Cap maximum delay at 2 hours
        delay_minutes = min(delay_minutes, 120)

        return timedelta(minutes=delay_minutes)

    @with_db_retry(max_retries=3)
    async def _schedule_retry(self, message: Message, retry_time: datetime) -> None:
        """
        Schedule a retry attempt for a failed message.

        Args:
            message: Message to retry
            retry_time: When to retry the message
        """
        try:
            # Import here to avoid circular imports
            from app.tasks.flows import send_flow_message

            # Prepare message data
            message_data = {
                "content": message.content,
                "type": message.type.value,
                "metadata": message.message_metadata,
                "is_retry": True,
                "retry_count": message.retry_count
            }

            # Schedule retry task with ETA
            task_result = send_flow_message.apply_async(
                args=[str(message.patient_id), message_data, str(message.id)],
                eta=retry_time
            )

            # Update message metadata with retry task ID
            message.message_metadata["retry_task_id"] = task_result.id
            message.message_metadata["retry_scheduled_at"] = datetime.utcnow().isoformat()

            logger.info(
                f"Scheduled retry task {task_result.id} for message {message.id} "
                f"at {retry_time.isoformat()}"
            )

        except Exception as e:
            logger.error(f"Failed to schedule retry for message {message.id}: {e}")
            raise

    async def _route_to_dlq_on_max_retries(
        self,
        message: Message,
        failure_reason: str,
        whatsapp_error: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Route message to Dead Letter Queue when max retries exceeded.

        Args:
            message: Message that exceeded max retries
            failure_reason: Human-readable failure reason
            whatsapp_error: WhatsApp API error details
        """
        try:
            from app.integrations.whatsapp.queue.dlq import DLQHandler

            # Get patient phone number
            patient = self.patient_repo.get(message.patient_id)
            whatsapp_phone = patient.phone if patient else "unknown"

            # Categorize failure reason
            categorized_reason = self._categorize_failure_reason(whatsapp_error or {"error": failure_reason})

            # Prepare failure details
            failure_details = {
                "original_failure_reason": failure_reason,
                "whatsapp_error": whatsapp_error,
                "max_retries": message.retry_count,
                "last_retry_at": message.last_retry_at.isoformat() if message.last_retry_at else None,
                "routed_at": datetime.utcnow().isoformat()
            }

            # Route to DLQ
            dlq_handler = DLQHandler(self.db)
            await dlq_handler.route_to_dlq(
                message_id=message.id,
                patient_id=message.patient_id,
                content=message.content,
                whatsapp_phone=whatsapp_phone,
                failure_reason=categorized_reason,
                failure_details=failure_details,
                retry_count=message.retry_count,
                metadata=message.message_metadata
            )

            logger.info(
                f"Message {message.id} routed to DLQ after {message.retry_count} retries"
            )

        except Exception as e:
            logger.error(
                f"Failed to route message {message.id} to DLQ: {e}",
                exc_info=True
            )
            # Don't raise - DLQ routing failure shouldn't break delivery failure handling

    def _categorize_failure_reason(self, delivery_info: Dict[str, Any] = None) -> FailureReason:
        """
        Categorize failure reason from delivery info.

        Args:
            delivery_info: Delivery failure information

        Returns:
            Categorized FailureReason
        """
        if not delivery_info:
            return FailureReason.UNKNOWN

        error_message = str(delivery_info.get('error', '')).lower()
        error_code = delivery_info.get('error_code', '')

        # Network errors
        if 'timeout' in error_message or 'timed out' in error_message:
            return FailureReason.TIMEOUT
        if 'network' in error_message or 'connection' in error_message:
            return FailureReason.NETWORK_ERROR

        # Phone number issues
        if 'invalid' in error_message and 'phone' in error_message:
            return FailureReason.INVALID_PHONE
        if 'blocked' in error_message or 'banned' in error_message:
            return FailureReason.BLOCKED_NUMBER

        # API errors
        if 'rate limit' in error_message or error_code in [429, '429']:
            return FailureReason.RATE_LIMIT
        if error_code in [400, 401, 403, 404, 500, 502, 503, 504]:
            return FailureReason.API_ERROR

        # Max retries (explicit)
        if 'max retries' in error_message or 'retry limit' in error_message:
            return FailureReason.MAX_RETRIES_EXCEEDED

        return FailureReason.UNKNOWN

    @with_db_retry(max_retries=3)
    async def _notify_flow_engine_failure(self, message: Message) -> None:
        """
        Notify flow engine when a message permanently fails.
        Updates flow state to prevent being stuck in "waiting" state.

        Args:
            message: Message that permanently failed
        """
        try:
            # Get flow context from message metadata
            flow_context = message.message_metadata.get("flow_context", {})

            if not flow_context:
                logger.warning(
                    f"No flow context found in message {message.id} metadata, "
                    f"cannot update flow state"
                )
                return

            # Import FlowStateRepository to update flow state
            from app.repositories.flow import FlowStateRepository

            flow_repo = FlowStateRepository(self.db)

            # Get active flow for patient
            active_flow = flow_repo.get_active_flow(message.patient_id)

            if not active_flow:
                logger.warning(
                    f"No active flow found for patient {message.patient_id}, "
                    f"cannot update flow state"
                )
                return

            # Update flow state to handle delivery failure
            flow_state_data = active_flow.state_data or {}
            flow_state_data["delivery_failures"] = flow_state_data.get("delivery_failures", [])
            flow_state_data["delivery_failures"].append({
                "message_id": str(message.id),
                "failure_timestamp": datetime.utcnow().isoformat(),
                "failure_reason": message.failure_reason,
                "retry_count": message.retry_count,
                "step": active_flow.current_step
            })

            # Mark that flow should not wait for this message
            flow_state_data["skip_waiting_for_message"] = str(message.id)
            flow_state_data["last_delivery_failure"] = datetime.utcnow().isoformat()

            active_flow.state_data = flow_state_data
            self.db.commit()

            logger.info(
                f"Updated flow state for patient {message.patient_id} "
                f"due to permanent message delivery failure {message.id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to notify flow engine of delivery failure for message {message.id}: {e}"
            )
            # Don't raise - this is a best-effort notification


# Dependency injection function
def get_message_scheduler(db: Session, config: MessageSchedulerConfig = None) -> MessageScheduler:
    """Get MessageScheduler instance with database session and optional configuration."""
    return MessageScheduler(db, config)