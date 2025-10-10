"""
Comprehensive unit tests for app.utils.pagination module.
Tests pagination, sorting, searching, and utility functions.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import UUID, uuid4
from math import ceil

from app.utils.pagination import (
    PaginationParams, SortParams, PaginatedResponse, PaginationMeta,
    SearchParams, ListParams, paginate_query, paginate_async_query,
    create_cursor_pagination, apply_search_filters, apply_sorting,
    PaginationHelper, paginate_patients, paginate_messages, paginate_alerts
)


class TestPaginationParams:
    """Test PaginationParams model."""

    def test_pagination_params_defaults(self):
        """Test PaginationParams default values."""
        params = PaginationParams()

        assert params.page == 1
        assert params.size == 20

    def test_pagination_params_custom_values(self):
        """Test PaginationParams with custom values."""
        params = PaginationParams(page=3, size=50)

        assert params.page == 3
        assert params.size == 50

    def test_pagination_params_offset_calculation(self):
        """Test offset property calculation."""
        test_cases = [
            (1, 20, 0),   # First page
            (2, 20, 20),  # Second page
            (3, 10, 20),  # Third page, different size
            (5, 25, 100)  # Fifth page
        ]

        for page, size, expected_offset in test_cases:
            params = PaginationParams(page=page, size=size)
            assert params.offset == expected_offset

    def test_pagination_params_validation(self):
        """Test PaginationParams validation constraints."""
        # Page must be >= 1
        with pytest.raises(ValueError):
            PaginationParams(page=0)

        with pytest.raises(ValueError):
            PaginationParams(page=-1)

        # Size must be >= 1
        with pytest.raises(ValueError):
            PaginationParams(size=0)

        # Size must be <= 100
        with pytest.raises(ValueError):
            PaginationParams(size=101)

    def test_pagination_params_edge_values(self):
        """Test PaginationParams with edge values."""
        # Minimum valid values
        params = PaginationParams(page=1, size=1)
        assert params.page == 1
        assert params.size == 1
        assert params.offset == 0

        # Maximum valid values
        params = PaginationParams(page=1000, size=100)
        assert params.page == 1000
        assert params.size == 100
        assert params.offset == 99900


class TestSortParams:
    """Test SortParams model."""

    def test_sort_params_defaults(self):
        """Test SortParams default values."""
        params = SortParams()

        assert params.sort_by == "created_at"
        assert params.sort_order == "desc"

    def test_sort_params_custom_values(self):
        """Test SortParams with custom values."""
        params = SortParams(sort_by="name", sort_order="asc")

        assert params.sort_by == "name"
        assert params.sort_order == "asc"

    def test_sort_params_validation(self):
        """Test SortParams validation."""
        # Valid sort orders
        valid_orders = ["asc", "desc"]
        for order in valid_orders:
            params = SortParams(sort_order=order)
            assert params.sort_order == order

        # Invalid sort order should raise validation error
        with pytest.raises(ValueError):
            SortParams(sort_order="invalid")


class TestPaginatedResponse:
    """Test PaginatedResponse model."""

    def test_paginated_response_creation(self):
        """Test PaginatedResponse creation."""
        items = ["item1", "item2", "item3"]
        response = PaginatedResponse.create(
            items=items,
            total=100,
            page=2,
            size=20
        )

        assert response.items == items
        assert response.total == 100
        assert response.page == 2
        assert response.size == 20
        assert response.pages == 5  # ceil(100/20)
        assert response.has_next is True  # page 2 < 5 pages
        assert response.has_prev is True  # page 2 > 1

    def test_paginated_response_first_page(self):
        """Test PaginatedResponse for first page."""
        response = PaginatedResponse.create(
            items=["item1"],
            total=50,
            page=1,
            size=10
        )

        assert response.has_prev is False
        assert response.has_next is True

    def test_paginated_response_last_page(self):
        """Test PaginatedResponse for last page."""
        response = PaginatedResponse.create(
            items=["item1"],
            total=50,
            page=5,
            size=10
        )

        assert response.has_prev is True
        assert response.has_next is False

    def test_paginated_response_single_page(self):
        """Test PaginatedResponse for single page."""
        response = PaginatedResponse.create(
            items=["item1"],
            total=5,
            page=1,
            size=10
        )

        assert response.pages == 1
        assert response.has_prev is False
        assert response.has_next is False

    def test_paginated_response_zero_size(self):
        """Test PaginatedResponse with zero size."""
        response = PaginatedResponse.create(
            items=[],
            total=100,
            page=1,
            size=0
        )

        assert response.pages == 0

    def test_paginated_response_empty_result(self):
        """Test PaginatedResponse with empty result."""
        response = PaginatedResponse.create(
            items=[],
            total=0,
            page=1,
            size=20
        )

        assert response.items == []
        assert response.total == 0
        assert response.pages == 0
        assert response.has_next is False
        assert response.has_prev is False


class TestPaginationMeta:
    """Test PaginationMeta model."""

    def test_pagination_meta_creation(self):
        """Test PaginationMeta model creation."""
        meta = PaginationMeta(
            current_page=2,
            per_page=20,
            total_items=100,
            total_pages=5,
            has_next_page=True,
            has_previous_page=True,
            next_page=3,
            previous_page=1
        )

        assert meta.current_page == 2
        assert meta.per_page == 20
        assert meta.total_items == 100
        assert meta.total_pages == 5
        assert meta.has_next_page is True
        assert meta.has_previous_page is True
        assert meta.next_page == 3
        assert meta.previous_page == 1


class TestSearchParams:
    """Test SearchParams model."""

    def test_search_params_defaults(self):
        """Test SearchParams default values."""
        params = SearchParams()

        assert params.q is None
        assert params.filters == {}

    def test_search_params_custom_values(self):
        """Test SearchParams with custom values."""
        filters = {"status": "active", "category": "urgent"}
        params = SearchParams(q="search term", filters=filters)

        assert params.q == "search term"
        assert params.filters == filters


class TestListParams:
    """Test ListParams combining all parameter types."""

    def test_list_params_inheritance(self):
        """Test ListParams inherits from all parameter classes."""
        params = ListParams(
            page=2,
            size=50,
            sort_by="name",
            sort_order="asc",
            q="search",
            filters={"status": "active"}
        )

        # Should have attributes from all parent classes
        assert params.page == 2
        assert params.size == 50
        assert params.sort_by == "name"
        assert params.sort_order == "asc"
        assert params.q == "search"
        assert params.filters == {"status": "active"}
        assert params.offset == 50  # (2-1) * 50


class TestPaginateQuery:
    """Test paginate_query function."""

    @pytest.fixture
    def mock_query(self):
        """Create a mock SQLAlchemy query."""
        query = Mock()
        query.count.return_value = 150
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = ["item1", "item2", "item3"]
        return query

    def test_paginate_query_basic(self, mock_query):
        """Test basic query pagination."""
        items, meta = paginate_query(mock_query, page=2, size=20)

        assert items == ["item1", "item2", "item3"]
        assert meta.current_page == 2
        assert meta.per_page == 20
        assert meta.total_items == 150
        assert meta.total_pages == 8  # ceil(150/20)

        # Verify query methods called correctly
        mock_query.count.assert_called_once()
        mock_query.offset.assert_called_once_with(20)  # (2-1) * 20
        mock_query.limit.assert_called_once_with(20)

    def test_paginate_query_first_page(self, mock_query):
        """Test pagination for first page."""
        items, meta = paginate_query(mock_query, page=1, size=10)

        assert meta.current_page == 1
        assert meta.has_previous_page is False
        assert meta.previous_page is None
        mock_query.offset.assert_called_once_with(0)

    def test_paginate_query_parameter_validation(self, mock_query):
        """Test parameter validation in paginate_query."""
        # Invalid page should be normalized to 1
        items, meta = paginate_query(mock_query, page=0, size=20)
        assert meta.current_page == 1

        items, meta = paginate_query(mock_query, page=-5, size=20)
        assert meta.current_page == 1

        # Invalid size should be normalized
        items, meta = paginate_query(mock_query, page=1, size=0, max_size=100)
        assert meta.per_page == 1

        items, meta = paginate_query(mock_query, page=1, size=200, max_size=100)
        assert meta.per_page == 100

    def test_paginate_query_pagination_metadata(self, mock_query):
        """Test pagination metadata calculation."""
        mock_query.count.return_value = 95

        # Test middle page
        items, meta = paginate_query(mock_query, page=3, size=20)
        assert meta.current_page == 3
        assert meta.total_pages == 5  # ceil(95/20)
        assert meta.has_previous_page is True
        assert meta.has_next_page is True
        assert meta.previous_page == 2
        assert meta.next_page == 4

        # Test last page
        items, meta = paginate_query(mock_query, page=5, size=20)
        assert meta.has_next_page is False
        assert meta.next_page is None

    def test_paginate_query_zero_items(self, mock_query):
        """Test pagination with zero items."""
        mock_query.count.return_value = 0
        mock_query.all.return_value = []

        items, meta = paginate_query(mock_query, page=1, size=20)

        assert items == []
        assert meta.total_items == 0
        assert meta.total_pages == 0
        assert meta.has_next_page is False
        assert meta.has_previous_page is False


class TestPaginateAsyncQuery:
    """Test paginate_async_query function."""

    @pytest.mark.asyncio
    async def test_paginate_async_query(self):
        """Test async query pagination delegates to sync version."""
        mock_db = Mock()
        mock_query = Mock()

        with patch('app.utils.pagination.paginate_query') as mock_paginate:
            mock_paginate.return_value = (["item1"], Mock())

            result = await paginate_async_query(mock_db, mock_query, page=2, size=30)

            mock_paginate.assert_called_once_with(mock_query, 2, 30, 100)
            assert result[0] == ["item1"]


class TestCreateCursorPagination:
    """Test create_cursor_pagination function."""

    def test_create_cursor_pagination_basic(self):
        """Test basic cursor pagination."""
        items = [Mock(id=1), Mock(id=2), Mock(id=3)]
        result = create_cursor_pagination(items, limit=2)

        assert len(result["items"]) == 2
        assert result["has_more"] is True
        assert result["next_cursor"] == "2"
        assert result["cursor_field"] == "id"

    def test_create_cursor_pagination_no_more(self):
        """Test cursor pagination when no more items."""
        items = [Mock(id=1), Mock(id=2)]
        result = create_cursor_pagination(items, limit=5)

        assert len(result["items"]) == 2
        assert result["has_more"] is False
        assert result["next_cursor"] is None

    def test_create_cursor_pagination_empty(self):
        """Test cursor pagination with empty items."""
        items = []
        result = create_cursor_pagination(items, limit=10)

        assert result["items"] == []
        assert result["has_more"] is False
        assert result["next_cursor"] is None

    def test_create_cursor_pagination_custom_field(self):
        """Test cursor pagination with custom cursor field."""
        items = [Mock(timestamp=1000), Mock(timestamp=2000)]
        result = create_cursor_pagination(items, cursor_field="timestamp", limit=1)

        assert result["next_cursor"] == "1000"
        assert result["cursor_field"] == "timestamp"

    def test_create_cursor_pagination_missing_field(self):
        """Test cursor pagination when item doesn't have cursor field."""
        items = [Mock(id=1), Mock()]  # Second item has no id
        result = create_cursor_pagination(items, limit=1)

        # Should still work, but next_cursor might be None
        assert len(result["items"]) == 1


