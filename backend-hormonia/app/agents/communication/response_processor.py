"""
Response Processor Agent - Intelligent Message Processing.

This agent wraps the ResponseProcessor service to provide agentic capabilities
for handling inbound patient messages, including:
- Message analysis and routing
- Intent recognition
- Flow state management
- Interactive response handling
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, MessagePriority
from app.services.response_processor import (
    ResponseProcessor, 
    ResponseProcessorConfig,
    InboundMessage,
    InteractiveResponse,
    ResponseType,
    MessageType,
    # Assuming ResponseAnalysis might be in services, if not I will define it below as a Pydantic model or similar
)
from app.repositories.patient import PatientRepository

# Re-export for agent package
class ResponseAnalysis:
    """
    Container for analysis results.
    """
    def __init__(self, sentiment: float = 0.0, intent: str = "unknown", entities: dict = None):
        self.sentiment = sentiment
        self.intent = intent
        self.entities = entities or {}

class ResponseProcessorAgent(BaseAgent):
    """
    Agent responsible for processing inbound messages and coordinating responses.
    
    Key responsibilities:
    - Analyze inbound messages (text, media, interactive)
    - Route messages to appropriate flows
    - Extract structured data from responses
    - Coordinate with other agents (e.g., QuizConductor)
    """
    
    def __init__(self, db_session: Session, **kwargs):
        """Initialize ResponseProcessorAgent."""
        super().__init__(
            agent_id=f"response_processor_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            agent_type="processing",
            specialization="message_processing",
            db_session=db_session,
            **kwargs
        )
        
        # Initialize ResponseProcessor service
        self.processor = ResponseProcessor(
            db=db_session,
            config=ResponseProcessorConfig(
                enable_ai_processing=True,
                enable_sentiment_analysis=True
            )
        )
        
        self.patient_repo = PatientRepository(db_session)
        
        # Agent capabilities
        self.capabilities = [
            "process_inbound_message",
            "handle_interactive_response",
            "analyze_sentiment",
            "route_message"
        ]

    async def _initialize(self):
        """Initialize agent resources."""
        self.logger.info("ResponseProcessorAgent initialized successfully")

    async def _cleanup(self):
        """Cleanup agent resources."""
        pass

    async def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return self.capabilities

    async def validate_task(self, task_data: Dict[str, Any]) -> bool:
        """Validate if agent can handle the task."""
        task_type = task_data.get("type", "")
        payload = task_data.get("payload", {})
        
        compatible_tasks = [
            "process_inbound_message",
            "handle_interactive_response"
        ]
        
        if task_type not in compatible_tasks:
            return False
            
        if task_type == "process_inbound_message":
            return all(key in payload for key in ["patient_phone", "content", "whatsapp_id"])
            
        if task_type == "handle_interactive_response":
            return all(key in payload for key in ["patient_id", "response_value", "response_type"])
            
        return True

    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process assigned task."""
        task_type = task_data.get("type")
        payload = task_data.get("payload", {})
        
        self.logger.info(f"Processing task: {task_type}")
        
        try:
            if task_type == "process_inbound_message":
                return await self._process_inbound_message(payload)
            elif task_type == "handle_interactive_response":
                return await self._handle_interactive_response(payload)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}
                
        except Exception as e:
            self.logger.error(f"Task processing failed: {e}")
            return {"success": False, "error": str(e)}

    async def _process_inbound_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process inbound message task."""
        # Convert payload to InboundMessage
        message_type_str = payload.get("message_type", "text").upper()
        try:
            message_type = MessageType[message_type_str]
        except KeyError:
            message_type = MessageType.TEXT
            
        inbound_message = InboundMessage(
            patient_phone=payload["patient_phone"],
            content=payload["content"],
            whatsapp_id=payload["whatsapp_id"],
            message_type=message_type,
            metadata=payload.get("metadata", {})
        )
        
        # Process message using service
        result = await self.processor.process_inbound_message(inbound_message)
        
        # If escalation required, notify appropriate agent
        if result.escalation_required:
            await self.send_message(
                "alert_analyzer_agent",
                "analyze_escalation",
                {
                    "patient_id": str(result.patient_id),
                    "reason": "escalation_required_by_processor",
                    "structured_response": result.structured_response.extracted_data
                },
                MessagePriority.HIGH
            )
            
        return {
            "success": True,
            "patient_id": str(result.patient_id),
            "processed_at": result.processed_at.isoformat(),
            "escalation_required": result.escalation_required,
            "flow_actions_count": len(result.flow_actions)
        }

    async def _handle_interactive_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle interactive response task."""
        # Convert payload to InteractiveResponse
        response_type_str = payload.get("response_type", "text").upper()
        try:
            response_type = ResponseType[response_type_str]
        except KeyError:
            response_type = ResponseType.TEXT
            
        interactive_response = InteractiveResponse(
            patient_id=UUID(payload["patient_id"]),
            response_value=payload["response_value"],
            response_type=response_type,
            original_message_id=UUID(payload["original_message_id"]) if payload.get("original_message_id") else None,
            metadata=payload.get("metadata", {})
        )
        
        # Process response using service
        result = await self.processor.handle_interactive_response(interactive_response)
        
        return {
            "success": True,
            "patient_id": str(result.patient_id),
            "processed_at": result.processed_at.isoformat(),
            "escalation_required": result.escalation_required
        }
