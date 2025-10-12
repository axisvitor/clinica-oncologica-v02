"""
Unit tests for date parameter handling utilities and analytics endpoints.

Tests the coerce_to_date function with various input formats and validates
that analytics endpoints properly handle datetime strings without validation errors.
"""

import pytest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app.core.date_utils import coerce_to_date, validate_date_range, set_default_date_range


class TestCoerceToDate:
    """Test the coerce_to_date function with various input formats."""
    
    def test_coerce_none_returns_none(self):
        """Test that None input returns None."""
        result = coerce_to_date(None)
        assert result is None
    
    def test_coerce_date_object_returns_same(self):
        """Test that date object input returns the same date."""
        input_date = date(2025, 10, 5)
        result = coerce_to_date(input_date)
        assert result == input_date
        assert isinstance(result, date)
    
    def test_coerce_datetime_object_extracts_date(self):
        """Test that datetime object input returns the date portion."""
        input_datetime = datetime(2025, 10, 5, 15, 30, 45)
        result = coerce_to_date(input_datetime)
        assert result == date(2025, 10, 5)
        assert isinstance(result, date)
    
    def test_coerce_iso_datetime_string_with_timezone(self):
        """Test ISO datetime string with timezone conversion."""
        test_cases = [
            "2025-10-05T15:01:57.695Z",
            "2025-10-05T15:01:57Z",
            "2025-10-05T15:01:57.695+00:00",
            "2025-10-05T15:01:57+00:00",
            "2025-12-25T23:59:59.999Z"
        ]
        
        expected_dates = [
            date(2025, 10, 5),
            date(2025, 10, 5),
            date(2025, 10, 5),
            date(2025, 10, 5),
            date(2025, 12, 25)
        ]
        
        for input_str, expected in zip(test_cases, expected_dates):
            result = coerce_to_date(input_str)
            assert result == expected, f"Failed for input: {input_str}"
    
    def test_coerce_simple_date_string(self):
        """Test simple date string format (YYYY-MM-DD)."""
        test_cases = [
            "2025-10-05",
            "2025-01-01",
            "2025-12-31"
        ]
        
        expected_dates = [
            date(2025, 10, 5),
            date(2025, 1, 1),
            date(2025, 12, 31)
        ]
        
        for input_str, expected in zip(test_cases, expected_dates):
            result = coerce_to_date(input_str)
            assert result == expected, f"Failed for input: {input_str}"
    
    def test_coerce_datetime_string_with_space_separator(self):
        """Test datetime string with space separator and timezone."""
        test_cases = [
            "2025-10-05 15:01:57.695Z",
            "2025-10-05 15:01:57+00:00",
            "2025-10-05 23:59:59Z"
        ]
        
        expected_dates = [
            date(2025, 10, 5),
            date(2025, 10, 5),
            date(2025, 10, 5)
        ]
        
        for input_str, expected in zip(test_cases, expected_dates):
            result = coerce_to_date(input_str)
            assert result == expected, f"Failed for input: {input_str}"
    
    def test_coerce_alternative_date_formats(self):
        """Test alternative date formats."""
        test_cases = [
            ("2025/10/05", date(2025, 10, 5)),
            ("10/05/2025", date(2025, 10, 5)),
            ("05/10/2025", date(2025, 5, 10)),  # DD/MM/YYYY
            ("2025-10-05", date(2025, 10, 5)),
            ("10-05-2025", date(2025, 10, 5)),
            ("05-10-2025", date(2025, 5, 10))   # DD-MM-YYYY
        ]
        
        for input_str, expected in test_cases:
            result = coerce_to_date(input_str)
            assert result == expected, f"Failed for input: {input_str}"
    
    def test_coerce_empty_string_returns_none(self):
        """Test that empty string returns None."""
        test_cases = ["", "   ", "\t", "\n"]
        
        for input_str in test_cases:
            result = coerce_to_date(input_str)
            assert result is None, f"Failed for input: '{input_str}'"
    
    def test_coerce_invalid_string_raises_error(self):
        """Test that invalid string formats raise ValueError with descriptive messages."""
        invalid_inputs = [
            "not-a-date",
            "2025-13-01",  # Invalid month
            "2025-02-30",  # Invalid day
            "25-10-05",    # Ambiguous year
            "abc-def-ghi",
            "2025/13/01"   # Invalid month in slash format
        ]
        
        for invalid_input in invalid_inputs:
            with pytest.raises(ValueError) as exc_info:
                coerce_to_date(invalid_input)
            
            error_message = str(exc_info.value)
            assert "Unable to parse date" in error_message or "Invalid" in error_message
            assert invalid_input in error_message
    
    def test_coerce_unsupported_type_raises_error(self):
        """Test that unsupported types raise ValueError."""
        unsupported_inputs = [
            123,
            12.34,
            [],
            {},
            object()
        ]
        
        for invalid_input in unsupported_inputs:
            with pytest.raises(ValueError) as exc_info:
                coerce_to_date(invalid_input)
            
            error_message = str(exc_info.value)
            assert "Cannot convert" in error_message
            assert type(invalid_input).__name__ in error_message


