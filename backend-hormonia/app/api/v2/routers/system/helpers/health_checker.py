"""
Health Check Helpers.

Provides helper functions for:
- Individual component health checking
- Overall system health score calculation
"""

from typing import Any, Dict
import time

from sqlalchemy import text

from app.schemas.v2.system import ComponentHealth
from app.config import settings
from .auth import _get_redis_client
from app.utils.timezone import now_sao_paulo


async def _check_component_health(component_name: str, db: Any) -> ComponentHealth:
    """
    Check individual component health with latency measurement.

    Args:
        component_name: Name of component to check (database, redis, session_auth, external_apis)
        db: Database session instance

    Returns:
        ComponentHealth: Component health status with metrics

    Components:
        - database: PostgreSQL connectivity and latency
        - redis: Cache connectivity and latency
        - session_auth: Session/cookie configuration status for staff auth
        - external_apis: External service availability

    Note:
        Measures latency in milliseconds for performance monitoring.
        Returns 'unknown' status for unconfigured or unsupported components.
    """
    start_time = time.time()

    try:
        if component_name == "database":
            await db.execute(text("SELECT 1"))
            latency_ms = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="database",
                status="healthy",
                latency_ms=latency_ms,
                last_check=now_sao_paulo(),
                metadata={"type": "postgresql"},
            )

        if component_name == "redis":
            redis = await _get_redis_client()
            if redis:
                await redis.ping()
                latency_ms = (time.time() - start_time) * 1000
                return ComponentHealth(
                    name="redis",
                    status="healthy",
                    latency_ms=latency_ms,
                    last_check=now_sao_paulo(),
                    metadata={"type": "cache"},
                )

            return ComponentHealth(
                name="redis",
                status="unhealthy",
                error="Redis client unavailable",
                last_check=now_sao_paulo(),
            )

        if component_name == "session_auth":
            latency_ms = (time.time() - start_time) * 1000
            secret_key = getattr(settings, "SECURITY_SECRET_KEY", None)
            cookie_name = getattr(settings, "SESSION_COOKIE_NAME", None)
            cookie_http_only = bool(
                getattr(settings, "SESSION_ENABLE_COOKIE_HTTPONLY", False)
            )
            csrf_secret_configured = bool(
                getattr(settings, "SECURITY_CSRF_SECRET_KEY", None)
            )

            missing = []
            if not secret_key:
                missing.append("SECURITY_SECRET_KEY")
            if not cookie_name:
                missing.append("SESSION_COOKIE_NAME")
            if not cookie_http_only:
                missing.append("SESSION_ENABLE_COOKIE_HTTPONLY")

            if missing:
                return ComponentHealth(
                    name="session_auth",
                    status="unhealthy",
                    latency_ms=latency_ms,
                    error=(
                        "Missing session-auth prerequisites: "
                        + ", ".join(missing)
                    ),
                    last_check=now_sao_paulo(),
                    metadata={
                        "mode": "session-first",
                        "csrf_protection_configured": csrf_secret_configured,
                    },
                )

            status = "healthy"
            error = None
            if (
                settings.APP_ENVIRONMENT.lower() == "production"
                and not csrf_secret_configured
            ):
                status = "degraded"
                error = (
                    "SECURITY_CSRF_SECRET_KEY is not configured for production "
                    "session auth"
                )

            return ComponentHealth(
                name="session_auth",
                status=status,
                latency_ms=latency_ms,
                error=error,
                last_check=now_sao_paulo(),
                metadata={
                    "mode": "session-first",
                    "cookie_name": cookie_name,
                    "cookie_secure": bool(
                        getattr(settings, "SESSION_ENABLE_COOKIE_SECURE", False)
                    ),
                    "cookie_http_only": cookie_http_only,
                    "csrf_protection_configured": csrf_secret_configured,
                },
            )

        if component_name == "external_apis":
            return ComponentHealth(
                name="external_apis",
                status="unknown",
                last_check=now_sao_paulo(),
                metadata={"evolution_enabled": settings.WHATSAPP_ENABLE_SERVICE},
            )

        return ComponentHealth(
            name=component_name,
            status="unknown",
            error="Unknown component",
            last_check=now_sao_paulo(),
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return ComponentHealth(
            name=component_name,
            status="unhealthy",
            latency_ms=latency_ms,
            error=str(e),
            last_check=now_sao_paulo(),
        )



def _calculate_health_score(components: Dict[str, ComponentHealth]) -> float:
    """
    Calculate overall health score (0-100) based on component status.

    Scoring:
    - Healthy: 100 points
    - Degraded: 50 points
    - Unhealthy: 0 points
    - Unknown: 25 points

    Args:
        components: Dictionary of component names to ComponentHealth instances

    Returns:
        float: Overall health score from 0.0 to 100.0

    Note:
        Returns 0.0 if no components provided.
        Score is averaged across all components.
    """
    if not components:
        return 0.0

    total_score = 0
    for component in components.values():
        if component.status == "healthy":
            total_score += 100
        elif component.status == "degraded":
            total_score += 50
        elif component.status == "unknown":
            total_score += 25
        # unhealthy = 0 points

    return total_score / len(components)


# Public API aliases (without underscore for backward compatibility)
check_component_health = _check_component_health
calculate_health_score = _calculate_health_score
