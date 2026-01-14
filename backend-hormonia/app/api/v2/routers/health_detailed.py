"""
Detailed Health Check Endpoint
Provides comprehensive system health including saga orchestration, database constraints, RBAC, and Celery
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
import asyncio

from app.database import get_db
from app.core.redis_client import get_async_redis_client

router = APIRouter(tags=["health"])


@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Comprehensive health check including all critical systems

    Returns:
        - Overall status
        - Database connectivity and constraints
        - Redis connectivity
        - Saga orchestration health
        - RBAC system status
        - Version information
    """
    results = await asyncio.gather(
        check_database_health(db),
        check_redis_health(),
        check_saga_health(db),
        check_rbac_health(db),
        check_database_constraints(db),
        return_exceptions=True,
    )

    database_health, redis_health, saga_health, rbac_health, constraints_health = (
        results
    )

    # Determine overall status
    all_healthy = all(
        [
            isinstance(r, dict) and r.get("status") == "healthy"
            for r in results
            if isinstance(r, dict)
        ]
    )

    overall_status = "healthy" if all_healthy else "degraded"

    # Check for critical failures
    if any(isinstance(r, Exception) for r in results):
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0-with-critical-fixes",
        "components": {
            "database": database_health
            if isinstance(database_health, dict)
            else {"status": "error", "error": str(database_health)},
            "redis": redis_health
            if isinstance(redis_health, dict)
            else {"status": "error", "error": str(redis_health)},
            "saga_system": saga_health
            if isinstance(saga_health, dict)
            else {"status": "error", "error": str(saga_health)},
            "rbac": rbac_health
            if isinstance(rbac_health, dict)
            else {"status": "error", "error": str(rbac_health)},
            "constraints": constraints_health
            if isinstance(constraints_health, dict)
            else {"status": "error", "error": str(constraints_health)},
        },
    }


