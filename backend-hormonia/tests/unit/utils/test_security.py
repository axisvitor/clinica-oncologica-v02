"""
Comprehensive unit tests for app.utils.security module.
Tests password hashing, JWT tokens, input validation, and security utilities.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, Request, status
from fastapi.datastructures import Headers

from app.utils.security import (
    hash_password, verify_password, get_password_hash,
    create_access_token, create_refresh_token, verify_token,
    validate_password_strength, mask_sensitive_url, mask_dict_secrets,
    validate_public_request, sanitize_input, validate_token_format,
    validate_uuid_format, generate_security_headers,
    _check_suspicious_headers, _contains_suspicious_patterns,
    mask_sensitive_url as mask_sensitive_url_duplicate,
    create_pwd_context, pwd_context
)
from app.config import settings


class TestPasswordHashing:
    """Test password hashing and verification functionality."""

    def test_hash_password_success(self):
        """Test successful password hashing."""
        password = "test_password_123"
        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password  # Should be hashed, not plain text

    def test_hash_password_empty(self):
        """Test hashing empty password raises ValueError."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password("")

    def test_hash_password_none(self):
        """Test hashing None password raises ValueError."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password(None)

    def test_hash_password_long(self):
        """Test hashing very long password (>72 bytes) gets truncated."""
        # Create a password longer than 72 bytes
        long_password = "a" * 100

        with patch('app.utils.security.logger') as mock_logger:
            hashed = hash_password(long_password)
            mock_logger.warning.assert_called_with("Password truncated to 72 bytes")

        assert hashed is not None

    @patch('app.utils.security.pwd_context', None)
    def test_hash_password_fallback_to_bcrypt(self):
        """Test fallback to direct bcrypt when pwd_context is None."""
        password = "test_password"

        with patch('app.utils.security.bcrypt_lib.gensalt') as mock_gensalt, \
             patch('app.utils.security.bcrypt_lib.hashpw') as mock_hashpw:

            mock_gensalt.return_value = b'salt'
            mock_hashpw.return_value = b'hashed_password'

            result = hash_password(password)

            mock_gensalt.assert_called_once_with(rounds=12)
            mock_hashpw.assert_called_once()
            assert result == 'hashed_password'

    def test_verify_password_success(self):
        """Test successful password verification."""
        password = "test_password_123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_wrong_password(self):
        """Test password verification with wrong password."""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_inputs(self):
        """Test password verification with empty inputs."""
        assert verify_password("", "hash") is False
        assert verify_password("password", "") is False
        assert verify_password("", "") is False
        assert verify_password(None, "hash") is False
        assert verify_password("password", None) is False

    def test_verify_password_long_password(self):
        """Test password verification with long password (>72 bytes)."""
        # Create a password longer than 72 bytes
        long_password = "a" * 100
        hashed = hash_password(long_password)

        # Should verify successfully even with long password
        assert verify_password(long_password, hashed) is True

    @patch('app.utils.security.pwd_context')
    def test_verify_password_passlib_bug_fallback(self, mock_pwd_context):
        """Test fallback to direct bcrypt when passlib has the 72-byte bug."""
        password = "test_password"
        hashed = "hashed_password"

        # Mock passlib to raise the specific ValueError
        mock_pwd_context.verify.side_effect = ValueError("password cannot be longer than 72 bytes")

        with patch('app.utils.security.bcrypt_lib.checkpw') as mock_checkpw, \
             patch('app.utils.security.logger') as mock_logger:

            mock_checkpw.return_value = True

            result = verify_password(password, hashed)

            assert result is True
            mock_logger.warning.assert_called_with("Passlib bcrypt bug detected, using direct bcrypt")
            mock_checkpw.assert_called_once()

    @patch('app.utils.security.pwd_context', None)
    def test_verify_password_fallback_to_bcrypt(self):
        """Test fallback to direct bcrypt when pwd_context is None."""
        password = "test_password"
        hashed = "hashed_password"

        with patch('app.utils.security.bcrypt_lib.checkpw') as mock_checkpw:
            mock_checkpw.return_value = True

            result = verify_password(password, hashed)

            assert result is True
            mock_checkpw.assert_called_once()

    def test_get_password_hash_alias(self):
        """Test get_password_hash is an alias for hash_password."""
        password = "test_password"
        hash1 = hash_password(password)
        hash2 = get_password_hash(password)

        # Should both be valid hashes
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestJWTTokens:
    """Test JWT token creation and verification."""

    def test_create_access_token(self):
        """Test access token creation."""
        data = {"sub": "test@example.com", "user_id": "123"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "test@example.com"
        assert payload["user_id"] == "123"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_access_token_with_expires_delta(self):
        """Test access token creation with custom expiration."""
        data = {"sub": "test@example.com"}
        expires_delta = timedelta(minutes=30)

        token = create_access_token(data, expires_delta)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # Verify expiration time is approximately correct
        expected_exp = datetime.utcnow() + expires_delta
        actual_exp = datetime.fromtimestamp(payload["exp"])
        diff = abs((expected_exp - actual_exp).total_seconds())
        assert diff < 5  # Within 5 seconds

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        data = {"sub": "test@example.com", "user_id": "123"}
        token = create_refresh_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "test@example.com"
        assert payload["user_id"] == "123"
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_verify_token_valid_access(self):
        """Test verification of valid access token."""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)

        token_data = verify_token(token, "access")

        assert token_data is not None
        assert token_data.email == "test@example.com"

    def test_verify_token_valid_refresh(self):
        """Test verification of valid refresh token."""
        data = {"sub": "test@example.com"}
        token = create_refresh_token(data)

        token_data = verify_token(token, "refresh")

        assert token_data is not None
        assert token_data.email == "test@example.com"

    def test_verify_token_wrong_type(self):
        """Test verification fails with wrong token type."""
        data = {"sub": "test@example.com"}
        access_token = create_access_token(data)

        # Try to verify access token as refresh token
        token_data = verify_token(access_token, "refresh")
        assert token_data is None

    def test_verify_token_expired(self):
        """Test verification fails with expired token."""
        data = {"sub": "test@example.com"}
        expires_delta = timedelta(seconds=-1)  # Already expired
        token = create_access_token(data, expires_delta)

        token_data = verify_token(token)
        assert token_data is None

    def test_verify_token_invalid(self):
        """Test verification fails with invalid token."""
        invalid_token = "invalid.token.here"

        token_data = verify_token(invalid_token)
        assert token_data is None

    def test_verify_token_no_subject(self):
        """Test verification fails when token has no subject."""
        # Create token without 'sub' field
        payload = {
            "exp": int((datetime.utcnow() + timedelta(minutes=30)).timestamp()),
            "type": "access"
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        token_data = verify_token(token)
        assert token_data is None

    def test_verify_token_no_exp(self):
        """Test verification fails when token has no expiration."""
        # Create token without 'exp' field
        payload = {
            "sub": "test@example.com",
            "type": "access"
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        token_data = verify_token(token)
        assert token_data is None


class TestPasswordValidation:
    """Test password strength validation."""

    def test_validate_password_strength_valid(self):
        """Test validation of strong password."""
        strong_password = "StrongP@ssw0rd123"
        result = validate_password_strength(strong_password)

        assert result["is_valid"] is True
        assert len(result["issues"]) == 0

    def test_validate_password_strength_too_short(self):
        """Test validation fails for too short password."""
        short_password = "Sh0rt!"
        result = validate_password_strength(short_password)

        assert result["is_valid"] is False
        assert "Password must be at least 8 characters long" in result["issues"]

    def test_validate_password_strength_too_long(self):
        """Test validation fails for too long password."""
        long_password = "A" * 129 + "1a!"
        result = validate_password_strength(long_password)

        assert result["is_valid"] is False
        assert "Password must be less than 128 characters long" in result["issues"]

    def test_validate_password_strength_missing_lowercase(self):
        """Test validation fails without lowercase letter."""
        password = "PASSWORD123!"
        result = validate_password_strength(password)

        assert result["is_valid"] is False
        assert "Password must contain at least one lowercase letter" in result["issues"]

    def test_validate_password_strength_missing_uppercase(self):
        """Test validation fails without uppercase letter."""
        password = "password123!"
        result = validate_password_strength(password)

        assert result["is_valid"] is False
        assert "Password must contain at least one uppercase letter" in result["issues"]

    def test_validate_password_strength_missing_digit(self):
        """Test validation fails without digit."""
        password = "Password!"
        result = validate_password_strength(password)

        assert result["is_valid"] is False
        assert "Password must contain at least one digit" in result["issues"]

    def test_validate_password_strength_missing_special(self):
        """Test validation fails without special character."""
        password = "Password123"
        result = validate_password_strength(password)

        assert result["is_valid"] is False
        assert "Password must contain at least one special character" in result["issues"]

    def test_validate_password_strength_common_patterns(self):
        """Test validation fails with common patterns."""
        patterns = [
            "Password111",  # Repeated characters
            "Password123",  # Sequential numbers
            "Passwordabc",  # Sequential letters
        ]

        for password in patterns:
            result = validate_password_strength(password)
            assert result["is_valid"] is False
            assert "Password contains common patterns and may be easily guessed" in result["issues"]


class TestURLMasking:
    """Test URL masking functionality."""

    def test_mask_sensitive_url_with_password(self):
        """Test masking URL with password."""
        url = "redis://:mypassword@localhost:6379/0"
        masked = mask_sensitive_url(url)

        assert "mypassword" not in masked
        assert "****" in masked
        assert "localhost:6379/0" in masked

    def test_mask_sensitive_url_with_credentials(self):
        """Test masking URL with username and password."""
        url = "https://user:secret@api.example.com/path"
        masked = mask_sensitive_url(url)

        assert "secret" not in masked
        assert "user:****@api.example.com" in masked

    def test_mask_sensitive_url_with_query_params(self):
        """Test masking URL with sensitive query parameters."""
        url = "https://api.example.com/path?token=secret123&other=value"
        masked = mask_sensitive_url(url)

        assert "secret123" not in masked
        assert "token=****" in masked
        assert "other=value" in masked

    def test_mask_sensitive_url_empty(self):
        """Test masking empty URL."""
        assert mask_sensitive_url("") == ""
        assert mask_sensitive_url(None) == ""

    def test_mask_sensitive_url_invalid(self):
        """Test masking invalid URL with fallback."""
        url = "not-a-valid-url"
        masked = mask_sensitive_url(url)

        # Should not raise exception, returns some masked version
        assert isinstance(masked, str)

    def test_mask_dict_secrets_default_keys(self):
        """Test masking dictionary with default sensitive keys."""
        data = {
            "password": "secret123",
            "DATABASE_URL": "postgres://user:pass@host/db",
            "normal_key": "normal_value",
            "token": "abc123"
        }

        masked = mask_dict_secrets(data)

        assert masked["password"] == "****"
        assert "pass" not in masked["DATABASE_URL"]
        assert masked["normal_key"] == "normal_value"
        assert masked["token"] == "****"

    def test_mask_dict_secrets_custom_keys(self):
        """Test masking dictionary with custom sensitive keys."""
        data = {
            "api_key": "secret123",
            "normal_key": "normal_value"
        }

        masked = mask_dict_secrets(data, keys_to_mask=["api_key"])

        assert masked["api_key"] == "****"
        assert masked["normal_key"] == "normal_value"

    def test_mask_dict_secrets_nested(self):
        """Test masking nested dictionary."""
        data = {
            "config": {
                "password": "secret123",
                "host": "localhost"
            }
        }

        masked = mask_dict_secrets(data)

        assert masked["config"]["password"] == "****"
        assert masked["config"]["host"] == "localhost"

    def test_mask_dict_secrets_empty(self):
        """Test masking empty dictionary."""
        assert mask_dict_secrets({}) == {}
        assert mask_dict_secrets(None) is None


class TestPublicEndpointSecurity:
    """Test public endpoint security validation."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request object."""
        request = Mock(spec=Request)
        request.headers = {}
        request.method = "GET"
        request.url = Mock()
        request.url.path = "/api/test"
        return request

    @pytest.mark.asyncio
    async def test_validate_public_request_success(self, mock_request):
        """Test successful validation of clean request."""
        mock_request.headers = {"user-agent": "Mozilla/5.0"}

        # Should not raise exception
        await validate_public_request(mock_request)

    @pytest.mark.asyncio
    async def test_validate_public_request_blocked_user_agent(self, mock_request):
        """Test blocking of suspicious user agents."""
        mock_request.headers = {"user-agent": "sqlmap/1.0"}

        with pytest.raises(HTTPException) as exc_info:
            await validate_public_request(mock_request)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_validate_public_request_oversized(self, mock_request):
        """Test blocking of oversized requests."""
        mock_request.headers = {"content-length": "2000000"}  # 2MB

        with pytest.raises(HTTPException) as exc_info:
            await validate_public_request(mock_request)

        assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_check_suspicious_headers_clean(self, mock_request):
        """Test clean headers pass validation."""
        mock_request.headers = {"authorization": "Bearer token"}

        # Should not raise exception
        await _check_suspicious_headers(mock_request)

    @pytest.mark.asyncio
    async def test_check_suspicious_headers_suspicious(self, mock_request):
        """Test suspicious headers are blocked."""
        mock_request.headers = {"x-original-url": "<script>alert('xss')</script>"}

        with pytest.raises(HTTPException) as exc_info:
            await _check_suspicious_headers(mock_request)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestInputSanitization:
    """Test input sanitization functionality."""

    def test_sanitize_input_normal(self):
        """Test sanitizing normal input."""
        result = sanitize_input("Hello World", max_length=100)
        assert result == "Hello World"

    def test_sanitize_input_none(self):
        """Test sanitizing None input."""
        result = sanitize_input(None)
        assert result == ""

    def test_sanitize_input_too_long(self):
        """Test sanitizing input that's too long."""
        long_input = "A" * 2000

        with pytest.raises(HTTPException) as exc_info:
            sanitize_input(long_input, max_length=100)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_sanitize_input_xss_attempt(self):
        """Test sanitizing XSS attempt."""
        xss_input = "<script>alert('xss')</script>"

        with patch('app.utils.security.logger') as mock_logger:
            with pytest.raises(HTTPException):
                sanitize_input(xss_input)
            mock_logger.warning.assert_called()

    def test_contains_suspicious_patterns_xss(self):
        """Test detection of XSS patterns."""
        xss_patterns = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "onclick=alert(1)",
            "<iframe src='evil'></iframe>"
        ]

        for pattern in xss_patterns:
            assert _contains_suspicious_patterns(pattern) is True

    def test_contains_suspicious_patterns_sql(self):
        """Test detection of SQL injection patterns."""
        sql_patterns = [
            "SELECT * FROM users",
            "UNION SELECT password",
            "DROP TABLE users",
            "' OR 1=1 --"
        ]

        for pattern in sql_patterns:
            assert _contains_suspicious_patterns(pattern) is True

    def test_contains_suspicious_patterns_clean(self):
        """Test clean input passes pattern detection."""
        clean_inputs = [
            "Hello World",
            "user@example.com",
            "Normal text input"
        ]

        for input_text in clean_inputs:
            assert _contains_suspicious_patterns(input_text) is False


