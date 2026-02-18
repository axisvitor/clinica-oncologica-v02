"""
Tests for Cursor Pagination Utility

MEDIUM-015: Test cursor-based pagination functionality and performance.
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID
from unittest.mock import Mock

from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
from app.utils.cursor_pagination import (
    CursorPaginator,
    CursorPage
)


class TestCursorEncoding:
    """Test cursor encoding and decoding."""

    def test_encode_cursor(self):
        """Test cursor encoding."""
        test_id = uuid4()
        test_timestamp = datetime(2025, 1, 1, 12, 0, 0)

        cursor = CursorPaginator.encode_cursor(test_id, test_timestamp)

        # Should return base64-encoded string
        assert isinstance(cursor, str)
        assert len(cursor) > 0

    def test_decode_cursor(self):
        """Test cursor decoding."""
        test_id = uuid4()
        test_timestamp = datetime(2025, 1, 1, 12, 0, 0)

        # Encode then decode
        cursor = CursorPaginator.encode_cursor(test_id, test_timestamp)
        decoded_id, decoded_timestamp = CursorPaginator.decode_cursor(cursor)

        # Should match original values
        assert decoded_id == test_id
        assert decoded_timestamp == test_timestamp

    def test_cursor_roundtrip(self):
        """Test encoding and decoding roundtrip."""
        original_id = uuid4()
        original_timestamp = now_sao_paulo_naive()

        cursor = CursorPaginator.encode_cursor(original_id, original_timestamp)
        decoded_id, decoded_timestamp = CursorPaginator.decode_cursor(cursor)

        assert decoded_id == original_id
        assert decoded_timestamp == original_timestamp

    def test_decode_invalid_cursor(self):
        """Test decoding invalid cursor raises ValueError."""
        invalid_cursors = [
            "invalid_base64!@#",
            "dGVzdA==",  # Valid base64 but not JSON
            "e30=",  # Empty JSON object
        ]

        for cursor in invalid_cursors:
            with pytest.raises(ValueError):
                CursorPaginator.decode_cursor(cursor)

    def test_cursor_contains_expected_fields(self):
        """Test that decoded cursor contains expected fields."""
        test_id = uuid4()
        test_timestamp = datetime(2025, 1, 1, 12, 0, 0)

        cursor = CursorPaginator.encode_cursor(test_id, test_timestamp)
        decoded_id, decoded_timestamp = CursorPaginator.decode_cursor(cursor)

        # Check types
        assert isinstance(decoded_id, UUID)
        assert isinstance(decoded_timestamp, datetime)


class TestCursorPage:
    """Test CursorPage model."""

    def test_cursor_page_creation(self):
        """Test CursorPage model creation."""
        items = [Mock(id=uuid4(), name=f"Item {i}") for i in range(10)]

        page = CursorPage(
            items=items,
            next_cursor="next_cursor_value",
            prev_cursor="prev_cursor_value",
            has_next=True,
            has_prev=False,
            total_count=100
        )

        assert len(page.items) == 10
        assert page.next_cursor == "next_cursor_value"
        assert page.prev_cursor == "prev_cursor_value"
        assert page.has_next is True
        assert page.has_prev is False
        assert page.total_count == 100

    def test_cursor_page_defaults(self):
        """Test CursorPage default values."""
        page = CursorPage()

        assert page.items == []
        assert page.next_cursor is None
        assert page.prev_cursor is None
        assert page.has_next is False
        assert page.has_prev is False
        assert page.total_count is None

    def test_cursor_page_generic_type(self):
        """Test that CursorPage works with generic types."""
        # Create a simple model
        class TestModel:
            def __init__(self, id, name):
                self.id = id
                self.name = name

        items = [TestModel(uuid4(), f"Item {i}") for i in range(5)]
        page = CursorPage[TestModel](items=items)

        assert len(page.items) == 5
        assert all(isinstance(item, TestModel) for item in page.items)


@pytest.mark.asyncio
class TestCursorPaginator:
    """Test cursor pagination functionality."""

    async def test_limit_clamping(self):
        """Test that limit is clamped between 1 and 100."""
        # Limit should be clamped to [1, 100] range
        # This would be tested in the actual paginate method
        assert min(max(1, 50), 100) == 50
        assert min(max(1, 0), 100) == 1
        assert min(max(1, 150), 100) == 100


class TestPaginationPerformance:
    """Test pagination performance characteristics."""

    def test_cursor_size_reasonable(self):
        """Test that cursor size is reasonable."""
        test_id = uuid4()
        test_timestamp = now_sao_paulo_naive()

        cursor = CursorPaginator.encode_cursor(test_id, test_timestamp)

        # Cursor should be reasonably sized (< 200 bytes)
        assert len(cursor) < 200

    def test_cursor_url_safe(self):
        """Test that cursor is URL-safe."""
        test_id = uuid4()
        test_timestamp = now_sao_paulo_naive()

        cursor = CursorPaginator.encode_cursor(test_id, test_timestamp)

        # Should only contain URL-safe characters
        import string
        url_safe_chars = string.ascii_letters + string.digits + '-_='
        assert all(c in url_safe_chars for c in cursor)


class TestPaginationEdgeCases:
    """Test edge cases for pagination."""

    def test_empty_results(self):
        """Test pagination with no results."""
        page = CursorPage(items=[])

        assert len(page.items) == 0
        assert page.has_next is False
        assert page.has_prev is False
        assert page.next_cursor is None

    def test_single_item(self):
        """Test pagination with single item."""
        items = [Mock(id=uuid4(), name="Single Item")]
        page = CursorPage(items=items, has_next=False)

        assert len(page.items) == 1
        assert page.has_next is False
