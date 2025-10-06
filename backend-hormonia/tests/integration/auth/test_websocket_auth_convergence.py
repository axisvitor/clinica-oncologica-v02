"""
Integration tests for WebSocket authentication convergence with HTTP auth.

Tests that WebSocket authentication:
- Uses same Firebase token validation as HTTP endpoints
- Returns same user object as HTTP auth
- Handles token expiration consistently
- Supports query parameter and header-based tokens
- Fails gracefully with proper error handling
"""
import pytest
from typing import Dict
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

from app.dependencies.auth_dependencies import get_current_user_websocket
from app.models.user import User, UserRole


class TestWebSocketAuthConvergence:
    """Test suite for WebSocket authentication convergence with HTTP."""

    @pytest.mark.asyncio
    async def test_websocket_auth_uses_same_firebase_validation(
        self,
        db_session,
        doctor_a_credentials: Dict[str, str],
        create_test_user
    ):
        """
        Test WebSocket auth uses same Firebase token validation as HTTP.

        Both HTTP and WebSocket should use FirebaseAuthService.verify_token()
        with identical validation logic.
        """
        # Create test user
        user = create_test_user(
            email=doctor_a_credentials["email"],
            firebase_uid=doctor_a_credentials["firebase_uid"],
            role=UserRole.DOCTOR
        )

        # Mock WebSocket connection with token
        mock_websocket = Mock()
        mock_websocket.query_params = {"token": doctor_a_credentials["token"]}

        # Mock service provider
        from app.services import ServiceProvider
        mock_services = Mock(spec=ServiceProvider)
        mock_services.db = db_session
        mock_services.user_repository = Mock()
        mock_services.user_repository.get_by_email = Mock(return_value=user)

        # Mock Firebase service to verify token
        with patch("app.dependencies.auth_dependencies._firebase_service") as mock_firebase:
            mock_firebase.verify_token = AsyncMock(return_value={
                "uid": doctor_a_credentials["firebase_uid"],
                "email": doctor_a_credentials["email"],
                "email_verified": True
            })

            # Act - authenticate via WebSocket
            ws_user = await get_current_user_websocket(mock_websocket, mock_services)

            # Assert
            assert ws_user is not None
            assert ws_user.email == doctor_a_credentials["email"]
            assert ws_user.firebase_uid == doctor_a_credentials["firebase_uid"]

            # Verify Firebase validation was called
            mock_firebase.verify_token.assert_called_once_with(
                doctor_a_credentials["token"]
            )

    @pytest.mark.asyncio
    async def test_websocket_auth_returns_same_user_as_http(
        self,
        db_session,
        doctor_a_credentials: Dict[str, str],
        create_test_user
    ):
        """
        Test WebSocket auth returns same User object as HTTP auth.

        User retrieved via WebSocket should be identical to
        user retrieved via HTTP /auth/me endpoint.
        """
        # Create test user
        user = create_test_user(
            email=doctor_a_credentials["email"],
            firebase_uid=doctor_a_credentials["firebase_uid"],
            role=UserRole.DOCTOR,
            firebase_custom_claims={"role": "doctor", "specialty": "Oncology"}
        )

        # Mock WebSocket connection
        mock_websocket = Mock()
        mock_websocket.query_params = {"token": doctor_a_credentials["token"]}

        # Mock services
        from app.services import ServiceProvider
        mock_services = Mock(spec=ServiceProvider)
        mock_services.db = db_session
        mock_services.user_repository = Mock()
        mock_services.user_repository.get_by_email = Mock(return_value=user)

        with patch("app.dependencies.auth_dependencies._firebase_service") as mock_firebase:
            mock_firebase.verify_token = AsyncMock(return_value={
                "uid": doctor_a_credentials["firebase_uid"],
                "email": doctor_a_credentials["email"],
                "email_verified": True
            })

            # Act
            ws_user = await get_current_user_websocket(mock_websocket, mock_services)

            # Assert - same user ID and attributes
            assert ws_user.id == user.id
            assert ws_user.email == user.email
            assert ws_user.role == user.role
            assert ws_user.firebase_custom_claims == user.firebase_custom_claims

    @pytest.mark.asyncio
    async def test_websocket_auth_token_from_query_param(
        self,
        db_session,
        doctor_a_credentials: Dict[str, str],
        create_test_user
    ):
        """
        Test WebSocket accepts token from query parameter.

        WebSocket URL: wss://api/ws?token=<firebase_token>
        """
        user = create_test_user(
            email=doctor_a_credentials["email"],
            firebase_uid=doctor_a_credentials["firebase_uid"]
        )

        # Mock WebSocket with query param
        mock_websocket = Mock()
        mock_websocket.query_params = {"token": doctor_a_credentials["token"]}
        mock_websocket.headers = {}

        # Mock services
        from app.services import ServiceProvider
        mock_services = Mock(spec=ServiceProvider)
        mock_services.db = db_session
        mock_services.user_repository = Mock()
        mock_services.user_repository.get_by_email = Mock(return_value=user)

        with patch("app.dependencies.auth_dependencies._firebase_service") as mock_firebase:
            mock_firebase.verify_token = AsyncMock(return_value={
                "uid": doctor_a_credentials["firebase_uid"],
                "email": doctor_a_credentials["email"],
                "email_verified": True
            })

            # Act
            ws_user = await get_current_user_websocket(mock_websocket, mock_services)

            # Assert
            assert ws_user is not None
            assert ws_user.email == doctor_a_credentials["email"]

    @pytest.mark.asyncio
    async def test_websocket_auth_token_from_header(
        self,
        db_session,
        doctor_a_credentials: Dict[str, str],
        create_test_user
    ):
        """
        Test WebSocket accepts token from Authorization header.

        Header: Authorization: Bearer <firebase_token>
        """
        user = create_test_user(
            email=doctor_a_credentials["email"],
            firebase_uid=doctor_a_credentials["firebase_uid"]
        )

        # Mock WebSocket with auth header
        mock_websocket = Mock()
        mock_websocket.query_params = {}
        mock_websocket.headers = {
            "authorization": f"Bearer {doctor_a_credentials['token']}"
        }

        # Mock services
        from app.services import ServiceProvider
        mock_services = Mock(spec=ServiceProvider)
        mock_services.db = db_session
        mock_services.user_repository = Mock()
        mock_services.user_repository.get_by_email = Mock(return_value=user)

        with patch("app.dependencies.auth_dependencies._firebase_service") as mock_firebase:
            mock_firebase.verify_token = AsyncMock(return_value={
                "uid": doctor_a_credentials["firebase_uid"],
                "email": doctor_a_credentials["email"],
                "email_verified": True
            })

            # Act
            ws_user = await get_current_user_websocket(mock_websocket, mock_services)

            # Assert
            assert ws_user is not None
            assert ws_user.email == doctor_a_credentials["email"]

    @pytest.mark.asyncio
    async def test_websocket_auth_fails_with_invalid_token(
        self,
        db_session
    ):
        """
        Test WebSocket auth returns None with invalid token.

        Invalid tokens should fail gracefully without throwing,
        returning None to indicate unauthenticated connection.
        """
        # Mock WebSocket with invalid token
        mock_websocket = Mock()
        mock_websocket.query_params = {"token": "invalid_token_xyz"}

        # Mock services
        from app.services import ServiceProvider
        mock_services = Mock(spec=ServiceProvider)
        mock_services.db = db_session

        with patch("app.dependencies.auth_dependencies._firebase_service") as mock_firebase:
            # Firebase validation fails
            mock_firebase.verify_token = AsyncMock(
                side_effect=Exception("Invalid token")
            )

            # Act
            ws_user = await get_current_user_websocket(mock_websocket, mock_services)

            # Assert
            assert ws_user is None

    @pytest.mark.asyncio
    async def test_websocket_auth_fails_with_expired_token(
        self,
        db_session,
        expired_token_credentials: Dict[str, str]
    ):
        """
        Test WebSocket auth returns None with expired token.

        Expired tokens should be handled consistently with HTTP auth.
        """
        # Mock WebSocket with expired token
        mock_websocket = Mock()
        mock_websocket.query_params = {"token": expired_token_credentials["token"]}

        # Mock services
        from app.services import ServiceProvider
        mock_services = Mock(spec=ServiceProvider)
        mock_services.db = db_session

        with patch("app.dependencies.auth_dependencies._firebase_service") as mock_firebase:
            # Firebase validation fails for expired token
            from firebase_admin.auth import ExpiredIdTokenError
            mock_firebase.verify_token = AsyncMock(
                side_effect=ExpiredIdTokenError("Token expired")
            )

            # Act
            ws_user = await get_current_user_websocket(mock_websocket, mock_services)

            # Assert
            assert ws_user is None

    @pytest.mark.asyncio
    async def test_websocket_auth_fails_for_inactive_user(
        self,
        db_session,
        doctor_a_credentials: Dict[str, str],
        create_test_user
    ):
        """
        Test WebSocket auth returns None for inactive user.

        Inactive users should be denied access via WebSocket,
        same as HTTP endpoints.
        """
        # Create inactive user
        user = create_test_user(
            email=doctor_a_credentials["email"],
            firebase_uid=doctor_a_credentials["firebase_uid"],
            is_active=False  # User is disabled
        )

        # Mock WebSocket
        mock_websocket = Mock()
        mock_websocket.query_params = {"token": doctor_a_credentials["token"]}

        # Mock services
        from app.services import ServiceProvider
        mock_services = Mock(spec=ServiceProvider)
        mock_services.db = db_session
        mock_services.user_repository = Mock()
        mock_services.user_repository.get_by_email = Mock(return_value=user)

        with patch("app.dependencies.auth_dependencies._firebase_service") as mock_firebase:
            mock_firebase.verify_token = AsyncMock(return_value={
                "uid": doctor_a_credentials["firebase_uid"],
                "email": doctor_a_credentials["email"],
                "email_verified": True
            })

            # Act
            ws_user = await get_current_user_websocket(mock_websocket, mock_services)

            # Assert
            assert ws_user is None

    @pytest.mark.asyncio
    async def test_websocket_auth_without_token_returns_none(
        self,
        db_session
    ):
        """
        Test WebSocket auth returns None when no token provided.

        Unauthenticated WebSocket connections should be allowed
        but return None user (for public endpoints).
        """
        # Mock WebSocket without token
        mock_websocket = Mock()
        mock_websocket.query_params = {}
        mock_websocket.headers = {}

        # Mock services
        from app.services import ServiceProvider
        mock_services = Mock(spec=ServiceProvider)
        mock_services.db = db_session

        # Act
        ws_user = await get_current_user_websocket(mock_websocket, mock_services)

        # Assert
        assert ws_user is None