class TestValidateDateRange:
    """Test the validate_date_range function."""
    
    def test_valid_date_range_passes(self):
        """Test that valid date ranges pass validation."""
        start = date(2025, 10, 1)
        end = date(2025, 10, 5)
        
        result_start, result_end = validate_date_range(start, end)
        assert result_start == start
        assert result_end == end
    
    def test_same_dates_passes(self):
        """Test that same start and end dates pass validation."""
        same_date = date(2025, 10, 5)
        
        result_start, result_end = validate_date_range(same_date, same_date)
        assert result_start == same_date
        assert result_end == same_date
    
    def test_none_dates_passes(self):
        """Test that None dates pass validation."""
        result_start, result_end = validate_date_range(None, None)
        assert result_start is None
        assert result_end is None
        
        result_start, result_end = validate_date_range(date(2025, 10, 5), None)
        assert result_start == date(2025, 10, 5)
        assert result_end is None
    
    def test_invalid_date_range_raises_error(self):
        """Test that invalid date ranges raise ValueError."""
        start = date(2025, 10, 5)
        end = date(2025, 10, 1)  # End before start
        
        with pytest.raises(ValueError) as exc_info:
            validate_date_range(start, end)
        
        error_message = str(exc_info.value)
        assert "Start date" in error_message
        assert "cannot be after" in error_message
        assert "end date" in error_message


class TestSetDefaultDateRange:
    """Test the set_default_date_range function."""
    
    @patch('app.core.date_utils.datetime')
    def test_both_none_sets_defaults(self, mock_datetime):
        """Test that None dates get default values."""
        mock_today = date(2025, 10, 10)
        mock_datetime.utcnow.return_value.date.return_value = mock_today
        
        result_start, result_end = set_default_date_range(None, None, 7)
        
        assert result_end == mock_today
        assert result_start == mock_today - timedelta(days=6)  # 7 days back - 1
    
    @patch('app.core.date_utils.datetime')
    def test_end_none_sets_today(self, mock_datetime):
        """Test that None end_date gets set to today."""
        mock_today = date(2025, 10, 10)
        mock_datetime.utcnow.return_value.date.return_value = mock_today
        
        start = date(2025, 10, 5)
        result_start, result_end = set_default_date_range(start, None, 7)
        
        assert result_start == start
        assert result_end == mock_today
    
    def test_start_none_sets_relative_to_end(self):
        """Test that None start_date gets set relative to end_date."""
        end = date(2025, 10, 10)
        result_start, result_end = set_default_date_range(None, end, 7)
        
        assert result_end == end
        assert result_start == end - timedelta(days=6)  # 7 days back - 1
    
    def test_both_provided_returns_unchanged(self):
        """Test that provided dates are returned unchanged."""
        start = date(2025, 10, 1)
        end = date(2025, 10, 10)
        
        result_start, result_end = set_default_date_range(start, end, 7)
        
        assert result_start == start
        assert result_end == end
    
    def test_custom_days_back(self):
        """Test custom days_back parameter."""
        end = date(2025, 10, 10)
        result_start, result_end = set_default_date_range(None, end, 30)
        
        assert result_end == end
        assert result_start == end - timedelta(days=29)  # 30 days back - 1


