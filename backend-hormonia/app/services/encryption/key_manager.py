"""
Key management service using AWS Secrets Manager.

Security Features:
- Keys stored encrypted in AWS Secrets Manager
- Automatic rotation support
- Audit logging via CloudTrail
- IAM-based access control
- Multi-region replication

Environment Variables:
    AWS_REGION: AWS region (e.g., "us-east-1")
    AWS_SECRET_NAME: Secret name in Secrets Manager
    ENCRYPTION_KEY_CURRENT: Fallback for local development
"""

import os
import json
import logging
from typing import Any, Optional
from datetime import datetime
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class KeyManagementService:
    """
    Manage encryption keys with AWS Secrets Manager.

    Supports:
    - AWS Secrets Manager (production)
    - Environment variables (development/testing)
    - Key rotation
    - Backup/restore
    """

    def __init__(self, use_aws: bool = False):
        """
        Initialize key management service.

        Args:
            use_aws: Use AWS Secrets Manager (True) or environment variables (False)
        """
        self.use_aws = use_aws

        if use_aws:
            try:
                import boto3
                self.secrets_client = boto3.client('secretsmanager')
                self.secret_name = os.getenv("AWS_SECRET_NAME", "hormonia/encryption-keys")
                logger.info(f"Initialized AWS Secrets Manager client for '{self.secret_name}'")
            except ImportError:
                logger.warning("boto3 not installed. Falling back to environment variables.")
                self.use_aws = False
                self.secrets_client = None
        else:
            self.secrets_client = None

    def get_current_key(self) -> str:
        """
        Get current active encryption key.

        Returns:
            Base64-encoded Fernet key

        Raises:
            KeyNotFoundError: If no current key exists
        """
        if self.use_aws:
            return self._get_key_from_aws("current")
        else:
            return self._get_key_from_env("ENCRYPTION_KEY_CURRENT")

    def get_previous_key(self) -> Optional[str]:
        """
        Get previous encryption key (for rotation).

        Returns:
            Base64-encoded Fernet key or None
        """
        if self.use_aws:
            try:
                return self._get_key_from_aws("previous")
            except KeyNotFoundError:
                return None
        else:
            return self._get_key_from_env("ENCRYPTION_KEY_PREVIOUS", required=False)

    def _get_key_from_aws(self, key_type: str) -> str:
        """
        Retrieve key from AWS Secrets Manager.

        Args:
            key_type: "current" or "previous"

        Returns:
            Base64-encoded encryption key

        Raises:
            KeyNotFoundError: If key doesn't exist
            AWSError: If AWS API call fails
        """
        try:
            # Get secret from AWS
            response = self.secrets_client.get_secret_value(
                SecretId=self.secret_name
            )

            # Parse JSON secret
            secret = json.loads(response['SecretString'])

            # Extract key
            key_value = secret.get(key_type)
            if not key_value:
                raise KeyNotFoundError(f"Key type '{key_type}' not found in secret")

            logger.info(f"Retrieved {key_type} key from AWS Secrets Manager")
            return key_value

        except self.secrets_client.exceptions.ResourceNotFoundException:
            raise KeyNotFoundError(f"Secret '{self.secret_name}' not found in AWS")

        except Exception as e:
            logger.error(f"Failed to retrieve key from AWS: {e}")
            raise AWSError(f"Failed to retrieve encryption key: {e}")

    def _get_key_from_env(self, var_name: str, required: bool = True) -> Optional[str]:
        """
        Retrieve key from environment variable (fallback).

        Args:
            var_name: Environment variable name
            required: Raise error if not found

        Returns:
            Base64-encoded encryption key or None
        """
        key_value = os.getenv(var_name)

        if not key_value and required:
            raise KeyNotFoundError(
                f"{var_name} not set. Generate with: "
                f"python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )

        return key_value

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded 32-byte key

        Example:
            >>> key = KeyManagementService.generate_key()
            >>> print(key)
            'Z3rH8BqK...' (44 characters, base64)
        """
        return Fernet.generate_key().decode()

    @staticmethod
    def generate_hash_salt() -> str:
        """
        Generate HMAC salt for searchable hashes.

        Returns:
            64-character hex string

        Example:
            >>> salt = KeyManagementService.generate_hash_salt()
            >>> print(salt)
            'a1b2c3d4...' (64 characters, hex)
        """
        import secrets
        return secrets.token_hex(32)


class KeyNotFoundError(Exception):
    """Raised when encryption key is not found."""
    pass


class AWSError(Exception):
    """Raised when AWS API call fails."""
    pass
