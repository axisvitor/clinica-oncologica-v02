"""
Message Composer Agent

Specialized agent responsible for intelligent message composition and personalization.
Uses AI to create contextually appropriate, empathetic messages adapted to patient state.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, AgentCapabilities, MessagePriority
# SwarmManager and KnowledgeGraph imported lazily to avoid circular import
# from app.memory.knowledge_graph import KnowledgeGraph
from app.integrations.gemini_client import get_gemini_client, GeminiClient
from app.models.patient import Patient
from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.repositories.patient import PatientRepository
from app.services.conversation_memory import get_conversation_memory
from app.services.template_loader import EnhancedTemplateLoader, MessageTemplate, FlowTemplateData
from app.utils.logging import get_logger


def _get_knowledge_graph():
    """Lazy import for KnowledgeGraph to prevent startup failures."""
    try:
        from app.memory.knowledge_graph import KnowledgeGraph
        return KnowledgeGraph
    except ImportError as e:
        logging.warning(f"KnowledgeGraph import failed: {e}")
        return None


class MessageComposerAgent(BaseAgent):
    """
    Agent specialized in intelligent message composition and personalization.
    
    Capabilities:
    - Contextual message generation
    - Personalization based on patient history
    - Emotional tone adaptation
    - Multi-language support
    - Template customization
    - Conversation continuity
    """
    
    def __init__(self, db_session: Session, template_loader: Optional[EnhancedTemplateLoader] = None):
        """Initialize Message Composer Agent."""
        super().__init__(
            agent_id="message_composer",
            agent_type="communication",
            specialization="message_composer",
            db_session=db_session,
            capabilities=[
                AgentCapabilities.MESSAGE_COMPOSITION,
                AgentCapabilities.PERSONALIZATION,
                AgentCapabilities.EMOTIONAL_INTELLIGENCE,
                AgentCapabilities.PATIENT_ADAPTATION
            ]
        )
        
        self.db_session = db_session
        self.patient_repo = PatientRepository(db_session)
        self.gemini_client = get_gemini_client()
        self.conversation_memory = get_conversation_memory()
        self.logger = get_logger(f"agent.{self.agent_id}")
        
        # Template support
        self.template_loader = template_loader or EnhancedTemplateLoader(
            template_path="app/templates/flows",
            db=db_session
        )
        self.loaded_templates: Dict[str, FlowTemplateData] = {}
        
        # Message composition configuration
        self.composition_config = {
            "max_message_length": 1000,
            "personalization_level": "high",
            "empathy_threshold": 0.7,
            "context_window": 10,  # Previous messages to consider
            "languages": ["pt-BR", "en", "es"],
            "tone_adaptation": True,
            "emoji_usage": "contextual"
        }
        
        # Message templates by category
        self.message_templates = {
            "greeting": {
                "morning": "Bom dia {name}! Como você está se sentindo hoje? 🌅",
                "afternoon": "Boa tarde {name}! Espero que esteja tendo um dia tranquilo. ☀️",
                "evening": "Boa noite {name}! Como foi seu dia? 🌙"
            },
            "checkup": {
                "daily": "Olá {name}! É hora do nosso check-in diário. Como você está? 💙",
                "weekly": "Olá {name}! Vamos fazer nosso acompanhamento semanal? 📋",
                "monthly": "Olá {name}! É hora do check-up mensal. Preparada? ✨"
            },
            "support": {
                "encouragement": "Você está indo muito bem, {name}! Continue assim! 💪",
                "comfort": "Entendo que pode ser difícil, {name}. Estou aqui para apoiá-la. 🤗",
                "celebration": "Parabéns, {name}! Esse é um marco importante! 🎉"
            },
            "medical": {
                "reminder": "Lembrete gentil para {name}: {reminder_text} 💊",
                "appointment": "Oi {name}! Seu próximo appointment é {date}. Está tudo ok? 📅",
                "results": "Olá {name}! Seus resultados chegaram. Vamos conversar sobre eles? 📄"
            }
        }
        
        self.logger.info("Message Composer Agent initialized")
    
    async def initialize(self):
        """Initialize the agent and load templates."""
        try:
            await self.load_message_templates()
            self.logger.info("Message Composer Agent fully initialized with templates")
        except Exception as e:
            self.logger.error(f"Failed to initialize message templates: {e}")
            # Continue without templates - fallback to hardcoded ones
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process message composition task."""
        try:
            task_type = task.get("task_type")
            payload = task.get("payload", {})
            
            if task_type == "compose_message":
                return await self._compose_message(payload)
            elif task_type == "personalize_template":
                return await self._personalize_template(payload)
            elif task_type == "adapt_tone":
                return await self._adapt_message_tone(payload)
            elif task_type == "compose_follow_up":
                return await self._compose_follow_up(payload)
            elif task_type == "generate_quiz_message":
                return await self._generate_quiz_message(payload)
            else:
                return {
                    "success": False,
                    "error": f"Unknown task type: {task_type}"
                }
        
        except Exception as e:
            self.logger.error(f"Task processing failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _compose_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Compose intelligent message based on context."""
        try:
            patient_id = UUID(payload.get("patient_id"))
            message_type = payload.get("message_type", "general")
            context = payload.get("context", {})
            template_id = payload.get("template_id")
            custom_content = payload.get("content")
            
            # Get patient information
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}
            
            # Build composition context
            composition_context = await self._build_composition_context(
                patient, context
            )
            
            # Compose message based on method
            if custom_content:
                # Personalize custom content
                message_content = await self._personalize_custom_content(
                    custom_content, patient, composition_context
                )
            elif template_id:
                # Use template with personalization
                message_content = await self._compose_from_template(
                    template_id, patient, composition_context
                )
            else:
                # AI-generated message
                message_content = await self._generate_contextual_message(
                    message_type, patient, composition_context
                )
            
            # Apply tone adaptation
            if self.composition_config.get("tone_adaptation", True):
                message_content = await self._adapt_message_tone({
                    "content": message_content,
                    "patient_context": composition_context,
                    "target_tone": composition_context.get("preferred_tone", "supportive")
                })
            
            # Store message pattern for learning
            await self.conversation_memory.store_message_pattern(
                patient_id, message_content
            )
            
            # Update knowledge graph
            await self._update_message_knowledge(patient_id, message_content, message_type)
            
            return {
                "success": True,
                "message_content": message_content,
                "composition_metadata": {
                    "method": "ai_composed" if not template_id and not custom_content else "template_based",
                    "personalization_level": self.composition_config["personalization_level"],
                    "context_tokens": len(str(composition_context)),
                    "generated_at": datetime.utcnow().isoformat()
                }
            }
        
        except Exception as e:
            self.logger.error(f"Message composition failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _build_composition_context(
        self, 
        patient: Patient, 
        additional_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build comprehensive context for message composition."""
        try:
            # Get patient's communication preferences
            comm_prefs = await self.conversation_memory.get_communication_preferences(
                patient.id
            )
            
            # Get recent conversation history
            conversation_history = await self.conversation_memory.get_conversation_history(
                patient.id, limit=self.composition_config["context_window"]
            )
            
            # Calculate treatment timeline
            enrollment_date = patient.enrollment_date or patient.created_at
            days_since_enrollment = (datetime.utcnow() - enrollment_date).days
            
            # Get patient emotional state
            emotional_context = await self._analyze_patient_emotional_state(patient.id)
            
            # Get time-based context
            current_time = datetime.utcnow()
            time_context = {
                "hour": current_time.hour,
                "day_of_week": current_time.weekday(),
                "time_of_day": self._get_time_of_day(current_time.hour)
            }
            
            composition_context = {
                "patient": {
                    "id": str(patient.id),
                    "name": patient.name,
                    "age": getattr(patient, 'age', None),
                    "treatment_type": getattr(patient, 'treatment_type', 'hormone_therapy'),
                    "days_since_enrollment": days_since_enrollment,
                    "treatment_phase": self._determine_treatment_phase(days_since_enrollment)
                },
                "communication_preferences": comm_prefs,
                "conversation_history": conversation_history,
                "emotional_context": emotional_context,
                "time_context": time_context,
                "additional_context": additional_context
            }
            
            return composition_context
            
        except Exception as e:
            self.logger.error(f"Failed to build composition context: {e}")
            return {}
    
    async def _generate_contextual_message(
        self, 
        message_type: str, 
        patient: Patient, 
        context: Dict[str, Any]
    ) -> str:
        """Generate contextual message using AI."""
        try:
            # Build AI prompt
            prompt = f"""
            Compose uma mensagem personalizada e empática para uma paciente de oncologia.

            Informações da paciente:
            - Nome: {patient.name}
            - Tipo de tratamento: {context['patient'].get('treatment_type', 'terapia hormonal')}
            - Dias desde início: {context['patient'].get('days_since_enrollment', 0)}
            - Fase do tratamento: {context['patient'].get('treatment_phase', 'inicial')}

            Tipo de mensagem: {message_type}

            Contexto emocional: {context.get('emotional_context', {})}
            
            Preferências de comunicação: {context.get('communication_preferences', {})}

            Histórico recente: {context.get('conversation_history', [])}

            Contexto de tempo: {context.get('time_context', {})}

            Diretrizes:
            1. Use tom acolhedor e empático
            2. Personalize com o nome da paciente
            3. Considere o contexto emocional atual
            4. Mantenha entre 100-300 caracteres
            5. Use emojis apropriados mas moderadamente
            6. Evite linguagem médica técnica
            7. Seja positiva mas realista

            Retorne apenas o texto da mensagem, sem explicações adicionais.
            """
            
            message_content = await self.gemini_client.generate_content(prompt)
            
            # Clean and validate message
            if message_content:
                message_content = self._clean_message_content(message_content)
                if len(message_content) > self.composition_config["max_message_length"]:
                    message_content = message_content[:self.composition_config["max_message_length"] - 3] + "..."
                
                return message_content
            else:
                # Fallback to template
                return self._get_fallback_message(message_type, patient.name)
        
        except Exception as e:
            self.logger.error(f"AI message generation failed: {e}")
            return self._get_fallback_message(message_type, patient.name)
    
    async def _personalize_template(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Personalize message template with patient context."""
        try:
            patient_id = UUID(payload.get("patient_id"))
            template = payload.get("template")
            context = payload.get("context", {})
            
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}
            
            # Build personalization context
            composition_context = await self._build_composition_context(patient, context)
            
            # Apply basic template substitutions
            personalized_content = template.format(
                name=patient.name,
                **context
            )
            
            # Apply AI-enhanced personalization
            if self.composition_config["personalization_level"] == "high":
                enhanced_prompt = f"""
                Personalize esta mensagem para a paciente considerando seu contexto:

                Mensagem original: "{personalized_content}"
                
                Contexto da paciente: {composition_context}
                
                Mantenha o sentido original mas torne mais pessoal e empática.
                Retorne apenas a mensagem personalizada.
                """
                
                enhanced_content = await self.gemini_client.generate_content(enhanced_prompt)
                if enhanced_content:
                    personalized_content = self._clean_message_content(enhanced_content)
            
            return {
                "success": True,
                "personalized_content": personalized_content,
                "personalization_metadata": {
                    "template_used": True,
                    "ai_enhanced": self.composition_config["personalization_level"] == "high",
                    "context_applied": len(composition_context) > 0
                }
            }
        
        except Exception as e:
            self.logger.error(f"Template personalization failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _adapt_message_tone(self, payload: Dict[str, Any]) -> str:
        """Adapt message tone based on patient context."""
        try:
            content = payload.get("content", "")
            patient_context = payload.get("patient_context", {})
            target_tone = payload.get("target_tone", "supportive")
            
            if not content:
                return content
            
            # Analyze current emotional state
            emotional_context = patient_context.get("emotional_context", {})
            mood_score = emotional_context.get("mood_score", 0.5)
            stress_level = emotional_context.get("stress_level", 0.5)
            
            # Determine appropriate tone adaptation
            if mood_score < 0.3 or stress_level > 0.7:
                # Patient seems distressed - use gentle, supportive tone
                target_tone = "gentle_supportive"
            elif mood_score > 0.7:
                # Patient seems positive - use encouraging tone
                target_tone = "encouraging"
            
            # Apply tone adaptation with AI
            tone_prompt = f"""
            Adapte o tom desta mensagem para ser mais {target_tone}:

            Mensagem original: "{content}"
            
            Contexto emocional da paciente:
            - Humor: {mood_score} (0-1 scale)
            - Stress: {stress_level} (0-1 scale)
            
            Tom desejado: {target_tone}
            
            Mantenha o conteúdo principal mas ajuste o tom e as palavras.
            Retorne apenas a mensagem adaptada.
            """
            
            adapted_content = await self.gemini_client.generate_content(tone_prompt)
            
            if adapted_content:
                return self._clean_message_content(adapted_content)
            else:
                return content
        
        except Exception as e:
            self.logger.error(f"Tone adaptation failed: {e}")
            return payload.get("content", "")
    
    async def _compose_follow_up(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Compose intelligent follow-up message."""
        try:
            patient_id = UUID(payload.get("patient_id"))
            previous_interaction = payload.get("previous_interaction", {})
            follow_up_reason = payload.get("reason", "general")
            
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}
            
            # Analyze previous interaction
            interaction_analysis = await self._analyze_previous_interaction(
                previous_interaction
            )
            
            # Generate appropriate follow-up
            follow_up_prompt = f"""
            Compose uma mensagem de follow-up apropriada:

            Paciente: {patient.name}
            Interação anterior: {previous_interaction}
            Análise da interação: {interaction_analysis}
            Motivo do follow-up: {follow_up_reason}
            
            A mensagem deve:
            1. Referenciar sutilmente a conversa anterior
            2. Mostrar que você prestou atenção às preocupações
            3. Ser empática e de apoio
            4. Oferecer ajuda adicional se necessário
            
            Retorne apenas a mensagem de follow-up.
            """
            
            follow_up_content = await self.gemini_client.generate_content(follow_up_prompt)
            
            if not follow_up_content:
                follow_up_content = f"Oi {patient.name}! Como você está se sentindo após nossa conversa? Estou aqui se precisar de algo. 💙"
            
            return {
                "success": True,
                "follow_up_content": self._clean_message_content(follow_up_content),
                "follow_up_metadata": {
                    "reason": follow_up_reason,
                    "based_on_previous": bool(previous_interaction),
                    "interaction_analysis": interaction_analysis
                }
            }
        
        except Exception as e:
            self.logger.error(f"Follow-up composition failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_quiz_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate personalized quiz message."""
        try:
            patient_id = UUID(payload.get("patient_id"))
            quiz_context = payload.get("quiz_context", {})
            question_data = payload.get("question_data", {})
            
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}
            
            # Build quiz context
            composition_context = await self._build_composition_context(
                patient, quiz_context
            )
            
            question_text = question_data.get("text", "")
            question_type = question_data.get("type", "open_text")
            options = question_data.get("options", [])
            
            # Generate contextual quiz introduction
            quiz_prompt = f"""
            Crie uma introdução personalizada para uma pergunta de quiz médico:

            Paciente: {patient.name}
            Contexto do tratamento: {composition_context}
            
            Pergunta: "{question_text}"
            Tipo: {question_type}
            Opções: {options}
            
            A introdução deve:
            1. Ser calorosa e acolhedora
            2. Contextualizar a importância da pergunta
            3. Encorajar honestidade na resposta
            4. Não ser muito longa
            
            Formato: [Introdução] + [Pergunta] + [Opções se necessário]
            """
            
            quiz_message = await self.gemini_client.generate_content(quiz_prompt)
            
            if not quiz_message:
                # Fallback quiz message
                quiz_message = f"Olá {patient.name}! Vamos fazer uma pergunta importante para acompanhar seu bem-estar:\n\n{question_text}"
                
                if options:
                    quiz_message += "\n\nOpções:\n" + "\n".join([f"• {opt}" for opt in options])
            
            return {
                "success": True,
                "quiz_message": self._clean_message_content(quiz_message),
                "quiz_metadata": {
                    "question_type": question_type,
                    "has_options": len(options) > 0,
                    "personalized": True
                }
            }
        
        except Exception as e:
            self.logger.error(f"Quiz message generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _analyze_patient_emotional_state(self, patient_id: UUID) -> Dict[str, Any]:
        """Analyze patient's emotional state from recent interactions."""
        try:
            # Get recent conversation history
            history = await self.conversation_memory.get_conversation_history(
                patient_id, limit=5
            )
            
            if not history:
                return {"mood_score": 0.5, "stress_level": 0.5, "confidence": "low"}
            
            # Analyze emotional indicators in recent messages
            emotional_prompt = f"""
            Analise o estado emocional da paciente baseado neste histórico de conversa:
            
            Conversas recentes: {history}
            
            Determine:
            1. Humor geral (0-1, onde 0=muito negativo, 1=muito positivo)
            2. Nível de stress (0-1, onde 0=relaxado, 1=muito estressado)
            3. Indicadores de ansiedade (presente/ausente)
            4. Nível de confiança na análise (baixo/médio/alto)
            
            Retorne em formato JSON:
            {
                "mood_score": 0.0-1.0,
                "stress_level": 0.0-1.0,
                "anxiety_indicators": true/false,
                "confidence": "low/medium/high"
            }
            """
            
            analysis = await self.gemini_client.generate_content(emotional_prompt)
            
            if analysis:
                import json
                try:
                    return json.loads(analysis)
                except json.JSONDecodeError:
                    pass
            
            # Fallback analysis
            return {
                "mood_score": 0.5,
                "stress_level": 0.5,
                "anxiety_indicators": False,
                "confidence": "low"
            }
        
        except Exception as e:
            self.logger.error(f"Emotional analysis failed: {e}")
            return {"mood_score": 0.5, "stress_level": 0.5, "confidence": "error"}
    
    async def _analyze_previous_interaction(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze previous interaction for follow-up context."""
        try:
            if not interaction:
                return {}
            
            interaction_text = interaction.get("content", "")
            interaction_type = interaction.get("type", "unknown")
            patient_response = interaction.get("patient_response", "")
            
            analysis_prompt = f"""
            Analise esta interação prévia para contexto de follow-up:
            
            Tipo: {interaction_type}
            Conteúdo: "{interaction_text}"
            Resposta da paciente: "{patient_response}"
            
            Determine:
            1. Tom emocional da resposta
            2. Principais preocupações mencionadas
            3. Necessidade de follow-up (sim/não)
            4. Tipo de suporte necessário
            
            Retorne resumo da análise.
            """
            
            analysis = await self.gemini_client.generate_content(analysis_prompt)
            
            return {
                "summary": analysis or "Análise não disponível",
                "needs_follow_up": True,
                "interaction_type": interaction_type
            }
        
        except Exception as e:
            self.logger.error(f"Interaction analysis failed: {e}")
            return {}
    
    async def _update_message_knowledge(
        self, 
        patient_id: UUID, 
        message_content: str, 
        message_type: str
    ):
        """Update knowledge graph with message patterns."""
        try:
            # Store message pattern and effectiveness
            await self.coordination_hooks.store_in_memory(
                key=f"message_patterns/{patient_id}/{message_type}",
                data={
                    "content": message_content,
                    "type": message_type,
                    "composed_at": datetime.utcnow().isoformat(),
                    "method": "ai_generated"
                }
            )
        
        except Exception as e:
            self.logger.error(f"Failed to update message knowledge: {e}")
    
    def _determine_treatment_phase(self, days_since_enrollment: int) -> str:
        """Determine treatment phase based on enrollment duration."""
        if days_since_enrollment <= 15:
            return "initial"
        elif days_since_enrollment <= 45:
            return "adaptation" 
        else:
            return "maintenance"
    
    def _get_time_of_day(self, hour: int) -> str:
        """Get time of day category."""
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "night"
    
    def _clean_message_content(self, content: str) -> str:
        """Clean and validate message content."""
        if not content:
            return ""
        
        # Remove extra whitespace
        content = content.strip()
        
        # Remove quotes if AI returned quoted text
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        
        # Ensure reasonable length
        if len(content) > self.composition_config["max_message_length"]:
            content = content[:self.composition_config["max_message_length"] - 3] + "..."
        
        return content
    
    def _get_fallback_message(self, message_type: str, patient_name: str) -> str:
        """Get fallback message when AI generation fails."""
        fallback_messages = {
            "greeting": f"Olá {patient_name}! Como você está hoje? 😊",
            "checkup": f"Oi {patient_name}! Hora do nosso check-in. Como você se sente? 💙",
            "support": f"Olá {patient_name}! Lembre-se que estou aqui para apoiá-la. 🤗",
            "reminder": f"Oi {patient_name}! Um lembrete gentil para você. 📝",
            "follow_up": f"Oi {patient_name}! Pensando em você. Como está? 💙"
        }
        
        return fallback_messages.get(message_type, f"Olá {patient_name}! Como você está? 😊")
    
    async def load_message_templates(self) -> None:
        """Load message templates from template files."""
        try:
            # Load flow templates that contain message templates
            flow_types = ["initial_15_days", "days_16_45", "monthly_recurring"]
            
            for flow_type in flow_types:
                try:
                    template_data = self.template_loader.load_flow_template(flow_type)
                    self.loaded_templates[flow_type] = template_data
                    self.logger.info(f"Loaded {flow_type} template: {len(template_data.messages)} message templates")
                except Exception as e:
                    self.logger.warning(f"Could not load {flow_type} template: {e}")
            
            self.logger.info(f"Successfully loaded {len(self.loaded_templates)} flow templates")
            
        except Exception as e:
            self.logger.error(f"Failed to load message templates: {e}")
    
    def get_template_message(self, flow_type: str, day: int) -> Optional[MessageTemplate]:
        """Get message template for specific flow type and day."""
        template_data = self.loaded_templates.get(flow_type)
        if template_data:
            return template_data.messages.get(day)
        return None
    
    async def compose_from_flow_template(
        self, flow_type: str, day: int, patient: Patient, context: Dict[str, Any]
    ) -> Optional[str]:
        """Compose message from flow template."""
        try:
            # Get template message
            template_message = self.get_template_message(flow_type, day)
            if not template_message:
                return None
            
            # Prepare personalization context
            personalization_context = {
                "patient_name": patient.name,
                "current_day": day,
                "mood_trend": context.get("mood_indicators", {}).get("trend", 0),
                "engagement_level": context.get("engagement_score", 0.5),
                "stress_level": context.get("stress_level", 0.0),
                "personalization_hints": template_message.personalization_hints,
                "core_elements": template_message.core_elements
            }
            
            # Use AI instructions if available
            if template_message.ai_instructions and self.gemini_client:
                composed_message = await self._compose_with_ai_instructions(
                    template_message, personalization_context
                )
            else:
                # Basic personalization
                composed_message = self._apply_basic_template_personalization(
                    template_message, personalization_context
                )
            
            return composed_message
            
        except Exception as e:
            self.logger.error(f"Failed to compose from flow template: {e}")
            return None
    
    async def _compose_with_ai_instructions(
        self, template: MessageTemplate, context: Dict[str, Any]
    ) -> str:
        """Compose message using AI instructions from template."""
        try:
            # Prepare AI prompt using template instructions
            ai_prompt = f"""
            {template.ai_instructions}
            
            Contexto do paciente:
            - Nome: {context['patient_name']}
            - Dia do tratamento: {context['current_day']}
            - Tendência de humor: {context['mood_trend']}
            - Nível de engajamento: {context['engagement_level']}
            - Nível de stress: {context['stress_level']}
            
            Dicas de personalização: {', '.join(context['personalization_hints'])}
            Elementos essenciais: {context['core_elements']}
            
            Conteúdo base: {template.base_content}
            
            Gere uma mensagem personalizada seguindo as instruções acima.
            Mantenha o tom apropriado para o contexto médico e de apoio.
            """
            
            response = await self.gemini_client.generate_content(ai_prompt)
            
            if response and hasattr(response, 'text'):
                return self._clean_message_content(response.text)
            
            # Fallback to basic personalization
            return self._apply_basic_template_personalization(template, context)
            
        except Exception as e:
            self.logger.error(f"AI composition failed: {e}")
            return self._apply_basic_template_personalization(template, context)
    
    def _apply_basic_template_personalization(
        self, template: MessageTemplate, context: Dict[str, Any]
    ) -> str:
        """Apply basic personalization to template."""
        content = template.base_content
        
        # Replace patient name placeholders
        content = content.replace("{patient_name}", context["patient_name"])
        content = content.replace("{name}", context["patient_name"])
        
        # Add mood-based personalization
        mood_trend = context.get("mood_trend", 0)
        if mood_trend < -0.5:
            content += " Estou aqui para te apoiar neste momento. 💜"
        elif mood_trend > 0.5:
            content += " Fico feliz em saber que você está bem! 😊"
        
        # Add engagement-based elements
        engagement = context.get("engagement_level", 0.5)
        if engagement < 0.3:
            content += " Lembre-se que pode me procurar sempre que precisar."
        
        return content
    
    def get_available_templates(self) -> Dict[str, List[int]]:
        """Get information about available templates."""
        available = {}
        for flow_type, template_data in self.loaded_templates.items():
            available[flow_type] = list(template_data.messages.keys())
        return available
    
    async def reload_templates(self) -> bool:
        """Reload all templates from source."""
        try:
            self.loaded_templates.clear()
            await self.load_message_templates()
            return len(self.loaded_templates) > 0
        except Exception as e:
            self.logger.error(f"Failed to reload templates: {e}")
            return False
    
    def _compose_from_template(
        self, 
        template_id: str, 
        patient: Patient, 
        context: Dict[str, Any]
    ) -> str:
        """Compose message from predefined template."""
        # This would look up template from database or config
        # For now, use built-in templates
        
        time_of_day = context.get("time_context", {}).get("time_of_day", "morning")
        
        if template_id in self.message_templates:
            template_category = self.message_templates[template_id]
            if time_of_day in template_category:
                return template_category[time_of_day].format(name=patient.name)
            else:
                # Use first available template in category
                first_template = list(template_category.values())[0]
                return first_template.format(name=patient.name)
        
        return self._get_fallback_message("general", patient.name)
    
    async def _personalize_custom_content(
        self, 
        content: str, 
        patient: Patient, 
        context: Dict[str, Any]
    ) -> str:
        """Personalize custom content with patient context."""
        try:
            # Basic substitutions
            personalized = content.replace("{name}", patient.name)
            personalized = personalized.replace("{patient_name}", patient.name)
            
            # Add AI personalization if enabled
            if self.composition_config["personalization_level"] == "high":
                personalization_prompt = f"""
                Personalize este conteúdo para a paciente:
                
                Conteúdo: "{personalized}"
                Paciente: {patient.name}
                Contexto: {context}
                
                Mantenha o sentido mas torne mais pessoal e empático.
                Retorne apenas o conteúdo personalizado.
                """
                
                ai_personalized = await self.gemini_client.generate_content(personalization_prompt)
                if ai_personalized:
                    personalized = self._clean_message_content(ai_personalized)
            
            return personalized
        
        except Exception as e:
            self.logger.error(f"Content personalization failed: {e}")
            return content.replace("{name}", patient.name)