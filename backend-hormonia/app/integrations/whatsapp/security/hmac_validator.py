"""
HMAC signature validation for WhatsApp webhooks.
"""

import hashlib
import hmac
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class WebhookHMACValidator:
    """Validate webhook HMAC signatures for multiple algorithms."""

    _ALGORITHMS = {
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }

    @classmethod
    def _parse_signature(cls, signature: str) -> Tuple[str, str]:
        """Parse signature header value into algorithm and digest."""
        signature = signature.strip()
        if "=" in signature:
            algorithm, digest = signature.split("=", 1)
            return algorithm.strip().lower(), digest.strip()
        if len(signature) == 128:
            return "sha512", signature
        return "sha256", signature

    @classmethod
    def validate_signature(cls, payload: bytes, signature: str, secret: str) -> bool:
        """
        Validate HMAC signature for payload.

        Supports signature formats:
        - sha256=<hex>
        - sha512=<hex>
        - <hex> (defaults to sha256, or sha512 if length is 128)
        """
        if not secret:
            logger.warning("Webhook HMAC secret missing")
            return False

        if not signature:
            logger.warning("Webhook HMAC signature missing")
            return False

        try:
            algorithm, digest = cls._parse_signature(signature)
            if algorithm not in cls._ALGORITHMS:
                logger.warning(
                    "Unsupported webhook HMAC algorithm",
                    extra={"algorithm": algorithm},
                )
                return False

            computed = hmac.new(
                secret.encode("utf-8"), payload, cls._ALGORITHMS[algorithm]
            ).hexdigest()
            valid = hmac.compare_digest(computed, digest)
            if not valid:
                logger.warning(
                    "Webhook HMAC validation failed",
                    extra={
                        "algorithm": algorithm,
                        "signature_length": len(digest),
                    },
                )
            return valid
        except Exception as exc:
            logger.error(
                "Webhook HMAC validation error",
                exc_info=True,
                extra={"error": str(exc)},
            )
            return False
