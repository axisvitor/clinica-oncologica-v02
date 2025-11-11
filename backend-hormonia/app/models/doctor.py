"""
Backward-compatible Doctor model used by legacy tests.

The new domain model stores physician data differently, but several tests still
import ``app.models.doctor.Doctor``. This lightweight Pydantic model provides
the expected interface without duplicating ORM definitions.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Doctor(BaseModel):
    """Minimal doctor representation for testing and compatibility."""

    id: UUID = Field(..., description="Doctor UUID")
    email: str = Field(..., description="Doctor email address")
    full_name: Optional[str] = Field(None, description="Doctor full name")
    specialty: Optional[str] = Field(None, description="Medical specialty")
    crm: Optional[str] = Field(None, description="Medical license/CRM number")
    phone: Optional[str] = Field(None, description="Contact phone number")
    is_active: bool = Field(default=True, description="Whether doctor is active")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        from_attributes = True


__all__ = ["Doctor"]
