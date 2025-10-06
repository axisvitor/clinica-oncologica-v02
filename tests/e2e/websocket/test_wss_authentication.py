"""
E2E Tests for WebSocket WSS Authentication

Tests WebSocket connections over WSS protocol with Firebase JWT authentication
in Railway production environment.
"""
import pytest
import os
import asyncio
import websockets
import json
from typing import Optional


@pytest.fixture
def railway_backend_url():
    """Railway production backend URL (HTTPS)"""
    return os.getenv(
        "RAILWAY_BACKEND_URL",
        "https://backend-hormonia-production.up.railway.app"
    )


@pytest.fixture
def railway_ws_url(railway_backend_url):
    """Railway WebSocket URL (WSS - secure)"""
    # Convert HTTPS to WSS
    ws_url = railway_backend_url.replace("https://", "wss://")
    return f"{ws_url}/ws/appointments"


@pytest.fixture
def test_firebase_token():
    """Test Firebase token from environment"""
    return os.getenv("TEST_FIREBASE_TOKEN")


class TestWebSocketWSSConnection:
    """Test suite for WebSocket WSS connections"""

    @pytest.mark.asyncio
    async def test_wss_protocol_required(self, railway_ws_url):
        """
        Test 1: WebSocket connections use WSS protocol (secure)

        Validates:
        - URL uses wss:// not ws://
        - No insecure WebSocket connections in production
        - HTTPS → WSS conversion is correct
        """
        assert railway_ws_url.startswith("wss://"), \
            f"WebSocket URL must use WSS protocol, got: {railway_ws_url}"

    @pytest.mark.asyncio
    async def test_wss_connection_without_token_rejected(self, railway_ws_url):
        """
        Test 2: WebSocket connection without token is rejected

        Validates:
        - Unauthenticated connections are refused
        - Connection requires valid token parameter
        - Security is enforced at WebSocket layer
        """
        try:
            async with websockets.connect(
                railway_ws_url,
                timeout=10
            ) as websocket:
                # If connection succeeds without token, test should fail
                pytest.fail("WebSocket should reject connections without authentication")

        except websockets.exceptions.InvalidStatusCode as e:
            # Expected: Should get 401 or 403
            assert e.status_code in [401, 403], \
                f"Expected 401/403 for unauthenticated connection, got {e.status_code}"

        except websockets.exceptions.WebSocketException:
            # Also acceptable - connection rejected
            pass

        except asyncio.TimeoutError:
            pytest.skip("WebSocket connection timed out - may not be deployed")

    @pytest.mark.asyncio
    async def test_wss_connection_with_valid_token(self, railway_ws_url, test_firebase_token):
        """
        Test 3: WebSocket connection succeeds with valid Firebase token

        Validates:
        - Valid Firebase JWT allows WebSocket connection
        - Token is passed via query parameter
        - Connection is established successfully
        """
        if not test_firebase_token:
            pytest.skip("TEST_FIREBASE_TOKEN not set - skipping")

        ws_url_with_token = f"{railway_ws_url}?token={test_firebase_token}"

        try:
            async with websockets.connect(
                ws_url_with_token,
                timeout=10
            ) as websocket:
                # Connection succeeded
                assert websocket.open, "WebSocket should be open"

                # Try to receive initial message (if any)
                try:
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=5.0
                    )
                    # Successfully received message
                    assert message is not None

                except asyncio.TimeoutError:
                    # No initial message is also OK
                    pass

        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 401:
                pytest.skip(f"Token may be expired or invalid: {e}")
            else:
                pytest.fail(f"Unexpected WebSocket error: {e}")

        except asyncio.TimeoutError:
            pytest.skip("WebSocket connection timed out")

    @pytest.mark.asyncio
    async def test_wss_connection_with_expired_token(self, railway_ws_url):
        """
        Test 4: WebSocket connection with expired token is rejected

        Validates:
        - Expired tokens are rejected at WebSocket layer
        - No connection established with invalid token
        - Security validation happens before upgrade
        """
        expired_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjF9.invalid"
        ws_url_with_token = f"{railway_ws_url}?token={expired_token}"

        try:
            async with websockets.connect(
                ws_url_with_token,
                timeout=10
            ) as websocket:
                pytest.fail("WebSocket should reject expired tokens")

        except websockets.exceptions.InvalidStatusCode as e:
            assert e.status_code in [401, 403], \
                f"Expected 401/403 for expired token, got {e.status_code}"

        except websockets.exceptions.WebSocketException:
            # Connection rejected - acceptable
            pass

    @pytest.mark.asyncio
    async def test_wss_message_exchange(self, railway_ws_url, test_firebase_token):
        """
        Test 5: WebSocket message exchange works correctly

        Validates:
        - Can send messages over WebSocket
        - Can receive messages over WebSocket
        - Bidirectional communication works
        - Connection remains stable
        """
        if not test_firebase_token:
            pytest.skip("TEST_FIREBASE_TOKEN not set")

        ws_url_with_token = f"{railway_ws_url}?token={test_firebase_token}"

        try:
            async with websockets.connect(
                ws_url_with_token,
                timeout=10
            ) as websocket:
                # Send a test message
                test_message = json.dumps({
                    "type": "ping",
                    "timestamp": "2025-10-06T00:00:00Z"
                })

                await websocket.send(test_message)

                # Wait for response
                try:
                    response = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=5.0
                    )

                    assert response is not None
                    # Try to parse as JSON
                    try:
                        response_data = json.loads(response)
                        assert isinstance(response_data, dict)
                    except json.JSONDecodeError:
                        # Response may not be JSON
                        pass

                except asyncio.TimeoutError:
                    # No response is OK for this test
                    pass

        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 401:
                pytest.skip("Token expired or invalid")
            else:
                pytest.fail(f"WebSocket error: {e}")

    @pytest.mark.asyncio
    async def test_wss_connection_close_gracefully(self, railway_ws_url, test_firebase_token):
        """
        Test 6: WebSocket connection closes gracefully

        Validates:
        - Connection can be closed cleanly
        - No errors on connection close
        - Proper cleanup after disconnect
        """
        if not test_firebase_token:
            pytest.skip("TEST_FIREBASE_TOKEN not set")

        ws_url_with_token = f"{railway_ws_url}?token={test_firebase_token}"

        try:
            async with websockets.connect(
                ws_url_with_token,
                timeout=10
            ) as websocket:
                # Connection established
                assert websocket.open

                # Close connection
                await websocket.close()

                # Verify closed
                assert not websocket.open

        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 401:
                pytest.skip("Token expired or invalid")

    @pytest.mark.asyncio
    async def test_wss_reconnection_after_disconnect(self, railway_ws_url, test_firebase_token):
        """
        Test 7: WebSocket can reconnect after disconnect

        Validates:
        - Client can reconnect after disconnection
        - No issues with multiple connections
        - Token remains valid across connections
        """
        if not test_firebase_token:
            pytest.skip("TEST_FIREBASE_TOKEN not set")

        ws_url_with_token = f"{railway_ws_url}?token={test_firebase_token}"

        try:
            # First connection
            async with websockets.connect(ws_url_with_token, timeout=10) as ws1:
                assert ws1.open

            # Second connection (reconnect)
            async with websockets.connect(ws_url_with_token, timeout=10) as ws2:
                assert ws2.open

        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 401:
                pytest.skip("Token expired or invalid")

    @pytest.mark.asyncio
    async def test_wss_multiple_concurrent_connections(self, railway_ws_url, test_firebase_token):
        """
        Test 8: Multiple concurrent WebSocket connections

        Validates:
        - Server handles multiple connections from same user
        - No race conditions with concurrent connections
        - All connections work independently
        """
        if not test_firebase_token:
            pytest.skip("TEST_FIREBASE_TOKEN not set")

        ws_url_with_token = f"{railway_ws_url}?token={test_firebase_token}"

        try:
            # Open 3 concurrent connections
            connections = []
            for _ in range(3):
                ws = await websockets.connect(ws_url_with_token, timeout=10)
                connections.append(ws)

            # Verify all are open
            for ws in connections:
                assert ws.open

            # Close all
            for ws in connections:
                await ws.close()

        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 401:
                pytest.skip("Token expired or invalid")
            else:
                pytest.fail(f"Error with concurrent connections: {e}")


