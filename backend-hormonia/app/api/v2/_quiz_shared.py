"""
Shared helpers for quiz extensions modules.

This module contains common authentication, authorization, and configuration
used across all quiz extension endpoints.
"""

from __future__ import annotations

from uuid import UUID
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.patient import Patient


# Cache TTL configurations
CACHE_TTL_RESPONSES = 300  # 5 minutes for quiz responses
CACHE_TTL_ALERTS = 60  # 1 minute for alerts (time-sensitive)
CACHE_TTL_STATISTICS = 120  # 2 minutes for statistics
CACHE_TTL_PUBLIC_QUIZ = 900  # 15 minutes for public quiz (longer, less changes)
CACHE_TTL_TEMPLATES = 1800  # 30 minutes for templates (rarely change)
CACHE_TTL_QUIZ_LIST = 300  # 5 minutes for quiz lists


def _get_current_user_simple(
    session_id: str = Header(None, alias="X-Session-ID"),
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Simplified session validation for V2 endpoints."""
    # Support both X-Session-ID and Authorization: Bearer headers
    final_session_id = session_id
    if not final_session_id and authorization and authorization.startswith("Bearer "):
        final_session_id = authorization.split(" ")[1]

    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided",
        )

    # For now, we'll use a simple lookup. In production, validate against Redis/session store
    # This is a placeholder - replace with actual session validation
    user = db.query(User).filter(User.id == final_session_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return user


def _check_patient_access(db: Session, current_user: User, patient_id: UUID) -> Patient:
    """Check if user has access to patient data."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
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
