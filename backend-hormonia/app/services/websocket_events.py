"""
WebSocket event broadcasting service for real-time notifications.
Handles broadcasting of system events, alerts, and flow updates via WebSocket.
"""
import logging
import json
from typing import Any, List, Optional, Dict
from datetime import datetime
from uuid import UUID
from pydantic import ValidationError

from redis import Redis

from app.schemas.websocket import (
    WebSocketEventType, 
    create_websocket_message,
    FlowEventData,
    AlertEventData,
    SystemEventData,
    MessageEventData,
    QuizEventData,
    ReportEventData
)
from app.services.websocket_manager import connection_manager

logger = logging.getLogger(__name__)


class WebSocketEventService:
    """Service for broadcasting WebSocket events."""
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def broadcast_flow_event(self, event_type: WebSocketEventType, 
                                 patient_id: UUID, flow_data: dict[str, Any]) -> int:
        """Broadcast flow-related event."""
        try:
            # Create flow event data
            event_data = FlowEventData(
                patient_id=patient_id,
                flow_type=flow_data.get('flow_type', ''),
                current_day=flow_data.get('current_day', 0),
                previous_day=flow_data.get('previous_day'),
                is_paused=flow_data.get('is_paused', False),
                enrollment_date=flow_data.get('enrollment_date', datetime.utcnow()),
                last_message_sent=flow_data.get('last_message_sent'),
                monthly_cycle=flow_data.get('monthly_cycle'),
                changes=flow_data.get('changes'),
                milestone_reached=flow_data.get('milestone_reached'),
                metadata=flow_data.get('metadata', {})
            )
            
            # Create WebSocket message
            message = create_websocket_message(event_type, event_data)
            
            # Broadcast to patient room
            sent_count = await connection_manager.broadcast_to_patient_room(
                message.dict(), str(patient_id)
            )
            
            logger.info(f"Broadcasted flow event {event_type.value} for patient {patient_id} to {sent_count} connections")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error broadcasting flow event: {e}")
            return 0
    
    async def broadcast_alert_event(self, event_type: WebSocketEventType,
                                  alert_data: dict[str, Any]) -> int:
        """Broadcast alert-related event."""
        try:
            # Create alert event data
            event_data = AlertEventData(
                alert_id=UUID(alert_data['alert_id']),
                patient_id=UUID(alert_data['patient_id']),
                alert_type=alert_data.get('alert_type', ''),
                severity=alert_data.get('severity', 'medium'),
                title=alert_data.get('title', ''),
                description=alert_data.get('description'),
                acknowledged=alert_data.get('acknowledged', False),
                acknowledged_by=UUID(alert_data['acknowledged_by']) if alert_data.get('acknowledged_by') else None,
                acknowledged_at=alert_data.get('acknowledged_at'),
                resolved=alert_data.get('resolved', False),
                resolved_by=UUID(alert_data['resolved_by']) if alert_data.get('resolved_by') else None,
                resolved_at=alert_data.get('resolved_at'),
                metadata=alert_data.get('metadata', {})
            )
            
            # Create WebSocket message
            message = create_websocket_message(event_type, event_data)
            
            # Broadcast to all authenticated connections for alerts
            sent_count = await connection_manager.broadcast_to_all_authenticated(message.dict())
            
            # Also broadcast to specific patient room if patient_id is provided
            if 'patient_id' in alert_data:
                patient_sent_count = await connection_manager.broadcast_to_patient_room(
                    message.dict(), str(alert_data['patient_id'])
                )
                sent_count += patient_sent_count
            
            logger.info(f"Broadcasted alert event {event_type.value} to {sent_count} connections")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error broadcasting alert event: {e}")
            return 0
    
    async def broadcast_message_event(self, event_type: WebSocketEventType,
                                    message_data: dict[str, Any]) -> int:
        """Broadcast message-related event."""
        try:
            # Create message event data
            event_data = MessageEventData(
                message_id=UUID(message_data['message_id']),
                patient_id=UUID(message_data['patient_id']),
                direction=message_data.get('direction', 'outbound'),
                type=message_data.get('type', 'text'),
                content=message_data.get('content'),
                status=message_data.get('status'),
                whatsapp_id=message_data.get('whatsapp_id'),
                metadata=message_data.get('metadata', {})
            )
            
            # Create WebSocket message
            message = create_websocket_message(event_type, event_data)
            
            # Broadcast to patient room
            sent_count = await connection_manager.broadcast_to_patient_room(
                message.dict(), str(message_data['patient_id'])
            )
            
            logger.info(f"Broadcasted message event {event_type.value} for patient {message_data['patient_id']} to {sent_count} connections")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error broadcasting message event: {e}")
            return 0
    
    async def broadcast_quiz_event(self, event_type: WebSocketEventType,
                                 quiz_data: dict[str, Any]) -> int:
        """Broadcast quiz-related event with proper parameter handling."""
        try:
            # Create quiz event data with proper parameter mapping
            event_data = QuizEventData(
                quiz_id=UUID(quiz_data['quiz_id']) if quiz_data.get('quiz_id') else None,
                patient_id=UUID(quiz_data['patient_id']),
                template_id=UUID(quiz_data['template_id']) if quiz_data.get('template_id') else None,
                session_id=UUID(quiz_data['session_id']) if quiz_data.get('session_id') else None,
                response_id=UUID(quiz_data['response_id']) if quiz_data.get('response_id') else None,
                question_id=quiz_data.get('question_id'),
                answer=quiz_data.get('answer'),
                completed=quiz_data.get('completed', False),
                score=quiz_data.get('score'),
                metadata=quiz_data.get('metadata', {})
            )
            
            # Create WebSocket message
            message = create_websocket_message(event_type, event_data)
            
            # Broadcast to patient room
            sent_count = await connection_manager.broadcast_to_patient_room(
                message.dict(), str(quiz_data['patient_id'])
            )
            
            logger.info(f"Broadcasted quiz event {event_type.value} for patient {quiz_data['patient_id']} to {sent_count} connections")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error broadcasting quiz event: {e}")
            return 0
    
    async def broadcast_report_event(self, event_type: WebSocketEventType,
                                   report_data: dict[str, Any]) -> int:
        """Broadcast report-related event."""
        try:
            # Create report event data
            event_data = ReportEventData(
                report_id=UUID(report_data['report_id']),
                patient_id=UUID(report_data['patient_id']),
                report_type=report_data.get('report_type', ''),
                status=report_data.get('status', 'generating'),
                file_path=report_data.get('file_path'),
                error_message=report_data.get('error_message'),
                metadata=report_data.get('metadata', {})
            )
            
            # Create WebSocket message
            message = create_websocket_message(event_type, event_data)
            
            # Broadcast to patient room
            sent_count = await connection_manager.broadcast_to_patient_room(
                message.dict(), str(report_data['patient_id'])
            )
            
            logger.info(f"Broadcasted report event {event_type.value} for patient {report_data['patient_id']} to {sent_count} connections")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error broadcasting report event: {e}")
            return 0
    
    async def broadcast_system_event(self, event_type: WebSocketEventType,
                                   system_data: dict[str, Any]) -> int:
        """Broadcast system-related event."""
        try:
            # Create system event data
            event_data = SystemEventData(
                message=system_data.get('message', ''),
                level=system_data.get('level', 'info'),
                affected_services=system_data.get('affected_services'),
                estimated_duration=system_data.get('estimated_duration'),
                metadata=system_data.get('metadata', {})
            )
            
            # Create WebSocket message
            message = create_websocket_message(event_type, event_data)
            
            # Broadcast to all authenticated connections for system events
            sent_count = await connection_manager.broadcast_to_all_authenticated(message.dict())
            
            logger.info(f"Broadcasted system event {event_type.value} to {sent_count} connections")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error broadcasting system event: {e}")
            return 0
    
    async def broadcast_to_all_authenticated(self, message: dict[str, Any]) -> int:
        """Broadcast message to all authenticated connections."""
        try:
            sent_count = await connection_manager.broadcast_to_all_authenticated(message)
            logger.info(f"Broadcasted message to {sent_count} authenticated connections")
            return sent_count
        except Exception as e:
            logger.error(f"Error broadcasting to all authenticated: {e}")
            return 0
    
    async def broadcast_to_patient_room(self, message: dict[str, Any], patient_id: str) -> int:
        """Broadcast message to specific patient room."""
        try:
            sent_count = await connection_manager.broadcast_to_patient_room(message, patient_id)
            logger.info(f"Broadcasted message to patient {patient_id} room: {sent_count} connections")
            return sent_count
        except Exception as e:
            logger.error(f"Error broadcasting to patient room {patient_id}: {e}")
            return 0
    
    async def broadcast_to_user(self, message: dict[str, Any], user_id: str) -> int:
        """Broadcast message to specific user."""
        try:
            sent_count = await connection_manager.broadcast_to_user(message, user_id)
            logger.info(f"Broadcasted message to user {user_id}: {sent_count} connections")
            return sent_count
        except Exception as e:
            logger.error(f"Error broadcasting to user {user_id}: {e}")
            return 0
    
    # Convenience methods for common events
    async def notify_flow_progression(self, patient_id: UUID, flow_data: dict[str, Any]) -> int:
        """Notify about flow progression."""
        return await self.broadcast_flow_event(
            WebSocketEventType.FLOW_PROGRESSION, 
            patient_id, 
            flow_data
        )
    
    async def notify_flow_state_changed(self, patient_id: UUID, flow_data: dict[str, Any]) -> int:
        """Notify about flow state change."""
        return await self.broadcast_flow_event(
            WebSocketEventType.FLOW_STATE_CHANGED, 
            patient_id, 
            flow_data
        )
    
    async def notify_message_sent(self, patient_id: UUID, message_data: dict[str, Any]) -> int:
        """Notify about message sent."""
        return await self.broadcast_message_event(
            WebSocketEventType.MESSAGE_SENT, 
            message_data
        )
    
    async def notify_message_delivered(self, patient_id: UUID, message_data: dict[str, Any]) -> int:
        """Notify about message delivered."""
        return await self.broadcast_message_event(
            WebSocketEventType.MESSAGE_DELIVERED, 
            message_data
        )
    
    async def notify_message_failed(self, patient_id: UUID, message_data: dict[str, Any]) -> int:
        """Notify about message failure."""
        return await self.broadcast_message_event(
            WebSocketEventType.MESSAGE_FAILED, 
            message_data
        )
    
    async def notify_quiz_started(self, patient_id: UUID, quiz_data: dict[str, Any]) -> int:
        """Notify about quiz started."""
        return await self.broadcast_quiz_event(
            WebSocketEventType.QUIZ_STARTED, 
            quiz_data
        )
    
    async def notify_quiz_completed(self, patient_id: UUID, quiz_data: dict[str, Any]) -> int:
        """Notify about quiz completed."""
        return await self.broadcast_quiz_event(
            WebSocketEventType.QUIZ_COMPLETED, 
            quiz_data
        )
    
    async def notify_report_generated(self, patient_id: UUID, report_data: dict[str, Any]) -> int:
        """Notify about report generation completion."""
        return await self.broadcast_report_event(
            WebSocketEventType.REPORT_GENERATION_COMPLETED, 
            report_data
        )
    
    async def notify_alert_created(self, alert_data: dict[str, Any]) -> int:
        """Notify about new alert."""
        return await self.broadcast_alert_event(
            WebSocketEventType.ALERT_CREATED, 
            alert_data
        )
    
    async def notify_alert_resolved(self, alert_data: dict[str, Any]) -> int:
        """Notify about alert resolution."""
        return await self.broadcast_alert_event(
            WebSocketEventType.ALERT_RESOLVED, 
            alert_data
        )
    
    async def notify_system_maintenance(self, message: str, affected_services: List[str] = None) -> int:
        """Notify about system maintenance."""
        system_data = {
            'message': message,
            'level': 'warning',
            'affected_services': affected_services or [],
            'metadata': {'maintenance_type': 'scheduled'}
        }
        return await self.broadcast_system_event(
            WebSocketEventType.SYSTEM_MAINTENANCE, 
            system_data
        )
    
    async def notify_system_notification(self, message: str, level: str = 'info') -> int:
        """Send general system notification."""
        system_data = {
            'message': message,
            'level': level,
            'metadata': {'notification_type': 'general'}
        }
        return await self.broadcast_system_event(
            WebSocketEventType.SYSTEM_NOTIFICATION,
            system_data
        )

    async def publish_quiz_event(self, event_type: WebSocketEventType,
                               patient_id: UUID, quiz_id: Optional[UUID] = None,
                               template_id: Optional[UUID] = None,
                               session_id: Optional[UUID] = None,
                               response_id: Optional[UUID] = None,
                               question_id: Optional[str] = None,
                               answer: Optional[Any] = None,
                               completed: bool = False,
                               score: Optional[float] = None,
                               **kwargs) -> int:
        """Publish quiz event with comprehensive parameter support."""
        quiz_data = {
            'patient_id': patient_id,
            'quiz_id': quiz_id,
            'template_id': template_id,
            'session_id': session_id,
            'response_id': response_id,
            'question_id': question_id,
            'answer': answer,
            'completed': completed,
            'score': score,
            'metadata': kwargs
        }
        return await self.broadcast_quiz_event(event_type, quiz_data)


# Global instance for easy import
# This will be initialized with Redis connection when the app starts
websocket_events: Optional[WebSocketEventService] = None