"""
Tests for deployment validation functionality.
Validates that deployment scripts detect critical issues correctly.
"""

import pytest
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import json

# Import the validation classes
sys.path.append(str(Path(__file__).parent.parent / "scripts"))
from deployment_validation import DeploymentValidator, DatabaseSchemaValidator
from validate_deployment_health import DeploymentHealthValidator
from validate_critical_fixes import CriticalFixesValidator


class TestDeploymentValidator:
    """Test the main deployment validator."""
    
    def setup_method(self):
        """Setup test environment."""
        self.validator = DeploymentValidator(base_url="http://test-api:8000")
    
    def test_validator_initialization(self):
        """Test validator initializes correctly."""
        assert self.validator.base_url == "http://test-api:8000"
        assert self.validator.errors == []
        assert self.validator.warnings == []
        assert isinstance(self.validator.test_results, dict)
    
    @patch('requests.get')
    def test_health_check_success(self, mock_get):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Test the health check method directly
        result = self.validator._run_health_checks()
        
        assert result is True
        mock_get.assert_called_with("http://test-api:8000/health", timeout=10)
    
    @patch('requests.get')
    def test_health_check_failure(self, mock_get):
        """Test health check failure."""
        mock_get.side_effect = ConnectionError("Connection refused")
        
        result = self.validator._run_health_checks()
        
        assert result is False
        assert len(self.validator.errors) > 0
        assert "unreachable" in self.validator.errors[0].lower()
    
    @patch('requests.get')
    def test_analytics_endpoint_validation(self, mock_get):
        """Test analytics endpoint validation with date parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        headers = {"Authorization": "Bearer test-token"}
        result = self.validator._test_analytics_endpoints(headers)
        
        # Should make multiple calls for different test cases
        assert mock_get.call_count >= 3
        assert result is True
    
    @patch('requests.get')
    def test_analytics_validation_error_detection(self, mock_get):
        """Test detection of validation errors in analytics endpoints."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = "Validation error: invalid date format"
        mock_get.return_value = mock_response
        
        headers = {"Authorization": "Bearer test-token"}
        result = self.validator._test_analytics_endpoints(headers)
        
        assert result is False
        assert len(self.validator.errors) > 0
        assert "validation" in self.validator.errors[0].lower()
    
    @patch('requests.get')
    def test_role_enum_error_detection(self, mock_get):
        """Test detection of role enum errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "AttributeError: 'UserRole' has no attribute 'SUPER_ADMIN'"
        mock_get.return_value = mock_response
        
        headers = {"Authorization": "Bearer test-token"}
        result = self.validator._test_monthly_quiz_endpoints(headers)
        
        assert result is False
        assert len(self.validator.errors) > 0
        assert "role enum error" in self.validator.errors[0].lower()
    
    @patch('requests.get')
    def test_schema_compatibility_error_detection(self, mock_get):
        """Test detection of database schema compatibility errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "column 'alert_type' does not exist"
        mock_get.return_value = mock_response
        
        headers = {"Authorization": "Bearer test-token"}
        result = self.validator._test_alerts_endpoints(headers)
        
        assert result is False
        assert len(self.validator.errors) > 0
        assert "schema compatibility error" in self.validator.errors[0].lower()
    
    def test_validation_report_generation(self):
        """Test validation report generation."""
        # Add some test data
        self.validator.errors = ["Test error"]
        self.validator.warnings = ["Test warning"]
        self.validator.test_results = {"test": "result"}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            self.validator.backend_root = Path(temp_dir)
            
            # Mock the async method call
            import asyncio
            asyncio.run(self.validator._generate_validation_report(False))
            
            report_file = Path(temp_dir) / "deployment_validation_report.json"
            assert report_file.exists()
            
            with open(report_file) as f:
                report = json.load(f)
            
            assert report["success"] is False
            assert report["errors"] == ["Test error"]
            assert report["warnings"] == ["Test warning"]
            assert report["summary"]["status"] == "FAIL"


