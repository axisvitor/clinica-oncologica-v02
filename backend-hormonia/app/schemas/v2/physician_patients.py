"""
Pydantic schemas for the physician patient list endpoint.

GET /api/v2/physicians/patients returns enriched patient data
with flow state, phase, and alert counts for the physician dashboard.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PhysicianPatientItem(BaseModel):
    """A single patient row in the physician dashboard list."""

    id: UUID
    name: str
    flow_phase: Optional[str] = Field(
        None,
        description="Flow kind key: onboarding, daily_follow_up, quiz_mensal, custom, or null if no flow",
    )
    flow_current_day: int = Field(
        0, description="Current day in the flow (from step_data.current_flow_day or current_step)"
    )
    flow_status: Optional[str] = Field(
        None,
        description="Flow state status: active, paused, completed, or null if no flow",
    )
    last_interaction: Optional[datetime] = Field(
        None, description="Last interaction timestamp from flow state"
    )
    unacknowledged_alerts_count: int = Field(
        0, description="Count of alerts where acknowledged=false"
    )
    treatment_type: Optional[str] = Field(None, description="Patient treatment type")

    class Config:
        from_attributes = True


class PhysicianPatientListResponse(BaseModel):
    """Paginated response for the physician patient list."""

    items: List[PhysicianPatientItem]
    total: int
    page: int
    size: int
