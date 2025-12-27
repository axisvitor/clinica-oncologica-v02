"""
Phone number normalization utilities for webhook processing.
Extracted from webhook_processor.py for modularity.
"""

import logging
from typing import Optional

from app.models.patient import Patient
from app.repositories.patient import PatientRepository

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
        from app.utils.pii_masking import mask_phone
        try:
            # Strategy 1: Normalize to E.164 and try with +
            normalized = self.normalize_phone_e164(phone)
            logger.info(f"Phone lookup attempt 1: E.164 format '{mask_phone(normalized)}'")
            patient = self.patient_repo.get_by_phone(normalized)
            if patient:
                logger.info(f"Patient found with E.164 format: {mask_phone(normalized)}")
                return patient

            # Strategy 2: Try without + prefix
            without_plus = normalized.lstrip("+")
            logger.info(f"Phone lookup attempt 2: Without + prefix '{mask_phone(without_plus)}'")
            patient = self.patient_repo.get_by_phone(without_plus)
            if patient:
                logger.info(f"Patient found without + prefix: {mask_phone(without_plus)}")
                return patient

            # Strategy 3: Try with +55 prefix if not already present
            if not phone.startswith("+55") and not phone.startswith("55"):
                with_prefix = f"+55{phone}"
                logger.info(
                    f"Phone lookup attempt 3: Adding +55 prefix '{mask_phone(with_prefix)}'"
                )
                patient = self.patient_repo.get_by_phone(with_prefix)
                if patient:
                    logger.info(f"Patient found with +55 prefix: {mask_phone(with_prefix)}")
                    return patient

            # Strategy 4: Try last 11 digits (Brazilian mobile with DDD)
            if len(without_plus) > 11:
                local_11 = without_plus[-11:]
                logger.info(f"Phone lookup attempt 4: Local 11 digits '{mask_phone(local_11)}'")
                patient = self.patient_repo.get_by_phone(local_11)
                if patient:
                    logger.info(f"Patient found with local 11 digits: {mask_phone(local_11)}")
                    return patient

            # Strategy 5: Try last 10 digits (Brazilian mobile without 9)
            if len(without_plus) > 10:
                local_10 = without_plus[-10:]
                logger.info(f"Phone lookup attempt 5: Local 10 digits '{mask_phone(local_10)}'")
                patient = self.patient_repo.get_by_phone(local_10)
                if patient:
                    logger.info(f"Patient found with local 10 digits: {mask_phone(local_10)}")
                    return patient

            logger.warning(
                f"Patient not found after all phone lookup strategies. "
                f"Original: {mask_phone(phone)}, Normalized: {mask_phone(normalized)}"
            )
            return None

        except Exception as e:
            logger.error(f"Error finding patient by phone {mask_phone(phone)}: {e}", exc_info=True)
            return None
