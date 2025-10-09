from datetime import date, datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
import hashlib
import logging
from email_validator import validate_email, EmailNotValidError

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.patient import Patient, FlowState
from app.models.flow import PatientFlowState
from app.models.user import User
from app.repositories.patient import PatientRepository
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
from app.schemas.patient import PatientCreate, PatientUpdate
from app.exceptions import ValidationError
from app.utils.unified_cache import (
    cache,
    get_unified_cache_manager as get_cache_manager,
    cache_patient_data,
    get_cached_patient_data,
    invalidate_patient_cache
)
from app.services.flow_engine import FlowEngine
from app.utils.db_retry import with_db_retry

logger = logging.getLogger(__name__)


class PatientService:
    """Service layer for patient management with data integrity validations"""

    def __init__(self, db: Session, patient_repository: PatientRepository, integrity_service: 'PatientIntegrityService', flow_engine: FlowEngine):
        self.db = db
        self.repository = patient_repository
        self.integrity_service = integrity_service
        self.flow_engine = flow_engine
    
    @with_db_retry(max_retries=3)
    async def create_patient(self, patient_data: PatientCreate, doctor_id: UUID, current_user: Optional[User] = None) -> Patient:
        """Create a new patient with duplicate validation"""
        try:
            # FIX #1: Validate for duplicates and data integrity
            await self.integrity_service.validate_patient_creation(patient_data, doctor_id)

            patient_dict = patient_data.dict()
            patient_dict["doctor_id"] = doctor_id

            # Generate data integrity checksum
            patient_dict["integrity_hash"] = self.integrity_service.generate_patient_hash(patient_dict)

            patient = self.repository.create(patient_dict)

            # Invalidate relevant caches on creation
            cache_manager = get_cache_manager()
            cache_manager.invalidate_pattern(f"patient_list:*:{doctor_id}*", namespace="cache")
            logger.debug(f"Invalidated patient list cache for doctor: {doctor_id}")

            logger.info(f"Patient created successfully: {patient.id} - {patient.name}")

        except ValidationError as e:
            logger.error(f"Patient validation failed: {e}")
            raise
        except IntegrityError as e:
            logger.error(f"Database integrity error during patient creation: {e}")
            self.db.rollback()
            raise ValidationError("Patient creation failed due to data integrity constraints")
        except Exception as e:
            logger.error(f"Unexpected error during patient creation: {e}")
            self.db.rollback()
            raise
        
        # Publish WebSocket event for new patient
        await websocket_events.publish_patient_event(
            event_type=WebSocketEventType.PATIENT_UPDATED,
            patient_id=patient.id,
            patient_name=patient.name,
            doctor_id=doctor_id,
            changes={"action": "created"},
            metadata={"treatment_type": patient.treatment_type}
        )

        # AUTO-TRIGGER: Start flow automatically after patient creation with validation
        try:
            # Determine template based on cancer type or treatment type
            template_name = self._get_default_template(
                patient.cancer_type if hasattr(patient, 'cancer_type') else patient.treatment_type
            )

            if template_name:
                # ENHANCED: Start flow with fallback handling
                # The flow_engine.start_flow() now includes fallback_to_default parameter
                # This ensures patient flows can start even if specific templates are missing
                flow_state = self.flow_engine.start_flow(
                    patient_id=patient.id,
                    flow_type=template_name,
                    initial_data={
                        "user_id": current_user.id if current_user else None,
                        "patient_cancer_type": patient.cancer_type if hasattr(patient, 'cancer_type') else None,
                        "patient_treatment_type": patient.treatment_type,
                        "auto_started": True,
                        "creation_timestamp": datetime.utcnow().isoformat()
                    },
                    fallback_to_default=True  # Enable fallback for missing templates
                )

                # Log success with template details
                actual_template = flow_state.flow_type
                if actual_template != template_name:
                    logger.warning(f"Patient {patient.id}: requested template '{template_name}' not found, using fallback '{actual_template}'")
                else:
                    logger.info(f"Automatic flow started for patient {patient.id} with template {template_name}")

                # Update patient metadata with flow information
                if not patient.patient_metadata:
                    patient.patient_metadata = {}
                patient.patient_metadata.update({
                    "auto_flow_started": True,
                    "requested_template": template_name,
                    "actual_template": actual_template,
                    "fallback_used": actual_template != template_name,
                    "flow_start_time": flow_state.started_at.isoformat()
                })
                self.db.commit()

            else:
                logger.warning(f"No suitable template found for patient {patient.id} (cancer_type: {getattr(patient, 'cancer_type', None)}, treatment_type: {patient.treatment_type})")

        except Exception as e:
            logger.error(f"Failed to start automatic flow for patient {patient.id}: {e}")
            # Don't fail patient creation if flow fails to start
            # Store error info in patient metadata for debugging
            if not patient.patient_metadata:
                patient.patient_metadata = {}
            patient.patient_metadata.update({
                "auto_flow_error": str(e),
                "flow_start_attempted": True,
                "flow_start_failed": True,
                "error_timestamp": datetime.utcnow().isoformat()
            })
            try:
                self.db.commit()
            except Exception as commit_error:
                logger.error(f"Failed to save flow error metadata for patient {patient.id}: {commit_error}")

        return patient
    
    @cache(ttl=300, key_prefix="patient_by_id")
    @with_db_retry(max_retries=3)
    def get_patient(self, patient_id: UUID) -> Optional[Patient]:
        """Get patient by ID with caching (5 min TTL)"""
        logger.debug(f"Fetching patient from database: {patient_id}")
        return self.repository.get_by_id(patient_id)
    
    @with_db_retry(max_retries=3)
    def get_patient_by_phone(self, phone: str) -> Optional[Patient]:
        """Get patient by phone number"""
        return self.repository.get_by_phone(phone)
    
    @with_db_retry(max_retries=3)
    async def update_patient(self, patient_id: UUID, patient_data: PatientUpdate) -> Optional[Patient]:
        """Update patient information"""
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            return None

        update_data = patient_data.dict(exclude_unset=True)
        updated_patient = self.repository.update(patient, update_data)

        # Invalidate patient cache on update
        invalidate_patient_cache(str(patient_id))
        cache_manager = get_cache_manager()
        cache_manager.invalidate_pattern(f"patient_by_id:*:{patient_id}*", namespace="cache")
        cache_manager.invalidate_pattern(f"patient_list:*:{patient.doctor_id}*", namespace="cache")
        logger.debug(f"Invalidated cache for patient: {patient_id}")

        # Invalidate AI cache when patient data changes
        try:
            from app.services.ai_redis_cache import get_ai_cache_service
            ai_cache = await get_ai_cache_service()
            invalidated = await ai_cache.invalidate_patient_cache(patient_id)
            logger.debug(f"Invalidated {invalidated} AI cache entries for patient: {patient_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate AI cache for patient {patient_id}: {e}")

        # Publish WebSocket event for patient update
        await websocket_events.publish_patient_event(
            event_type=WebSocketEventType.PATIENT_UPDATED,
            patient_id=patient_id,
            patient_name=updated_patient.name,
            doctor_id=updated_patient.doctor_id,
            changes=update_data,
            metadata={"action": "updated"}
        )

        return updated_patient
    
    @with_db_retry(max_retries=3)
    def delete_patient(self, patient_id: UUID) -> bool:
        """Delete patient (soft delete recommended)"""
        patient = self.repository.get_by_id(patient_id)
        result = self.repository.delete(patient_id)

        if result and patient:
            # Invalidate caches on deletion
            invalidate_patient_cache(str(patient_id))
            cache_manager = get_cache_manager()
            cache_manager.invalidate_pattern(f"patient_by_id:*:{patient_id}*", namespace="cache")
            cache_manager.invalidate_pattern(f"patient_list:*:{patient.doctor_id}*", namespace="cache")
            logger.debug(f"Invalidated cache for deleted patient: {patient_id}")

        return result
    
    @with_db_retry(max_retries=3)
    def get_patients_by_doctor(self, doctor_id: UUID, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Get all patients for a doctor"""
        return self.repository.get_by_doctor(doctor_id, skip, limit)
    
    @cache(ttl=300, key_prefix="patient_list")
    @with_db_retry(max_retries=3)
    def list_patients(
        self,
        *,
        doctor_id: UUID,
        page: int,
        size: int,
        search: Optional[str] = None,
        flow_state: Optional[FlowState] = None,
        treatment_type: Optional[str] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
    ) -> tuple[list[Patient], int]:
        """List patients with pagination and optional filtering (cached 5 min)."""
        logger.debug(f"Fetching patient list for doctor: {doctor_id}")
        return self.repository.get_paginated(
            doctor_id=doctor_id,
            page=page,
            limit=size,
            search=search,
            flow_state=flow_state,
            treatment_type=treatment_type,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
        )
    @with_db_retry(max_retries=3)
    async def activate_patient(self, patient_id: UUID) -> Optional[Patient]:
        """Activate patient and set flow state to active"""
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            return None
        
        update_data = {"flow_state": "ACTIVE"}
        updated_patient = self.repository.update(patient, update_data)
        
        # Publish WebSocket event for flow state change
        await websocket_events.publish_patient_event(
            event_type=WebSocketEventType.PATIENT_FLOW_CHANGED,
            patient_id=patient_id,
            patient_name=updated_patient.name,
            doctor_id=updated_patient.doctor_id,
            changes={"flow_state": "ACTIVE"},
            metadata={"action": "activated"}
        )
        
        return updated_patient
    
    @with_db_retry(max_retries=3)
    async def pause_patient(self, patient_id: UUID) -> Optional[Patient]:
        """Pause patient flow"""
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            return None
        
        update_data = {"flow_state": "PAUSED"}
        updated_patient = self.repository.update(patient, update_data)
        
        # Publish WebSocket event for flow state change
        await websocket_events.publish_patient_event(
            event_type=WebSocketEventType.PATIENT_FLOW_CHANGED,
            patient_id=patient_id,
            patient_name=updated_patient.name,
            doctor_id=updated_patient.doctor_id,
            changes={"flow_state": "PAUSED"},
            metadata={"action": "paused"}
        )
        
        return updated_patient
    
    @with_db_retry(max_retries=3)
    def complete_patient_treatment(self, patient_id: UUID) -> Optional[Patient]:
        """Mark patient treatment as completed"""
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            return None
        
        update_data = {"flow_state": "COMPLETED"}
        return self.repository.update(patient, update_data)
    
    @with_db_retry(max_retries=3)
    def update_patient_day(self, patient_id: UUID, day: int) -> Optional[Patient]:
        """Update patient's current day in treatment"""
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            return None
        
        update_data = {"current_day": day}
        return self.repository.update(patient, update_data)
    
    @with_db_retry(max_retries=3)
    def search_patients(self, name: str, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Search patients by name"""
        return self.repository.search_by_name(name, skip, limit)
    
    @with_db_retry(max_retries=3)
    def get_patients_by_flow_state(self, flow_state: str, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Get patients by flow state"""
        return self.repository.get_by_flow_state(flow_state, skip, limit)

    @with_db_retry(max_retries=3)
    async def merge_duplicate_patients(self, primary_patient_id: UUID, duplicate_patient_id: UUID) -> Patient:
        """Merge duplicate patients into primary patient record"""
        try:
            return await self.integrity_service.merge_patients(primary_patient_id, duplicate_patient_id)
        except Exception as e:
            logger.error(f"Patient merge failed: {e}")
            raise

    def _get_default_template(self, cancer_or_treatment_type: Optional[str]) -> Optional[str]:
        """
        Map cancer type or treatment type to default flow template.
        This ensures every new patient automatically starts a relevant flow.
        Maps to actual flow_types in database (hormone_therapy_1, etc.)
        """
        if not cancer_or_treatment_type:
            return "initial_15_days"  # Default generic flow

        # Normalize the type for matching
        type_lower = cancer_or_treatment_type.lower().strip()

        # Mapping based on treatment types - aligned with database flow_kinds
        template_mapping = {
            # Hormone therapy
            "hormone": "hormone_therapy_1",
            "hormonal": "hormone_therapy_1",
            "hormone_therapy": "hormone_therapy_1",
            "hormonioterapia": "hormone_therapy_1",

            # Chemotherapy
            "chemotherapy": "chemotherapy_cycle_1",
            "quimio": "chemotherapy_cycle_1",
            "quimioterapia": "chemotherapy_cycle_1",

            # Initial onboarding
            "initial": "initial_15_days",
            "onboarding": "initial_15_days",

            # Monthly follow-up
            "monthly": "days_16_45",
            "followup": "days_16_45",
        }

        # Find matching template
        for key, template in template_mapping.items():
            if key in type_lower:
                logger.info(f"Selected template '{template}' for type '{cancer_or_treatment_type}'")
                return template

        # Default template if no specific match
        logger.info(f"Using default template 'initial_15_days' for type '{cancer_or_treatment_type}'")
        return "initial_15_days"


class PatientIntegrityService:
    """Service for patient data integrity validation and management"""

    def __init__(self, db: Session, patient_repository: PatientRepository):
        self.db = db
        self.repository = patient_repository

    @with_db_retry(max_retries=3)
    async def validate_patient_creation(self, patient_data: PatientCreate, doctor_id: UUID) -> None:
        """FIX #1: Comprehensive validation for patient creation"""
        try:
            # Validate email format if provided
            if patient_data.email:
                try:
                    validate_email(patient_data.email)
                except EmailNotValidError as e:
                    raise ValidationError(f"Invalid email format: {e}")

            # Validate CPF if provided (now checks both direct attribute and metadata for compatibility)
            cpf = None
            if hasattr(patient_data, 'cpf') and patient_data.cpf:
                cpf = patient_data.cpf
            elif hasattr(patient_data, 'patient_data') and patient_data.patient_data:
                cpf = patient_data.patient_data.get('cpf')

            if cpf:
                self._validate_cpf(cpf)
                # Check for duplicates by CPF
                existing_cpf = await self._check_duplicate_cpf(cpf)
                if existing_cpf:
                    raise ValidationError(f"Patient with CPF {cpf} already exists: {existing_cpf.name}")

            # Check for duplicates by email
            if patient_data.email:
                existing_email = await self._check_duplicate_email(patient_data.email)
                if existing_email:
                    raise ValidationError(f"Patient with email {patient_data.email} already exists: {existing_email.name}")

            # Check for duplicates by phone (already handled by DB constraints)
            existing_phone = self.repository.get_by_phone(patient_data.phone)
            if existing_phone:
                raise ValidationError(f"Patient with phone {patient_data.phone} already exists: {existing_phone.name}")

            # Validate treatment data consistency
            if patient_data.treatment_type and patient_data.treatment_start_date:
                if patient_data.treatment_start_date > date.today():
                    raise ValidationError("Treatment start date cannot be in the future")

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Patient validation error: {e}")
            raise ValidationError(f"Patient validation failed: {str(e)}")

    @with_db_retry(max_retries=3)
    async def _check_duplicate_cpf(self, cpf: str) -> Optional[Patient]:
        """Check for existing patient with same CPF"""
        try:
            # FIX: Use SQLAlchemy ORM query against the dedicated 'cpf' column
            existing_patient = self.db.query(Patient).filter(Patient.cpf == cpf).first()
            return existing_patient
        except Exception as e:
            logger.error(f"CPF duplicate check failed: {e}")
            return None

    @with_db_retry(max_retries=3)
    async def _check_duplicate_email(self, email: str) -> Optional[Patient]:
        """Check for existing patient with same email"""
        try:
            from sqlalchemy import func
            existing = self.db.query(Patient).filter(
                func.lower(Patient.email) == email.lower()
            ).first()
            return existing
        except Exception as e:
            logger.error(f"Email duplicate check failed: {e}")
            return None

    def _validate_cpf(self, cpf: str) -> bool:
        """Validate Brazilian CPF format and check digit"""
        try:
            # Remove non-numeric characters
            cpf = ''.join(filter(str.isdigit, cpf))

            # Check if CPF has 11 digits
            if len(cpf) != 11:
                raise ValidationError("CPF must have 11 digits")

            # Check for known invalid CPFs (all same digits)
            if cpf in ['00000000000', '11111111111', '22222222222', '33333333333',
                      '44444444444', '55555555555', '66666666666', '77777777777',
                      '88888888888', '99999999999']:
                raise ValidationError("Invalid CPF: cannot be all same digits")

            # Validate CPF check digits
            def calc_digit(cpf_partial):
                total = sum(int(digit) * (len(cpf_partial) + 1 - i) for i, digit in enumerate(cpf_partial))
                remainder = total % 11
                return '0' if remainder < 2 else str(11 - remainder)

            # Check first digit
            if cpf[9] != calc_digit(cpf[:9]):
                raise ValidationError("Invalid CPF: first check digit is incorrect")

            # Check second digit
            if cpf[10] != calc_digit(cpf[:10]):
                raise ValidationError("Invalid CPF: second check digit is incorrect")

            return True

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"CPF validation error: {e}")
            raise ValidationError(f"CPF validation failed: {str(e)}")

    def generate_patient_hash(self, patient_data: Dict[str, Any]) -> str:
        """Generate integrity hash for patient data"""
        try:
            # Create hash from critical fields
            hash_fields = {
                'phone': patient_data.get('phone', ''),
                'name': patient_data.get('name', ''),
                'email': patient_data.get('email', ''),
                'cpf': patient_data.get('patient_data', {}).get('cpf', '') if patient_data.get('patient_data') else ''
            }

            # Sort fields for consistent hashing
            hash_string = '|'.join(f"{k}:{v}" for k, v in sorted(hash_fields.items()))

            return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()

        except Exception as e:
            logger.error(f"Hash generation failed: {e}")
            return ""

    @with_db_retry(max_retries=3)
    async def merge_patients(self, primary_patient_id: UUID, duplicate_patient_id: UUID) -> Patient:
        """Merge duplicate patient records"""
        try:
            primary_patient = self.repository.get_by_id(primary_patient_id)
            duplicate_patient = self.repository.get_by_id(duplicate_patient_id)

            if not primary_patient or not duplicate_patient:
                raise ValidationError("One or both patients not found")

            if primary_patient.id == duplicate_patient.id:
                raise ValidationError("Cannot merge patient with itself")

            # Merge strategy: primary patient keeps identity, duplicate data is merged
            merge_metadata = {}

            # Merge metadata
            if primary_patient.patient_data:
                merge_metadata.update(primary_patient.patient_data)
            if duplicate_patient.patient_data:
                for key, value in duplicate_patient.patient_data.items():
                    if key not in merge_metadata and value:
                        merge_metadata[key] = value

            # Update primary patient with merged data
            updates = {
                'patient_data': merge_metadata,
                'email': primary_patient.email or duplicate_patient.email,
                'birth_date': primary_patient.birth_date or duplicate_patient.birth_date,
                'treatment_type': primary_patient.treatment_type or duplicate_patient.treatment_type,
                'treatment_start_date': primary_patient.treatment_start_date or duplicate_patient.treatment_start_date
            }

            # Migrate related records
            await self._migrate_patient_relationships(duplicate_patient_id, primary_patient_id)

            # Update primary patient
            updated_patient = self.repository.update(primary_patient, updates)

            # Soft delete duplicate patient
            await self._soft_delete_patient(duplicate_patient_id)

            logger.info(f"Patients merged successfully: {duplicate_patient_id} -> {primary_patient_id}")

            return updated_patient

        except Exception as e:
            logger.error(f"Patient merge failed: {e}")
            self.db.rollback()
            raise

    @with_db_retry(max_retries=3)
    async def _migrate_patient_relationships(self, from_patient_id: UUID, to_patient_id: UUID) -> None:
        """Migrate all relationships from duplicate to primary patient"""
        try:
            # Update messages
            from app.models.message import Message
            self.db.query(Message).filter(
                Message.patient_id == from_patient_id
            ).update({'patient_id': to_patient_id})

            # Update flow states
            from app.models.flow import PatientFlowState
            self.db.query(PatientFlowState).filter(
                PatientFlowState.patient_id == from_patient_id
            ).update({'patient_id': to_patient_id})

            # Update alerts
            from app.models.alert import Alert
            self.db.query(Alert).filter(
                Alert.patient_id == from_patient_id
            ).update({'patient_id': to_patient_id})

            self.db.commit()

        except Exception as e:
            logger.error(f"Relationship migration failed: {e}")
            self.db.rollback()
            raise

    @with_db_retry(max_retries=3)
    async def _soft_delete_patient(self, patient_id: UUID) -> None:
        """Soft delete patient by updating metadata"""
        try:
            patient = self.repository.get_by_id(patient_id)
            if patient:
                patient.patient_data = patient.patient_data or {}
                patient.patient_data['deleted'] = True
                patient.patient_data['deleted_at'] = date.today().isoformat()
                patient.flow_state = FlowState.INACTIVE
                self.db.commit()

        except Exception as e:
            logger.error(f"Soft delete failed: {e}")
            self.db.rollback()
            raise


