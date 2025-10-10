"""
Integration tests for Request Validation Middleware.

Tests request validation, input sanitization, and data validation.
"""

import pytest
import json
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field, validator
import re
from unittest.mock import Mock, patch


class ValidationConfig:
    """Configuration for validation rules."""

    def __init__(self):
        self.max_body_size = 1024 * 1024  # 1MB
        self.max_query_params = 10
        self.max_header_size = 8192
        self.allowed_content_types = [
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data"
        ]
        self.blocked_patterns = [
            r"<script.*?>.*?</script>",  # XSS
            r"javascript:",  # XSS
            r"on\w+\s*=",  # Event handlers
            r"SELECT.*FROM",  # SQL injection
            r"DROP\s+TABLE",  # SQL injection
            r"UNION\s+SELECT",  # SQL injection
            r"\.\./",  # Path traversal
            r"\\x[0-9a-fA-F]{2}",  # Hex encoding
        ]
        self.email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        self.phone_pattern = r"^\+?1?\d{9,15}$"


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Request validation and sanitization middleware."""

    def __init__(
        self,
        app,
        config: ValidationConfig = None,
        enable_sanitization: bool = True,
        enable_size_limits: bool = True,
        enable_pattern_blocking: bool = True,
        log_violations: bool = True
    ):
        super().__init__(app)
        self.config = config or ValidationConfig()
        self.enable_sanitization = enable_sanitization
        self.enable_size_limits = enable_size_limits
        self.enable_pattern_blocking = enable_pattern_blocking
        self.log_violations = log_violations
        self.violations_log = []

    async def dispatch(self, request: Request, call_next):
        """Validate and sanitize incoming requests."""
        try:
            # Validate request size
            if self.enable_size_limits:
                await self._validate_size(request)

            # Validate content type
            await self._validate_content_type(request)

            # Validate headers
            await self._validate_headers(request)

            # Validate query parameters
            await self._validate_query_params(request)

            # Validate and sanitize body
            if request.method in ["POST", "PUT", "PATCH"]:
                await self._validate_body(request)

            # Process request
            response = await call_next(request)

            return response

        except ValidationError as e:
            if self.log_violations:
                self.violations_log.append({
                    "path": request.url.path,
                    "method": request.method,
                    "error": str(e),
                    "type": "validation"
                })
            return JSONResponse(
                status_code=400,
                content={"error": str(e), "type": "validation_error"}
            )
        except HTTPException:
            raise
        except Exception as e:
            if self.log_violations:
                self.violations_log.append({
                    "path": request.url.path,
                    "method": request.method,
                    "error": str(e),
                    "type": "internal"
                })
            raise

    async def _validate_size(self, request: Request):
        """Validate request size limits."""
        # Check Content-Length header
        content_length = request.headers.get("Content-Length")
        if content_length:
            size = int(content_length)
            if size > self.config.max_body_size:
                raise ValidationError(f"Request body too large: {size} bytes")

        # Check header size
        headers_size = sum(len(k) + len(v) for k, v in request.headers.items())
        if headers_size > self.config.max_header_size:
            raise ValidationError(f"Headers too large: {headers_size} bytes")

    async def _validate_content_type(self, request: Request):
        """Validate content type."""
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("Content-Type", "").split(";")[0]
            if content_type and content_type not in self.config.allowed_content_types:
                raise ValidationError(f"Invalid content type: {content_type}")

    async def _validate_headers(self, request: Request):
        """Validate request headers."""
        for key, value in request.headers.items():
            # Check for malicious patterns
            if self.enable_pattern_blocking:
                for pattern in self.config.blocked_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        raise ValidationError(f"Blocked pattern in header: {key}")

            # Sanitize header values
            if self.enable_sanitization:
                request.headers._list = [
                    (k, self._sanitize_string(v) if k == key else v)
                    for k, v in request.headers._list
                ]

    async def _validate_query_params(self, request: Request):
        """Validate query parameters."""
        params = dict(request.query_params)

        # Check parameter count
        if len(params) > self.config.max_query_params:
            raise ValidationError(f"Too many query parameters: {len(params)}")

        # Validate each parameter
        for key, value in params.items():
            # Check for malicious patterns
            if self.enable_pattern_blocking:
                for pattern in self.config.blocked_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        raise ValidationError(f"Blocked pattern in query param: {key}")

            # Sanitize values
            if self.enable_sanitization:
                params[key] = self._sanitize_string(value)

    async def _validate_body(self, request: Request):
        """Validate and sanitize request body."""
        # Read body
        body = await request.body()

        # Check size
        if self.enable_size_limits and len(body) > self.config.max_body_size:
            raise ValidationError(f"Request body too large: {len(body)} bytes")

        # Parse and validate JSON
        if request.headers.get("Content-Type", "").startswith("application/json"):
            try:
                data = json.loads(body)

                # Validate nested data
                self._validate_json_data(data)

                # Sanitize if enabled
                if self.enable_sanitization:
                    data = self._sanitize_json_data(data)
                    # Update body for downstream
                    request._body = json.dumps(data).encode()

            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON in request body")

    def _validate_json_data(self, data: Any, depth: int = 0):
        """Recursively validate JSON data."""
        if depth > 10:
            raise ValidationError("JSON nesting too deep")

        if isinstance(data, dict):
            for key, value in data.items():
                # Check key
                if self.enable_pattern_blocking:
                    for pattern in self.config.blocked_patterns:
                        if re.search(pattern, str(key), re.IGNORECASE):
                            raise ValidationError(f"Blocked pattern in JSON key: {key}")

                # Recurse
                self._validate_json_data(value, depth + 1)

        elif isinstance(data, list):
            for item in data:
                self._validate_json_data(item, depth + 1)

        elif isinstance(data, str):
            # Check for malicious patterns
            if self.enable_pattern_blocking:
                for pattern in self.config.blocked_patterns:
                    if re.search(pattern, data, re.IGNORECASE):
                        raise ValidationError(f"Blocked pattern in JSON value")

    def _sanitize_json_data(self, data: Any) -> Any:
        """Recursively sanitize JSON data."""
        if isinstance(data, dict):
            return {
                self._sanitize_string(k): self._sanitize_json_data(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._sanitize_json_data(item) for item in data]
        elif isinstance(data, str):
            return self._sanitize_string(data)
        else:
            return data

    def _sanitize_string(self, value: str) -> str:
        """Sanitize string value."""
        # Remove null bytes
        value = value.replace('\x00', '')

        # HTML escape
        value = value.replace('<', '&lt;').replace('>', '&gt;')

        # Remove control characters
        value = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')

        return value.strip()


class ValidationError(Exception):
    """Custom validation error."""
    pass


from starlette.responses import JSONResponse


# Test models for validation
class UserModel(BaseModel):
    """Test user model with validation."""
    username: str = Field(..., min_length=3, max_length=20)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    age: int = Field(..., ge=0, le=150)

    @validator('username')
    def validate_username(cls, v):
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v


@pytest.fixture
def app_with_validation():
    """Create FastAPI app with validation middleware."""
    app = FastAPI()
    config = ValidationConfig()

    # Add validation middleware
    app.add_middleware(
        RequestValidationMiddleware,
        config=config,
        enable_sanitization=True,
        enable_size_limits=True,
        enable_pattern_blocking=True,
        log_violations=True
    )

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.post("/user")
    async def create_user(user: UserModel):
        return {"user": user.dict()}

    @app.post("/data")
    async def post_data(request: Request):
        body = await request.body()
        return {"size": len(body)}

    @app.get("/search")
    async def search(q: str):
        return {"query": q}

    @app.post("/raw")
    async def raw_data(request: Request):
        body = await request.body()
        data = json.loads(body)
        return {"received": data}

    return app, config


@pytest.fixture
def client(app_with_validation):
    """Create test client."""
    app, config = app_with_validation
    client = TestClient(app)

    # Get middleware instance for inspection
    middleware = None
    for m in app.middleware:
        if hasattr(m, 'cls') and m.cls == RequestValidationMiddleware:
            middleware = m.kwargs
            break

    return client, config, middleware


class TestRequestValidation:
    """Test request validation functionality."""

    def test_valid_request(self, client):
        """Test valid request passes through."""
        test_client, config, middleware = client
        response = test_client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_valid_post_request(self, client):
        """Test valid POST request with JSON."""
        test_client, config, middleware = client
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "age": 25
        }
        response = test_client.post("/user", json=user_data)
        assert response.status_code == 200

    def test_invalid_json(self, client):
        """Test invalid JSON is rejected."""
        test_client, config, middleware = client
        response = test_client.post(
            "/data",
            data="{invalid json}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["error"]

    def test_body_size_limit(self, client):
        """Test request body size limit."""
        test_client, config, middleware = client

        # Create large payload
        large_data = {"data": "x" * (config.max_body_size + 1)}

        response = test_client.post("/data", json=large_data)
        assert response.status_code == 400
        assert "too large" in response.json()["error"].lower()

    def test_sql_injection_blocking(self, client):
        """Test SQL injection patterns are blocked."""
        test_client, config, middleware = client

        # Try SQL injection in query parameter
        response = test_client.get("/search?q='; DROP TABLE users;--")
        assert response.status_code == 400
        assert "Blocked pattern" in response.json()["error"]

    def test_xss_blocking(self, client):
        """Test XSS patterns are blocked."""
        test_client, config, middleware = client

        # Try XSS in JSON body
        xss_data = {"comment": "<script>alert('XSS')</script>"}
        response = test_client.post("/raw", json=xss_data)
        assert response.status_code == 400
        assert "Blocked pattern" in response.json()["error"]

    def test_path_traversal_blocking(self, client):
        """Test path traversal patterns are blocked."""
        test_client, config, middleware = client

        # Try path traversal in query
        response = test_client.get("/search?q=../../etc/passwd")
        assert response.status_code == 400
        assert "Blocked pattern" in response.json()["error"]

    def test_header_validation(self, client):
        """Test header validation."""
        test_client, config, middleware = client

        # Try malicious pattern in header
        response = test_client.get(
            "/test",
            headers={"X-Custom": "SELECT * FROM users"}
        )
        assert response.status_code == 400
        assert "Blocked pattern in header" in response.json()["error"]

    def test_query_param_limit(self, client):
        """Test query parameter count limit."""
        test_client, config, middleware = client

        # Create too many query parameters
        params = "&".join([f"param{i}={i}" for i in range(config.max_query_params + 2)])
        response = test_client.get(f"/test?{params}")
        assert response.status_code == 400
        assert "Too many query parameters" in response.json()["error"]

    def test_content_type_validation(self, client):
        """Test content type validation."""
        test_client, config, middleware = client

        # Try unsupported content type
        response = test_client.post(
            "/data",
            data="test data",
            headers={"Content-Type": "text/plain"}
        )
        assert response.status_code == 400
        assert "Invalid content type" in response.json()["error"]

    def test_sanitization(self, client):
        """Test input sanitization."""
        test_client, config, middleware = client

        # Send data with HTML tags (not in blocked patterns)
        data = {"text": "Hello <b>world</b>"}
        response = test_client.post("/raw", json=data)

        # Should be sanitized but not blocked
        assert response.status_code == 200
        result = response.json()["received"]
        assert result["text"] == "Hello &lt;b&gt;world&lt;/b&gt;"

    def test_null_byte_removal(self, client):
        """Test null byte removal."""
        test_client, config, middleware = client

        # Send data with null bytes
        response = test_client.get("/search?q=test\x00value")

        # Should process without null bytes
        if response.status_code == 200:
            assert "\x00" not in response.json()["query"]

    def test_nested_json_validation(self, client):
        """Test deeply nested JSON validation."""
        test_client, config, middleware = client

        # Create deeply nested structure
        data = {"level1": {}}
        current = data["level1"]
        for i in range(12):  # More than max depth
            current["level"] = {}
            current = current["level"]

        response = test_client.post("/raw", json=data)
        assert response.status_code == 400
        assert "too deep" in response.json()["error"].lower()


class TestValidationConfiguration:
    """Test validation middleware configuration."""

    def test_disable_sanitization(self):
        """Test with sanitization disabled."""
        app = FastAPI()
        config = ValidationConfig()

        app.add_middleware(
            RequestValidationMiddleware,
            config=config,
            enable_sanitization=False
        )

        @app.post("/test")
        async def test(request: Request):
            body = await request.body()
            return {"data": json.loads(body)}

        client = TestClient(app)

        # HTML should not be sanitized
        response = client.post("/test", json={"text": "<b>test</b>"})
        assert response.status_code == 200
        assert response.json()["data"]["text"] == "<b>test</b>"

    def test_disable_size_limits(self):
        """Test with size limits disabled."""
        app = FastAPI()
        config = ValidationConfig()
        config.max_body_size = 100  # Very small limit

        app.add_middleware(
            RequestValidationMiddleware,
            config=config,
            enable_size_limits=False
        )

        @app.post("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)

        # Large body should be allowed
        large_data = {"data": "x" * 1000}
        response = client.post("/test", json=large_data)
        assert response.status_code == 200

    def test_disable_pattern_blocking(self):
        """Test with pattern blocking disabled."""
        app = FastAPI()
        config = ValidationConfig()

        app.add_middleware(
            RequestValidationMiddleware,
            config=config,
            enable_pattern_blocking=False
        )

        @app.get("/test")
        async def test(q: str):
            return {"query": q}

        client = TestClient(app)

        # SQL pattern should be allowed
        response = client.get("/test?q=SELECT * FROM users")
        assert response.status_code == 200


class TestValidationPerformance:
    """Test validation performance impact."""

    def test_validation_overhead(self, client):
        """Test validation overhead is acceptable."""
        test_client, config, middleware = client
        import time

        # Warm up
        test_client.get("/test")

        # Measure with small payload
        small_data = {"key": "value"}
        start = time.time()
        for _ in range(100):
            response = test_client.post("/raw", json=small_data)
            assert response.status_code == 200
        validation_time = time.time() - start

        # Should be reasonably fast
        avg_time = validation_time / 100
        assert avg_time < 0.01  # Less than 10ms per request

    def test_large_json_performance(self, client):
        """Test performance with larger JSON."""
        test_client, config, middleware = client
        import time

        # Create medium-sized JSON
        data = {
            f"field_{i}": {
                "value": f"data_{i}",
                "nested": {"id": i}
            }
            for i in range(100)
        }

        start = time.time()
        response = test_client.post("/raw", json=data)
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 0.1  # Should process in under 100ms