class TestValidationUtils:
    """Test various validation utility functions."""

    def test_validate_token_format_valid(self):
        """Test validation of valid token format."""
        valid_tokens = [
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.hash",
            "valid-token-123",
            "ABC123.DEF456.GHI789"
        ]

        for token in valid_tokens:
            assert validate_token_format(token) is True

    def test_validate_token_format_invalid(self):
        """Test validation of invalid token format."""
        invalid_tokens = [
            "",
            "short",
            "a" * 3000,  # Too long
            "invalid token with spaces",
            "token-with-@-symbol"
        ]

        for token in invalid_tokens:
            assert validate_token_format(token) is False

    def test_validate_uuid_format_valid(self):
        """Test validation of valid UUID format."""
        valid_uuids = [
            "123e4567-e89b-12d3-a456-426614174000",
            "00000000-0000-0000-0000-000000000000",
            "ffffffff-ffff-ffff-ffff-ffffffffffff"
        ]

        for uuid_str in valid_uuids:
            assert validate_uuid_format(uuid_str) is True

    def test_validate_uuid_format_invalid(self):
        """Test validation of invalid UUID format."""
        invalid_uuids = [
            "",
            "not-a-uuid",
            "123e4567-e89b-12d3-a456",  # Too short
            "123e4567-e89b-12d3-a456-426614174000-extra",  # Too long
            "gggggggg-gggg-gggg-gggg-gggggggggggg"  # Invalid characters
        ]

        for uuid_str in invalid_uuids:
            assert validate_uuid_format(uuid_str) is False

    def test_generate_security_headers(self):
        """Test generation of security headers."""
        headers = generate_security_headers()

        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy",
            "Permissions-Policy"
        ]

        for header in expected_headers:
            assert header in headers
            assert isinstance(headers[header], str)
            assert len(headers[header]) > 0


