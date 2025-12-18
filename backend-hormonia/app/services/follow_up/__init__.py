"""
Follow-up system module with Redis persistence.

Provides Redis-backed storage for:
- Follow-up actions (pending, executed, failed)
- Escalation alerts (active, acknowledged, resolved)
- Conversation contexts (with 7-day TTL)
"""

from app.services.follow_up.redis_store import FollowUpRedisStore

__all__ = ["FollowUpRedisStore"]
