"""Pydantic request/response schemas for per-patient flow day overrides."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────


class OverrideDayInput(BaseModel):
    """Single day override payload sent by the physician."""

    day_number: int = Field(..., ge=1, description="Day number in the flow")
    content: str = Field(
        ..., min_length=1, description="Override message content for this day"
    )
    message_type: str = Field(
        "question",
        description="Semantic type: question, motivation, or reminder",
    )
    expects_response: bool = Field(
        False, description="Whether the system waits for patient response"
    )
    skip: bool = Field(
        False, description="If true the day is skipped entirely during delivery"
    )


class OverrideDayUpdateRequest(BaseModel):
    """Bulk override upsert request — replaces all overrides for future days."""

    days: list[OverrideDayInput]


# ── Response schemas ─────────────────────────────────────────────


class MergedDayItem(BaseModel):
    """A single day in the merged (global + override) view."""

    day_number: int
    content: str
    message_type: str
    expects_response: bool
    skip: bool
    source: Literal["global", "override"] = Field(
        ..., description="Whether this day comes from the global template or a patient override"
    )
    editable: bool = Field(
        ..., description="Whether the physician can still edit this day (false for past days)"
    )


class MergedDayListResponse(BaseModel):
    """Full merged day list returned by the GET endpoint."""

    patient_id: UUID
    flow_state_id: UUID
    current_flow_day: int
    days: list[MergedDayItem]
