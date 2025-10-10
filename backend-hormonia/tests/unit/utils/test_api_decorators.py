"""
Comprehensive unit tests for app.utils.api_decorators module.
Tests API decorators for exception handling, validation, permissions, logging, and caching.
"""
import pytest
import json
import hashlib
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import HTTPException, status

from app.utils.api_decorators import (
    handle_service_exceptions,
    validate_pagination,
    require_permissions,
    log_api_call,
    cache_response,
    get_redis_client
)
from app.exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
    AuthenticationError,
    AuthorizationError,
    ExternalServiceError,
    DatabaseError
)


class TestGetRedisClient:
    """Test the get_redis_client function."""

    @pytest.mark.asyncio
    async def test_get_redis_client_success(self):
        """Test successful Redis client creation."""
        with patch('redis.asyncio.from_url') as mock_from_url, \
             patch('app.utils.api_decorators.settings') as mock_settings:

            mock_settings.REDIS_URL = "redis://localhost:6379"
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_from_url.return_value = mock_client

            result = await get_redis_client()

            assert result == mock_client
            mock_from_url.assert_called_once_with("redis://localhost:6379")
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_redis_client_connection_failure(self):
        """Test Redis client creation failure."""
        with patch('redis.asyncio.from_url') as mock_from_url, \
             patch('app.utils.api_decorators.settings') as mock_settings:

            mock_settings.REDIS_URL = "redis://localhost:6379"
            mock_client = AsyncMock()
            mock_client.ping.side_effect = Exception("Connection failed")
            mock_from_url.return_value = mock_client

            result = await get_redis_client()

            assert result is None

    @pytest.mark.asyncio
    async def test_get_redis_client_cached(self):
        """Test Redis client caching."""
        with patch('redis.asyncio.from_url') as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock()
            mock_from_url.return_value = mock_client

            # Set global client to simulate cached state
            import app.utils.api_decorators
            app.utils.api_decorators.redis_client = mock_client

            result = await get_redis_client()

            assert result == mock_client
            # Should not create new client
            mock_from_url.assert_not_called()

            # Reset for other tests
            app.utils.api_decorators.redis_client = None


