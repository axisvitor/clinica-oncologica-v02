"""
AI Services Constants - Cache TTLs, rate limits, and cost estimates.
"""
from app.schemas.v2.ai import AIModelType


# Cache TTLs (in seconds)
CACHE_TTL_AI_RESPONSE = 7200  # 2 hours for AI responses
CACHE_TTL_INSIGHTS = 900  # 15 minutes for insights
CACHE_TTL_HEALTH = 300  # 5 minutes for health checks
CACHE_TTL_STATS = 3600  # 1 hour for usage stats

# Rate limit configurations (requests per minute)
RATE_LIMIT_AI_GENERAL = 10  # General AI calls
RATE_LIMIT_HUMANIZE = 30  # Humanize endpoint (lighter)
RATE_LIMIT_INSIGHTS = 10  # Insights generation
RATE_LIMIT_ANALYSIS = 20  # Analysis endpoints

# Token cost estimates (USD per 1K tokens)
COST_PER_1K_TOKENS = {
    AIModelType.GEMINI_PRO: 0.0015,
    AIModelType.GEMINI_FLASH: 0.0005,
    AIModelType.GPT4: 0.03,
    AIModelType.GPT35: 0.002,
}