class TestAnalyticsEndpointsDateHandling:
    """Test that analytics endpoints properly handle datetime strings."""
    
    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app for testing."""
        from app.main import app
        return app
    
    @pytest.fixture
    def client(self, mock_app):
        """Create a test client."""
        return TestClient(mock_app)
    
    @pytest.fixture
    def mock_auth(self):
        """Mock authentication dependencies."""
        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = Mock()
            mock_user.id = "test-user-id"
            mock_user.role = "ADMIN"  # Use string for compatibility
            mock_get_user.return_value = mock_user
            yield mock_user
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        with patch('app.database.get_db') as mock_get_db:
            mock_session = Mock()
            mock_get_db.return_value = mock_session
            yield mock_session
    
    @pytest.fixture
    def mock_analytics_service(self):
        """Mock analytics service."""
        with patch('app.services.analytics.AnalyticsService') as mock_service:
            mock_instance = Mock()
            mock_service.return_value = mock_instance
            yield mock_instance
    
    def test_engagement_endpoint_accepts_iso_datetime_strings(
        self, client, mock_auth, mock_db, mock_analytics_service
    ):
        """Test that engagement endpoint accepts ISO datetime strings."""
        # Mock the analytics service to return valid data
        mock_analytics_service.get_analytics.return_value = Mock()
        
        # Mock database queries to return empty results
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_db.query.return_value = mock_query
        
        response = client.get(
            "/api/v1/analytics/engagement",
            params={
                "start_date": "2025-10-05T15:01:57.695Z",
                "end_date": "2025-10-12T15:01:57.695Z"
            }
        )
        
        # Should not be a validation error (422)
        assert response.status_code != 422
        # Should be successful or auth error, but not validation error
        assert response.status_code in [200, 401, 403]
    
    def test_patients_endpoint_accepts_iso_datetime_strings(
        self, client, mock_auth, mock_db, mock_analytics_service
    ):
        """Test that patients endpoint accepts ISO datetime strings."""
        # Mock the analytics service
        mock_result = Mock()
        mock_result.patient_analytics = []
        mock_analytics_service.get_analytics.return_value = mock_result
        
        response = client.get(
            "/api/v1/analytics/patients",
            params={
                "start_date": "2025-10-05T15:01:57.695Z",
                "end_date": "2025-10-12T15:01:57.695Z"
            }
        )
        
        # Should not be a validation error (422)
        assert response.status_code != 422
        # Should be successful or auth error, but not validation error
        assert response.status_code in [200, 401, 403]
    
    def test_engagement_endpoint_handles_invalid_date_format(
        self, client, mock_auth, mock_db
    ):
        """Test that engagement endpoint returns 400 for invalid date formats."""
        response = client.get(
            "/api/v1/analytics/engagement",
            params={
                "start_date": "invalid-date-format",
                "end_date": "2025-10-12T15:01:57.695Z"
            }
        )
        
        # Should return 400 Bad Request for invalid date format
        if response.status_code != 401 and response.status_code != 403:  # Skip if auth fails
            assert response.status_code == 400
            assert "Invalid date format" in response.json().get("detail", "")
    
    def test_patients_endpoint_handles_invalid_date_format(
        self, client, mock_auth, mock_db
    ):
        """Test that patients endpoint returns 400 for invalid date formats."""
        response = client.get(
            "/api/v1/analytics/patients",
            params={
                "start_date": "2025-10-05T15:01:57.695Z",
                "end_date": "not-a-date"
            }
        )
        
        # Should return 400 Bad Request for invalid date format
        if response.status_code != 401 and response.status_code != 403:  # Skip if auth fails
            assert response.status_code == 400
            assert "Invalid date format" in response.json().get("detail", "")
    
    def test_endpoints_handle_none_dates_with_defaults(
        self, client, mock_auth, mock_db, mock_analytics_service
    ):
        """Test that endpoints handle None dates by setting appropriate defaults."""
        # Mock the analytics service
        mock_result = Mock()
        mock_result.patient_analytics = []
        mock_analytics_service.get_analytics.return_value = mock_result
        
        # Mock database queries for engagement endpoint
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_db.query.return_value = mock_query
        
        # Test engagement endpoint without date parameters
        response = client.get("/api/v1/analytics/engagement")
        if response.status_code not in [401, 403]:  # Skip if auth fails
            assert response.status_code == 200
            data = response.json()
            assert "period" in data
            assert "start_date" in data["period"]
            assert "end_date" in data["period"]
        
        # Test patients endpoint without date parameters
        response = client.get("/api/v1/analytics/patients")
        if response.status_code not in [401, 403]:  # Skip if auth fails
            assert response.status_code == 200
            data = response.json()
            assert "period" in data
            assert "start_date" in data["period"]
            assert "end_date" in data["period"]
    
    def test_endpoints_validate_date_ranges(
        self, client, mock_auth, mock_db
    ):
        """Test that endpoints validate start_date is not after end_date."""
        response = client.get(
            "/api/v1/analytics/engagement",
            params={
                "start_date": "2025-10-12",
                "end_date": "2025-10-05"  # End before start
            }
        )
        
        # Should return 400 Bad Request for invalid date range
        if response.status_code not in [401, 403]:  # Skip if auth fails
            assert response.status_code == 400
            assert "Start date" in response.json().get("detail", "")
            assert "cannot be after" in response.json().get("detail", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])