"""
Comprehensive tests for Docs API v2
Tests for API documentation, guides, examples, and search functionality.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.api.v2.routers.docs.data_providers import get_static_examples, get_static_guides


# ==================== Test Fixtures ====================

@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache for testing."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.setex = AsyncMock()
    cache.delete = AsyncMock()
    cache.keys = AsyncMock(return_value=[])
    return cache


@pytest.fixture
def mock_openapi_spec():
    """Mock OpenAPI specification."""
    return {
        "openapi": "3.0.2",
        "info": {
            "title": "Hormonia API",
            "version": "2.0.0",
            "description": "Oncology management platform API"
        },
        "paths": {
            "/api/v2/patients": {
                "get": {
                    "summary": "List patients",
                    "description": "Retrieve paginated list of patients",
                    "tags": ["Patients"],
                    "security": [{"SessionAuth": []}],
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "description": "Page size",
                            "required": False,
                            "schema": {"type": "integer", "default": 20}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            }
                        }
                    }
                },
                "post": {
                    "summary": "Create patient",
                    "description": "Create a new patient record",
                    "tags": ["Patients"],
                    "security": [{"SessionAuth": []}],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    },
                    "responses": {
                        "201": {"description": "Patient created"}
                    }
                }
            },
            "/api/v2/auth/login": {
                "post": {
                    "summary": "Login",
                    "description": "Authenticate user and create session",
                    "tags": ["Authentication"],
                    "responses": {
                        "200": {"description": "Login successful"}
                    }
                }
            }
        }
    }


# ==================== Endpoint Documentation Tests ====================

class TestListAPIEndpoints:
    """Tests for listing API endpoints."""

    def test_list_all_endpoints_success(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test listing all API endpoints successfully."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/endpoints")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data
        assert "by_category" in data
        assert "total" in data
        assert "categories" in data

        assert data["total"] >= 2  # At least 2 endpoints in mock spec
        assert len(data["data"]) > 0
        assert "Patients" in data["categories"]

    def test_list_endpoints_with_category_filter(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test filtering endpoints by category."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/endpoints?category=Patients")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned endpoints should be in Patients category
        for endpoint in data["data"]:
            assert "Patients" in endpoint["tags"]

    def test_list_endpoints_with_method_filter(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test filtering endpoints by HTTP method."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/endpoints?method=GET")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned endpoints should be GET
        for endpoint in data["data"]:
            assert endpoint["method"] == "GET"

    def test_list_endpoints_with_search(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test searching endpoints."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/endpoints?search=patient")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["data"]) > 0
        # Search term should appear in path, summary, or description
        for endpoint in data["data"]:
            search_text = (
                endpoint["path"] +
                endpoint["summary"] +
                endpoint["description"]
            ).lower()
            assert "patient" in search_text

    def test_list_endpoints_with_auth_filter(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test filtering endpoints by authentication requirement."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/endpoints?requires_auth=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned endpoints should require auth
        for endpoint in data["data"]:
            assert endpoint["requires_auth"] is True

    def test_list_endpoints_with_limit(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test limiting number of returned endpoints."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/endpoints?limit=1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["data"]) <= 1

    def test_list_endpoints_caching(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test that endpoint list is cached."""
        cached_data = {
            "data": [],
            "by_category": {},
            "total": 0,
            "categories": []
        }
        mock_redis_cache.get = AsyncMock(return_value=json.dumps(cached_data))

        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/endpoints")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return cached data
        assert data == cached_data
        mock_redis_cache.get.assert_called_once()


