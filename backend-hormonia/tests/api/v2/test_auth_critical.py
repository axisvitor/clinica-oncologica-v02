import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

# Mock dependencies
@pytest.fixture
def mock_redis_cache():
    cache = AsyncMock()
    cache.create_session.return_value = True
    return cache

@pytest.fixture
def mock_firebase_verify():
    with patch("app.dependencies.auth_dependencies.verify_firebase_token", new_callable=AsyncMock) as mock:
        yield mock

@pytest.fixture
def client_with_mocks(mock_redis_cache):
    from app.dependencies.auth_dependencies import get_redis_cache
    app.dependency_overrides[get_redis_cache] = lambda: mock_redis_cache
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_webhook_unauthenticated_access(client_with_mocks):
    """Test that webhook endpoints are protected."""
    response = client_with_mocks.get("/api/v2/webhooks")
    # Should be 401 Unauthorized or 403 Forbidden depending on how auth is handled (no credentials provided)
    assert response.status_code in [401, 403]

def test_webhook_admin_access(client_with_mocks, admin_auth_headers):
    """Test that admin can access webhook endpoints."""
    # We need to mock the service call too since we don't want to hit the DB/Service logic
    with patch("app.services.webhook_service.WebhookService.list_webhooks", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = {"items": [], "total": 0, "page": 1, "size": 10, "pages": 0}
        
        response = client_with_mocks.get("/api/v2/webhooks", headers=admin_auth_headers)
        assert response.status_code == 200

def test_firebase_login_flow(client_with_mocks, mock_redis_cache, mock_firebase_verify, db_session):
    """
    Test Firebase login flow:
    1. Verifies response shape.
    2. Verifies Redis session creation.
    """
    # Setup mock Firebase user
    firebase_uid = "test_firebase_uid_123"
    email = "test_firebase@example.com"
    mock_firebase_verify.return_value = {
        "uid": firebase_uid,
        "email": email,
        "name": "Firebase User",
        "email_verified": True,
        "custom_claims": {"role": "doctor"}
    }

    # Ensure user doesn't exist (or cleanup)
    # (In a real test DB, transaction rollback handles this, but let's be safe)
    
    payload = {"id_token": "valid_firebase_token"}
    
    response = client_with_mocks.post("/api/v2/auth/firebase/verify", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify Response Shape
    assert "valid" in data
    assert data["valid"] is True
    assert "session_id" in data
    assert "message" in data
    
    # Verify Redis Session Creation
    mock_redis_cache.create_session.assert_called_once()
    call_args = mock_redis_cache.create_session.call_args[1]
    assert call_args["firebase_uid"] == firebase_uid
    assert call_args["user_id"] is not None
    assert call_args["ttl_seconds"] == 432000

