"""
Hive-Mind API endpoints for monitoring and management.

Provides RESTful API for interacting with the Hive-Mind agent system,
including health monitoring, agent status, and system management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import get_db
from app.services.hive_mind_integration import get_hive_mind_integration, IntegrationMode
# TODO: Restore when app.coordination module is implemented
# from app.coordination.health_monitor import get_system_health_monitor
# from app.coordination.swarm_manager import get_swarm_manager
from app.utils.logging import get_logger

router = APIRouter(prefix="/hive-mind", tags=["hive-mind"])
logger = get_logger("hive_mind_api")


@router.get("/health")
async def get_system_health():
    """Get overall system health status."""
    try:
        health_monitor = await get_system_health_monitor()
        overview = health_monitor.get_system_overview()
        
        return {
            "status": "healthy" if overview["agents_by_status"]["critical"] == 0 else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "system_health": overview,
            "system_alerts": len(health_monitor.get_system_alerts(active_only=True))
        }
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system health")


@router.get("/agents")
async def get_agents_status():
    """Get status of all agents."""
    try:
        health_monitor = await get_system_health_monitor()
        agents_status = health_monitor.get_all_agents_status()
        
        return {
            "agents": agents_status,
            "total_agents": len(agents_status),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get agents status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agents status")


@router.get("/agents/{agent_id}")
async def get_agent_status(agent_id: str):
    """Get detailed status for specific agent."""
    try:
        health_monitor = await get_system_health_monitor()
        agent_status = health_monitor.get_agent_status(agent_id)
        
        if not agent_status:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        return agent_status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agent status")


@router.get("/agents/{agent_id}/metrics")
async def get_agent_metrics(
    agent_id: str,
    limit: Optional[int] = Query(default=10, description="Number of metrics entries to return")
):
    """Get historical metrics for specific agent."""
    try:
        health_monitor = await get_system_health_monitor()
        
        if agent_id not in health_monitor.agent_monitors:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        monitor = health_monitor.agent_monitors[agent_id]
        metrics_history = monitor.get_metrics_history(limit=limit)
        
        return {
            "agent_id": agent_id,
            "metrics": [m.to_dict() for m in metrics_history],
            "count": len(metrics_history),
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agent metrics")


@router.get("/alerts")
async def get_alerts(
    active_only: bool = Query(default=True, description="Return only active alerts"),
    severity: Optional[str] = Query(default=None, description="Filter by severity level")
):
    """Get system and agent alerts."""
    try:
        health_monitor = await get_system_health_monitor()
        
        # Get system alerts
        system_alerts = health_monitor.get_system_alerts(active_only=active_only)
        
        # Get agent alerts
        agent_alerts = []
        for monitor in health_monitor.agent_monitors.values():
            if active_only:
                alerts = monitor.get_active_alerts()
            else:
                alerts = monitor.get_all_alerts()
            agent_alerts.extend(alerts)
        
        all_alerts = system_alerts + agent_alerts
        
        # Filter by severity if specified
        if severity:
            all_alerts = [alert for alert in all_alerts if alert.severity.value == severity]
        
        return {
            "alerts": [alert.to_dict() for alert in all_alerts],
            "count": len(all_alerts),
            "active_count": len([a for a in all_alerts if a.resolved_at is None]),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.get("/integration/status")
async def get_integration_status():
    """Get Hive-Mind integration status."""
    try:
        integration = await get_hive_mind_integration()
        status = integration.get_integration_status()
        
        return {
            "integration": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get integration status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve integration status")


@router.put("/integration/mode")
async def set_integration_mode(mode: str):
    """Set integration mode."""
    try:
        # Validate mode
        try:
            integration_mode = IntegrationMode(mode)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid mode. Valid modes: {[m.value for m in IntegrationMode]}"
            )
        
        integration = await get_hive_mind_integration()
        await integration.set_integration_mode(integration_mode)
        
        return {
            "success": True,
            "new_mode": mode,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set integration mode: {e}")
        raise HTTPException(status_code=500, detail="Failed to set integration mode")


@router.put("/integration/migration-percentage")
async def set_migration_percentage(percentage: int):
    """Set migration percentage for gradual rollout."""
    try:
        if not 0 <= percentage <= 100:
            raise HTTPException(status_code=400, detail="Percentage must be between 0 and 100")
        
        integration = await get_hive_mind_integration()
        await integration.update_migration_percentage(percentage)
        
        return {
            "success": True,
            "new_percentage": percentage,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set migration percentage: {e}")
        raise HTTPException(status_code=500, detail="Failed to set migration percentage")


@router.get("/swarm/status")
async def get_swarm_status():
    """Get swarm manager status."""
    try:
        swarm_manager = await get_swarm_manager()
        
        # Get basic swarm info
        swarm_info = {
            "swarm_id": swarm_manager.swarm_id,
            "status": swarm_manager.status.value,
            "uptime_seconds": int((datetime.utcnow() - swarm_manager.created_at).total_seconds()),
            "total_agents": len(swarm_manager.agents),
            "active_tasks": len([t for t in swarm_manager.tasks.values() if t.status.value in ["pending", "assigned", "in_progress"]]),
            "completed_tasks": len([t for t in swarm_manager.tasks.values() if t.status.value == "completed"]),
            "failed_tasks": len([t for t in swarm_manager.tasks.values() if t.status.value == "failed"])
        }
        
        return {
            "swarm": swarm_info,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get swarm status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve swarm status")


@router.get("/swarm/agents")
async def get_swarm_agents():
    """Get agents registered with swarm manager."""
    try:
        swarm_manager = await get_swarm_manager()
        
        agents_info = []
        for agent_id, agent in swarm_manager.agents.items():
            health = swarm_manager.agent_health.get(agent_id)
            capabilities = swarm_manager.agent_capabilities.get(agent_id, [])
            
            agent_info = {
                "agent_id": agent_id,
                "agent_type": getattr(agent, 'agent_type', 'unknown'),
                "status": agent.status.value if hasattr(agent, 'status') else 'unknown',
                "capabilities": capabilities,
                "health": {
                    "is_healthy": health.is_healthy() if health else False,
                    "response_time": health.response_time if health else 0.0,
                    "success_rate": health.success_rate if health else 0.0,
                    "active_tasks": health.active_tasks if health else 0,
                    "error_count": health.error_count if health else 0
                } if health else None
            }
            agents_info.append(agent_info)
        
        return {
            "agents": agents_info,
            "count": len(agents_info),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get swarm agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve swarm agents")


@router.post("/tasks/process-flows")
async def trigger_flow_processing(
    limit: int = Query(default=50, description="Maximum number of patients to process"),
    db: Session = Depends(get_db)
):
    """Trigger manual flow processing."""
    try:
        integration = await get_hive_mind_integration()
        results = await integration.process_daily_flows(limit=limit)
        
        return {
            "success": True,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to process flows: {e}")
        raise HTTPException(status_code=500, detail="Failed to process flows")


@router.post("/tasks/conduct-quiz/{patient_id}")
async def trigger_quiz_session(
    patient_id: str,
    quiz_type: str = Query(default="monthly_checkup", description="Type of quiz to conduct")
):
    """Trigger quiz session for specific patient."""
    try:
        from uuid import UUID
        patient_uuid = UUID(patient_id)
        
        integration = await get_hive_mind_integration()
        result = await integration.conduct_quiz_session(patient_uuid, quiz_type)
        
        return {
            "patient_id": patient_id,
            "quiz_type": quiz_type,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient ID format")
    except Exception as e:
        logger.error(f"Failed to conduct quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to conduct quiz session")


@router.get("/stats")
async def get_system_stats():
    """Get comprehensive system statistics."""
    try:
        health_monitor = await get_system_health_monitor()
        integration = await get_hive_mind_integration()
        swarm_manager = await get_swarm_manager()
        
        # System overview
        system_overview = health_monitor.get_system_overview()
        integration_status = integration.get_integration_status()
        
        # Calculate additional stats
        total_alerts = 0
        for monitor in health_monitor.agent_monitors.values():
            total_alerts += len(monitor.get_all_alerts())
        total_alerts += len(health_monitor.get_system_alerts(active_only=False))
        
        stats = {
            "system": {
                "uptime_seconds": system_overview["system_uptime_seconds"],
                "total_agents": system_overview["total_agents"],
                "healthy_agents": system_overview["agents_by_status"]["healthy"],
                "integration_mode": integration_status["integration_mode"],
                "migration_percentage": integration_status["migration_percentage"]
            },
            "swarm": {
                "swarm_id": swarm_manager.swarm_id,
                "status": swarm_manager.status.value,
                "total_tasks": len(swarm_manager.tasks),
                "active_tasks": len([t for t in swarm_manager.tasks.values() if t.status.value in ["pending", "assigned", "in_progress"]])
            },
            "alerts": {
                "active_alerts": system_overview["total_active_alerts"],
                "total_alerts": total_alerts,
                "system_alerts": system_overview["active_system_alerts"]
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return stats
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system statistics")