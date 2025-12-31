#!/usr/bin/env python3
"""
Environment Validation Script

Validates environment configuration for both development and production:
- Check required environment variables
- Validate variable formats and values
- Check file permissions
- Validate external dependencies
- Security audit

Usage:
    python scripts/validate_env.py [--strict] [--json]
"""

import sys
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('EnvValidator')


class Severity(Enum):
    """Validation severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Validation issue"""
    variable: str
    severity: Severity
    message: str
    suggestion: Optional[str] = None


class EnvironmentValidator:
    """Validates environment configuration"""

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.issues: List[ValidationIssue] = []

    def validate(self) -> bool:
        """Run all validation checks"""
        logger.info("=" * 80)
        logger.info("Environment Validation")
        logger.info("=" * 80)
        logger.info(f"Mode: {'STRICT' if self.strict else 'NORMAL'}")

        # Run all validation checks
        self._check_required_variables()
        self._validate_database_url()
        self._validate_redis_url()
        self._validate_security_keys()
        self._validate_api_settings()
        self._validate_external_services()
        self._check_file_permissions()
        self._security_audit()

        # Print summary
        self._print_summary()

        # Determine if validation passed
        has_errors = any(i.severity in [Severity.ERROR, Severity.CRITICAL] for i in self.issues)
        has_warnings = any(i.severity == Severity.WARNING for i in self.issues)

        if self.strict and has_warnings:
            return False

        return not has_errors

    def _check_required_variables(self) -> None:
        """Check for required environment variables"""
        logger.info("\n[1/8] Checking required variables...")

        required = {
            # Database
            'DATABASE_URL': 'PostgreSQL connection URL',
            # Redis
            'REDIS_URL': 'Redis connection URL',
            # Security
            'SECRET_KEY': 'Application secret key for JWT signing',
            'ENCRYPTION_KEY': 'Encryption key for sensitive data',
            'SECURITY_CSRF_SECRET_KEY': 'Secret key for CSRF protection',
            'HASH_SALT': 'Salt for hashing sensitive data',
            # API
            'CORS_ORIGINS': 'Allowed CORS origins',
            # Firebase
            'FIREBASE_ADMIN_PROJECT_ID': 'Firebase project ID',
        }

        for var, description in required.items():
            value = os.getenv(var)
            if not value:
                self.issues.append(ValidationIssue(
                    variable=var,
                    severity=Severity.CRITICAL,
                    message=f"Required variable missing: {description}",
                    suggestion=f"Set {var} in .env file or environment"
                ))

    def _validate_database_url(self) -> None:
        """Validate DATABASE_URL format"""
        logger.info("\n[2/8] Validating DATABASE_URL...")

        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            return

        # Check PostgreSQL format
        if not db_url.startswith('postgresql://') and not db_url.startswith('postgres://'):
            self.issues.append(ValidationIssue(
                variable='DATABASE_URL',
                severity=Severity.ERROR,
                message='DATABASE_URL must start with postgresql:// or postgres://',
                suggestion='Format: postgresql://user:password@host:port/database'
            ))

        # Check for localhost in production
        if 'localhost' in db_url or '127.0.0.1' in db_url:
            env = os.getenv('APP_ENVIRONMENT', 'development')
            if env == 'production':
                self.issues.append(ValidationIssue(
                    variable='DATABASE_URL',
                    severity=Severity.WARNING,
                    message='Using localhost database in production',
                    suggestion='Use remote database for production'
                ))

        # Check for password
        if '@' not in db_url or ':' not in db_url.split('@')[0]:
            self.issues.append(ValidationIssue(
                variable='DATABASE_URL',
                severity=Severity.WARNING,
                message='DATABASE_URL may be missing credentials',
                suggestion='Ensure format includes username and password'
            ))

    def _validate_redis_url(self) -> None:
        """Validate REDIS_URL format"""
        logger.info("\n[3/8] Validating REDIS_URL...")

        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            self.issues.append(ValidationIssue(
                variable='REDIS_URL',
                severity=Severity.WARNING,
                message='REDIS_URL not set (some features will be disabled)',
                suggestion='Set REDIS_URL for caching and session management'
            ))
            return

        # Check Redis format
        if not redis_url.startswith('redis://') and not redis_url.startswith('rediss://'):
            self.issues.append(ValidationIssue(
                variable='REDIS_URL',
                severity=Severity.ERROR,
                message='REDIS_URL must start with redis:// or rediss://',
                suggestion='Format: redis://[:password@]host:port/db'
            ))

        # Check for TLS in production
        if redis_url.startswith('redis://'):
            env = os.getenv('APP_ENVIRONMENT', 'development')
            if env == 'production':
                self.issues.append(ValidationIssue(
                    variable='REDIS_URL',
                    severity=Severity.WARNING,
                    message='Using non-TLS Redis connection in production',
                    suggestion='Use rediss:// (Redis with TLS) for production'
                ))

    def _validate_security_keys(self) -> None:
        """Validate security-related keys"""
        logger.info("\n[4/8] Validating security keys...")

        # Check SECRET_KEY
        secret_key = os.getenv('SECRET_KEY')
        if secret_key:
            if len(secret_key) < 32:
                self.issues.append(ValidationIssue(
                    variable='SECRET_KEY',
                    severity=Severity.ERROR,
                    message=f'SECRET_KEY too short ({len(secret_key)} chars, minimum 32)',
                    suggestion='Generate strong key: python -c "import secrets; print(secrets.token_urlsafe(32))"'
                ))

            # Check for common weak values
            weak_patterns = ['secret', 'password', '123', 'test', 'demo']
            if any(pattern in secret_key.lower() for pattern in weak_patterns):
                self.issues.append(ValidationIssue(
                    variable='SECRET_KEY',
                    severity=Severity.CRITICAL,
                    message='SECRET_KEY appears to be weak or default value',
                    suggestion='Generate cryptographically strong random key'
                ))

        # Check ENCRYPTION_KEY
        encryption_key = os.getenv('ENCRYPTION_KEY')
        if encryption_key:
            if len(encryption_key) != 32:
                self.issues.append(ValidationIssue(
                    variable='ENCRYPTION_KEY',
                    severity=Severity.ERROR,
                    message=f'ENCRYPTION_KEY must be exactly 32 bytes ({len(encryption_key)} found)',
                    suggestion='Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
                ))

    def _validate_api_settings(self) -> None:
        """Validate API configuration"""
        logger.info("\n[5/8] Validating API settings...")

        # Check CORS origins
        cors_origins = os.getenv('CORS_ORIGINS', '')
        if cors_origins == '*':
            self.issues.append(ValidationIssue(
                variable='CORS_ORIGINS',
                severity=Severity.WARNING,
                message='CORS allows all origins (*) - security risk',
                suggestion='Specify exact origins: http://localhost:3000,https://yourdomain.com'
            ))

        # Check API rate limiting
        rate_limit = os.getenv('RATE_LIMIT_ENABLE_SERVICE')
        if rate_limit and rate_limit.lower() == 'false':
            self.issues.append(ValidationIssue(
                variable='RATE_LIMIT_ENABLE_SERVICE',
                severity=Severity.WARNING,
                message='Rate limiting is disabled',
                suggestion='Enable rate limiting for production: RATE_LIMIT_ENABLE_SERVICE=true'
            ))

    def _validate_external_services(self) -> None:
        """Validate external service configuration"""
        logger.info("\n[6/8] Validating external services...")

        # Check Firebase configuration
        firebase_creds = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if firebase_creds:
            creds_path = Path(firebase_creds)
            if not creds_path.exists():
                self.issues.append(ValidationIssue(
                    variable='FIREBASE_CREDENTIALS_PATH',
                    severity=Severity.ERROR,
                    message=f'Firebase credentials file not found: {firebase_creds}',
                    suggestion='Ensure the credentials file exists at the specified path'
                ))

        # Check SMTP configuration
        smtp_host = os.getenv('SMTP_HOST')
        if smtp_host:
            smtp_user = os.getenv('SMTP_USER')
            smtp_pass = os.getenv('SMTP_PASSWORD')

            if not smtp_user or not smtp_pass:
                self.issues.append(ValidationIssue(
                    variable='SMTP_USER/SMTP_PASSWORD',
                    severity=Severity.WARNING,
                    message='SMTP host set but credentials missing',
                    suggestion='Set both SMTP_USER and SMTP_PASSWORD'
                ))

    def _check_file_permissions(self) -> None:
        """Check critical file permissions"""
        logger.info("\n[7/8] Checking file permissions...")

        # Check .env file
        env_file = project_root / ".env"
        if env_file.exists():
            stat_info = env_file.stat()
            mode = oct(stat_info.st_mode)[-3:]

            # .env should be 600 (read/write owner only)
            if mode not in ["600", "400"]:
                self.issues.append(
                    ValidationIssue(
                        variable=".env file",
                        severity=Severity.WARNING,
                        message=f".env file has permissive permissions: {mode}",
                        suggestion="Set secure permissions: chmod 600 .env",
                    )
                )

        # Check credentials files (excluding venv and node_modules)
        creds_patterns = ["*credentials*.json", "*.key", "*.pem"]
        exclude_dirs = {
            "venv",
            "venv_linux",
            "node_modules",
            ".git",
            ".mypy_cache",
            ".ruff_cache",
        }

        for pattern in creds_patterns:
            for file in project_root.rglob(pattern):
                # Skip excluded directories
                if any(ex in file.parts for ex in exclude_dirs):
                    continue

                if file.is_file():
                    stat_info = file.stat()
                    mode = oct(stat_info.st_mode)[-3:]

                    if mode not in ["600", "400"]:
                        self.issues.append(
                            ValidationIssue(
                                variable=f"{file.name}",
                                severity=Severity.WARNING,
                                message=f"Credentials file has permissive permissions: {mode}",
                                suggestion=f"Set secure permissions: chmod 600 {file}",
                            )
                        )

    def _security_audit(self) -> None:
        """Run security audit"""
        logger.info("\n[8/8] Running security audit...")

        # Check for hardcoded secrets in code
        sensitive_patterns = [
            (r'password\s*=\s*["\'](?!.*\$\{)(.+)["\']', 'Hardcoded password'),
            (r'api[_-]?key\s*=\s*["\'](?!.*\$\{)(.+)["\']', 'Hardcoded API key'),
            (r'secret\s*=\s*["\'](?!.*\$\{)(.+)["\']', 'Hardcoded secret'),
        ]

        # Check debug mode in production
        debug_mode = os.getenv('APP_ENABLE_DEBUG', 'false')
        env = os.getenv('APP_ENVIRONMENT', 'development')

        if debug_mode.lower() == 'true' and env == 'production':
            self.issues.append(ValidationIssue(
                variable='APP_ENABLE_DEBUG',
                severity=Severity.CRITICAL,
                message='Debug mode enabled in production',
                suggestion='Set APP_ENABLE_DEBUG=false for production'
            ))

    def _print_summary(self) -> None:
        """Print validation summary"""
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 80)

        # Count by severity
        by_severity = {severity: [] for severity in Severity}
        for issue in self.issues:
            by_severity[issue.severity].append(issue)

        # Print by severity
        for severity in [Severity.CRITICAL, Severity.ERROR, Severity.WARNING, Severity.INFO]:
            issues = by_severity[severity]
            if issues:
                symbol = "🔴" if severity in [Severity.CRITICAL, Severity.ERROR] else "⚠️" if severity == Severity.WARNING else "ℹ️"
                logger.info(f"\n{symbol} {severity.value.upper()} ({len(issues)}):")

                for issue in issues:
                    logger.info(f"  • {issue.variable}: {issue.message}")
                    if issue.suggestion:
                        logger.info(f"    → {issue.suggestion}")

        logger.info("\n" + "-" * 80)
        logger.info(f"Total issues: {len(self.issues)}")

        critical = len(by_severity[Severity.CRITICAL])
        errors = len(by_severity[Severity.ERROR])
        warnings = len(by_severity[Severity.WARNING])

        logger.info(f"Critical: {critical} | Errors: {errors} | Warnings: {warnings}")
        logger.info("=" * 80)

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary"""
        return {
            'strict_mode': self.strict,
            'total_issues': len(self.issues),
            'by_severity': {
                severity.value: len([i for i in self.issues if i.severity == severity])
                for severity in Severity
            },
            'issues': [asdict(issue) for issue in self.issues]
        }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate environment configuration')
    parser.add_argument('--strict', action='store_true',
                        help='Treat warnings as errors')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')
    args = parser.parse_args()

    validator = EnvironmentValidator(strict=args.strict)
    success = validator.validate()

    if args.json:
        print(json.dumps(validator.to_dict(), indent=2, default=str))

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
