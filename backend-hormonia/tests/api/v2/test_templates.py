"""
Comprehensive tests for Templates API v2
Tests for flow templates, quiz templates, and version management.
"""

import pytest
import json
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.flow import FlowKind, FlowTemplateVersion
from app.models.quiz import QuizTemplate


# ==================== Test Fixtures ====================

@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache for testing."""
    cache = AsyncMock()
    cache.get_session = AsyncMock(return_value={
        "firebase_uid": "test_firebase_uid",
        "user_id": str(uuid4())
    })
    cache.get_user_by_uid = AsyncMock(return_value={
        "id": str(uuid4()),
        "firebase_uid": "test_firebase_uid",
        "email": "doctor@test.com",
        "full_name": "Dr. Test",
        "role": "doctor",
        "is_active": True
    })
    cache.cache_user_data = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.setex = AsyncMock()
    cache.delete = AsyncMock()
    cache.keys = AsyncMock(return_value=[])
    return cache


@pytest.fixture
def mock_admin_user():
    """Mock admin user for testing."""
    return {
        "id": str(uuid4()),
        "firebase_uid": "admin_firebase_uid",
        "email": "admin@test.com",
        "full_name": "Admin User",
        "role": "admin",
        "is_active": True
    }


@pytest.fixture
def mock_doctor_user():
    """Mock doctor user for testing."""
    return {
        "id": str(uuid4()),
        "firebase_uid": "doctor_firebase_uid",
        "email": "doctor@test.com",
        "full_name": "Dr. Test",
        "role": "doctor",
        "is_active": True
    }


@pytest.fixture
def sample_flow_kind(db: Session):
    """Create a sample flow kind for testing."""
    flow_kind = FlowKind(
        id=uuid4(),
        kind_key="test_treatment",
        display_name="Test Treatment Flow",
        description="Flow for testing",
        is_active=True
    )
    db.add(flow_kind)
    db.commit()
    db.refresh(flow_kind)
    return flow_kind


@pytest.fixture
def sample_flow_template(db: Session, sample_flow_kind: FlowKind):
    """Create a sample flow template for testing."""
    template = FlowTemplateVersion(
        id=uuid4(),
        kind_id=sample_flow_kind.id,
        version_number=1,
        template_name="Test Template v1",
        description="Test template description",
        messages={"day_1": {"message": "Welcome", "type": "greeting"}},
        template_metadata={"duration_days": 30},
        is_active=True,
        is_draft=False,
        published_at=datetime.utcnow(),
        created_by=uuid4()
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@pytest.fixture
def sample_quiz_template(db: Session):
    """Create a sample quiz template for testing."""
    quiz = QuizTemplate(
        id=uuid4(),
        name="Test Quiz",
        version="1.0",
        description="Test quiz description",
        questions=[
            {
                "id": "q1",
                "text": "How are you feeling?",
                "type": "multiple_choice",
                "options": ["Great", "Good", "Fair", "Poor"]
            }
        ],
        category="health_check",
        tags=["test", "health"],
        passing_score=70,
        time_limit_minutes=15,
        randomize_questions=False,
        is_active=True
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz


# ==================== Flow Template Tests ====================

class TestFlowTemplateList:
    """Tests for listing flow templates."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_list_flow_templates_success(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test successful flow template list retrieval."""
        mock_get_redis.return_value = None  # No cache

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    "/api/v2/templates/flows",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data
        assert len(data["data"]) > 0
        assert data["data"][0]["template_name"] == "Test Template v1"

    @patch("app.api.v2.templates.get_async_redis")
    async def test_list_flow_templates_with_filters(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test flow template list with filters."""
        mock_get_redis.return_value = None

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    "/api/v2/templates/flows?is_active=true&is_draft=false&limit=10",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data

    @patch("app.api.v2.templates.get_async_redis")
    async def test_list_flow_templates_with_pagination(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test flow template list with cursor pagination."""
        mock_get_redis.return_value = None

        # Create cursor
        cursor_data = {
            "id": str(sample_flow_template.id),
            "created_at": sample_flow_template.created_at.isoformat()
        }
        cursor = json.dumps(cursor_data)

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    f"/api/v2/templates/flows?cursor={cursor}&limit=5",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK

    async def test_list_flow_templates_unauthorized(self, client: TestClient):
        """Test flow template list without authentication."""
        response = client.get("/api/v2/templates/flows")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestFlowTemplateGet:
    """Tests for getting a specific flow template."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_get_flow_template_success(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test successful flow template retrieval."""
        mock_get_redis.return_value = None

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    f"/api/v2/templates/flows/{sample_flow_template.id}",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(sample_flow_template.id)
        assert data["template_name"] == "Test Template v1"
        assert "steps" in data

    @patch("app.api.v2.templates.get_async_redis")
    async def test_get_flow_template_not_found(
        self,
        mock_get_redis,
        client: TestClient,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test flow template not found."""
        mock_get_redis.return_value = None
        fake_id = uuid4()

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    f"/api/v2/templates/flows/{fake_id}",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestFlowTemplateCreate:
    """Tests for creating flow templates."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_create_flow_template_success(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_kind: FlowKind,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test successful flow template creation."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        template_data = {
            "flow_kind_id": str(sample_flow_kind.id),
            "version_number": 2,
            "template_name": "New Template v2",
            "description": "New template description",
            "steps": {"day_1": {"message": "Hello", "type": "greeting"}},
            "metadata": {"duration_days": 45},
            "is_active": False,
            "is_draft": True
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.post(
                    "/api/v2/templates/flows",
                    json=template_data,
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["template_name"] == "New Template v2"
        assert data["version_number"] == 2
        assert data["is_draft"] is True

    @patch("app.api.v2.templates.get_async_redis")
    async def test_create_flow_template_with_new_kind(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test flow template creation with new flow kind."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        template_data = {
            "kind_key": "new_treatment_type",
            "display_name": "New Treatment Type",
            "version_number": 1,
            "template_name": "New Treatment v1",
            "description": "New treatment flow",
            "steps": {"day_1": {"message": "Start", "type": "start"}},
            "metadata": {},
            "is_active": True,
            "is_draft": False
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.post(
                    "/api/v2/templates/flows",
                    json=template_data,
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["kind_key"] == "new_treatment_type"

    @patch("app.api.v2.templates.get_async_redis")
    async def test_create_flow_template_duplicate_version(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test flow template creation with duplicate version."""
        mock_get_redis.return_value = None

        template_data = {
            "flow_kind_id": str(sample_flow_template.kind_id),
            "version_number": sample_flow_template.version_number,  # Duplicate
            "template_name": "Duplicate Template",
            "steps": {},
            "is_draft": True
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.post(
                    "/api/v2/templates/flows",
                    json=template_data,
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_409_CONFLICT


class TestFlowTemplateUpdate:
    """Tests for updating flow templates."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_update_flow_template_success(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test successful flow template update."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        update_data = {
            "template_name": "Updated Template Name",
            "description": "Updated description",
            "is_active": True
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.put(
                    f"/api/v2/templates/flows/{sample_flow_template.id}",
                    json=update_data,
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["template_name"] == "Updated Template Name"
        assert data["description"] == "Updated description"

    @patch("app.api.v2.templates.get_async_redis")
    async def test_update_flow_template_not_found(
        self,
        mock_get_redis,
        client: TestClient,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test flow template update not found."""
        mock_get_redis.return_value = None
        fake_id = uuid4()

        update_data = {"template_name": "Updated"}

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.put(
                    f"/api/v2/templates/flows/{fake_id}",
                    json=update_data,
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestFlowTemplateDelete:
    """Tests for deleting flow templates."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_delete_flow_template_soft(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test soft delete flow template."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.delete(
                    f"/api/v2/templates/flows/{sample_flow_template.id}?soft_delete=true",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify soft delete
        db.refresh(sample_flow_template)
        assert sample_flow_template.is_active is False

    @patch("app.api.v2.templates.get_async_redis")
    async def test_delete_flow_template_hard(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test hard delete flow template."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        template_id = sample_flow_template.id

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.delete(
                    f"/api/v2/templates/flows/{template_id}?soft_delete=false",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify hard delete
        deleted = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == template_id
        ).first()
        assert deleted is None


class TestFlowTemplateDuplicate:
    """Tests for duplicating flow templates."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_duplicate_flow_template_success(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test successful flow template duplication."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        duplicate_data = {
            "new_version_number": 3,
            "new_template_name": "Duplicated Template",
            "description": "Duplicated from v1"
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.post(
                    f"/api/v2/templates/flows/{sample_flow_template.id}/duplicate",
                    json=duplicate_data,
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["version_number"] == 3
        assert data["template_name"] == "Duplicated Template"
        assert data["is_draft"] is True


# ==================== Quiz Template Tests ====================

class TestQuizTemplateList:
    """Tests for listing quiz templates."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_list_quiz_templates_success(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_quiz_template: QuizTemplate,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test successful quiz template list retrieval."""
        mock_get_redis.return_value = None

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    "/api/v2/templates/quiz",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0

    @patch("app.api.v2.templates.get_async_redis")
    async def test_list_quiz_templates_with_category_filter(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_quiz_template: QuizTemplate,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test quiz template list with category filter."""
        mock_get_redis.return_value = None

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    "/api/v2/templates/quiz?category=health_check",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK


class TestQuizTemplateCreate:
    """Tests for creating quiz templates."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_create_quiz_template_success(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test successful quiz template creation."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        quiz_data = {
            "name": "New Quiz",
            "version": "2.0",
            "description": "New quiz description",
            "questions": [
                {
                    "id": "q1",
                    "text": "Question 1?",
                    "type": "multiple_choice",
                    "options": ["A", "B", "C"]
                }
            ],
            "category": "wellness",
            "tags": ["new", "test"],
            "passing_score": 80,
            "time_limit_minutes": 20,
            "randomize_questions": True,
            "is_active": True
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.post(
                    "/api/v2/templates/quiz",
                    json=quiz_data,
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "New Quiz"
        assert data["version"] == "2.0"


# ==================== Flow Kind Tests ====================

class TestFlowKindList:
    """Tests for listing flow kinds."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_list_flow_kinds_success(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_kind: FlowKind,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test successful flow kind list retrieval."""
        mock_get_redis.return_value = None

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    "/api/v2/templates/flow-kinds",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "total" in data


class TestFlowKindCreate:
    """Tests for creating flow kinds."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_create_flow_kind_success(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test successful flow kind creation."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        kind_data = {
            "kind_key": "chemotherapy",
            "display_name": "Chemotherapy Flow",
            "description": "Flow for chemotherapy patients",
            "is_active": True
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.post(
                    "/api/v2/templates/flow-kinds",
                    json=kind_data,
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["kind_key"] == "chemotherapy"


# ==================== Version Management Tests ====================

class TestVersionManagement:
    """Tests for version management operations."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_list_template_versions(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test listing template versions."""
        mock_get_redis.return_value = None

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    f"/api/v2/templates/flows/{sample_flow_template.id}/versions",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "total" in data

    @patch("app.api.v2.templates.get_async_redis")
    async def test_publish_template_version(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test publishing a draft template version."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        # Create a draft template
        flow_kind = FlowKind(
            id=uuid4(),
            kind_key="test_publish",
            display_name="Test Publish",
            is_active=True
        )
        db.add(flow_kind)
        db.commit()

        draft_template = FlowTemplateVersion(
            id=uuid4(),
            kind_id=flow_kind.id,
            version_number=1,
            template_name="Draft Template",
            messages={},
            template_metadata={},
            is_active=False,
            is_draft=True,
            created_by=uuid4()
        )
        db.add(draft_template)
        db.commit()

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.post(
                    f"/api/v2/templates/flows/{draft_template.id}/publish?set_as_active=true",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_draft"] is False
        assert data["published_at"] is not None


# ==================== Search & Validation Tests ====================

class TestTemplateSearch:
    """Tests for template search."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_search_templates_success(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        sample_quiz_template: QuizTemplate,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test successful template search."""
        mock_get_redis.return_value = None

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    "/api/v2/templates/search?q=test",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "results" in data
        assert "total" in data


class TestTemplateValidation:
    """Tests for template validation."""

    async def test_validate_flow_template_success(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test successful flow template validation."""
        template_data = {
            "version_number": 1,
            "template_name": "Test Template",
            "steps": {"day_1": {"message": "Hello"}},
            "metadata": {}
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            response = client.post(
                "/api/v2/templates/validate?template_type=flow",
                json=template_data,
                headers={"X-Session-ID": "test_session"}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True

    async def test_validate_flow_template_with_errors(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test flow template validation with errors."""
        template_data = {
            "template_name": "Test Template"
            # Missing required fields
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            response = client.post(
                "/api/v2/templates/validate?template_type=flow",
                json=template_data,
                headers={"X-Session-ID": "test_session"}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0


# ==================== RBAC Tests ====================

class TestTemplateRBAC:
    """Tests for role-based access control."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_admin_can_create_template(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        mock_redis_cache,
        mock_admin_user
    ):
        """Test admin can create templates."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        template_data = {
            "kind_key": "admin_test",
            "version_number": 1,
            "template_name": "Admin Template",
            "steps": {},
            "is_draft": True
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_admin_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.post(
                    "/api/v2/templates/flows",
                    json=template_data,
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_201_CREATED

    @patch("app.api.v2.templates.get_async_redis")
    async def test_doctor_can_create_template(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        mock_redis_cache,
        mock_doctor_user
    ):
        """Test doctor can create templates."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis

        template_data = {
            "kind_key": "doctor_test",
            "version_number": 1,
            "template_name": "Doctor Template",
            "steps": {},
            "is_draft": True
        }

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.post(
                    "/api/v2/templates/flows",
                    json=template_data,
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_201_CREATED


# ==================== Cache Tests ====================

class TestTemplateCache:
    """Tests for template caching."""

    @patch("app.api.v2.templates.get_async_redis")
    async def test_list_uses_cache(
        self,
        mock_get_redis,
        client: TestClient,
        db: Session,
        sample_flow_template: FlowTemplateVersion,
        mock_doctor_user
    ):
        """Test that list endpoint uses cache."""
        mock_redis = AsyncMock()
        cached_data = {
            "data": [{"id": "cached"}],
            "next_cursor": None,
            "has_more": False
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))
        mock_get_redis.return_value = mock_redis

        mock_redis_cache = AsyncMock()
        mock_redis_cache.get_session = AsyncMock(return_value={"firebase_uid": "test"})
        mock_redis_cache.get_user_by_uid = AsyncMock(return_value=mock_doctor_user)

        with patch("app.api.v2.templates._get_current_user_simple", return_value=mock_doctor_user):
            with patch("app.api.v2.templates.get_redis_cache", return_value=mock_redis_cache):
                response = client.get(
                    "/api/v2/templates/flows",
                    headers={"X-Session-ID": "test_session"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"][0]["id"] == "cached"
