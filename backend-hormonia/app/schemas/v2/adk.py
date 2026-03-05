"""Schemas for ADK v2 execution endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, constr, model_validator


class ADKRuntimeControls(BaseModel):
    """Explicit per-invocation runtime overrides."""

    max_llm_calls: int | None = Field(
        default=None,
        ge=1,
        le=32,
        description="Optional per-invocation limit for ADK LLM calls",
    )
    timeout_seconds: float | None = Field(
        default=None,
        gt=0,
        le=300,
        description="Optional per-invocation timeout override in seconds",
    )

    model_config = ConfigDict(extra="forbid")


class ADKSessionControls(BaseModel):
    """Explicit ADK session lifecycle controls."""

    action: Literal["auto", "create", "resume", "close"] = Field(
        default="auto",
        description="Session lifecycle action resolved before runtime execution",
    )
    session_id: constr(strip_whitespace=True, min_length=1, max_length=128) | None = (
        Field(
            default=None,
            description="Explicit ADK session identifier for resume/close semantics",
        )
    )
    state_size_limit_bytes: int | None = Field(
        default=None,
        ge=1024,
        le=1_048_576,
        description="Optional session state size budget used by later runtime controls",
    )

    model_config = ConfigDict(extra="forbid")


class ADKInvocationControls(BaseModel):
    """Explicit ADK invocation lifecycle controls."""

    action: Literal["run", "cancel"] = Field(
        default="run",
        description="Invocation lifecycle action resolved before runtime execution",
    )
    invocation_id: constr(strip_whitespace=True, min_length=1, max_length=128) | None = (
        Field(
            default=None,
            description="Invocation identifier for cancel/lookup semantics",
        )
    )

    model_config = ConfigDict(extra="forbid")


class ADKRunRequest(BaseModel):
    """Request payload for /api/v2/adk/run."""

    prompt: str | None = Field(
        default=None,
        max_length=4000,
        description="Prompt text to process via ADK",
    )
    tool_name: constr(strip_whitespace=True, min_length=1, max_length=64) = Field(
        ..., description="Registered ADK tool name"
    )
    user_id: str | None = Field(None, description="Optional caller user identifier")
    session_id: constr(strip_whitespace=True, min_length=1, max_length=128) | None = (
        Field(
            None,
            description="Legacy session identifier retained for compatibility with prior callers",
        )
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional extra context passed to PIISafeADKWrapper",
    )
    runtime: ADKRuntimeControls | None = Field(
        default=None,
        description="Explicit per-invocation runtime overrides",
    )
    session: ADKSessionControls | None = Field(
        default=None,
        description="Explicit ADK session lifecycle controls",
    )
    invocation: ADKInvocationControls | None = Field(
        default=None,
        description="Explicit ADK invocation lifecycle controls",
    )

    model_config = ConfigDict(extra="forbid")

    def resolved_runtime_controls(self) -> ADKRuntimeControls:
        return self.runtime or ADKRuntimeControls()

    def resolved_session_controls(self) -> ADKSessionControls:
        if self.session is None:
            return ADKSessionControls(session_id=self.session_id)
        if self.session_id and self.session.session_id is None:
            return self.session.model_copy(update={"session_id": self.session_id})
        return self.session

    def resolved_invocation_controls(self) -> ADKInvocationControls:
        return self.invocation or ADKInvocationControls()

    @model_validator(mode="after")
    def validate_control_combinations(self) -> "ADKRunRequest":
        session_controls = self.resolved_session_controls()
        invocation_controls = self.resolved_invocation_controls()

        if (
            self.session_id
            and self.session is not None
            and self.session.session_id is not None
            and self.session.session_id != self.session_id
        ):
            raise ValueError(
                "session_id must match session.session_id when both are provided"
            )

        if session_controls.action in {"resume", "close"} and not session_controls.session_id:
            raise ValueError(
                f"session_id is required when session.action='{session_controls.action}'"
            )

        if (
            invocation_controls.action == "cancel"
            and not invocation_controls.invocation_id
        ):
            raise ValueError(
                "invocation.invocation_id is required when invocation.action='cancel'"
            )

        if (
            invocation_controls.action == "cancel"
            and session_controls.action == "create"
        ):
            raise ValueError("invocation cancellation cannot create a new session")

        prompt = (self.prompt or "").strip()
        if not prompt and session_controls.action != "close" and invocation_controls.action != "cancel":
            raise ValueError(
                "prompt is required unless closing a session or cancelling an invocation"
            )

        return self


class ADKRunResponse(BaseModel):
    """Normalized response returned by /api/v2/adk/run."""

    status: str = Field(..., description="Normalized execution status")
    tool_name: str = Field(..., description="Tool requested by client")
    session_id: str | None = Field(None, description="Execution session id")
    output: Any = Field(..., description="Normalized output payload")
