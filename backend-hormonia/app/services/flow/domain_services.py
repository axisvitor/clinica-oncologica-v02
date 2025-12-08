"""Flow Domain Services - Clean Architecture Implementation"""
from abc import ABC, abstractmethod
from typing import Protocol, Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime

# =============================================================================
# DOMAIN INTERFACES (Protocol-based dependency inversion)
# =============================================================================

class FlowProcessor(Protocol):
    """Core flow processing domain service"""
    async def process_patient_flows(self, patient_ids: List[UUID]) -> Dict[str, Any]: ...
    async def advance_flow_state(self, patient_id: UUID) -> Dict[str, Any]: ...

class MessageScheduler(Protocol):
    """Message scheduling domain service"""
    async def schedule_flow_message(self, message_request: 'FlowMessageRequest') -> bool: ...
    async def calculate_optimal_send_time(self, patient_id: UUID) -> datetime: ...

class TemplateResolver(Protocol):
    """Template resolution domain service"""
    async def resolve_template(self, flow_type: str, day: int) -> Optional['MessageTemplate']: ...
    async def personalize_message(self, template: 'MessageTemplate', context: Dict) -> str: ...

class FlowAnalytics(Protocol):
    """Flow analytics domain service"""
    async def track_flow_event(self, event: 'FlowEvent') -> None: ...
    async def get_flow_metrics(self, filters: Dict) -> Dict[str, Any]: ...

# =============================================================================
# DOMAIN MODELS
# =============================================================================

class FlowMessageRequest:
    def __init__(self, patient_id: UUID, template: 'MessageTemplate', 
                 send_time: datetime, priority: str = 'normal'):
        self.patient_id = patient_id
        self.template = template
        self.send_time = send_time
        self.priority = priority

class FlowEvent:
    def __init__(self, patient_id: UUID, event_type: str, 
                 flow_type: str, day: int, metadata: Dict = None):
        self.patient_id = patient_id
        self.event_type = event_type
        self.flow_type = flow_type
        self.day = day
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()

# =============================================================================
# CORE FLOW ORCHESTRATOR (Reduced to coordination only)
# =============================================================================

class FlowOrchestrator:
    """Coordinates flow processing between domain services (Single Responsibility)"""
    
    def __init__(self, 
                 flow_processor: FlowProcessor,
                 message_scheduler: MessageScheduler, 
                 template_resolver: TemplateResolver,
                 analytics: FlowAnalytics):
        self.flow_processor = flow_processor
        self.message_scheduler = message_scheduler
        self.template_resolver = template_resolver
        self.analytics = analytics
    
    async def orchestrate_daily_flows(self, patient_ids: List[UUID]) -> Dict[str, Any]:
        """Main orchestration logic (simplified to ~50 lines)"""
        results = {'processed': 0, 'scheduled': 0, 'errors': 0}
        
        # Step 1: Process flows
        flow_results = await self.flow_processor.process_patient_flows(patient_ids)
        
        # Step 2: Schedule messages for successful flows
        for patient_id, flow_data in flow_results.items():
            if flow_data.get('success'):
                await self._schedule_patient_message(patient_id, flow_data)
                results['scheduled'] += 1
                
            # Step 3: Track analytics
            await self.analytics.track_flow_event(
                FlowEvent(patient_id, 'flow_processed', 
                         flow_data.get('flow_type'), flow_data.get('day'))
            )
        
        results['processed'] = len(flow_results)
        return results
    
    async def _schedule_patient_message(self, patient_id: UUID, flow_data: Dict) -> bool:
        """Single responsibility: coordinate message scheduling"""
        template = await self.template_resolver.resolve_template(
            flow_data['flow_type'], flow_data['day']
        )
        
        if not template:
            return False
            
        message_request = FlowMessageRequest(
            patient_id=patient_id,
            template=template,
            send_time=await self.message_scheduler.calculate_optimal_send_time(patient_id)
        )
        
        return await self.message_scheduler.schedule_flow_message(message_request)

# =============================================================================
# MIGRATION STRATEGY
# =============================================================================

# Migration steps:
# 1. Extract FlowProcessor from EnhancedFlowEngine (focus on core flow logic)
# 2. Extract MessageScheduler from FlowEngineIntegrationService  
# 3. Extract TemplateResolver from template_loader integration
# 4. Extract FlowAnalytics from analytics_service integration
# 5. Replace FlowEngineIntegrationService with FlowOrchestrator
# 6. Update all dependent services gradually