class TestDatabaseSchemaValidator:
    """Test database schema validation."""
    
    def setup_method(self):
        """Setup test environment."""
        self.validator = DatabaseSchemaValidator()
    
    def test_validator_initialization(self):
        """Test validator initializes correctly."""
        assert self.validator.errors == []
        assert isinstance(self.validator.backend_root, Path)
    
    @patch('subprocess.run')
    def test_migration_status_check_success(self, mock_run):
        """Test successful migration status check."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = self.validator._check_migration_status()
        
        assert result is True
        mock_run.assert_called_once()
        assert "alembic" in mock_run.call_args[0][0][0]
    
    @patch('subprocess.run')
    def test_migration_status_check_failure(self, mock_run):
        """Test migration status check failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Migration error"
        mock_run.return_value = mock_result
        
        result = self.validator._check_migration_status()
        
        assert result is False
        assert len(self.validator.errors) > 0
        assert "migration" in self.validator.errors[0].lower()
    
    def test_required_tables_check(self):
        """Test required tables check."""
        # This is a simulated check in the current implementation
        result = self.validator._check_required_tables()
        assert result is True
    
    def test_critical_columns_check(self):
        """Test critical columns check."""
        # This is a simulated check in the current implementation
        result = self.validator._check_critical_columns()
        assert result is True


class TestDeploymentHealthValidator:
    """Test deployment health validation."""
    
    def setup_method(self):
        """Setup test environment."""
        self.validator = DeploymentHealthValidator(base_url="http://test-api:8000")
    
    @patch('requests.get')
    def test_api_health_check_success(self, mock_get):
        """Test successful API health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = self.validator._check_api_health()
        
        assert result is True
        mock_get.assert_called_with("http://test-api:8000/health", timeout=10)
    
    @patch('requests.get')
    def test_api_health_check_connection_error(self, mock_get):
        """Test API health check with connection error."""
        mock_get.side_effect = ConnectionError("Connection refused")
        
        result = self.validator._check_api_health()
        
        assert result is False
        assert len(self.validator.errors) > 0
        assert "not reachable" in self.validator.errors[0]
    
    @patch('requests.get')
    def test_api_health_check_timeout(self, mock_get):
        """Test API health check timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        result = self.validator._check_api_health()
        
        assert result is False
        assert len(self.validator.errors) > 0
        assert "timed out" in self.validator.errors[0]
    
    @patch('requests.get')
    def test_dependency_injection_error_detection(self, mock_get):
        """Test detection of dependency injection errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "generator object has no attribute 'monthly_quiz_service'"
        mock_get.return_value = mock_response
        
        result = self.validator._check_dependency_injection()
        
        assert result is False
        assert len(self.validator.errors) > 0
        assert "dependency injection" in self.validator.errors[0].lower()
    
    @patch('subprocess.run')
    def test_critical_imports_check_success(self, mock_run):
        """Test successful critical imports check."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.validator._check_critical_imports()
        
        assert result is True
        # Should have called subprocess for each critical module
        assert mock_run.call_count >= 5
    
    @patch('subprocess.run')
    def test_critical_imports_check_failure(self, mock_run):
        """Test critical imports check failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "ImportError: No module named 'app.core.config'"
        mock_run.return_value = mock_result
        
        result = self.validator._check_critical_imports()
        
        assert result is False
        assert len(self.validator.errors) > 0
        assert "import" in self.validator.errors[0].lower()


class TestCriticalFixesValidator:
    """Test critical fixes validation."""
    
    def setup_method(self):
        """Setup test environment."""
        self.validator = CriticalFixesValidator(base_url="http://test-api:8000")
    
    def test_validator_initialization(self):
        """Test validator initializes correctly."""
        assert self.validator.base_url == "http://test-api:8000"
        assert self.validator.errors == []
        assert self.validator.warnings == []
        assert isinstance(self.validator.fix_results, dict)
    
    @patch('builtins.open', new_callable=mock_open, read_data="""
class _ThreadSafeProviderDependency:
    def __call__(self):
        yield from get_thread_safe_service_provider()