class TestApplySearchFilters:
    """Test apply_search_filters function."""

    @pytest.fixture
    def mock_query(self):
        """Create a mock SQLAlchemy query."""
        query = Mock()
        query.filter.return_value = query
        query.column_descriptions = [{"type": Mock()}]
        return query

    @pytest.fixture
    def mock_model_class(self):
        """Create a mock model class."""
        model = Mock()
        # Mock string field
        string_field = Mock()
        string_field.type.python_type = str
        string_field.ilike.return_value = "filter_condition"
        model.name = string_field
        model.description = string_field

        # Mock non-string field
        int_field = Mock()
        int_field.type.python_type = int
        model.id = int_field

        return model

    def test_apply_search_filters_with_query(self, mock_query, mock_model_class):
        """Test applying search filters with query string."""
        mock_query.column_descriptions[0]["type"] = mock_model_class
        search_params = SearchParams(q="test search")
        searchable_fields = ["name", "description"]

        with patch('app.utils.pagination.or_') as mock_or:
            mock_or.return_value = "or_condition"

            result = apply_search_filters(mock_query, search_params, searchable_fields)

            # Should have called ilike on searchable fields
            mock_model_class.name.ilike.assert_called_with("%test search%")
            mock_model_class.description.ilike.assert_called_with("%test search%")
            mock_or.assert_called_once()
            mock_query.filter.assert_called_with("or_condition")

    def test_apply_search_filters_with_additional_filters(self, mock_query, mock_model_class):
        """Test applying additional filters."""
        mock_query.column_descriptions[0]["type"] = mock_model_class
        search_params = SearchParams(filters={"id": 123, "status": "active"})

        # Mock hasattr to return True for id, False for status
        def mock_hasattr(obj, attr):
            return attr == "id"

        with patch('builtins.hasattr', side_effect=mock_hasattr):
            result = apply_search_filters(mock_query, search_params, [])

            # Should filter by id but not status (status doesn't exist on model)
            assert mock_query.filter.call_count >= 1

    def test_apply_search_filters_no_query_no_filters(self, mock_query):
        """Test applying search filters with no query or filters."""
        search_params = SearchParams()

        result = apply_search_filters(mock_query, search_params, ["name"])

        # Should return query unchanged
        assert result == mock_query
        mock_query.filter.assert_not_called()

    def test_apply_search_filters_invalid_model(self, mock_query):
        """Test applying search filters with invalid model structure."""
        mock_query.column_descriptions = []  # Empty descriptions
        search_params = SearchParams(q="test")

        result = apply_search_filters(mock_query, search_params, ["name"])

        # Should handle gracefully and not crash
        assert result == mock_query


