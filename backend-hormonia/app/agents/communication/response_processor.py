"""
Response Processor Agent

Specialized agent for intelligent processing and analysis of patient responses.
Uses advanced NLP and AI to understand context, emotion, medical concerns, and intent.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from uuid import UUID
import re
import json

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, AgentCapabilities, MessagePriority
# SwarmManager and KnowledgeGraph imported lazily to avoid circular import
# from app.memory.knowledge_graph import KnowledgeGraph
from app.integrations.gemini_client import get_gemini_client, GeminiClient
from app.models.patient import Patient
from app.models.message import Message
from app.repositories.patient import PatientRepository
from app.services.conversation_memory import get_conversation_memory
from app.utils.logging import get_logger


def _get_knowledge_graph():
    """Lazy import for KnowledgeGraph to prevent startup failures."""
    try:
        from app.memory.knowledge_graph import KnowledgeGraph
        return KnowledgeGraph
    except ImportError as e:
        logging.warning(f"KnowledgeGraph import failed: {e}")
        return None


class ResponseAnalysis:
    """Structured response analysis result."""
    
    def __init__(self):
        self.sentiment_score: float = 0.0  # -1 to 1
        self.emotion_tags: List[str] = []
        self.medical_concerns: List[str] = []
        self.urgency_level: str = "low"  # low, medium, high, critical
        self.intent_classification: str = "unknown"
        self.key_topics: List[str] = []
        self.requires_follow_up: bool = False
        self.requires_medical_attention: bool = False
        self.confidence_score: float = 0.0  # 0 to 1
        self.extracted_entities: Dict[str, Any] = {}
        self.response_quality: str = "complete"  # complete, partial, unclear, evasive
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis to dictionary."""
        return {
            "sentiment_score": self.sentiment_score,
            "emotion_tags": self.emotion_tags,
            "medical_concerns": self.medical_concerns,
            "urgency_level": self.urgency_level,
            "intent_classification": self.intent_classification,
            "key_topics": self.key_topics,
            "requires_follow_up": self.requires_follow_up,
            "requires_medical_attention": self.requires_medical_attention,
            "confidence_score": self.confidence_score,
            "extracted_entities": self.extracted_entities,
            "response_quality": self.response_quality
        }


