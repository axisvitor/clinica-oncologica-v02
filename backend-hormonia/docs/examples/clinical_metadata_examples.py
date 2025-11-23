"""
Clinical Metadata Examples - Patient JSONB Fields

This file contains practical examples for working with clinical metadata
in the patient.patient_data JSONB field.

Reference: docs/reference/CLINICAL_METADATA_SCHEMA.md
"""

from typing import Dict, Any
from app.utils.patient_metadata_schema import (
    validate_clinical_metadata,
    validate_blood_type,
    validate_emergency_contact,
    get_clinical_fields,
    merge_clinical_metadata,
    extract_clinical_summary,
)


# =========================================================================
# EXAMPLE 1: Creating New Patient with Clinical Data
# =========================================================================

def example_create_patient_with_clinical_data():
    """Example: Create new patient with complete clinical data."""

    # Patient clinical metadata
    clinical_metadata = {
        "medical_history": {
            "allergies": ["Penicillin", "Latex", "Sulfa drugs"],
            "medications": [
                "Metformin 500mg - 2x daily with meals",
                "Lisinopril 10mg - 1x daily morning",
                "Levothyroxine 50mcg - 1x daily fasting"
            ],
            "conditions": [
                "Type 2 Diabetes Mellitus",
                "Essential Hypertension",
                "Hypothyroidism"
            ],
            "family_history": [
                "Breast Cancer (mother, diagnosed age 52)",
                "Type 2 Diabetes (father)",
                "Hypertension (both parents)"
            ],
            "surgeries": [
                {
                    "type": "Appendectomy",
                    "date": "2010-08-15",
                    "notes": "Laparoscopic, no complications"
                },
                {
                    "type": "Cesarean Section",
                    "date": "2015-03-20",
                    "notes": "Planned C-section, healthy delivery"
                }
            ]
        },
        "blood_type": "A+",
        "emergency_contact": {
            "name": "Maria Silva Santos",
            "phone": "+5511987654321",
            "relationship": "Spouse",
            "email": "maria.santos@example.com"
        },
        "preferences": {
            "language": "pt-BR",
            "timezone": "America/Sao_Paulo",
            "notification_enabled": True,
            "notification_time": "09:00"
        }
    }

    # Validate before saving
    validated = validate_clinical_metadata(clinical_metadata, strict=True)

    print("✅ Clinical metadata validated successfully!")
    print(f"Blood type: {validated['blood_type']}")
    print(f"Allergies: {', '.join(validated['medical_history']['allergies'])}")
    print(f"Emergency contact: {validated['emergency_contact']['name']}")

    return validated


# =========================================================================
# EXAMPLE 2: Updating Existing Patient Clinical Data
# =========================================================================

def example_update_patient_clinical_data():
    """Example: Update existing patient's clinical information."""

    # Existing patient metadata
    existing_metadata = {
        "medical_history": {
            "allergies": ["Penicillin"],
            "medications": ["Aspirin 100mg"]
        },
        "preferences": {
            "language": "pt-BR"
        },
        "onboarding": {
            "completed": True,
            "completed_at": "2024-01-15T10:00:00Z"
        }
    }

    # New clinical updates from doctor
    clinical_updates = {
        "medical_history": {
            "medications": [
                "Aspirin 100mg - 1x daily",
                "Metformin 500mg - 2x daily"  # New medication
            ],
            "conditions": ["Type 2 Diabetes"]  # New diagnosis
        },
        "blood_type": "A+",  # Lab results came back
        "emergency_contact": {
            "name": "João Silva",
            "phone": "+5511912345678",
            "relationship": "Son"
        }
    }

    # Merge updates (deep merge for nested structures)
    updated_metadata = merge_clinical_metadata(
        existing=existing_metadata,
        updates=clinical_updates,
        validate_result=True
    )

    print("✅ Patient clinical data updated successfully!")
    print(f"Medications: {updated_metadata['medical_history']['medications']}")
    print(f"New diagnosis: {updated_metadata['medical_history']['conditions']}")
    print(f"Blood type recorded: {updated_metadata['blood_type']}")

    return updated_metadata


# =========================================================================
# EXAMPLE 3: API Endpoint - Get Patient Clinical Summary
# =========================================================================

def example_api_get_patient_clinical_summary():
    """Example: Extract clinical summary for API response."""

    # Patient metadata from database
    patient_metadata = {
        "medical_history": {
            "allergies": ["Penicillin", "Latex"],
            "medications": [
                "Metformin 500mg - 2x daily",
                "Lisinopril 10mg - 1x daily"
            ],
            "conditions": ["Type 2 Diabetes", "Hypertension"]
        },
        "blood_type": "B+",
        "emergency_contact": {
            "name": "Maria Silva",
            "phone": "+5511987654321",
            "relationship": "Spouse"
        },
        "preferences": {
            "language": "pt-BR"
        },
        "onboarding": {
            "completed": True
        }
    }

    # Extract flattened clinical summary for API
    clinical_summary = extract_clinical_summary(patient_metadata)

    # This returns a flat structure perfect for frontend consumption
    api_response = {
        "patient_id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "João Silva",
        "clinical_data": clinical_summary
    }

    print("✅ API response prepared:")
    print(f"  Allergies: {clinical_summary.get('allergies', [])}")
    print(f"  Current medications: {clinical_summary.get('current_medications', [])}")
    print(f"  Comorbidities: {clinical_summary.get('comorbidities', [])}")
    print(f"  Blood type: {clinical_summary.get('blood_type', 'Not recorded')}")
    print(f"  Emergency contact: {clinical_summary.get('emergency_contact_name', 'None')}")

    return api_response


