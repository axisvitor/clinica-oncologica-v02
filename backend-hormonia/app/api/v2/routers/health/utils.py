"""
Health Check Utilities Module

Provides helper functions for health scoring and status determination.
"""

import time
from typing import Dict
from app.schemas.v2.health import HealthStatus


# Application startup time for uptime calculation
APP_START_TIME = time.time()


def calculate_health_score(component_checks: Dict[str, HealthStatus]) -> float:
    """
    Calculate overall health score (0-100) based on component statuses.

    Weights:
    - Database: 30%
    - Redis: 20%
    - Workers: 15%
    - External Services: 15%
    - Storage: 20%

    Args:
        component_checks: Dictionary of component statuses

    Returns:
        Health score between 0 and 100
    """
    weights = {
        "database": 30.0,
        "redis": 20.0,
        "workers": 15.0,
        "external_services": 15.0,
        "storage": 20.0,
    }

    status_scores = {
        HealthStatus.HEALTHY: 100.0,
        HealthStatus.DEGRADED: 50.0,
        HealthStatus.UNHEALTHY: 0.0,
        HealthStatus.UNKNOWN: 25.0,
    }

    total_score = 0.0
    for component, weight in weights.items():
        component_status = component_checks.get(component, HealthStatus.UNKNOWN)
        score = status_scores.get(component_status, 0.0)
        total_score += (score * weight) / 100.0

    return round(total_score, 2)


def determine_overall_status(health_score: float) -> HealthStatus:
    """
    Determine overall health status from health score.

    Args:
        health_score: Health score (0-100)

    Returns:
        Overall health status
    """
    if health_score >= 90:
        return HealthStatus.HEALTHY
    elif health_score >= 70:
        return HealthStatus.DEGRADED
    else:
        return HealthStatus.UNHEALTHY