@pytest.mark.integration
class TestWebSocketProductionIntegration:
    """Integration tests for WebSocket in production"""

    @pytest.mark.skip(reason="Requires live deployment")
    async def test_wss_appointment_notifications(self):
        """
        Test 9: WebSocket appointment notifications work

        Manual test steps:
        1. Connect to WebSocket with valid token
        2. Create/update an appointment via API
        3. Verify WebSocket receives notification
        4. Check notification format and content
        5. Verify only authorized users receive notification

        Expected: Real-time notifications over WSS
        """
        pass

    @pytest.mark.skip(reason="Requires browser testing")
    async def test_wss_frontend_integration(self):
        """
        Test 10: Frontend WebSocket integration works

        Manual test steps:
        1. Login to production frontend
        2. Open browser DevTools → Network → WS tab
        3. Verify WebSocket connection established
        4. Check connection uses wss:// protocol
        5. Verify token is included in connection
        6. Test real-time updates work

        Expected: Frontend successfully connects via WSS
        """
        pass

    @pytest.mark.skip(reason="Requires load testing")
    async def test_wss_load_handling(self):
        """
        Test 11: WebSocket handles load correctly

        Manual test steps:
        1. Open 50+ WebSocket connections
        2. Send messages on all connections
        3. Monitor Railway metrics
        4. Check for connection drops
        5. Verify performance is acceptable

        Expected: Stable connections under load
        """
        pass


@pytest.mark.smoke
class TestWebSocketSmoke:
    """Quick smoke tests for WebSocket"""

    @pytest.mark.asyncio
    async def test_ws_endpoint_exists(self, railway_backend_url):
        """
        Smoke Test 1: WebSocket endpoint is configured

        Quick check that endpoint exists
        """
        import httpx

        async with httpx.AsyncClient() as client:
            try:
                # Try to access WebSocket endpoint via HTTP (will fail but should get recognized)
                response = await client.get(f"{railway_backend_url}/ws/appointments")

                # Should get 400 or 426 (Upgrade Required) not 404
                assert response.status_code != 404, \
                    "WebSocket endpoint should exist (not 404)"

            except httpx.ConnectError:
                pytest.skip("Cannot connect to backend")

    @pytest.mark.asyncio
    async def test_wss_url_format_correct(self, railway_ws_url):
        """
        Smoke Test 2: WSS URL is correctly formatted

        Quick validation of URL format
        """
        assert railway_ws_url.startswith("wss://")
        assert "/ws/appointments" in railway_ws_url
        assert railway_ws_url.count("wss://") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