class TestApplySorting:
    """Test apply_sorting function."""

    @pytest.fixture
    def mock_query(self):
        """Create a mock SQLAlchemy query."""
        query = Mock()
        query.order_by.return_value = query
        query.column_descriptions = [{"type": Mock()}]
        return query

    @pytest.fixture
    def mock_model_class(self):
        """Create a mock model class."""
        model = Mock()
        attr = Mock()
        attr.asc.return_value = "asc_order"
        attr.desc.return_value = "desc_order"
        model.created_at = attr
        model.name = attr
        return model

    def test_apply_sorting_allowed_field_desc(self, mock_query, mock_model_class):
        """Test applying sorting with allowed field in descending order."""
        mock_query.column_descriptions[0]["type"] = mock_model_class
        sort_params = SortParams(sort_by="created_at", sort_order="desc")
        allowed_fields = ["created_at", "name"]

        result = apply_sorting(mock_query, sort_params, allowed_fields)

        mock_model_class.created_at.desc.assert_called_once()
        mock_query.order_by.assert_called_once_with("desc_order")

    def test_apply_sorting_allowed_field_asc(self, mock_query, mock_model_class):
        """Test applying sorting with allowed field in ascending order."""
        mock_query.column_descriptions[0]["type"] = mock_model_class
        sort_params = SortParams(sort_by="name", sort_order="asc")
        allowed_fields = ["created_at", "name"]

        result = apply_sorting(mock_query, sort_params, allowed_fields)

        mock_model_class.name.asc.assert_called_once()
        mock_query.order_by.assert_called_once_with("asc_order")

    def test_apply_sorting_disallowed_field(self, mock_query, mock_model_class):
        """Test applying sorting with disallowed field."""
        sort_params = SortParams(sort_by="invalid_field", sort_order="desc")
        allowed_fields = ["created_at", "name"]

        result = apply_sorting(mock_query, sort_params, allowed_fields)

        # Should return query unchanged
        assert result == mock_query
        mock_query.order_by.assert_not_called()

    def test_apply_sorting_invalid_model(self, mock_query):
        """Test applying sorting with invalid model structure."""
        mock_query.column_descriptions = []  # Empty descriptions
        sort_params = SortParams(sort_by="created_at", sort_order="desc")

        result = apply_sorting(mock_query, sort_params, ["created_at"])

        # Should handle gracefully
        assert result == mock_query