class TestHandleServiceExceptions:
    """Test the handle_service_exceptions decorator."""

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_success(self):
        """Test decorator with successful function execution."""
        @handle_service_exceptions
        async def successful_func():
            return {"success": True}

        result = await successful_func()
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_not_found_error(self):
        """Test decorator with NotFoundError."""
        @handle_service_exceptions
        async def not_found_func():
            raise NotFoundError("Resource not found", {"resource_id": "123"})

        with pytest.raises(HTTPException) as exc_info:
            await not_found_func()

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail["error"] == "resource_not_found"
        assert exc_info.value.detail["message"] == "Resource not found"
        assert exc_info.value.detail["details"] == {"resource_id": "123"}

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_validation_error(self):
        """Test decorator with ValidationError."""
        @handle_service_exceptions
        async def validation_func():
            raise ValidationError("Invalid input", {"field": "email"})

        with pytest.raises(HTTPException) as exc_info:
            await validation_func()

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert exc_info.value.detail["error"] == "validation_error"
        assert exc_info.value.detail["message"] == "Invalid input"
        assert exc_info.value.detail["details"] == {"field": "email"}

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_conflict_error(self):
        """Test decorator with ConflictError."""
        @handle_service_exceptions
        async def conflict_func():
            raise ConflictError("Resource already exists", {"duplicate_field": "email"})

        with pytest.raises(HTTPException) as exc_info:
            await conflict_func()

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail["error"] == "conflict_error"
        assert exc_info.value.detail["message"] == "Resource already exists"

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_authentication_error(self):
        """Test decorator with AuthenticationError."""
        @handle_service_exceptions
        async def auth_func():
            raise AuthenticationError("Invalid credentials")

        with pytest.raises(HTTPException) as exc_info:
            await auth_func()

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail["error"] == "authentication_error"
        assert exc_info.value.detail["message"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_authorization_error(self):
        """Test decorator with AuthorizationError."""
        @handle_service_exceptions
        async def authz_func():
            raise AuthorizationError("Insufficient permissions")

        with pytest.raises(HTTPException) as exc_info:
            await authz_func()

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail["error"] == "authorization_error"
        assert exc_info.value.detail["message"] == "Insufficient permissions"

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_external_service_error(self):
        """Test decorator with ExternalServiceError."""
        @handle_service_exceptions
        async def external_func():
            raise ExternalServiceError("Service unavailable")

        with pytest.raises(HTTPException) as exc_info:
            await external_func()

        assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
        assert exc_info.value.detail["error"] == "external_service_error"
        assert "temporarily unavailable" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_database_error(self):
        """Test decorator with DatabaseError."""
        @handle_service_exceptions
        async def db_func():
            raise DatabaseError("Connection timeout")

        with pytest.raises(HTTPException) as exc_info:
            await db_func()

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc_info.value.detail["error"] == "database_error"
        assert "Database operation failed" in exc_info.value.detail["message"]
        # Should not expose internal database errors
        assert exc_info.value.detail["details"] == {}

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_unexpected_error(self):
        """Test decorator with unexpected exception."""
        @handle_service_exceptions
        async def unexpected_func():
            raise RuntimeError("Unexpected error")

        with pytest.raises(HTTPException) as exc_info:
            await unexpected_func()

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc_info.value.detail["error"] == "internal_server_error"
        assert "unexpected error occurred" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""
        @handle_service_exceptions
        async def documented_func():
            """This function has documentation."""
            return "result"

        assert documented_func.__name__ == "documented_func"
        assert "This function has documentation" in documented_func.__doc__

    @pytest.mark.asyncio
    async def test_handle_service_exceptions_with_args_kwargs(self):
        """Test decorator with function arguments."""
        @handle_service_exceptions
        async def func_with_args(x, y, multiplier=1):
            return (x + y) * multiplier

        result = await func_with_args(5, 3, multiplier=2)
        assert result == 16


class TestValidatePagination:
    """Test the validate_pagination decorator."""

    @pytest.mark.asyncio
    async def test_validate_pagination_success(self):
        """Test decorator with valid pagination parameters."""
        @validate_pagination(max_limit=100)
        async def paginated_func(skip=0, limit=10):
            return {"skip": skip, "limit": limit}

        result = await paginated_func(skip=5, limit=20)
        assert result == {"skip": 5, "limit": 20}

    @pytest.mark.asyncio
    async def test_validate_pagination_negative_skip(self):
        """Test decorator with negative skip parameter."""
        @validate_pagination()
        async def paginated_func(skip=0, limit=10):
            return {"skip": skip, "limit": limit}

        with pytest.raises(HTTPException) as exc_info:
            await paginated_func(skip=-1, limit=10)

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Skip parameter must be non-negative" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_validate_pagination_zero_limit(self):
        """Test decorator with zero limit parameter."""
        @validate_pagination()
        async def paginated_func(skip=0, limit=10):
            return {"skip": skip, "limit": limit}

        with pytest.raises(HTTPException) as exc_info:
            await paginated_func(skip=0, limit=0)

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Limit must be between 1 and" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_validate_pagination_exceeds_max_limit(self):
        """Test decorator with limit exceeding maximum."""
        @validate_pagination(max_limit=50)
        async def paginated_func(skip=0, limit=10):
            return {"skip": skip, "limit": limit}

        with pytest.raises(HTTPException) as exc_info:
            await paginated_func(skip=0, limit=100)

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Limit must be between 1 and 50" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_validate_pagination_default_values(self):
        """Test decorator with default pagination values."""
        @validate_pagination()
        async def paginated_func(skip=0, limit=100):
            return {"skip": skip, "limit": limit}

        result = await paginated_func()
        assert result == {"skip": 0, "limit": 100}

    @pytest.mark.asyncio
    async def test_validate_pagination_custom_max_limit(self):
        """Test decorator with custom max limit."""
        @validate_pagination(max_limit=500)
        async def paginated_func(skip=0, limit=10):
            return {"skip": skip, "limit": limit}

        result = await paginated_func(skip=10, limit=300)
        assert result == {"skip": 10, "limit": 300}

    @pytest.mark.asyncio
    async def test_validate_pagination_preserves_other_kwargs(self):
        """Test decorator preserves other function arguments."""
        @validate_pagination()
        async def func_with_other_args(skip=0, limit=10, search=None):
            return {"skip": skip, "limit": limit, "search": search}

        result = await func_with_other_args(skip=5, limit=15, search="test")
        assert result == {"skip": 5, "limit": 15, "search": "test"}


class TestRequirePermissions:
    """Test the require_permissions decorator."""

    @pytest.mark.asyncio
    async def test_require_permissions_success(self):
        """Test decorator with user having required permissions."""
        @require_permissions("read:patients", "write:patients")
        async def protected_func(current_user=None):
            return {"user_id": current_user.id}

        mock_user = Mock()
        mock_user.id = "user123"
        mock_user.role = "doctor"
        mock_user.permissions = ["read:patients", "write:patients", "read:treatments"]

        result = await protected_func(current_user=mock_user)
        assert result == {"user_id": "user123"}

    @pytest.mark.asyncio
    async def test_require_permissions_no_user(self):
        """Test decorator without current_user."""
        @require_permissions("read:patients")
        async def protected_func(current_user=None):
            return {"success": True}

        with pytest.raises(HTTPException) as exc_info:
            await protected_func()

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "authentication_required" in exc_info.value.detail["error"]

    @pytest.mark.asyncio
    async def test_require_permissions_missing_permission(self):
        """Test decorator with user missing required permission."""
        @require_permissions("write:admin", "delete:patients")
        async def protected_func(current_user=None):
            return {"success": True}

        mock_user = Mock()
        mock_user.role = "doctor"
        mock_user.permissions = ["read:patients", "write:patients"]

        with pytest.raises(HTTPException) as exc_info:
            await protected_func(current_user=mock_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "insufficient_permissions" in exc_info.value.detail["error"]
        assert "write:admin" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_require_permissions_admin_bypass(self):
        """Test decorator with admin user bypassing permission checks."""
        @require_permissions("super:secret", "admin:all")
        async def protected_func(current_user=None):
            return {"admin_access": True}

        mock_user = Mock()
        mock_user.role = "admin"
        mock_user.permissions = ["read:patients"]  # Limited permissions

        result = await protected_func(current_user=mock_user)
        assert result == {"admin_access": True}

    @pytest.mark.asyncio
    async def test_require_permissions_single_permission(self):
        """Test decorator with single permission requirement."""
        @require_permissions("read:patients")
        async def protected_func(current_user=None):
            return {"data": "patient_data"}

        mock_user = Mock()
        mock_user.role = "nurse"
        mock_user.permissions = ["read:patients"]

        result = await protected_func(current_user=mock_user)
        assert result == {"data": "patient_data"}

    @pytest.mark.asyncio
    async def test_require_permissions_no_permissions_attribute(self):
        """Test decorator with user having no permissions attribute."""
        @require_permissions("read:patients")
        async def protected_func(current_user=None):
            return {"success": True}

        mock_user = Mock()
        mock_user.role = "user"
        # No permissions attribute

        with pytest.raises(HTTPException) as exc_info:
            await protected_func(current_user=mock_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_require_permissions_with_other_args(self):
        """Test decorator with additional function arguments."""
        @require_permissions("read:patients")
        async def func_with_args(patient_id, current_user=None, include_history=False):
            return {
                "patient_id": patient_id,
                "user_id": current_user.id,
                "include_history": include_history
            }

        mock_user = Mock()
        mock_user.id = "user123"
        mock_user.role = "doctor"
        mock_user.permissions = ["read:patients"]

        result = await func_with_args("patient123", current_user=mock_user, include_history=True)
        assert result["patient_id"] == "patient123"
        assert result["user_id"] == "user123"
        assert result["include_history"] is True


class TestLogApiCall:
    """Test the log_api_call decorator."""

    @pytest.mark.asyncio
    async def test_log_api_call_success(self):
        """Test decorator logs successful API calls."""
        with patch('app.utils.api_decorators.logger') as mock_logger:
            @log_api_call()
            async def api_func(param1, param2=None):
                return {"result": "success", "param1": param1, "param2": param2}

            result = await api_func("value1", param2="value2")

            assert result == {"result": "success", "param1": "value1", "param2": "value2"}
            # Check that info logs were called
            assert mock_logger.info.call_count == 2
            mock_logger.info.assert_any_call("API call: api_func with args: ('value1',), kwargs: {'param2': 'value2'}")
            mock_logger.info.assert_any_call("API call api_func completed successfully")

    @pytest.mark.asyncio
    async def test_log_api_call_with_response(self):
        """Test decorator logs API calls including response."""
        with patch('app.utils.api_decorators.logger') as mock_logger:
            @log_api_call(include_response=True)
            async def api_func():
                return {"data": "response_data"}

            result = await api_func()

            assert result == {"data": "response_data"}
            mock_logger.info.assert_any_call("API response for api_func: {'data': 'response_data'}")

    @pytest.mark.asyncio
    async def test_log_api_call_exception(self):
        """Test decorator logs API call failures."""
        with patch('app.utils.api_decorators.logger') as mock_logger:
            @log_api_call()
            async def failing_api_func():
                raise ValueError("API error")

            with pytest.raises(ValueError):
                await failing_api_func()

            mock_logger.error.assert_called_with("API call failing_api_func failed: API error")

    @pytest.mark.asyncio
    async def test_log_api_call_preserves_metadata(self):
        """Test decorator preserves function metadata."""
        @log_api_call()
        async def documented_api_func():
            """API function with documentation."""
            return "result"

        assert documented_api_func.__name__ == "documented_api_func"
        assert "API function with documentation" in documented_api_func.__doc__

    @pytest.mark.asyncio
    async def test_log_api_call_no_args(self):
        """Test decorator with function that takes no arguments."""
        with patch('app.utils.api_decorators.logger') as mock_logger:
            @log_api_call()
            async def no_args_func():
                return {"success": True}

            result = await no_args_func()

            assert result == {"success": True}
            mock_logger.info.assert_any_call("API call: no_args_func with args: (), kwargs: {}")


class TestCacheResponse:
    """Test the cache_response decorator."""

    @pytest.mark.asyncio
    async def test_cache_response_miss_and_store(self):
        """Test cache miss and storing response."""
        mock_client = AsyncMock()
        mock_client.get.return_value = None  # Cache miss
        mock_client.setex = AsyncMock()

        with patch('app.utils.api_decorators.get_redis_client', return_value=mock_client):
            @cache_response(ttl_seconds=600)
            async def cached_func(param1):
                return {"data": f"result_{param1}"}

            result = await cached_func("test")

            assert result == {"data": "result_test"}
            # Should store in cache
            mock_client.setex.assert_called_once()
            call_args = mock_client.setex.call_args
            assert call_args[0][1] == 600  # TTL
            assert '"data": "result_test"' in call_args[0][2]  # JSON response

    @pytest.mark.asyncio
    async def test_cache_response_hit(self):
        """Test cache hit returning cached response."""
        cached_data = '{"data": "cached_result"}'
        mock_client = AsyncMock()
        mock_client.get.return_value = cached_data

        with patch('app.utils.api_decorators.get_redis_client', return_value=mock_client):
            @cache_response()
            async def cached_func():
                return {"data": "fresh_result"}  # Should not be called

            result = await cached_func()

            assert result == {"data": "cached_result"}
            # Should not store since we got cache hit
            mock_client.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_response_no_redis(self):
        """Test cache decorator when Redis is unavailable."""
        with patch('app.utils.api_decorators.get_redis_client', return_value=None):
            @cache_response()
            async def cached_func():
                return {"data": "no_cache_result"}

            result = await cached_func()

            assert result == {"data": "no_cache_result"}

    @pytest.mark.asyncio
    async def test_cache_response_redis_error(self):
        """Test cache decorator handling Redis errors gracefully."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Redis error")
        mock_client.setex.side_effect = Exception("Redis error")

        with patch('app.utils.api_decorators.get_redis_client', return_value=mock_client), \
             patch('app.utils.api_decorators.logger') as mock_logger:

            @cache_response()
            async def cached_func():
                return {"data": "error_handling"}

            result = await cached_func()

            assert result == {"data": "error_handling"}
            # Should log warnings for Redis errors
            assert mock_logger.warning.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_response_key_generation(self):
        """Test cache key generation from function parameters."""
        mock_client = AsyncMock()
        mock_client.get.return_value = None

        with patch('app.utils.api_decorators.get_redis_client', return_value=mock_client):
            @cache_response()
            async def cached_func(param1, param2=None):
                return {"param1": param1, "param2": param2}

            await cached_func("value1", param2="value2")

            # Check that get was called with a cache key
            mock_client.get.assert_called_once()
            cache_key = mock_client.get.call_args[0][0]
            assert cache_key.startswith("cache:")
            assert len(cache_key) == 38  # "cache:" + 32-char MD5 hash

    @pytest.mark.asyncio
    async def test_cache_response_different_params_different_keys(self):
        """Test that different parameters generate different cache keys."""
        mock_client = AsyncMock()
        mock_client.get.return_value = None

        with patch('app.utils.api_decorators.get_redis_client', return_value=mock_client):
            @cache_response()
            async def cached_func(param):
                return {"param": param}

            await cached_func("value1")
            await cached_func("value2")

            # Should have been called with two different cache keys
            assert mock_client.get.call_count == 2
            call1_key = mock_client.get.call_args_list[0][0][0]
            call2_key = mock_client.get.call_args_list[1][0][0]
            assert call1_key != call2_key

    @pytest.mark.asyncio
    async def test_cache_response_custom_ttl(self):
        """Test cache decorator with custom TTL."""
        mock_client = AsyncMock()
        mock_client.get.return_value = None

        with patch('app.utils.api_decorators.get_redis_client', return_value=mock_client):
            @cache_response(ttl_seconds=1800)  # 30 minutes
            async def cached_func():
                return {"data": "custom_ttl"}

            await cached_func()

            # Check TTL was set correctly
            mock_client.setex.assert_called_once()
            call_args = mock_client.setex.call_args
            assert call_args[0][1] == 1800

    @pytest.mark.asyncio
    async def test_cache_response_complex_data_serialization(self):
        """Test cache decorator with complex data types."""
        mock_client = AsyncMock()
        mock_client.get.return_value = None

        with patch('app.utils.api_decorators.get_redis_client', return_value=mock_client):
            @cache_response()
            async def cached_func():
                return {
                    "list": [1, 2, 3],
                    "nested": {"key": "value"},
                    "null": None,
                    "bool": True
                }

            result = await cached_func()

            # Should handle complex data serialization
            assert result["list"] == [1, 2, 3]
            assert result["nested"]["key"] == "value"
            assert result["null"] is None
            assert result["bool"] is True


class TestDecoratorIntegration:
    """Test combining multiple decorators."""

    @pytest.mark.asyncio
    async def test_combined_decorators(self):
        """Test combining service exception handling with other decorators."""
        with patch('app.utils.api_decorators.logger'):
            @handle_service_exceptions
            @log_api_call()
            @validate_pagination(max_limit=50)
            async def combined_func(skip=0, limit=10):
                if limit > 25:
                    raise ValidationError("Limit too high")
                return {"skip": skip, "limit": limit}

            # Test successful execution
            result = await combined_func(skip=5, limit=20)
            assert result == {"skip": 5, "limit": 20}

            # Test validation error handling through exception decorator
            with pytest.raises(HTTPException) as exc_info:
                await combined_func(skip=0, limit=30)

            assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_permission_and_exception_decorators(self):
        """Test combining permission checking with exception handling."""
        @handle_service_exceptions
        @require_permissions("read:data")
        async def protected_func(current_user=None):
            if not hasattr(current_user, 'active') or not current_user.active:
                raise AuthenticationError("User not active")
            return {"data": "protected"}

        # Test with valid user
        mock_user = Mock()
        mock_user.role = "user"
        mock_user.permissions = ["read:data"]
        mock_user.active = True

        result = await protected_func(current_user=mock_user)
        assert result == {"data": "protected"}

        # Test with inactive user
        mock_user.active = False
        with pytest.raises(HTTPException) as exc_info:
            await protected_func(current_user=mock_user)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED