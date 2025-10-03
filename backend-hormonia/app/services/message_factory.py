"""
Message Factory Service
Centralizes message creation patterns to eliminate code duplication.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.quiz import QuizTemplate
from app.schemas.quiz import QuizQuestion


class MessageTemplate(Enum):
    """Pre-defined message templates"""
    QUIZ_INTRODUCTION = "quiz_introduction"
    QUIZ_QUESTION = "quiz_question"
    QUIZ_COMPLETION = "quiz_completion"
    QUIZ_CLARIFICATION = "quiz_clarification"
    QUIZ_PAUSED = "quiz_paused"
    FLOW_MESSAGE = "flow_message"
    ALERT_MESSAGE = "alert_message"
    REMINDER = "reminder"
    FOLLOW_UP = "follow_up"
    # Monthly quiz link templates
    MONTHLY_QUIZ_LINK_INVITATION = "monthly_quiz_link_invitation"
    MONTHLY_QUIZ_LINK_REMINDER = "monthly_quiz_link_reminder"
    MONTHLY_QUIZ_LINK_EXPIRED = "monthly_quiz_link_expired"
    MONTHLY_QUIZ_LINK_COMPLETED = "monthly_quiz_link_completed"


class MessageFactory:
    """
    Factory class for creating standardized messages.
    Eliminates code duplication across services.
    """
    
    def __init__(self, db: Session):
        """
        Initialize MessageFactory.

        Args:
            db: Database session
        """
        self.db = db

        # Message templates for monthly quiz links
        self.monthly_quiz_templates = {
            'invitation': "Olá {patient_name}! 🌸\n\nChegou o momento do seu questionário mensal de bem-estar! 📋\n\nAcesse através do link: {link}\n\n⏰ Válido por {expiry_hours} horas\n\nSua participação é muito importante para acompanharmos seu progresso.",
            'reminder': "Oi {patient_name}! ⏰\n\nLembrete: você ainda não respondeu ao questionário mensal.\n\nPor favor, acesse: {link}\n\n⚠️ Expira em {hours_remaining} horas\n\nContamos com você!",
            'expired': "Olá {patient_name}! 😔\n\nO link do seu questionário expirou.\n\nUm novo link será enviado em breve. Fique atento!",
            'completed': "Obrigado {patient_name}! 🎉\n\nRecebemos suas respostas do questionário mensal.\n\nNossa equipe médica irá analisá-las em breve.\n\nContinue cuidando bem da sua saúde! 💪"
        }
    
    def create_outbound_message(
        self,
        patient_id: UUID,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
        scheduled_for: Optional[datetime] = None,
        template_type: Optional[MessageTemplate] = None
    ) -> Message:
        """
        Create standardized outbound message.
        
        Args:
            patient_id: Patient UUID
            content: Message content
            message_type: Type of message
            metadata: Optional metadata
            scheduled_for: Schedule time
            template_type: Optional template type for tracking
            
        Returns:
            Created Message object
        """
        message = Message(
            patient_id=patient_id,
            direction=MessageDirection.OUTBOUND,
            type=message_type,
            content=content,
            message_metadata=self._enrich_metadata(metadata, template_type),
            status=MessageStatus.PENDING,
            scheduled_for=scheduled_for or datetime.utcnow()
        )
        
        return self._save_message(message)
    
    def create_quiz_message(
        self,
        patient_id: UUID,
        question: Dict[str, Any],
        session_id: str,
        question_index: int,
        total_questions: int,
        patient_name: Optional[str] = None
    ) -> Message:
        """
        Create specialized quiz question message.
        
        Args:
            patient_id: Patient UUID
            question: Question data
            session_id: Quiz session ID
            question_index: Current question index
            total_questions: Total number of questions
            patient_name: Optional patient name for personalization
            
        Returns:
            Created Message object
        """
        content = self._format_quiz_question(
            question, 
            question_index, 
            total_questions,
            patient_name
        )
        
        metadata = {
            "quiz_session_id": session_id,
            "quiz_question_index": question_index,
            "quiz_question_id": question.get('id'),
            "message_type": "quiz_question",
            "template_type": MessageTemplate.QUIZ_QUESTION.value
        }
        
        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            metadata=metadata,
            template_type=MessageTemplate.QUIZ_QUESTION
        )
    
    def create_quiz_introduction(
        self,
        patient_id: UUID,
        patient_name: str,
        session_id: str,
        first_question: Dict[str, Any],
        total_questions: int = 5
    ) -> Message:
        """
        Create quiz introduction message.
        
        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            session_id: Quiz session ID
            first_question: First question data
            total_questions: Total number of questions
            
        Returns:
            Created Message object
        """
        content = f"""Olá {patient_name}! 🌸

