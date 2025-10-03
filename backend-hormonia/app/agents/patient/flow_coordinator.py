"""
Flow Coordinator Agent - Manages patient treatment flows with swarm intelligence.

This agent coordinates with other agents to make intelligent decisions about
patient flow progression, message timing, and treatment adaptation.
"""

import asyncio
import logging
from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, MessagePriority
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.services.enhanced_flow_engine import get_enhanced_flow_engine, FlowType
from app.services.message_sender import MessageSender
from app.services.template_loader import EnhancedTemplateLoader, FlowTemplateData, MessageTemplate
# Lazy import for memory module to prevent startup failures
# from app.memory.knowledge_graph import KnowledgeGraph
from app.integrations.gemini_client import get_gemini_client
from app.utils.template_variables import TemplateVariableProcessor


def _get_knowledge_graph():
    """Lazy import for KnowledgeGraph to prevent startup failures."""
    try:
        from app.memory.knowledge_graph import KnowledgeGraph
        return KnowledgeGraph
    except ImportError as e:
        logging.warning(f"KnowledgeGraph import failed: {e}")
        return None


class FlowDecision(Enum):
    """Types of flow decisions."""
    CONTINUE_CURRENT = "continue_current"
    ADVANCE_PHASE = "advance_phase"
    ADJUST_TIMING = "adjust_timing"
    PERSONALIZE_CONTENT = "personalize_content"
    ESCALATE_INTERVENTION = "escalate_intervention"
    PAUSE_FLOW = "pause_flow"
    RESUME_FLOW = "resume_flow"


class FlowContext:
    """Context for flow decision making."""
    
    def __init__(self):
        self.patient_id: Optional[UUID] = None
        self.current_day: Optional[int] = None
        self.flow_state: Optional[PatientFlowState] = None
        self.patient_data: Optional[Patient] = None
        self.recent_interactions: List[Dict] = []
        self.mood_indicators: Dict[str, Any] = {}
        self.adherence_metrics: Dict[str, float] = {}
        self.risk_factors: List[str] = []
        self.knowledge_context: Dict[str, Any] = {}


