"""
RLS Health Check API endpoints.

Provides comprehensive health monitoring for Row Level Security implementation.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from app.dependencies.auth_dependencies import get_current_user
from app.dependencies.rls_dependencies import get_rls_db, test_rls_connection
from app.database import get_db
from app.models.user import UserRole, User
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/health/rls",
    tags=["health", "monitoring"],
    responses={404: {"description": "Not found"}},
)


@router.get("/status", response_model=Dict[str, Any])
async def get_rls_status(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current RLS status and configuration.

    Returns information about:
    - RLS configuration settings
    - Tables with RLS enabled
    - Policy count and distribution
    - Current rollout phase
    """
    try:
        # Check RLS configuration
        config = {
            "use_service_role": settings.SUPABASE_USE_SERVICE_ROLE,
            "bypass_rls": settings.SUPABASE_BYPASS_RLS,
            "environment": settings.ENVIRONMENT,
            "phase": getattr(settings, 'DEPLOYMENT_RLS_PHASE', 1)
        }

        # Query RLS status from database
        rls_status_query = text("""
            SELECT
                t.tablename,
                t.rowsecurity as rls_enabled,
                COUNT(p.policyname) as policy_count
            FROM pg_tables t
            LEFT JOIN pg_policies p ON t.tablename = p.tablename AND t.schemaname = p.schemaname
            WHERE t.schemaname = 'public'
            AND t.tablename IN (
                'users', 'patients', 'messages', 'medical_reports',
                'flow_states', 'quiz_sessions', 'quiz_responses'
            )
            GROUP BY t.tablename, t.rowsecurity
            ORDER BY t.tablename
        """)

        result = db.execute(rls_status_query)
        tables = []
        for row in result:
            tables.append({
                "table": row[0],
                "rls_enabled": row[1],
                "policy_count": row[2]
            })

        # Count total policies by type
        policy_count_query = text("""
            SELECT
                cmd as operation,
                COUNT(*) as count
            FROM pg_policies
            WHERE schemaname = 'public'
            GROUP BY cmd
        """)

        policy_result = db.execute(policy_count_query)
        policies = {}
        for row in policy_result:
            policies[row[0].lower()] = row[1]

        # Calculate health score
        total_tables = len(tables)
        enabled_tables = sum(1 for t in tables if t['rls_enabled'])
        total_policies = sum(policies.values())

        health_score = 0
        if enabled_tables > 0:
            health_score += 40 * (enabled_tables / total_tables)
        if total_policies > 0:
            health_score += 30 * min(1.0, total_policies / 20)
        if policies.get('select', 0) > 0:
            health_score += 10
        if policies.get('insert', 0) > 0:
            health_score += 10
        if policies.get('update', 0) > 0:
            health_score += 5
        if policies.get('delete', 0) > 0:
            health_score += 5

        status = "healthy" if health_score >= 70 else "warning" if health_score >= 40 else "critical"

        return {
            "status": status,
            "health_score": round(health_score, 2),
            "configuration": config,
            "tables": tables,
            "policies": policies,
            "summary": {
                "total_tables": total_tables,
                "rls_enabled_tables": enabled_tables,
                "total_policies": total_policies,
                "coverage_percentage": round((enabled_tables / total_tables * 100) if total_tables > 0 else 0, 2)
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting RLS status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving RLS status"
        )


@router.get("/performance", response_model=Dict[str, Any])
async def get_rls_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get RLS performance metrics.

    Requires admin role.
    Returns query performance statistics for RLS-protected tables.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        # Get query performance metrics
        performance_query = text("""
            SELECT
                LEFT(query, 100) as query_preview,
                calls,
                ROUND(mean_exec_time::numeric, 2) as avg_ms,
                ROUND(max_exec_time::numeric, 2) as max_ms,
                ROUND(min_exec_time::numeric, 2) as min_ms,
                rows as avg_rows
            FROM pg_stat_statements
            WHERE (
                query LIKE '%patients%'
                OR query LIKE '%messages%'
                OR query LIKE '%quiz_sessions%'
                OR query LIKE '%auth.uid()%'
            )
            AND query NOT LIKE '%pg_stat_statements%'
            ORDER BY mean_exec_time DESC
            LIMIT 10
        """)

        queries = []
        try:
            result = db.execute(performance_query)
            for row in result:
                queries.append({
                    "query": row[0],
                    "calls": row[1],
                    "avg_ms": float(row[2]) if row[2] else 0,
                    "max_ms": float(row[3]) if row[3] else 0,
                    "min_ms": float(row[4]) if row[4] else 0,
                    "avg_rows": row[5]
                })
        except:
            # pg_stat_statements might not be enabled
            queries = []

        # Get connection pool stats
        connection_query = text("""
            SELECT
                COUNT(*) as total_connections,
                COUNT(*) FILTER (WHERE state = 'active') as active,
                COUNT(*) FILTER (WHERE state = 'idle') as idle,
                COUNT(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                MAX(EXTRACT(EPOCH FROM (NOW() - state_change))) as max_idle_seconds
            FROM pg_stat_activity
            WHERE datname = current_database()
        """)

        conn_result = db.execute(connection_query).first()
        connections = {
            "total": conn_result[0],
            "active": conn_result[1],
            "idle": conn_result[2],
            "idle_in_transaction": conn_result[3],
            "max_idle_seconds": float(conn_result[4]) if conn_result[4] else 0
        }

        # Calculate performance health
        slow_queries = sum(1 for q in queries if q['avg_ms'] > 1000)
        performance_score = 100
        if slow_queries > 0:
            performance_score -= (slow_queries * 10)
        if connections['idle_in_transaction'] > 5:
            performance_score -= 20
        if connections['max_idle_seconds'] > 300:
            performance_score -= 10

        return {
            "status": "healthy" if performance_score >= 70 else "degraded" if performance_score >= 40 else "critical",
            "performance_score": max(0, performance_score),
            "queries": queries,
            "connections": connections,
            "metrics": {
                "slow_query_count": slow_queries,
                "avg_query_time": sum(q['avg_ms'] for q in queries) / len(queries) if queries else 0,
                "connection_utilization": (connections['active'] / connections['total'] * 100) if connections['total'] > 0 else 0
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting RLS performance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving performance metrics"
        )


@router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_rls_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    alerts = []

    try:
        # Check for slow queries
        slow_query_check = text("""
            SELECT COUNT(*) as count
            FROM pg_stat_statements
            WHERE mean_exec_time > 2000
            AND calls > 10
        """)

        try:
            result = db.execute(slow_query_check).first()
            if result[0] > 0:
                alerts.append({
                    "level": "critical",
                    "type": "performance",
                    "message": f"{result[0]} queries exceeding 2s threshold",
                    "action": "Review and optimize slow queries"
                })
        except:
            pass

        # Check for stuck connections
        stuck_conn_check = text("""
            SELECT COUNT(*) as count
            FROM pg_stat_activity
            WHERE state = 'idle in transaction'
            AND NOW() - state_change > INTERVAL '5 minutes'
        """)

        result = db.execute(stuck_conn_check).first()
        if result[0] > 0:
            alerts.append({
                "level": "warning",
                "type": "connections",
                "message": f"{result[0]} connections stuck in transaction",
                "action": "Review application transaction handling"
            })

        # Check for missing RLS
        missing_rls_check = text("""
            SELECT COUNT(*) as count
            FROM pg_tables
            WHERE schemaname = 'public'
            AND rowsecurity = false
            AND tablename IN (
                'users', 'patients', 'messages', 'medical_reports',
                'flow_states', 'quiz_sessions', 'quiz_responses'
            )
        """)

        result = db.execute(missing_rls_check).first()
        if result[0] > 0:
            alerts.append({
                "level": "warning",
                "type": "security",
                "message": f"{result[0]} tables without RLS enabled",
                "action": "Enable RLS on remaining tables"
            })

        # Check for tables with RLS but no policies
        no_policy_check = text("""
            SELECT t.tablename
            FROM pg_tables t
            LEFT JOIN pg_policies p ON t.tablename = p.tablename
            WHERE t.schemaname = 'public'
            AND t.rowsecurity = true
            AND p.policyname IS NULL
        """)

        result = db.execute(no_policy_check)
        tables_without_policies = [row[0] for row in result]
        if tables_without_policies:
            alerts.append({
                "level": "critical",
                "type": "security",
                "message": f"Tables with RLS but no policies: {', '.join(tables_without_policies)}",
                "action": "Add policies to these tables immediately"
            })

        # Add informational alert if everything is good
        if not alerts:
            alerts.append({
                "level": "info",
                "type": "system",
                "message": "No RLS issues detected",
                "action": "Continue monitoring"
            })

        return alerts

    except Exception as e:
        logger.error(f"Error getting RLS alerts: {str(e)}")
        return [{
            "level": "error",
            "type": "system",
            "message": f"Error checking alerts: {str(e)}",
            "action": "Check system logs"
        }]


@router.get("/verify", response_model=Dict[str, Any])
async def verify_rls_context(
    db_rls: Session = Depends(get_rls_db),
    db_normal: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Verify RLS context is working correctly.

    Tests that RLS context is properly set and functioning.
    """
    try:
        # Test RLS connection
        rls_status = test_rls_connection(db_rls) if current_user else {"rls_ready": False}

        # Test normal connection
        normal_query = text("SELECT current_setting('request.jwt.claims', true)")
        normal_result = db_normal.execute(normal_query).first()
        normal_claims = normal_result[0] if normal_result and normal_result[0] else None

        # Test auth functions if available
        auth_test = {}
        if rls_status.get("rls_ready"):
            try:
                uid_result = db_rls.execute(text("SELECT auth.uid()")).first()
                role_result = db_rls.execute(text("SELECT auth.role()")).first()
                auth_test = {
                    "uid": str(uid_result[0]) if uid_result and uid_result[0] else None,
                    "role": role_result[0] if role_result and role_result[0] else None
                }
            except:
                auth_test = {"error": "Auth functions not available"}

        # Compare patient counts if user is authenticated
        comparison = {}
        if current_user:
            try:
                # Count with RLS
                from app.models.patient import Patient
                rls_count = db_rls.query(Patient).count()

                # Count without RLS (if bypass enabled)
                normal_count = db_normal.query(Patient).count() if settings.SUPABASE_BYPASS_RLS else None

                comparison = {
                    "rls_patient_count": rls_count,
                    "normal_patient_count": normal_count,
                    "filtering_active": normal_count is None or rls_count < normal_count if current_user.role != UserRole.ADMIN else True
                }
            except Exception as e:
                comparison = {"error": str(e)}

        return {
            "rls_context": rls_status,
            "normal_context": {"has_claims": bool(normal_claims)},
            "auth_functions": auth_test,
            "comparison": comparison,
            "user": {
                "id": str(current_user.id) if current_user else None,
                "email": current_user.email if current_user else None,
                "role": current_user.role if current_user else None
            },
            "configuration": {
                "bypass_enabled": settings.SUPABASE_BYPASS_RLS,
                "service_role": settings.SUPABASE_USE_SERVICE_ROLE,
                "environment": settings.ENVIRONMENT
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error verifying RLS context: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error verifying RLS context"
        )


@router.get("/readiness", response_model=Dict[str, Any])
async def check_rls_readiness(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Check if system is ready for next RLS phase.

    Requires admin role.
    Evaluates current state and provides recommendations.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        current_phase = getattr(settings, 'DEPLOYMENT_RLS_PHASE', 1)

        # Check criteria for current phase
        criteria = {}
        recommendations = []

        if current_phase == 1:
            # Phase 1: Read-only policies
            criteria = {
                "tables_with_rls": {"required": 7, "current": 0},
                "select_policies": {"required": 7, "current": 0},
                "performance_degradation": {"max": 20, "current": 0},
                "error_rate": {"max": 0.1, "current": 0}
            }

            # Count tables with RLS
            rls_count = db.execute(text("""
                SELECT COUNT(*) FROM pg_tables
                WHERE schemaname = 'public' AND rowsecurity = true
            """)).first()[0]
            criteria["tables_with_rls"]["current"] = rls_count

            # Count SELECT policies
            select_count = db.execute(text("""
                SELECT COUNT(*) FROM pg_policies
                WHERE schemaname = 'public' AND cmd = 'SELECT'
            """)).first()[0]
            criteria["select_policies"]["current"] = select_count

            # Check if ready for Phase 2
            if rls_count >= 7 and select_count >= 7:
                recommendations.append("✅ Ready to proceed to Phase 2 (write policies)")
            else:
                recommendations.append(f"⚠️ Complete Phase 1: Enable RLS on {7 - rls_count} more tables")

        elif current_phase == 2:
            # Phase 2: Write policies
            criteria = {
                "insert_policies": {"required": 7, "current": 0},
                "update_policies": {"required": 7, "current": 0},
                "delete_policies": {"required": 7, "current": 0},
                "audit_logging": {"required": True, "current": False}
            }

            # Count write policies
            for cmd in ['INSERT', 'UPDATE', 'DELETE']:
                count = db.execute(text(f"""
                    SELECT COUNT(*) FROM pg_policies
                    WHERE schemaname = 'public' AND cmd = '{cmd}'
                """)).first()[0]
                criteria[f"{cmd.lower()}_policies"]["current"] = count

            # Check audit logging
            audit_exists = db.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'audit_logs'
                )
            """)).first()[0]
            criteria["audit_logging"]["current"] = audit_exists

            # Recommendations
            if all(c["current"] >= c.get("required", 0) for c in criteria.values() if isinstance(c, dict)):
                recommendations.append("✅ Ready to proceed to Phase 3 (full coverage)")
            else:
                recommendations.append("⚠️ Complete Phase 2: Add remaining write policies")

        # Calculate readiness score
        total_criteria = len(criteria)
        met_criteria = sum(
            1 for c in criteria.values()
            if isinstance(c, dict) and c["current"] >= c.get("required", c.get("max", 0))
        )
        readiness_score = (met_criteria / total_criteria * 100) if total_criteria > 0 else 0

        return {
            "current_phase": current_phase,
            "next_phase": current_phase + 1 if current_phase < 4 else "Complete",
            "readiness_score": round(readiness_score, 2),
            "ready_for_next": readiness_score >= 90,
            "criteria": criteria,
            "recommendations": recommendations,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error checking RLS readiness: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking readiness"
        )


# Export router
__all__ = ["router"]