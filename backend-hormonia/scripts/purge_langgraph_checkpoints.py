"""Purge LangGraph Redis checkpoints and emit LGPD audit records."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.core.redis_manager import (
    get_redis_connection_kwargs,
    get_sync_redis_client,
)

try:
    import redis
except Exception:  # pragma: no cover - import is always expected in runtime
    redis = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
lgpd_logger = logging.getLogger("lgpd.data_deletion")

KEY_PATTERN = "langgraph:checkpoint:*"


def _client_db(redis_client: Any) -> int | None:
    pool = getattr(redis_client, "connection_pool", None)
    kwargs = getattr(pool, "connection_kwargs", None)
    if isinstance(kwargs, dict):
        db_value = kwargs.get("db")
        if isinstance(db_value, int):
            return db_value
    return None


def _ensure_db0_client(redis_client: Any) -> Any:
    db_number = _client_db(redis_client)
    if db_number in (None, 0):
        return redis_client
    if redis is None:
        return redis_client

    broker_url = getattr(settings, "CELERY_BROKER_URL", None) or settings.REDIS_URL
    if broker_url.rsplit("/", 1)[-1].isdigit():
        base_url = broker_url.rsplit("/", 1)[0]
        db0_url = f"{base_url}/0"
    else:
        db0_url = f"{broker_url.rstrip('/')}/0"

    logger.warning(
        "Sync Redis client is on DB %s; creating DB 0 client for checkpoint purge",
        db_number,
    )
    return redis.Redis.from_url(
        db0_url,
        **get_redis_connection_kwargs(mode="sync"),
    )


def purge_langgraph_checkpoints(batch_size: int = 100) -> int:
    """Delete Redis keys matching langgraph checkpoint prefix."""
    redis_client = _ensure_db0_client(get_sync_redis_client())
    deleted = 0
    batch: list[Any] = []

    for key in redis_client.scan_iter(match=KEY_PATTERN, count=100):
        batch.append(key)
        if len(batch) >= batch_size:
            deleted += int(redis_client.delete(*batch) or 0)
            batch.clear()

    if batch:
        deleted += int(redis_client.delete(*batch) or 0)

    lgpd_logger.critical(
        "LGPD data deletion event: Redis LangGraph checkpoints purged",
        extra={
            "event_type": "lgpd_data_deleted",
            "event_category": "data_change",
            "severity": "warning",
            "deletion_scope": "redis_langgraph_checkpoints",
            "reason": "LGPD Art. 46 - PHI ephemeral data purge during LangGraph decommission",
            "keys_deleted": deleted,
            "key_pattern": KEY_PATTERN,
            "legal_basis": "legal_obligation",
            "retention_note": "This log record must be retained for 7 years per LGPD Art. 46",
        },
    )

    try:
        from app.db.session import SessionLocal
        from app.services.audit.service import AuditService

        db = SessionLocal()
        try:
            audit = AuditService(db=db)
            audit.log_event(
                event_type="lgpd_data_deleted",
                event_category="data_change",
                severity="warning",
                actor_id=None,
                subject_id=None,
                event_data={
                    "deletion_scope": "redis_langgraph_checkpoints",
                    "reason": "LGPD Art. 46 - PHI ephemeral data purge during LangGraph decommission",
                    "keys_deleted": deleted,
                    "key_pattern": KEY_PATTERN,
                },
                result="success",
                legal_basis="legal_obligation",
                retention_days=2555,
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover - optional audit channel
        logger.warning(
            "DB audit log unavailable; structured log is the primary LGPD record: %s",
            exc,
        )

    return deleted


def main() -> None:
    purge_count = purge_langgraph_checkpoints()
    print(f"Purged {purge_count} LangGraph checkpoint keys from Redis DB 0")


if __name__ == "__main__":
    main()
