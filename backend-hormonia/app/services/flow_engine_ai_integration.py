"""
Flow Engine AI Integration Module
Integração seletiva de IA para humanização de mensagens não-críticas
"""

from typing import Optional, Dict, Any
import logging
from app.services.ai import AIHumanizer
from app.models.patient import Patient

logger = logging.getLogger(__name__)

class FlowEngineAIIntegration:
    """
    Integração de IA no FlowEngine com controles de segurança médica.
    """

    # Mensagens CRÍTICAS que NUNCA devem ser alteradas por IA
    CRITICAL_MESSAGE_TYPES = [
        'medication_reminder',
        'dosage_instruction',
        'emergency_alert',
        'surgery_preparation',
        'chemotherapy_schedule',
        'radiation_schedule',
        'exam_preparation',
        'critical_lab_result'
    ]

    # Palavras-chave que indicam conteúdo crítico
    CRITICAL_KEYWORDS = [
        'medicação', 'medicamento', 'remédio',
        'dosagem', 'dose', 'mg', 'ml', 'mcg',
        'comprimido', 'cápsula', 'injeção',
        'emergência', 'urgente', 'imediato',
        'cirurgia', 'operação', 'procedimento',
        'quimioterapia', 'radioterapia', 'radiação',
        'exame', 'jejum', 'preparo',
        'contraindicação', 'alergia', 'reação'
    ]

    # Mensagens SEGURAS para humanização
    SAFE_MESSAGE_TYPES = [
        'welcome',
        'daily_checkin',
        'motivational',
        'educational',
        'quiz_reminder',
        'appointment_reminder',
        'thank_you',
        'feedback_request',
        'general_tips'
    ]

    def __init__(self):
        self.ai_humanizer = None
        self._initialize_ai()

    def _initialize_ai(self):
        """Inicializa o serviço de IA com tratamento de erro."""
        try:
            self.ai_humanizer = AIHumanizer()
            logger.info("AI Humanizer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI Humanizer: {e}")
            self.ai_humanizer = None

    def should_humanize_message(
        self,
        message_type: str,
        message_content: str,
        patient: Optional[Patient] = None
    ) -> bool:
        """
        Determina se uma mensagem deve ser humanizada por IA.

        Args:
            message_type: Tipo da mensagem
            message_content: Conteúdo da mensagem
            patient: Dados do paciente (opcional)

        Returns:
            True se a mensagem pode ser humanizada com segurança
        """
        # Nunca humanizar se IA não está disponível
        if not self.ai_humanizer:
            return False

        # Nunca humanizar mensagens críticas
        if message_type in self.CRITICAL_MESSAGE_TYPES:
            logger.info(f"Message type '{message_type}' is critical - skipping AI")
            return False

        # Verificar palavras-chave críticas
        content_lower = message_content.lower()
        for keyword in self.CRITICAL_KEYWORDS:
            if keyword in content_lower:
                logger.info(f"Critical keyword '{keyword}' found - skipping AI")
                return False

        # Verificar se o paciente tem restrições especiais
        if patient and hasattr(patient, 'metadata'):
            metadata = patient.metadata or {}
            if metadata.get('no_ai_messages', False):
                logger.info(f"Patient {patient.id} has AI restriction - skipping")
                return False

            # Pacientes em estado crítico não devem receber mensagens AI
            if metadata.get('critical_condition', False):
                logger.info(f"Patient {patient.id} in critical condition - skipping AI")
                return False

        # Mensagem é segura para humanização
        return message_type in self.SAFE_MESSAGE_TYPES

    async def humanize_message_safely(
        self,
        message_type: str,
        message_content: str,
        patient: Patient,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Humaniza uma mensagem de forma segura com fallback.

        Args:
            message_type: Tipo da mensagem
            message_content: Conteúdo original
            patient: Dados do paciente
            context: Contexto adicional

        Returns:
            Mensagem humanizada ou original em caso de erro
        """
        # Verificar se deve humanizar
        if not self.should_humanize_message(message_type, message_content, patient):
            return message_content

        try:
            # Importar PatientContext e config
            from app.services.ai import PatientContext
            from app.config import settings
            import asyncio

            # Construir PatientContext usando a assinatura correta do AIHumanizer
            patient_context = PatientContext(
                patient_id=str(patient.id),
                name=patient.name,
                treatment_type=getattr(patient, 'treatment_type', 'general'),
                treatment_day=getattr(patient, 'current_day', 1),
                age=getattr(patient, 'age', None),
                recent_responses=[],  # Pode ser populado do histórico se disponível
                medical_history={},
                preferences={}
            )

            # Usar timeout da configuração global
            timeout = settings.AI_HUMANIZATION_TIMEOUT

            # Humanizar usando a assinatura correta do AIHumanizer
            humanized_response = await asyncio.wait_for(
                self.ai_humanizer.humanize_message(
                    template_message=message_content,
                    patient_context=patient_context,
                    message_type=message_type
                ),
                timeout=timeout
            )

            # Extrair mensagem humanizada da resposta
            humanized = humanized_response.humanized_message if hasattr(humanized_response, 'humanized_message') else str(humanized_response)

            # Validação final - garantir que não alterou conteúdo crítico
            if self._contains_critical_content(humanized):
                logger.warning("AI output contains critical content - using original")
                return message_content

            logger.info(f"Message successfully humanized for patient {patient.id}")
            return humanized

        except asyncio.TimeoutError:
            logger.error("AI humanization timeout - using original message")
            return message_content
        except Exception as e:
            logger.error(f"AI humanization failed: {e} - using original message")
            return message_content

    def _contains_critical_content(self, message: str) -> bool:
        """Verifica se a mensagem contém conteúdo crítico após processamento."""
        message_lower = message.lower()
        for keyword in self.CRITICAL_KEYWORDS:
            if keyword in message_lower:
                return True
        return False

    def get_humanization_metrics(self) -> Dict[str, Any]:
        """Retorna métricas de humanização para monitoramento."""
        return {
            'ai_available': self.ai_humanizer is not None,
            'critical_types_count': len(self.CRITICAL_MESSAGE_TYPES),
            'safe_types_count': len(self.SAFE_MESSAGE_TYPES),
            'critical_keywords_count': len(self.CRITICAL_KEYWORDS)
        }


# Integração com FlowEngine existente
def integrate_ai_into_flow_engine():
    """
    Patch para integrar IA no FlowEngine existente.
    Deve ser chamado durante inicialização do sistema.
    """
    from app.services.flow_engine import FlowEngine

    # Criar instância do integrador
    ai_integration = FlowEngineAIIntegration()

    # Salvar método original
    original_schedule_step = FlowEngine._schedule_step

    async def enhanced_schedule_step(self, flow_state, step, delay_minutes=0):
        """Versão aprimorada com IA do _schedule_step."""

        # Obter conteúdo original
        if step.type == 'message':
            message_content = step.content
            message_type = step.metadata.get('type', 'general') if hasattr(step, 'metadata') else 'general'

            # Buscar dados do paciente
            patient = self.db.query(Patient).filter(
                Patient.id == flow_state.patient_id
            ).first()

            if patient:
                # Tentar humanizar se apropriado
                humanized_content = await ai_integration.humanize_message_safely(
                    message_type=message_type,
                    message_content=message_content,
                    patient=patient,
                    context={'flow_state': flow_state}
                )

                # Atualizar step com conteúdo humanizado
                step.content = humanized_content

        # Chamar método original com conteúdo possivelmente humanizado
        return await original_schedule_step(self, flow_state, step, delay_minutes)

    # Aplicar patch
    FlowEngine._schedule_step = enhanced_schedule_step

    logger.info("AI integration successfully patched into FlowEngine")
    return ai_integration


# Uso em produção
if __name__ == "__main__":
    # Exemplo de ativação
    integration = integrate_ai_into_flow_engine()
    metrics = integration.get_humanization_metrics()
    print(f"AI Integration Status: {metrics}")