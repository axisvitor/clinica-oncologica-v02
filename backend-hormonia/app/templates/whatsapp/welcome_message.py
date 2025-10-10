"""
Welcome message template for new patient registration.

This template is sent automatically when a patient is registered in the system
to introduce them to the clinic's WhatsApp-based monitoring system.
"""
from typing import Optional


def get_welcome_message(
    patient_name: str,
    clinic_name: str = "Clínica Oncológica Hormonia",
    support_phone: Optional[str] = None
) -> str:
    """
    Generate personalized welcome message for new patients.

    Args:
        patient_name: The patient's name for personalization
        clinic_name: Name of the clinic (default: "Clínica Oncológica Hormonia")
        support_phone: Optional support phone number for emergencies

    Returns:
        Formatted welcome message string ready to send via WhatsApp

    Example:
        >>> message = get_welcome_message("Maria Silva", support_phone="+5511999999999")
    """

    # Base welcome message
    message = f"""Olá {patient_name}! 👋

Seja bem-vindo(a) à {clinic_name}!

Estamos muito felizes em tê-lo(a) conosco nesta jornada de cuidado e tratamento oncológico.

📱 *O que esperar deste canal:*
• Mensagens de acompanhamento diárias
• Lembretes de medicação e consultas
• Questionários mensais de avaliação
• Orientações educacionais sobre seu tratamento
• Dicas de bem-estar e autocuidado

💬 *Você pode sempre contar conosco!*
Responda a qualquer momento com suas dúvidas, preocupações ou sintomas. Nossa equipe médica está disponível para auxiliá-lo(a).
"""

    # Add support phone if provided
    if support_phone:
        message += f"\n📞 *Em caso de emergência:*\nLigue para {support_phone}\n"

    # Closing
    message += f"""
🏥 *Juntos nessa jornada!*
Sua saúde e bem-estar são nossa prioridade.

_Equipe {clinic_name}_
"""

    return message.strip()


def get_welcome_message_brief(patient_name: str) -> str:
    """
    Generate a brief welcome message for patients who prefer shorter messages.

    Args:
        patient_name: The patient's name for personalization

    Returns:
        Brief welcome message string
    """
    return f"""Olá {patient_name}! 👋

Bem-vindo(a) à Clínica Oncológica Hormonia!

Você receberá mensagens de acompanhamento, lembretes e orientações sobre seu tratamento por este canal.

💬 Responda a qualquer momento se precisar de ajuda.

_Equipe Hormonia_
""".strip()


def get_registration_confirmation(
    patient_name: str,
    doctor_name: str,
    treatment_type: Optional[str] = None
) -> str:
    """
    Generate registration confirmation message with treatment details.

    Args:
        patient_name: Patient's name
        doctor_name: Assigned doctor's name
        treatment_type: Type of treatment (e.g., "hormonioterapia", "quimioterapia")

    Returns:
        Registration confirmation message
    """
    message = f"""✅ *Cadastro Confirmado*

Olá {patient_name}!

Seu cadastro foi realizado com sucesso.

👨‍⚕️ *Médico Responsável:* Dr(a). {doctor_name}
"""

    if treatment_type:
        # Translate treatment type to Portuguese if needed
        treatment_names = {
            "hormone_therapy": "Hormonioterapia",
            "chemotherapy": "Quimioterapia",
            "radiotherapy": "Radioterapia",
            "immunotherapy": "Imunoterapia"
        }
        treatment_display = treatment_names.get(treatment_type, treatment_type)
        message += f"💊 *Tratamento:* {treatment_display}\n"

    message += """
Em breve você começará a receber mensagens de acompanhamento.

_Equipe Hormonia_
"""

    return message.strip()
