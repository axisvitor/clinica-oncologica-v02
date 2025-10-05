"""
Quiz Conductor Agent - Manages intelligent quiz presentation and adaptation.

This agent orchestrates quiz sessions with real-time personalization,
swarm coordination for response analysis, and adaptive questioning.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, MessagePriority
from app.models.patient import Patient
from app.models.quiz import QuizTemplate, QuizSession, QuizResponse
from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.services.quiz import QuizTemplateService, QuizSessionService, QuizResponseService
from app.services.message_sender import MessageSender
from app.services.template_loader import EnhancedTemplateLoader
from app.repositories.patient import PatientRepository
from app.schemas.quiz import QuizSessionCreate, QuizResponseCreate, QuestionType
# from app.memory.knowledge_graph import KnowledgeGraph
from app.integrations.gemini_client import get_gemini_client


def _get_knowledge_graph():
    """Lazy import for KnowledgeGraph to prevent startup failures."""
    try:
        from app.memory.knowledge_graph import KnowledgeGraph
        return KnowledgeGraph
    except ImportError as e:
        logging.warning(f"KnowledgeGraph import failed: {e}")
        return None


class QuizAdaptationType(Enum):
    """Types of quiz adaptations."""
    REDUCE_COMPLEXITY = "reduce_complexity"
    INCREASE_SUPPORT = "increase_support"
    FOCUS_ON_MOOD = "focus_on_mood"
    SKIP_SENSITIVE = "skip_sensitive"
    ADD_CLARIFICATION = "add_clarification"
    ACCELERATE_COMPLETION = "accelerate_completion"


class QuizContext:
    """Context for quiz conduction and adaptation."""
    
    def __init__(self):
        self.patient_id: Optional[UUID] = None
        self.session: Optional[QuizSession] = None
        self.template: Optional[QuizTemplate] = None
        self.patient_data: Optional[Patient] = None
        self.current_question_index: int = 0
        self.responses_so_far: List[Dict] = []
        self.mood_indicators: Dict[str, Any] = {}
        self.stress_level: float = 0.0
        self.engagement_score: float = 1.0
        self.knowledge_context: Dict[str, Any] = {}
        self.adaptation_history: List[Dict] = []


class QuizConductorAgent(BaseAgent):
    """
    Agent responsible for conducting intelligent quiz sessions.
    
    Key responsibilities:
    - Manage quiz session flow and progression
    - Adapt questions in real-time based on responses
    - Coordinate with other agents for comprehensive analysis
    - Personalize quiz experience based on patient context
    - Handle complex response interpretation using AI
    - Manage quiz completion and follow-up actions
    """
    
    def __init__(self, db_session: Session, template_loader: Optional[EnhancedTemplateLoader] = None, **kwargs):
        """Initialize QuizConductorAgent."""
        super().__init__(
            agent_id=f"quiz_conductor_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            agent_type="communication",
            specialization="quiz_conductor",
            db_session=db_session,
            **kwargs
        )
        
        # Service dependencies
        self.quiz_template_service = QuizTemplateService(db_session)
        self.quiz_session_service = QuizSessionService(db_session)
        self.quiz_response_service = QuizResponseService(db_session)
        self.message_sender = MessageSender(db_session)
        self.patient_repo = PatientRepository(db_session)
        
        # Template support
        self.template_loader = template_loader or EnhancedTemplateLoader(
            db=db_session  # FIX: Remove template_path parameter - EnhancedTemplateLoader doesn't accept it
        )
        self.quiz_templates: Dict[str, Dict[str, Any]] = {}
        
        # AI and memory dependencies
        self.knowledge_graph = None  # Initialized during start
        self.gemini_client = None  # Initialized during start
        
        # Agent capabilities
        self.capabilities = [
            "quiz_conduction",
            "adaptive_questioning",
            "response_interpretation",
            "mood_detection",
            "engagement_analysis",
            "personalization",
            "consensus_analysis"
        ]
        
        # Quiz parameters
        self.max_questions_per_session = 10
        self.response_timeout_minutes = 30
        self.adaptation_threshold = 0.6
        self.stress_threshold = 0.7
        self.engagement_threshold = 0.4
        
        # Response interpretation settings
        self.ai_interpretation_confidence_threshold = 0.8
        self.require_human_review_threshold = 0.3
        
    async def _initialize(self):
        """Initialize agent-specific resources."""
        try:
            # Initialize AI client
            self.gemini_client = get_gemini_client()  # FIX: Remove await - get_gemini_client() is synchronous
            
            # Initialize knowledge graph
            self.knowledge_graph = KnowledgeGraph(self.db_session)
            await self.knowledge_graph.initialize()
            
            # Load quiz templates
            await self.load_quiz_templates()
            
            self.logger.info("QuizConductorAgent initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize QuizConductorAgent: {e}")
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
        payload = task_data.get("payload", {})
        
        # Check task type compatibility
        compatible_tasks = [
            "conduct_quiz_session",
            "process_quiz_response",
            "adapt_quiz_questions",
            "analyze_quiz_completion",
            "trigger_monthly_quiz"
        ]
        
        if task_type not in compatible_tasks:
            return False
        
        # Check required fields
        if task_type in ["conduct_quiz_session", "trigger_monthly_quiz"]:
            return "patient_id" in payload
        elif task_type == "process_quiz_response":
            return all(key in payload for key in ["patient_id", "response_text"])
        elif task_type == "adapt_quiz_questions":
            return all(key in payload for key in ["patient_id", "session_id"])
        
        return True
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process assigned task."""
        task_type = task_data.get("type")
        payload = task_data.get("payload", {})
        
        self.logger.info(f"Processing quiz task: {task_type}")
        
        try:
            if task_type == "conduct_quiz_session":
                return await self._conduct_quiz_session(payload)
            elif task_type == "process_quiz_response":
                return await self._process_quiz_response(payload)
            elif task_type == "adapt_quiz_questions":
                return await self._adapt_quiz_questions(payload)
            elif task_type == "analyze_quiz_completion":
                return await self._analyze_quiz_completion(payload)
            elif task_type == "trigger_monthly_quiz":
                return await self._trigger_monthly_quiz(payload)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}
                
        except Exception as e:
            self.logger.error(f"Quiz task processing failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _conduct_quiz_session(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Conduct complete quiz session with adaptive intelligence."""
        patient_id = UUID(payload["patient_id"])
        quiz_type = payload.get("quiz_type", "monthly_checkup")
        
        # Build quiz context
        context = await self._build_quiz_context(patient_id, quiz_type)
        
        if not context.patient_data:
            return {"success": False, "error": "Patient not found"}
        
        # Create or get active session
        if not context.session:
            session = await self._create_quiz_session(context, quiz_type)
            if not session:
                return {"success": False, "error": "Failed to create quiz session"}
            context.session = session
        
        # Conduct quiz with swarm intelligence
        conduction_result = await self._conduct_adaptive_quiz(context)
        
        return {
            "success": True,
            "patient_id": str(patient_id),
            "session_id": str(context.session.id),
            "quiz_type": quiz_type,
            "questions_asked": len(context.responses_so_far),
            "adaptations_made": len(context.adaptation_history),
            "completion_status": conduction_result
        }
    
    async def _build_quiz_context(self, patient_id: UUID, quiz_type: str) -> QuizContext:
        """Build comprehensive quiz context."""
        context = QuizContext()
        context.patient_id = patient_id
        
        # Get patient data
        context.patient_data = self.patient_repo.get(patient_id)
        
        # Get active quiz session
        active_session = self.quiz_session_service.get_active_session(patient_id)
        if active_session:
            context.session = active_session
            context.current_question_index = active_session.current_question_index
            
            # Get template
            context.template = self.quiz_template_service.get_template(active_session.quiz_template_id)
        
        # Get knowledge graph context
        if self.knowledge_graph:
            context.knowledge_context = await self.knowledge_graph.get_patient_context(patient_id)
        
        # Analyze patient state
        context.mood_indicators = await self._analyze_current_mood(context)
        context.stress_level = await self._assess_stress_level(context)
        context.engagement_score = await self._calculate_engagement_score(context)
        
        # Get previous responses
        if context.session:
            context.responses_so_far = await self._get_session_responses(context.session.id)
        
        return context
    
    async def _create_quiz_session(self, context: QuizContext, quiz_type: str) -> Optional[QuizSession]:
        """Create new quiz session."""
        try:
            # Get or create appropriate template
            template = await self._get_or_create_quiz_template(quiz_type, context)
            
            if not template:
                self.logger.error(f"Failed to get quiz template for type: {quiz_type}")
                return None
            
            # Create session
            session_data = QuizSessionCreate(
                patient_id=context.patient_id,
                quiz_template_id=template.id
            )
            
            session = await self.quiz_session_service.start_quiz_session(session_data)
            
            # Update session metadata with swarm context
            session_metadata = {
                "quiz_type": quiz_type,
                "conducted_by_agent": self.agent_id,
                "initial_mood": context.mood_indicators,
                "initial_stress": context.stress_level,
                "personalization_applied": True,
                "swarm_coordination": True
            }
            
            # Add context from knowledge graph
            if context.knowledge_context.get("patterns"):
                session_metadata["known_patterns"] = [
                    p.get("pattern_type") for p in context.knowledge_context["patterns"][-3:]
                ]
            
            # Store metadata (this would need to be added to the session model)
            
            context.template = template
            return session
            
        except Exception as e:
            self.logger.error(f"Failed to create quiz session: {e}")
            return None
    
    async def _conduct_adaptive_quiz(self, context: QuizContext) -> Dict[str, Any]:
        """Conduct quiz with real-time adaptation."""
        completion_status = {
            "completed": False,
            "total_questions": len(context.template.questions) if context.template else 0,
            "questions_asked": 0,
            "adaptations_made": 0,
            "early_completion": False,
            "intervention_triggered": False
        }
        
        try:
            # Start with welcome message
            await self._send_quiz_introduction(context)
            
            # Process questions with adaptation
            while (context.current_question_index < len(context.template.questions) and 
                   context.current_question_index < self.max_questions_per_session):
                
                # Check if adaptation is needed
                if await self._should_adapt_quiz(context):
                    adaptation = await self._determine_adaptation(context)
                    await self._apply_adaptation(context, adaptation)
                    context.adaptation_history.append({
                        "adaptation_type": adaptation.value,
                        "question_index": context.current_question_index,
                        "reason": await self._get_adaptation_reason(context, adaptation),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    completion_status["adaptations_made"] += 1
                
                # Send current question
                question_result = await self._send_quiz_question(context)
                
                if not question_result["success"]:
                    break
                
                completion_status["questions_asked"] += 1
                context.current_question_index += 1
                
                # Check for early completion triggers
                if await self._should_complete_early(context):
                    completion_status["early_completion"] = True
                    break
                
                # Check for intervention triggers
                if await self._should_trigger_intervention(context):
                    await self._trigger_intervention(context)
                    completion_status["intervention_triggered"] = True
                    break
            
            # Complete session
            if context.current_question_index >= len(context.template.questions):
                await self._complete_quiz_session(context)
                completion_status["completed"] = True
            
            return completion_status
            
        except Exception as e:
            self.logger.error(f"Quiz conduction failed: {e}")
            completion_status["error"] = str(e)
            return completion_status
    
    async def _send_quiz_introduction(self, context: QuizContext):
        """Send personalized quiz introduction."""
        try:
            patient_name = context.patient_data.name
            
            # Personalize introduction based on context
            if context.mood_indicators.get("trend", 0) < -0.5:
                intro_tone = "supportive"
                intro_text = f"Olá {patient_name}! 💜 Sei que às vezes os dias podem ser desafiadores. Preparei algumas perguntas bem rápidas para entender melhor como você está. Vamos juntas?"
            elif context.stress_level > self.stress_threshold:
                intro_tone = "gentle"
                intro_text = f"Oi {patient_name}! 🌸 Vamos fazer um check-up rápido e tranquilo? São apenas algumas perguntas para eu entender como você está se sentindo."
            else:
                intro_tone = "encouraging"
                intro_text = f"Olá {patient_name}! 😊 É hora do nosso check-up mensal! Preparei algumas perguntas importantes para acompanhar seu progresso. Vamos começar?"
            
            # Add context-aware elements
            if context.knowledge_context.get("patterns"):
                recent_patterns = context.knowledge_context["patterns"][-2:]
                for pattern in recent_patterns:
                    if "improvement" in pattern.get("pattern_type", ""):
                        intro_text += " Fico feliz em ver seu progresso! 💪"
                        break
            
            # Add question count
            question_count = min(len(context.template.questions), self.max_questions_per_session)
            intro_text += f"\n\n*São {question_count} perguntas rápidas.*"
            
            # Send message
            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=intro_text,
                message_metadata={
                    "quiz_session_id": str(context.session.id),
                    "message_type": "quiz_introduction",
                    "intro_tone": intro_tone,
                    "generated_by": self.agent_id,
                    "swarm_context": True
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.utcnow()
            )
            
            self.db_session.add(message)
            self.db_session.commit()
            self.db_session.refresh(message)
            
            await self.message_sender.send_message(message)
            
        except Exception as e:
            self.logger.error(f"Failed to send quiz introduction: {e}")
    
    async def _send_quiz_question(self, context: QuizContext) -> Dict[str, Any]:
        """Send current quiz question with personalization."""
        try:
            if context.current_question_index >= len(context.template.questions):
                return {"success": False, "error": "No more questions"}
            
            question = context.template.questions[context.current_question_index]
            
            # Personalize question presentation
            question_content = await self._personalize_question(context, question)
            
            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=question_content["content"],
                message_metadata={
                    "quiz_session_id": str(context.session.id),
                    "quiz_question_index": context.current_question_index,
                    "quiz_question_id": question['id'],
                    "message_type": "quiz_question",
                    "personalization_level": question_content["personalization_level"],
                    "generated_by": self.agent_id
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.utcnow()
            )
            
            self.db_session.add(message)
            self.db_session.commit()
            self.db_session.refresh(message)
            
            success = await self.message_sender.send_message(message)
            
            return {
                "success": success,
                "question_index": context.current_question_index,
                "question_id": question['id']
            }
            
        except Exception as e:
            self.logger.error(f"Failed to send quiz question: {e}")
            return {"success": False, "error": str(e)}
    
    async def _personalize_question(self, context: QuizContext, question: Dict) -> Dict[str, Any]:
        """Personalize question based on context."""
        base_text = question['text']
        personalization_level = "standard"
        
        try:
            # Add patient name for warmth
            if not any(name_word in base_text.lower() for name_word in ["você", "seu", "sua"]):
                base_text = f"{context.patient_data.name}, {base_text.lower()}"
                personalization_level = "high"
            
            # Question number for progress tracking
            total_questions = min(len(context.template.questions), self.max_questions_per_session)
            progress_text = f"*Pergunta {context.current_question_index + 1} de {total_questions}:*\n\n"
            
            content = progress_text + base_text
            
            # Add options if available
            if question.get('options'):
                content += "\n\n*Opções:*"
                for option in question['options']:
                    content += f"\n• {option['text']}"
            
            # Add supportive context for mood-related questions
            if "humor" in question['text'].lower() or "sentindo" in question['text'].lower():
                if context.stress_level > self.stress_threshold:
                    content += "\n\n_Não se preocupe, não há resposta certa ou errada. Queremos apenas te conhecer melhor._"
                    personalization_level = "supportive"
            
            return {
                "content": content,
                "personalization_level": personalization_level
            }
            
        except Exception as e:
            self.logger.error(f"Question personalization failed: {e}")
            return {"content": base_text, "personalization_level": "standard"}
    
    # Response processing methods
    async def _process_quiz_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process patient response with swarm analysis."""
        patient_id = UUID(payload["patient_id"])
        response_text = payload["response_text"]
        message_metadata = payload.get("message_metadata", {})
        
        # Get active session
        active_session = self.quiz_session_service.get_active_session(patient_id)
        if not active_session:
            return {"success": False, "error": "No active quiz session"}
        
        # Build context
        context = await self._build_quiz_context(patient_id, "current")
        
        # Process response with AI and swarm intelligence
        processing_result = await self._process_response_with_swarm(context, response_text)
        
        if not processing_result["valid"]:
            # Send clarification message
            await self._send_clarification_message(context, processing_result["error"])
            return {
                "success": False,
                "action": "clarification_requested",
                "error": processing_result["error"]
            }
        
        # Store response
        response_data = QuizResponseCreate(
            patient_id=patient_id,
            quiz_template_id=active_session.quiz_template_id,
            question_id=processing_result["question_id"],
            question_text=processing_result["question_text"],
            response_type=processing_result["response_type"],
            response_value=processing_result["processed_value"],
            response_metadata={
                "original_text": response_text,
                "ai_processed": processing_result.get("ai_processed", False),
                "confidence_score": processing_result.get("confidence", 1.0),
                "swarm_analysis": processing_result.get("swarm_analysis", {}),
                "processed_by_agent": self.agent_id
            },
            responded_at=datetime.utcnow()
        )
        
        response = await self.quiz_response_service.create_response(response_data)
        
        # Update knowledge graph
        if self.knowledge_graph and response:
            await self.knowledge_graph.add_quiz_response_node(response)
        
        # Determine next action
        if context.current_question_index >= len(context.template.questions) - 1:
            # Complete quiz
            await self._complete_quiz_session(context)
            return {
                "success": True,
                "action": "quiz_completed",
                "session_id": str(active_session.id)
            }
        else:
            # Advance to next question
            self.quiz_session_service.advance_session(active_session.id)
            
            # Send next question (with potential adaptation)
            next_context = await self._build_quiz_context(patient_id, "current")
            await self._send_quiz_question(next_context)
            
            return {
                "success": True,
                "action": "next_question",
                "question_index": context.current_question_index + 1
            }
    
    async def _process_response_with_swarm(self, context: QuizContext, response_text: str) -> Dict[str, Any]:
        """Process response with swarm intelligence and AI analysis."""
        if context.current_question_index >= len(context.template.questions):
            return {"valid": False, "error": "No active question"}
        
        current_question = context.template.questions[context.current_question_index]
        
        # Basic processing
        basic_result = await self._basic_response_processing(current_question, response_text)
        
        # If basic processing is uncertain, use AI enhancement
        if basic_result.get("confidence", 1.0) < self.ai_interpretation_confidence_threshold:
            ai_result = await self._ai_enhanced_processing(current_question, response_text, context)
            
            if ai_result and ai_result.get("confidence", 0) > basic_result.get("confidence", 0):
                basic_result.update(ai_result)
                basic_result["ai_processed"] = True
        
        # Request swarm analysis for complex responses
        if basic_result.get("confidence", 1.0) < self.require_human_review_threshold:
            swarm_analysis = await self._request_swarm_analysis(context, response_text, basic_result)
            basic_result["swarm_analysis"] = swarm_analysis
        
        # Add context information
        basic_result.update({
            "question_id": current_question['id'],
            "question_text": current_question['text'],
            "response_type": current_question['type']
        })
        
        return basic_result
    
    async def _basic_response_processing(self, question: Dict, response_text: str) -> Dict[str, Any]:
        """Basic response processing without AI."""
        question_type = question['type']
        response_text = response_text.strip()
        
        if question_type == QuestionType.OPEN_TEXT.value:
            return {
                "valid": True,
                "processed_value": response_text,
                "confidence": 1.0
            }
        
        elif question_type == QuestionType.SCALE.value:
            # Try to extract number
            import re
            numbers = re.findall(r'\d+', response_text)
            
            if numbers:
                scale_value = int(numbers[0])
                if 1 <= scale_value <= 5:
                    return {
                        "valid": True,
                        "processed_value": str(scale_value),
                        "confidence": 1.0
                    }
            
            return {
                "valid": False,
                "error": "Por favor, responda com um número de 1 a 5",
                "confidence": 0.0
            }
        
        elif question_type == QuestionType.MULTIPLE_CHOICE.value:
            options = question.get('options', [])
            
            # Direct text match
            for option in options:
                if (response_text.lower() in option['text'].lower() or 
                    option['text'].lower() in response_text.lower()):
                    return {
                        "valid": True,
                        "processed_value": option['value'],
                        "confidence": 0.9
                    }
            
            # Return uncertain result for AI processing
            return {
                "valid": False,
                "error": "Não consegui entender sua resposta",
                "confidence": 0.2,
                "options": options
            }
        
        elif question_type == QuestionType.YES_NO.value:
            response_lower = response_text.lower()
            
            yes_words = ['sim', 'yes', 's', 'claro', 'certamente', 'com certeza']
            no_words = ['não', 'nao', 'no', 'n', 'nunca', 'jamais']
            
            if any(word in response_lower for word in yes_words):
                return {"valid": True, "processed_value": "yes", "confidence": 0.9}
            elif any(word in response_lower for word in no_words):
                return {"valid": True, "processed_value": "no", "confidence": 0.9}
            
            return {
                "valid": False,
                "error": "Por favor, responda com 'sim' ou 'não'",
                "confidence": 0.0
            }
        
        return {
            "valid": False,
            "error": "Tipo de pergunta não suportado",
            "confidence": 0.0
        }
    
    async def _ai_enhanced_processing(self, question: Dict, response_text: str, context: QuizContext) -> Optional[Dict[str, Any]]:
        """AI-enhanced response processing using Gemini."""
        try:
            if not self.gemini_client:
                return None
            
            question_type = question['type']
            
            if question_type == QuestionType.SCALE.value:
                prompt = f"""
                Analise a resposta do paciente para uma pergunta de escala de 1 a 5:
                
                Pergunta: {question['text']}
                Resposta: "{response_text}"
                
                Contexto do paciente: {context.patient_data.name} está em tratamento de terapia hormonal.
                
                Escala:
                1 = Muito ruim/baixo/negativo
                2 = Ruim/baixo/negativo  
                3 = Neutro/regular/médio
                4 = Bom/alto/positivo
                5 = Muito bom/alto/positivo
                
                Retorne apenas o número (1-5) que melhor representa a resposta.
                Se não conseguir interpretar, retorne "INVALID".
                """
            
            elif question_type == QuestionType.MULTIPLE_CHOICE.value:
                options_text = "\n".join([f"- {opt['value']}: {opt['text']}" for opt in question.get('options', [])])
                
                prompt = f"""
                Analise a resposta do paciente e determine qual opção ela melhor representa:
                
                Pergunta: {question['text']}
                Resposta: "{response_text}"
                
                Opções disponíveis:
                {options_text}
                
                Retorne apenas o valor (value) da opção que melhor corresponde.
                Se não conseguir determinar, retorne "INVALID".
                """
            else:
                return None
            
            # Get AI response
            ai_response = await self.gemini_client.generate_content(prompt)
            
            if not ai_response or ai_response.strip() == "INVALID":
                return None
            
            # Validate AI response
            if question_type == QuestionType.SCALE.value:
                if ai_response.strip().isdigit():
                    value = int(ai_response.strip())
                    if 1 <= value <= 5:
                        return {
                            "valid": True,
                            "processed_value": str(value),
                            "confidence": 0.8,
                            "ai_interpreted": True
                        }
            
            elif question_type == QuestionType.MULTIPLE_CHOICE.value:
                options = question.get('options', [])
                option_values = [opt['value'] for opt in options]
                if ai_response.strip() in option_values:
                    return {
                        "valid": True,
                        "processed_value": ai_response.strip(),
                        "confidence": 0.8,
                        "ai_interpreted": True
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"AI response processing failed: {e}")
            return None
    
    async def _request_swarm_analysis(self, context: QuizContext, response_text: str, basic_result: Dict) -> Dict[str, Any]:
        """Request analysis from other agents in the swarm."""
        try:
            # Request analysis from relevant agents
            analysis_requests = {
                "mood_analysis": "alert_analyzer_agent",
                "medical_significance": "patient_monitor_agent",
                "flow_impact": "flow_coordinator_agent"
            }
            
            swarm_analysis = {}
            
            for analysis_type, agent_id in analysis_requests.items():
                try:
                    # Send analysis request
                    await self.send_message(
                        agent_id,
                        "analyze_quiz_response",
                        {
                            "patient_id": str(context.patient_id),
                            "response_text": response_text,
                            "question_context": context.template.questions[context.current_question_index],
                            "basic_processing": basic_result,
                            "analysis_type": analysis_type
                        },
                        MessagePriority.HIGH
                    )
                    
                    # For now, simulate analysis results
                    # In real implementation, would wait for responses
                    swarm_analysis[analysis_type] = {
                        "agent": agent_id,
                        "confidence": 0.7,
                        "insights": ["response_processed_by_swarm"]
                    }
                    
                except Exception as e:
                    self.logger.error(f"Failed to request {analysis_type} from {agent_id}: {e}")
            
            return swarm_analysis
            
        except Exception as e:
            self.logger.error(f"Swarm analysis request failed: {e}")
            return {}
    
    # Adaptation methods
    async def _should_adapt_quiz(self, context: QuizContext) -> bool:
        """Determine if quiz adaptation is needed."""
        # Check stress level
        if context.stress_level > self.stress_threshold:
            return True
        
        # Check engagement
        if context.engagement_score < self.engagement_threshold:
            return True
        
        # Check mood indicators
        if context.mood_indicators.get("distress", 0) > 0.7:
            return True
        
        # Check response patterns
        if len(context.responses_so_far) >= 3:
            # Check for pattern of short or unclear responses
            unclear_responses = sum(1 for r in context.responses_so_far[-3:] 
                                  if r.get("confidence", 1.0) < 0.6)
            if unclear_responses >= 2:
                return True
        
        return False
    
    async def _determine_adaptation(self, context: QuizContext) -> QuizAdaptationType:
        """Determine what type of adaptation is needed."""
        # High stress - reduce complexity
        if context.stress_level > self.stress_threshold:
            return QuizAdaptationType.REDUCE_COMPLEXITY
        
        # Low engagement - increase support
        if context.engagement_score < self.engagement_threshold:
            return QuizAdaptationType.INCREASE_SUPPORT
        
        # Mood distress - focus on mood
        if context.mood_indicators.get("distress", 0) > 0.7:
            return QuizAdaptationType.FOCUS_ON_MOOD
        
        # Pattern of unclear responses - add clarification
        if len(context.responses_so_far) >= 2:
            recent_unclear = [r for r in context.responses_so_far[-2:] 
                            if r.get("confidence", 1.0) < 0.6]
            if len(recent_unclear) >= 1:
                return QuizAdaptationType.ADD_CLARIFICATION
        
        return QuizAdaptationType.INCREASE_SUPPORT
    
    async def _apply_adaptation(self, context: QuizContext, adaptation: QuizAdaptationType):
        """Apply specific adaptation to quiz."""
        adaptation_message = None
        
        if adaptation == QuizAdaptationType.REDUCE_COMPLEXITY:
            adaptation_message = "Vamos simplificar um pouco. Responda apenas com o que vier à mente primeiro. 💜"
            
        elif adaptation == QuizAdaptationType.INCREASE_SUPPORT:
            adaptation_message = f"{context.patient_data.name}, você está indo muito bem! Vamos continuar juntas. 🌸"
            
        elif adaptation == QuizAdaptationType.FOCUS_ON_MOOD:
            adaptation_message = "Percebi que pode estar sendo um momento difícil. Não se preocupe, não há resposta errada. 🤗"
            
        elif adaptation == QuizAdaptationType.ADD_CLARIFICATION:
            adaptation_message = "Para me ajudar a entender melhor, que tal responder de forma bem simples? Pode ser só uma palavra mesmo. 😊"
        
        # Send adaptation message if needed
        if adaptation_message:
            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=adaptation_message,
                message_metadata={
                    "quiz_session_id": str(context.session.id),
                    "message_type": "quiz_adaptation",
                    "adaptation_type": adaptation.value,
                    "generated_by": self.agent_id
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.utcnow()
            )
            
            self.db_session.add(message)
            self.db_session.commit()
            
            await self.message_sender.send_message(message)
    
    # Completion and analysis methods
    async def _complete_quiz_session(self, context: QuizContext):
        """Complete quiz session with comprehensive analysis."""
        try:
            # Mark session as completed
            await self.quiz_session_service.complete_session(context.session.id)
            
            # Trigger comprehensive analysis
            await self._trigger_comprehensive_analysis(context)
            
            # Send completion message
            await self._send_completion_message(context)
            
            # Update knowledge graph with session insights
            if self.knowledge_graph:
                await self.knowledge_graph.add_quiz_session_node(context.session)
                
                # Discover new patterns
                patterns = await self.knowledge_graph.discover_patterns(context.patient_id)
                if patterns:
                    self.logger.info(f"Discovered {len(patterns)} new patterns for patient {context.patient_id}")
            
        except Exception as e:
            self.logger.error(f"Quiz completion failed: {e}")
    
    async def _trigger_comprehensive_analysis(self, context: QuizContext):
        """Trigger comprehensive analysis by multiple agents."""
        analysis_data = {
            "patient_id": str(context.patient_id),
            "session_id": str(context.session.id),
            "responses_count": len(context.responses_so_far),
            "adaptations_made": len(context.adaptation_history),
            "final_mood": context.mood_indicators,
            "engagement_level": context.engagement_score
        }
        
        # Request analysis from different agents
        analysis_agents = [
            "alert_analyzer_agent",
            "patient_monitor_agent", 
            "flow_coordinator_agent",
            "insight_generator_agent"
        ]
        
        for agent_id in analysis_agents:
            try:
                await self.send_message(
                    agent_id,
                    "analyze_completed_quiz",
                    analysis_data,
                    MessagePriority.NORMAL
                )
            except Exception as e:
                self.logger.error(f"Failed to request analysis from {agent_id}: {e}")
    
    async def _send_completion_message(self, context: QuizContext):
        """Send personalized completion message."""
        try:
            patient_name = context.patient_data.name
            
            # Personalize based on session performance
            if context.engagement_score > 0.8:
                completion_message = f"Parabéns {patient_name}! 🎉 Você completou o check-up com excelência! Suas respostas foram registradas e nossa equipe analisará tudo com cuidado."
            elif len(context.adaptation_history) > 0:
                completion_message = f"Obrigada {patient_name}! 💜 Sei que algumas perguntas podem ser desafiadoras, mas você foi muito bem! Suas respostas são muito valiosas para seu cuidado."
            else:
                completion_message = f"Muito obrigada {patient_name}! 😊 Você completou seu check-up mensal. Suas respostas ajudam nossa equipe a cuidar melhor de você."
            
            completion_message += "\n\nSe precisar de algo, estarei sempre aqui! 🌸"
            
            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=completion_message,
                message_metadata={
                    "quiz_session_id": str(context.session.id),
                    "message_type": "quiz_completion",
                    "generated_by": self.agent_id,
                    "session_summary": {
                        "questions_completed": len(context.responses_so_far),
                        "adaptations_made": len(context.adaptation_history),
                        "engagement_score": context.engagement_score
                    }
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.utcnow()
            )
            
            self.db_session.add(message)
            self.db_session.commit()
            
            await self.message_sender.send_message(message)
            
        except Exception as e:
            self.logger.error(f"Failed to send completion message: {e}")
    
    # Helper methods
    async def _analyze_current_mood(self, context: QuizContext) -> Dict[str, Any]:
        """Analyze current mood indicators."""
        mood_data = {"trend": 0.0, "distress": 0.0, "confidence": 0.5}
        
        # Use knowledge graph patterns
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                pattern_type = pattern.get("pattern_type", "")
                if "mood" in pattern_type:
                    if "improvement" in pattern_type:
                        mood_data["trend"] = 0.7
                    elif "decline" in pattern_type:
                        mood_data["trend"] = -0.7
                        mood_data["distress"] = 0.6
                    
                    mood_data["confidence"] = pattern.get("confidence", 0.5)
                    break
        
        return mood_data
    
    async def _assess_stress_level(self, context: QuizContext) -> float:
        """Assess patient stress level from context."""
        stress_indicators = 0.0
        
        # Check for stress patterns in knowledge graph
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                if any(keyword in pattern.get("description", "") for keyword in 
                      ["anxiety", "stress", "worried", "ansiedade", "preocup"]):
                    stress_indicators += 0.3
        
        # Check recent interaction frequency (low frequency might indicate stress)
        # This would analyze actual interaction data
        
        return min(1.0, stress_indicators)
    
    async def _calculate_engagement_score(self, context: QuizContext) -> float:
        """Calculate patient engagement score."""
        engagement = 1.0
        
        # Reduce score based on knowledge patterns
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                if "low_engagement" in pattern.get("pattern_type", ""):
                    engagement -= 0.3
        
        return max(0.0, engagement)
    
    async def _get_session_responses(self, session_id: UUID) -> List[Dict]:
        """Get responses for current session."""
        # This would query actual responses from database
        # For now, return empty list
        return []
    
    async def _get_or_create_quiz_template(self, quiz_type: str, context: QuizContext) -> Optional[QuizTemplate]:
        """Get or create quiz template based on type."""
        try:
            # Try to get existing template
            template_name = f"{quiz_type}_template"
            
            try:
                template_response = self.quiz_template_service.get_template_by_name(template_name)
                return self.quiz_template_service.template_repository.get(template_response.id)
            except:
                pass
            
            # Create new template if needed - use existing logic from quiz_flow_integration.py
            # For now, return None to use default template creation
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get/create quiz template: {e}")
            return None
    
    async def _send_clarification_message(self, context: QuizContext, error_message: str):
        """Send clarification message for unclear response."""
        try:
            clarification = f"Desculpe {context.patient_data.name}, {error_message}\n\nVamos tentar novamente? 😊"
            
            message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=clarification,
                message_metadata={
                    "quiz_session_id": str(context.session.id),
                    "message_type": "quiz_clarification",
                    "generated_by": self.agent_id
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.utcnow()
            )
            
            self.db_session.add(message)
            self.db_session.commit()
            
            await self.message_sender.send_message(message)
            
        except Exception as e:
            self.logger.error(f"Failed to send clarification message: {e}")
    
    async def _should_complete_early(self, context: QuizContext) -> bool:
        """Check if quiz should be completed early."""
        # Complete early if high stress detected
        if context.stress_level > 0.9:
            return True
        
        # Complete early if enough critical information gathered
        critical_responses = sum(1 for r in context.responses_so_far 
                               if any(keyword in r.get("question_text", "").lower() 
                                     for keyword in ["humor", "energia", "sintoma"]))
        
        if critical_responses >= 3 and len(context.responses_so_far) >= 5:
            return True
        
        return False
    
    async def _should_trigger_intervention(self, context: QuizContext) -> bool:
        """Check if medical intervention should be triggered."""
        # Check for crisis indicators
        if context.mood_indicators.get("distress", 0) > 0.9:
            return True
        
        # Check for concerning response patterns
        concerning_responses = sum(1 for r in context.responses_so_far 
                                 if r.get("processed_value") == "1" and "humor" in r.get("question_text", ""))
        
        if concerning_responses >= 2:
            return True
        
        return False
    
    async def _trigger_intervention(self, context: QuizContext):
        """Trigger medical intervention."""
        # Send urgent message to alert analyzer
        await self.send_message(
            "alert_analyzer_agent",
            "urgent_intervention_needed",
            {
                "patient_id": str(context.patient_id),
                "quiz_session_id": str(context.session.id),
                "trigger_reason": "concerning_quiz_responses",
                "mood_indicators": context.mood_indicators,
                "stress_level": context.stress_level
            },
            MessagePriority.CRITICAL
        )
    
    async def _get_adaptation_reason(self, context: QuizContext, adaptation: QuizAdaptationType) -> str:
        """Get reason for adaptation."""
        if adaptation == QuizAdaptationType.REDUCE_COMPLEXITY:
            return f"High stress level detected: {context.stress_level:.2f}"
        elif adaptation == QuizAdaptationType.INCREASE_SUPPORT:
            return f"Low engagement score: {context.engagement_score:.2f}"
        elif adaptation == QuizAdaptationType.FOCUS_ON_MOOD:
            return f"Mood distress detected: {context.mood_indicators.get('distress', 0):.2f}"
        else:
            return "Response clarity improvement needed"
    
    # Additional task methods
    async def _adapt_quiz_questions(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt quiz questions mid-session."""
        patient_id = UUID(payload["patient_id"])
        session_id = UUID(payload["session_id"])
        
        context = await self._build_quiz_context(patient_id, "current")
        
        if not context.session or str(context.session.id) != str(session_id):
            return {"success": False, "error": "Session not found or inactive"}
        
        # Determine needed adaptation
        adaptation = await self._determine_adaptation(context)
        
        # Apply adaptation
        await self._apply_adaptation(context, adaptation)
        
        return {
            "success": True,
            "adaptation_applied": adaptation.value,
            "reason": await self._get_adaptation_reason(context, adaptation)
        }
    
    async def _analyze_quiz_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze completed quiz session."""
        session_id = UUID(payload["session_id"])
        
        # Get completed session
        session = self.quiz_session_service.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        # Build analysis context
        context = await self._build_quiz_context(session.patient_id, "analysis")
        context.session = session
        
        # Perform comprehensive analysis
        analysis = {
            "session_id": str(session_id),
            "patient_id": str(session.patient_id),
            "completion_quality": await self._assess_completion_quality(context),
            "mood_analysis": context.mood_indicators,
            "engagement_metrics": {
                "score": context.engagement_score,
                "adaptations_needed": len(context.adaptation_history)
            },
            "medical_insights": await self._extract_medical_insights(context),
            "recommendations": await self._generate_follow_up_recommendations(context)
        }
        
        return {"success": True, "analysis": analysis}
    
    async def _trigger_monthly_quiz(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger monthly quiz for patient."""
        patient_id = UUID(payload["patient_id"])
        
        # Build context
        context = await self._build_quiz_context(patient_id, "monthly_checkup")
        
        if not context.patient_data:
            return {"success": False, "error": "Patient not found"}
        
        # Check if already has active session
        active_session = self.quiz_session_service.get_active_session(patient_id)
        if active_session:
            return {"success": False, "error": "Patient already has active quiz session"}
        
        # Create and start quiz session
        result = await self._conduct_quiz_session({
            "patient_id": str(patient_id),
            "quiz_type": "monthly_checkup"
        })
        
        return result
    
    async def _assess_completion_quality(self, context: QuizContext) -> Dict[str, Any]:
        """Assess the quality of quiz completion."""
        return {
            "completeness": 1.0 if len(context.responses_so_far) >= 5 else len(context.responses_so_far) / 5,
            "response_clarity": sum(r.get("confidence", 1.0) for r in context.responses_so_far) / len(context.responses_so_far) if context.responses_so_far else 0,
            "engagement_maintained": context.engagement_score,
            "adaptations_needed": len(context.adaptation_history)
        }
    
    async def _extract_medical_insights(self, context: QuizContext) -> List[Dict]:
        """Extract medical insights from quiz responses."""
        insights = []
        
        # Analyze mood trends
        mood_responses = [r for r in context.responses_so_far if "humor" in r.get("question_text", "").lower()]
        if mood_responses:
            avg_mood = sum(float(r.get("processed_value", 3)) for r in mood_responses) / len(mood_responses)
            
            insights.append({
                "type": "mood_assessment",
                "value": avg_mood,
                "interpretation": "concerning" if avg_mood < 2.5 else "stable" if avg_mood < 3.5 else "positive",
                "confidence": 0.8
            })
        
        return insights
    
    async def _generate_follow_up_recommendations(self, context: QuizContext) -> List[str]:
        """Generate follow-up recommendations."""
        recommendations = []
        
        if context.stress_level > 0.7:
            recommendations.append("consider_stress_management_resources")
        
        if context.engagement_score < 0.5:
            recommendations.append("increase_personalized_communication")
        
        if len(context.adaptation_history) > 2:
            recommendations.append("review_communication_approach")
        
        return recommendations
    
    async def load_quiz_templates(self) -> None:
        """Load available quiz templates."""
        try:
            # List available templates
            available_templates = self.template_loader.list_available_templates()
            
            for template_info in available_templates:
                template_name = template_info.get("flow_type", template_info.get("name", "unknown"))
                try:
                    # Load template using the template loader's approach
                    template_file_path = template_info.get("file_path")
                    if template_file_path:
                        import yaml
                        with open(template_file_path, 'r', encoding='utf-8') as f:
                            template_data = yaml.safe_load(f)
                        
                        self.quiz_templates[template_name] = template_data
                        self.logger.info(f"Loaded quiz template: {template_name}")
                    
                except Exception as e:
                    self.logger.warning(f"Could not load quiz template {template_name}: {e}")
            
            self.logger.info(f"Successfully loaded {len(self.quiz_templates)} quiz templates")
            
        except Exception as e:
            self.logger.error(f"Failed to load quiz templates: {e}")
    
    def get_quiz_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get quiz template by name."""
        return self.quiz_templates.get(template_name)
    
    def get_questions_from_template(self, template_name: str) -> List[Dict[str, Any]]:
        """Extract questions from template."""
        template = self.get_quiz_template(template_name)
        if template and "questions" in template:
            return template["questions"]
        return []
    
    async def create_adaptive_quiz_from_template(
        self, template_name: str, patient_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create adaptive quiz based on template and patient context."""
        try:
            template = self.get_quiz_template(template_name)
            if not template:
                return None
            
            questions = self.get_questions_from_template(template_name)
            if not questions:
                return None
            
            # Apply personalization based on context
            personalized_questions = []
            
            for question in questions:
                # Check if question should be included based on context
                if self._should_include_question(question, patient_context):
                    personalized_question = await self._personalize_question(
                        question, patient_context
                    )
                    personalized_questions.append(personalized_question)
            
            return {
                "template_name": template_name,
                "original_questions": len(questions),
                "personalized_questions": len(personalized_questions),
                "questions": personalized_questions,
                "metadata": template.get("metadata", {}),
                "scoring": template.get("scoring", {}),
                "alerts": template.get("alerts", [])
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create adaptive quiz from template {template_name}: {e}")
            return None
    
    def _should_include_question(self, question: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Determine if question should be included based on context."""
        # Get question metadata
        metadata = question.get("metadata", {})
        importance = metadata.get("importance", "medium")
        category = metadata.get("category", "general")
        
        # Always include critical questions
        if importance == "critical":
            return True
        
        # Skip low importance questions if patient has low engagement
        engagement_score = context.get("engagement_score", 0.5)
        if importance == "low" and engagement_score < 0.4:
            return False
        
        # Context-specific filtering
        stress_level = context.get("stress_level", 0.0)
        if stress_level > 0.7 and category in ["detailed_symptoms", "lifestyle"]:
            return False  # Skip detailed questions if stressed
        
        return True
    
    async def _personalize_question(
        self, question: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Personalize question based on patient context."""
        try:
            personalized_question = question.copy()
            
            # Replace patient name placeholders
            patient_name = context.get("patient_name", "Cliente")
            if "text" in personalized_question:
                personalized_question["text"] = personalized_question["text"].replace(
                    "{patient_name}", patient_name
                ).replace("{name}", patient_name)
            
            if "description" in personalized_question:
                personalized_question["description"] = personalized_question["description"].replace(
                    "{patient_name}", patient_name
                ).replace("{name}", patient_name)
            
            # Adjust question based on mood indicators
            mood_trend = context.get("mood_trend", 0.0)
            if mood_trend < -0.5:
                # Add supportive note for patients with mood decline
                supportive_note = " (Lembre-se: não há resposta certa ou errada, queremos apenas saber como você está)"
                if "description" in personalized_question:
                    personalized_question["description"] += supportive_note
                else:
                    personalized_question["description"] = supportive_note
            
            # Use AI for advanced personalization if available
            if self.gemini_client and context.get("use_ai_personalization", False):
                ai_personalized = await self._apply_ai_personalization(
                    personalized_question, context
                )
                if ai_personalized:
                    personalized_question = ai_personalized
            
            return personalized_question
            
        except Exception as e:
            self.logger.error(f"Failed to personalize question: {e}")
            return question  # Return original if personalization fails
    
    async def _apply_ai_personalization(
        self, question: Dict[str, Any], context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Apply AI-based personalization to question."""
        try:
            # Prepare AI prompt
            ai_prompt = f"""
            Personalize esta pergunta de quiz médico para uma paciente de terapia hormonal:
            
            Pergunta original: {question.get('text', '')}
            Descrição: {question.get('description', '')}
            
            Contexto da paciente:
            - Nome: {context.get('patient_name', 'Cliente')}
            - Tendência de humor: {context.get('mood_trend', 0)}
            - Nível de stress: {context.get('stress_level', 0)}
            - Nível de engajamento: {context.get('engagement_score', 0.5)}
            - Dia de tratamento: {context.get('current_day', 1)}
            
            Mantenha o tom acolhedor, empático e profissional.
            Mantenha a estrutura original da pergunta.
            Retorne apenas o texto personalizado da pergunta.
            """
            
            response = await self.gemini_client.generate_content(ai_prompt)
            
            if response and hasattr(response, 'text'):
                personalized_text = response.text.strip()
                if personalized_text:
                    personalized_question = question.copy()
                    personalized_question["text"] = personalized_text
                    return personalized_question
            
        except Exception as e:
            self.logger.error(f"AI personalization failed: {e}")
        
        return None