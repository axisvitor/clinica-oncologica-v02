"""
Patient Metadata JSONB Schema Validation - Clinical Fields Extension.

This module extends the base jsonb_validator with focused validation for
clinical fields stored in patient_data (metadata) JSONB column.

Reference: V2 API Evolution - Clinical Fields
Related: app/utils/jsonb_validator.py

Clinical Fields Added:
- allergies: List of known allergies
- current_medications: List of current medications (alias for medical_history.medications)
- comorbidities: Pre-existing conditions (alias for medical_history.conditions)
- blood_type: Blood type in standard format (A+, B-, etc.)
- emergency_contact_name: Emergency contact name
- emergency_contact_phone: Emergency contact phone (E.164 format)

Usage:
    from app.utils.patient_metadata_schema import validate_clinical_metadata

    # Validate clinical fields in patient metadata
    metadata = {
        "medical_history": {
            "allergies": ["Penicillin", "Peanuts"],
            "medications": ["Aspirin 100mg"],
            "conditions": ["Diabetes Type 2"]
        },
        "blood_type": "A+",
        "emergency_contact": {
            "name": "Maria Silva",
            "phone": "+5511987654321"
        }
    }

    validated = validate_clinical_metadata(metadata)
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator, ValidationError as PydanticValidationError
from app.core.exceptions import ValidationError


# =========================================================================
# PYDANTIC SCHEMAS FOR CLINICAL DATA
# =========================================================================


class BloodTypeValidator(BaseModel):
    """Blood type validation."""
    blood_type: str = Field(
        ...,
        pattern="^(A|B|AB|O)[+-]$",
        description="Blood type in standard format (A+, B-, AB+, O-, etc.)"
    )


class EmergencyContactSchema(BaseModel):
    """Emergency contact information schema."""
    name: str = Field(..., min_length=1, max_length=200, description="Emergency contact name")
    phone: str = Field(..., description="Emergency contact phone in E.164 format")
    relationship: Optional[str] = Field(None, max_length=100, description="Relationship to patient")
    email: Optional[str] = Field(None, description="Emergency contact email")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number in E.164 format."""
        if not v.startswith('+'):
            raise ValueError('Phone must start with country code (+)')
        # E.164 format: +[1-9]\d{1,14}
        if not v[1:].isdigit() or len(v) < 8 or len(v) > 16:
            raise ValueError('Phone must be in E.164 format: +[country][number]')
        return v


