"""
Medico (Doctor) API endpoints for dashboard and doctor-specific operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
import logging
from typing import Optional

from app.dependencies import get_thread_safe_db, get_doctor_user
from app.models.user import User
from app.services.medico_stats_service import MedicoStatsService
from app.schemas.medico import MedicoDashboardStats
from app.core.redis_unified import get_sync_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/medico", tags=["Medico"])


@router.get("/dashboard-stats", response_model=MedicoDashboardStats)
async def get_dashboard_stats(
    db: Session = Depends(get_thread_safe_db),
    current_user: User = Depends(get_doctor_user)
):
    """
    Get dashboard statistics for medico's panel.

    Returns comprehensive statistics including:
    - **pacientes_ativos**: Active patients count
    - **consultas_hoje**: Today's appointments/consultations
    - **pendencias**: Pending tasks (exams + messages)
    - **exames_aguardando**: Exams awaiting review
    - **engagement**: Message engagement metrics (messages today, unread, response rate)
    - **alerts**: Alert counts by severity (critical, high, medium, low)

    **Authentication**: Requires doctor role or higher.

    **Caching**: Results are cached for 2 minutes in Redis for performance.

    **Rate Limiting**: Standard rate limits apply.

    ## Example Response

    ```json
    {
      "pacientes_ativos": 45,
      "consultas_hoje": 8,
      "pendencias": 12,
      "exames_aguardando": 5,
      "engagement": {
        "messages_today": 23,
        "messages_unread": 4,
        "response_rate": 0.87,
        "avg_response_time_minutes": 45
      },
      "alerts": {
        "total": 15,
        "critical": 2,
        "high": 5,
        "medium": 6,
        "low": 2
      },
      "timestamp": "2025-10-06T14:30:00Z"
    }
    ```

    ## Edge Cases

    - New medico with no patients → returns zeros
    - No messages → response_rate = 0.0, avg_response_time = null
    - No appointments today → consultas_hoje = 0

    ## Database Tables Used

    - `patients` - Active patients filtering
    - `messages` - Message engagement metrics
    - `alerts` - Alert severity counts

    ## Performance

    - Query execution: ~50-100ms (uncached)
    - Redis cache hit: ~5ms
    - Cache TTL: 2 minutes
    """
    try:
        # Generate cache key for this medico's stats
        cache_key = f"medico:dashboard-stats:{current_user.id}"

        # Try to get from Redis cache
        try:
            redis_client = get_sync_redis()
            if redis_client:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    logger.info(f"Cache HIT for medico {current_user.id} dashboard stats")
                    stats_dict = json.loads(cached_data)
                    return MedicoDashboardStats(**stats_dict)
                else:
                    logger.debug(f"Cache MISS for medico {current_user.id} dashboard stats")
        except Exception as cache_error:
            logger.warning(f"Redis cache error (continuing without cache): {cache_error}")
            # Continue without cache on error

        # Calculate stats using service
        service = MedicoStatsService(db, str(current_user.id))
        stats_dict = service.get_all_stats()

        # Validate and create response model
        response = MedicoDashboardStats(**stats_dict)

        # Cache in Redis for 2 minutes
        try:
            redis_client = get_sync_redis()
            if redis_client:
                redis_client.setex(
                    cache_key,
                    120,  # 2 minutes TTL
                    response.json()
                )
                logger.info(f"Cached dashboard stats for medico {current_user.id} (TTL: 2min)")
        except Exception as cache_error:
            logger.warning(f"Failed to cache dashboard stats: {cache_error}")
            # Continue even if caching fails

        return response

    except Exception as e:
        logger.error(f"Error fetching dashboard stats for medico {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve dashboard statistics: {str(e)}"
        )


@router.get("/health")
async def medico_health():
    """
    Health check endpoint for medico API.

    Returns:
        Simple health status
    """
    return {
        "status": "healthy",
        "service": "medico-api",
        "endpoints": [
            "GET /api/v1/medico/dashboard-stats - Dashboard statistics"
        ]
    }