async def check_database_health(db: AsyncSession) -> Dict[str, Any]:
    """Check database connection and basic query performance"""
    try:
        start_time = datetime.now(timezone.utc)
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Check connection pool status
        pool_size = (
            db.get_bind().pool.size() if hasattr(db.get_bind(), "pool") else None
        )
        checked_out = (
            db.get_bind().pool.checkedout() if hasattr(db.get_bind(), "pool") else None
        )

        status = "healthy" if latency_ms < 100 else "degraded"

        return {
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "pool_size": pool_size,
            "connections_in_use": checked_out,
            "connection_pool_usage": round((checked_out / pool_size * 100), 2)
            if pool_size and checked_out
            else 0,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_redis_health() -> Dict[str, Any]:
    """Check Redis connection and latency"""
    try:
        redis_client = await get_async_redis_client()
        if redis_client is None:
            return {"status": "unhealthy", "error": "Redis client not available"}

        start_time = datetime.now(timezone.utc)
        await redis_client.ping()
        latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Get Redis info
        info = await redis_client.info()

        status = "healthy" if latency_ms < 50 else "degraded"

        return {
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_saga_health(db: AsyncSession) -> Dict[str, Any]:
    """Check saga orchestrator health and performance"""
    try:
        # Check for stuck sagas (sagas in intermediate state for > 30 minutes)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=30)

        stuck_sagas_query = text("""
            SELECT COUNT(*) as stuck_count
            FROM saga_execution_log
            WHERE status IN ('running', 'compensating')
            AND created_at < :cutoff_time
        """)

        result = await db.execute(stuck_sagas_query, {"cutoff_time": cutoff_time})
        stuck_count = result.scalar() or 0

        # Calculate recent success rate (last 1 hour)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=1)

        success_rate_query = text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed') as success_count,
                COUNT(*) as total_count
            FROM saga_execution_log
            WHERE created_at > :recent_cutoff
        """)

        result = await db.execute(success_rate_query, {"recent_cutoff": recent_cutoff})
        row = result.fetchone()

        success_count = row.success_count if row else 0
        total_count = row.total_count if row else 0
        success_rate = (success_count / total_count) if total_count > 0 else 1.0

        # Calculate compensation rate
        compensation_query = text("""
            SELECT COUNT(*) as compensation_count
            FROM saga_execution_log
            WHERE status = 'compensated'
            AND created_at > :recent_cutoff
        """)

        result = await db.execute(compensation_query, {"recent_cutoff": recent_cutoff})
        compensation_count = result.scalar() or 0
        compensation_rate = (
            (compensation_count / total_count) if total_count > 0 else 0.0
        )

        # Determine health status
        status = "healthy"
        if stuck_count > 0:
            status = "degraded"
        if success_rate < 0.90:
            status = "unhealthy"

        return {
            "status": status,
            "stuck_sagas": stuck_count,
            "success_rate": round(success_rate, 4),
            "compensation_rate": round(compensation_rate, 4),
            "recent_executions": total_count,
            "health_threshold": {
                "success_rate_target": 0.95,
                "max_stuck_sagas": 0,
                "max_compensation_rate": 0.05,
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_rbac_health(db: AsyncSession) -> Dict[str, Any]:
    """Check RBAC system configuration and health"""
    try:
        # Count roles and permissions
        roles_query = text("SELECT COUNT(*) FROM roles")
        permissions_query = text("SELECT COUNT(*) FROM permissions")
        role_permissions_query = text("SELECT COUNT(*) FROM role_permissions")

        roles_count = (await db.execute(roles_query)).scalar() or 0
        permissions_count = (await db.execute(permissions_query)).scalar() or 0
        role_permissions_count = (
            await db.execute(role_permissions_query)
        ).scalar() or 0

        # Check for users without roles
        users_without_roles_query = text("""
            SELECT COUNT(*)
            FROM users u
            LEFT JOIN user_roles ur ON u.id = ur.user_id
            WHERE ur.user_id IS NULL
        """)
        users_without_roles = (
            await db.execute(users_without_roles_query)
        ).scalar() or 0

        status = "healthy"
        if roles_count == 0 or permissions_count == 0:
            status = "unhealthy"
        elif users_without_roles > 0:
            status = "degraded"

        return {
            "status": status,
            "roles_count": roles_count,
            "permissions_count": permissions_count,
            "role_permissions_count": role_permissions_count,
            "users_without_roles": users_without_roles,
            "rbac_enabled": True,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_database_constraints(db: AsyncSession) -> Dict[str, Any]:
    """Verify critical database constraints are in place"""
    try:
        constraints_to_check = [
            ("patients", "unique_cpf_constraint"),
            ("patients", "unique_email_constraint"),
            ("patients", "unique_phone_constraint"),
            ("saga_execution_log", "saga_execution_log_pkey"),
        ]

        constraint_status = {}
        all_present = True

        for table_name, constraint_name in constraints_to_check:
            constraint_query = text("""
                SELECT COUNT(*)
                FROM information_schema.table_constraints
                WHERE table_name = :table_name
                AND constraint_name = :constraint_name
            """)

            result = await db.execute(
                constraint_query,
                {"table_name": table_name, "constraint_name": constraint_name},
            )
            exists = result.scalar() > 0
            constraint_status[f"{table_name}.{constraint_name}"] = exists
            all_present = all_present and exists

        # Check for recent duplicate prevention (blocked attempts)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        duplicate_blocks_query = text("""
            SELECT COUNT(*)
            FROM audit_log
            WHERE event_type = 'duplicate_patient_blocked'
            AND created_at > :recent_cutoff
        """)

        try:
            result = await db.execute(
                duplicate_blocks_query, {"recent_cutoff": recent_cutoff}
            )
            duplicate_blocks = result.scalar() or 0
        except Exception:
            duplicate_blocks = 0  # Audit log might not exist

        status = "healthy" if all_present else "unhealthy"

        return {
            "status": status,
            "constraints": constraint_status,
            "all_constraints_present": all_present,
            "duplicate_attempts_blocked_24h": duplicate_blocks,
            "constraint_effectiveness": 1.0 if all_present else 0.0,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_celery_health() -> Dict[str, Any]:
    """Check Celery workers and task queue health"""
    try:
        from app.celery_app import app as celery_app

        inspector = celery_app.control.inspect()

        # Get active workers
        active_workers = inspector.active()
        registered_tasks = inspector.registered()
        stats = inspector.stats()
        active_tasks = inspector.active()

        if not active_workers:
            return {
                "status": "unhealthy",
                "error": "No active Celery workers",
                "workers": 0,
                "active_tasks": 0,
            }

        # Calculate metrics
        num_workers = len(active_workers)
        total_active_tasks = (
            sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0
        )
        total_registered_tasks = (
            sum(len(tasks) for tasks in registered_tasks.values())
            if registered_tasks
            else 0
        )

        # Get queue lengths from Redis
        try:
            redis_client = await get_async_redis_client()
            queue_lengths = {}
            if redis_client:
                for queue in [
                    "celery",
                    "high_priority",
                    "low_priority",
                    "quiz_flow",
                    "alerts",
                    "whatsapp",
                    "reports",
                ]:
                    queue_key = f"celery:queue:{queue}"
                    length = await redis_client.llen(queue_key)
                    queue_lengths[queue] = length or 0

            total_queued = sum(queue_lengths.values())
        except Exception:
            queue_lengths = {}
            total_queued = 0

        # Determine status
        status = "healthy"
        if num_workers < 1:
            status = "unhealthy"
        elif total_queued > 1000:
            status = "degraded"

        return {
            "status": status,
            "workers": num_workers,
            "active_tasks": total_active_tasks,
            "registered_tasks": total_registered_tasks,
            "queue_lengths": queue_lengths,
            "total_queued": total_queued,
            "stats": stats,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Celery health check failed",
        }


@router.get("/health/celery")
async def celery_health_endpoint() -> Dict[str, Any]:
    """
    Detailed Celery health check endpoint.

    Returns:
        - Worker status and count
        - Active tasks
        - Queue lengths
        - Worker statistics
    """
    health = await check_celery_health()

    if health.get("status") == "unhealthy":
        raise HTTPException(status_code=503, detail=health)

    return health


@router.get("/health")
async def basic_health_check() -> Dict[str, str]:
    """Basic health check for load balancers"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
