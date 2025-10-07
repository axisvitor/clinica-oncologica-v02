"""
MessageSender service for outbound WhatsApp messages.
DEPRECATED: This service now delegates to UnifiedWhatsAppService for better maintainability.
Enhanced with flow-specific message handling and delivery callbacks.

Migration Notice:
- Direct usage of MessageSender is deprecated
- Use UnifiedWhatsAppService for new implementations
- Existing code continues to work for backward compatibility
"""
import logging
from typing import Any, Optional, Callable
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.integrations.evolution import get_evolution_client, EvolutionAPIError
from app.integrations.whatsapp.services.message_service import WhatsAppMessageService as WhatsAppQueueService
from app.models.message import Message, MessageType, MessageStatus
from app.models.flow import PatientFlowState
from app.services.message import MessageService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
from app.exceptions import ExternalServiceError, NotFoundError


logger = logging.getLogger(__name__)

# Deprecation warnings
import warnings
warnings.warn(
    "MessageSender is deprecated. Use UnifiedWhatsAppService instead.",
    DeprecationWarning,
    stacklevel=2
)

# Legacy mode deprecation
def _warn_legacy_mode():
    """Warn about legacy mode usage."""
    warnings.warn(
        "MessagingMode.LEGACY is deprecated and will be removed in a future version. "
        "Use MessagingMode.QUEUE for retry/backoff policies.",
        DeprecationWarning,
        stacklevel=3
    )


