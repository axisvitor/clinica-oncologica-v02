from typing import Any, List, Optional
from uuid import UUID
from datetime import date, datetime


from app.repositories.treatment import TreatmentRepository
from app.models.treatment import Treatment, TreatmentStatus, TreatmentType
from app.schemas.v2.treatment import TreatmentV2Create, TreatmentV2Update
from app.utils.db_retry import with_db_retry

class TreatmentService:
    def __init__(self, db: Any, repository: TreatmentRepository):
        self.db = db
        self.repository = repository

    @with_db_retry()
    def create_treatment(self, data: TreatmentV2Create, doctor_id: UUID) -> Treatment:
        create_data = data.dict(exclude={"treatment_type", "status"})
        
        # Enums
        create_data["treatment_type"] = TreatmentType(data.treatment_type.lower())
        if data.status:
            create_data["status"] = TreatmentStatus(data.status.lower())
        else:
            create_data["status"] = TreatmentStatus.PLANNED
            
        create_data["doctor_id"] = doctor_id
        
        new_treatment = Treatment(**create_data)
        self.db.add(new_treatment)
        self.db.commit()
        self.db.refresh(new_treatment)
        return new_treatment

    @with_db_retry()
    def update_treatment(self, id: UUID, data: TreatmentV2Update) -> Optional[Treatment]:
        treatment = self.repository.get_by_id(id)
        if not treatment or not treatment.is_active:
            return None
            
        update_data = data.dict(exclude_unset=True)
        
        # Enum conversion
        if "treatment_type" in update_data:
            update_data["treatment_type"] = TreatmentType(update_data["treatment_type"].lower())
        if "status" in update_data:
            update_data["status"] = TreatmentStatus(update_data["status"].lower())
            
        for k, v in update_data.items():
            setattr(treatment, k, v)
            
        self.db.commit()
        self.db.refresh(treatment)
        return treatment

    @with_db_retry()
    def delete_treatment(self, id: UUID) -> bool:
        treatment = self.repository.get_by_id(id)
        if not treatment: return False
        
        treatment.is_active = False
        treatment.status = TreatmentStatus.CANCELLED
        self.db.commit()
        return True

    @with_db_retry()
    def activate_treatment(self, id: UUID) -> Optional[Treatment]:
        treatment = self.repository.get_by_id(id)
        if not treatment or not treatment.is_active: return None
        
        treatment.status = TreatmentStatus.ACTIVE
        self.db.commit()
        self.db.refresh(treatment)
        return treatment
