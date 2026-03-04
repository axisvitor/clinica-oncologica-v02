"""Schemas for ADK v2 execution endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, constr


class ADKRunRequest(BaseModel):
    """Request payload for /api/v2/adk/run."""

    prompt: constr(min_length=1, max_length=4000) = Field(
        ..., description="Prompt text to process via ADK"
    )
    tool_name: constr(strip_whitespace=True, min_length=1, max_length=64) = Field(
        ..., description="Registered ADK tool name"
    )
    user_id: str | None = Field(None, description="Optional caller user identifier")
    session_id: str | None = Field(None, description="Optional caller session identifier")
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional extra context passed to PIISafeADKWrapper",
    )

    model_config = ConfigDict(extra="forbid")


class ADKRunResponse(BaseModel):
    """Normalized response returned by /api/v2/adk/run."""

    status: str = Field(..., description="Normalized execution status")
    tool_name: str = Field(..., description="Tool requested by client")
    session_id: str | None = Field(None, description="Execution session id")
    output: Any = Field(..., description="Normalized output payload")
