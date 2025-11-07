"""
Dashboard API endpoints for real-time metrics and data visualization
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, desc
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.utils.logging import get_logger

router = APIRouter(tags=["dashboard"])  # Prefix removed - set in router_registry.py
logger = get_logger(__name__)


@router.get("/metrics")
async def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get key dashboard metrics including patients, messages, flows, and alerts
    """
    try:
        # Get current date ranges
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Patient metrics
        total_patients_query = db.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN is_active = true THEN 1 END) as active,
                   COUNT(CASE WHEN created_at >= :week_ago THEN 1 END) as new_this_week
            FROM patients
        """), {"week_ago": week_ago})
        patient_metrics = total_patients_query.fetchone()

        # Message metrics
        message_metrics_query = db.execute(text("""
            SELECT COUNT(*) as total_today,
                   COUNT(CASE WHEN created_at >= :week_ago THEN 1 END) as total_week,
                   COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent_count,
                   COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count
            FROM messages 
            WHERE created_at >= :today
        """), {"today": today, "week_ago": week_ago})
        message_metrics = message_metrics_query.fetchone()

        # Flow metrics
        flow_metrics_query = db.execute(text("""
            SELECT COUNT(CASE WHEN status = 'active' THEN 1 END) as active_flows,
                   COUNT(CASE WHEN status = 'completed' AND updated_at >= :week_ago THEN 1 END) as completed_this_week,
                   AVG(CASE WHEN status = 'completed' THEN 
                       EXTRACT(DAY FROM (updated_at - created_at)) END) as avg_completion_days
            FROM patient_flows
            WHERE created_at >= :month_ago
        """), {"week_ago": week_ago, "month_ago": month_ago})
        flow_metrics = flow_metrics_query.fetchone()

        # Alert metrics
        alert_metrics_query = db.execute(text("""
            SELECT COUNT(CASE WHEN acknowledged = false THEN 1 END) as pending_alerts,
                   COUNT(CASE WHEN severity = 'high' OR severity = 'critical' THEN 1 END) as high_priority,
                   COUNT(CASE WHEN created_at >= :today THEN 1 END) as new_today
            FROM alerts
            WHERE resolved_at IS NULL
        """), {"today": today})
        alert_metrics = alert_metrics_query.fetchone()

        # Calculate response rate for messages
        response_rate = 0
        if message_metrics.total_week > 0:
            response_count_query = db.execute(text("""
                SELECT COUNT(*) FROM messages 
                WHERE created_at >= :week_ago AND patient_response_received = true
            """), {"week_ago": week_ago})
            response_count = response_count_query.scalar()
            response_rate = round((response_count / message_metrics.total_week) * 100, 1)

        return {
            "totalPatients": patient_metrics.total or 0,
            "activePatients": patient_metrics.active or 0,
            "newPatientsThisWeek": patient_metrics.new_this_week or 0,
            "messagesToday": message_metrics.total_today or 0,
            "messagesThisWeek": message_metrics.total_week or 0,
            "messagesSent": message_metrics.sent_count or 0,
            "messagesFailed": message_metrics.failed_count or 0,
            "responseRate": response_rate,
            "activeFlows": flow_metrics.active_flows or 0,
            "completedFlowsThisWeek": flow_metrics.completed_this_week or 0,
            "avgCompletionDays": round(flow_metrics.avg_completion_days or 0, 1),
            "pendingAlerts": alert_metrics.pending_alerts or 0,
            "highPriorityAlerts": alert_metrics.high_priority or 0,
            "newAlertsToday": alert_metrics.new_today or 0,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching dashboard metrics: {str(e)}")
        return {
            "error": "Failed to fetch metrics",
            "totalPatients": 0,
            "activePatients": 0,
            "messagesToday": 0,
            "activeFlows": 0,
            "pendingAlerts": 0
        }


@router.get("/activity")
async def get_recent_activity(
    limit: int = Query(10, description="Number of activities to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get recent system activity feed
    """
    try:
        # Get recent activities from different sources
        activities = []

        # Recent messages
        recent_messages_query = db.execute(text("""
            SELECT 'message_sent' as type, 
                   CONCAT('Mensagem enviada para ', p.full_name) as description,
                   p.full_name as patient_name,
                   m.created_at as timestamp,
                   m.id::text as reference_id
            FROM messages m
            JOIN patients p ON m.patient_id = p.id
            WHERE m.created_at >= NOW() - INTERVAL '24 hours'
            ORDER BY m.created_at DESC
            LIMIT :limit
        """), {"limit": limit // 2})
        
        for row in recent_messages_query.fetchall():
            activities.append({
                "id": f"msg_{row.reference_id}",
                "type": row.type,
                "description": row.description,
                "patient_name": row.patient_name,
                "timestamp": row.timestamp.isoformat()
            })

        # Recent flow completions
        recent_flows_query = db.execute(text("""
            SELECT 'flow_completed' as type,
                   CONCAT('Fluxo ', ft.name, ' concluído por ', p.full_name) as description,
                   p.full_name as patient_name,
                   pf.updated_at as timestamp,
                   pf.id::text as reference_id
            FROM patient_flows pf
            JOIN patients p ON pf.patient_id = p.id
            JOIN flow_templates ft ON pf.flow_template_id = ft.id
            WHERE pf.status = 'completed' AND pf.updated_at >= NOW() - INTERVAL '24 hours'
            ORDER BY pf.updated_at DESC
            LIMIT :limit
        """), {"limit": limit // 2})
        
        for row in recent_flows_query.fetchall():
            activities.append({
                "id": f"flow_{row.reference_id}",
                "type": row.type,
                "description": row.description,
                "patient_name": row.patient_name,
                "timestamp": row.timestamp.isoformat()
            })

        # Recent alerts
        recent_alerts_query = db.execute(text("""
            SELECT 'alert_created' as type,
                   a.title as description,
                   COALESCE(p.full_name, 'Sistema') as patient_name,
                   a.created_at as timestamp,
                   a.id::text as reference_id
            FROM alerts a
            LEFT JOIN patients p ON a.patient_id = p.id
            WHERE a.created_at >= NOW() - INTERVAL '24 hours'
            ORDER BY a.created_at DESC
            LIMIT :limit
        """), {"limit": limit // 2})
        
        for row in recent_alerts_query.fetchall():
            activities.append({
                "id": f"alert_{row.reference_id}",
                "type": row.type,
                "description": row.description,
                "patient_name": row.patient_name,
                "timestamp": row.timestamp.isoformat()
            })

        # Sort by timestamp and limit
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        activities = activities[:limit]

        return {
            "activities": activities,
            "total": len(activities),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching recent activity: {str(e)}")
        return {
            "activities": [],
            "total": 0,
            "error": "Failed to fetch activities"
        }


@router.get("/charts/engagement")
async def get_engagement_chart_data(
    days: int = Query(7, description="Number of days to include"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get patient engagement chart data (line chart)
    """
    try:
        start_date = datetime.utcnow().date() - timedelta(days=days-1)
        
        # Get daily engagement data
        engagement_query = db.execute(text("""
            WITH date_series AS (
                SELECT generate_series(
                    :start_date::date,
                    CURRENT_DATE,
                    '1 day'::interval
                )::date AS date
            ),
            daily_messages AS (
                SELECT DATE(created_at) as date,
                       COUNT(*) as messages_sent,
                       COUNT(CASE WHEN patient_response_received = true THEN 1 END) as responses_received
                FROM messages
                WHERE DATE(created_at) >= :start_date
                GROUP BY DATE(created_at)
            )
            SELECT ds.date,
                   COALESCE(dm.messages_sent, 0) as messages_sent,
                   COALESCE(dm.responses_received, 0) as responses_received,
                   CASE 
                       WHEN COALESCE(dm.messages_sent, 0) = 0 THEN 0
                       ELSE ROUND((COALESCE(dm.responses_received, 0)::float / dm.messages_sent) * 100, 1)
                   END as response_rate
            FROM date_series ds
            LEFT JOIN daily_messages dm ON ds.date = dm.date
            ORDER BY ds.date
        """), {"start_date": start_date})

        data = []
        for row in engagement_query.fetchall():
            data.append({
                "date": row.date.strftime("%Y-%m-%d"),
                "messages_sent": row.messages_sent,
                "responses_received": row.responses_received,
                "response_rate": row.response_rate
            })

        return {
            "data": data,
            "period": f"{days} days",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching engagement chart data: {str(e)}")
        return {"data": [], "error": "Failed to fetch engagement data"}


@router.get("/charts/message-volume")
async def get_message_volume_chart_data(
    days: int = Query(7, description="Number of days to include"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get message volume chart data (bar chart)
    """
    try:
        start_date = datetime.utcnow().date() - timedelta(days=days-1)
        
        volume_query = db.execute(text("""
            WITH date_series AS (
                SELECT generate_series(
                    :start_date::date,
                    CURRENT_DATE,
                    '1 day'::interval
                )::date AS date
            ),
            daily_volume AS (
                SELECT DATE(created_at) as date,
                       COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent,
                       COUNT(CASE WHEN status = 'delivered' THEN 1 END) as delivered,
                       COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
                FROM messages
                WHERE DATE(created_at) >= :start_date
                GROUP BY DATE(created_at)
            )
            SELECT ds.date,
                   COALESCE(dv.sent, 0) as sent,
                   COALESCE(dv.delivered, 0) as delivered,
                   COALESCE(dv.failed, 0) as failed
            FROM date_series ds
            LEFT JOIN daily_volume dv ON ds.date = dv.date
            ORDER BY ds.date
        """), {"start_date": start_date})

        data = []
        for row in volume_query.fetchall():
            data.append({
                "date": row.date.strftime("%Y-%m-%d"),
                "sent": row.sent,
                "delivered": row.delivered,
                "failed": row.failed,
                "total": row.sent + row.delivered + row.failed
            })

        return {
            "data": data,
            "period": f"{days} days",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching message volume data: {str(e)}")
        return {"data": [], "error": "Failed to fetch message volume data"}


@router.get("/charts/flow-completion")
async def get_flow_completion_chart_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get flow completion rates chart data (donut chart)
    """
    try:
        completion_query = db.execute(text("""
            SELECT ft.name,
                   COUNT(*) as total_flows,
                   COUNT(CASE WHEN pf.status = 'completed' THEN 1 END) as completed,
                   COUNT(CASE WHEN pf.status = 'active' THEN 1 END) as active,
                   COUNT(CASE WHEN pf.status = 'paused' THEN 1 END) as paused,
                   ROUND(
                       (COUNT(CASE WHEN pf.status = 'completed' THEN 1 END)::float / COUNT(*)) * 100, 
                       1
                   ) as completion_rate
            FROM patient_flows pf
            JOIN flow_templates ft ON pf.flow_template_id = ft.id
            WHERE pf.created_at >= NOW() - INTERVAL '30 days'
            GROUP BY ft.id, ft.name
            ORDER BY completion_rate DESC
        """))

        data = []
        for row in completion_query.fetchall():
            data.append({
                "name": row.name,
                "total": row.total_flows,
                "completed": row.completed,
                "active": row.active,
                "paused": row.paused,
                "completion_rate": row.completion_rate,
                "color": f"hsl({hash(row.name) % 360}, 70%, 50%)"  # Generate color based on name
            })

        return {
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching flow completion data: {str(e)}")
        return {"data": [], "error": "Failed to fetch flow completion data"}


@router.get("/charts/response-trends")
async def get_response_trends_chart_data(
    days: int = Query(30, description="Number of days to include"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get response rate trends over time
    """
    try:
        start_date = datetime.utcnow().date() - timedelta(days=days-1)
        
        trends_query = db.execute(text("""
            WITH weekly_data AS (
                SELECT DATE_TRUNC('week', created_at::date) as week,
                       COUNT(*) as messages_sent,
                       COUNT(CASE WHEN patient_response_received = true THEN 1 END) as responses
                FROM messages
                WHERE created_at >= :start_date
                GROUP BY DATE_TRUNC('week', created_at::date)
            )
            SELECT week,
                   messages_sent,
                   responses,
                   CASE 
                       WHEN messages_sent = 0 THEN 0
                       ELSE ROUND((responses::float / messages_sent) * 100, 1)
                   END as response_rate
            FROM weekly_data
            ORDER BY week
        """), {"start_date": start_date})

        data = []
        for row in trends_query.fetchall():
            data.append({
                "week": row.week.strftime("%Y-%m-%d"),
                "messages_sent": row.messages_sent,
                "responses": row.responses,
                "response_rate": row.response_rate
            })

        return {
            "data": data,
            "period": f"{days} days",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching response trends data: {str(e)}")
        return {"data": [], "error": "Failed to fetch response trends data"}