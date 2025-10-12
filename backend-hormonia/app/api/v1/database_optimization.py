"""
Database Optimization API endpoints.
Provides database index analysis and optimization capabilities.
"""
import logging
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.services.database_index_optimizer import DatabaseIndexOptimizer
from app.services.query_performance_monitor import QueryPerformanceMonitor
from app.core.monitoring_logging import monitoring_logger


logger = logging.getLogger(__name__)
router = APIRouter(tags=["database-optimization"])


@router.get(
    "/indexes/analysis",
    response_model=None,
    summary="Analyze database indexes",
    description="Analyze current database indexes and identify optimization opportunities"
)
async def analyze_database_indexes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Analyze database indexes and provide optimization recommendations."""
    # Only admins can access database optimization
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )
    
    try:
        optimizer = DatabaseIndexOptimizer(db)
        analysis = optimizer.analyze_indexes()
        
        # Convert dataclasses to dictionaries for JSON response
        response = {
            "existing_indexes": analysis.existing_indexes,
            "missing_indexes": [
                {
                    "table_name": rec.table_name,
                    "columns": rec.columns,
                    "index_type": rec.index_type,
                    "reason": rec.reason,
                    "estimated_benefit": rec.estimated_benefit,
                    "query_patterns": rec.query_patterns,
                    "existing_index": rec.existing_index
                }
                for rec in analysis.missing_indexes
            ],
            "redundant_indexes": analysis.redundant_indexes,
            "performance_impact": analysis.performance_impact
        }
        
        monitoring_logger.log_system_event(
            event_type="database_index_analysis_requested",
            message="Database index analysis requested by admin",
            level="INFO",
            context={
                "admin_user_id": str(current_user.id),
                "missing_indexes_count": len(analysis.missing_indexes),
                "redundant_indexes_count": len(analysis.redundant_indexes)
            }
        )
        
        logger.info(f"Database index analysis completed for admin {current_user.id}")
        return response
        
    except Exception as e:
        logger.error(f"Error analyzing database indexes: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to analyze database indexes"
        )


@router.post(
    "/indexes/create",
    response_model=None,
    summary="Create recommended indexes",
    description="Create recommended database indexes to improve performance"
)
async def create_recommended_indexes(
    dry_run: bool = Query(True, description="If true, only return SQL without executing"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create recommended database indexes."""
    # Only admins can create indexes
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )
    
    try:
        optimizer = DatabaseIndexOptimizer(db)
        analysis = optimizer.analyze_indexes()
        
        # Create only high-benefit indexes to avoid over-indexing
        high_benefit_indexes = [
            rec for rec in analysis.missing_indexes 
            if rec.estimated_benefit == "high"
        ]
        
        sql_statements = optimizer.create_recommended_indexes(
            high_benefit_indexes, 
            dry_run=dry_run
        )
        
        monitoring_logger.log_system_event(
            event_type="database_indexes_creation_requested",
            message=f"Database index creation requested by admin (dry_run: {dry_run})",
            level="WARNING" if not dry_run else "INFO",
            context={
                "admin_user_id": str(current_user.id),
                "dry_run": dry_run,
                "indexes_count": len(high_benefit_indexes),
                "sql_statements_count": len(sql_statements)
            }
        )
        
        logger.info(
            f"Database index creation {'simulated' if dry_run else 'executed'} "
            f"by admin {current_user.id}: {len(sql_statements)} statements"
        )
        
        return {
            "success": True,
            "dry_run": dry_run,
            "indexes_created": len(high_benefit_indexes),
            "sql_statements": sql_statements,
            "recommendations": [
                {
                    "table_name": rec.table_name,
                    "columns": rec.columns,
                    "reason": rec.reason
                }
                for rec in high_benefit_indexes
            ]
        }
        
    except Exception as e:
        logger.error(f"Error creating database indexes: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create database indexes"
        )


