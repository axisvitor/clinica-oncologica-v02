from typing import Any, Optional
from uuid import UUID
from datetime import datetime


from app.repositories.medication import MedicationRepository
from app.models.medication import Medication
from app.schemas.v2.medication import MedicationV2Create, MedicationV2Update
from app.utils.db_retry import with_db_retry


class MedicationService:
    def __init__(self, db: Any, repository: MedicationRepository):
        self.db = db
        self.repository = repository

    @with_db_retry()
    def create_medication(
        self,
        data: MedicationV2Create,
        prescribed_by_id: UUID,
        treatment_id: Optional[UUID] = None,
    ) -> Medication:
        create_data = data.dict(
            exclude={"patient_id", "prescribed_by_id", "treatment_id"}
        )
        create_data["patient_id"] = UUID(data.patient_id)
        create_data["prescribed_by_id"] = prescribed_by_id
        if treatment_id:
            create_data["treatment_id"] = treatment_id

        new_medication = Medication(**create_data)
        self.db.add(new_medication)
        self.db.commit()
        self.db.refresh(new_medication)
        return new_medication

    @with_db_retry()
    def update_medication(
        self, id: UUID, data: MedicationV2Update
    ) -> Optional[Medication]:
        medication = self.repository.get_by_id(id)
        if not medication:
            return None

        update_data = data.dict(exclude_unset=True)

        # Handle UUIDs
        if "prescribed_by_id" in update_data and update_data["prescribed_by_id"]:
            update_data["prescribed_by_id"] = UUID(update_data["prescribed_by_id"])
        if "treatment_id" in update_data and update_data["treatment_id"]:
            update_data["treatment_id"] = UUID(update_data["treatment_id"])

        for k, v in update_data.items():
            setattr(medication, k, v)

        self.db.commit()
        self.db.refresh(medication)
        return medication

    @with_db_retry()
    def delete_medication(self, id: UUID) -> bool:
        medication = self.repository.get_by_id(id)
        if not medication:
            return False

        medication.is_active = False
        medication.deleted_at = datetime.utcnow()
        self.db.commit()
        return True
