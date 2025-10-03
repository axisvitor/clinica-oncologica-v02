"""
Application constants for the Hormonia platform.
"""

# Message limits
WHATSAPP_MESSAGE_LIMIT = 4000
MAX_CONVERSATION_HISTORY = 10

# Response processing
DEFAULT_CONFIDENCE_SCORE = 0.0
ESCALATION_DELAY_SECONDS = 300  # 5 minutes
CRITICAL_ESCALATION_DELAY = 0   # Immediate

# Urgent keywords for medical escalation
URGENT_KEYWORDS = [
    'emergency', 'emergência', 'urgent', 'urgente', 'help', 'ajuda',
    'hospital', 'ambulance', 'ambulância', 'severe', 'severo',
    'can\'t breathe', 'não consigo respirar', 'chest pain', 'dor no peito',
    'bleeding', 'sangramento', 'unconscious', 'inconsciente'
]

# Mood pattern recognition
POSITIVE_MOOD_PATTERNS = r'\b(bem|good|great|ótimo|feliz|happy|melhor|better)\b'
NEGATIVE_MOOD_PATTERNS = r'\b(mal|bad|terrible|péssimo|triste|sad|pior|worse)\b'

# Boolean response patterns
YES_PATTERNS = r'\b(sim|yes|yeah|ok|okay|claro|certo|positivo)\b'
NO_PATTERNS = r'\b(não|no|nope|never|negativo|jamais)\b'

# Medical patterns
MEDICATION_PATTERNS = r'\b(mg|ml|comprimido|cápsula|medicamento|remédio)\b'
PAIN_SCALE_PATTERN = r'\b([1-9]|10)\b.*\b(dor|pain|scale|escala)\b'
TIME_PATTERNS = r'\b(\d{1,2}):(\d{2})\b|(\d{1,2})\s*(am|pm|h|horas?)\b'

# Flow action priorities
PRIORITY_CRITICAL = "critical"
PRIORITY_HIGH = "high"
PRIORITY_NORMAL = "normal"
PRIORITY_LOW = "low"

# Response messages
ERROR_MESSAGES = {
    "empty_content": "Desculpe, não consegui entender sua resposta. Por favor, envie uma mensagem com texto.",
    "invalid_button": "Por favor, use os botões disponíveis para responder.",
    "generic_error": "Pode tentar novamente?",
    "invalid_interactive": "Resposta inválida. Por favor, use as opções disponíveis.",
    "high_concern_ack": "Obrigada por compartilhar isso comigo. Vou garantir que sua equipe médica seja notificada.",
    "positive_response": "Que bom saber que você está bem! Continue assim. 😊",
    "negative_response": "Entendo que você não está se sentindo bem. Estou aqui para te apoiar.",
    "confirmation_yes": "Perfeito! Obrigada pela confirmação.",
    "confirmation_no": "Entendi. Obrigada por me informar."
}

# Quiz flow constants
QUIZ_FLOW_CONSTANTS = {
    'MONTHLY_QUIZ_DAY': 30,  # Day 30 in monthly flow triggers quiz
    'QUIZ_COOLDOWN_DAYS': 25,  # Minimum days between quiz sessions
    'QUIZ_QUESTION_DELAY': 5,  # Seconds between questions
    'QUIZ_INTRO_DELAY': 30,  # Seconds after intro before first question
    'MAX_QUIZ_DURATION_HOURS': 24,  # Maximum time to complete quiz
    'ENCOURAGEMENT_MESSAGES': [
        "Obrigada pela resposta! 😊",
        "Perfeito! Cada informação me ajuda a cuidar melhor de você. ✨",
        "Que bom saber disso! 💕",
        "Obrigada por compartilhar isso comigo! 🌸"
    ]
}

# Message types for quiz flow
QUIZ_MESSAGE_TYPES = {
    'QUIZ_INTRO': 'quiz_intro',
    'QUIZ_QUESTION': 'quiz_question',
    'QUIZ_ENCOURAGEMENT': 'quiz_encouragement',
    'QUIZ_COMPLETION': 'quiz_completion'
}