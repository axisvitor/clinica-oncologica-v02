"""
Flow Event Broadcasting Service for real-time WebSocket updates.

This service handles broadcasting flow-related events to healthcare providers
through WebSocket connections, enabling real-time monitoring of patient flows.
"""
import logging
from typing import Any, Optional, List
from uuid import UUID
from datetime import datetime

from app.services.websocket_manager import connection_manager
from app.schemas.websocket import (
    WebSocketEventType,
    create_websocket_message,
    PatientEventData,
    MessageEventData,
    AlertEventData,
    ReportEventData
)
from app.models.flow import PatientFlowState
from app.models.message import Message
from app.models.alert import Alert

logger = logging.getLogger(__name__)


class FlowEventBroadcaster:
    """
    Service for broadcasting flow-related events via WebSocket.
    
    Handles real-time notifications for:
    - Flow state changes and progressions
    - Patient interaction updates
    - Alert generation and updates
    - Report completion notifications
    """
    
    def __init__(self):
        self.connection_manager = connection_manager
    
    async def broadcast_flow_state_change(
        self,
        patient_id: UUID,
        flow_state: PatientFlowState,
        previous_state: Optional[dict[str, Any]] = None
    ) -> int:
        """
        Broadcast flow state change to healthcare providers monitoring the patient.

        Args:
            patient_id: Patient whose flow state changed
            flow_state: New flow state
            previous_state: Previous flow state data for comparison

        Returns:
            Number of connections that received the broadcast
        """
        try:
            # Check if connection manager is available
            if not self.connection_manager:
                logger.warning("Connection manager not available, skipping broadcast")
                return 0

            # Determine what changed
            changes = {}
            if previous_state:
                if previous_state.get("flow_type") != flow_state.flow_type:
                    changes["flow_type"] = {
                        "from": previous_state.get("flow_type"),
                        "to": flow_state.flow_type
                    }
                if previous_state.get("current_day") != flow_state.current_day:
                    changes["current_day"] = {
                        "from": previous_state.get("current_day"),
                        "to": flow_state.current_day
                    }
                if previous_state.get("is_paused") != flow_state.is_paused:
                    changes["is_paused"] = {
                        "from": previous_state.get("is_paused"),
                        "to": flow_state.is_paused
                    }

            # Create event data
            event_data = PatientEventData(
                patient_id=patient_id,
                changes=changes,
                metadata={
                    "flow_type": flow_state.flow_type,
                    "current_day": flow_state.current_day,
                    "is_paused": flow_state.is_paused,
                    "enrollment_date": flow_state.enrollment_date.isoformat(),
                    "last_message_sent": flow_state.last_message_sent.isoformat() if flow_state.last_message_sent else None,
                    "monthly_cycle": flow_state.monthly_cycle
                }
            )

            # Create WebSocket message
            message = create_websocket_message(
                WebSocketEventType.PATIENT_FLOW_CHANGED,
                event_data
            )

            # Broadcast to patient room with error handling
            try:
                sent_count = await self.connection_manager.broadcast_to_patient_room(
                    message.dict(), str(patient_id)
                )

                logger.info(
                    f"Broadcasted flow state change for patient {patient_id} "
                    f"to {sent_count} connections"
                )

                return sent_count
            except Exception as broadcast_error:
                logger.warning(f"WebSocket broadcast failed (non-critical): {broadcast_error}")
                return 0

        except Exception as e:
            logger.error(f"Error broadcasting flow state change: {e}", exc_info=True)
            return 0
    
    async def broadcast_patient_interaction(
        self,
        patient_id: UUID,
        message: Message,
        interaction_type: str = "message_received"
    ) -> int:
        """
        Broadcast patient interaction update to monitoring healthcare providers.

        Args:
            patient_id: Patient who interacted
            message: Message object representing the interaction
            interaction_type: Type of interaction (message_received, response_sent, etc.)

        Returns:
            Number of connections that received the broadcast
        """
        try:
            # Check prerequisites
            if not self.connection_manager:
                logger.debug("Connection manager unavailable, skipping patient interaction broadcast")
                return 0

            # Create event data
            event_data = MessageEventData(
                message_id=message.id,
                patient_id=patient_id,
                direction=message.direction,
                type=message.type,
                content=message.content[:100] + "..." if len(message.content) > 100 else message.content,
                status=message.status,
                whatsapp_id=message.whatsapp_id,
                metadata={
                    "interaction_type": interaction_type,
                    "timestamp": message.created_at.isoformat(),
                    "has_media": bool(message.media_url),
                    "is_interactive": message.type in ["button", "list", "quick_reply"]
                }
            )

            # Create WebSocket message
            message_ws = create_websocket_message(
                WebSocketEventType.NEW_MESSAGE,
                event_data
            )

            # Broadcast to patient room with error handling
            try:
                sent_count = await self.connection_manager.broadcast_to_patient_room(
                    message_ws.dict(), str(patient_id)
                )

                logger.info(
                    f"Broadcasted patient interaction for patient {patient_id} "
                    f"to {sent_count} connections"
                )

                return sent_count
            except Exception as broadcast_error:
                logger.warning(f"WebSocket broadcast failed (non-critical): {broadcast_error}")
                return 0

        except Exception as e:
            logger.error(f"Error broadcasting patient interaction: {e}")
            return 0
    
    async def broadcast_alert_created(
        self,
        alert: Alert,
        patient_id: UUID
    ) -> int:
        """
        Broadcast alert creation to healthcare providers.
        
        Args:
            alert: Alert that was created
            patient_id: Patient the alert is related to
            
        Returns:
            Number of connections that received the broadcast
        """
        try:
            # Create event data
            event_data = AlertEventData(
                alert_id=alert.id,
                patient_id=patient_id,
                alert_type=alert.type,
                severity=alert.severity,
                title=alert.title,
                description=alert.description,
                acknowledged=alert.acknowledged,
                acknowledged_by=alert.acknowledged_by,
                acknowledged_at=alert.acknowledged_at,
                resolved=alert.resolved,
                resolved_by=alert.resolved_by,
                resolved_at=alert.resolved_at,
                metadata={
                    "created_at": alert.created_at.isoformat(),
                    "source": "flow_system",
                    "requires_immediate_attention": alert.severity in ["high", "critical"]
                }
            )
            
            # Create WebSocket message
            message = create_websocket_message(
                WebSocketEventType.ALERT_CREATED,
                event_data
            )
            
            # Broadcast to patient room and all authenticated users for critical alerts
            sent_count = await self.connection_manager.broadcast_to_patient_room(
                message.dict(), str(patient_id)
            )
            
            # For critical alerts, also broadcast to all authenticated healthcare providers
            if alert.severity == "critical":
                additional_sent = await self.connection_manager.broadcast_to_all_authenticated(
                    message.dict()
                )
                sent_count += additional_sent
            
            logger.info(
                f"Broadcasted alert creation for patient {patient_id} "
                f"(severity: {alert.severity}) to {sent_count} connections"
            )
            
            return sent_count
            
        except Exception as e:
            logger.error(f"Error broadcasting alert creation: {e}")
            return 0
    
    async def broadcast_report_completion(
        self,
        report_id: UUID,
        patient_id: UUID,
        report_type: str,
        file_path: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> int:
        """
        Broadcast report completion notification to healthcare providers.
        
        Args:
            report_id: ID of the completed report
            patient_id: Patient the report is for
            report_type: Type of report (monthly_quiz, flow_summary, etc.)
            file_path: Path to generated report file
            success: Whether report generation was successful
            error_message: Error message if generation failed
            
        Returns:
            Number of connections that received the broadcast
        """
        try:
            # Create event data
            event_data = ReportEventData(
                report_id=report_id,
                patient_id=patient_id,
                report_type=report_type,
                status="completed" if success else "failed",
                file_path=file_path,
                error_message=error_message,
                metadata={
                    "generated_at": datetime.utcnow().isoformat(),
                    "success": success,
                    "downloadable": success and file_path is not None
                }
            )
            
            # Create WebSocket message
            event_type = (
                WebSocketEventType.REPORT_GENERATION_COMPLETED 
                if success 
                else WebSocketEventType.REPORT_GENERATION_FAILED
            )
            
            message = create_websocket_message(event_type, event_data)
            
            # Broadcast to patient room
            sent_count = await self.connection_manager.broadcast_to_patient_room(
                message.dict(), str(patient_id)
            )
            
            logger.info(
                f"Broadcasted report completion for patient {patient_id} "
                f"(type: {report_type}, success: {success}) to {sent_count} connections"
            )
            
            return sent_count
            
        except Exception as e:
            logger.error(f"Error broadcasting report completion: {e}")
            return 0
    
    async def broadcast_flow_message_sent(
        self,
        patient_id: UUID,
        message: Message,
        flow_day: int,
        flow_type: str
    ) -> int:
        """
        Broadcast flow message sent notification with graceful degradation.

        Args:
            patient_id: Patient who received the message
            message: Message that was sent
            flow_day: Day in the flow sequence
            flow_type: Type of flow (initial_15_days, etc.)

        Returns:
            Number of connections that received the broadcast
        """
        try:
            # Check prerequisites
            if not self.connection_manager:
                logger.debug("Connection manager unavailable, skipping flow message broadcast")
                return 0

            # Create event data
            event_data = MessageEventData(
                message_id=message.id,
                patient_id=patient_id,
                direction=message.direction,
                type=message.type,
                content=message.content[:100] + "..." if len(message.content) > 100 else message.content,
                status=message.status,
                whatsapp_id=message.whatsapp_id,
                metadata={
                    "flow_day": flow_day,
                    "flow_type": flow_type,
                    "sent_at": message.created_at.isoformat(),
                    "is_flow_message": True,
                    "automated": True
                }
            )

            # Create WebSocket message
            message_ws = create_websocket_message(
                WebSocketEventType.MESSAGE_SENT,
                event_data
            )

            # Broadcast to patient room with error handling
            try:
                sent_count = await self.connection_manager.broadcast_to_patient_room(
                    message_ws.dict(), str(patient_id)
                )

                logger.debug(
                    f"Broadcasted flow message sent for patient {patient_id} "
                    f"(day {flow_day}) to {sent_count} connections"
                )

                return sent_count
            except Exception as broadcast_error:
                logger.debug(f"WebSocket broadcast failed (non-critical): {broadcast_error}")
                return 0

        except Exception as e:
            # Don't log full error for non-critical broadcast failures
            logger.debug(f"Error broadcasting flow message sent: {e}")
            return 0
    
    async def broadcast_flow_progression(
        self,
        patient_id: UUID,
        from_day: int,
        to_day: int,
        flow_type: str,
        milestone_reached: Optional[str] = None
    ) -> int:
        """
        Broadcast flow progression milestone to healthcare providers.
        
        Args:
            patient_id: Patient whose flow progressed
            from_day: Previous day in flow
            to_day: New day in flow
            flow_type: Type of flow
            milestone_reached: Special milestone if any (e.g., "flow_transition")
            
        Returns:
            Number of connections that received the broadcast
        """
        try:
            # Create event data
            event_data = PatientEventData(
                patient_id=patient_id,
                changes={
                    "flow_progression": {
                        "from_day": from_day,
                        "to_day": to_day,
                        "milestone": milestone_reached
                    }
                },
                metadata={
                    "flow_type": flow_type,
                    "progression_date": datetime.utcnow().isoformat(),
                    "milestone_reached": milestone_reached,
                    "days_progressed": to_day - from_day
                }
            )
            
            # Create WebSocket message
            message = create_websocket_message(
                WebSocketEventType.PATIENT_FLOW_CHANGED,
                event_data
            )
            
            # Broadcast to patient room
            sent_count = await self.connection_manager.broadcast_to_patient_room(
                message.dict(), str(patient_id)
            )
            
            logger.info(
                f"Broadcasted flow progression for patient {patient_id} "
                f"from day {from_day} to {to_day} to {sent_count} connections"
            )
            
            return sent_count
            
        except Exception as e:
            logger.error(f"Error broadcasting flow progression: {e}")
            return 0
    
    async def broadcast_system_notification(
        self,
        message: str,
        level: str = "info",
        affected_patients: Optional[List[UUID]] = None
    ) -> int:
        """
        Broadcast system-wide notification to healthcare providers.
        
        Args:
            message: Notification message
            level: Severity level (info, warning, error)
            affected_patients: List of affected patient IDs if applicable
            
        Returns:
            Number of connections that received the broadcast
        """
        try:
            from app.schemas.websocket import SystemEventData
            
            # Create event data
            event_data = SystemEventData(
                message=message,
                level=level,
                metadata={
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "flow_system",
                    "affected_patients": [str(pid) for pid in affected_patients] if affected_patients else None
                }
            )
            
            # Create WebSocket message
            ws_message = create_websocket_message(
                WebSocketEventType.SYSTEM_NOTIFICATION,
                event_data
            )
            
            # Broadcast to all authenticated connections
            sent_count = await self.connection_manager.broadcast_to_all_authenticated(
                ws_message.dict()
            )
            
            logger.info(
                f"Broadcasted system notification (level: {level}) "
                f"to {sent_count} connections"
            )
            
            return sent_count
            
        except Exception as e:
            logger.error(f"Error broadcasting system notification: {e}")
            return 0


# Global flow event broadcaster instance
flow_event_broadcaster = FlowEventBroadcaster()