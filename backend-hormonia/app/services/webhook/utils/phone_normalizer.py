"""
Phone number normalization utilities for webhook processing.
Extracted from webhook_processor.py for modularity.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

import httpx

from app.config import settings
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.utils.pii_redaction import mask_phone

logger = logging.getLogger(__name__)


class PhoneNormalizer:
    """
    Phone number normalization and patient lookup utilities.

    Handles E.164 format normalization and multi-strategy patient lookup.
    """
    _lid_resolution_cache: Dict[str, str] = {}

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

    async def resolve_phone_from_lid(
        self, lid_jid: str, instance_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Resolve WhatsApp LID JID to a phone-based JID using Evolution chats.

        Evolution may deliver inbound messages as ``<id>@lid`` while outbound
        sends still use ``<phone>@s.whatsapp.net``. This helper links both
        representations so patient lookup can continue.
        """
        if not isinstance(lid_jid, str) or not lid_jid.endswith("@lid"):
            return None

        instance = instance_name or getattr(settings, "WHATSAPP_EVOLUTION_INSTANCE_NAME", "")
        base_url = getattr(settings, "WHATSAPP_EVOLUTION_API_URL", "").rstrip("/")
        api_key = getattr(settings, "WHATSAPP_EVOLUTION_API_KEY", "")
        if not instance or not base_url or not api_key:
            return None

        cache_key = f"{instance}:{lid_jid}"
        cached_phone = self._lid_resolution_cache.get(cache_key)
        if cached_phone:
            return cached_phone

        try:
            chats = await self._fetch_evolution_chats(
                base_url=base_url,
                api_key=api_key,
                instance_name=instance,
            )
            if not chats:
                return None

            lid_chat = next(
                (
                    chat
                    for chat in chats
                    if isinstance(chat, dict) and chat.get("remoteJid") == lid_jid
                ),
                None,
            )
            if not lid_chat:
                return None

            resolved_jid = self._match_phone_jid_for_lid(lid_chat, chats)
            if not resolved_jid:
                return None

            resolved_phone = self.clean_phone_number(resolved_jid.split("@")[0])
            if not resolved_phone:
                return None

            self._lid_resolution_cache[cache_key] = resolved_phone
            logger.info(
                "Resolved LID JID to phone JID",
                extra={
                    "instance_name": instance,
                    "lid_jid": lid_jid,
                    "resolved_phone": mask_phone(resolved_phone),
                },
            )
            return resolved_phone
        except Exception as exc:
            logger.warning(
                "Failed to resolve LID JID via Evolution chats: %s",
                exc,
                exc_info=True,
            )
            return None

    async def _fetch_evolution_chats(
        self, *, base_url: str, api_key: str, instance_name: str
    ) -> List[Dict[str, Any]]:
        timeout_seconds = float(
            getattr(settings, "WHATSAPP_EVOLUTION_TIMEOUT_SECONDS", 10)
        )
        endpoint = f"{base_url}/chat/findChats/{instance_name}"
        headers = {"apikey": api_key, "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(endpoint, headers=headers, json={})
            if response.status_code != 200:
                logger.warning(
                    "Evolution findChats request failed",
                    extra={
                        "instance_name": instance_name,
                        "status_code": response.status_code,
                    },
                )
                return []

            payload = response.json()
            if isinstance(payload, list):
                return payload
            return []

    def _match_phone_jid_for_lid(
        self, lid_chat: Dict[str, Any], chats: List[Dict[str, Any]]
    ) -> Optional[str]:
        lid_name = self._normalize_chat_name(lid_chat.get("pushName"))
        candidates: List[tuple[bool, datetime, str]] = []
        for chat in chats:
            if not isinstance(chat, dict):
                continue

            remote_jid = str(chat.get("remoteJid") or "")
            if not remote_jid.endswith("@s.whatsapp.net"):
                continue

            chat_name = self._normalize_chat_name(chat.get("pushName"))
            same_name = bool(lid_name and chat_name and lid_name == chat_name)
            chat_updated = self._parse_chat_timestamp(chat.get("updatedAt"))
            if chat_updated is None:
                chat_updated = datetime.fromtimestamp(0, tz=timezone.utc)

            phone_digits = self.clean_phone_number(remote_jid.split("@")[0])
            if not (phone_digits.startswith("55") and len(phone_digits) in (12, 13)):
                continue

            candidates.append((same_name, chat_updated, remote_jid))

        if not candidates:
            return None

        # Simple and deterministic: prefer same pushName, then most recent chat update.
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][2]

    @staticmethod
    def _normalize_chat_name(raw_name: Any) -> str:
        return str(raw_name or "").strip().lower()

    @staticmethod
    def _parse_chat_timestamp(value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            normalized = str(value).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
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