class ResponseProcessorAgent(BaseAgent):
    """
    Agent specialized in intelligent processing of patient responses.
    
    Capabilities:
    - Sentiment analysis and emotion detection
    - Medical concern identification
    - Intent classification
    - Urgency assessment
    - Entity extraction
    - Context understanding
    - Response quality evaluation
    """
    
    def __init__(self, db_session: Session):
        """Initialize Response Processor Agent."""
        super().__init__(
            agent_id="response_processor",
            agent_type="communication",
            specialization="response_processor",
            db_session=db_session,
            capabilities=[
                AgentCapabilities.RESPONSE_INTERPRETATION,
                AgentCapabilities.SENTIMENT_ANALYSIS,
                AgentCapabilities.MEDICAL_NLP,
                AgentCapabilities.EMOTIONAL_INTELLIGENCE
            ]
        )
        
        self.db_session = db_session
        self.patient_repo = PatientRepository(db_session)
        self.gemini_client = get_gemini_client()
        self.conversation_memory = get_conversation_memory()
        self.logger = get_logger(f"agent.{self.agent_id}")
        
        # Processing configuration
        self.processing_config = {
            "sentiment_threshold": {
                "very_negative": -0.7,
                "negative": -0.3,
                "neutral": 0.3,
                "positive": 0.7
            },
            "urgency_keywords": {
                "critical": ["emergência", "urgente", "dor intensa", "sangramento", "febre alta"],
                "high": ["preocupada", "ansiedade", "não durmo", "muito mal", "piorou"],
                "medium": ["desconfortável", "cansada", "enjoada", "preocupação"]
            },
            "medical_concern_patterns": [
                r"dor\s+(forte|intensa|insuportável)",
                r"sangramento",
                r"febre\s+(alta|muito|acima)",
                r"não\s+(consigo|durmo|como)",
                r"vômito|enjoo\s+(constante|frequente)",
                r"tontura|vertigem",
                r"falta\s+de\s+ar",
                r"inchação|inchaço"
            ],
            "emotion_indicators": {
                "anxiety": ["nervosa", "ansiosa", "preocupada", "medo", "aflita"],
                "sadness": ["triste", "deprimida", "desanimada", "chorando"],
                "anger": ["irritada", "brava", "revoltada", "indignada"],
                "joy": ["feliz", "alegre", "bem", "ótima", "animada"],
                "fear": ["assustada", "com medo", "receosa", "apavorada"]
            },
            "intent_patterns": {
                "question": r"\?|como\s+(fazer|saber)|o\s+que\s+(é|significa)",
                "complaint": r"(não\s+estou|me\s+sinto)\s+(bem|boa)",
                "request_help": r"(ajuda|ajudem|socorro|preciso)",
                "report_symptom": r"(tenho|sinto|estou\s+com)\s+",
                "express_gratitude": r"(obrigad|grat|muito\s+bom)"
            }
        }
        
        self.logger.info("Response Processor Agent initialized")
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process response analysis task."""
        try:
            task_type = task.get("task_type")
            payload = task.get("payload", {})
            
            if task_type == "process_quiz_response":
                return await self._process_quiz_response(payload)
            elif task_type == "analyze_response":
                return await self._analyze_response(payload)
            elif task_type == "extract_medical_info":
                return await self._extract_medical_info(payload)
            elif task_type == "assess_urgency":
                return await self._assess_urgency(payload)
            elif task_type == "classify_intent":
                return await self._classify_intent(payload)
            else:
                return {
                    "success": False,
                    "error": f"Unknown task type: {task_type}"
                }
        
        except Exception as e:
            self.logger.error(f"Task processing failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_quiz_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process quiz response with comprehensive analysis."""
        try:
            patient_id = UUID(payload.get("patient_id"))
            response_text = payload.get("response_text", "")
            message_metadata = payload.get("message_metadata", {})
            question_context = payload.get("question_context", {})
            
            # Get patient information
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}
            
            # Perform comprehensive analysis
            analysis = await self._comprehensive_response_analysis(
                response_text, patient, question_context
            )
            
            # Process quiz-specific logic
            quiz_processing = await self._process_quiz_logic(
                response_text, question_context, analysis
            )
            
            # Generate recommendations
            recommendations = await self._generate_response_recommendations(
                analysis, patient, question_context
            )
            
            # Update patient insights
            await self._update_patient_insights(patient_id, analysis, response_text)
            
            # Check if follow-up is needed
            follow_up_needed = await self._determine_follow_up_need(
                analysis, patient, question_context
            )
            
            return {
                "success": True,
                "analysis": analysis.to_dict(),
                "quiz_processing": quiz_processing,
                "recommendations": recommendations,
                "follow_up_needed": follow_up_needed,
                "processing_metadata": {
                    "processed_at": datetime.utcnow().isoformat(),
                    "processor_version": "2.0",
                    "processing_time_ms": 0  # Would be calculated in real implementation
                }
            }
        
        except Exception as e:
            self.logger.error(f"Quiz response processing failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _comprehensive_response_analysis(
        self, 
        response_text: str, 
        patient: Patient, 
        context: Dict[str, Any]
    ) -> ResponseAnalysis:
        """Perform comprehensive analysis of patient response."""
        try:
            analysis = ResponseAnalysis()
            
            # Basic sentiment analysis
            analysis.sentiment_score = await self._analyze_sentiment(response_text)
            
            # Emotion detection
            analysis.emotion_tags = await self._detect_emotions(response_text)
            
            # Medical concern identification
            analysis.medical_concerns = await self._identify_medical_concerns(response_text)
            
            # Urgency assessment
            analysis.urgency_level = await self._assess_response_urgency(response_text)
            
            # Intent classification
            analysis.intent_classification = await self._classify_response_intent(response_text)
            
            # Key topic extraction
            analysis.key_topics = await self._extract_key_topics(response_text)
            
            # Entity extraction
            analysis.extracted_entities = await self._extract_entities(response_text)
            
            # Response quality assessment
            analysis.response_quality = await self._assess_response_quality(
                response_text, context
            )
            
            # AI-powered comprehensive analysis
            ai_analysis = await self._ai_comprehensive_analysis(
                response_text, patient, context
            )
            
            # Merge AI insights
            if ai_analysis:
                analysis = self._merge_ai_analysis(analysis, ai_analysis)
            
            # Determine follow-up and medical attention needs
            analysis.requires_follow_up = self._requires_follow_up(analysis)
            analysis.requires_medical_attention = self._requires_medical_attention(analysis)
            
            # Calculate confidence score
            analysis.confidence_score = self._calculate_confidence_score(analysis)
            
            return analysis
        
        except Exception as e:
            self.logger.error(f"Comprehensive analysis failed: {e}")
            return ResponseAnalysis()
    
    async def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of response text."""
        try:
            if not text.strip():
                return 0.0
            
            # AI-powered sentiment analysis
            sentiment_prompt = f"""
            Analise o sentimento desta resposta de paciente de oncologia:
            
            Texto: "{text}"
            
            Considere:
            - Contexto médico e emocional
            - Nuances do português brasileiro
            - Expressões indiretas de desconforto
            
            Retorne apenas um número entre -1 e 1:
            -1 = muito negativo
            0 = neutro
            1 = muito positivo
            """
            
            sentiment_result = await self.gemini_client.generate_content(sentiment_prompt)
            
            if sentiment_result:
                try:
                    score = float(sentiment_result.strip())
                    return max(-1.0, min(1.0, score))  # Clamp between -1 and 1
                except ValueError:
                    pass
            
            # Fallback: rule-based sentiment
            return self._rule_based_sentiment(text)
        
        except Exception as e:
            self.logger.error(f"Sentiment analysis failed: {e}")
            return 0.0
    
    async def _detect_emotions(self, text: str) -> List[str]:
        """Detect emotions in response text."""
        try:
            emotions = []
            text_lower = text.lower()
            
            # Rule-based emotion detection
            for emotion, indicators in self.processing_config["emotion_indicators"].items():
                if any(indicator in text_lower for indicator in indicators):
                    emotions.append(emotion)
            
            # AI-powered emotion detection for nuanced analysis
            emotion_prompt = f"""
            Identifique as emoções presentes nesta resposta de paciente:
            
            Texto: "{text}"
            
            Possíveis emoções: ansiedade, tristeza, raiva, alegria, medo, esperança, frustração, alívio, preocupação
            
            Retorne apenas as emoções detectadas, separadas por vírgula.
            Se nenhuma emoção clara, retorne "neutro".
            """
            
            ai_emotions = await self.gemini_client.generate_content(emotion_prompt)
            
            if ai_emotions and ai_emotions.strip().lower() != "neutro":
                ai_emotion_list = [e.strip() for e in ai_emotions.split(",")]
                emotions.extend(ai_emotion_list)
            
            # Remove duplicates and return
            return list(set(emotions))
        
        except Exception as e:
            self.logger.error(f"Emotion detection failed: {e}")
            return []
    
    async def _identify_medical_concerns(self, text: str) -> List[str]:
        """Identify medical concerns in response."""
        try:
            concerns = []
            text_lower = text.lower()
            
            # Pattern-based medical concern detection
            for pattern in self.processing_config["medical_concern_patterns"]:
                matches = re.findall(pattern, text_lower)
                if matches:
                    concerns.extend(matches)
            
            # AI-powered medical concern identification
            medical_prompt = f"""
            Identifique preocupações médicas mencionadas nesta resposta:
            
            Texto: "{text}"
            
            Procure por:
            - Sintomas físicos
            - Efeitos colaterais
            - Mudanças no estado de saúde
            - Preocupações com o tratamento
            
            Retorne cada preocupação em uma linha separada.
            Se não houver preocupações, retorne "nenhuma".
            """
            
            ai_concerns = await self.gemini_client.generate_content(medical_prompt)
            
            if ai_concerns and ai_concerns.strip().lower() != "nenhuma":
                ai_concern_list = [c.strip() for c in ai_concerns.split("\n") if c.strip()]
                concerns.extend(ai_concern_list)
            
            return list(set(concerns))
        
        except Exception as e:
            self.logger.error(f"Medical concern identification failed: {e}")
            return []
    
    async def _assess_response_urgency(self, text: str) -> str:
        """Assess urgency level of response."""
        try:
            text_lower = text.lower()
            
            # Check urgency keywords
            for level, keywords in self.processing_config["urgency_keywords"].items():
                if any(keyword in text_lower for keyword in keywords):
                    return level
            
            # AI-powered urgency assessment
            urgency_prompt = f"""
            Avalie o nível de urgência desta resposta de paciente oncológica:
            
            Texto: "{text}"
            
            Níveis:
            - critical: emergência médica imediata
            - high: necessita atenção médica em 24h
            - medium: deve ser acompanhado pela equipe
            - low: acompanhamento de rotina
            
            Retorne apenas: critical, high, medium ou low
            """
            
            urgency_result = await self.gemini_client.generate_content(urgency_prompt)
            
            if urgency_result and urgency_result.strip() in ["critical", "high", "medium", "low"]:
                return urgency_result.strip()
            
            return "low"
        
        except Exception as e:
            self.logger.error(f"Urgency assessment failed: {e}")
            return "low"
    
    async def _classify_response_intent(self, text: str) -> str:
        """Classify the intent of patient response."""
        try:
            text_lower = text.lower()
            
            # Pattern-based intent classification
            for intent, pattern in self.processing_config["intent_patterns"].items():
                if re.search(pattern, text_lower):
                    return intent
            
            # AI-powered intent classification
            intent_prompt = f"""
            Classifique a intenção desta resposta de paciente:
            
            Texto: "{text}"
            
            Possíveis intenções:
            - question: faz uma pergunta
            - complaint: expressa uma queixa ou desconforto
            - request_help: pede ajuda
            - report_symptom: relata sintoma
            - express_gratitude: expressa gratidão
            - provide_info: fornece informação solicitada
            - express_emotion: expressa sentimentos
            
            Retorne apenas a intenção mais provável.
            """
            
            intent_result = await self.gemini_client.generate_content(intent_prompt)
            
            if intent_result:
                return intent_result.strip()
            
            return "provide_info"
        
        except Exception as e:
            self.logger.error(f"Intent classification failed: {e}")
            return "unknown"
    
    async def _extract_key_topics(self, text: str) -> List[str]:
        """Extract key topics from response."""
        try:
            # AI-powered topic extraction
            topic_prompt = f"""
            Extraia os principais tópicos mencionados nesta resposta:
            
            Texto: "{text}"
            
            Identifique tópicos como:
            - Sintomas específicos
            - Emoções
            - Atividades mencionadas
            - Pessoas (família, médicos)
            - Tratamentos ou medicamentos
            
            Retorne os tópicos separados por vírgula.
            Máximo 5 tópicos mais relevantes.
            """
            
            topics_result = await self.gemini_client.generate_content(topic_prompt)
            
            if topics_result:
                topics = [t.strip() for t in topics_result.split(",") if t.strip()]
                return topics[:5]  # Limit to top 5
            
            return []
        
        except Exception as e:
            self.logger.error(f"Topic extraction failed: {e}")
            return []
    
    async def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract named entities and structured information."""
        try:
            entities = {
                "symptoms": [],
                "medications": [],
                "people": [],
                "locations": [],
                "dates": [],
                "numbers": []
            }
            
            # AI-powered entity extraction
            entity_prompt = f"""
            Extraia entidades estruturadas desta resposta:
            
            Texto: "{text}"
            
            Identifique:
            - Sintomas: dor, náusea, cansaço, etc.
            - Medicamentos: nomes de remédios
            - Pessoas: médico, enfermeira, família
            - Datas ou horários mencionados
            - Números relevantes (doses, dias, etc.)
            
            Retorne em formato JSON:
            {{
                "symptoms": ["sintoma1", "sintoma2"],
                "medications": ["med1", "med2"],
                "people": ["pessoa1"],
                "dates": ["data1"],
                "numbers": ["numero1"]
            }}
            """
            
            entity_result = await self.gemini_client.generate_content(entity_prompt)
            
            if entity_result:
                try:
                    ai_entities = json.loads(entity_result)
                    entities.update(ai_entities)
                except json.JSONDecodeError:
                    pass
            
            return entities
        
        except Exception as e:
            self.logger.error(f"Entity extraction failed: {e}")
            return {}
    
    async def _assess_response_quality(self, text: str, context: Dict[str, Any]) -> str:
        """Assess quality and completeness of response."""
        try:
            if not text.strip():
                return "empty"
            
            text_len = len(text.strip())
            
            # Basic quality assessment
            if text_len < 5:
                return "too_short"
            elif text_len < 20:
                return "brief"
            
            # Check for evasive responses
            evasive_patterns = [
                r"não\s+sei", r"talvez", r"não\s+tenho\s+certeza",
                r"não\s+quero\s+(falar|responder)", r"prefiro\s+não"
            ]
            
            if any(re.search(pattern, text.lower()) for pattern in evasive_patterns):
                return "evasive"
            
            # AI-powered quality assessment
            quality_prompt = f"""
            Avalie a qualidade desta resposta de paciente:
            
            Texto: "{text}"
            Contexto da pergunta: {context}
            
            Critérios:
            - complete: resposta clara e informativa
            - partial: resposta incompleta mas útil
            - unclear: resposta confusa ou ambígua
            - evasive: evita responder diretamente
            
            Retorne apenas: complete, partial, unclear ou evasive
            """
            
            quality_result = await self.gemini_client.generate_content(quality_prompt)
            
            if quality_result and quality_result.strip() in ["complete", "partial", "unclear", "evasive"]:
                return quality_result.strip()
            
            return "complete"
        
        except Exception as e:
            self.logger.error(f"Quality assessment failed: {e}")
            return "unknown"
    
    async def _ai_comprehensive_analysis(
        self, 
        text: str, 
        patient: Patient, 
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Perform AI-powered comprehensive analysis."""
        try:
            comprehensive_prompt = f"""
            Faça uma análise abrangente desta resposta de paciente oncológica:
            
            Paciente: {patient.name}
            Resposta: "{text}"
            Contexto: {context}
            
            Analise:
            1. Estado emocional geral
            2. Sinais de alerta médicos
            3. Necessidade de suporte adicional
            4. Padrões de comunicação
            5. Insights sobre o bem-estar da paciente
            
            Retorne em formato JSON:
            {{
                "emotional_state": "descrição",
                "medical_alerts": ["alerta1", "alerta2"],
                "support_needs": ["necessidade1"],
                "communication_patterns": ["padrão1"],
                "wellbeing_insights": ["insight1"],
                "overall_assessment": "resumo geral"
            }}
            """
            
            ai_result = await self.gemini_client.generate_content(comprehensive_prompt)
            
            if ai_result:
                try:
                    return json.loads(ai_result)
                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse AI comprehensive analysis JSON")
            
            return None
        
        except Exception as e:
            self.logger.error(f"AI comprehensive analysis failed: {e}")
            return None
    
    async def _process_quiz_logic(
        self, 
        response_text: str, 
        question_context: Dict[str, Any], 
        analysis: ResponseAnalysis
    ) -> Dict[str, Any]:
        """Process quiz-specific logic based on response."""
        try:
            question_type = question_context.get("type", "open_text")
            question_id = question_context.get("id", "unknown")
            
            quiz_result = {
                "question_id": question_id,
                "question_type": question_type,
                "raw_response": response_text,
                "processed_value": None,
                "interpretation": None,
                "needs_clarification": False
            }
            
            # Process based on question type
            if question_type == "scale":
                quiz_result.update(await self._process_scale_response(response_text, question_context))
            elif question_type == "multiple_choice":
                quiz_result.update(await self._process_multiple_choice_response(response_text, question_context))
            elif question_type == "yes_no":
                quiz_result.update(await self._process_yes_no_response(response_text, question_context))
            elif question_type == "open_text":
                quiz_result.update(await self._process_open_text_response(response_text, question_context, analysis))
            
            return quiz_result
        
        except Exception as e:
            self.logger.error(f"Quiz logic processing failed: {e}")
            return {"error": str(e)}
    
    async def _process_scale_response(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process scale-type question response."""
        # Extract number from response
        numbers = re.findall(r'\b([1-5])\b', text)
        
        if numbers:
            value = int(numbers[0])
            interpretation = self._interpret_scale_value(value, context)
            return {
                "processed_value": value,
                "interpretation": interpretation,
                "needs_clarification": False
            }
        else:
            # Try AI interpretation
            ai_value = await self._ai_interpret_scale(text, context)
            if ai_value:
                return {
                    "processed_value": ai_value,
                    "interpretation": self._interpret_scale_value(ai_value, context),
                    "needs_clarification": False,
                    "ai_interpreted": True
                }
            
            return {
                "processed_value": None,
                "interpretation": "Resposta não clara",
                "needs_clarification": True
            }
    
    async def _process_multiple_choice_response(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process multiple choice response."""
        options = context.get("options", [])
        
        # Direct match attempt
        text_lower = text.lower()
        for option in options:
            if option.get("text", "").lower() in text_lower:
                return {
                    "processed_value": option.get("value"),
                    "interpretation": f"Selecionou: {option.get('text')}",
                    "needs_clarification": False
                }
        
        # AI interpretation
        ai_match = await self._ai_interpret_multiple_choice(text, options)
        if ai_match:
            return {
                "processed_value": ai_match["value"],
                "interpretation": f"Interpretado como: {ai_match['text']}",
                "needs_clarification": False,
                "ai_interpreted": True
            }
        
        return {
            "processed_value": None,
            "interpretation": "Opção não identificada",
            "needs_clarification": True
        }
    
    async def _process_yes_no_response(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process yes/no response."""
        text_lower = text.lower()
        
        yes_indicators = ["sim", "yes", "s", "claro", "certamente", "com certeza"]
        no_indicators = ["não", "nao", "no", "n", "nunca", "jamais"]
        
        if any(indicator in text_lower for indicator in yes_indicators):
            return {
                "processed_value": "yes",
                "interpretation": "Resposta afirmativa",
                "needs_clarification": False
            }
        elif any(indicator in text_lower for indicator in no_indicators):
            return {
                "processed_value": "no",
                "interpretation": "Resposta negativa",
                "needs_clarification": False
            }
        
        return {
            "processed_value": None,
            "interpretation": "Resposta ambígua",
            "needs_clarification": True
        }
    
    async def _process_open_text_response(
        self, 
        text: str, 
        context: Dict[str, Any], 
        analysis: ResponseAnalysis
    ) -> Dict[str, Any]:
        """Process open text response with analysis insights."""
        return {
            "processed_value": text,
            "interpretation": f"Resposta analisada - Sentimento: {analysis.sentiment_score:.2f}, Tópicos: {', '.join(analysis.key_topics[:3])}",
            "needs_clarification": analysis.response_quality in ["unclear", "evasive"],
            "analysis_summary": {
                "sentiment": analysis.sentiment_score,
                "key_topics": analysis.key_topics[:3],
                "medical_concerns": len(analysis.medical_concerns) > 0
            }
        }
    
    def _rule_based_sentiment(self, text: str) -> float:
        """Simple rule-based sentiment analysis fallback."""
        positive_words = ["bem", "boa", "melhor", "feliz", "alegre", "otima", "excelente"]
        negative_words = ["mal", "ruim", "pior", "triste", "terrível", "horrível", "péssimo"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in negative_words)
        
        if positive_count + negative_count == 0:
            return 0.0
        
        return (positive_count - negative_count) / (positive_count + negative_count)
    
    def _requires_follow_up(self, analysis: ResponseAnalysis) -> bool:
        """Determine if response requires follow-up."""
        return (
            analysis.urgency_level in ["high", "critical"] or
            analysis.sentiment_score < -0.5 or
            len(analysis.medical_concerns) > 0 or
            "anxiety" in analysis.emotion_tags or
            analysis.response_quality == "evasive"
        )
    
    def _requires_medical_attention(self, analysis: ResponseAnalysis) -> bool:
        """Determine if response requires medical attention."""
        return (
            analysis.urgency_level == "critical" or
            len(analysis.medical_concerns) > 2 or
            analysis.sentiment_score < -0.7
        )
    
    def _calculate_confidence_score(self, analysis: ResponseAnalysis) -> float:
        """Calculate confidence score for analysis."""
        confidence = 0.5  # Base confidence
        
        # Adjust based on various factors
        if analysis.response_quality == "complete":
            confidence += 0.2
        elif analysis.response_quality in ["unclear", "evasive"]:
            confidence -= 0.2
        
        if len(analysis.key_topics) > 0:
            confidence += 0.1
        
        if analysis.intent_classification != "unknown":
            confidence += 0.1
        
        # Clamp between 0 and 1
        return max(0.0, min(1.0, confidence))
    
    def _merge_ai_analysis(self, analysis: ResponseAnalysis, ai_data: Dict[str, Any]) -> ResponseAnalysis:
        """Merge AI analysis insights into structured analysis."""
        try:
            # Update medical concerns with AI alerts
            if "medical_alerts" in ai_data:
                analysis.medical_concerns.extend(ai_data["medical_alerts"])
                analysis.medical_concerns = list(set(analysis.medical_concerns))  # Remove duplicates
            
            # Update topics with AI insights
            if "wellbeing_insights" in ai_data:
                analysis.key_topics.extend(ai_data["wellbeing_insights"])
                analysis.key_topics = list(set(analysis.key_topics))[:5]  # Keep top 5
            
            return analysis
        
        except Exception as e:
            self.logger.error(f"Failed to merge AI analysis: {e}")
            return analysis
    
    async def _generate_response_recommendations(
        self, 
        analysis: ResponseAnalysis, 
        patient: Patient, 
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # High urgency recommendation
        if analysis.urgency_level in ["high", "critical"]:
            recommendations.append({
                "type": "medical_attention",
                "priority": "high",
                "description": "Paciente necessita atenção médica",
                "actions": ["contact_medical_team", "schedule_appointment"]
            })
        
        # Emotional support recommendation
        if analysis.sentiment_score < -0.5 or "anxiety" in analysis.emotion_tags:
            recommendations.append({
                "type": "emotional_support",
                "priority": "medium",
                "description": "Paciente precisa de suporte emocional",
                "actions": ["send_supportive_message", "offer_counseling"]
            })
        
        # Medical concerns recommendation
        if analysis.medical_concerns:
            recommendations.append({
                "type": "medical_follow_up",
                "priority": "medium",
                "description": f"Investigar: {', '.join(analysis.medical_concerns[:2])}",
                "actions": ["document_symptoms", "medical_review"]
            })
        
        return recommendations
    
    async def _update_patient_insights(
        self, 
        patient_id: UUID, 
        analysis: ResponseAnalysis, 
        response_text: str
    ):
        """Update patient insights in knowledge graph."""
        try:
            # Store analysis in memory for pattern recognition
            await self.coordination_hooks.store_in_memory(
                key=f"response_analysis/{patient_id}/{datetime.utcnow().isoformat()}",
                data={
                    "analysis": analysis.to_dict(),
                    "response_text": response_text,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            # Update patient emotional trends
            if analysis.sentiment_score != 0.0:
                await self.coordination_hooks.store_in_memory(
                    key=f"emotional_trends/{patient_id}/latest_sentiment",
                    data={
                        "sentiment_score": analysis.sentiment_score,
                        "emotion_tags": analysis.emotion_tags,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
        
        except Exception as e:
            self.logger.error(f"Failed to update patient insights: {e}")
    
    async def _determine_follow_up_need(
        self, 
        analysis: ResponseAnalysis, 
        patient: Patient, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Determine if and what kind of follow-up is needed."""
        follow_up = {
            "needed": analysis.requires_follow_up,
            "urgency": analysis.urgency_level,
            "type": "none",
            "suggested_timing": "24h",
            "message_type": "supportive"
        }
        
        if analysis.requires_medical_attention:
            follow_up.update({
                "type": "medical",
                "suggested_timing": "immediate",
                "message_type": "medical_attention"
            })
        elif analysis.sentiment_score < -0.5:
            follow_up.update({
                "type": "emotional_support",
                "suggested_timing": "4h",
                "message_type": "supportive"
            })
        elif analysis.response_quality == "evasive":
            follow_up.update({
                "type": "clarification",
                "suggested_timing": "2h",
                "message_type": "gentle_inquiry"
            })
        
        return follow_up
    
    def _interpret_scale_value(self, value: int, context: Dict[str, Any]) -> str:
        """Interpret scale value in context."""
        interpretations = {
            1: "Muito baixo/ruim",
            2: "Baixo/ruim", 
            3: "Médio/regular",
            4: "Alto/bom",
            5: "Muito alto/excelente"
        }
        
        return interpretations.get(value, f"Valor {value}")
    
    async def _ai_interpret_scale(self, text: str, context: Dict[str, Any]) -> Optional[int]:
        """Use AI to interpret scale response."""
        try:
            prompt = f"""
            Interprete esta resposta para uma escala de 1-5:
            
            Resposta: "{text}"
            Contexto da pergunta: {context.get('text', '')}
            
            Escala: 1=muito ruim, 2=ruim, 3=médio, 4=bom, 5=muito bom
            
            Retorne apenas o número (1-5) ou "INVALID" se não conseguir interpretar.
            """
            
            result = await self.gemini_client.generate_content(prompt)
            
            if result and result.strip().isdigit():
                value = int(result.strip())
                if 1 <= value <= 5:
                    return value
            
            return None
        
        except Exception as e:
            self.logger.error(f"AI scale interpretation failed: {e}")
            return None
    
    async def _ai_interpret_multiple_choice(
        self, 
        text: str, 
        options: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Use AI to interpret multiple choice response."""
        try:
            options_text = "\n".join([f"- {opt['value']}: {opt.get('text', '')}" for opt in options])
            
            prompt = f"""
            Interprete esta resposta e encontre a melhor opção correspondente:
            
            Resposta: "{text}"
            
            Opções disponíveis:
            {options_text}
            
            Retorne apenas o "value" da opção mais apropriada ou "INVALID".
            """
            
            result = await self.gemini_client.generate_content(prompt)
            
            if result and result.strip() != "INVALID":
                # Find matching option
                for option in options:
                    if option.get("value") == result.strip():
                        return option
            
            return None
        
        except Exception as e:
            self.logger.error(f"AI multiple choice interpretation failed: {e}")
            return None