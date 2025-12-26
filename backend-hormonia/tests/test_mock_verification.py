"""
Quick test to verify monkeypatch works for get_onboarding_coordinator.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ["APP_ENVIRONMENT"] = "testing"
os.environ["ENVIRONMENT"] = "testing"

def test_monkeypatch_works(monkeypatch):
    """Test that monkeypatch can intercept the factory function."""
    from unittest.mock import MagicMock

    # Import the module
    import app.services.patient.onboarding_factory as factory_module

    # Create mock
    mock_coordinator = MagicMock()
    mock_coordinator.name = "MOCK_COORDINATOR"

    def mock_factory(db, saga_orchestrator=None):
        print("✅ Mock factory called!")
        return mock_coordinator

    # Patch it
    monkeypatch.setattr(factory_module, "get_onboarding_coordinator", mock_factory)

    # Now try importing and calling from the crud module
    from app.services.patient.onboarding_factory import get_onboarding_coordinator

    result = get_onboarding_coordinator(None, None)
    print(f"Result: {result.name}")
    assert result.name == "MOCK_COORDINATOR"
    print("✅ Test passed! Monkeypatch works!")

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
