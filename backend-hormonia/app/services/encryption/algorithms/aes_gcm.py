"""
AES-256-GCM encryption algorithm implementation.

GCM (Galois/Counter Mode) provides both confidentiality and authenticity.
Recommended for new implementations.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .base import BaseAlgorithm


class AESGCMAlgorithm(BaseAlgorithm):
    """
    AES-256-GCM encryption algorithm.

    Features:
    - Authenticated encryption (AEAD)
    - 256-bit key
    - 12-byte nonce (recommended for GCM)
    - Built-in authentication tag

    Format: "encrypted:gcm:{base64(nonce+ciphertext)}"
    """

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt using AES-256-GCM.

        Args:
            plaintext: Value to encrypt

        Returns:
            Encrypted value: "encrypted:gcm:{base64(nonce+ciphertext)}"
        """
        # Generate random nonce (12 bytes recommended for GCM)
        nonce = os.urandom(12)

        # Create AESGCM cipher
        aesgcm = AESGCM(self.keys["phi"])

        # Encrypt (returns ciphertext + tag)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

        # Combine nonce + ciphertext, then base64 encode
        combined = nonce + ciphertext
        encrypted = base64.b64encode(combined).decode("utf-8")

        return f"{self.get_prefix()}{encrypted}"

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt AES-256-GCM encrypted data.

        Args:
            encrypted: Encrypted value with prefix

        Returns:
            Decrypted plaintext

        Raises:
            ValueError: If authentication fails
        """
        # Remove prefix and decode
        encrypted_data = encrypted.replace(self.get_prefix(), "")
        combined = base64.b64decode(encrypted_data)

        # Extract nonce and ciphertext
        nonce = combined[:12]
        ciphertext = combined[12:]

        # Create AESGCM cipher
        aesgcm = AESGCM(self.keys["phi"])

        # Decrypt and verify
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext.decode("utf-8")

    def get_prefix(self) -> str:
        """Get AES-GCM prefix."""
        return "encrypted:gcm:"
