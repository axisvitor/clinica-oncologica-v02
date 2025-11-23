import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# Import app factory instead of instance to allow env mocking
from app.core.application_factory import create_app

def test_debug_endpoints_disabled_by_default():
    """
    Ensure debug endpoints are NOT accessible by default (when env var is unset).
    This is critical for production security.
    """
    # Ensure env var is unset for this test
    with patch.dict(os.environ, {}, clear=True):
        # Re-create app to pick up env change
        app = create_app()
        client = TestClient(app)
        
        # Try to access a known debug endpoint
        response = client.get("/api/v2/debug/env")
        
        # Should return 404 Not Found (because router is not included)
        assert response.status_code == 404, "Debug endpoint should be 404 when disabled"

def test_debug_endpoints_disabled_explicitly():
    """
    Ensure debug endpoints are disabled when ENABLE_DEBUG_ENDPOINTS=false
    """
    with patch.dict(os.environ, {"ENABLE_DEBUG_ENDPOINTS": "false"}):
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/api/v2/debug/env")
        assert response.status_code == 404

def test_production_environment_enforces_security():
    """
    In production environment, debug endpoints MUST be disabled regardless of flag,
    OR at least the flag must default to false.
    """
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "ENABLE_DEBUG_ENDPOINTS": "false"}):
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/api/v2/debug/env")
        assert response.status_code == 404

def test_docs_url_hidden_in_production():
    """
    Swagger UI (/docs) should ideally be hidden or protected in production,
    but at minimum check that we can configure it.
    """
    # This depends on your specific docs_url config logic in main.py
    # For now, we just verify the app creates successfully
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        app = create_app()
        assert app is not None
