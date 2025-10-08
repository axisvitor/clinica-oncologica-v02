
import pytest
from unittest.mock import MagicMock, patch
from fastapi import Response
from app.routers.quiz_auth import quiz_login, LoginRequest
from app.models.user import User

@pytest.mark.asyncio
async def test_quiz_login_case_insensitive_email():
    """
    Tests that a user can log in with a case-insensitive email address.
    """
    # 1. Create a mock user with a mixed-case email
    mock_user = User(
        id=1,
        email="Test.User@example.com",
        hashed_password="hashed_password",
        is_active=True,
        name="Test User",
        role="test"
    )

    # 2. Mock the request object with a lowercase email
    login_request = LoginRequest(
        email="test.user@example.com",
        password="password",
        remember_me=False
    )

    # 3. Mock the services and database query
    mock_services = MagicMock()
    mock_query = MagicMock()
    mock_query.first.return_value = mock_user
    mock_services.db.query.return_value.filter.return_value = mock_query
    mock_services.session_service.create_session.return_value = "test_session_id"

    # 4. Mock the password verification
    with patch("app.routers.quiz_auth.verify_password", return_value=True):
        # 5. Call the login function
        response = Response()
        login_response = await quiz_login(
            request=login_request,
            response=response,
            services=mock_services
        )

        # 6. Assert that the login was successful
        assert login_response.success is True
        assert login_response.message == "Login successful"
        assert login_response.user["email"] == "Test.User@example.com"

        # 7. Verify that the query was called with ilike
        mock_services.db.query.return_value.filter.assert_called_once()
        # Check that ilike was used in the filter call
        filter_call_args = mock_services.db.query.return_value.filter.call_args[0]
        assert "ilike" in str(filter_call_args[0]).lower()