# =========================================================================
# EXAMPLE 4: Validating Individual Fields
# =========================================================================

def example_validate_individual_fields():
    """Example: Validate individual clinical fields."""

    # Validate blood type before saving
    blood_types_to_check = ["A+", "Invalid", "B-", "AB", "O+"]

    print("🩸 Blood Type Validation:")
    for bt in blood_types_to_check:
        is_valid = validate_blood_type(bt)
        status = "✅" if is_valid else "❌"
        print(f"  {status} {bt}: {'Valid' if is_valid else 'Invalid'}")

    # Validate emergency contact
    contacts_to_check = [
        {
            "name": "Maria Silva",
            "phone": "+5511987654321"
        },
        {
            "name": "João Santos",
            "phone": "11987654321"  # Missing + (invalid)
        },
        {
            "phone": "+5511987654321"  # Missing name (invalid)
        }
    ]

    print("\n📞 Emergency Contact Validation:")
    for contact in contacts_to_check:
        is_valid = validate_emergency_contact(contact)
        status = "✅" if is_valid else "❌"
        name = contact.get('name', '(no name)')
        phone = contact.get('phone', '(no phone)')
        print(f"  {status} {name} - {phone}")


# =========================================================================
# EXAMPLE 5: Extracting Only Clinical Fields
# =========================================================================

def example_extract_clinical_fields():
    """Example: Extract only clinical fields from full metadata."""

    # Full patient metadata with mixed data
    full_metadata = {
        "medical_history": {
            "allergies": ["Penicillin"]
        },
        "blood_type": "A+",
        "emergency_contact": {
            "name": "Maria",
            "phone": "+5511987654321"
        },
        "preferences": {  # Not clinical
            "language": "pt-BR",
            "timezone": "America/Sao_Paulo"
        },
        "onboarding": {  # Not clinical
            "completed": True
        },
        "system": {  # Not clinical
            "source": "whatsapp"
        }
    }

    # Extract only clinical fields
    clinical_only = get_clinical_fields(full_metadata)

    print("🏥 Clinical Fields Only:")
    for key, value in clinical_only.items():
        print(f"  {key}: {value}")

    print(f"\nNote: Non-clinical fields (preferences, onboarding, system) were filtered out")

    return clinical_only


# =========================================================================
# EXAMPLE 6: Handling Validation Errors
# =========================================================================

def example_handle_validation_errors():
    """Example: Proper error handling for validation failures."""

    from app.core.exceptions import ValidationError

    # Invalid metadata
    invalid_metadata = {
        "blood_type": "Invalid",  # Wrong format
        "emergency_contact": {
            "name": "Maria",
            "phone": "11987654321"  # Missing + prefix
        }
    }

    # Strict mode - raises exception
    print("🚨 Strict Validation:")
    try:
        validate_clinical_metadata(invalid_metadata, strict=True)
        print("  Validation passed")
    except ValidationError as e:
        print(f"  ❌ Validation failed: {e}")
        print(f"  Error details: {e.details if hasattr(e, 'details') else 'N/A'}")

    # Non-strict mode - returns original data
    print("\n⚠️  Non-Strict Validation:")
    result = validate_clinical_metadata(invalid_metadata, strict=False)
    print(f"  Result: {result}")
    print(f"  Note: Invalid data was returned as-is (no exception)")


# =========================================================================
# EXAMPLE 7: Complete Patient Onboarding Flow
# =========================================================================

