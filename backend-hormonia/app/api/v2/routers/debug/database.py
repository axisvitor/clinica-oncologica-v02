"""
Database Debug & Diagnostics Endpoints

Endpoints:
- GET /database - Database connection and pool diagnostics
- POST /test-query - Test SQL query execution
"""

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import text

from app.database import get_db
from app.models.user import User
from app.utils.rate_limiter import limiter
from app.schemas.v2.debug import (
    DatabaseDiagnostics,
    DatabasePoolInfo,
    TestQueryRequest,
    TestQueryResult,
    DebugResponse,
    ConnectionStatus,
    DebugSeverity,
)

from .common import (
    check_debug_enabled,
    require_debug_enabled,
    get_admin_user,
    log_debug_operation,
    sanitize_sql_query,
)
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Database Diagnostics
# ============================================================================


@router.get(
    "/database",
    dependencies=[Depends(require_debug_enabled)],
    response_model=DebugResponse,
    summary="Get database diagnostics",
    description="""
    Get database connection and pool diagnostics.

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Checks:
    - Database connectivity
    - Connection pool status
    - Query response time
    """,
)
@limiter.limit("5/minute")
async def get_database_diagnostics(
    request: Request, admin_user: User = Depends(get_admin_user), db=Depends(get_db)
):
    """
    Get database connection diagnostics.

    Tests database connectivity, pool status, and response time.
    """
    check_debug_enabled()

    try:
        # Test database connection
        start_time = time.time()
        try:
            db.execute(text("SELECT 1"))
            response_time_ms = (time.time() - start_time) * 1000
            connected = True
            db_status = ConnectionStatus.HEALTHY
            error_msg = None
        except Exception as e:
            response_time_ms = None
            connected = False
            db_status = ConnectionStatus.UNHEALTHY
            error_msg = str(e)
            logger.error(f"Database connection test failed: {e}")

        # Get pool info if available
        pool_info = None
        try:
            engine = db.get_bind()
            pool = engine.pool
            pool_info = DatabasePoolInfo(
                size=pool.size(),
                checked_out=pool.checkedout(),
                overflow=pool.overflow(),
                checked_in=pool.checkedin(),
            )
        except Exception as e:
            logger.warning(f"Failed to get pool info: {e}")

        diagnostics = DatabaseDiagnostics(
            status=db_status,
            connected=connected,
            pool_info=pool_info,
            response_time_ms=response_time_ms,
            error=error_msg,
            timestamp=now_sao_paulo(),
        )

        # Audit log
        await log_debug_operation(
            db=db,
            admin_user=admin_user,
            endpoint="/database",
            parameters={},
            result_summary=f"Database {db_status.value}, {response_time_ms}ms response"
            if connected
            else "Database connection failed",
            request=request,
            severity=DebugSeverity.WARNING if not connected else DebugSeverity.INFO,
        )

        return DebugResponse(
            success=True,
            data=diagnostics.dict(),
            audit_logged=True,
            timestamp=now_sao_paulo(),
        )

    except Exception as e:
        logger.error(f"Database diagnostics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database diagnostics: {str(e)}",
        )


@router.post(
    "/test-query",
    dependencies=[Depends(require_debug_enabled)],
    response_model=DebugResponse,
    summary="Test SQL query execution",
    description="""
    Test SQL query execution (SELECT only).

    **ADMIN-ONLY** - Rate limited: 5 req/min

    Security:
    - Only SELECT queries allowed
    - Dangerous keywords blocked
    - Query timeout enforced
    - Results limited to 10 rows
    """,
)
@limiter.limit("5/minute")
async def test_sql_query(
    request: Request,
    query_request: TestQueryRequest,
    admin_user: User = Depends(get_admin_user),
    db=Depends(get_db),
):
    """
    Test SQL query execution with safety checks.

    Only SELECT queries are allowed.
    Results are limited to prevent data exposure.
    """
    check_debug_enabled()

    try:
        # Execute query with timeout
        start_time = time.time()
        try:
            # Validate and set statement timeout (prevent SQL injection via timeout value)
            # PostgreSQL statement_timeout is in milliseconds, max 1 hour for safety
            timeout_ms = int(query_request.timeout_seconds * 1000)
            if timeout_ms < 100 or timeout_ms > 3600000:  # 100ms to 1 hour
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Timeout must be between 0.1 and 3600 seconds"
                )
            # Use set_config with parameter binding to avoid SQL interpolation.
            db.execute(
                text("SELECT set_config('statement_timeout', :statement_timeout, true)"),
                {"statement_timeout": f"{timeout_ms}ms"},
            )

            # Execute query
            result = db.execute(text(query_request.query))
            rows = result.fetchmany(10)  # Limit to 10 rows
            execution_time_ms = (time.time() - start_time) * 1000

            # Convert rows to dicts
            if rows:
                columns = result.keys()
                result_data = [dict(zip(columns, row)) for row in rows]
            else:
                result_data = []

            test_result = TestQueryResult(
                success=True,
                rows_returned=len(rows),
                execution_time_ms=execution_time_ms,
                result=result_data,
                error=None,
                query_sanitized=sanitize_sql_query(query_request.query),
            )

            # Audit log
            await log_debug_operation(
                db=db,
                admin_user=admin_user,
                endpoint="/test-query",
                parameters={"query": sanitize_sql_query(query_request.query, 50)},
                result_summary=f"Query executed: {len(rows)} rows, {execution_time_ms:.2f}ms",
                request=request,
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            test_result = TestQueryResult(
                success=False,
                rows_returned=None,
                execution_time_ms=execution_time_ms,
                result=None,
                error=str(e),
                query_sanitized=sanitize_sql_query(query_request.query),
            )

            # Audit log error
            await log_debug_operation(
                db=db,
                admin_user=admin_user,
                endpoint="/test-query",
                parameters={"query": sanitize_sql_query(query_request.query, 50)},
                result_summary=f"Query failed: {str(e)}",
                request=request,
                severity=DebugSeverity.WARNING,
            )

        return DebugResponse(
            success=test_result.success,
            data=test_result.dict(),
            audit_logged=True,
            timestamp=now_sao_paulo(),
        )

    except Exception as e:
        logger.error(f"Test query error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test query: {str(e)}",
        )
