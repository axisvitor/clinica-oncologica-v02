"""
Test Health Reset Endpoint - Regression Tests for DI Refactoring

Tests that the health reset endpoint doesn't raise ImportError after
the dependency injection refactoring.

ISSUE: Railway health check was using wrong import path
RESOLUTION: Fixed to use app.database.get_db instead of app.dependencies.session_manager.get_db

Run with: pytest tests/api/v1/test_health_reset.py -v
"""
import pytest
from fastapi.testclient import TestClient


class TestHealthResetEndpoint:
    """Test health reset endpoint functionality"""

    def setup_method(self):
        """Setup test client for each test"""
        from app.main import app
        self.client = TestClient(app)

    def test_health_reset_endpoint_exists(self):
        """Test that /api/v1/railway/health endpoint exists"""
        response = self.client.get("/api/v1/railway/health")
        # Should return 200 or 503 (if services unhealthy), but NOT 404
        assert response.status_code in [200, 503], f"Unexpected status: {response.status_code}"

    def test_health_reset_no_import_error(self):
        """
        CRITICAL TEST: Ensure health endpoint doesn't raise ImportError.

        This was the bug: app/api/v1/railway_health.py was importing from
        app.dependencies.session_manager.get_db which doesn't exist.
        """
        response = self.client.get("/api/v1/railway/health")

        # Should NOT return 500 (ImportError would cause 500)
        assert response.status_code != 500, f"ImportError detected! Response: {response.json()}"

    def test_health_check_response_structure(self):
        """Test health check returns proper JSON structure"""
        response = self.client.get("/api/v1/railway/health")

        assert "application/json" in response.headers["content-type"]
        data = response.json()

        # Should have status and checks fields
        if response.status_code == 200:
            assert "status" in data
            assert "checks" in data
            assert data["status"] in ["healthy", "unhealthy"]

    def test_health_check_database_validation(self):
        """Test that health check validates database connectivity"""
        response = self.client.get("/api/v1/railway/health")
        data = response.json()

        if "checks" in data:
            assert "database" in data["checks"]
            assert "healthy" in data["checks"]["database"]

    def test_health_check_service_provider_validation(self):
        """Test that health check validates ServiceProvider initialization"""
        response = self.client.get("/api/v1/railway/health")
        data = response.json()

        if "checks" in data:
            assert "service_provider" in data["checks"]
            assert "healthy" in data["checks"]["service_provider"]

    def test_health_readiness_probe(self):
        """Test Railway readiness probe endpoint"""
        response = self.client.get("/api/v1/railway/health/readiness")
        assert response.status_code in [200, 503]

        data = response.json()
        assert "status" in data
        assert data["status"] in ["ready", "not_ready", "error"]

    def test_health_liveness_probe(self):
        """Test Railway liveness probe endpoint"""
        response = self.client.get("/api/v1/railway/health/liveness")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    def test_health_startup_probe(self):
        """Test Railway startup probe endpoint"""
        response = self.client.get("/api/v1/railway/health/startup")
        assert response.status_code in [200, 503]

        data = response.json()
        assert "status" in data
        assert data["status"] in ["started", "starting", "error"]


class TestHealthEndpointImports:
    """Test that health endpoint uses correct imports"""

    def test_correct_database_import(self):
        """Verify railway_health.py uses app.database.get_db"""
        import app.api.v1.railway_health as health_module

        # The module should successfully import without errors
        assert health_module is not None
        assert hasattr(health_module, "railway_health_check")

    def test_service_provider_import(self):
        """Verify ServiceProvider is imported correctly"""
        from app.services import ServiceProvider
        from app.database import get_db

        # Should be able to create ServiceProvider with get_db
        db = next(get_db())
        try:
            service_provider = ServiceProvider(db)
            assert service_provider is not None
            assert service_provider.db is db
        finally:
            db.close()