class FlowCoordinatorAgent(BaseAgent):
    """
    Agent responsible for coordinating patient treatment flows.
    
    Key responsibilities:
    - Analyze patient progress through treatment phases
    - Make decisions on flow progression and timing
    - Coordinate with other agents for consensus on critical decisions
    - Adapt flows based on patient responses and patterns
    - Manage transitions between different flow types
    """
    
    def __init__(self, db_session: Session, template_loader: Optional[EnhancedTemplateLoader] = None, **kwargs):
        """Initialize FlowCoordinatorAgent."""
        super().__init__(
            agent_id=f"flow_coordinator_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            agent_type="patient",
            specialization="flow_coordinator",
            db_session=db_session,
            **kwargs
        )
        
        # Repository dependencies
        self.patient_repo = PatientRepository(db_session)
        self.flow_repo = FlowStateRepository(db_session)
        
        # Service dependencies
        self.flow_engine = None  # Initialized during start
        self.message_sender = MessageSender(db_session)
        self.knowledge_graph = None  # Initialized during start
        self.gemini_client = None  # Initialized during start
        
        # Template support
        self.template_loader = template_loader or EnhancedTemplateLoader(
            template_path="app/templates/flows",
            db=db_session
        )
        self.flow_templates: Dict[str, FlowTemplateData] = {}
        
        # Agent capabilities
        self.capabilities = [
            "flow_analysis",
            "flow_coordination", 
            "timing_optimization",
            "phase_transition",
            "patient_adaptation",
            "consensus_participation"
        ]
        
        # Decision thresholds
        self.consensus_threshold = 0.7  # Require consensus for major decisions
        self.intervention_threshold = 0.8  # Threshold for intervention escalation
        self.adaptation_threshold = 0.6  # Threshold for flow adaptation
        
        # Flow timing parameters
        self.daily_flow_hours = [8, 14, 20]  # Default message times
        self.quiz_trigger_day = 15  # Day of month to trigger quiz
        self.transition_day_45 = 45  # Transition to monthly flows
        
    async def _initialize(self):
        """Initialize agent-specific resources."""
        try:
            # Initialize dependencies
            self.flow_engine = await get_enhanced_flow_engine()
            self.gemini_client = await get_gemini_client()
            
            # Initialize knowledge graph with lazy loading
            KnowledgeGraph = _get_knowledge_graph()
            if KnowledgeGraph:
                self.knowledge_graph = KnowledgeGraph(self.db_session)
                await self.knowledge_graph.initialize()
            else:
                self.knowledge_graph = None
                logging.warning("Knowledge graph not available - some features may be limited")
            
            # Load flow templates
            await self.load_flow_templates()
            
            self.logger.info("FlowCoordinatorAgent initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize FlowCoordinatorAgent: {e}")
            raise
    
    async def _cleanup(self):
        """Cleanup agent resources."""
        if self.knowledge_graph:
            await self.knowledge_graph.close()
    
    async def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return self.capabilities
    
    async def validate_task(self, task_data: Dict[str, Any]) -> bool:
        """Validate if agent can handle the task."""
        task_type = task_data.get("type", "")
        required_fields = task_data.get("payload", {})
        
        # Check task type compatibility
        compatible_tasks = [
            "process_daily_flow",
            "evaluate_flow_transition", 
            "optimize_message_timing",
            "adapt_flow_content",
            "coordinate_intervention"
        ]
        
        if task_type not in compatible_tasks:
            return False
        
        # Check required fields
        if task_type == "process_daily_flow":
            return "patient_id" in required_fields and "current_day" in required_fields
        elif task_type == "evaluate_flow_transition":
            return "patient_id" in required_fields and "flow_state_id" in required_fields
        elif task_type in ["optimize_message_timing", "adapt_flow_content"]:
            return "patient_id" in required_fields
        
        return True
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process assigned task."""
        task_type = task_data.get("type")
        payload = task_data.get("payload", {})
        
        self.logger.info(f"Processing task: {task_type}")
        
        try:
            if task_type == "process_daily_flow":
                return await self._process_daily_flow(payload)
            elif task_type == "evaluate_flow_transition":
                return await self._evaluate_flow_transition(payload)
            elif task_type == "optimize_message_timing":
                return await self._optimize_message_timing(payload)
            elif task_type == "adapt_flow_content":
                return await self._adapt_flow_content(payload)
            elif task_type == "coordinate_intervention":
                return await self._coordinate_intervention(payload)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}
                
        except Exception as e:
            self.logger.error(f"Task processing failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_daily_flow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process daily flow for a patient."""
        patient_id = UUID(payload["patient_id"])
        current_day = int(payload["current_day"])
        
        # Build flow context
        context = await self._build_flow_context(patient_id, current_day)
        
        if not context.patient_data or not context.flow_state:
            return {"success": False, "error": "Patient or flow state not found"}
        
        # Analyze current situation
        analysis = await self._analyze_flow_situation(context)
        
        # Make flow decision
        decision = await self._make_flow_decision(context, analysis)
        
        # Execute decision (if consensus reached for critical decisions)
        execution_result = await self._execute_flow_decision(decision, context)
        
        return {
            "success": True,
            "patient_id": str(patient_id),
            "current_day": current_day,
            "decision": decision.value,
            "analysis": analysis,
            "execution": execution_result
        }
    
    async def _build_flow_context(self, patient_id: UUID, current_day: int) -> FlowContext:
        """Build comprehensive context for flow decision making."""
        context = FlowContext()
        context.patient_id = patient_id
        context.current_day = current_day
        
        # Get patient data
        context.patient_data = self.patient_repo.get(patient_id)
        
        # Get flow state
        flow_states = self.flow_repo.get_by_patient_id(patient_id)
        context.flow_state = flow_states[0] if flow_states else None
        
        # Get knowledge graph context
        if self.knowledge_graph:
            context.knowledge_context = await self.knowledge_graph.get_patient_context(patient_id)
        
        # Analyze recent interactions
        context.recent_interactions = await self._get_recent_interactions(patient_id)
        
        # Calculate mood indicators
        context.mood_indicators = await self._analyze_mood_indicators(context)
        
        # Calculate adherence metrics
        context.adherence_metrics = await self._calculate_adherence_metrics(context)
        
        # Identify risk factors
        context.risk_factors = await self._identify_risk_factors(context)
        
        return context
    
    async def _analyze_flow_situation(self, context: FlowContext) -> Dict[str, Any]:
        """Analyze current flow situation and patient state."""
        analysis = {
            "phase": "unknown",
            "progress_score": 0.0,
            "engagement_score": 0.0,
            "risk_level": "low",
            "patterns": [],
            "recommendations": []
        }
        
        # Determine current phase
        if context.current_day <= 45:
            analysis["phase"] = "intensive_daily"
        else:
            analysis["phase"] = "monthly_maintenance"
        
        # Calculate progress score based on various factors
        progress_factors = []
        
        # Adherence score
        adherence = context.adherence_metrics.get("message_response_rate", 0.0)
        progress_factors.append(adherence * 0.3)
        
        # Mood improvement score
        mood_trend = context.mood_indicators.get("trend", 0.0)
        progress_factors.append(max(0, mood_trend) * 0.25)
        
        # Engagement score
        engagement = len(context.recent_interactions) / 7.0  # Expected daily interaction
        engagement = min(1.0, engagement)
        progress_factors.append(engagement * 0.2)
        analysis["engagement_score"] = engagement
        
        # Quiz completion rate
        quiz_rate = context.adherence_metrics.get("quiz_completion_rate", 1.0)
        progress_factors.append(quiz_rate * 0.25)
        
        analysis["progress_score"] = sum(progress_factors)
        
        # Assess risk level
        risk_score = len(context.risk_factors) / 5.0  # Max 5 risk factors
        
        if risk_score >= 0.6:
            analysis["risk_level"] = "high"
        elif risk_score >= 0.3:
            analysis["risk_level"] = "medium"
        else:
            analysis["risk_level"] = "low"
        
        # Extract patterns from knowledge graph
        if context.knowledge_context:
            analysis["patterns"] = context.knowledge_context.get("patterns", [])
        
        # Generate recommendations
        analysis["recommendations"] = await self._generate_recommendations(context, analysis)
        
        return analysis
    
    async def _make_flow_decision(self, context: FlowContext, analysis: Dict[str, Any]) -> FlowDecision:
        """Make intelligent flow decision based on context and analysis."""
        progress_score = analysis["progress_score"]
        risk_level = analysis["risk_level"]
        engagement_score = analysis["engagement_score"]
        
        # Decision logic based on multiple factors
        
        # High risk situations require intervention
        if risk_level == "high":
            if await self._requires_consensus_decision("escalate_intervention", context):
                consensus_result = await self._seek_agent_consensus(
                    "intervention_decision",
                    {
                        "patient_id": str(context.patient_id),
                        "risk_factors": context.risk_factors,
                        "analysis": analysis
                    }
                )
                
                if consensus_result["consensus_reached"]:
                    return FlowDecision.ESCALATE_INTERVENTION
            
            return FlowDecision.ESCALATE_INTERVENTION
        
        # Low engagement requires content personalization
        if engagement_score < 0.4:
            return FlowDecision.PERSONALIZE_CONTENT
        
        # Phase transition logic
        if context.current_day == self.transition_day_45:
            if await self._requires_consensus_decision("advance_phase", context):
                consensus_result = await self._seek_agent_consensus(
                    "phase_transition",
                    {
                        "patient_id": str(context.patient_id),
                        "from_phase": "daily",
                        "to_phase": "monthly",
                        "progress_score": progress_score
                    }
                )
                
                if consensus_result["consensus_reached"]:
                    return FlowDecision.ADVANCE_PHASE
            else:
                return FlowDecision.ADVANCE_PHASE
        
        # Timing optimization for better engagement
        if progress_score > 0.7 and engagement_score < 0.6:
            return FlowDecision.ADJUST_TIMING
        
        # Content personalization for moderate progress
        if 0.4 <= progress_score < 0.7:
            return FlowDecision.PERSONALIZE_CONTENT
        
        # Continue current flow if everything is going well
        return FlowDecision.CONTINUE_CURRENT
    
    async def _execute_flow_decision(
        self, 
        decision: FlowDecision, 
        context: FlowContext
    ) -> Dict[str, Any]:
        """Execute the flow decision."""
        execution_result = {"decision": decision.value, "actions_taken": []}
        
        try:
            if decision == FlowDecision.CONTINUE_CURRENT:
                # Process normal daily flow
                result = await self._process_normal_flow(context)
                execution_result["actions_taken"].append("processed_daily_messages")
                execution_result["messages_sent"] = result.get("messages_sent", 0)
            
            elif decision == FlowDecision.ADVANCE_PHASE:
                # Transition to next phase
                await self._transition_flow_phase(context)
                execution_result["actions_taken"].append("advanced_to_monthly_phase")
            
            elif decision == FlowDecision.ADJUST_TIMING:
                # Optimize message timing
                new_timing = await self._optimize_timing(context)
                execution_result["actions_taken"].append("optimized_timing")
                execution_result["new_timing"] = new_timing
            
            elif decision == FlowDecision.PERSONALIZE_CONTENT:
                # Personalize content and messages
                await self._personalize_content(context)
                execution_result["actions_taken"].append("personalized_content")
            
            elif decision == FlowDecision.ESCALATE_INTERVENTION:
                # Escalate for medical intervention
                await self._escalate_intervention(context)
                execution_result["actions_taken"].append("escalated_intervention")
            
            elif decision == FlowDecision.PAUSE_FLOW:
                # Pause flow temporarily
                await self._pause_flow(context)
                execution_result["actions_taken"].append("paused_flow")
            
            elif decision == FlowDecision.RESUME_FLOW:
                # Resume paused flow
                await self._resume_flow(context)
                execution_result["actions_taken"].append("resumed_flow")
            
            execution_result["success"] = True
            
        except Exception as e:
            self.logger.error(f"Failed to execute decision {decision.value}: {e}")
            execution_result["success"] = False
            execution_result["error"] = str(e)
        
        return execution_result
    
    async def _process_normal_flow(self, context: FlowContext) -> Dict[str, Any]:
        """Process normal daily flow messages."""
        messages_sent = 0
        
        try:
            # Determine appropriate message for current day
            message_content = await self._generate_daily_message(context)
            
            if message_content:
                # Create and send message
                message = Message(
                    patient_id=context.patient_id,
                    direction=MessageDirection.OUTBOUND,
                    type=MessageType.TEXT,
                    content=message_content["content"],
                    message_metadata={
                        "flow_day": context.current_day,
                        "generated_by": self.agent_id,
                        "personalization_level": message_content.get("personalization_level", "standard"),
                        "flow_decision": "continue_current"
                    },
                    status=MessageStatus.PENDING,
                    scheduled_for=datetime.utcnow()
                )
                
                # Save and send
                self.db_session.add(message)
                self.db_session.commit()
                
                success = await self.message_sender.send_message(message)
                if success:
                    messages_sent = 1
                    
                    # Update flow state
                    if context.flow_state:
                        if not context.flow_state.state_data:
                            context.flow_state.state_data = {}
                        
                        context.flow_state.state_data.update({
                            "last_message_sent": datetime.utcnow().isoformat(),
                            "current_day": context.current_day,
                            "decision_agent": self.agent_id
                        })
                        
                        self.db_session.commit()
        
        except Exception as e:
            self.logger.error(f"Error processing normal flow: {e}")
        
        return {"messages_sent": messages_sent}
    
    async def _generate_daily_message(self, context: FlowContext) -> Optional[Dict[str, Any]]:
        """Generate appropriate daily message using templates and AI optimization."""
        if not context.patient_data:
            return None
        
        try:
            # Determine appropriate flow template based on current day
            flow_type = self._determine_flow_type(context.current_day)
            
            # Try to get message from templates first
            template_message = await self._get_template_message(flow_type, context.current_day)
            
            if template_message:
                # Use AI to generate personalized content based on template
                personalized_content = await self._personalize_template_message(
                    template_message, context
                )
                return personalized_content
            
            # Fallback to legacy generation if template not found
            return await self._generate_legacy_message(context)
            
        except Exception as e:
            self.logger.error(f"Error generating daily message: {e}")
            # Fallback to legacy generation
            return await self._generate_legacy_message(context)
    
    def _determine_flow_type(self, current_day: int) -> str:
        """Determine appropriate flow type based on current day."""
        if current_day <= 15:
            return "initial_15_days"
        elif current_day <= 45:
            return "days_16_45"
        else:
            return "monthly_recurring"
    
    async def _get_template_message(self, flow_type: str, day: int) -> Optional[MessageTemplate]:
        """Get message template for specific flow type and day."""
        try:
            # Check if template is already loaded
            if flow_type not in self.flow_templates:
                await self._load_specific_template(flow_type)
            
            flow_template = self.flow_templates.get(flow_type)
            if flow_template:
                return flow_template.messages.get(day)
            
        except Exception as e:
            self.logger.warning(f"Could not get template message for {flow_type}, day {day}: {e}")
        
        return None
    
    async def _load_specific_template(self, flow_type: str) -> None:
        """Load specific flow template."""
        try:
            template_data = self.template_loader.load_flow_template(flow_type)
            self.flow_templates[flow_type] = template_data
            self.logger.info(f"Loaded template for {flow_type}: {len(template_data.messages)} messages")
        except Exception as e:
            self.logger.error(f"Failed to load template {flow_type}: {e}")
    
    async def _personalize_template_message(
        self, template: MessageTemplate, context: FlowContext
    ) -> Dict[str, Any]:
        """Personalize template message using AI and context."""
        try:
            # Prepare personalization context
            personalization_context = {
                "patient_name": context.patient_data.name if context.patient_data else "Cliente",
                "current_day": context.current_day,
                "mood_trend": context.mood_indicators.get("trend", 0),
                "engagement_level": context.adherence_metrics.get("message_response_rate", 0.5),
                "risk_factors": context.risk_factors,
                "personalization_hints": template.personalization_hints,
                "core_elements": template.core_elements
            }
            
            # Generate personalized content using AI if available
            if template.ai_instructions and self.gemini_client:
                personalized_content = await self._generate_ai_content(
                    template, personalization_context
                )
            else:
                # Use base template with basic personalization
                personalized_content = self._apply_basic_personalization(
                    template, personalization_context
                )
            
            return {
                "content": personalized_content,
                "personalization_level": "high" if template.ai_instructions else "standard",
                "template_intent": template.intent,
                "generated_at": datetime.utcnow().isoformat(),
                "source": "template"
            }
            
        except Exception as e:
            self.logger.error(f"Error personalizing template message: {e}")
            # Fallback to base content
            return {
                "content": template.base_content.replace("{patient_name}", 
                    context.patient_data.name if context.patient_data else "Cliente"),
                "personalization_level": "basic",
                "template_intent": template.intent,
                "generated_at": datetime.utcnow().isoformat(),
                "source": "template_fallback"
            }
    
    async def _generate_ai_content(
        self, template: MessageTemplate, context: Dict[str, Any]
    ) -> str:
        """Generate AI-optimized content based on template and context."""
        try:
            # Prepare AI prompt
            ai_prompt = f"""
            {template.ai_instructions}
            
            Contexto do paciente:
            - Nome: {context['patient_name']}
            - Dia do tratamento: {context['current_day']}
            - Tendência de humor: {context['mood_trend']}
            - Nível de engajamento: {context['engagement_level']}
            - Fatores de risco: {', '.join(context['risk_factors'])}
            
            Dicas de personalização: {', '.join(context['personalization_hints'])}
            Elementos essenciais: {context['core_elements']}
            
            Conteúdo base: {template.base_content}
            
            Gere uma mensagem personalizada seguindo as instruções acima:
            """
            
            # Call AI service
            response = await self.gemini_client.generate_content(ai_prompt)
            
            if response and hasattr(response, 'text'):
                return response.text.strip()
            
            # Fallback if AI fails
            return self._apply_basic_personalization(template, context)
            
        except Exception as e:
            self.logger.error(f"AI content generation failed: {e}")
            return self._apply_basic_personalization(template, context)
    
    def _apply_basic_personalization(
        self, template: MessageTemplate, context: Dict[str, Any]
    ) -> str:
        """Apply basic personalization to template."""
        content = template.base_content
        
        # Use TemplateVariableProcessor for comprehensive variable substitution
        content = TemplateVariableProcessor.substitute_variables(content, context)
        
        # Validate that all variables were replaced
        unreplaced = TemplateVariableProcessor.validate_variables(content)
        if unreplaced:
            self.logger.warning(f"Unreplaced variables in message: {unreplaced}")
        
        # Add mood-based personalization
        mood_trend = context.get("mood_trend", 0)
        if mood_trend < -0.5:
            content += " Notei que você pode estar passando por um momento mais difícil. Estou aqui para te apoiar. 💜"
        elif mood_trend > 0.5:
            content += " Que bom perceber que você parece estar se sentindo melhor! 😊"
        
        # Add engagement-based elements
        engagement = context.get("engagement_level", 0.5)
        if engagement < 0.3:
            content += " Lembre-se: pode me procurar sempre que precisar, ok?"
        
        return content
    
    async def _generate_legacy_message(self, context: FlowContext) -> Dict[str, Any]:
        """Generate message using legacy approach (fallback)."""
        if not context.patient_data:
            return None
        
        try:
            # Base message template based on day
            if context.current_day <= 7:
                # Welcome phase
                base_template = f"Bom dia, {context.patient_data.name}! Como você está se sentindo hoje? Lembre-se de que estou aqui para acompanhar sua jornada. 💜"
            elif context.current_day <= 21:
                # Adaptation phase
                base_template = f"Olá {context.patient_data.name}! Espero que você esteja bem hoje. Como tem sido sua experiência com o tratamento?"
            elif context.current_day <= 45:
                # Stabilization phase
                base_template = f"Oi {context.patient_data.name}! Continuamos juntas nessa jornada. Como você se sente hoje?"
            else:
                # Maintenance phase
                base_template = f"Olá {context.patient_data.name}! Que bom te ouvir novamente. Como tem passado?"
            
            # Personalize based on mood indicators and patterns
            if context.mood_indicators.get("trend", 0) < -0.5:
                # Recent mood decline
                personalization = " Notei que você pode estar passando por um momento mais difícil. Gostaria de conversar sobre isso?"
                base_template += personalization
            elif context.mood_indicators.get("trend", 0) > 0.5:
                # Mood improvement
                personalization = " Fico feliz em perceber que você parece estar se sentindo melhor! 😊"
                base_template += personalization
            
            # Add contextual elements based on knowledge graph
            if context.knowledge_context.get("patterns"):
                recent_patterns = context.knowledge_context["patterns"]
                for pattern in recent_patterns[-2:]:  # Last 2 patterns
                    if pattern.get("pattern_type") == "recurring_symptom":
                        symptom_note = f" Se algum sintoma estiver incomodando, não hesite em me contar."
                        if symptom_note not in base_template:
                            base_template += symptom_note
                        break
            
            return {
                "content": base_template,
                "personalization_level": "high" if len(base_template) > 150 else "standard",
                "generated_at": datetime.utcnow().isoformat(),
                "source": "legacy"
            }
            
        except Exception as e:
            self.logger.error(f"Error generating legacy message: {e}")
            return None
    
    # Helper methods for various operations
    async def _get_recent_interactions(self, patient_id: UUID) -> List[Dict]:
        """Get recent patient interactions."""
        # This would query the message history
        # For now, return placeholder
        return []
    
    async def _analyze_mood_indicators(self, context: FlowContext) -> Dict[str, Any]:
        """Analyze mood indicators from patient context."""
        mood_data = {"trend": 0.0, "current_level": 3.0, "confidence": 0.5}
        
        # Extract mood data from knowledge graph
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                if "mood" in pattern.get("pattern_type", ""):
                    if "improvement" in pattern["pattern_type"]:
                        mood_data["trend"] = 0.7
                    elif "decline" in pattern["pattern_type"]:
                        mood_data["trend"] = -0.7
                    
                    mood_data["confidence"] = pattern.get("confidence", 0.5)
                    break
        
        return mood_data
    
    async def _calculate_adherence_metrics(self, context: FlowContext) -> Dict[str, float]:
        """Calculate patient adherence metrics."""
        # Placeholder - would analyze actual interaction data
        return {
            "message_response_rate": 0.8,
            "quiz_completion_rate": 0.9,
            "scheduled_engagement_rate": 0.7
        }
    
    async def _identify_risk_factors(self, context: FlowContext) -> List[str]:
        """Identify risk factors from patient context."""
        risk_factors = []
        
        # Check mood decline
        if context.mood_indicators.get("trend", 0) < -0.6:
            risk_factors.append("mood_decline")
        
        # Check low engagement
        if context.adherence_metrics.get("message_response_rate", 1.0) < 0.3:
            risk_factors.append("low_engagement")
        
        # Check recurring symptoms from patterns
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                if pattern.get("pattern_type") == "recurring_symptom":
                    risk_factors.append(f"recurring_{pattern.get('description', 'symptom')}")
        
        return risk_factors
    
    async def _generate_recommendations(self, context: FlowContext, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        if analysis["engagement_score"] < 0.5:
            recommendations.append("increase_personalization")
            recommendations.append("optimize_timing")
        
        if analysis["risk_level"] == "high":
            recommendations.append("escalate_to_medical_team")
            recommendations.append("increase_monitoring_frequency")
        
        if analysis["progress_score"] > 0.8:
            recommendations.append("consider_reducing_frequency")
            recommendations.append("focus_on_maintenance")
        
        return recommendations
    
    # Consensus and coordination methods
    async def _requires_consensus_decision(self, decision_type: str, context: FlowContext) -> bool:
        """Check if decision requires consensus from other agents."""
        critical_decisions = [
            "escalate_intervention",
            "advance_phase",
            "pause_flow"
        ]
        
        return decision_type in critical_decisions
    
    async def _seek_agent_consensus(self, decision_topic: str, decision_data: Dict[str, Any]) -> Dict[str, Any]:
        """Seek consensus from other agents on important decisions."""
        try:
            # Send consensus request to relevant agents
            consensus_agents = ["alert_analyzer", "quiz_conductor", "patient_monitor"]
            votes = {}
            
            # Send messages to agents
            for agent_type in consensus_agents:
                response_id = await self.send_message(
                    f"{agent_type}_agent",  # Assuming agent naming convention
                    "consensus_request",
                    {
                        "decision_topic": decision_topic,
                        "decision_data": decision_data,
                        "requesting_agent": self.agent_id
                    },
                    MessagePriority.HIGH,
                    requires_response=True
                )
                
                # For now, simulate consensus (would wait for actual responses)
                votes[agent_type] = {"vote": "approve", "confidence": 0.8}
            
            # Calculate consensus
            approvals = sum(1 for vote in votes.values() if vote["vote"] == "approve")
            consensus_reached = approvals / len(votes) >= self.consensus_threshold
            
            return {
                "consensus_reached": consensus_reached,
                "votes": votes,
                "approval_rate": approvals / len(votes)
            }
            
        except Exception as e:
            self.logger.error(f"Consensus seeking failed: {e}")
            return {"consensus_reached": False, "error": str(e)}
    
    # Execution methods for different decisions
    async def _transition_flow_phase(self, context: FlowContext):
        """Transition patient to different flow phase."""
        if context.flow_state:
            # Update flow state to monthly recurring
            context.flow_state.state_data = context.flow_state.state_data or {}
            context.flow_state.state_data.update({
                "phase_transition": {
                    "from": "daily_intensive",
                    "to": "monthly_recurring",
                    "transitioned_at": datetime.utcnow().isoformat(),
                    "transitioned_by": self.agent_id
                }
            })
            
            # Change flow type
            context.flow_state.flow_type = FlowType.MONTHLY_RECURRING.value
            
            self.db_session.commit()
    
    async def _optimize_timing(self, context: FlowContext) -> Dict[str, Any]:
        """Optimize message timing for better engagement."""
        # Analyze response patterns to find optimal times
        # For now, return adjusted timing
        optimized_timing = {
            "morning": 9,  # 9 AM instead of 8 AM
            "afternoon": 15,  # 3 PM instead of 2 PM
            "evening": 19  # 7 PM instead of 8 PM
        }
        
        # Update flow state with new timing
        if context.flow_state:
            context.flow_state.state_data = context.flow_state.state_data or {}
            context.flow_state.state_data.update({
                "optimized_timing": optimized_timing,
                "timing_optimized_by": self.agent_id,
                "timing_optimized_at": datetime.utcnow().isoformat()
            })
            
            self.db_session.commit()
        
        return optimized_timing
    
    async def _personalize_content(self, context: FlowContext):
        """Personalize content based on patient patterns."""
        if context.flow_state:
            personalization_settings = {
                "tone": "supportive" if any("mood" in rf for rf in context.risk_factors) else "encouraging",
                "frequency": "reduced" if context.adherence_metrics.get("message_response_rate", 1.0) < 0.5 else "normal",
                "content_focus": await self._determine_content_focus(context),
                "personalized_by": self.agent_id,
                "personalized_at": datetime.utcnow().isoformat()
            }
            
            context.flow_state.state_data = context.flow_state.state_data or {}
            context.flow_state.state_data.update({
                "personalization": personalization_settings
            })
            
            self.db_session.commit()
    
    async def _determine_content_focus(self, context: FlowContext) -> List[str]:
        """Determine content focus areas based on patient needs."""
        focus_areas = []
        
        # Base on risk factors
        for risk_factor in context.risk_factors:
            if "mood" in risk_factor:
                focus_areas.append("emotional_support")
            elif "symptom" in risk_factor:
                focus_areas.append("symptom_management")
            elif "engagement" in risk_factor:
                focus_areas.append("motivation_enhancement")
        
        # Default focus if no specific risks
        if not focus_areas:
            focus_areas = ["general_wellness", "treatment_adherence"]
        
        return focus_areas
    
    async def _escalate_intervention(self, context: FlowContext):
        """Escalate situation for medical intervention."""
        # Create alert for medical team
        alert_data = {
            "patient_id": str(context.patient_id),
            "risk_factors": context.risk_factors,
            "escalated_by": self.agent_id,
            "escalated_at": datetime.utcnow().isoformat(),
            "priority": "high",
            "recommended_actions": [
                "schedule_medical_consultation",
                "increase_monitoring_frequency",
                "review_treatment_plan"
            ]
        }
        
        # Send alert to alert analyzer agent
        await self.send_message(
            "alert_analyzer_agent",
            "escalation_alert",
            alert_data,
            MessagePriority.CRITICAL
        )
    
    async def _pause_flow(self, context: FlowContext):
        """Pause flow temporarily."""
        if context.flow_state:
            context.flow_state.state_data = context.flow_state.state_data or {}
            context.flow_state.state_data.update({
                "flow_paused": True,
                "paused_at": datetime.utcnow().isoformat(),
                "paused_by": self.agent_id,
                "pause_reason": "patient_request_or_medical_indication"
            })
            
            self.db_session.commit()
    
    async def _resume_flow(self, context: FlowContext):
        """Resume paused flow."""
        if context.flow_state:
            context.flow_state.state_data = context.flow_state.state_data or {}
            context.flow_state.state_data.update({
                "flow_paused": False,
                "resumed_at": datetime.utcnow().isoformat(),
                "resumed_by": self.agent_id
            })
            
            self.db_session.commit()
    
    async def load_flow_templates(self) -> None:
        """Load all available flow templates."""
        try:
            # Load main flow templates
            flow_types = ["initial_15_days", "days_16_45", "monthly_recurring"]
            
            for flow_type in flow_types:
                try:
                    template_data = self.template_loader.load_flow_template(flow_type)
                    self.flow_templates[flow_type] = template_data
                    self.logger.info(f"Loaded {flow_type} template: {len(template_data.messages)} messages")
                except Exception as e:
                    self.logger.warning(f"Could not load {flow_type} template: {e}")
            
            self.logger.info(f"Successfully loaded {len(self.flow_templates)} flow templates")
            
        except Exception as e:
            self.logger.error(f"Failed to load flow templates: {e}")
    
    def get_loaded_templates(self) -> Dict[str, str]:
        """Get information about loaded templates."""
        return {
            flow_type: f"{template.name} v{template.version} ({len(template.messages)} messages)"
            for flow_type, template in self.flow_templates.items()
        }
    
    async def reload_templates(self) -> bool:
        """Reload all templates from source."""
        try:
            self.flow_templates.clear()
            await self.load_flow_templates()
            return len(self.flow_templates) > 0
        except Exception as e:
            self.logger.error(f"Failed to reload templates: {e}")
            return False
    
    # Other task processing methods
    async def _evaluate_flow_transition(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if patient should transition flow phases."""
        patient_id = UUID(payload["patient_id"])
        flow_state_id = payload["flow_state_id"]
        
        # Get flow state
        flow_state = self.flow_repo.get_by_id(flow_state_id)
        if not flow_state:
            return {"success": False, "error": "Flow state not found"}
        
        # Build context for evaluation
        context = await self._build_flow_context(patient_id, flow_state.current_day or 0)
        
        # Analyze readiness for transition
        analysis = await self._analyze_flow_situation(context)
        
        # Determine if transition is recommended
        transition_ready = (
            analysis["progress_score"] >= 0.6 and
            analysis["risk_level"] != "high" and
            analysis["engagement_score"] >= 0.4
        )
        
        return {
            "success": True,
            "patient_id": str(patient_id),
            "transition_ready": transition_ready,
            "analysis": analysis,
            "recommendations": analysis["recommendations"]
        }
    
    async def _optimize_message_timing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize message timing for patient."""
        patient_id = UUID(payload["patient_id"])
        
        # Build context
        context = await self._build_flow_context(patient_id, 0)  # Day doesn't matter for timing optimization
        
        # Optimize timing
        optimized_timing = await self._optimize_timing(context)
        
        return {
            "success": True,
            "patient_id": str(patient_id),
            "optimized_timing": optimized_timing
        }
    
    async def _adapt_flow_content(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt flow content for patient."""
        patient_id = UUID(payload["patient_id"])
        
        # Build context
        context = await self._build_flow_context(patient_id, 0)
        
        # Personalize content
        await self._personalize_content(context)
        
        return {
            "success": True,
            "patient_id": str(patient_id),
            "content_adapted": True
        }
    
    async def _coordinate_intervention(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Coordinate intervention for patient."""
        patient_id = UUID(payload["patient_id"])
        intervention_type = payload.get("intervention_type", "standard")
        
        # Build context
        context = await self._build_flow_context(patient_id, 0)
        
        # Coordinate based on intervention type
        if intervention_type == "escalation":
            await self._escalate_intervention(context)
        elif intervention_type == "pause":
            await self._pause_flow(context)
        elif intervention_type == "resume":
            await self._resume_flow(context)
        
        return {
            "success": True,
            "patient_id": str(patient_id),
            "intervention_type": intervention_type,
            "coordinated": True
        }