class TestPaginationHelper:
    """Test PaginationHelper utility class."""

    def test_get_pagination_links(self):
        """Test pagination links generation."""
        links = PaginationHelper.get_pagination_links(
            base_url="https://api.example.com/items",
            page=3,
            total_pages=5,
            size=20
        )

        assert links["first"] == "https://api.example.com/items?page=1&size=20"
        assert links["last"] == "https://api.example.com/items?page=5&size=20"
        assert links["next"] == "https://api.example.com/items?page=4&size=20"
        assert links["prev"] == "https://api.example.com/items?page=2&size=20"

    def test_get_pagination_links_first_page(self):
        """Test pagination links for first page."""
        links = PaginationHelper.get_pagination_links(
            base_url="https://api.example.com/items",
            page=1,
            total_pages=5,
            size=20
        )

        assert links["prev"] is None
        assert links["next"] == "https://api.example.com/items?page=2&size=20"

    def test_get_pagination_links_last_page(self):
        """Test pagination links for last page."""
        links = PaginationHelper.get_pagination_links(
            base_url="https://api.example.com/items",
            page=5,
            total_pages=5,
            size=20
        )

        assert links["next"] is None
        assert links["prev"] == "https://api.example.com/items?page=4&size=20"

    def test_validate_pagination_params(self):
        """Test pagination parameter validation."""
        # Valid parameters
        page, size = PaginationHelper.validate_pagination_params(2, 30)
        assert page == 2
        assert size == 30

        # Invalid page (None, negative)
        page, size = PaginationHelper.validate_pagination_params(None, 20)
        assert page == 1

        page, size = PaginationHelper.validate_pagination_params(-1, 20)
        assert page == 1

        # Invalid size (None, negative, too large)
        page, size = PaginationHelper.validate_pagination_params(1, None, default_size=25)
        assert size == 25

        page, size = PaginationHelper.validate_pagination_params(1, 0, default_size=20)
        assert size == 20

        page, size = PaginationHelper.validate_pagination_params(1, 200, max_size=100)
        assert size == 100

    def test_validate_pagination_params_custom_defaults(self):
        """Test pagination parameter validation with custom defaults."""
        page, size = PaginationHelper.validate_pagination_params(
            None, None, default_size=50, max_size=200
        )
        assert page == 1
        assert size == 50


