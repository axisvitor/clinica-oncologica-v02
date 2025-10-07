from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.patient import Patient, FlowState
from app.repositories.base import BaseRepository


class PatientRepository(BaseRepository[Patient]):
    """Repository for Patient model"""
    
    def __init__(self, db: Session):
        super().__init__(db, Patient)
    
    def get_by_phone(self, phone: str) -> Optional[Patient]:
        """
        Get patient by phone number.

        Handles both E.164 format (+55...) and without prefix (55...).
        The webhook processor handles fallback strategies, this just does exact match.

        Args:
            phone: Phone number in any format

        Returns:
            Patient or None if not found
        """
        return self.db.query(Patient).filter(Patient.phone == phone).first()
    
    def get_by_doctor(self, doctor_id: UUID, skip: int = 0, limit: int = 100, eager_load: bool = False) -> List[Patient]:
        """
        Get patients by doctor with optional eager loading.

        PERFORMANCE FIX #1: Added eager loading to prevent N+1 queries
        when accessing patient relationships (messages, flow_states, etc.)
        """
        query = self.db.query(Patient).filter(Patient.doctor_id == doctor_id)

        if eager_load:
            # Eager load commonly accessed relationships to prevent N+1 queries
            query = query.options(
                joinedload(Patient.doctor),
                joinedload(Patient.flow_states),
                joinedload(Patient.alerts)
            )

        return query.offset(skip).limit(limit).all()
    
    def get_paginated(
        self,
        doctor_id: UUID,
        page: int,
        limit: int,
        *,
        search: Optional[str] = None,
        flow_state: Optional[FlowState] = None,
        treatment_type: Optional[str] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
        eager_load: bool = False,
    ) -> tuple[list[Patient], int]:
        """
        Get patients with pagination and optional filtering.

        PERFORMANCE FIX #1: Added eager loading support to prevent N+1 queries.
        When eager_load=True, commonly accessed relationships are loaded in one query.
        """
        base_query = self.db.query(Patient).filter(Patient.doctor_id == doctor_id)

        # PERFORMANCE: Eager load relationships if requested to prevent N+1
        if eager_load:
            base_query = base_query.options(
                joinedload(Patient.doctor),
                joinedload(Patient.flow_states),
                joinedload(Patient.alerts)
            )

        if search:
            search_value = search.strip()
            if search_value:
                pattern = f"%{search_value}%"
                # PERFORMANCE: Uses index on name with ILIKE
                # Consider adding GIN index for better performance
                base_query = base_query.filter(
                    or_(
                        Patient.name.ilike(pattern),
                        Patient.phone.ilike(pattern),
                        Patient.email.ilike(pattern),
                    )
                )

        if flow_state:
            base_query = base_query.filter(Patient.flow_state == flow_state)

        if treatment_type:
            base_query = base_query.filter(Patient.treatment_type == treatment_type)

        if start_date_from:
            base_query = base_query.filter(Patient.treatment_start_date >= start_date_from)

        if start_date_to:
            base_query = base_query.filter(Patient.treatment_start_date <= start_date_to)

        total = base_query.count()
        if total == 0:
            return [], 0

        offset = (page - 1) * limit
        items = (
            base_query
            .order_by(Patient.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return items, total

    def get_by_flow_state(self, flow_state: FlowState, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Get patients by flow state"""
        return (
            self.db.query(Patient)
            .filter(Patient.flow_state == flow_state)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_treatment_type(self, treatment_type: str, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Get patients by treatment type"""
        return (
            self.db.query(Patient)
            .filter(Patient.treatment_type == treatment_type)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def search_by_name(self, name: str, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Search patients by name (case-insensitive)"""
        return (
            self.db.query(Patient)
            .filter(Patient.name.ilike(f"%{name}%"))
            .offset(skip)
            .limit(limit)
            .all()
        )


