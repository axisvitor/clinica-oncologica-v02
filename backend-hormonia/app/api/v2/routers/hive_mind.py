from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.auth_helpers import is_admin
from app.services.hive_mind_integration import get_hive_mind_integration
from app.schemas.v2.hive_mind import (
    AgentListResponse,
    AgentStatusSchema,
    AgentHealthSchema,
    SystemHealthOverview
)
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.get("/health", response_model=SystemHealthOverview)
async def get_hive_mind_health(
    current_user=Depends(get_current_user_from_session),
):
    """Get overall Hive Mind system health."""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    integration = await get_hive_mind_integration()
    swarm_manager = integration.swarm_manager
    
    if not swarm_manager:
        # If swarm is not active, return a basic "down" status
        return SystemHealthOverview(
            status="down",
            timestamp=datetime.now(),
            system_health={
                "total_agents": 0,
                "active_agents": 0,
                "system_uptime_seconds": 0,
                "agents_by_status": {},
                "active_system_alerts": 0,
                "total_active_alerts": 0
            },
            system_alerts=0
        )
        
    swarm_status = swarm_manager.get_swarm_status()
    
    # Calculate overall health based on swarm status
    status_map = {
        "active": "healthy",
        "degraded": "degraded", 
        "critical": "down",
        "shutdown": "down",
        "initializing": "degraded"
    }
    
    overall_status = status_map.get(swarm_status["status"], "degraded")
    
    return SystemHealthOverview(
        status=overall_status,
        timestamp=datetime.now(),
        system_health={
            "total_agents": swarm_status["total_agents"],
            "active_agents": swarm_status["healthy_agents"], # Using healthy count for active
            "system_uptime_seconds": 0, # Placeholder, swarm_manager doesn't track uptime seconds directly in get_swarm_status
            "agents_by_status": {}, # Placeholder
            "active_system_alerts": swarm_status.get("active_tasks", 0), # Using active tasks as proxy for now
            "total_active_alerts": swarm_status.get("pending_tasks", 0)
        },
        system_alerts=0
    )

@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    current_user=Depends(get_current_user_from_session),
):
    """List all registered Hive Mind agents."""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    integration = await get_hive_mind_integration()
    swarm_manager = integration.swarm_manager

    if not swarm_manager:
         return AgentListResponse(
            agents=[],
            total_agents=0,
            timestamp=datetime.now()
        )

    agents_data = swarm_manager.get_agent_list()
    
    agents_list = []
    for agent in agents_data:
        health_data = agent.get("health")
        health_schema = None
        if health_data:
            health_schema = AgentHealthSchema(
                is_healthy=health_data.get("status") == "active", # Mapping status to healthy bool
                response_time=health_data.get("response_time", 0.0),
                success_rate=health_data.get("success_rate", 1.0),
                active_tasks=health_data.get("active_tasks", 0),
                error_count=health_data.get("error_count", 0)
            )
            
        agents_list.append(AgentStatusSchema(
            agent_id=agent["agent_id"],
            agent_type=agent["agent_type"],
            status=agent["status"],
            specialization=agent.get("specialization"),
            capabilities=agent.get("capabilities", []),
            health=health_schema
        ))

    return AgentListResponse(
        agents=agents_list,
        total_agents=len(agents_list),
        timestamp=datetime.now()
    )
