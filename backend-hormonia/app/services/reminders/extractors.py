"""
Intent extraction for reminders - AI and rule-based approaches.
"""

import json
import logging
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.integrations.gemini_client import GeminiClient
from app.utils.timezone import SAO_PAULO_TZ_NAME

from .models import DurationInfo, ReminderIntent
from .patterns import (
    RE_DATE_DAY,
    RE_DATE_DMY,
    RE_DURATION_DAYS,
    RE_DURATION_END_DATE,
    RE_DURATION_MONTHS,
    RE_DURATION_OCCURRENCES,
    RE_DURATION_WEEKS,
    RE_INTERVAL_DAYS,
    RE_JSON,
    RE_NO,
    RE_REMINDER_CUTOFF,
    RE_REMINDER_TEXT,
    RE_REMINDER_TIME_CUTOFF,
    RE_TIME_HHMM,
    RE_WEEKDAY_EVERY,
    RE_WHITESPACE,
    RE_YES,
    REMINDER_KEYWORDS,
    SAO_PAULO_PYTZ_TZ,
    TIME_PATTERNS,
    WEEKDAY_ALIASES,
)

logger = logging.getLogger(__name__)


# ---- Utilities ----


def safe_int(value: Any) -> Optional[int]:
    """Safely convert value to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any, default: float) -> float:
    """Safely convert value to float with default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_text(text: Optional[str]) -> str:
    """Normalize text: remove accents, lowercase, strip whitespace."""
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = RE_WHITESPACE.sub(" ", normalized).strip().lower()
    return normalized


def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from AI response."""
    if not response:
        return None
    try:
        match = RE_JSON.search(response)
        if not match:
            return None
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def clean_optional_text(value: Any) -> Optional[str]:
    """Clean optional text value."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def clean_date_local(value: Any) -> Optional[str]:
    """Clean and validate date string."""
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return None


def clean_time(value: Any) -> Optional[str]:
    """Clean and validate time string."""
    if not value:
        return None
    value = str(value).strip()
    match = RE_TIME_HHMM.match(value)
    if not match:
        return None
    hour = safe_int(match.group(1))
    minute = safe_int(match.group(2))
    if hour is None or minute is None:
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def parse_date_parts(
    day: Optional[int],
    month: Optional[int],
    year: Optional[int],
    now_local: datetime,
) -> Optional[str]:
    """Parse day/month/year into ISO date string."""
    from datetime import date as date_type
    
    if not day or not month:
        return None
    year = year or now_local.year
    if year < 100:
        year += 2000
    try:
        return date_type(year, month, day).isoformat()
    except ValueError:
        return None


# ---- Extraction Functions ----


def last_message_mentions_reminder(message: Optional[str]) -> bool:
    """Check if message mentions reminder keywords."""
    if not message:
        return False
    normalized = normalize_text(message)
    return any(keyword in normalized for keyword in REMINDER_KEYWORDS)


def infer_reminder_text(message: Optional[str]) -> Optional[str]:
    """Infer reminder text from context keywords."""
    if not message:
        return None
    normalized = normalize_text(message)
    if "medic" in normalized or "remedio" in normalized:
        return "sua medicacao"
    if "exame" in normalized:
        return "seus exames"
    if "consulta" in normalized:
        return "sua consulta"
    if "data" in normalized:
        return "uma data importante"
    return None


def extract_time_local(text: str, *, normalized: Optional[str] = None) -> Optional[str]:
    """Extract time from text (HH:MM format)."""
    normalized = normalized if normalized is not None else normalize_text(text)
    for pattern in TIME_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        hour = safe_int(match.group(1))
        minute = safe_int(match.group(2)) if match.lastindex and match.lastindex >= 2 else 0
        if hour is None or minute is None:
            continue
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    return None


def extract_date_local(
    text: str,
    now_local: datetime,
    *,
    normalized: Optional[str] = None,
) -> Optional[str]:
    """Extract date from text (ISO format)."""
    normalized = normalized if normalized is not None else normalize_text(text)

    if "depois de amanha" in normalized:
        return (now_local.date() + timedelta(days=2)).isoformat()
    if "amanha" in normalized:
        return (now_local.date() + timedelta(days=1)).isoformat()
    if "hoje" in normalized:
        return now_local.date().isoformat()

    date_match = RE_DATE_DMY.search(normalized)
    if date_match:
        day = safe_int(date_match.group(1))
        month = safe_int(date_match.group(2))
        year = safe_int(date_match.group(3)) if date_match.group(3) else now_local.year
        return parse_date_parts(day, month, year, now_local)

    day_match = RE_DATE_DAY.search(normalized)
    if day_match:
        day = safe_int(day_match.group(1))
        if day:
            month = now_local.month
            year = now_local.year
            if day < now_local.day:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            return parse_date_parts(day, month, year, now_local)

    for name in WEEKDAY_ALIASES:
        if name in normalized:
            return None

    return None