@router.get(
    "/indexes/usage",
    response_model=None,
    summary="Get index usage statistics",
    description="Get database index usage statistics and performance metrics"
)
async def get_index_usage_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get database index usage statistics."""
    # Only admins can access index usage stats
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )
    
    try:
        optimizer = DatabaseIndexOptimizer(db)
        usage_stats = optimizer.get_index_usage_stats()
        
        logger.info(f"Index usage statistics retrieved by admin {current_user.id}")
        return usage_stats
        
    except Exception as e:
        logger.error(f"Error getting index usage statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve index usage statistics"
        )


@router.get(
    "/queries/slow-analysis",
    response_model=None,
    summary="Analyze slow queries for index recommendations",
    description="Analyze slow queries and recommend indexes to improve performance"
)
async def analyze_slow_queries_for_indexes(
    hours_back: int = Query(1, ge=1, le=24, description="Hours of slow queries to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Analyze slow queries and recommend indexes."""
    # Only admins can access slow query analysis
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )
    
    try:
        # Get slow queries from performance monitor
        query_monitor = QueryPerformanceMonitor(db)
        slow_queries = query_monitor.identify_slow_queries(limit=50)
        
        # Extract query texts
        query_texts = [q.query_text for q in slow_queries]
        
        # Analyze for index recommendations
        optimizer = DatabaseIndexOptimizer(db)
        recommendations = optimizer.analyze_slow_queries_for_indexes(query_texts)
        
        # Get query analysis
        query_analysis = query_monitor.get_query_analysis(hours_back)
        
        response = {
            "slow_queries_analyzed": len(query_texts),
            "index_recommendations": [
                {
                    "table_name": rec.table_name,
                    "columns": rec.columns,
                    "index_type": rec.index_type,
                    "reason": rec.reason,
                    "estimated_benefit": rec.estimated_benefit,
                    "query_patterns": rec.query_patterns
                }
                for rec in recommendations
            ],
            "query_analysis": query_analysis,
            "analysis_period_hours": hours_back
        }
        
        monitoring_logger.log_system_event(
            event_type="slow_query_index_analysis",
            message="Slow query index analysis completed",
            level="INFO",
            context={
                "admin_user_id": str(current_user.id),
                "slow_queries_count": len(query_texts),
                "recommendations_count": len(recommendations),
                "hours_analyzed": hours_back
            }
        )
        
        logger.info(
            f"Slow query analysis completed by admin {current_user.id}: "
            f"{len(query_texts)} queries, {len(recommendations)} recommendations"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error analyzing slow queries for indexes: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to analyze slow queries for indexes"
        )


@router.get(
    "/performance/summary",
    response_model=None,
    summary="Get database performance summary",
    description="Get comprehensive database performance summary with optimization recommendations"
)
async def get_database_performance_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get comprehensive database performance summary."""
    # Only admins can access performance summary
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )
    
    try:
        # Get query performance metrics
        query_monitor = QueryPerformanceMonitor(db)
        query_metrics = query_monitor.get_performance_metrics()
        query_analysis = query_monitor.get_query_analysis(hours_back=1)
        
        # Get index analysis
        optimizer = DatabaseIndexOptimizer(db)
        index_analysis = optimizer.analyze_indexes()
        index_usage = optimizer.get_index_usage_stats()
        
        # Generate overall recommendations
        recommendations = []
        
        # Query performance recommendations
        if query_metrics.slow_queries > 0:
            recommendations.append(
                f"Found {query_metrics.slow_queries} slow queries - consider index optimization"
            )
        
        # Index recommendations
        if len(index_analysis.missing_indexes) > 0:
            recommendations.append(
                f"Found {len(index_analysis.missing_indexes)} missing indexes for analytics queries"
            )
        
        if len(index_analysis.redundant_indexes) > 0:
            recommendations.append(
                f"Found {len(index_analysis.redundant_indexes)} potentially redundant indexes"
            )
        
        # Overall health score (0-100)
        health_score = 100
        if query_metrics.slow_queries > 10:
            health_score -= 20
        if len(index_analysis.missing_indexes) > 5:
            health_score -= 15
        if query_metrics.avg_duration_ms > 100:
            health_score -= 10
        
        health_score = max(0, health_score)
        
        response = {
            "health_score": health_score,
            "query_performance": {
                "total_queries": query_metrics.total_queries,
                "slow_queries": query_metrics.slow_queries,
                "avg_duration_ms": query_metrics.avg_duration_ms,
                "max_duration_ms": query_metrics.max_duration_ms,
                "queries_per_second": query_metrics.queries_per_second
            },
            "index_status": {
                "missing_indexes": len(index_analysis.missing_indexes),
                "redundant_indexes": len(index_analysis.redundant_indexes),
                "total_indexes": sum(len(indexes) for indexes in index_analysis.existing_indexes.values())
            },
            "recommendations": recommendations,
            "detailed_analysis": {
                "query_analysis": query_analysis,
                "index_usage": index_usage
            }
        }
        
        logger.info(f"Database performance summary retrieved by admin {current_user.id}")
        return response
        
    except Exception as e:
        logger.error(f"Error getting database performance summary: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve database performance summary"
        )