É hora do seu check-up mensal! Preparei algumas perguntas importantes para acompanhar como você está se sentindo.

São apenas {total_questions} perguntas rápidas que me ajudam a entender melhor seu progresso e bem-estar. Vamos começar?

*Pergunta 1 de {total_questions}:*
{first_question.get('text', '')}"""
        
        # Add options if available
        if first_question.get('options'):
            content += "\n\n*Opções:*\n"
            for option in first_question['options']:
                content += f"• {option.get('text', '')}\n"
        
        metadata = {
            "quiz_session_id": session_id,
            "quiz_question_index": 0,
            "quiz_question_id": first_question.get('id'),
            "message_type": "quiz_introduction",
            "template_type": MessageTemplate.QUIZ_INTRODUCTION.value
        }
        
        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            metadata=metadata,
            template_type=MessageTemplate.QUIZ_INTRODUCTION
        )
    
    def create_quiz_completion(
        self,
        patient_id: UUID,
        patient_name: str,
        session_id: str
    ) -> Message:
        """
        Create quiz completion message.
        
        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            session_id: Quiz session ID
            
        Returns:
            Created Message object
        """
        content = f"""Parabéns {patient_name}! 🎉

Você completou seu check-up mensal. Suas respostas foram registradas e nossa equipe médica irá analisá-las.

Obrigada por dedicar esse tempo para cuidar da sua saúde. Continue assim! 💪

Se tiver alguma dúvida ou preocupação, não hesite em me procurar."""
        
        metadata = {
            "quiz_session_id": session_id,
            "message_type": "quiz_completion",
            "template_type": MessageTemplate.QUIZ_COMPLETION.value
        }
        
        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            metadata=metadata,
            template_type=MessageTemplate.QUIZ_COMPLETION
        )
    
    def create_quiz_clarification(
        self,
        patient_id: UUID,
        patient_name: str,
        question: Dict[str, Any],
        error_message: str
    ) -> Message:
        """
        Create quiz clarification message for invalid responses.
        
        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            question: Question data
            error_message: Error description
            
        Returns:
            Created Message object
        """
        content = f"""Desculpe {patient_name}, não consegui entender sua resposta.

{error_message}

*Pergunta:* {question.get('text', '')}"""
        
        # Add options if available
        if question.get('options'):
            content += "\n\n*Opções:*\n"
            for option in question['options']:
                content += f"• {option.get('text', '')}\n"
        
        metadata = {
            "message_type": "quiz_clarification",
            "question_id": question.get('id'),
            "template_type": MessageTemplate.QUIZ_CLARIFICATION.value
        }
        
        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            metadata=metadata,
            template_type=MessageTemplate.QUIZ_CLARIFICATION
        )
    
    def create_quiz_pause(
        self,
        patient_id: UUID,
        patient_name: str,
        session_id: str
    ) -> Message:
        """
        Create quiz pause message.
        
        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            session_id: Quiz session ID
            
        Returns:
            Created Message object
        """
        content = f"""Quiz pausado, {patient_name}! ⏸️

Você pode retomar quando quiser. Suas respostas anteriores foram salvas.