def extract_recurrence(
    text: str,
    *,
    normalized: Optional[str] = None,
) -> Tuple[str, Optional[int], Optional[int]]:
    """Extract recurrence pattern from text."""
    normalized = normalized if normalized is not None else normalize_text(text)
    weekday = None
    recurrence = "none"
    interval_days = None

    interval_match = RE_INTERVAL_DAYS.search(normalized)
    if interval_match:
        interval_days = safe_int(interval_match.group(1))
        if interval_days:
            recurrence = "interval"

    weekday_match = RE_WEEKDAY_EVERY.search(normalized)
    if weekday_match:
        weekday_name = weekday_match.group(1)
        weekday_name = weekday_name.replace("-feira", "")
        if weekday_name in WEEKDAY_ALIASES:
            weekday = WEEKDAY_ALIASES[weekday_name]
            recurrence = "weekly"

    if "todo dia" in normalized or "todos os dias" in normalized or "diari" in normalized:
        recurrence = "daily"
    elif "toda semana" in normalized or "semanal" in normalized:
        recurrence = "weekly"
    elif "todo mes" in normalized or "mensal" in normalized:
        recurrence = "monthly"

    return recurrence, weekday, interval_days


def extract_interval_days(
    text: str,
    *,
    normalized: Optional[str] = None,
) -> Optional[int]:
    """Extract interval days for recurrence like 'a cada X dias'."""
    normalized = normalized if normalized is not None else normalize_text(text)
    interval_match = RE_INTERVAL_DAYS.search(normalized)
    if not interval_match:
        return None
    interval_days = safe_int(interval_match.group(1))
    if interval_days and interval_days > 0:
        return interval_days
    return None


def extract_duration_info(
    text: str,
    now_local: datetime,
    *,
    normalized: Optional[str] = None,
) -> DurationInfo:
    """Extract duration information from text."""
    normalized = normalized if normalized is not None else normalize_text(text)
    duration_info = DurationInfo()

    occurrences_match = RE_DURATION_OCCURRENCES.search(normalized)
    if occurrences_match:
        duration_info.occurrences = safe_int(occurrences_match.group(1))

    days_match = RE_DURATION_DAYS.search(normalized)
    if days_match:
        duration_info.days = safe_int(days_match.group(1))

    weeks_match = RE_DURATION_WEEKS.search(normalized)
    if weeks_match:
        duration_info.weeks = safe_int(weeks_match.group(1))

    months_match = RE_DURATION_MONTHS.search(normalized)
    if months_match:
        duration_info.months = safe_int(months_match.group(1))

    end_match = RE_DURATION_END_DATE.search(normalized)
    if end_match:
        day = safe_int(end_match.group(1))
        month = safe_int(end_match.group(2))
        year = safe_int(end_match.group(3)) if end_match.group(3) else now_local.year
        duration_info.end_date = parse_date_parts(day, month, year, now_local)

    # Validate positive values
    if duration_info.occurrences and duration_info.occurrences <= 0:
        duration_info.occurrences = None
    if duration_info.days and duration_info.days <= 0:
        duration_info.days = None
    if duration_info.weeks and duration_info.weeks <= 0:
        duration_info.weeks = None
    if duration_info.months and duration_info.months <= 0:
        duration_info.months = None

    return duration_info


def extract_reminder_text(text: str) -> Optional[str]:
    """Extract the reminder subject from text."""
    match = RE_REMINDER_TEXT.search(text)
    if not match:
        return None
    reminder_text = match.group(1).strip()
    reminder_text = RE_REMINDER_CUTOFF.sub("", reminder_text).strip()
    reminder_text = RE_REMINDER_TIME_CUTOFF.sub("", reminder_text).strip()
    reminder_text = reminder_text.strip(" .,!?:;")
    return reminder_text or None


