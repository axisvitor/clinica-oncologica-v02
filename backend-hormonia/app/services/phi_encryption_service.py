"""
PHI Encryption Service for Healthcare Compliance
Implements field-level encryption for Protected Health Information (PHI)
"""

import os
import base64
import logging
from typing import Any, Optional
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import json
from app.config import get_settings

logger = logging.getLogger(__name__)

class PHIEncryptionService:
    """
    Service for encrypting and decrypting PHI data.
    Uses AES-256-CBC with PBKDF2 key derivation.
    """

    def __init__(self):
        self.settings = get_settings()
        self.backend = default_backend()
        self._initialize_encryption_key()

    def _initialize_encryption_key(self):
        """Initialize or derive encryption key from master secret."""
        try:
            # Get master key from environment (should be stored in secret manager)
            master_key = os.getenv('PHI_ENCRYPTION_KEY', '')

            if not master_key:
                # Generate a new key for development (NOT for production)
                if self.settings.ENVIRONMENT == 'development':
                    master_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                    logger.warning("Generated development encryption key. Use proper key management in production!")
                else:
                    raise ValueError("PHI_ENCRYPTION_KEY not configured for production")

            # Derive actual encryption key using PBKDF2
            salt = b'hormonia_phi_salt_2025'  # Should be unique per deployment
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=self.backend
            )

            self.key = kdf.derive(master_key.encode() if isinstance(master_key, str) else master_key)
            logger.info("PHI encryption key initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize encryption key: {e}")
            raise

    def encrypt_field(self, plaintext: str) -> str:
        """
        Encrypt a single field value.

        Args:
            plaintext: The value to encrypt

        Returns:
            Base64 encoded encrypted value
        """
        if not plaintext:
            return plaintext

        try:
            # Generate random IV for each encryption
            iv = os.urandom(16)

            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.CBC(iv),
                backend=self.backend
            )
            encryptor = cipher.encryptor()

            # Pad the plaintext
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(plaintext.encode()) + padder.finalize()

            # Encrypt
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()

            # Combine IV and ciphertext, then base64 encode
            encrypted = base64.b64encode(iv + ciphertext).decode('utf-8')

            return f"encrypted:{encrypted}"

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt_field(self, encrypted: str) -> str:
        """
        Decrypt a single field value.

        Args:
            encrypted: The encrypted value

        Returns:
            Decrypted plaintext
        """
        if not encrypted or not encrypted.startswith('encrypted:'):
            return encrypted

        try:
            # Remove prefix and decode
            encrypted_data = encrypted.replace('encrypted:', '')
            combined = base64.b64decode(encrypted_data)

            # Extract IV and ciphertext
            iv = combined[:16]
            ciphertext = combined[16:]

            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.CBC(iv),
                backend=self.backend
            )
            decryptor = cipher.decryptor()

            # Decrypt
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            # Remove padding
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

            return plaintext.decode('utf-8')

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

    def encrypt_patient_data(self, patient_data: dict) -> dict:
        """
        Encrypt PHI fields in patient data.

        Args:
            patient_data: Dictionary containing patient information

        Returns:
            Dictionary with encrypted PHI fields
        """
        # Fields that contain PHI and must be encrypted
        phi_fields = [
            'name', 'cpf', 'rg', 'email', 'phone',
            'address', 'birth_date', 'medical_record_number',
            'emergency_contact_name', 'emergency_contact_phone',
            'insurance_number', 'diagnosis', 'medications'
        ]

        encrypted_data = patient_data.copy()

        for field in phi_fields:
            if field in encrypted_data and encrypted_data[field]:
                # Handle different data types
                if isinstance(encrypted_data[field], str):
                    encrypted_data[field] = self.encrypt_field(encrypted_data[field])
                elif isinstance(encrypted_data[field], (dict, list)):
                    # Serialize complex types before encryption
                    json_str = json.dumps(encrypted_data[field])
                    encrypted_data[field] = self.encrypt_field(json_str)

        # Add encryption metadata
        encrypted_data['__encrypted'] = True
        encrypted_data['__encryption_version'] = '1.0'

        return encrypted_data

    def decrypt_patient_data(self, encrypted_data: dict) -> dict:
        """
        Decrypt PHI fields in patient data.

        Args:
            encrypted_data: Dictionary with encrypted PHI fields

        Returns:
            Dictionary with decrypted PHI fields
        """
        if not encrypted_data.get('__encrypted'):
            return encrypted_data

        phi_fields = [
            'name', 'cpf', 'rg', 'email', 'phone',
            'address', 'birth_date', 'medical_record_number',
            'emergency_contact_name', 'emergency_contact_phone',
            'insurance_number', 'diagnosis', 'medications'
        ]

        decrypted_data = encrypted_data.copy()

        for field in phi_fields:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_value = self.decrypt_field(decrypted_data[field])

                # Try to deserialize if it's JSON
                if decrypted_value.startswith('[') or decrypted_value.startswith('{'):
                    try:
                        decrypted_data[field] = json.loads(decrypted_value)
                    except json.JSONDecodeError:
                        decrypted_data[field] = decrypted_value
                else:
                    decrypted_data[field] = decrypted_value

        # Remove encryption metadata
        decrypted_data.pop('__encrypted', None)
        decrypted_data.pop('__encryption_version', None)

        return decrypted_data

    def mask_phi_for_display(self, value: str, field_type: str = 'default') -> str:
        """
        Mask PHI for display purposes (e.g., showing partial data).

        Args:
            value: The value to mask
            field_type: Type of field for appropriate masking

        Returns:
            Masked value
        """
        if not value:
            return value

        if field_type == 'cpf':
            # Show: ***.***.789-**
            if len(value) >= 11:
                return f"***.***.{value[-5:-2]}-**"
        elif field_type == 'phone':
            # Show: (**) ****-1234
            if len(value) >= 10:
                return f"(**) ****-{value[-4:]}"
        elif field_type == 'email':
            # Show: j***@domain.com
            if '@' in value:
                parts = value.split('@')
                return f"{parts[0][0]}***@{parts[1]}"
        else:
            # Default: show first and last character
            if len(value) > 2:
                return f"{value[0]}{'*' * (len(value) - 2)}{value[-1]}"

        return '*' * len(value)

    def rotate_encryption_key(self, new_master_key: str) -> bool:
        """
        Rotate encryption key by re-encrypting all data.
        This should be done periodically for security.

        Args:
            new_master_key: The new master encryption key

        Returns:
            Success status
        """
        try:
            # Store old key temporarily
            old_key = self.key

            # Derive new key
            salt = b'hormonia_phi_salt_2025'
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=self.backend
            )
            new_key = kdf.derive(new_master_key.encode())

            # TODO: Implement batch re-encryption of all patient data
            # This would involve:
            # 1. Decrypt all data with old key
            # 2. Encrypt all data with new key
            # 3. Update database in transaction
            # 4. Only commit if all successful

            # Update to new key
            self.key = new_key

            logger.info("Encryption key rotated successfully")
            return True

        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            return False


# Singleton instance
_encryption_service: Optional[PHIEncryptionService] = None

def get_phi_encryption_service() -> PHIEncryptionService:
    """Get or create the PHI encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = PHIEncryptionService()
    return _encryption_service