class TestConveniencePaginationFunctions:
    """Test convenience pagination functions for specific models."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = Mock()
        query = Mock()
        query.filter.return_value = query
        query.order_by.return_value = query
        session.query.return_value = query
        return session

    def test_paginate_patients(self, mock_db_session):
        """Test paginate_patients convenience function."""
        with patch('app.utils.pagination.paginate_query') as mock_paginate, \
             patch('app.utils.pagination.Patient') as mock_patient_model, \
             patch('app.utils.pagination.FlowState') as mock_flow_state:

            mock_paginate.return_value = ([], Mock())

            # Test with all parameters
            doctor_id = uuid4()
            result = paginate_patients(
                mock_db_session,
                page=2,
                size=30,
                search="John",
                doctor_id=doctor_id,
                flow_state="active"
            )

            # Verify query building
            mock_db_session.query.assert_called_once()
            mock_paginate.assert_called_once()

    def test_paginate_messages(self, mock_db_session):
        """Test paginate_messages convenience function."""
        with patch('app.utils.pagination.paginate_query') as mock_paginate, \
             patch('app.utils.pagination.Message') as mock_message_model:

            mock_paginate.return_value = ([], Mock())

            patient_id = uuid4()
            result = paginate_messages(
                mock_db_session,
                patient_id=patient_id,
                page=1,
                size=25,
                direction="inbound"
            )

            mock_paginate.assert_called_once()

    def test_paginate_alerts(self, mock_db_session):
        """Test paginate_alerts convenience function."""
        with patch('app.utils.pagination.paginate_query') as mock_paginate, \
             patch('app.utils.pagination.Alert') as mock_alert_model:

            mock_paginate.return_value = ([], Mock())

            patient_id = uuid4()
            result = paginate_alerts(
                mock_db_session,
                page=1,
                size=20,
                severity="high",
                status="open",
                patient_id=patient_id
            )

            mock_paginate.assert_called_once()

    def test_paginate_patients_invalid_flow_state(self, mock_db_session):
        """Test paginate_patients with invalid flow_state."""
        with patch('app.utils.pagination.paginate_query') as mock_paginate, \
             patch('app.utils.pagination.Patient') as mock_patient_model, \
             patch('app.utils.pagination.FlowState') as mock_flow_state:

            # Mock FlowState to raise ValueError for invalid value
            mock_flow_state.side_effect = ValueError("Invalid flow state")
            mock_paginate.return_value = ([], Mock())

            # Should not raise exception, just ignore the filter
            result = paginate_patients(
                mock_db_session,
                flow_state="invalid_state"
            )

            mock_paginate.assert_called_once()