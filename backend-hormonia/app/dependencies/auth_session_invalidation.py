"""Shared Redis session invalidation helpers for staff-session auth flows.

PostgreSQL session rows are the authorization source of truth. These helpers
only remove Redis cache hints at explicit revocation/logout boundaries and must
fail closed by returning ``False`` rather than raising cache details to callers.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_SESSION_CACHE_PREFIX = "session:"


def _session_log_prefix(session_id: str) -> str:
    """Return a short non-secret correlation prefix for cache diagnostics."""
    return str(session_id)[:8]


async def _maybe_await(result: Any) -> Any:
    if inspect.isawaitable(result):
        return await result
    return result


def _cache_delete_succeeded(result: Any) -> bool:
    """Normalize cache-adapter delete return values.

    Some compatibility adapters return ``None`` for a successful no-op, while
    Redis clients usually return an integer delete count.
    """
    return True if result is None else bool(result)


def _warn_cache_invalidation_failed(
    *,
    log: logging.Logger,
    method_name: str,
    session_id: str,
    exc: BaseException,
) -> None:
    """Emit a sanitized cache failure diagnostic without exception messages."""
    log.warning(
        "session_cache_invalidation_failed method=%s error_class=%s session_prefix=%s",
        method_name,
        exc.__class__.__name__,
        _session_log_prefix(session_id),
    )


def _session_cache_keys(session_id: str) -> tuple[str, ...]:
    """Return the canonical Redis session key plus raw-ID compatibility key."""
    canonical_key = f"{_SESSION_CACHE_PREFIX}{session_id}"
    if canonical_key == session_id:
        return (canonical_key,)
    return (canonical_key, session_id)


async def invalidate_session_cache(
    redis_cache: Any,
    session_id: str,
    *,
    log: Optional[logging.Logger] = None,
) -> bool:
    """Invalidate one session cache entry using wrapper or raw Redis contracts.

    Supports wrapper adapters that expose ``invalidate_session(session_id)`` or
    ``delete_session(session_id)`` and raw Redis clients that expose
    ``delete(*keys)``. Raw deletion always targets ``session:{session_id}``, the
    key written by ``SessionCache.create_session()``, and also deletes the raw ID
    for older compatibility shims.
    """
    if not redis_cache or not session_id:
        return False

    log = log or logger
    normalized_session_id = str(session_id)

    for method_name in ("invalidate_session", "delete_session"):
        method = getattr(redis_cache, method_name, None)
        if not callable(method):
            continue
        try:
            result = await _maybe_await(method(normalized_session_id))
        except TypeError:
            # Compatibility shims may expose the name with an incompatible
            # signature; try the next supported contract rather than failing.
            continue
        except Exception as exc:  # pragma: no cover - exercised through tests
            _warn_cache_invalidation_failed(
                log=log,
                method_name=method_name,
                session_id=normalized_session_id,
                exc=exc,
            )
            continue

        if _cache_delete_succeeded(result):
            return True

    delete = getattr(redis_cache, "delete", None)
    if callable(delete):
        keys = _session_cache_keys(normalized_session_id)
        try:
            result = await _maybe_await(delete(*keys))
            return _cache_delete_succeeded(result)
        except TypeError:
            deleted_any = False
            for key in keys:
                try:
                    result = await _maybe_await(delete(key))
                except TypeError:
                    continue
                except Exception as exc:
                    _warn_cache_invalidation_failed(
                        log=log,
                        method_name="delete",
                        session_id=normalized_session_id,
                        exc=exc,
                    )
                    return deleted_any
                deleted_any = _cache_delete_succeeded(result) or deleted_any
            return deleted_any
        except Exception as exc:
            _warn_cache_invalidation_failed(
                log=log,
                method_name="delete",
                session_id=normalized_session_id,
                exc=exc,
            )
            return False

    log.debug(
        "session_cache_invalidation_unavailable session_prefix=%s",
        _session_log_prefix(normalized_session_id),
    )
    return False


async def invalidate_all_user_sessions_cache(redis_cache: Any, identity: Optional[str]) -> int:
    """Invalidate all cached sessions for a user through compatibility adapters."""
    if not redis_cache or not identity:
        return 0

    invalidate_all = getattr(redis_cache, "invalidate_all_user_sessions", None)
    if callable(invalidate_all):
        try:
            result = await _maybe_await(invalidate_all(identity))
            return int(result or 0)
        except Exception as exc:
            logger.warning(
                "session_cache_bulk_invalidation_failed method=invalidate_all_user_sessions error_class=%s",
                exc.__class__.__name__,
            )
            return 0

    delete_pattern = getattr(redis_cache, "delete_pattern", None)
    if callable(delete_pattern):
        try:
            result = await _maybe_await(delete_pattern(f"session:*{identity}*"))
            return int(result) if isinstance(result, int) else 0
        except Exception as exc:
            logger.warning(
                "session_cache_bulk_invalidation_failed method=delete_pattern error_class=%s",
                exc.__class__.__name__,
            )
            return 0

    logger.debug("session_cache_bulk_invalidation_unavailable")
    return 0
