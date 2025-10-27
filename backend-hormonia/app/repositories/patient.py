"""
Patient repository with soft delete support
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.repositories.base import BaseRepository


class PatientRepository(BaseRepository[Patient]):
    """Patient repository with soft delete filtering"""
    
    def __init__(self, db: Session):
        super().__init__(db, Patient)
    
    def get_by_id(self, patient_id: UUID) -> Optional[Patient]:
        """Get patient by ID (only active patients)"""
        return self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.deleted_at.is_(None)
        ).first()
    
    def get_by_id_including_deleted(self, patient_id: UUID) -> Optional[Patient]:
        """Get patient by ID including soft-deleted patients"""
        return self.db.query(Patient).filter(Patient.id == patient_id).first()
    
    def get_by_phone(self, phone: str) -> Optional[Patient]:
        """Get patient by phone (only active patients)"""
        return self.db.query(Patient).filter(
            Patient.phone == phone,
            Patient.deleted_at.is_(None)
        ).first()
    
    def get_by_doctor(self, doctor_id: UUID, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Get active patients for a doctor"""
        return self.db.query(Patient).filter(
            Patient.doctor_id == doctor_id,
            Patient.deleted_at.is_(None)
        ).offset(skip).limit(limit).all()
    
    def get_all_active(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Get all active (non-deleted) patients"""
        return self.db.query(Patient).filter(
            Patient.deleted_at.is_(None)
        ).offset(skip).limit(limit).all()
    
    def get_all_deleted(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Get all soft-deleted patients"""
        return self.db.query(Patient).filter(
            Patient.deleted_at.isnot(None)
        ).offset(skip).limit(limit).all()
    
    def count_active(self, **filters) -> int:
        """Count active patients with optional filters"""
        query = self.db.query(Patient).filter(Patient.deleted_at.is_(None))
        
        for field, value in filters.items():
            if hasattr(Patient, field) and value is not None:
                query = query.filter(getattr(Patient, field) == value)
        
        return query.count()
    
    def count_deleted(self) -> int:
        """Count soft-deleted patients"""
        return self.db.query(Patient).filter(Patient.deleted_at.isnot(None)).count()
    
    def search_active(self, search_term: str, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Search active patients by name, email, or phone"""
        search_pattern = f"%{search_term}%"
        return self.db.query(Patient).filter(
            Patient.deleted_at.is_(None)
        ).filter(
            (Patient.name.ilike(search_pattern)) |
            (Patient.email.ilike(search_pattern)) |
            (Patient.phone.ilike(search_pattern))
        ).offset(skip).limit(limit).all()