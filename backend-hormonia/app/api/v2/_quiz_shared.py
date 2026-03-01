"""
Shared helpers for quiz extensions modules.

This module contains common authentication, authorization, and configuration
used across all quiz extension endpoints.
"""

from __future__ import annotations

from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User, UserRole
from app.models.patient import Patient
from app.dependencies.auth_dependencies import get_current_user_object_from_session


# Cache TTL configurations
CACHE_TTL_RESPONSES = 300  # 5 minutes for quiz responses
CACHE_TTL_ALERTS = 60  # 1 minute for alerts (time-sensitive)
CACHE_TTL_STATISTICS = 120  # 2 minutes for statistics
CACHE_TTL_PUBLIC_QUIZ = 900  # 15 minutes for public quiz (longer, less changes)
CACHE_TTL_TEMPLATES = 1800  # 30 minutes for templates (rarely change)
CACHE_TTL_QUIZ_LIST = 300  # 5 minutes for quiz lists


async def _get_current_user_simple(
    current_user: User = Depends(get_current_user_object_from_session),
) -> User:
    """Session-based auth for quiz endpoints (cookie/X-Session-ID/Bearer session_id)."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user


async def _check_patient_access(
    db: AsyncSession, current_user: User, patient_id: UUID
) -> Patient:
    """Check if user has access to patient data."""
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    # Admin has access to all patients
    if current_user.role == UserRole.ADMIN:
        return patient

    # Doctors can access assigned patients
    if current_user.role == UserRole.DOCTOR and patient.doctor_id == current_user.id:
        return patient

    # FIXED: Removed UserRole.PATIENT check - only ADMIN and DOCTOR roles exist

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this patient's data",
    )
