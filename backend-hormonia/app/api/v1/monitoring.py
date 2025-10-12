"""
Monitoring and alerting endpoints for critical system health.

This module provides endpoints for monitoring error tracking metrics,
health checks for critical fixes, and alerting configuration.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.database import get_db
from app.core.error_handler import error_handler
from app.models.error_tracking import ErrorLog
from app.models.user import User, UserRole
from app.dependencies.auth_dependencies import get_current_user
from app.dependencies import get_thread_safe_service_provider
from app.core.date_utils import coerce_to_date


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health/critical-fixes")
async def check_critical_fixes_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Health check endpoint that validates critical fixes are working.
    
    Checks:
    - Dependency injection is working correctly
    - Role enum comparisons are functioning
    - Database schema compatibility
    - Date parameter handling
    - Error tracking system
    
    Returns:
        Dictionary with health status of each critical fix
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "overall_status": "healthy",
        "checks": {}
    }
    
    # Check 1: Dependency Injection
    try:
        provider = get_thread_safe_service_provider()
        provider_instance = next(provider)
        
        # Verify provider has expected services
        has_monthly_quiz = hasattr(provider_instance, 'monthly_quiz_service')
        has_quiz_service = hasattr(provider_instance, 'quiz_service')
        is_not_generator = not hasattr(provider_instance, '__next__')
        
        health_status["checks"]["dependency_injection"] = {
            "status": "healthy" if (has_monthly_quiz and has_quiz_service and is_not_generator) else "unhealthy",
            "details": {
                "has_monthly_quiz_service": has_monthly_quiz,
                "has_quiz_service": has_quiz_service,
                "is_not_generator": is_not_generator
            }
        }
    except Exception as e:
        health_status["checks"]["dependency_injection"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall_status"] = "unhealthy"
    
    # Check 2: Role Enum System
    try:
        # Test role enum comparison
        admin_role = UserRole.ADMIN
        role_comparison_works = (admin_role == UserRole.ADMIN)
        enum_values_exist = hasattr(UserRole, 'ADMIN') and hasattr(UserRole, 'DOCTOR')
        
        health_status["checks"]["role_enum_system"] = {
            "status": "healthy" if (role_comparison_works and enum_values_exist) else "unhealthy",
            "details": {
                "role_comparison_works": role_comparison_works,
                "enum_values_exist": enum_values_exist,
                "available_roles": [role.value for role in UserRole]
            }
        }
    except Exception as e:
        health_status["checks"]["role_enum_system"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall_status"] = "unhealthy"
    
    # Check 3: Database Schema Compatibility
    try:
        # Test basic database operations
        error_count = db.query(ErrorLog).count()
        
        # Test alerts table compatibility (if it exists)
        try:
            from app.models.alert import Alert
            alert_count = db.query(Alert).count()
            alerts_compatible = True
        except Exception:
            alert_count = None
            alerts_compatible = False
        
        health_status["checks"]["database_schema"] = {
            "status": "healthy" if alerts_compatible else "warning",
            "details": {
                "error_logs_accessible": True,
                "error_log_count": error_count,
                "alerts_compatible": alerts_compatible,
                "alert_count": alert_count
            }
        }
    except Exception as e:
        health_status["checks"]["database_schema"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall_status"] = "unhealthy"
    
    # Check 4: Date Parameter Handling
    try:
        from app.core.date_utils import coerce_to_date
        
        # Test various date formats
        test_cases = [
            ("2025-10-05T15:01:57.695Z", True),
            ("2025-10-05", True),
            (None, True),
            ("invalid-date", False)
        ]
        
        date_handling_works = True
        test_results = []
        
        for test_input, should_succeed in test_cases:
            try:
                result = coerce_to_date(test_input)
                test_results.append({
                    "input": test_input,
                    "success": True,
                    "result": result.isoformat() if result else None
                })
            except Exception as e:
                if should_succeed:
                    date_handling_works = False
                test_results.append({
                    "input": test_input,
                    "success": False,
                    "error": str(e)
                })
        
        health_status["checks"]["date_parameter_handling"] = {
            "status": "healthy" if date_handling_works else "unhealthy",
            "details": {
                "test_results": test_results
            }
        }
    except Exception as e:
        health_status["checks"]["date_parameter_handling"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall_status"] = "unhealthy"
    
    # Check 5: Error Tracking System
    try:
        error_stats = error_handler.get_error_stats()
        
        # Check recent error activity
        recent_errors = db.query(ErrorLog).filter(
            ErrorLog.last_seen >= datetime.utcnow() - timedelta(hours=1)
        ).count()
        
        health_status["checks"]["error_tracking"] = {
            "status": "healthy",
            "details": {
                "error_handler_stats": error_stats,
                "recent_errors_count": recent_errors,
                "tracking_enabled": error_handler.enable_tracking
            }
        }
    except Exception as e:
        health_status["checks"]["error_tracking"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall_status"] = "unhealthy"
    
    return health_status


@router.get("/errors/metrics")
async def get_error_metrics(
    hours: int = Query(24, description="Hours to look back for error metrics"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get error tracking metrics for monitoring and alerting.
    
    Args:
        hours: Number of hours to look back for metrics
        
    Returns:
        Dictionary with error metrics and statistics
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    # Get error counts by type
    error_type_counts = db.query(
        ErrorLog.error_type,
        func.count(ErrorLog.id).label('count'),
        func.sum(ErrorLog.count).label('total_occurrences')
    ).filter(
        ErrorLog.last_seen >= cutoff_time
    ).group_by(ErrorLog.error_type).all()
    
    # Get error counts by severity
    severity_counts = db.query(
        ErrorLog.severity,
        func.count(ErrorLog.id).label('count'),
        func.sum(ErrorLog.count).label('total_occurrences')
    ).filter(
        ErrorLog.last_seen >= cutoff_time
    ).group_by(ErrorLog.severity).all()
    
    # Get most frequent errors
    frequent_errors = db.query(ErrorLog).filter(
        ErrorLog.last_seen >= cutoff_time
    ).order_by(desc(ErrorLog.count)).limit(10).all()
    
    # Get recent critical errors
    critical_errors = db.query(ErrorLog).filter(
        ErrorLog.last_seen >= cutoff_time,
        ErrorLog.severity == 'CRITICAL'
    ).order_by(desc(ErrorLog.last_seen)).limit(5).all()
    
    # Calculate error rates
    total_errors = sum(row.total_occurrences for row in error_type_counts)
    error_rate_per_hour = total_errors / hours if hours > 0 else 0
    
    # Get error handler statistics
    handler_stats = error_handler.get_error_stats()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "time_window_hours": hours,
        "summary": {
            "total_error_types": len(error_type_counts),
            "total_error_occurrences": total_errors,
            "error_rate_per_hour": round(error_rate_per_hour, 2),
            "critical_errors_count": len(critical_errors)
        },
        "error_types": [
            {
                "type": row.error_type,
                "unique_errors": row.count,
                "total_occurrences": row.total_occurrences
            }
            for row in error_type_counts
        ],
        "severity_breakdown": [
            {
                "severity": row.severity,
                "unique_errors": row.count,
                "total_occurrences": row.total_occurrences
            }
            for row in severity_counts
        ],
        "most_frequent_errors": [
            {
                "id": str(error.id),
                "type": error.error_type,
                "message": error.error_message[:100] + "..." if len(error.error_message) > 100 else error.error_message,
                "count": error.count,
                "severity": error.severity,
                "first_seen": error.first_seen.isoformat(),
                "last_seen": error.last_seen.isoformat()
            }
            for error in frequent_errors
        ],
        "recent_critical_errors": [
            {
                "id": str(error.id),
                "type": error.error_type,
                "message": error.error_message[:100] + "..." if len(error.error_message) > 100 else error.error_message,
                "count": error.count,
                "last_seen": error.last_seen.isoformat(),
                "context": error.context
            }
            for error in critical_errors
        ],
        "error_handler_stats": handler_stats
    }


@router.get("/errors/{error_id}")
async def get_error_details(
    error_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific error.
    
    Args:
        error_id: UUID of the error log entry
        
    Returns:
        Detailed error information
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    error_log = db.query(ErrorLog).filter(ErrorLog.id == error_id).first()
    if not error_log:
        raise HTTPException(status_code=404, detail="Error not found")
    
    return {
        "id": str(error_log.id),
        "error_type": error_log.error_type,
        "error_message": error_log.error_message,
        "severity": error_log.severity,
        "count": error_log.count,
        "first_seen": error_log.first_seen.isoformat(),
        "last_seen": error_log.last_seen.isoformat(),
        "resolved": error_log.resolved,
        "context": error_log.context,
        "stack_trace": error_log.stack_trace
    }


@router.post("/errors/{error_id}/resolve")
async def resolve_error(
    error_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Mark an error as resolved.
    
    Args:
        error_id: UUID of the error log entry
        
    Returns:
        Updated error information
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    error_log = db.query(ErrorLog).filter(ErrorLog.id == error_id).first()
    if not error_log:
        raise HTTPException(status_code=404, detail="Error not found")
    
    error_log.resolved = True
    db.commit()
    
    logger.info(f"Error {error_id} marked as resolved by user {current_user.id}")
    
    return {
        "id": str(error_log.id),
        "resolved": error_log.resolved,
        "message": "Error marked as resolved"
    }


@router.get("/alerts/configuration")
async def get_alert_configuration(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current alerting configuration for critical error patterns.
    
    Returns:
        Current alert configuration and thresholds
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return {
        "error_rate_thresholds": {
            "critical_errors_per_hour": 5,
            "total_errors_per_hour": 50,
            "dependency_injection_errors_per_hour": 3,
            "role_enum_errors_per_hour": 10,
            "schema_mismatch_errors_per_hour": 2
        },
        "alert_channels": {
            "email_enabled": True,
            "webhook_enabled": False,
            "log_alerts": True
        },
        "monitoring_intervals": {
            "health_check_minutes": 5,
            "error_metrics_minutes": 15,
            "critical_error_immediate": True
        },
        "error_handler_config": {
            "max_errors_per_hour": error_handler.max_errors_per_hour,
            "tracking_enabled": error_handler.enable_tracking,
            "rate_limiting_enabled": True
        }
    }


@router.get("/system/status")
async def get_system_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get overall system status including critical fixes health.
    
    Returns:
        Comprehensive system status information
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get critical fixes health
    health_check = await check_critical_fixes_health(current_user, db)
    
    # Get recent error summary
    recent_errors = db.query(ErrorLog).filter(
        ErrorLog.last_seen >= datetime.utcnow() - timedelta(hours=1)
    ).count()
    
    critical_errors = db.query(ErrorLog).filter(
        ErrorLog.last_seen >= datetime.utcnow() - timedelta(hours=1),
        ErrorLog.severity == 'CRITICAL'
    ).count()
    
    # Determine overall system health
    system_healthy = (
        health_check["overall_status"] == "healthy" and
        critical_errors == 0 and
        recent_errors < 10
    )
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system_status": "healthy" if system_healthy else "degraded",
        "critical_fixes_health": health_check,
        "error_summary": {
            "recent_errors_1h": recent_errors,
            "critical_errors_1h": critical_errors,
            "error_tracking_active": error_handler.enable_tracking
        },
        "recommendations": _get_system_recommendations(health_check, recent_errors, critical_errors)
    }


def _get_system_recommendations(
    health_check: Dict[str, Any],
    recent_errors: int,
    critical_errors: int
) -> List[str]:
    """
    Generate system recommendations based on current status.
    
    Args:
        health_check: Results from critical fixes health check
        recent_errors: Number of recent errors
        critical_errors: Number of critical errors
        
    Returns:
        List of recommendations for system improvement
    """
    recommendations = []
    
    # Check individual health components
    for check_name, check_result in health_check.get("checks", {}).items():
        if check_result.get("status") == "unhealthy":
            if check_name == "dependency_injection":
                recommendations.append("Fix dependency injection system - service provider not working correctly")
            elif check_name == "role_enum_system":
                recommendations.append("Fix role enum system - enum comparisons failing")
            elif check_name == "database_schema":
                recommendations.append("Fix database schema compatibility issues")
            elif check_name == "date_parameter_handling":
                recommendations.append("Fix date parameter handling in API endpoints")
            elif check_name == "error_tracking":
                recommendations.append("Fix error tracking system")
    
    # Check error levels
    if critical_errors > 0:
        recommendations.append(f"Investigate {critical_errors} critical errors in the last hour")
    
    if recent_errors > 20:
        recommendations.append(f"High error rate detected: {recent_errors} errors in the last hour")
    
    # General recommendations
    if not recommendations:
        recommendations.append("System is healthy - continue monitoring")
    
    return recommendations