class TestGetEndpointDocumentation:
    """Tests for getting specific endpoint documentation."""

    def test_get_endpoint_documentation_success(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test getting endpoint documentation successfully."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/endpoints/GET/api/v2/patients")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["method"] == "GET"
        assert data["path"] == "/api/v2/patients"
        assert "summary" in data
        assert "description" in data
        assert "parameters" in data
        assert "responses" in data
        assert "related_endpoints" in data

    def test_get_endpoint_documentation_not_found(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test getting non-existent endpoint documentation."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/endpoints/GET/api/v2/nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    def test_get_endpoint_documentation_with_related(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test that related endpoints are included."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/endpoints/GET/api/v2/patients")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "related_endpoints" in data
        # Should have at least one related endpoint (POST patients)
        if len(data["related_endpoints"]) > 0:
            related = data["related_endpoints"][0]
            assert "method" in related
            assert "path" in related
            assert "summary" in related


# ==================== Guides Tests ====================

class TestListGuides:
    """Tests for listing documentation guides."""

    def test_list_all_guides_success(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test listing all guides successfully."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/guides")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data
        assert "total" in data
        assert "categories" in data

        assert data["total"] > 0
        assert len(data["data"]) > 0

        # Check guide structure
        guide = data["data"][0]
        assert "id" in guide
        assert "slug" in guide
        assert "title" in guide
        assert "description" in guide
        assert "category" in guide
        assert "tags" in guide

    def test_list_guides_with_category_filter(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test filtering guides by category."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/guides?category=basics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All guides should be in basics category
        for guide in data["data"]:
            assert guide["category"] == "basics"

    def test_list_guides_with_tags_filter(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test filtering guides by tags."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/guides?tags=authentication")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All guides should have authentication tag
        for guide in data["data"]:
            assert "authentication" in guide["tags"]

    def test_list_guides_ordering(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test that guides are ordered correctly."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/guides")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check that guides are ordered by 'order' field
        orders = [guide["order"] for guide in data["data"]]
        assert orders == sorted(orders)


class TestGetGuideBySlug:
    """Tests for getting specific guide."""

    def test_get_guide_success(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test getting guide successfully."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/guides/getting-started")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["slug"] == "getting-started"
        assert "content" in data
        assert "related_guides" in data
        assert len(data["content"]) > 0

        # Content should be Markdown
        assert "#" in data["content"]  # Markdown heading

    def test_get_guide_not_found(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test getting non-existent guide."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/guides/nonexistent-guide")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    def test_get_guide_with_related(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test that related guides are included."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/guides/getting-started")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "related_guides" in data
        # Related guides should have minimal info
        if len(data["related_guides"]) > 0:
            related = data["related_guides"][0]
            assert "id" in related
            assert "slug" in related
            assert "title" in related


# ==================== Code Examples Tests ====================

class TestListCodeExamples:
    """Tests for listing code examples."""

    def test_list_all_examples_success(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test listing all examples successfully."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/examples")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data
        assert "total" in data
        assert "languages" in data
        assert "categories" in data

        assert data["total"] > 0
        assert len(data["data"]) > 0

        # Check example structure
        example = data["data"][0]
        assert "id" in example
        assert "title" in example
        assert "language" in example
        assert "category" in example

    def test_list_examples_with_category_filter(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test filtering examples by category."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/examples?category=patients")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All examples should be in patients category
        for example in data["data"]:
            assert example["category"] == "patients"

    def test_list_examples_with_language_filter(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test filtering examples by language."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/examples?language=python")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All examples should be Python
        for example in data["data"]:
            assert example["language"] == "python"

    def test_list_examples_with_endpoint_filter(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test filtering examples by endpoint."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/examples?endpoint=/api/v2/patients")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All examples should be for /api/v2/patients endpoint
        for example in data["data"]:
            if example["endpoint"]:
                assert example["endpoint"] == "/api/v2/patients"


class TestGetCodeExample:
    """Tests for getting specific code example."""

    def test_get_example_success(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test getting example successfully."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/examples/example-001")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == "example-001"
        assert "code" in data
        assert "related_examples" in data
        assert len(data["code"]) > 0

    def test_get_example_not_found(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test getting non-existent example."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/examples/nonexistent-example")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data


# ==================== Search Tests ====================

class TestSearchDocumentation:
    """Tests for documentation search."""

    def test_search_documentation_success(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test searching documentation successfully."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/search?q=authentication")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "query" in data
        assert "results" in data
        assert "total" in data
        assert "types" in data

        assert data["query"] == "authentication"
        assert data["total"] > 0

        # Check result structure
        if len(data["results"]) > 0:
            result = data["results"][0]
            assert "type" in result
            assert "id" in result
            assert "title" in result
            assert "relevance_score" in result
            assert "url" in result

    def test_search_with_type_filter(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test searching with type filter."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/search?q=patient&type=endpoint")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All results should be endpoints
        for result in data["results"]:
            assert result["type"] == "endpoint"

    def test_search_relevance_scoring(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test that search results are scored by relevance."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/search?q=authentication")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Results should be sorted by relevance
        scores = [result["relevance_score"] for result in data["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_search_with_limit(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test limiting search results."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                response = client.get("/api/v2/docs/search?q=patient&limit=2")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["results"]) <= 2

    def test_search_minimum_query_length(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test that search requires minimum query length."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/search?q=a")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ==================== Changelog Tests ====================

class TestGetAPIChangelog:
    """Tests for API changelog."""

    def test_get_changelog_success(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test getting changelog successfully."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/changelog")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "versions" in data
        assert "current_version" in data
        assert "latest_stable" in data
        assert "deprecated_versions" in data

        assert len(data["versions"]) > 0

        # Check version structure
        version = data["versions"][0]
        assert "version" in version
        assert "release_date" in version
        assert "status" in version
        assert "breaking_changes" in version
        assert "changes" in version

        # Check changes structure
        if len(version["changes"]) > 0:
            change = version["changes"][0]
            assert "type" in change
            assert "category" in change
            assert "description" in change

    def test_get_changelog_specific_version(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test getting changelog for specific version."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/changelog?version=2.0.0")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should only return specified version
        assert len(data["versions"]) == 1
        assert data["versions"][0]["version"] == "2.0.0"

    def test_get_changelog_nonexistent_version(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test getting changelog for non-existent version."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/changelog?version=99.99.99")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data


# ==================== Caching Tests ====================

class TestDocumentationCaching:
    """Tests for documentation caching."""

    def test_cache_hit_returns_cached_data(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test that cache hit returns cached data."""
        cached_guides = {
            "data": [{"id": "cached"}],
            "total": 1,
            "categories": []
        }
        mock_redis_cache.get = AsyncMock(return_value=json.dumps(cached_guides))

        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/guides")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return exact cached data
        assert data["data"][0]["id"] == "cached"
        mock_redis_cache.get.assert_called_once()

    def test_cache_miss_sets_cache(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test that cache miss sets new cache entry."""
        mock_redis_cache.get = AsyncMock(return_value=None)

        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            response = client.get("/api/v2/docs/guides")

        assert response.status_code == status.HTTP_200_OK

        # Should have tried to set cache
        mock_redis_cache.setex.assert_called_once()


# ==================== Public Access Tests ====================

class TestPublicAccess:
    """Tests for public access to documentation."""

    def test_endpoints_public_access(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test that endpoints can be accessed without authentication."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                # No session headers
                response = client.get("/api/v2/docs/endpoints")

        # Should succeed without authentication
        assert response.status_code == status.HTTP_200_OK

    def test_guides_public_access(
        self,
        client: TestClient,
        mock_redis_cache
    ):
        """Test that guides can be accessed without authentication."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            # No session headers
            response = client.get("/api/v2/docs/guides")

        # Should succeed without authentication
        assert response.status_code == status.HTTP_200_OK

    def test_search_public_access(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_openapi_spec
    ):
        """Test that search can be accessed without authentication."""
        with patch("app.api.v2.routers.docs.cache_utils.get_async_redis", return_value=mock_redis_cache):
            with patch.object(client.app, "openapi", return_value=mock_openapi_spec):
                # No session headers
                response = client.get("/api/v2/docs/search?q=test")

        # Should succeed without authentication
        assert response.status_code == status.HTTP_200_OK


class TestCanonicalRuntimeDocsGuidance:
    def test_static_guides_use_cookie_backed_contract_without_firebase_or_header(self):
        guides = {guide["slug"]: guide for guide in get_static_guides()}
        combined = "\n".join(
            [guides["getting-started"]["content"], guides["authentication"]["content"]]
        )

        assert "Firebase" not in combined
        assert "X-Session-ID" not in combined
        assert "session_id" in combined
        assert "cookie" in combined.lower()

    def test_static_examples_use_cookie_aware_clients_without_legacy_transports(self):
        examples = {example["id"]: example for example in get_static_examples()}
        combined = "\n".join(example["code"] for example in examples.values())

        assert "Firebase" not in combined
        assert "X-Session-ID" not in combined
        assert "requests.Session()" in examples["example-003"]["code"]
        assert "withCredentials: true" in examples["example-002"]["code"]
        assert "withCredentials: true" in examples["example-005"]["code"]

    def test_authentication_guide_endpoint_returns_cookie_guidance(
        self,
        client: TestClient,
        mock_redis_cache,
    ):
        with patch(
            "app.api.v2.routers.docs.cache_utils.get_async_redis",
            return_value=mock_redis_cache,
        ):
            response = client.get("/api/v2/docs/guides/authentication")

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert "Firebase" not in payload["content"]
        assert "X-Session-ID" not in payload["content"]
        assert "session_id" in payload["content"]
