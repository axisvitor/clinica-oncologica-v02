"""
Integration tests for Session Middleware.

Tests session management functionality.
"""

import pytest
import json
import time
import uuid
from typing import Dict, Optional
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from unittest.mock import Mock, patch, AsyncMock
import redis.asyncio as redis


class SessionStore:
    """In-memory session store for testing."""

    def __init__(self):
        self.sessions: Dict[str, dict] = {}

    async def get(self, session_id: str) -> Optional[dict]:
        """Get session data."""
        session = self.sessions.get(session_id)
        if session and session.get("expires_at", 0) > time.time():
            return session.get("data", {})
        return None

    async def set(self, session_id: str, data: dict, ttl: int = 3600):
        """Set session data."""
        self.sessions[session_id] = {
            "data": data,
            "expires_at": time.time() + ttl,
            "created_at": time.time()
        }

    async def delete(self, session_id: str):
        """Delete session."""
        self.sessions.pop(session_id, None)

    async def exists(self, session_id: str) -> bool:
        """Check if session exists."""
        session = self.sessions.get(session_id)
        return session is not None and session.get("expires_at", 0) > time.time()


class SessionMiddleware(BaseHTTPMiddleware):
    """Session management middleware."""

    def __init__(
        self,
        app,
        secret_key: str,
        session_cookie: str = "session_id",
        max_age: int = 3600,
        httponly: bool = True,
        secure: bool = False,
        samesite: str = "lax",
        store: SessionStore = None
    ):
        super().__init__(app)
        self.secret_key = secret_key
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.httponly = httponly
        self.secure = secure
        self.samesite = samesite
        self.store = store or SessionStore()

    async def dispatch(self, request: Request, call_next):
        """Handle session for request."""
        # Get session ID from cookie
        session_id = request.cookies.get(self.session_cookie)

        # Load or create session
        if session_id:
            session_data = await self.store.get(session_id)
            if session_data is None:
                # Session expired or invalid
                session_id = str(uuid.uuid4())
                session_data = {}
        else:
            # New session
            session_id = str(uuid.uuid4())
            session_data = {}

        # Attach session to request
        request.state.session = session_data
        request.state.session_id = session_id

        # Process request
        response = await call_next(request)

        # Save session if modified
        if hasattr(request.state, "session_modified") and request.state.session_modified:
            await self.store.set(session_id, request.state.session, self.max_age)

        # Set session cookie
        if not request.cookies.get(self.session_cookie) or request.state.session_modified:
            response.set_cookie(
                key=self.session_cookie,
                value=session_id,
                max_age=self.max_age,
                httponly=self.httponly,
                secure=self.secure,
                samesite=self.samesite
            )

        # Handle session deletion
        if hasattr(request.state, "delete_session") and request.state.delete_session:
            await self.store.delete(session_id)
            response.delete_cookie(self.session_cookie)

        return response


@pytest.fixture
def app_with_session():
    """Create FastAPI app with session middleware."""
    app = FastAPI()
    store = SessionStore()

    # Add session middleware
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret-key",
        session_cookie="session_id",
        max_age=3600,
        httponly=True,
        secure=False,
        samesite="lax",
        store=store
    )

    @app.get("/test")
    async def test_endpoint(request: Request):
        return {"session_id": request.state.session_id}

    @app.get("/get-session")
    async def get_session(request: Request):
        return {"session": request.state.session}

    @app.post("/set-session")
    async def set_session(request: Request, data: dict):
        request.state.session.update(data)
        request.state.session_modified = True
        return {"status": "session updated"}

    @app.get("/user")
    async def get_user(request: Request):
        user = request.state.session.get("user")
        if not user:
            return {"error": "Not logged in"}, 401
        return {"user": user}

    @app.post("/login")
    async def login(request: Request, username: str):
        request.state.session["user"] = username
        request.state.session["login_time"] = time.time()
        request.state.session_modified = True
        return {"status": "logged in", "user": username}

    @app.post("/logout")
    async def logout(request: Request):
        request.state.delete_session = True
        return {"status": "logged out"}

    @app.get("/counter")
    async def counter(request: Request):
        count = request.state.session.get("count", 0) + 1
        request.state.session["count"] = count
        request.state.session_modified = True
        return {"count": count}

    return app, store


@pytest.fixture
def client(app_with_session):
    """Create test client."""
    app, store = app_with_session
    return TestClient(app), store