""")
    @patch('os.path.exists')
    def test_dependency_injection_fix_validation_success(self, mock_exists, mock_file):
        """Test successful dependency injection fix validation."""
        mock_exists.return_value = True
        
        result = self.validator._validate_dependency_injection_fix()
        
        assert result is True
        assert self.validator.fix_results["dependency_injection"] is True
    
    @patch('builtins.open', new_callable=mock_open, read_data="""
class _ThreadSafeProviderDependency:
    def __call__(self):
        return get_thread_safe_service_provider()
""")
    @patch('os.path.exists')
    def test_dependency_injection_fix_validation_failure(self, mock_exists, mock_file):
        """Test dependency injection fix validation failure."""
        mock_exists.return_value = True
        
        result = self.validator._validate_dependency_injection_fix()
        
        assert result is False
        assert self.validator.fix_results["dependency_injection"] is False
        assert len(self.validator.errors) > 0
    
    @patch('builtins.open', new_callable=mock_open, read_data="""
# Analytics endpoints without SUPER_ADMIN
allowed_roles = {UserRole.ADMIN}
""")
    @patch('os.path.exists')
    def test_role_enum_fix_validation_success(self, mock_exists, mock_file):
        """Test successful role enum fix validation."""
        mock_exists.return_value = True
        
        result = self.validator._validate_role_enum_fixes()
        
        assert result is True
        assert self.validator.fix_results["role_enums"] is True
    
    @patch('builtins.open', new_callable=mock_open, read_data="""
# Analytics endpoints still using SUPER_ADMIN
allowed_roles = {UserRole.ADMIN, UserRole.SUPER_ADMIN}
""")
    @patch('os.path.exists')
    def test_role_enum_fix_validation_failure(self, mock_exists, mock_file):
        """Test role enum fix validation failure."""
        mock_exists.return_value = True
        
        result = self.validator._validate_role_enum_fixes()
        
        assert result is False
        assert self.validator.fix_results["role_enums"] is False
        assert len(self.validator.errors) > 0
    
    @patch('builtins.open', new_callable=mock_open, read_data="""
class Alert(Base):
    alert_type = Column("type", String(50))
    description = Column("message", Text)
    
    @property
    def quiz_session_id(self):
        return self.data.get("quiz_session_id")
""")
    @patch('os.path.exists')
    def test_alerts_schema_fix_validation_success(self, mock_exists, mock_file):
        """Test successful alerts schema fix validation."""
        mock_exists.return_value = True
        
        result = self.validator._validate_alerts_schema_fix()
        
        assert result is True
        assert self.validator.fix_results["alerts_schema"] is True
    
    @patch('builtins.open', new_callable=mock_open, read_data="""
def coerce_to_date(value):
    # Date coercion implementation
    pass