class MedicalHistorySchema(BaseModel):
    """Medical history schema - extends base jsonb_validator structure."""
    allergies: Optional[List[str]] = Field(
        None,
        description="Known allergies (medications, foods, environmental)"
    )
    medications: Optional[List[str]] = Field(
        None,
        description="Current medications with dosage"
    )
    conditions: Optional[List[str]] = Field(
        None,
        description="Pre-existing medical conditions (comorbidities)"
    )
    family_history: Optional[List[str]] = Field(None, description="Family medical history")
    surgeries: Optional[List[Dict[str, Any]]] = Field(None, description="Past surgical procedures")

    @field_validator('allergies', 'medications', 'conditions', 'family_history')
    @classmethod
    def validate_unique_items(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Ensure list items are unique."""
        if v is None:
            return v
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for item in v:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique


class ClinicalMetadataSchema(BaseModel):
    """
    Complete clinical metadata schema for patient_data JSONB.

    This schema validates the clinical fields stored in the patient.patient_data
    (metadata JSONB column). It's designed to be backward compatible with
    existing data while enforcing validation for new clinical fields.
    """
    medical_history: Optional[MedicalHistorySchema] = Field(
        None,
        description="Medical history including allergies, medications, conditions"
    )
    blood_type: Optional[str] = Field(
        None,
        pattern="^(A|B|AB|O)[+-]$",
        description="Blood type"
    )
    emergency_contact: Optional[EmergencyContactSchema] = Field(
        None,
        description="Emergency contact information"
    )

    # Allow other fields (backward compatibility)
    class Config:
        extra = "allow"


# =========================================================================
# VALIDATION FUNCTIONS
# =========================================================================


def validate_clinical_metadata(
    metadata: Dict[str, Any],
    strict: bool = True
) -> Dict[str, Any]:
    """
    Validate clinical fields in patient metadata.

    This function extracts and validates clinical-specific fields from the
    patient metadata JSONB. It works alongside the base jsonb_validator to
    ensure data integrity for clinical information.

    Args:
        metadata: The full patient metadata dictionary
        strict: If True, raise ValidationError on failure. If False, return original data.

    Returns:
        The validated metadata (same as input if valid)

    Raises:
        ValidationError: If clinical fields don't pass validation (when strict=True)

    Examples:
        >>> metadata = {
        ...     "medical_history": {
        ...         "allergies": ["Penicillin"],
        ...         "medications": ["Aspirin 100mg"]
        ...     },
        ...     "blood_type": "A+",
        ...     "emergency_contact": {
        ...         "name": "Maria Silva",
        ...         "phone": "+5511987654321"
        ...     }
        ... }
        >>> validated = validate_clinical_metadata(metadata)

        >>> bad_metadata = {"blood_type": "Invalid"}
        >>> validate_clinical_metadata(bad_metadata)  # Raises ValidationError
    """
    if not metadata:
        return {}

    try:
        # Validate using Pydantic schema
        validated_schema = ClinicalMetadataSchema(**metadata)

        # Return the original metadata (Pydantic validated the structure)
        # We don't use validated_schema.dict() because we want to preserve
        # all fields (including those not in the schema due to extra="allow")
        return metadata

    except PydanticValidationError as e:
        error_message = f"Invalid clinical metadata: {e}"
        error_details = {
            "errors": [
                {
                    "field": ".".join(str(loc) for loc in err["loc"]),
                    "message": err["msg"],
                    "type": err["type"]
                }
                for err in e.errors()
            ]
        }

        if strict:
            raise ValidationError(error_message, error_details)
        else:
            # In non-strict mode, just return original data
            return metadata


def validate_blood_type(blood_type: str) -> bool:
    """
    Validate blood type format.

    Args:
        blood_type: Blood type string to validate

    Returns:
        True if valid, False otherwise

    Examples:
        >>> validate_blood_type("A+")
        True
        >>> validate_blood_type("Invalid")
        False
    """
    try:
        BloodTypeValidator(blood_type=blood_type)
        return True
    except PydanticValidationError:
        return False


def validate_emergency_contact(contact: Dict[str, Any]) -> bool:
    """
    Validate emergency contact information.

    Args:
        contact: Emergency contact dictionary

    Returns:
        True if valid, False otherwise

    Examples:
        >>> contact = {"name": "Maria", "phone": "+5511987654321"}
        >>> validate_emergency_contact(contact)
        True
    """
    try:
        EmergencyContactSchema(**contact)
        return True
    except PydanticValidationError:
        return False


def get_clinical_fields(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract clinical fields from patient metadata.

    This function extracts only the clinical-specific fields, making it easier
    to work with just the clinical data subset.

    Args:
        metadata: Full patient metadata

    Returns:
        Dictionary containing only clinical fields

    Examples:
        >>> metadata = {
        ...     "medical_history": {"allergies": ["Penicillin"]},
        ...     "blood_type": "A+",
        ...     "preferences": {"language": "pt-BR"}  # Not clinical
        ... }
        >>> clinical = get_clinical_fields(metadata)
        >>> print(clinical.keys())  # ['medical_history', 'blood_type']
    """
    if not metadata:
        return {}

    clinical_field_names = {
        'medical_history',
        'blood_type',
        'emergency_contact'
    }

    return {
        key: value
        for key, value in metadata.items()
        if key in clinical_field_names
    }


def merge_clinical_metadata(
    existing: Optional[Dict[str, Any]],
    updates: Dict[str, Any],
    validate_result: bool = True
) -> Dict[str, Any]:
    """
    Safely merge clinical metadata updates into existing metadata.

    This function handles deep merging of nested clinical data structures
    (like medical_history) while preserving existing non-clinical fields.

    Args:
        existing: Current metadata (or None)
        updates: New clinical metadata to merge
        validate_result: If True, validate merged result

    Returns:
        Merged metadata

    Raises:
        ValidationError: If merged result is invalid (when validate_result=True)

    Examples:
        >>> existing = {
        ...     "medical_history": {"allergies": ["Penicillin"]},
        ...     "preferences": {"language": "pt-BR"}
        ... }
        >>> updates = {
        ...     "medical_history": {"medications": ["Aspirin"]},
        ...     "blood_type": "A+"
        ... }
        >>> merged = merge_clinical_metadata(existing, updates)
        >>> # Result preserves allergies, adds medications and blood_type
    """
    if existing is None:
        existing = {}

    # Deep copy to avoid modifying original
    result = existing.copy()

    # Handle nested medical_history specially
    if 'medical_history' in updates:
        if 'medical_history' in result:
            # Deep merge medical_history
            result['medical_history'] = {
                **result['medical_history'],
                **updates['medical_history']
            }
        else:
            result['medical_history'] = updates['medical_history']

        # Remove from updates to avoid double-processing
        remaining_updates = {k: v for k, v in updates.items() if k != 'medical_history'}
    else:
        remaining_updates = updates

    # Merge remaining fields
    for key, value in remaining_updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Deep merge for nested dicts (like emergency_contact)
            result[key] = {**result[key], **value}
        else:
            # Replace for non-dict values
            result[key] = value

    if validate_result:
        return validate_clinical_metadata(result)

    return result


# =========================================================================
# HELPER FUNCTIONS FOR API ENDPOINTS
# =========================================================================


def extract_clinical_summary(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract a clinical summary from patient metadata for API responses.

    This creates a flattened, API-friendly representation of clinical data
    that's easier to consume in frontend applications.

    Args:
        metadata: Full patient metadata

    Returns:
        Flattened clinical summary

    Examples:
        >>> metadata = {
        ...     "medical_history": {
        ...         "allergies": ["Penicillin"],
        ...         "medications": ["Aspirin"]
        ...     },
        ...     "blood_type": "A+"
        ... }
        >>> summary = extract_clinical_summary(metadata)
        >>> print(summary)
        {
            "allergies": ["Penicillin"],
            "current_medications": ["Aspirin"],
            "blood_type": "A+"
        }
    """
    if not metadata:
        return {}

    summary = {}

    # Extract from medical_history
    medical_history = metadata.get('medical_history', {})
    if medical_history:
        if 'allergies' in medical_history:
            summary['allergies'] = medical_history['allergies']
        if 'medications' in medical_history:
            summary['current_medications'] = medical_history['medications']
        if 'conditions' in medical_history:
            summary['comorbidities'] = medical_history['conditions']

    # Extract direct fields
    if 'blood_type' in metadata:
        summary['blood_type'] = metadata['blood_type']

    # Extract emergency contact
    emergency_contact = metadata.get('emergency_contact', {})
    if emergency_contact:
        if 'name' in emergency_contact:
            summary['emergency_contact_name'] = emergency_contact['name']
        if 'phone' in emergency_contact:
            summary['emergency_contact_phone'] = emergency_contact['phone']

    return summary


__all__ = [
    "ClinicalMetadataSchema",
    "MedicalHistorySchema",
    "EmergencyContactSchema",
    "BloodTypeValidator",
    "validate_clinical_metadata",
    "validate_blood_type",
    "validate_emergency_contact",
    "get_clinical_fields",
    "merge_clinical_metadata",
    "extract_clinical_summary",
]