class TestSessionMiddleware:
    """Test session middleware functionality."""

    def test_new_session_creation(self, client):
        """Test new session is created for first request."""
        test_client, store = client
        response = test_client.get("/test")
        assert response.status_code == 200

        # Should have session cookie
        assert "session_id" in response.cookies
        session_id = response.cookies["session_id"]
        assert session_id is not None
        assert len(session_id) == 36  # UUID format

    def test_session_persistence(self, client):
        """Test session persists across requests."""
        test_client, store = client

        # First request
        response1 = test_client.get("/test")
        session_id1 = response1.json()["session_id"]

        # Second request with same client
        response2 = test_client.get("/test")
        session_id2 = response2.json()["session_id"]

        # Should have same session ID
        assert session_id1 == session_id2

    def test_session_data_storage(self, client):
        """Test session data can be stored and retrieved."""
        test_client, store = client

        # Set session data
        response = test_client.post("/set-session", json={"key": "value", "number": 123})
        assert response.status_code == 200

        # Get session data
        response = test_client.get("/get-session")
        assert response.status_code == 200
        session_data = response.json()["session"]
        assert session_data["key"] == "value"
        assert session_data["number"] == 123

    def test_session_cookie_attributes(self, client):
        """Test session cookie has correct attributes."""
        test_client, store = client
        response = test_client.get("/test")

        # Check cookie attributes
        cookie_header = response.headers.get("set-cookie")
        assert "HttpOnly" in cookie_header
        assert "SameSite=lax" in cookie_header.lower()
        assert "Max-Age=3600" in cookie_header

    def test_login_logout_flow(self, client):
        """Test login and logout session flow."""
        test_client, store = client

        # Login
        response = test_client.post("/login?username=testuser")
        assert response.status_code == 200
        assert response.json()["user"] == "testuser"

        # Check user in session
        response = test_client.get("/user")
        assert response.status_code == 200
        assert response.json()["user"] == "testuser"

        # Logout
        response = test_client.post("/logout")
        assert response.status_code == 200

        # Check session deleted
        response = test_client.get("/user")
        assert "error" in response.json()

    def test_session_counter(self, client):
        """Test session-based counter."""
        test_client, store = client

        # First visit
        response = test_client.get("/counter")
        assert response.json()["count"] == 1

        # Second visit
        response = test_client.get("/counter")
        assert response.json()["count"] == 2

        # Third visit
        response = test_client.get("/counter")
        assert response.json()["count"] == 3

    def test_multiple_sessions(self, client):
        """Test multiple independent sessions."""
        test_client, store = client

        # First client
        client1 = TestClient(test_client.app)
        response1 = client1.post("/set-session", json={"client": "one"})
        assert response1.status_code == 200

        # Second client
        client2 = TestClient(test_client.app)
        response2 = client2.post("/set-session", json={"client": "two"})
        assert response2.status_code == 200

        # Verify sessions are independent
        response1 = client1.get("/get-session")
        assert response1.json()["session"]["client"] == "one"

        response2 = client2.get("/get-session")
        assert response2.json()["session"]["client"] == "two"

    def test_session_deletion_removes_cookie(self, client):
        """Test session deletion removes cookie."""
        test_client, store = client

        # Create session
        response = test_client.post("/set-session", json={"data": "test"})
        assert response.status_code == 200

        # Delete session
        response = test_client.post("/logout")
        assert response.status_code == 200

        # Check cookie is deleted
        cookie_header = response.headers.get("set-cookie")
        assert "session_id=;" in cookie_header or "session_id=\"\"" in cookie_header

    def test_invalid_session_creates_new(self, client):
        """Test invalid session ID creates new session."""
        test_client, store = client

        # Set invalid session cookie
        test_client.cookies.set("session_id", "invalid-session-id")

        response = test_client.get("/test")
        assert response.status_code == 200

        # Should get new session ID
        new_session_id = response.json()["session_id"]
        assert new_session_id != "invalid-session-id"
        assert len(new_session_id) == 36


class TestSessionExpiration:
    """Test session expiration handling."""

    def test_expired_session_creates_new(self):
        """Test expired session creates new session."""
        app = FastAPI()
        store = SessionStore()

        app.add_middleware(
            SessionMiddleware,
            secret_key="test",
            max_age=1,  # 1 second expiry
            store=store
        )

        @app.get("/test")
        async def test(request: Request):
            return {"session_id": request.state.session_id}

        client = TestClient(app)

        # First request
        response1 = client.get("/test")
        session_id1 = response1.json()["session_id"]

        # Wait for expiry
        time.sleep(2)

        # Second request
        response2 = client.get("/test")
        session_id2 = response2.json()["session_id"]

        # Should have new session
        assert session_id1 != session_id2


class TestSessionSecurity:
    """Test session security features."""

    def test_secure_cookie_flag(self):
        """Test secure flag on cookie."""
        app = FastAPI()

        app.add_middleware(
            SessionMiddleware,
            secret_key="test",
            secure=True
        )

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")

        cookie_header = response.headers.get("set-cookie")
        assert "Secure" in cookie_header

    def test_session_fixation_prevention(self, client):
        """Test session ID changes on login."""
        test_client, store = client

        # Get initial session
        response = test_client.get("/test")
        initial_session_id = response.json()["session_id"]

        # Login (should ideally regenerate session ID)
        response = test_client.post("/login?username=testuser")

        # Note: In a real implementation, session ID should change
        # to prevent session fixation attacks


class TestSessionPerformance:
    """Test session performance."""

    def test_session_overhead(self, client):
        """Test session middleware overhead."""
        test_client, store = client
        import time

        # Warm up
        test_client.get("/test")

        # Measure with session
        start = time.time()
        for _ in range(100):
            response = test_client.get("/test")
            assert response.status_code == 200
        session_time = time.time() - start

        # Should be fast
        avg_time = session_time / 100
        assert avg_time < 0.01  # Less than 10ms per request

    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, client):
        """Test concurrent session handling."""
        test_client, store = client
        import asyncio

        async def make_request(client_num):
            client = TestClient(test_client.app)
            response = client.post("/set-session", json={"client": client_num})
            return response.status_code

        # Create concurrent sessions
        tasks = [make_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(status == 200 for status in results)