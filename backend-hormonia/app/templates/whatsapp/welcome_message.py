"""
Welcome message template for new patient registration.

This template is sent automatically when a patient is registered in the system
to introduce them to the clinic's WhatsApp-based monitoring system.
"""
from typing import Optional


def get_welcome_message(
    patient_name: str,
    clinic_name: str = "Neoplasias Litoral",
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

Eu sou a Hormonia, sua IA de cuidado da {clinic_name}. Vou te acompanhar com carinho nesta jornada. 💜

📱 *O que você pode esperar por aqui:*
• Mensagens de acompanhamento personalizadas
• Lembretes de medicação e consultas
• Questionários mensais de bem‑estar
• Orientações úteis sobre seu tratamento
• Dicas de autocuidado e motivação

💬 *Conte comigo sempre!*
Pode me mandar mensagem quando quiser com dúvidas, preocupações ou sintomas. Se eu não souber, nossa equipe entra para te apoiar.
"""

    # Add support phone if provided
    if support_phone:
        message += f"\n📞 *Em caso de emergência:*\nLigue para {support_phone}\n"

    # Closing
    message += f"""
🏥 *Estamos juntos nessa!* 
Sua saúde e bem-estar são nossa prioridade.

— Hormonia (IA), em parceria com a equipe {clinic_name}
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

Eu sou a Hormonia, sua IA de cuidado da Neoplasias Litoral.
Vou te enviar lembretes, acompanhamentos e orientações por aqui.

💬 Me chama quando precisar.

— Hormonia (IA) • Neoplasias Litoral
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
    message = f"""✅ *Cadastro confirmado*

Olá {patient_name}!

Eu sou a Hormonia (IA). Seu cadastro foi concluído com sucesso e vamos começar seu acompanhamento por aqui.

👨‍⚕️ *Médico responsável:* Dr(a). {doctor_name}
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
