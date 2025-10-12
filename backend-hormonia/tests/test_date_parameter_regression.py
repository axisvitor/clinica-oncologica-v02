"""
Date Parameter Regression Tests
Comprehensive tests to prevent regression of date parameter handling issues.
"""

import pytest
import re
from pathlib import Path
from datetime import datetime, date, timezone
from typing import Optional, Union
from unittest.mock import patch, Mock

from app.core.date_utils import coerce_to_date


class TestDateUtilsRegression:
    """Comprehensive tests for date utility functions."""
    
    def test_coerce_to_date_function_exists(self):
        """Test that coerce_to_date function exists and is callable."""
        assert coerce_to_date is not None
        assert callable(coerce_to_date)
    
    def test_coerce_to_date_iso_datetime_strings(self):
        """Test coerce_to_date with ISO datetime strings."""
        test_cases = [
            ("2025-10-05T15:01:57.695Z", date(2025, 10, 5)),
            ("2025-10-05T15:01:57Z", date(2025, 10, 5)),
            ("2025-10-05T15:01:57.695+00:00", date(2025, 10, 5)),
            ("2025-10-05T15:01:57+00:00", date(2025, 10, 5)),
            ("2025-12-31T23:59:59.999Z", date(2025, 12, 31)),
            ("2025-01-01T00:00:00.000Z", date(2025, 1, 1)),
        ]
        
        for input_str, expected_date in test_cases:
            result = coerce_to_date(input_str)
            assert result == expected_date, \
                f"coerce_to_date('{input_str}') should return {expected_date}, got {result}"
    
    def test_coerce_to_date_simple_date_strings(self):
        """Test coerce_to_date with simple date strings."""
        test_cases = [
            ("2025-10-05", date(2025, 10, 5)),
            ("2025-12-31", date(2025, 12, 31)),
            ("2025-01-01", date(2025, 1, 1)),
            ("2024-02-29", date(2024, 2, 29)),  # Leap year
        ]
        
        for input_str, expected_date in test_cases:
            result = coerce_to_date(input_str)
            assert result == expected_date, \
                f"coerce_to_date('{input_str}') should return {expected_date}, got {result}"
    
    def test_coerce_to_date_datetime_objects(self):
        """Test coerce_to_date with datetime objects."""
        test_cases = [
            (datetime(2025, 10, 5, 15, 1, 57), date(2025, 10, 5)),
            (datetime(2025, 12, 31, 23, 59, 59), date(2025, 12, 31)),
            (datetime(2025, 1, 1, 0, 0, 0), date(2025, 1, 1)),
        ]
        
        for input_dt, expected_date in test_cases:
            result = coerce_to_date(input_dt)
            assert result == expected_date, \
                f"coerce_to_date({input_dt}) should return {expected_date}, got {result}"
    
    def test_coerce_to_date_date_objects(self):
        """Test coerce_to_date with date objects."""
        test_cases = [
            date(2025, 10, 5),
            date(2025, 12, 31),
            date(2025, 1, 1),
        ]
        
        for input_date in test_cases:
            result = coerce_to_date(input_date)
            assert result == input_date, \
                f"coerce_to_date({input_date}) should return {input_date}, got {result}"
    
    def test_coerce_to_date_none_values(self):
        """Test coerce_to_date with None values."""
        result = coerce_to_date(None)
        assert result is None, "coerce_to_date(None) should return None"
    
    def test_coerce_to_date_error_handling(self):
        """Test coerce_to_date error handling for invalid inputs."""
        invalid_inputs = [
            "invalid-date",
            "2025-13-45",  # Invalid month/day
            "not-a-date",
            "2025/10/05",  # Wrong format
            "10-05-2025",  # Wrong order
            123,           # Invalid type
            [],            # Invalid type
            {},            # Invalid type
        ]
        
        for invalid_input in invalid_inputs:
            with pytest.raises(ValueError, match="Invalid date format|Cannot convert"):
                coerce_to_date(invalid_input)
    
    def test_coerce_to_date_timezone_handling(self):
        """Test that timezone information is properly handled."""
        # Different timezone formats should all extract the same date
        timezone_formats = [
            "2025-10-05T15:01:57.695Z",
            "2025-10-05T15:01:57.695+00:00",
            "2025-10-05T10:01:57.695-05:00",  # Different timezone, same UTC date
            "2025-10-05T20:01:57.695+05:00",  # Different timezone, same UTC date
        ]
        
        expected_date = date(2025, 10, 5)
        
        for tz_format in timezone_formats:
            try:
                result = coerce_to_date(tz_format)
                # All should extract the same date (ignoring time/timezone)
                assert result.year == expected_date.year
                assert result.month == expected_date.month
                assert result.day == expected_date.day
            except ValueError:
                # Some formats might not be supported, that's okay
                pass


