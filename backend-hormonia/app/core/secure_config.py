"""
Secure configuration management for production environment.
Implements secret management, encryption, and secure defaults.
"""
import os
import json
import base64
from typing import Any, Dict, Optional
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import logging

logger = logging.getLogger(__name__)


class SecureConfigManager:
    """Manages secure configuration and secrets."""

    def __init__(self, env_file: Optional[str] = None):
        """Initialize secure config manager."""
        self.env_file = env_file or ".env"
        self._cipher = None
        self._secrets = {}
        self._load_encryption_key()
        self._load_secrets()

    def _load_encryption_key(self):
        """Load or generate encryption key for secrets."""
        key_file = Path(".encryption_key")

        if key_file.exists():
            with open(key_file, "rb") as f:
                key = f.read()
        else:
            # Generate new key if not exists
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict permissions
            logger.info("Generated new encryption key")

        self._cipher = Fernet(key)

    def _load_secrets(self):
        """Load secrets from secure storage."""
        secrets_file = Path(".secrets.enc")

        if secrets_file.exists():
            try:
                with open(secrets_file, "rb") as f:
                    encrypted_data = f.read()
                decrypted_data = self._cipher.decrypt(encrypted_data)
                self._secrets = json.loads(decrypted_data.decode())
            except Exception as e:
                logger.error(f"Failed to load secrets: {e}")
                self._secrets = {}
        else:
            # Initialize with default secrets structure
            self._initialize_default_secrets()

    def _initialize_default_secrets(self):
        """Initialize default secrets structure."""
        self._secrets = {
            "database": {
                "password": os.getenv("DB_PASSWORD", ""),
                "service_role_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            },
            "redis": {
                "password": os.getenv("REDIS_PASSWORD", ""),
                "acl_password": self._generate_secure_password()
            },
            "api_keys": {
                "gemini": os.getenv("GEMINI_API_KEY", ""),
                "evolution": os.getenv("EVOLUTION_API_KEY", ""),
                "monthly_quiz_token": os.getenv("MONTHLY_QUIZ_TOKEN_SECRET", "")
            },
            "encryption": {
                "field_encryption_key": self._generate_secure_password(),
                "jwt_secret": os.getenv("SECRET_KEY", "")
            }
        }
        self._save_secrets()

    def _save_secrets(self):
        """Save encrypted secrets to file."""
        try:
            secrets_json = json.dumps(self._secrets)
            encrypted_data = self._cipher.encrypt(secrets_json.encode())

            secrets_file = Path(".secrets.enc")
            with open(secrets_file, "wb") as f:
                f.write(encrypted_data)
            os.chmod(secrets_file, 0o600)  # Restrict permissions
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")

    def _generate_secure_password(self, length: int = 32) -> str:
        """Generate a secure random password."""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def get_secret(self, category: str, key: str, default: Any = None) -> Any:
        """Get a secret value."""
        try:
            return self._secrets.get(category, {}).get(key, default)
        except Exception:
            return default

    def set_secret(self, category: str, key: str, value: Any):
        """Set a secret value."""
        if category not in self._secrets:
            self._secrets[category] = {}
        self._secrets[category][key] = value
        self._save_secrets()

    def get_redis_config(self) -> Dict[str, Any]:
        """Get secure Redis configuration."""
        return {
            "host": os.getenv("REDIS_HOST"),
            "port": int(os.getenv("REDIS_PORT", 6379)),
            "password": self.get_secret("redis", "password"),
            "ssl": os.getenv("REDIS_SSL", "true").lower() == "true",
            "ssl_cert_reqs": os.getenv("REDIS_SSL_CERT_REQS", "required"),
            "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", 25)),
            "socket_timeout": float(os.getenv("REDIS_SOCKET_TIMEOUT", 10.0)),
            "socket_connect_timeout": float(os.getenv("REDIS_SOCKET_TIMEOUT", 10.0)),
            "retry_on_timeout": os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower() == "true",
            "max_retries": int(os.getenv("REDIS_MAX_RETRIES", 3)),
            "health_check_interval": 30,
            "decode_responses": True
        }

    def get_database_config(self) -> Dict[str, Any]:
        """Get secure database configuration."""
        return {
            "url": os.getenv("DATABASE_URL"),
            "pool_size": int(os.getenv("DB_POOL_SIZE", 30)),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", 40)),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", 20)),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", 3600)),
            "pool_pre_ping": True,
            "echo": False,  # Never log SQL in production
            "connect_args": {
                "server_settings": {
                    "application_name": "clinica_oncologica",
                    "jit": "on"
                },
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5
            }
        }

    def get_security_headers(self) -> Dict[str, str]:
        """Get security headers for HTTP responses."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }

    def get_rate_limit_config(self) -> Dict[str, Any]:
        """Get rate limiting configuration."""
        return {
            "quiz": {
                "per_minute": 10,
                "per_hour": 50,
                "per_day": 200,
                "burst_limit": 5
            },
            "webhook": {
                "per_minute": 100,
                "burst_limit": 20
            },
            "public_api": {
                "per_minute": 30,
                "per_hour": 500,
                "burst_limit": 10
            }
        }

    def validate_environment(self) -> Dict[str, bool]:
        """Validate that all required environment variables are set."""
        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "SECRET_KEY",
            "FIREBASE_ADMIN_PROJECT_ID",
            "FIREBASE_ADMIN_CLIENT_EMAIL",
            "FIREBASE_ADMIN_PRIVATE_KEY"
        ]

        validation_results = {}
        for var in required_vars:
            validation_results[var] = bool(os.getenv(var))

        # Check security settings
        auto_provision_flag = os.getenv(
            "AUTO_PROVISION_IDENTITY_USERS",
            os.getenv("AUTO_PROVISION_SUPABASE_USERS", "true")
        )

        security_checks = {
            "REDIS_SSL": os.getenv("REDIS_SSL", "false").lower() == "true",
            "AUTO_PROVISION_IDENTITY_USERS": auto_provision_flag.lower() == "false",
            "ENABLE_AUDIT_LOGGING": os.getenv("ENABLE_AUDIT_LOGGING", "false").lower() == "true",
            "ENABLE_EVOLUTION": os.getenv("ENABLE_EVOLUTION", "false").lower() == "true",
            "FORCE_HTTPS_QUIZ_LINKS": os.getenv("FORCE_HTTPS_QUIZ_LINKS", "false").lower() == "true"
        }

        validation_results.update(security_checks)

        # Log validation results
        for key, value in validation_results.items():
            if not value:
                logger.warning(f"Configuration issue: {key} is not properly configured")

        return validation_results


# Singleton instance
_secure_config = None


def get_secure_config() -> SecureConfigManager:
    """Get the singleton secure config instance."""
    global _secure_config
    if _secure_config is None:
        _secure_config = SecureConfigManager()
    return _secure_config


# Export commonly used functions
def get_secret(category: str, key: str, default: Any = None) -> Any:
    """Get a secret value."""
    return get_secure_config().get_secret(category, key, default)


def get_redis_config() -> Dict[str, Any]:
    """Get secure Redis configuration."""
    return get_secure_config().get_redis_config()


def get_database_config() -> Dict[str, Any]:
    """Get secure database configuration."""
    return get_secure_config().get_database_config()


def validate_environment() -> Dict[str, bool]:
    """Validate environment configuration."""
    return get_secure_config().validate_environment()
