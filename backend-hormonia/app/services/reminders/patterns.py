"""
Regex patterns and constants for reminder parsing.
"""

import re

import pytz

from app.utils.constants import NO_PATTERNS, YES_PATTERNS
from app.utils.timezone import SAO_PAULO_TZ_NAME

# ---- Constants ----
MAX_ACTIVE_REMINDERS = 5
MAX_HISTORY_ENTRIES = 10

REMINDER_KEYWORDS = (
    "lembrete",
    "lembrar",
    "lembra",
    "lembre",
    "avisar",
    "avisa",
    "avise",
    "recordar",
    "recorda",
)

WEEKDAY_ALIASES = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}

SAO_PAULO_PYTZ_TZ = pytz.timezone(SAO_PAULO_TZ_NAME)

# ---- Precompiled regex patterns ----
RE_NO = re.compile(NO_PATTERNS)
RE_YES = re.compile(YES_PATTERNS)

RE_WHITESPACE = re.compile(r"\s+")
RE_JSON = re.compile(r"\{.*\}", re.DOTALL)

RE_WEEKDAY_EVERY = re.compile(r"\btoda\s+([a-z-]+)\b")
RE_DATE_DMY = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
RE_DATE_DAY = re.compile(r"\bdia\s+(\d{1,2})\b")
RE_INTERVAL_DAYS = re.compile(r"\ba cada\s+(\d{1,3})\s+dias?\b")

RE_REMINDER_TEXT = re.compile(
    r"(?:lembra(?:r|e)?|lembrete|avisa(?:r|e)?|recorda(?:r)?)\s*"
    r"(?:de|para|pra)?\s*(.+)",
    re.IGNORECASE,
)
RE_REMINDER_CUTOFF = re.compile(
    r"\b(?:amanha|hoje|depois de amanha|todo dia|todos os dias|diariamente|toda semana|semanal|"
    r"todo mes|mensal|a cada \d+ dias)\b.*$",
    re.IGNORECASE,
)
RE_REMINDER_TIME_CUTOFF = re.compile(
    r"\bas\s*\d{1,2}(?:[:h]\d{0,2})?\b.*$",
    re.IGNORECASE,
)

TIME_PATTERNS = (
    re.compile(r"\b(\d{1,2})[:h](\d{2})\b"),
    re.compile(r"\b(\d{1,2})\s*(?:h|hora|horas)\b"),
    re.compile(r"\b(?:as|a|por volta de|por volta das)\s*(\d{1,2})\b"),
)

RE_DURATION_OCCURRENCES = re.compile(
    r"\b(?:por|durante|pelos proximos|pelas proximas)\s+(\d{1,3})\s+vez(?:es)?\b"
)
RE_DURATION_DAYS = re.compile(
    r"\b(?:por|durante|pelos proximos|pelas proximas)\s+(\d{1,3})\s+dia(?:s)?\b"
)
RE_DURATION_WEEKS = re.compile(
    r"\b(?:por|durante|pelos proximos|pelas proximas)\s+(\d{1,3})\s+semana(?:s)?\b"
)
RE_DURATION_MONTHS = re.compile(
    r"\b(?:por|durante|pelos proximos|pelas proximas)\s+(\d{1,3})\s+mes(?:es)?\b"
)
RE_DURATION_END_DATE = re.compile(
    r"\b(?:ate|ate o dia|ate dia)\s+(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b"
)

RE_TIME_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")
RE_NUMBER_ONLY = re.compile(r"^\d{1,3}$")
