"""
Tests for the authentication API endpoints in /api/v1/auth.py
"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.dependencies.auth_dependencies import get_current_user

client = TestClient(app)

def test_patch_user_preferences_ignores_invalid_fields():
    """
    Verify that the PATCH /users/preferences endpoint
    successfully ignores invalid fields in the payload and
    only updates the valid ones.
    """
    # 1. Setup a mock user with initial preferences
    initial_prefs = {"theme": "light", "language": "pt-BR"}
    test_user = User(
        id="test-user-id-456",
        email="test-patch-prefs@example.com",
        metadata={"preferences": initial_prefs},
    )

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    # 2. Define the payload with valid and invalid fields
    payload = {
        "theme": "dark",             # Valid field to update
        "invalid_field": "foo",      # Invalid field to be ignored
        "another_bad_one": 123       # Invalid field to be ignored
    }

    # 3. Call the endpoint
    response = client.patch("/api/v1/users/preferences", json=payload)

    # 4. Assert that the request was successful
    assert response.status_code == 200

    # 5. Assert that the response contains the correctly updated preferences
    response_data = response.json()
    updated_prefs = response_data["preferences"]
    assert updated_prefs["theme"] == "dark"
    assert updated_prefs["language"] == "pt-BR"  # Should be unchanged
    assert "invalid_field" not in updated_prefs
    assert "another_bad_one" not in updated_prefs

    # Clean up dependency override
    app.dependency_overrides = {}
