"""
Manual Health Test Module

Provides admin-only manual health testing endpoint.
"""

import time
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth_dependencies import get_admin_user
from app.models.user import User
from app.schemas.v2.health import (
    HealthTestRequest,
    HealthTestResponse,
    HealthStatus,
)
from .database_health import check_database_health
from .service_health import check_redis_health, check_worker_health
from .storage_external import check_storage_health


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/test", response_model=HealthTestResponse)
async def manual_health_test(
    request_data: HealthTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
) -> HealthTestResponse:
    """
    Manual health test trigger (Admin only).

    Runs comprehensive health checks on demand.
    NO caching - always executes fresh tests.
    Rate limited to 20 requests per minute.
    """
    start_time = time.time()
    test_id = f"test_{uuid4().hex[:12]}"

    components_to_test = request_data.components or [
        "database",
        "redis",
        "workers",
        "storage",
    ]
    results = {}

    # Run requested tests
    if "database" in components_to_test:
        results["database"] = (await check_database_health(db)).model_dump()

    if "redis" in components_to_test:
        results["redis"] = (await check_redis_health()).model_dump()

    if "workers" in components_to_test:
        results["workers"] = (await check_worker_health(db)).model_dump()

    if "storage" in components_to_test:
        results["storage"] = (await check_storage_health()).model_dump()

    # Determine overall test status
    all_healthy = all(result.get("status") == "healthy" for result in results.values())
    test_status = HealthStatus.HEALTHY if all_healthy else HealthStatus.DEGRADED

    duration_ms = (time.time() - start_time) * 1000

    return HealthTestResponse(
        test_id=test_id,
        timestamp=datetime.now(timezone.utc),
        status=test_status,
        components_tested=components_to_test,
        results=results,
        duration_ms=round(duration_ms, 2),
    )