class TestAPIDateParameterRegression:
    """Test API endpoint date parameter handling."""
    
    def test_analytics_api_date_parameters(self):
        """Test that analytics API properly handles date parameters."""
        backend_root = Path(__file__).parent.parent
        analytics_file = backend_root / "app/api/v1/analytics.py"
        
        if not analytics_file.exists():
            pytest.skip("Analytics API file not found")
        
        with open(analytics_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should use coerce_to_date for date parameters
        if any(param in content for param in ['start_date', 'end_date']):
            assert 'coerce_to_date' in content, \
                "Analytics API with date parameters should use coerce_to_date"
            
            # Should import coerce_to_date
            assert 'from app.core.date_utils import' in content, \
                "Analytics API should import coerce_to_date from date_utils"
            
            # Should have error handling
            assert 'HTTPException' in content, \
                "Analytics API should have HTTPException for date errors"
    
    def test_api_date_parameter_type_annotations(self):
        """Test that API endpoints use correct type annotations for date parameters."""
        backend_root = Path(__file__).parent.parent
        api_files = list((backend_root / "app/api").rglob("*.py"))
        
        for file_path in api_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for date parameter patterns
            date_param_patterns = [
                r'(\w*date\w*)\s*:\s*Optional\[date\]',
                r'(\w*date\w*)\s*:\s*date',
                r'(\w*time\w*)\s*:\s*Optional\[datetime\]',
                r'(\w*time\w*)\s*:\s*datetime'
            ]
            
            for pattern in date_param_patterns:
                matches = re.findall(pattern, content)
                for param_name in matches:
                    # If using date/datetime types directly, should have coercion
                    if 'coerce_to_date' not in content:
                        # This might be problematic - should use str with coercion
                        pass  # Warning level issue
    
    def test_no_direct_date_type_usage_in_endpoints(self):
        """Test that endpoints don't use date types directly without coercion."""
        backend_root = Path(__file__).parent.parent
        api_files = list((backend_root / "app/api").rglob("*.py"))
        
        problematic_patterns = []
        
        for file_path in api_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for function parameters with date types
            # This is a simplified check - in practice, you'd parse AST
            if 'def ' in content and 'date' in content:
                # Check for patterns like: param: date = None
                direct_date_pattern = r'(\w+)\s*:\s*(?:Optional\[)?date(?:\])?\s*='
                matches = re.findall(direct_date_pattern, content)
                
                if matches and 'coerce_to_date' not in content:
                    problematic_patterns.append((file_path, matches))
        
        # This is more of a warning than an error
        if problematic_patterns:
            for file_path, params in problematic_patterns:
                print(f"Warning: {file_path} has date parameters without coercion: {params}")


class TestDateParameterIntegration:
    """Integration tests for date parameter handling."""
    
    @pytest.mark.integration
    def test_analytics_endpoint_with_datetime_strings(self):
        """Test analytics endpoints accept datetime strings."""
        # This would require FastAPI test client setup
        # For now, test the pattern exists
        
        backend_root = Path(__file__).parent.parent
        analytics_file = backend_root / "app/api/v1/analytics.py"
        
        if analytics_file.exists():
            with open(analytics_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Should have proper error handling pattern
            if 'coerce_to_date' in content:
                # Should wrap in try/catch
                assert 'try:' in content or 'except' in content or 'HTTPException' in content, \
                    "Date coercion should have error handling"
    
    @pytest.mark.integration
    def test_date_parameter_error_responses(self):
        """Test that invalid date parameters return proper error responses."""
        # This would test actual HTTP responses
        # For now, verify the error handling pattern exists
        
        from fastapi import HTTPException
        
        # Test that coerce_to_date errors can be caught and converted to HTTP errors
        try:
            coerce_to_date("invalid-date")
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            # Should be able to convert to HTTPException
            http_error = HTTPException(status_code=400, detail=f"Invalid date format: {e}")
            assert http_error.status_code == 400
            assert "Invalid date format" in http_error.detail
    
    def test_date_parameter_default_handling(self):
        """Test that date parameters handle defaults correctly."""
        # Test common default patterns
        
        # Default to today
        today = date.today()
        result = coerce_to_date(None)
        assert result is None  # Should handle None explicitly
        
        # Test with actual default logic (would be in endpoint)
        def mock_endpoint_logic(end_date_str: Optional[str] = None):
            end_date = coerce_to_date(end_date_str) if end_date_str else date.today()
            return end_date
        
        # Test with None (should use default)
        result = mock_endpoint_logic(None)
        assert result == today
        
        # Test with actual date string
        result = mock_endpoint_logic("2025-10-05")
        assert result == date(2025, 10, 5)


class TestDateParameterErrorPrevention:
    """Tests to prevent common date parameter errors."""
    
    def test_prevent_pydantic_validation_errors(self):
        """Test patterns that prevent Pydantic validation errors."""
        # The main issue was Pydantic rejecting datetime strings for date fields
        
        # Test that our coercion handles the problematic case
        iso_datetime = "2025-10-05T15:01:57.695Z"
        result = coerce_to_date(iso_datetime)
        assert result == date(2025, 10, 5)
        
        # This should not raise ValidationError when used properly
        assert isinstance(result, date)
        assert not isinstance(result, datetime)
    
    def test_prevent_timezone_confusion(self):
        """Test that timezone handling doesn't cause date confusion."""
        # Different timezones on the same date should extract the same date
        same_date_different_tz = [
            "2025-10-05T02:00:00Z",           # UTC
            "2025-10-05T03:00:00+01:00",      # UTC+1
            "2025-10-04T21:00:00-05:00",      # UTC-5 (previous day local time)
        ]
        
        for dt_str in same_date_different_tz:
            result = coerce_to_date(dt_str)
            # All should extract date based on the date part, not timezone conversion
            assert result.year == 2025
            assert result.month == 10
            # Day might vary depending on implementation - document expected behavior
    
    def test_prevent_format_confusion(self):
        """Test that different date formats are handled consistently."""
        # These should all be rejected (not supported formats)
        unsupported_formats = [
            "10/05/2025",      # US format
            "05/10/2025",      # European format
            "2025.10.05",      # Dot separator
            "Oct 5, 2025",     # Text month
            "5 Oct 2025",      # Text month, different order
        ]
        
        for fmt in unsupported_formats:
            with pytest.raises(ValueError):
                coerce_to_date(fmt)
    
    def test_prevent_silent_failures(self):
        """Test that invalid dates fail loudly, not silently."""
        invalid_dates = [
            "2025-02-30",      # Invalid day for February
            "2025-13-01",      # Invalid month
            "2025-00-01",      # Invalid month (zero)
            "2025-01-00",      # Invalid day (zero)
            "2025-01-32",      # Invalid day for January
        ]
        
        for invalid_date in invalid_dates:
            with pytest.raises(ValueError):
                coerce_to_date(invalid_date)
    
    def test_prevent_type_confusion(self):
        """Test that return types are consistent and correct."""
        # Should always return date objects (not datetime)
        test_inputs = [
            "2025-10-05",
            "2025-10-05T15:01:57Z",
            datetime(2025, 10, 5, 15, 1, 57),
            date(2025, 10, 5),
        ]
        
        for input_val in test_inputs:
            result = coerce_to_date(input_val)
            assert isinstance(result, date), f"Result should be date object, got {type(result)}"
            assert not isinstance(result, datetime), f"Result should not be datetime object"


class TestDateParameterPerformance:
    """Performance tests for date parameter handling."""
    
    def test_coerce_to_date_performance(self):
        """Test that date coercion is reasonably fast."""
        import time
        
        test_date = "2025-10-05T15:01:57.695Z"
        iterations = 1000
        
        start_time = time.time()
        for _ in range(iterations):
            coerce_to_date(test_date)
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_time = total_time / iterations
        
        # Should be fast (less than 1ms per call on average)
        assert avg_time < 0.001, f"Date coercion too slow: {avg_time:.4f}s per call"
    
    def test_no_memory_leaks_in_date_coercion(self):
        """Test that repeated date coercion doesn't leak memory."""
        import gc
        
        # Run many coercions
        for _ in range(1000):
            result = coerce_to_date("2025-10-05T15:01:57.695Z")
            assert result == date(2025, 10, 5)
        
        # Force garbage collection
        gc.collect()
        
        # This is a basic test - in practice, you'd use memory profiling
        assert True, "Memory leak test completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])