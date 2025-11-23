"""
SQLAlchemy TypeDecorator for automatic field encryption/decryption.

Usage:
    class Patient(Base):
        email = Column(EncryptedString(255))
        diagnosis = Column(EncryptedText)
        metadata = Column(EncryptedJSON)
"""

import json
from typing import Any, Optional
from sqlalchemy.types import TypeDecorator, String, Text
from datetime import date

from app.core.encryption import EncryptionService


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy type for encrypted string fields.

    Automatically encrypts on INSERT/UPDATE and decrypts on SELECT.
    Stores encrypted data as base64-encoded TEXT in database.

    Example:
        class Patient(Base):
            email = Column(EncryptedString(255))  # Encrypted!
            email_hash = Column(String(64), index=True)  # For searching

    Database Storage:
        - Plaintext: "john@example.com" (20 chars)
        - Encrypted: "gAAAAABhZ3rH8..." (~200 chars base64)
        - Storage overhead: ~10x (acceptable for security)
    """

    impl = Text  # Store as TEXT in database (not VARCHAR)
    cache_ok = True  # SQLAlchemy caching safe

    def __init__(self, length: Optional[int] = None, *args, **kwargs):
        """
        Initialize encrypted string type.

        Args:
            length: Original field length (ignored, stored as TEXT)
        """
        super().__init__(*args, **kwargs)
        self.length = length
        self.encryption_service = EncryptionService()

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """
        Encrypt value before storing in database.

        Called automatically during INSERT/UPDATE.
        """
        if value is None:
            return None
        return self.encryption_service.encrypt(value)

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """
        Decrypt value after retrieving from database.

        Called automatically during SELECT.
        """
        if value is None:
            return None
        return self.encryption_service.decrypt(value)


class EncryptedText(TypeDecorator):
    """
    SQLAlchemy type for encrypted text fields (large text).

    Same as EncryptedString but for TEXT columns.
    """

    impl = Text
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encryption_service = EncryptionService()

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        return self.encryption_service.encrypt(value)

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        return self.encryption_service.decrypt(value)


class EncryptedJSON(TypeDecorator):
    """
    SQLAlchemy type for encrypted JSON fields.

    Encrypts entire JSON structure as a string.

    Example:
        class Patient(Base):
            metadata = Column(EncryptedJSON)

        # Usage:
        patient.metadata = {"lab_results": [...], "vitals": {...}}
        # Stored encrypted in database
    """

    impl = Text  # Store encrypted JSON as TEXT
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encryption_service = EncryptionService()

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        """Serialize to JSON, then encrypt."""
        if value is None:
            return None

        # Serialize to JSON string
        json_str = json.dumps(value, ensure_ascii=False)

        # Encrypt JSON string
        return self.encryption_service.encrypt(json_str)

    def process_result_value(self, value: Optional[str], dialect) -> Any:
        """Decrypt, then deserialize from JSON."""
        if value is None:
            return None

        # Decrypt to JSON string
        json_str = self.encryption_service.decrypt(value)

        # Deserialize from JSON
        return json.loads(json_str)


class EncryptedDate(TypeDecorator):
    """
    SQLAlchemy type for encrypted date fields.

    Stores dates as encrypted ISO format strings.
    """

    impl = Text
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encryption_service = EncryptionService()

    def process_bind_param(self, value: Optional[date], dialect) -> Optional[str]:
        if value is None:
            return None

        # Convert date to ISO format string
        date_str = value.isoformat()

        # Encrypt
        return self.encryption_service.encrypt(date_str)

    def process_result_value(self, value: Optional[str], dialect) -> Optional[date]:
        if value is None:
            return None

        # Decrypt
        date_str = self.encryption_service.decrypt(value)

        # Parse ISO format back to date
        return date.fromisoformat(date_str)