class TestPasswordContextCreation:
    """Test password context creation and fallback mechanisms."""

    @patch('app.utils.security.CryptContext')
    def test_create_pwd_context_success(self, mock_crypt_context):
        """Test successful password context creation."""
        mock_context = Mock()
        mock_crypt_context.return_value = mock_context

        result = create_pwd_context()

        assert result == mock_context
        mock_crypt_context.assert_called_once()

    @patch('app.utils.security.CryptContext')
    def test_create_pwd_context_failure(self, mock_crypt_context):
        """Test password context creation failure."""
        mock_crypt_context.side_effect = Exception("Bcrypt not available")

        with patch('app.utils.security.logger') as mock_logger:
            result = create_pwd_context()

            assert result is None
            mock_logger.error.assert_called()

    @patch('app.utils.security.passlib.hash.bcrypt')
    def test_create_pwd_context_backend_setting(self, mock_bcrypt):
        """Test password context backend setting attempts."""
        with patch('app.utils.security.CryptContext') as mock_crypt_context, \
             patch('app.utils.security.logger') as mock_logger:

            mock_context = Mock()
            mock_crypt_context.return_value = mock_context

            # First backend setting succeeds
            result = create_pwd_context()

            assert result == mock_context
            mock_bcrypt.set_backend.assert_called_with("builtin")
            mock_logger.info.assert_called_with("Using builtin bcrypt backend")


class TestMaskSensitiveURLDuplicate:
    """Test the duplicate mask_sensitive_url function."""

    def test_mask_sensitive_url_duplicate_empty(self):
        """Test masking empty URL with duplicate function."""
        assert mask_sensitive_url_duplicate("") == "[no url]"

    def test_mask_sensitive_url_duplicate_with_password(self):
        """Test masking URL with password using duplicate function."""
        url = "https://user:secret@example.com/path?query=value"
        masked = mask_sensitive_url_duplicate(url)

        assert "secret" not in masked
        assert ":***@" in masked
        assert "query" not in masked  # Query parameters are removed

    def test_mask_sensitive_url_duplicate_invalid(self):
        """Test masking invalid URL with duplicate function."""
        invalid_url = "not a valid url"
        result = mask_sensitive_url_duplicate(invalid_url)

        assert result == "[invalid url]"