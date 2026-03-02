"""
Phone number normalization utilities for webhook processing.
Extracted from webhook_processor.py for modularity.
"""

import logging
from typing import Optional, Dict, List
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.utils.pii_redaction import mask_phone

logger = logging.getLogger(__name__)


class PhoneNormalizer:
    """
    Phone number normalization and patient lookup utilities.

    Handles E.164 format normalization and multi-strategy patient lookup.
    """
    def __init__(self, patient_repo: PatientRepository):
        """
        Initialize phone normalizer.

        Args:
            patient_repo: Patient repository for lookups
        """
        self.patient_repo = patient_repo

    def normalize_phone_e164(self, phone: str) -> str:
        """
        Normalize phone number to E.164 format (+55...).

        Args:
            phone: Raw phone number (may have +, 55, or neither)

        Returns:
            E.164 formatted phone (+55...)
        """
        # Remove all non-digit characters except +
        cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

        # Remove leading zeros
        cleaned = cleaned.lstrip("0")

        # If already has +, return as-is
        if cleaned.startswith("+"):
            return cleaned

        # If starts with country code (55), add +
        if cleaned.startswith("55"):
            return f"+{cleaned}"

        # Otherwise, assume Brazilian number and add +55
        return f"+55{cleaned}"

    def clean_phone_number(self, phone: str) -> str:
        """
        Clean and normalize phone number from WhatsApp format.

        Preserves + prefix for E.164 format compatibility.
        WhatsApp sends numbers like: "5511987654321@s.whatsapp.net"

        Args:
            phone: Raw phone number from WhatsApp

        Returns:
            Cleaned phone number with + prefix if valid
        """
        # Remove @s.whatsapp.net suffix
        if "@" in phone:
            phone = phone.split("@")[0]

        # Remove non-digit characters except +
        cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

        # Remove leading zeros (but preserve +)
        if cleaned.startswith("+"):
            cleaned = "+" + cleaned[1:].lstrip("0")
        else:
            cleaned = cleaned.lstrip("0")

        logger.debug(f"Phone number cleaned: '{mask_phone(phone)}' -> '{mask_phone(cleaned)}'")
        return cleaned

    def find_patient_by_phone(self, phone: str) -> Optional[Patient]:
        """
        Find patient by phone number with E.164 normalization and fallback strategies.

        Tries multiple formats for maximum compatibility:
        1. E.164 format with + prefix (+55...)
        2. Without + prefix (55...)
        3. Add country code if missing (+55{phone})
        4. Remove country code (last 10-11 digits)

        Args:
            phone: Cleaned phone number

        Returns:
            Patient or None if not found
        """
        from app.utils.pii_redaction import mask_phone
        from app.schemas.validators.phone import build_br_phone_variants
        try:
            candidates: Dict[str, Dict[str, object]] = {}
            queried_variants: set[str] = set()
            attempt_number = 0

            def _add_candidate(candidate: Optional[Patient], label: str) -> None:
                if not candidate:
                    return
                key = str(candidate.id)
                entry = candidates.get(key)
                if entry is None:
                    candidates[key] = {"patient": candidate, "labels": [label]}
                else:
                    entry["labels"].append(label)

            def _lookup_variant(variant: str, strategy_label: str) -> None:
                nonlocal attempt_number
                if not variant or variant in queried_variants:
                    return
                queried_variants.add(variant)
                attempt_number += 1
                logger.info(
                    f"Phone lookup attempt {attempt_number}: "
                    f"{strategy_label} '{mask_phone(variant)}'"
                )
                try:
                    patient = self.patient_repo.get_by_phone(variant)
                except StopIteration:
                    # Defensive for mocked side_effect iterables exhausted in tests.
                    return
                _add_candidate(patient, f"{strategy_label}:{variant}")

            # Strategy 1: Normalize to E.164 and try with +
            normalized = self.normalize_phone_e164(phone)
            _lookup_variant(normalized, "E.164 format")

            # Strategy 2: Try structured BR variants (with/without +, 8/9 digit)
            for variant in build_br_phone_variants(normalized):
                _lookup_variant(variant, "Variant")

            # Strategy 3: Try last 11/10 digits as a final fallback
            without_plus = normalized.lstrip("+")
            if len(without_plus) > 11:
                local_11 = without_plus[-11:]
                _lookup_variant(local_11, "Local 11 digits")

            if len(without_plus) > 10:
                local_10 = without_plus[-10:]
                _lookup_variant(local_10, "Local 10 digits")

            if not candidates:
                logger.warning(
                    f"Patient not found after all phone lookup strategies. "
                    f"Original: {mask_phone(phone)}, Normalized: {mask_phone(normalized)}"
                )
                return None

            if len(candidates) == 1:
                selected = next(iter(candidates.values()))["patient"]
                logger.info(
                    f"Patient found after phone normalization: {mask_phone(normalized)}"
                )
                return selected  # type: ignore[return-value]

            selected = self._select_best_candidate(
                [entry["patient"] for entry in candidates.values()]  # type: ignore[list-item]
            )
            logger.warning(
                "Multiple patients matched phone variants; selected best candidate",
                extra={
                    "phone": mask_phone(normalized),
                    "candidate_ids": list(candidates.keys()),
                    "selected_id": str(selected.id) if selected else None,
                },
            )
            return selected

        except Exception as e:
            logger.error(f"Error finding patient by phone {mask_phone(phone)}: {e}", exc_info=True)
            return None

    def _select_best_candidate(self, patients: List[Patient]) -> Optional[Patient]:
        """Choose the most likely patient when multiple phone variants match."""
        from app.repositories.flow import FlowStateRepository

        if not patients:
            return None

        flow_state_repo = FlowStateRepository(self.patient_repo.db)

        best_patient = None
        best_score = (-1, -1.0, -1.0)

        for patient in patients:
            flow_state = flow_state_repo.get_active_flow(patient.id)
            step_data = flow_state.step_data or {} if flow_state else {}
            awaiting_response = bool(step_data.get("awaiting_response"))
            last_interaction_ts = (
                flow_state.last_interaction_at.timestamp()
                if flow_state and flow_state.last_interaction_at
                else 0.0
            )
            updated_at_ts = (
                patient.updated_at.timestamp() if getattr(patient, "updated_at", None) else 0.0
            )
            score = (1 if awaiting_response else 0, last_interaction_ts, updated_at_ts)
            if score > best_score:
                best_score = score
                best_patient = patient

        return best_patient
