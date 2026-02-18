from app.ai.context_compactor import compact_patient_context


def test_compact_patient_context_omits_patient_identifier_fields():
    patient_context = {
        "patient_id": "patient-123",
        "patient_name": "Maria Silva",
        "name": "Maria Silva",
        "flow_type": "daily_follow_up",
        "flow_kind": "onboarding",
        "current_day": 7,
        "diagnosis": "linfoma",
    }

    compacted = compact_patient_context(patient_context)

    assert "patient_id" not in compacted
    assert "patient_name" not in compacted
    assert "name" not in compacted
    assert compacted["flow_type"] == "daily_follow_up"
    assert compacted["flow_kind"] == "onboarding"
    assert compacted["current_day"] == 7
    assert compacted["diagnosis"] == "linfoma"


def test_compact_patient_context_preserves_non_sensitive_nested_allowlists():
    patient_context = {
        "communication_preferences": {
            "formality_level": "friendly",
            "question_style": "open",
            "preferred_greetings": ["Oi", "Bom dia"],
            "patient_name": "Maria Silva",
            "phone": "+5511999999999",
        },
        "medical_context": {
            "treatment_type": "chemotherapy",
            "treatment_phase": "maintenance",
            "diagnosis": "lymphoma",
            "patient_id": "patient-123",
        },
    }

    compacted = compact_patient_context(patient_context)

    assert compacted["communication_preferences"] == {
        "formality_level": "friendly",
        "question_style": "open",
        "preferred_greetings": ["Oi", "Bom dia"],
    }
    assert compacted["medical_context"] == {
        "treatment_type": "chemotherapy",
        "treatment_phase": "maintenance",
        "diagnosis": "lymphoma",
    }


def test_compact_patient_context_still_clips_non_sensitive_fields():
    long_text = "x" * 400
    patient_context = {
        "flow_kind": long_text,
        "communication_preferences": {
            "preferred_greetings": [f"greeting-{i}" for i in range(10)],
        },
        "medical_context": {
            "diagnosis": long_text,
        },
    }

    compacted = compact_patient_context(patient_context)

    assert compacted["flow_kind"].endswith("…")
    assert len(compacted["flow_kind"]) == 240
    assert len(compacted["communication_preferences"]["preferred_greetings"]) == 5
    assert compacted["medical_context"]["diagnosis"].endswith("…")
    assert len(compacted["medical_context"]["diagnosis"]) == 240