def example_patient_onboarding_flow():
    """Example: Complete patient onboarding with clinical data collection."""

    # Step 1: Initial patient creation (minimal data)
    print("📋 Step 1: Initial Patient Creation")
    initial_metadata = {
        "preferences": {
            "language": "pt-BR"
        },
        "onboarding": {
            "completed": False,
            "steps_completed": ["basic_info"]
        }
    }
    print("  ✅ Basic patient created")

    # Step 2: Doctor adds medical history
    print("\n📋 Step 2: Medical History Collection")
    medical_history_update = {
        "medical_history": {
            "allergies": ["Penicillin", "Latex"],
            "conditions": ["Hypertension"]
        }
    }
    metadata_v2 = merge_clinical_metadata(initial_metadata, medical_history_update)
    print("  ✅ Medical history added")

    # Step 3: Lab results come back
    print("\n📋 Step 3: Lab Results")
    lab_results_update = {
        "blood_type": "A+"
    }
    metadata_v3 = merge_clinical_metadata(metadata_v2, lab_results_update)
    print("  ✅ Blood type recorded")

    # Step 4: Emergency contact collected
    print("\n📋 Step 4: Emergency Contact")
    emergency_contact_update = {
        "emergency_contact": {
            "name": "Maria Silva",
            "phone": "+5511987654321",
            "relationship": "Spouse"
        }
    }
    metadata_v4 = merge_clinical_metadata(metadata_v3, emergency_contact_update)
    print("  ✅ Emergency contact added")

    # Step 5: Medications prescribed
    print("\n📋 Step 5: Treatment Plan")
    medications_update = {
        "medical_history": {
            "medications": [
                "Lisinopril 10mg - 1x daily",
                "Aspirin 100mg - 1x daily"
            ]
        }
    }
    final_metadata = merge_clinical_metadata(metadata_v4, medications_update)
    print("  ✅ Medications prescribed")

    # Step 6: Complete onboarding
    print("\n📋 Step 6: Onboarding Complete")
    final_metadata["onboarding"]["completed"] = True
    final_metadata["onboarding"]["steps_completed"].extend([
        "medical_history",
        "lab_results",
        "emergency_contact",
        "treatment_plan"
    ])

    # Validate final state
    validate_clinical_metadata(final_metadata, strict=True)
    print("  ✅ All clinical data validated")

    # Extract summary
    summary = extract_clinical_summary(final_metadata)
    print("\n📊 Clinical Summary:")
    print(f"  Blood type: {summary.get('blood_type')}")
    print(f"  Allergies: {', '.join(summary.get('allergies', []))}")
    print(f"  Comorbidities: {', '.join(summary.get('comorbidities', []))}")
    print(f"  Medications: {len(summary.get('current_medications', []))} prescribed")
    print(f"  Emergency contact: {summary.get('emergency_contact_name')}")

    return final_metadata


# =========================================================================
# EXAMPLE 8: Database Query Patterns
# =========================================================================

def example_database_queries():
    """Example: SQL queries for clinical metadata."""

    queries = {
        "Find patients with specific allergy": """
            SELECT id, name, phone
            FROM patients
            WHERE patient_data->'medical_history'->'allergies' ? 'Penicillin';
        """,

        "Find patients by blood type": """
            SELECT id, name
            FROM patients
            WHERE patient_data->>'blood_type' = 'A+';
        """,

        "Find patients with emergency contacts": """
            SELECT
                id,
                name,
                patient_data->'emergency_contact'->>'name' as emergency_contact_name,
                patient_data->'emergency_contact'->>'phone' as emergency_contact_phone
            FROM patients
            WHERE patient_data->'emergency_contact' IS NOT NULL;
        """,

        "Find patients with diabetes": """
            SELECT id, name
            FROM patients
            WHERE patient_data->'medical_history'->'conditions' ? 'Type 2 Diabetes';
        """,

        "Count patients by blood type": """
            SELECT
                patient_data->>'blood_type' as blood_type,
                COUNT(*) as patient_count
            FROM patients
            WHERE patient_data->>'blood_type' IS NOT NULL
            GROUP BY patient_data->>'blood_type'
            ORDER BY patient_count DESC;
        """
    }

    print("🔍 Example Database Queries:")
    for description, query in queries.items():
        print(f"\n{description}:")
        print(query)


# =========================================================================
# RUN ALL EXAMPLES
# =========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("CLINICAL METADATA EXAMPLES")
    print("=" * 70)

    print("\n" + "=" * 70)
    print("EXAMPLE 1: Create Patient with Clinical Data")
    print("=" * 70)
    example_create_patient_with_clinical_data()

    print("\n" + "=" * 70)
    print("EXAMPLE 2: Update Patient Clinical Data")
    print("=" * 70)
    example_update_patient_clinical_data()

    print("\n" + "=" * 70)
    print("EXAMPLE 3: API Clinical Summary")
    print("=" * 70)
    example_api_get_patient_clinical_summary()

    print("\n" + "=" * 70)
    print("EXAMPLE 4: Validate Individual Fields")
    print("=" * 70)
    example_validate_individual_fields()

    print("\n" + "=" * 70)
    print("EXAMPLE 5: Extract Clinical Fields")
    print("=" * 70)
    example_extract_clinical_fields()

    print("\n" + "=" * 70)
    print("EXAMPLE 6: Handle Validation Errors")
    print("=" * 70)
    example_handle_validation_errors()

    print("\n" + "=" * 70)
    print("EXAMPLE 7: Patient Onboarding Flow")
    print("=" * 70)
    example_patient_onboarding_flow()

    print("\n" + "=" * 70)
    print("EXAMPLE 8: Database Query Patterns")
    print("=" * 70)
    example_database_queries()

    print("\n" + "=" * 70)
    print("ALL EXAMPLES COMPLETED")
    print("=" * 70)