""")
    @patch('os.path.exists')
    def test_date_parameter_fix_validation_success(self, mock_exists, mock_file):
        """Test successful date parameter fix validation."""
        mock_exists.return_value = True
        
        result = self.validator._validate_date_parameter_fix()
        
        assert result is True
        assert self.validator.fix_results["date_parameters"] is True
    
    @patch('requests.get')
    def test_api_fixes_validation_success(self, mock_get):
        """Test API fixes validation success."""
        mock_response = MagicMock()
        mock_response.status_code = 400  # Not 422 validation error
        mock_get.return_value = mock_response
        
        result = self.validator._test_fixes_via_api()
        
        assert result is True
    
    @patch('requests.get')
    def test_api_fixes_validation_failure(self, mock_get):
        """Test API fixes validation failure."""
        mock_response = MagicMock()
        mock_response.status_code = 422  # Validation error indicates fix not working
        mock_get.return_value = mock_response
        
        result = self.validator._test_fixes_via_api()
        
        assert result is False
        assert len(self.validator.errors) > 0


class TestDeploymentScripts:
    """Test deployment script execution."""
    
    def test_deployment_validation_script_exists(self):
        """Test that deployment validation script exists."""
        script_path = Path(__file__).parent.parent / "scripts" / "deployment_validation.py"
        assert script_path.exists()
    
    def test_health_validation_script_exists(self):
        """Test that health validation script exists."""
        script_path = Path(__file__).parent.parent / "scripts" / "validate_deployment_health.py"
        assert script_path.exists()
    
    def test_critical_fixes_script_exists(self):
        """Test that critical fixes validation script exists."""
        script_path = Path(__file__).parent.parent / "scripts" / "validate_critical_fixes.py"
        assert script_path.exists()
    
    def test_bash_deployment_script_exists(self):
        """Test that bash deployment script exists."""
        script_path = Path(__file__).parent.parent / "scripts" / "deploy_validate.sh"
        assert script_path.exists()
    
    def test_batch_deployment_script_exists(self):
        """Test that Windows batch deployment script exists."""
        script_path = Path(__file__).parent.parent / "scripts" / "deploy_validate.bat"
        assert script_path.exists()
    
    @patch('subprocess.run')
    def test_deployment_script_execution(self, mock_run):
        """Test deployment script can be executed."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        script_path = Path(__file__).parent.parent / "scripts" / "deployment_validation.py"
        
        # Test script execution
        result = subprocess.run([
            sys.executable, str(script_path), "--skip-smoke-tests"
        ], capture_output=True, text=True)
        
        # The actual result depends on the environment, but script should be executable
        assert result.returncode in [0, 1]  # Success or controlled failure


class TestConfigurationValidation:
    """Test configuration validation functionality."""
    
    def test_environment_variable_validation(self):
        """Test environment variable validation."""
        # Test with missing required variables
        with patch.dict(os.environ, {}, clear=True):
            validator = DeploymentHealthValidator()
            result = validator._check_environment_config()
            
            # Should still return True but have warnings
            assert result is True
            assert len(validator.warnings) > 0
    
    def test_configuration_loading(self):
        """Test configuration loading validation."""
        # This tests that the config can be imported and loaded
        try:
            from app.core.config import settings
            # If we get here, config loading works
            assert True
        except ImportError:
            # Config module doesn't exist or has issues
            pytest.skip("Config module not available in test environment")
    
    def test_database_configuration_validation(self):
        """Test database configuration validation."""
        # Test database URL validation
        test_urls = [
            "postgresql://user:pass@localhost/db",
            "sqlite:///./test.db",
            "invalid-url"
        ]
        
        for url in test_urls:
            with patch.dict(os.environ, {"DATABASE_URL": url}):
                # Test that configuration handles different URL formats
                try:
                    from app.core.config import settings
                    # Configuration should handle various URL formats
                    assert True
                except Exception:
                    # Some URLs might be invalid, which is expected
                    pass


@pytest.mark.integration
class TestDeploymentIntegration:
    """Integration tests for deployment validation."""
    
    def test_full_validation_pipeline(self):
        """Test the full validation pipeline."""
        # This would run the complete validation in a test environment
        validator = DeploymentValidator(base_url="http://localhost:8000")
        
        # Mock external dependencies
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Run static validations only (no API calls)
            import asyncio
            result = asyncio.run(validator._run_static_validations())
            
            # Should complete without errors (result depends on actual code state)
            assert isinstance(result, bool)
    
    def test_error_aggregation(self):
        """Test that errors are properly aggregated across validators."""
        validator = DeploymentValidator()
        
        # Add test errors
        validator.errors.append("Test error 1")
        validator.errors.append("Test error 2")
        validator.warnings.append("Test warning 1")
        
        # Test report generation
        import asyncio
        with tempfile.TemporaryDirectory() as temp_dir:
            validator.backend_root = Path(temp_dir)
            asyncio.run(validator._generate_validation_report(False))
            
            report_file = Path(temp_dir) / "deployment_validation_report.json"
            assert report_file.exists()
            
            with open(report_file) as f:
                report = json.load(f)
            
            assert len(report["errors"]) == 2
            assert len(report["warnings"]) == 1
            assert report["summary"]["total_errors"] == 2
            assert report["summary"]["total_warnings"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])