"""
Portuguese message templates for the reminder system.
"""

from typing import Optional

from .models import DurationInfo


def build_reminder_content(patient_name: str, reminder_text: str) -> str:
    """Build the reminder message content."""
    name = patient_name or ""
    text = reminder_text.strip()
    return f"Oi {name}! Lembrete combinado: {text}"


def format_duration_phrase(duration_info: DurationInfo) -> Optional[str]:
    """Format duration info as a Portuguese phrase."""
    if duration_info.occurrences:
        return f"por {duration_info.occurrences} vezes"
    if duration_info.days:
        return f"por {duration_info.days} dias"
    if duration_info.weeks:
        return f"por {duration_info.weeks} semanas"
    if duration_info.months:
        return f"por {duration_info.months} meses"
    if duration_info.end_date:
        return f"ate {duration_info.end_date}"
    return None


def build_confirmation_message(
    recurrence: str, interval_days: Optional[int], duration_info: DurationInfo
) -> str:
    """Build the confirmation message for a scheduled reminder."""
    duration_phrase = format_duration_phrase(duration_info)

    if recurrence == "daily":
        base = "Combinado! Vou te lembrar todos os dias nesse horario."
        return f"{base} Vou manter {duration_phrase}." if duration_phrase else base
    if recurrence == "weekly":
        base = "Combinado! Vou te lembrar toda semana nesse horario."
        return f"{base} Vou manter {duration_phrase}." if duration_phrase else base
    if recurrence == "monthly":
        base = "Combinado! Vou te lembrar todo mes nesse horario."
        return f"{base} Vou manter {duration_phrase}." if duration_phrase else base
    if recurrence == "interval" and interval_days:
        base = f"Combinado! Vou te lembrar a cada {interval_days} dias nesse horario."
        return f"{base} Vou manter {duration_phrase}." if duration_phrase else base

    base = "Combinado! Vou te lembrar no horario combinado."
    return f"{base} Vou manter {duration_phrase}." if duration_phrase else base


def build_clarification_message(
    missing_text: bool,
    missing_time: bool,
    missing_interval: bool,
    missing_duration: bool,
) -> str:
    """Build a clarification request message based on missing fields."""
    if missing_text and missing_time:
        return "Claro! O que voce quer que eu lembre e em qual horario?"
    if missing_text:
        return "Qual lembrete voce quer que eu guarde?"
    if missing_time and missing_interval and missing_duration:
        return "Qual horario, a cada quantos dias e por quanto tempo?"
    if missing_time and missing_duration:
        return "Qual horario e por quanto tempo devo repetir esse lembrete?"
    if missing_time and missing_interval:
        return "Qual horario e a cada quantos dias devo lembrar?"
    if missing_interval and missing_duration:
        return "A cada quantos dias devo lembrar e por quanto tempo?"
    if missing_time:
        return "Que horario voce prefere receber esse lembrete?"
    if missing_interval:
        return "A cada quantos dias voce quer receber esse lembrete?"
    if missing_duration:
        return "Por quanto tempo devo repetir esse lembrete?"
    return "Pode me passar mais detalhes do lembrete?"


def build_limit_message(limit: int) -> str:
    """Build message when patient has reached reminder limit."""
    return f"Hoje voce ja tem {limit} lembretes ativos. Quer que eu cancele algum para criar outro?"