Para continuar, basta me enviar uma mensagem."""
        
        metadata = {
            "quiz_session_id": session_id,
            "message_type": "quiz_paused",
            "template_type": MessageTemplate.QUIZ_PAUSED.value
        }
        
        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            metadata=metadata,
            template_type=MessageTemplate.QUIZ_PAUSED
        )
    
    def create_flow_message(
        self,
        patient_id: UUID,
        content: str,
        flow_type: str,
        flow_step: int,
        metadata: Optional[Dict[str, Any]] = None,
        scheduled_for: Optional[datetime] = None
    ) -> Message:
        """
        Create flow-related message.
        
        Args:
            patient_id: Patient UUID
            content: Message content
            flow_type: Type of flow
            flow_step: Current flow step
            metadata: Additional metadata
            scheduled_for: Schedule time
            
        Returns:
            Created Message object
        """
        flow_metadata = {
            "flow_type": flow_type,
            "flow_step": flow_step,
            "message_type": "flow_message",
            "template_type": MessageTemplate.FLOW_MESSAGE.value
        }
        
        if metadata:
            flow_metadata.update(metadata)
        
        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            metadata=flow_metadata,
            scheduled_for=scheduled_for,
            template_type=MessageTemplate.FLOW_MESSAGE
        )
    
    def create_batch_messages(
        self,
        messages_data: List[Dict[str, Any]]
    ) -> List[Message]:
        """
        Create multiple messages in batch.
        
        Args:
            messages_data: List of message data dictionaries
            
        Returns:
            List of created Message objects
        """
        messages = []
        
        for data in messages_data:
            message_type = data.get('template_type', MessageTemplate.FLOW_MESSAGE)
            
            if message_type == MessageTemplate.QUIZ_QUESTION:
                message = self.create_quiz_message(**data)
            elif message_type == MessageTemplate.QUIZ_INTRODUCTION:
                message = self.create_quiz_introduction(**data)
            elif message_type == MessageTemplate.QUIZ_COMPLETION:
                message = self.create_quiz_completion(**data)
            else:
                message = self.create_outbound_message(**data)
            
            messages.append(message)
        
        return messages
    
    def _format_quiz_question(
        self,
        question: Dict[str, Any],
        question_index: int,
        total_questions: int,
        patient_name: Optional[str] = None
    ) -> str:
        """
        Format quiz question for display.
        
        Args:
            question: Question data
            question_index: Current question index
            total_questions: Total questions
            patient_name: Optional patient name
            
        Returns:
            Formatted question text
        """
        content = f"*Pergunta {question_index + 1} de {total_questions}:*\n\n"
        content += question.get('text', '')
        
        # Add options if available
        if question.get('options'):
            content += "\n\n*Opções:*\n"
            for option in question['options']:
                content += f"• {option.get('text', '')}\n"
        
        return content
    
    def _enrich_metadata(
        self,
        metadata: Optional[Dict[str, Any]],
        template_type: Optional[MessageTemplate]
    ) -> Dict[str, Any]:
        """
        Enrich metadata with standard fields.
        
        Args:
            metadata: Original metadata
            template_type: Template type
            
        Returns:
            Enriched metadata
        """
        enriched = metadata or {}
        
        # Add standard fields
        enriched['created_at'] = datetime.utcnow().isoformat()
        enriched['factory_version'] = '1.0.0'
        
        if template_type:
            enriched['template_type'] = template_type.value
        
        return enriched
    
    def create_monthly_quiz_link_message(
        self,
        patient_id: UUID,
        patient_name: str,
        link_url: str,
        quiz_session_id: str,
        expiry_hours: int = 72,
        delivery_method: str = "whatsapp",
        custom_message: Optional[str] = None
    ) -> Message:
        """
        Create monthly quiz link invitation message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name for personalization
            link_url: Quiz access link
            quiz_session_id: Quiz session ID
            expiry_hours: Link expiry in hours
            delivery_method: Delivery channel (whatsapp, email, sms)
            custom_message: Optional custom message override

        Returns:
            Created Message object
        """
        # Use custom message or default template
        if custom_message:
            content = custom_message.format(
                patient_name=patient_name,
                link=link_url,
                expiry_hours=expiry_hours
            )
        else:
            content = self.monthly_quiz_templates['invitation'].format(
                patient_name=patient_name,
                link=link_url,
                expiry_hours=expiry_hours
            )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": "monthly_quiz_link",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_INVITATION.value,
            "link_url": link_url,
            "expiry_hours": expiry_hours,
            "delivery_method": delivery_method,
            "link_metadata": {
                "is_clickable": True,
                "requires_token": True
            }
        }

        message_type = MessageType.TEXT
        if delivery_method == "whatsapp":
            # WhatsApp automatically makes URLs clickable
            message_type = MessageType.MONTHLY_QUIZ_LINK

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=message_type,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_INVITATION
        )

    def create_monthly_quiz_reminder_message(
        self,
        patient_id: UUID,
        patient_name: str,
        link_url: str,
        quiz_session_id: str,
        hours_remaining: int,
        delivery_method: str = "whatsapp"
    ) -> Message:
        """
        Create monthly quiz reminder message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            link_url: Quiz access link
            quiz_session_id: Quiz session ID
            hours_remaining: Hours until expiration
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        content = self.monthly_quiz_templates['reminder'].format(
            patient_name=patient_name,
            link=link_url,
            hours_remaining=hours_remaining
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": "monthly_quiz_reminder",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER.value,
            "link_url": link_url,
            "hours_remaining": hours_remaining,
            "delivery_method": delivery_method,
            "reminder_type": "expiration_warning"
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_REMINDER,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER
        )

    def create_monthly_quiz_expired_message(
        self,
        patient_id: UUID,
        patient_name: str,
        quiz_session_id: str,
        delivery_method: str = "whatsapp"
    ) -> Message:
        """
        Create monthly quiz link expired message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            quiz_session_id: Quiz session ID
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        content = self.monthly_quiz_templates['expired'].format(
            patient_name=patient_name
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": "monthly_quiz_expired",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_EXPIRED.value,
            "delivery_method": delivery_method
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_EXPIRED,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_EXPIRED
        )

    def create_monthly_quiz_completed_message(
        self,
        patient_id: UUID,
        patient_name: str,
        quiz_session_id: str,
        delivery_method: str = "whatsapp"
    ) -> Message:
        """
        Create monthly quiz completion confirmation message.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            quiz_session_id: Quiz session ID
            delivery_method: Delivery channel

        Returns:
            Created Message object
        """
        content = self.monthly_quiz_templates['completed'].format(
            patient_name=patient_name
        )

        metadata = {
            "quiz_session_id": quiz_session_id,
            "message_type": "monthly_quiz_completed",
            "template_type": MessageTemplate.MONTHLY_QUIZ_LINK_COMPLETED.value,
            "delivery_method": delivery_method
        }

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_COMPLETED,
            metadata=metadata,
            template_type=MessageTemplate.MONTHLY_QUIZ_LINK_COMPLETED
        )

    def create_multi_channel_message(
        self,
        patient_id: UUID,
        content: str,
        channels: List[str],
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Message]:
        """
        Create message for multiple delivery channels.

        Args:
            patient_id: Patient UUID
            content: Message content
            channels: List of delivery channels (whatsapp, email, sms)
            message_type: Type of message
            metadata: Optional metadata

        Returns:
            List of created Message objects (one per channel)
        """
        messages = []

        for channel in channels:
            channel_metadata = metadata.copy() if metadata else {}
            channel_metadata['delivery_method'] = channel

            # Adapt content for channel if needed
            adapted_content = content
            if channel == "sms":
                # Truncate for SMS (160 chars)
                adapted_content = content[:157] + "..." if len(content) > 160 else content
            elif channel == "email":
                # Could wrap in HTML template for email
                channel_metadata['email_format'] = 'html'

            message = self.create_outbound_message(
                patient_id=patient_id,
                content=adapted_content,
                message_type=message_type,
                metadata=channel_metadata
            )
            messages.append(message)

        return messages

    def _save_message(self, message: Message) -> Message:
        """
        Save message to database.

        Args:
            message: Message to save

        Returns:
            Saved Message object
        """
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message


def get_message_factory(db: Session) -> MessageFactory:
    """
    Get MessageFactory instance.
    
    Args:
        db: Database session
        
    Returns:
        MessageFactory instance
    """
    return MessageFactory(db)