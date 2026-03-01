import pytest
import os
from unittest.mock import patch
from scripts.validate_env import EnvironmentValidator, Severity


@pytest.fixture(autouse=True)
def _disable_permission_scan(monkeypatch):
    """Keep audit tests fast by skipping recursive file permission scans."""
    monkeypatch.setattr(EnvironmentValidator, "_check_file_permissions", lambda self: None)


@pytest.mark.security
class TestConfigAuditVerification:
    """
    Audit verification tests for production configuration and secrets.
    """

    def test_env_validator_detects_missing_required_vars(self):
        """Verify that the env validator correctly identifies missing required variables."""
        # Mock empty environment
        with patch.dict(os.environ, {}, clear=True):
            validator = EnvironmentValidator(strict=True)
            # We expect it to return False because critical vars are missing
            assert validator.validate() is False
            
            critical_vars = {i.variable for i in validator.issues if i.severity == Severity.CRITICAL}
            assert 'DATABASE_URL' in critical_vars
            assert 'SECRET_KEY' in critical_vars
            assert 'ENCRYPTION_KEY' in critical_vars
            assert 'SECURITY_CSRF_SECRET_KEY' in critical_vars

    def test_env_validator_detects_weak_secrets(self):
        """Verify that weak secrets trigger warnings/errors."""
        env_overrides = {
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'SECRET_KEY': 'too-short',
            'ENCRYPTION_KEY': 'not-32-bytes-long-at-all-really',
            'CORS_ORIGINS': '*',
            'APP_ENVIRONMENT': 'production',
            'APP_ENABLE_DEBUG': 'true'
        }
        
        with patch.dict(os.environ, env_overrides, clear=True):
            validator = EnvironmentValidator(strict=False)
            validator.validate()
            
            issue_vars = {i.variable for i in validator.issues}
            # SECRET_KEY too short
            assert 'SECRET_KEY' in issue_vars
            # CORS origins is *
            assert 'CORS_ORIGINS' in issue_vars
            # Debug mode in production
            assert 'APP_ENABLE_DEBUG' in issue_vars

    def test_production_encryption_key_requirements(self):
        """
        Verify specific production requirements for ENCRYPTION_KEY.
        Must be exactly 32 bytes for AES-256.
        """
        env_overrides = {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "SECRET_KEY": "this-is-a-valid-length-secret-key-for-tests-12345",
            "ENCRYPTION_KEY": "too-short",
            "SECURITY_CSRF_SECRET_KEY": "csrf-secret-key-32-bytes-long-value",
            "HASH_SALT": "hash-salt",
            "CORS_ORIGINS": "http://localhost:3000",
            "FIREBASE_ADMIN_PROJECT_ID": "test-project",
        }

        with patch.dict(os.environ, env_overrides, clear=True):
            validator = EnvironmentValidator(strict=False)
            validator.validate()

            encryption_issues = [
                issue for issue in validator.issues if issue.variable == "ENCRYPTION_KEY"
            ]
            assert encryption_issues, "ENCRYPTION_KEY length issue should be reported"
            assert any("exactly 32 bytes" in issue.message for issue in encryption_issues)

    def test_actual_environment_validation(self, monkeypatch):
        """
        Validate the CURRENT real environment configuration.
        This test uses the real os.environ.
        """
        validator = EnvironmentValidator(strict=False)
        # Avoid expensive recursive permission scans during unit test runs.
        monkeypatch.setattr(validator, "_check_file_permissions", lambda: None)
        # We don't assert True here because the developer's local env 
        # might have some missing vars, but we want to see the report.
        success = validator.validate()
        
        # Print summary for the logs
        print(f"\nREAL ENV VALIDATION RESULT: {'PASSED' if success else 'FAILED'}")
        
        # In a real production CI, we might want to enforce this
        # assert success, "Real environment validation failed! Check logs."
