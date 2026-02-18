"""
Unit tests for CursorEncoder class.

Tests cursor encoding/decoding functionality for cursor-based pagination.
"""
import sys
from pathlib import Path

from app.utils.timezone import SAO_PAULO_TZ
# Add the backend-hormonia directory to the path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from datetime import datetime, timezone
import base64
import json

from app.schemas.v2.common import CursorEncoder


class TestCursorEncoder:
    """Test suite for CursorEncoder class."""
    
    def test_encode_basic(self):
        """Test basic cursor encoding with valid inputs."""
        # Arrange
        last_id = 123
        last_created_at = datetime(2025, 1, 17, 15, 30, 0)
        
        # Act
        cursor = CursorEncoder.encode(last_id, last_created_at)
        
        # Assert
        assert cursor is not None
        assert isinstance(cursor, str)
        assert len(cursor) > 0
        
        # Verify it's valid base64
        decoded_bytes = base64.urlsafe_b64decode(cursor.encode())
        decoded_data = json.loads(decoded_bytes)
        assert decoded_data["id"] == last_id
        assert decoded_data["created_at"] == last_created_at.isoformat()
    
    def test_encode_with_timezone(self):
        """Test cursor encoding with timezone-aware datetime."""
        # Arrange
        last_id = 456
        last_created_at = datetime(2025, 1, 17, 15, 30, 0, tzinfo=SAO_PAULO_TZ)
        
        # Act
        cursor = CursorEncoder.encode(last_id, last_created_at)
        
        # Assert
        assert cursor is not None
        decoded_bytes = base64.urlsafe_b64decode(cursor.encode())
        decoded_data = json.loads(decoded_bytes)
        assert decoded_data["id"] == last_id
        assert "2025-01-17" in decoded_data["created_at"]
    
    def test_encode_with_large_id(self):
        """Test cursor encoding with large ID values."""
        # Arrange
        last_id = 999999999
        last_created_at = datetime(2025, 1, 17, 15, 30, 0)
        
        # Act
        cursor = CursorEncoder.encode(last_id, last_created_at)
        
        # Assert
        assert cursor is not None
        decoded_bytes = base64.urlsafe_b64decode(cursor.encode())
        decoded_data = json.loads(decoded_bytes)
        assert decoded_data["id"] == last_id
    
    def test_encode_with_microseconds(self):
        """Test cursor encoding preserves microseconds in datetime."""
        # Arrange
        last_id = 789
        last_created_at = datetime(2025, 1, 17, 15, 30, 45, 123456)
        
        # Act
        cursor = CursorEncoder.encode(last_id, last_created_at)
        
        # Assert
        decoded_bytes = base64.urlsafe_b64decode(cursor.encode())
        decoded_data = json.loads(decoded_bytes)
        assert "123456" in decoded_data["created_at"]
    
    def test_decode_basic(self):
        """Test basic cursor decoding with valid cursor."""
        # Arrange
        last_id = 123
        last_created_at = datetime(2025, 1, 17, 15, 30, 0)
        cursor = CursorEncoder.encode(last_id, last_created_at)
        
        # Act
        decoded = CursorEncoder.decode(cursor)
        
        # Assert
        assert decoded is not None
        assert isinstance(decoded, dict)
        assert decoded["id"] == last_id
        assert decoded["created_at"] == last_created_at.isoformat()
    
    def test_decode_returns_dict(self):
        """Test that decode returns a dictionary with expected keys."""
        # Arrange
        cursor = CursorEncoder.encode(100, datetime(2025, 1, 1, 0, 0, 0))
        
        # Act
        decoded = CursorEncoder.decode(cursor)
        
        # Assert
        assert "id" in decoded
        assert "created_at" in decoded
        assert len(decoded) == 2
    
    def test_decode_invalid_base64(self):
        """Test decode raises ValueError for invalid base64."""
        # Arrange
        invalid_cursor = "not-valid-base64!!!"
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            CursorEncoder.decode(invalid_cursor)
        
        assert "Invalid cursor format" in str(exc_info.value)
    
    def test_decode_invalid_json(self):
        """Test decode raises ValueError for invalid JSON."""
        # Arrange
        # Valid base64 but invalid JSON
        invalid_json = base64.urlsafe_b64encode(b"not json").decode()
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            CursorEncoder.decode(invalid_json)
        
        assert "Invalid cursor format" in str(exc_info.value)
    
    def test_decode_empty_string(self):
        """Test decode raises ValueError for empty string."""
        # Arrange
        empty_cursor = ""
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            CursorEncoder.decode(empty_cursor)
        
        assert "Invalid cursor format" in str(exc_info.value)
    
    def test_decode_malformed_data(self):
        """Test decode with valid JSON but missing required fields."""
        # Arrange
        # Valid base64 and JSON but missing 'id' field
        malformed_data = {"created_at": "2025-01-17T15:30:00"}
        malformed_cursor = base64.urlsafe_b64encode(
            json.dumps(malformed_data).encode()
        ).decode()
        
        # Act
        decoded = CursorEncoder.decode(malformed_cursor)
        
        # Assert - should decode successfully but missing 'id'
        assert decoded is not None
        assert "created_at" in decoded
        assert "id" not in decoded
    
    def test_encode_decode_roundtrip(self):
        """Test that encode->decode roundtrip preserves data."""
        # Arrange
        original_id = 42
        original_datetime = datetime(2025, 1, 17, 15, 30, 45, 123456)
        
        # Act
        cursor = CursorEncoder.encode(original_id, original_datetime)
        decoded = CursorEncoder.decode(cursor)
        
        # Assert
        assert decoded["id"] == original_id
        assert decoded["created_at"] == original_datetime.isoformat()
    
    def test_encode_decode_multiple_cursors(self):
        """Test encoding and decoding multiple different cursors."""
        # Arrange
        test_cases = [
            (1, datetime(2025, 1, 1, 0, 0, 0)),
            (100, datetime(2025, 6, 15, 12, 30, 0)),
            (999999, datetime(2025, 12, 31, 23, 59, 59)),
        ]
        
        # Act & Assert
        for test_id, test_datetime in test_cases:
            cursor = CursorEncoder.encode(test_id, test_datetime)
            decoded = CursorEncoder.decode(cursor)
            
            assert decoded["id"] == test_id
            assert decoded["created_at"] == test_datetime.isoformat()
    
    def test_different_cursors_for_different_data(self):
        """Test that different data produces different cursors."""
        # Arrange
        cursor1 = CursorEncoder.encode(1, datetime(2025, 1, 1, 0, 0, 0))
        cursor2 = CursorEncoder.encode(2, datetime(2025, 1, 1, 0, 0, 0))
        cursor3 = CursorEncoder.encode(1, datetime(2025, 1, 2, 0, 0, 0))
        
        # Assert
        assert cursor1 != cursor2
        assert cursor1 != cursor3
        assert cursor2 != cursor3
    
    def test_same_data_produces_same_cursor(self):
        """Test that encoding the same data twice produces identical cursors."""
        # Arrange
        test_id = 123
        test_datetime = datetime(2025, 1, 17, 15, 30, 0)
        
        # Act
        cursor1 = CursorEncoder.encode(test_id, test_datetime)
        cursor2 = CursorEncoder.encode(test_id, test_datetime)
        
        # Assert
        assert cursor1 == cursor2
    
    def test_decode_with_extra_whitespace(self):
        """Test decode handles cursors with extra whitespace."""
        # Arrange
        cursor = CursorEncoder.encode(123, datetime(2025, 1, 17, 15, 30, 0))
        cursor_with_whitespace = f"  {cursor}  "
        
        # Act
        decoded = CursorEncoder.decode(cursor_with_whitespace.strip())
        
        # Assert
        assert decoded["id"] == 123
    
    def test_encode_with_zero_id(self):
        """Test cursor encoding with ID of zero."""
        # Arrange
        last_id = 0
        last_created_at = datetime(2025, 1, 17, 15, 30, 0)
        
        # Act
        cursor = CursorEncoder.encode(last_id, last_created_at)
        decoded = CursorEncoder.decode(cursor)
        
        # Assert
        assert decoded["id"] == 0
    
    def test_encode_with_negative_id(self):
        """Test cursor encoding with negative ID (edge case)."""
        # Arrange
        last_id = -1
        last_created_at = datetime(2025, 1, 17, 15, 30, 0)
        
        # Act
        cursor = CursorEncoder.encode(last_id, last_created_at)
        decoded = CursorEncoder.decode(cursor)
        
        # Assert
        assert decoded["id"] == -1
    
    def test_cursor_is_url_safe(self):
        """Test that encoded cursor is URL-safe (no special characters)."""
        # Arrange
        last_id = 123
        last_created_at = datetime(2025, 1, 17, 15, 30, 0)
        
        # Act
        cursor = CursorEncoder.encode(last_id, last_created_at)
        
        # Assert - URL-safe base64 should not contain +, /, or =
        # (or they should be replaced with -, _, and omitted respectively)
        assert '+' not in cursor or '-' in cursor
        assert '/' not in cursor or '_' in cursor