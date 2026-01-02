from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class AgentHealthSchema(BaseModel):
    is_healthy: bool
    response_time: float
    success_rate: float
    active_tasks: int
    error_count: int

class AgentStatusSchema(BaseModel):
    agent_id: str
    agent_type: str
    status: str
    specialization: Optional[str] = None
    capabilities: List[str]
    health: Optional[AgentHealthSchema] = None

class AgentListResponse(BaseModel):
    agents: List[AgentStatusSchema]
    total_agents: int
    timestamp: datetime

class SystemHealthOverview(BaseModel):
    status: str
    timestamp: datetime
    system_health: Dict[str, Any]
    system_alerts: int