class MessageSender:
    """
    DEPRECATED: Service for sending outbound messages via WhatsApp with flow integration.

    This class now delegates to UnifiedWhatsAppService for actual implementation.
    Maintains backward compatibility while encouraging migration to the unified service.
    """

    def __init__(self, db: Session, messaging_mode: MessagingMode = MessagingMode.QUEUE):
        """
        Initialize MessageSender with configurable messaging mode.

        Args:
            db: Database session
            messaging_mode: Messaging mode (default: QUEUE for retry/backoff policies)
        """
        self.db = db
        self.message_service = MessageService(db)
        self.messaging_mode = messaging_mode

        # Warn if using legacy mode
        if messaging_mode == MessagingMode.LEGACY:
            _warn_legacy_mode()
            logger.warning("MessageSender using LEGACY mode - retry/backoff policies may be limited")
        else:
            logger.info(f"MessageSender using {messaging_mode.value} mode with full retry/backoff support")

        # Initialize unified service as delegate
        self._unified_service = UnifiedWhatsAppService(
            db=db,
            messaging_mode=messaging_mode  # Use queue mode by default for retry/backoff
        )

        # Log mode selection for monitoring
        logger.info(f"MessageSender initialized with messaging_mode={messaging_mode.value}")

        # Note: WhatsAppQueueService (queue-based service) is imported for reference
        # but actual implementation is delegated to UnifiedWhatsAppService for consistency
        # self._queue_service = WhatsAppQueueService  # Available if needed

        # Delegate callback registration to unified service
        self.flow_message_callbacks: dict[str, Callable] = {}

        # Maintain legacy retry policies for compatibility
        self.retry_policies: dict[str, dict[str, Any]] = {
            'default': {
                'max_retries': 3,
                'backoff_factor': 2,
                'base_delay': 300  # 5 minutes
            },
            'flow_message': {
                'max_retries': 5,
                'backoff_factor': 1.5,
                'base_delay': 180  # 3 minutes
            },
            'urgent': {
                'max_retries': 7,
                'backoff_factor': 1.2,
                'base_delay': 60  # 1 minute
            }
        }

        logger.warning("MessageSender is deprecated. Consider migrating to UnifiedWhatsAppService.")
    
    def register_flow_callback(self, callback_type: str, callback: Callable):
        """Register callback for flow message events."""
        self.flow_message_callbacks[callback_type] = callback
        # Delegate to unified service
        self._unified_service.register_flow_callback(callback_type, callback)
        logger.info(f"Registered flow callback: {callback_type}")
    
    async def send_flow_message(self,
                              message: Message,
                              flow_context: Optional[dict[str, Any]] = None) -> bool:
        """
        Send a flow-specific message with enhanced tracking and callbacks.

        DEPRECATED: Delegates to UnifiedWhatsAppService.send_flow_message()

        Args:
            message: Message object to send
            flow_context: Flow-specific context data

        Returns:
            True if message was sent successfully, False otherwise
        """
        logger.debug(f"MessageSender.send_flow_message delegating to UnifiedWhatsAppService for message {message.id}")
        return await self._unified_service.send_flow_message(message, flow_context)
    
    async def send_message(self, message: Message) -> bool:
        """
        Send a message via WhatsApp Evolution API.

        DEPRECATED: Delegates to UnifiedWhatsAppService.send_message()

        Args:
            message: Message object to send

        Returns:
            True if message was sent successfully, False otherwise
        """
        logger.debug(f"MessageSender.send_message delegating to UnifiedWhatsAppService for message {message.id}")
        return await self._unified_service.send_message(message)
    
    # Legacy methods removed - now handled by UnifiedWhatsAppService
    # _send_by_type, _extract_message_id, _mark_message_failed are deprecated
    
    async def send_scheduled_messages(self, limit: int = 100) -> int:
        """
        Send scheduled messages that are due for delivery.
        
        Args:
            limit: Maximum number of messages to process
            
        Returns:
            Number of messages processed
        """
        current_time = datetime.utcnow()
        scheduled_messages = self.message_service.get_scheduled_messages(
            before_time=current_time,
            limit=limit
        )
        
        sent_count = 0
        
        for message in scheduled_messages:
            try:
                success = await self.send_message(message)
                if success:
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to send scheduled message {message.id}: {e}", exc_info=True)
                await self._mark_message_failed(message, {
                    "error": "Scheduled send failed",
                    "message": str(e)
                })
        
        logger.info(f"Processed {len(scheduled_messages)} scheduled messages, sent {sent_count}")
        return sent_count
    
    async def retry_failed_messages(self, limit: int = 50) -> int:
        """
        Retry sending failed messages using dynamic retry policies.

        DEPRECATED: Delegates to UnifiedWhatsAppService.retry_failed_messages()

        Args:
            limit: Maximum number of messages to retry

        Returns:
            Number of messages successfully retried
        """
        logger.debug(f"MessageSender.retry_failed_messages delegating to UnifiedWhatsAppService (limit={limit})")
        return await self._unified_service.retry_failed_messages(limit)
    
    async def get_message_delivery_status(self, message_id: UUID) -> Optional[dict[str, Any]]:
        """
        Get detailed delivery status for a message.
        
        Args:
            message_id: Message ID to check
            
        Returns:
            Dictionary with delivery status information
        """
        message = self.message_service.get_message(message_id)
        
        if not message:
            return None
        
        status_info = {
            'message_id': str(message.id),
            'whatsapp_id': message.whatsapp_id,
            'status': message.status.value,
            'created_at': message.created_at.isoformat() if message.created_at else None,
            'sent_at': message.sent_at.isoformat() if message.sent_at else None,
            'delivered_at': message.delivered_at.isoformat() if message.delivered_at else None,
            'read_at': message.read_at.isoformat() if message.read_at else None,
            'metadata': message.message_metadata or {}
        }
        
        # Calculate delivery metrics
        if message.sent_at and message.created_at:
            send_delay = (message.sent_at - message.created_at).total_seconds()
            status_info['send_delay_seconds'] = send_delay
        
        if message.delivered_at and message.sent_at:
            delivery_delay = (message.delivered_at - message.sent_at).total_seconds()
            status_info['delivery_delay_seconds'] = delivery_delay
        
        if message.read_at and message.delivered_at:
            read_delay = (message.read_at - message.delivered_at).total_seconds()
            status_info['read_delay_seconds'] = read_delay
        
        return status_info
    
    async def update_flow_message_status(self, 
                                       message_id: UUID, 
                                       status: MessageStatus,
                                       flow_state_id: Optional[UUID] = None,
                                       additional_data: Optional[dict[str, Any]] = None) -> bool:
        """
        Update flow message status with flow-specific tracking.
        
        Args:
            message_id: Message ID to update
            status: New message status
            flow_state_id: Associated flow state ID (optional)
            additional_data: Additional tracking data
            
        Returns:
            True if update was successful
        """
        try:
            message = self.message_service.get_message(message_id)
            if not message:
                logger.error(f"Message {message_id} not found for status update")
                return False
            
            # Update message status
            update_data = {'status': status}
            
            # Add timestamp based on status
            current_time = datetime.utcnow()
            if status == MessageStatus.SENT:
                update_data['sent_at'] = current_time
            elif status == MessageStatus.DELIVERED:
                update_data['delivered_at'] = current_time
            elif status == MessageStatus.READ:
                update_data['read_at'] = current_time
            
            # Update metadata with flow tracking
            metadata = message.message_metadata or {}
            metadata['status_updates'] = metadata.get('status_updates', [])
            metadata['status_updates'].append({
                'status': status.value,
                'timestamp': current_time.isoformat(),
                'flow_state_id': str(flow_state_id) if flow_state_id else None
            })
            
            if additional_data:
                metadata.update(additional_data)
            
            update_data['message_metadata'] = metadata
            
            # Perform update
            self.message_service.update_message(message_id, update_data)
            
            # Execute status update callback
            if 'status_updated' in self.flow_message_callbacks:
                try:
                    await self.flow_message_callbacks['status_updated'](
                        message, status, flow_state_id, additional_data
                    )
                except Exception as e:
                    logger.error(f"Status update callback error: {e}")
            
            logger.info(f"Updated message {message_id} status to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update flow message status: {e}")
            return False
    
    async def get_flow_message_metrics(self, 
                                     flow_state_id: UUID,
                                     date_range: Optional[tuple] = None) -> dict[str, Any]:
        """
        Get delivery metrics for flow messages.
        
        Args:
            flow_state_id: Flow state ID to analyze
            date_range: Optional date range tuple (start, end)
            
        Returns:
            Flow message metrics
        """
        try:
            # This would query messages associated with the flow
            # For now, return basic structure
            metrics = {
                'flow_state_id': str(flow_state_id),
                'total_messages': 0,
                'sent_messages': 0,
                'delivered_messages': 0,
                'read_messages': 0,
                'failed_messages': 0,
                'delivery_rate': 0.0,
                'read_rate': 0.0,
                'average_delivery_time': None,
                'average_read_time': None,
                'retry_statistics': {
                    'total_retries': 0,
                    'successful_retries': 0,
                    'failed_after_retries': 0
                }
            }
            
            # TODO: Implement actual metrics calculation
            # This would involve querying the messages table with flow context
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get flow message metrics: {e}")
            return {}
    
    async def cancel_scheduled_flow_messages(self, 
                                           patient_id: UUID,
                                           flow_type: Optional[str] = None) -> int:
        """
        Cancel scheduled flow messages for a patient.
        
        Args:
            patient_id: Patient ID
            flow_type: Specific flow type to cancel (optional)
            
        Returns:
            Number of messages cancelled
        """
        try:
            # Get scheduled messages for patient
            scheduled_messages = self.message_service.get_scheduled_messages_for_patient(
                patient_id=patient_id,
                status=MessageStatus.PENDING
            )
            
            cancelled_count = 0
            
            for message in scheduled_messages:
                # Check if message matches flow type filter
                if flow_type:
                    metadata = message.message_metadata or {}
                    flow_context = metadata.get('flow_context', {})
                    if flow_context.get('flow_type') != flow_type:
                        continue
                
                # Cancel the message
                self.message_service.update_message(message.id, {
                    'status': MessageStatus.FAILED,
                    'message_metadata': {
                        **metadata,
                        'cancelled': True,
                        'cancelled_at': datetime.utcnow().isoformat(),
                        'cancellation_reason': 'Flow cancellation'
                    }
                })
                
                cancelled_count += 1
                logger.info(f"Cancelled scheduled message {message.id}")
            
            logger.info(f"Cancelled {cancelled_count} scheduled flow messages for patient {patient_id}")
            return cancelled_count
            
        except Exception as e:
            logger.error(f"Failed to cancel scheduled flow messages: {e}")
            return 0