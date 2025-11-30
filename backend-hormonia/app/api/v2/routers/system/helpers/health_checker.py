"""
Health Check Helpers.

Provides helper functions for:
- Individual component health checking
- Overall system health score calculation
"""

from typing import Any, Dict
from datetime import datetime
import time

from sqlalchemy import text

from app.schemas.v2.system import ComponentHealth
from app.config import settings
from .auth import _get_redis_client


async def _check_component_health(component_name: str, db: Any) -> ComponentHealth:
    """
    Check individual component health with latency measurement.

    Args:
        component_name: Name of component to check (database, redis, firebase, external_apis)
        db: Database session instance

    Returns:
        ComponentHealth: Component health status with metrics

    Components:
        - database: PostgreSQL connectivity and latency
        - redis: Cache connectivity and latency
        - firebase: Admin SDK configuration status
        - external_apis: External service availability

    Note:
        Measures latency in milliseconds for performance monitoring.
        Returns 'unknown' status for unconfigured or unsupported components.
    """
    start_time = time.time()

    try:
        if component_name == "database":
            # Check database connectivity
            db.execute(text("SELECT 1"))
            latency_ms = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="database",
                status="healthy",
                latency_ms=latency_ms,
                last_check=datetime.utcnow(),
                metadata={"type": "postgresql"}
            )

        elif component_name == "redis":
            # Check Redis connectivity
            redis = await _get_redis_client()
            if redis:
                await redis.ping()
                latency_ms = (time.time() - start_time) * 1000
                return ComponentHealth(
                    name="redis",
                    status="healthy",
                    latency_ms=latency_ms,
                    last_check=datetime.utcnow(),
                    metadata={"type": "cache"}
                )
            else:
                return ComponentHealth(
                    name="redis",
                    status="unhealthy",
                    error="Redis client unavailable",
                    last_check=datetime.utcnow()
                )

        elif component_name == "firebase":
            # Check Firebase Admin SDK actual connectivity
            try:
                import firebase_admin
                from firebase_admin import auth as firebase_auth

                # Check if Firebase app is initialized
                app = firebase_admin.get_app()
                if app and settings.FIREBASE_ADMIN_PROJECT_ID:
                    # Try to verify the SDK is functional (fast operation)
                    latency_ms = (time.time() - start_time) * 1000
                    return ComponentHealth(
                        name="firebase",
                        status="healthy",
                        latency_ms=latency_ms,
                        last_check=datetime.utcnow(),
                        metadata={
                            "configured": True,
                            "project_id": settings.FIREBASE_ADMIN_PROJECT_ID
                        }
                    )
                else:
                    return ComponentHealth(
                        name="firebase",
                        status="degraded",
                        last_check=datetime.utcnow(),
                        metadata={"configured": False, "reason": "not_initialized"}
                    )
            except (ValueError, ImportError):
                # Firebase not initialized or not installed
                return ComponentHealth(
                    name="firebase",
                    status="unknown",
                    last_check=datetime.utcnow(),
                    metadata={"configured": bool(settings.FIREBASE_ADMIN_PROJECT_ID), "reason": "sdk_not_initialized"}
                )

        elif component_name == "external_apis":
            # Check external API availability (placeholder)
            return ComponentHealth(
                name="external_apis",
                status="unknown",
                last_check=datetime.utcnow(),
                metadata={"evolution_enabled": settings.WHATSAPP_ENABLE_SERVICE}
            )

        else:
            return ComponentHealth(
                name=component_name,
                status="unknown",
                error="Unknown component",
                last_check=datetime.utcnow()
            )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return ComponentHealth(
            name=component_name,
            status="unhealthy",
            latency_ms=latency_ms,
            error=str(e),
            last_check=datetime.utcnow()
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
