"""
Message Templates - Monthly Quiz Message Templates (QW-022).

This module contains message template constants used by MessageFactory.
"""

from typing import Dict


class MessageTemplates:
    """Container for message template strings."""

    # Message templates for monthly quiz links
    MONTHLY_QUIZ_TEMPLATES: Dict[str, str] = {
        "invitation": (
            "Olá {patient_name}! 😊\n\n"
            "Chegou o momento do seu questionário mensal de bem-estar!\n\n"
            "Acesse pelo link: {link}\n\n"
            "➡️ Válido por {expiry_hours} horas\n\n"
            "Sua participação é muito importante para acompanharmos seu progresso."
        ),
        "reminder": (
            "Oi {patient_name}! 💬\n\n"
            "Lembrete: você ainda não respondeu ao questionário mensal.\n\n"
            "Por favor, acesse: {link}\n\n"
            "⏳ Expira em {hours_remaining} horas\n\n"
            "Contamos com você!"
        ),
        "expired": (
            "Olá {patient_name}! ⏰\n\n"
            "O link do seu questionário expirou.\n\n"
            "Um novo link será enviado em breve. Fique atenta(o)!"
        ),
        "completed": (
            "Obrigada, {patient_name}! 🙌\n\n"
            "Recebemos suas respostas do questionário mensal.\n\n"
            "Nossa equipe médica irá analisá-las em breve.\n\n"
            "Continue cuidando bem da sua saúde! 🌷"
        ),
    }
