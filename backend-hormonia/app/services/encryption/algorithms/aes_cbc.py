"""
AES-256-CBC encryption algorithm implementation.

CBC (Cipher Block Chaining) mode for backward compatibility with legacy systems.
Use AES-GCM for new implementations.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

from .base import BaseAlgorithm


class AESCBCAlgorithm(BaseAlgorithm):
    """
    AES-256-CBC encryption algorithm.

    Features:
    - 256-bit key
    - 16-byte IV (initialization vector)
    - PKCS7 padding
    - Legacy compatibility

    Format: "encrypted:{base64(iv+ciphertext)}"
    """

    def __init__(self, keys):
        """Initialize with encryption keys."""
        super().__init__(keys)
        self.backend = default_backend()

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt using AES-256-CBC.

        Args:
            plaintext: Value to encrypt

        Returns:
            Encrypted value: "encrypted:{base64(iv+ciphertext)}"
        """
        # Generate random IV
        iv = os.urandom(16)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.keys["phi"]), modes.CBC(iv), backend=self.backend
        )
        encryptor = cipher.encryptor()

        # Pad the plaintext
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode()) + padder.finalize()

        # Encrypt
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # Combine IV and ciphertext, then base64 encode
        combined = iv + ciphertext
        encrypted = base64.b64encode(combined).decode("utf-8")

        return f"{self.get_prefix()}{encrypted}"

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt AES-256-CBC encrypted data.

        Args:
            encrypted: Encrypted value with prefix

        Returns:
            Decrypted plaintext
        """
        # Remove prefix and decode
        encrypted_data = encrypted.replace(self.get_prefix(), "")
        combined = base64.b64decode(encrypted_data)

        # Extract IV and ciphertext
        iv = combined[:16]
        ciphertext = combined[16:]

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.keys["phi"]), modes.CBC(iv), backend=self.backend
        )
        decryptor = cipher.decryptor()

        # Decrypt
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # Remove padding
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

        return plaintext.decode("utf-8")

    def get_prefix(self) -> str:
        """Get AES-CBC prefix."""
        return "encrypted:"