def get_missing_fields(
    reminder_text: Optional[str],
    time_local: Optional[str],
    recurrence: str,
    interval_days: Optional[int],
    duration_info: DurationInfo,
) -> Tuple[bool, bool, bool, bool]:
    """Determine which fields are missing."""
    missing_text = not reminder_text
    missing_time = not time_local
    missing_interval = recurrence == "interval" and not interval_days
    missing_duration = recurrence != "none" and not duration_info.has_value()
    return missing_text, missing_time, missing_interval, missing_duration


def infer_recurrence_from_duration(duration_info: DurationInfo) -> str:
    """Infer recurrence type from duration info."""
    if duration_info.months:
        return "monthly"
    if duration_info.weeks:
        return "weekly"
    if duration_info.days or duration_info.occurrences:
        return "daily"
    return "none"


# ---- Main Extractors ----


async def extract_intent(
    gemini_client: Optional[GeminiClient],
    message_text: str,
    last_outbound: Optional[str],
    pending: Optional[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]],
    timezone_name: Optional[str],
    local_now: Optional[datetime],
) -> ReminderIntent:
    """Extract reminder intent from message, using AI if available."""
    if gemini_client:
        try:
            ai_intent = await extract_intent_ai(
                gemini_client=gemini_client,
                message_text=message_text,
                last_outbound=last_outbound,
                pending=pending,
                conversation_history=conversation_history,
                timezone_name=timezone_name,
                local_now=local_now,
            )
            if ai_intent:
                return ai_intent
        except Exception as exc:
            logger.warning("Reminder AI extraction failed: %s", exc)

    return extract_intent_rules(
        message_text=message_text,
        last_outbound=last_outbound,
        pending=pending,
        local_now=local_now,
    )


async def extract_intent_ai(
    gemini_client: GeminiClient,
    message_text: str,
    last_outbound: Optional[str],
    pending: Optional[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]],
    timezone_name: Optional[str],
    local_now: Optional[datetime],
) -> Optional[ReminderIntent]:
    """Extract intent using Gemini AI."""
    prompt = build_ai_prompt(
        message_text,
        last_outbound,
        pending,
        conversation_history,
        timezone_name=timezone_name,
        local_now=local_now,
    )
    response = await gemini_client.generate_content(
        prompt,
        fallback_response="{}",
        max_retries=1,
    )
    data = parse_json_response(response)
    if not data:
        return None

    is_request = bool(data.get("is_reminder_request"))
    declined = bool(data.get("declined"))
    reminder_text = clean_optional_text(data.get("reminder_text"))
    time_local = clean_time(data.get("time_local"))
    date_local = clean_date_local(data.get("date_local"))
    recurrence = data.get("recurrence") or "none"
    interval_days = safe_int(data.get("interval_days"))
    weekday = data.get("weekday")
    duration_occurrences = safe_int(data.get("duration_occurrences"))
    duration_days = safe_int(data.get("duration_days"))
    duration_weeks = safe_int(data.get("duration_weeks"))
    duration_months = safe_int(data.get("duration_months"))
    duration_end_date = clean_date_local(data.get("duration_end_date"))
    confidence = safe_float(data.get("confidence"), 0.0)
    needs_clarification = bool(data.get("needs_clarification"))

    if weekday is not None:
        try:
            weekday = int(weekday)
        except (TypeError, ValueError):
            weekday = None

    # Validate positive values
    if interval_days is not None and interval_days <= 0:
        interval_days = None
    if duration_occurrences is not None and duration_occurrences <= 0:
        duration_occurrences = None
    if duration_days is not None and duration_days <= 0:
        duration_days = None
    if duration_weeks is not None and duration_weeks <= 0:
        duration_weeks = None
    if duration_months is not None and duration_months <= 0:
        duration_months = None

    return ReminderIntent(
        is_request=is_request,
        declined=declined,
        reminder_text=reminder_text,
        time_local=time_local,
        date_local=date_local,
        recurrence=str(recurrence),
        interval_days=interval_days,
        weekday=weekday,
        duration_occurrences=duration_occurrences,
        duration_days=duration_days,
        duration_weeks=duration_weeks,
        duration_months=duration_months,
        duration_end_date=duration_end_date,
        confidence=confidence,
        needs_clarification=needs_clarification,
        source="ai",
    )


