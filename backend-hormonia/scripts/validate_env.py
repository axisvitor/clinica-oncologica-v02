#!/usr/bin/env python3
"""
Environment Variable Validation Script

Validates that all required environment variables are set and properly configured
before starting the application. Helps catch configuration issues early.

Usage:
    python scripts/validate_env.py [--strict] [--environment=production]

Options:
    --strict          Fail on warnings (treat warnings as errors)
    --environment     Specify environment (development/staging/production)
                     Default: Read from ENVIRONMENT variable or 'development'

Exit Codes:
    0 - All validations passed
    1 - Critical errors found
    2 - Warnings found (only with --strict)

Examples:
    # Basic validation
    python scripts/validate_env.py

    # Strict validation for production
    python scripts/validate_env.py --strict --environment=production

    # Use in CI/CD pipeline
    python scripts/validate_env.py --environment=staging || exit 1
"""

import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Callable
from urllib.parse import urlparse


class Severity(Enum):
    """Validation error severity levels."""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationResult:
    """Result of an environment variable validation."""
    variable: str
    severity: Severity
    message: str
    passed: bool = False


class EnvironmentValidator:
    """Validates environment variables for different environments."""

    def __init__(self, environment: str = "development", strict: bool = False):
        self.environment = environment
        self.strict = strict
        self.results: List[ValidationResult] = []

    def validate_required(self, var_name: str, description: str = "") -> bool:
        """Validate that a required variable exists and is non-empty."""
        value = os.getenv(var_name)

        if not value:
            self.results.append(ValidationResult(
                variable=var_name,
                severity=Severity.CRITICAL,
                message=f"Required variable not set. {description}",
                passed=False
            ))
            return False

        self.results.append(ValidationResult(
            variable=var_name,
            severity=Severity.INFO,
            message="✓ Set",
            passed=True
        ))
        return True

    def validate_optional(self, var_name: str, default: str, description: str = "") -> bool:
        """Validate optional variable (will use default if not set)."""
        value = os.getenv(var_name)

        if not value:
            self.results.append(ValidationResult(
                variable=var_name,
                severity=Severity.INFO,
                message=f"Using default: {default}. {description}",
                passed=True
            ))
            return True

        self.results.append(ValidationResult(
            variable=var_name,
            severity=Severity.INFO,
            message="✓ Set",
            passed=True
        ))
        return True

    def validate_url(self, var_name: str, required_scheme: Optional[str] = None) -> bool:
        """Validate that variable is a valid URL."""
        if not self.validate_required(var_name, "Must be a valid URL"):
            return False

        value = os.getenv(var_name)
        try:
            parsed = urlparse(value)

            if not parsed.scheme or not parsed.netloc:
                self.results.append(ValidationResult(
                    variable=var_name,
                    severity=Severity.CRITICAL,
                    message=f"Invalid URL format: {value}",
                    passed=False
                ))
                return False

            if required_scheme and parsed.scheme != required_scheme:
                severity = Severity.CRITICAL if self.environment == "production" else Severity.WARNING
                self.results.append(ValidationResult(
                    variable=var_name,
                    severity=severity,
                    message=f"Expected scheme '{required_scheme}', got '{parsed.scheme}'",
                    passed=False
                ))
                return False

            return True

        except Exception as e:
            self.results.append(ValidationResult(
                variable=var_name,
                severity=Severity.CRITICAL,
                message=f"URL parsing error: {e}",
                passed=False
            ))
            return False

    def validate_database_url(self) -> bool:
        """Validate DATABASE_URL with SSL requirements for production."""
        if not self.validate_url("DATABASE_URL"):
            return False

        value = os.getenv("DATABASE_URL")
        parsed = urlparse(value)

        # Check for SSL in production
        if self.environment == "production":
            if "sslmode" not in value:
                self.results.append(ValidationResult(
                    variable="DATABASE_URL",
                    severity=Severity.CRITICAL,
                    message="Production database must use SSL (sslmode=require)",
                    passed=False
                ))
                return False

            if "sslmode=require" not in value and "sslmode=verify-full" not in value:
                self.results.append(ValidationResult(
                    variable="DATABASE_URL",
                    severity=Severity.WARNING,
                    message="Consider using sslmode=require or sslmode=verify-full",
                    passed=True
                ))

        return True

    def validate_redis_url(self) -> bool:
        """Validate REDIS_URL with SSL requirements for production."""
        if not self.validate_url("REDIS_URL"):
            return False

        value = os.getenv("REDIS_URL")

        # Check for SSL scheme in production
        if self.environment == "production":
            if not value.startswith("rediss://"):
                self.results.append(ValidationResult(
                    variable="REDIS_URL",
                    severity=Severity.CRITICAL,
                    message="Production Redis must use SSL (rediss:// scheme)",
                    passed=False
                ))
                return False

        return True

    def validate_secret(self, var_name: str, min_length: int = 32) -> bool:
        """Validate that secret is set and meets minimum length."""
        if not self.validate_required(var_name, f"Must be at least {min_length} characters"):
            return False

        value = os.getenv(var_name)

        # Check for placeholder values
        placeholders = ["CHANGE_THIS", "YOUR_", "PASSWORD", "SECRET", "KEY_HERE"]
        if any(placeholder in value for placeholder in placeholders):
            self.results.append(ValidationResult(
                variable=var_name,
                severity=Severity.CRITICAL,
                message="Secret contains placeholder text. Must be changed for production.",
                passed=False
            ))
            return False

        # Check minimum length
        if len(value) < min_length:
            severity = Severity.CRITICAL if self.environment == "production" else Severity.WARNING
            self.results.append(ValidationResult(
                variable=var_name,
                severity=severity,
                message=f"Secret too short ({len(value)} chars, minimum {min_length})",
                passed=False
            ))
            return False

        return True

    def validate_boolean(self, var_name: str, expected_value: Optional[bool] = None) -> bool:
        """Validate boolean variable."""
        value = os.getenv(var_name, "").lower()

        if value not in ["true", "false", "1", "0", ""]:
            self.results.append(ValidationResult(
                variable=var_name,
                severity=Severity.WARNING,
                message=f"Expected boolean value (true/false), got: {value}",
                passed=False
            ))
            return False

        if expected_value is not None:
            actual = value in ["true", "1"]
            if actual != expected_value:
                severity = Severity.WARNING if not self.strict else Severity.CRITICAL
                self.results.append(ValidationResult(
                    variable=var_name,
                    severity=severity,
                    message=f"Expected {expected_value}, got {actual}",
                    passed=False
                ))
                return False

        return True

    def validate_integer(self, var_name: str, min_value: Optional[int] = None, max_value: Optional[int] = None) -> bool:
        """Validate integer variable with optional range."""
        value = os.getenv(var_name)

        if not value:
            return True  # Optional integer

        try:
            int_value = int(value)

            if min_value is not None and int_value < min_value:
                self.results.append(ValidationResult(
                    variable=var_name,
                    severity=Severity.WARNING,
                    message=f"Value {int_value} below minimum {min_value}",
                    passed=False
                ))
                return False

            if max_value is not None and int_value > max_value:
                self.results.append(ValidationResult(
                    variable=var_name,
                    severity=Severity.WARNING,
                    message=f"Value {int_value} above maximum {max_value}",
                    passed=False
                ))
                return False

            return True

        except ValueError:
            self.results.append(ValidationResult(
                variable=var_name,
                severity=Severity.CRITICAL,
                message=f"Invalid integer value: {value}",
                passed=False
            ))
            return False

    def validate_email(self, var_name: str) -> bool:
        """Validate email address format."""
        if not self.validate_required(var_name):
            return False

        value = os.getenv(var_name)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not re.match(email_pattern, value):
            self.results.append(ValidationResult(
                variable=var_name,
                severity=Severity.WARNING,
                message=f"Invalid email format: {value}",
                passed=False
            ))
            return False

        return True

    def validate_cors_origins(self) -> bool:
        """Validate CORS origins configuration."""
        frontend_url = os.getenv("FRONTEND_URL")
        quiz_url = os.getenv("QUIZ_URL")

        if not frontend_url or not quiz_url:
            self.results.append(ValidationResult(
                variable="FRONTEND_URL/QUIZ_URL",
                severity=Severity.CRITICAL,
                message="Both FRONTEND_URL and QUIZ_URL must be set",
                passed=False
            ))
            return False

        # Check for wildcards in production
        if self.environment == "production":
            if "*" in frontend_url or "*" in quiz_url:
                self.results.append(ValidationResult(
                    variable="CORS_ORIGINS",
                    severity=Severity.CRITICAL,
                    message="Wildcard CORS origins not allowed in production",
                    passed=False
                ))
                return False

            # Ensure HTTPS in production
            if not frontend_url.startswith("https://") or not quiz_url.startswith("https://"):
                self.results.append(ValidationResult(
                    variable="CORS_ORIGINS",
                    severity=Severity.CRITICAL,
                    message="Production CORS origins must use HTTPS",
                    passed=False
                ))
                return False

        return True

    def run_validation(self) -> bool:
        """Run all validations for the current environment."""
        print(f"🔍 Validating environment variables for: {self.environment}")
        print(f"📋 Strict mode: {self.strict}")
        print()

        # Database
        print("=" * 60)
        print("DATABASE CONFIGURATION")
        print("=" * 60)
        self.validate_database_url()
        self.validate_integer("DB_POOL_SIZE", min_value=5, max_value=100)
        self.validate_integer("DB_MAX_OVERFLOW", min_value=0, max_value=100)

        # Redis
        print()
        print("=" * 60)
        print("REDIS CONFIGURATION")
        print("=" * 60)
        self.validate_redis_url()
        self.validate_boolean("ENABLE_REDIS")
        self.validate_integer("REDIS_MAX_CONNECTIONS", min_value=10, max_value=500)

        # Security
        print()
        print("=" * 60)
        print("SECURITY CONFIGURATION")
        print("=" * 60)
        self.validate_secret("JWT_SECRET", min_length=32)
        self.validate_secret("CSRF_SECRET_KEY", min_length=32)
        self.validate_secret("ENCRYPTION_KEY", min_length=32)

        if self.environment == "production":
            self.validate_boolean("DEBUG", expected_value=False)
            self.validate_boolean("ENABLE_SWAGGER_UI", expected_value=False)

        # CORS
        print()
        print("=" * 60)
        print("CORS CONFIGURATION")
        print("=" * 60)
        self.validate_cors_origins()

        # Integrations
        print()
        print("=" * 60)
        print("INTEGRATIONS")
        print("=" * 60)
        self.validate_url("EVOLUTION_API_URL")
        self.validate_required("EVOLUTION_API_KEY")
        self.validate_secret("EVOLUTION_WEBHOOK_SECRET", min_length=32)

        if os.getenv("ENABLE_REDIS") == "true":
            self.validate_required("GEMINI_API_KEY")

        # Firebase
        self.validate_required("FIREBASE_ADMIN_PROJECT_ID")
        self.validate_email("FIREBASE_ADMIN_CLIENT_EMAIL")

        # Monitoring
        if self.environment == "production":
            print()
            print("=" * 60)
            print("MONITORING & ERROR TRACKING")
            print("=" * 60)
            self.validate_url("SENTRY_DSN", required_scheme="https")

        # Print results
        print()
        print("=" * 60)
        print("VALIDATION RESULTS")
        print("=" * 60)
        print()

        critical_errors = [r for r in self.results if r.severity == Severity.CRITICAL and not r.passed]
        warnings = [r for r in self.results if r.severity == Severity.WARNING and not r.passed]
        passed = [r for r in self.results if r.passed]

        print(f"✅ Passed: {len(passed)}")
        print(f"⚠️  Warnings: {len(warnings)}")
        print(f"❌ Critical Errors: {len(critical_errors)}")
        print()

        if critical_errors:
            print("CRITICAL ERRORS:")
            for result in critical_errors:
                print(f"  ❌ {result.variable}: {result.message}")
            print()

        if warnings:
            print("WARNINGS:")
            for result in warnings:
                print(f"  ⚠️  {result.variable}: {result.message}")
            print()

        # Determine exit code
        if critical_errors:
            print("❌ Validation failed: Critical errors found")
            return False

        if warnings and self.strict:
            print("❌ Validation failed: Warnings found (strict mode)")
            return False

        print("✅ All validations passed!")
        return True


def main():
    """Main execution function."""
    # Parse arguments
    strict = "--strict" in sys.argv
    environment = "development"

    for arg in sys.argv[1:]:
        if arg.startswith("--environment="):
            environment = arg.split("=")[1]

    # Override with ENVIRONMENT variable if set
    environment = os.getenv("ENVIRONMENT", environment)

    # Run validation
    validator = EnvironmentValidator(environment=environment, strict=strict)
    success = validator.run_validation()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
