"""Standalone helpers for compacting patient context before injecting into AI prompts."""

from typing import Any, Dict


def clip_value(value: Any, *, max_len: int = 240, max_items: int = 5) -> Any:
    """Clip long values for prompt context safety."""
    if value is None:
        return None
    if isinstance(value, str):
        if len(value) <= max_len:
            return value
        return value[: max_len - 1].rstrip() + "…"
    if isinstance(value, list):
        return [
            clip_value(v, max_len=max_len, max_items=max_items)
            for v in value[:max_items]
        ]
    if isinstance(value, dict):
        clipped: Dict[str, Any] = {}
        for key, val in value.items():
            clipped_val = clip_value(val, max_len=max_len, max_items=max_items)
            if clipped_val is not None:
                clipped[key] = clipped_val
        return clipped
    return value


def compact_patient_context(patient_context: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce patient context to a compact, prompt-safe subset."""
    if not patient_context:
        return {}

    allowlist = {
        "flow_type",
        "flow_kind",
        "current_day",
        "treatment_day",
        "send_mode",
        "current_day_message_index",
        "awaiting_response",
        "timestamp",
        "treatment_type",
        "treatment_phase",
        "diagnosis",
    }

    compact: Dict[str, Any] = {}
    for key in allowlist:
        if key in patient_context:
            value = clip_value(patient_context.get(key))
            if value is not None:
                compact[key] = value

    comm_prefs = patient_context.get("communication_preferences")
    if isinstance(comm_prefs, dict):
        comm_allowlist = {
            "formality_level",
            "emoji_usage",
            "preferred_greetings",
            "question_style",
            "emotional_tone",
            "message_length_preference",
        }
        filtered = {
            key: clip_value(comm_prefs.get(key))
            for key in comm_allowlist
            if comm_prefs.get(key) is not None
        }
        if filtered:
            compact["communication_preferences"] = filtered

    medical_context = patient_context.get("medical_context")
    if isinstance(medical_context, dict):
        med_allowlist = {
            "treatment_type",
            "treatment_phase",
            "diagnosis",
        }
        filtered = {
            key: clip_value(medical_context.get(key))
            for key in med_allowlist
            if medical_context.get(key) is not None
        }
        if filtered:
            compact["medical_context"] = filtered

    return compact