def extract_intent_rules(
    message_text: str,
    last_outbound: Optional[str],
    pending: Optional[Dict[str, Any]],
    local_now: Optional[datetime],
) -> ReminderIntent:
    """Extract intent using rule-based regex patterns."""
    normalized = normalize_text(message_text)
    declined = bool(RE_NO.search(normalized))
    affirmative = bool(RE_YES.search(normalized))
    mentions_reminder = any(keyword in normalized for keyword in REMINDER_KEYWORDS)

    last_outbound_mentions = last_message_mentions_reminder(last_outbound)
    is_request = mentions_reminder or (affirmative and last_outbound_mentions)

    local_now = local_now or datetime.now(SAO_PAULO_PYTZ_TZ)
    time_local = extract_time_local(message_text, normalized=normalized)
    date_local = extract_date_local(message_text, local_now, normalized=normalized)
    recurrence, weekday, interval_days = extract_recurrence(
        message_text,
        normalized=normalized,
    )
    duration_info = extract_duration_info(
        message_text,
        local_now,
        normalized=normalized,
    )
    reminder_text = extract_reminder_text(message_text)

    if interval_days and recurrence != "interval":
        recurrence = "interval"

    if recurrence == "none" and duration_info.has_value():
        recurrence = infer_recurrence_from_duration(duration_info)

    missing_text, missing_time, missing_interval, missing_duration = get_missing_fields(
        reminder_text=reminder_text,
        time_local=time_local,
        recurrence=recurrence,
        interval_days=interval_days,
        duration_info=duration_info,
    )

    needs_clarification = is_request and (
        missing_text or missing_time or missing_interval or missing_duration
    )

    if pending and (time_local or reminder_text):
        is_request = True

    return ReminderIntent(
        is_request=is_request,
        declined=declined,
        reminder_text=reminder_text,
        time_local=time_local,
        date_local=date_local,
        recurrence=recurrence,
        interval_days=interval_days,
        weekday=weekday,
        duration_occurrences=duration_info.occurrences,
        duration_days=duration_info.days,
        duration_weeks=duration_info.weeks,
        duration_months=duration_info.months,
        duration_end_date=duration_info.end_date,
        confidence=0.4,
        needs_clarification=needs_clarification,
        source="rule",
    )


def build_ai_prompt(
    message_text: str,
    last_outbound: Optional[str],
    pending: Optional[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]],
    timezone_name: Optional[str],
    local_now: Optional[datetime],
) -> str:
    """Build AI prompt for intent extraction."""
    local_now = local_now or datetime.now(SAO_PAULO_PYTZ_TZ)
    context = {
        "last_outbound_message": last_outbound,
        "pending_reminder": pending or None,
        "conversation_history": conversation_history or [],
        "patient_timezone": timezone_name or SAO_PAULO_TZ_NAME,
        "local_date": local_now.date().isoformat(),
        "local_time": local_now.strftime("%H:%M"),
        "local_datetime": local_now.isoformat(),
    }
    return f"""
Voce esta operando como a ferramenta de extracao para registrar lembretes.
Voce deve extrair pedidos de lembrete em mensagens de pacientes.
Responda somente com JSON valido (sem texto extra).

Campos:
- is_reminder_request: true|false
- declined: true|false
- reminder_text: string|null
- time_local: "HH:MM"|null
- date_local: "YYYY-MM-DD"|null
- recurrence: "none"|"daily"|"weekly"|"monthly"|"interval"
- interval_days: integer|null (use quando recurrence="interval")
- weekday: 0-6|null (0=segunda)
- duration_occurrences: integer|null (ex: "por 5 vezes")
- duration_days: integer|null (ex: "por 7 dias")
- duration_weeks: integer|null (ex: "por 3 semanas")
- duration_months: integer|null (ex: "por 2 meses")
- duration_end_date: "YYYY-MM-DD"|null (ex: "ate 10/12/2025")
- confidence: 0.0-1.0
- needs_clarification: true|false

Regras:
- Se a mensagem for apenas "sim"/"ok" e a ultima mensagem da clinica perguntar sobre lembretes, trate como pedido.
- Se a mensagem negar ("nao", "nao quero"), defina declined=true.
- Nao invente horarios ou datas. Se faltar horario ou o que lembrar, marque needs_clarification=true.
- Se houver recorrencia ("todo dia", "toda semana", "mensal", "a cada X dias")
  mas nao houver duracao, marque needs_clarification=true.
- Se houver "a cada X dias", use recurrence="interval" e preencha interval_days.
- Se houver duracao sem recorrencia explicita, escolha uma recorrencia coerente
  (dias -> daily, semanas -> weekly, meses -> monthly).
- Use o conversation_history para entender respostas curtas e o contexto da conversa.

Contexto: {json.dumps(context, ensure_ascii=False)}
Mensagem do paciente: {message_text}
JSON:
"""
