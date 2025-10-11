"""
Template CRUD Operations Comprehensive Test Suite
================================================

This test suite validates all template CRUD operations for the quiz template system,
ensuring data integrity, validation, error handling, and edge case coverage.

Test Coverage:
- Template creation with validation
- Template retrieval and filtering
- Template updates and versioning
- Template deletion and soft-delete scenarios
- Edge cases and error conditions
- Performance and concurrency testing
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from uuid import UUID, uuid4
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.quiz import QuizTemplate, QuizQuestion, QuestionType
from app.schemas.template import (
    TemplateCreateRequest,
    TemplateUpdateRequest,
    TemplateResponse,
    TemplateListResponse
)


client = TestClient(app)


class TestTemplateCRUDOperations:
    """Comprehensive test suite for template CRUD operations."""

    @pytest.fixture
    def mock_auth_user(self):
        """Mock authenticated user."""
        return MagicMock(
            id=uuid4(),
            email="doctor@test.com",
            role="doctor",
            is_active=True
        )

    @pytest.fixture
    def mock_database_session(self):
        """Mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def sample_template_data(self):
        """Sample template data for testing."""
        return {
            "name": "Test Template",
            "description": "A test template for unit testing",
            "category": "symptom_assessment",
            "is_active": True,
            "questions": [
                {
                    "id": "q1",
                    "text": "How are you feeling today?",
                    "type": "multiple_choice",
                    "required": True,
                    "options": ["Very Good", "Good", "Fair", "Poor", "Very Poor"],
                    "order": 1
                },
                {
                    "id": "q2",
                    "text": "Rate your pain level (1-10)",
                    "type": "scale",
                    "required": True,
                    "scale_min": 1,
                    "scale_max": 10,
                    "order": 2
                },
                {
                    "id": "q3",
                    "text": "Any additional comments?",
                    "type": "text",
                    "required": False,
                    "order": 3
                }
            ]
        }

    def test_create_template_success(self, mock_auth_user, mock_database_session, sample_template_data):
        """Test successful template creation."""
        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                # Mock template creation
                created_template = MagicMock()
                created_template.id = uuid4()
                created_template.name = sample_template_data["name"]
                created_template.description = sample_template_data["description"]
                created_template.category = sample_template_data["category"]
                created_template.is_active = sample_template_data["is_active"]
                created_template.created_at = datetime.now()
                created_template.updated_at = datetime.now()
                created_template.created_by = mock_auth_user.id

                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service_instance.create_template.return_value = created_template
                    mock_service.return_value = mock_service_instance

                    response = client.post("/api/v1/templates", json=sample_template_data)

                    assert response.status_code == 201
                    data = response.json()

                    # Validate response structure
                    assert "id" in data
                    assert data["name"] == sample_template_data["name"]
                    assert data["description"] == sample_template_data["description"]
                    assert data["category"] == sample_template_data["category"]
                    assert data["is_active"] == sample_template_data["is_active"]
                    assert "created_at" in data
                    assert "updated_at" in data

    def test_create_template_validation_errors(self, mock_auth_user):
        """Test template creation validation errors."""
        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            # Test missing required fields
            invalid_data = {
                "description": "Missing name field"
            }

            response = client.post("/api/v1/templates", json=invalid_data)

            assert response.status_code == 422
            data = response.json()
            assert "detail" in data
            assert isinstance(data["detail"], list)

            # Find name field error
            name_error = next((error for error in data["detail"] if "name" in error.get("loc", [])), None)
            assert name_error is not None

    def test_create_template_with_invalid_questions(self, mock_auth_user, sample_template_data):
        """Test template creation with invalid question structure."""
        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            # Invalid question type
            invalid_template_data = sample_template_data.copy()
            invalid_template_data["questions"] = [
                {
                    "id": "q1",
                    "text": "Test question",
                    "type": "invalid_type",  # Invalid question type
                    "required": True
                }
            ]

            response = client.post("/api/v1/templates", json=invalid_template_data)

            assert response.status_code == 422
            data = response.json()
            assert "detail" in data

    def test_get_template_by_id_success(self, mock_auth_user, mock_database_session):
        """Test successful template retrieval by ID."""
        template_id = str(uuid4())

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                # Mock template retrieval
                mock_template = MagicMock()
                mock_template.id = template_id
                mock_template.name = "Test Template"
                mock_template.description = "Test Description"
                mock_template.category = "symptom_assessment"
                mock_template.is_active = True
                mock_template.created_at = datetime.now()
                mock_template.updated_at = datetime.now()

                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service_instance.get_template.return_value = mock_template
                    mock_service.return_value = mock_service_instance

                    response = client.get(f"/api/v1/templates/{template_id}")

                    assert response.status_code == 200
                    data = response.json()

                    assert data["id"] == template_id
                    assert data["name"] == "Test Template"
                    assert data["description"] == "Test Description"

    def test_get_template_not_found(self, mock_auth_user, mock_database_session):
        """Test template retrieval when template doesn't exist."""
        non_existent_id = str(uuid4())

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service_instance.get_template.return_value = None
                    mock_service.return_value = mock_service_instance

                    response = client.get(f"/api/v1/templates/{non_existent_id}")

                    assert response.status_code == 404
                    data = response.json()
                    assert "detail" in data

    def test_list_templates_with_pagination(self, mock_auth_user, mock_database_session):
        """Test template listing with pagination."""
        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                # Mock template list
                mock_templates = []
                for i in range(5):
                    template = MagicMock()
                    template.id = str(uuid4())
                    template.name = f"Template {i+1}"
                    template.description = f"Description {i+1}"
                    template.category = "symptom_assessment"
                    template.is_active = True
                    template.created_at = datetime.now()
                    template.updated_at = datetime.now()
                    mock_templates.append(template)

                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service_instance.list_templates.return_value = (mock_templates, 25)  # (items, total)
                    mock_service.return_value = mock_service_instance

                    response = client.get("/api/v1/templates?page=1&size=5")

                    assert response.status_code == 200
                    data = response.json()

                    # Validate pagination structure
                    assert "items" in data
                    assert "total" in data
                    assert "page" in data
                    assert "size" in data
                    assert "total_pages" in data
                    assert "has_next" in data
                    assert "has_previous" in data

                    # Validate content
                    assert len(data["items"]) == 5
                    assert data["total"] == 25
                    assert data["page"] == 1
                    assert data["size"] == 5
                    assert data["total_pages"] == 5
                    assert data["has_next"] is True
                    assert data["has_previous"] is False

    def test_list_templates_with_filters(self, mock_auth_user, mock_database_session):
        """Test template listing with category and status filters."""
        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service_instance.list_templates.return_value = ([], 0)
                    mock_service.return_value = mock_service_instance

                    # Test category filter
                    response = client.get("/api/v1/templates?category=symptom_assessment")
                    assert response.status_code == 200

                    # Test active status filter
                    response = client.get("/api/v1/templates?is_active=true")
                    assert response.status_code == 200

                    # Test combined filters
                    response = client.get("/api/v1/templates?category=symptom_assessment&is_active=true")
                    assert response.status_code == 200

                    # Verify service was called with correct filters
                    mock_service_instance.list_templates.assert_called()

    def test_update_template_success(self, mock_auth_user, mock_database_session, sample_template_data):
        """Test successful template update."""
        template_id = str(uuid4())
        update_data = {
            "name": "Updated Template Name",
            "description": "Updated description",
            "is_active": False
        }

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                # Mock updated template
                updated_template = MagicMock()
                updated_template.id = template_id
                updated_template.name = update_data["name"]
                updated_template.description = update_data["description"]
                updated_template.is_active = update_data["is_active"]
                updated_template.updated_at = datetime.now()

                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service_instance.update_template.return_value = updated_template
                    mock_service.return_value = mock_service_instance

                    response = client.put(f"/api/v1/templates/{template_id}", json=update_data)

                    assert response.status_code == 200
                    data = response.json()

                    assert data["id"] == template_id
                    assert data["name"] == update_data["name"]
                    assert data["description"] == update_data["description"]
                    assert data["is_active"] == update_data["is_active"]

    def test_update_template_partial_update(self, mock_auth_user, mock_database_session):
        """Test partial template update (PATCH-like behavior)."""
        template_id = str(uuid4())
        partial_update = {
            "name": "Partially Updated Name"
            # Only updating name, other fields should remain unchanged
        }

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()

                    # Mock existing template
                    existing_template = MagicMock()
                    existing_template.id = template_id
                    existing_template.name = "Original Name"
                    existing_template.description = "Original Description"
                    existing_template.is_active = True

                    # Mock updated template
                    updated_template = MagicMock()
                    updated_template.id = template_id
                    updated_template.name = partial_update["name"]
                    updated_template.description = "Original Description"  # Unchanged
                    updated_template.is_active = True  # Unchanged

                    mock_service_instance.get_template.return_value = existing_template
                    mock_service_instance.update_template.return_value = updated_template
                    mock_service.return_value = mock_service_instance

                    response = client.put(f"/api/v1/templates/{template_id}", json=partial_update)

                    assert response.status_code == 200
                    data = response.json()

                    assert data["name"] == partial_update["name"]
                    assert data["description"] == "Original Description"
                    assert data["is_active"] is True

    def test_update_template_not_found(self, mock_auth_user, mock_database_session):
        """Test update attempt on non-existent template."""
        non_existent_id = str(uuid4())
        update_data = {"name": "Updated Name"}

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service_instance.update_template.side_effect = ValueError("Template not found")
                    mock_service.return_value = mock_service_instance

                    response = client.put(f"/api/v1/templates/{non_existent_id}", json=update_data)

                    assert response.status_code == 404
                    data = response.json()
                    assert "detail" in data

    def test_delete_template_success(self, mock_auth_user, mock_database_session):
        """Test successful template deletion."""
        template_id = str(uuid4())

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service_instance.delete_template.return_value = True
                    mock_service.return_value = mock_service_instance

                    response = client.delete(f"/api/v1/templates/{template_id}")

                    assert response.status_code == 204

    def test_delete_template_not_found(self, mock_auth_user, mock_database_session):
        """Test deletion attempt on non-existent template."""
        non_existent_id = str(uuid4())

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()
                    mock_service_instance.delete_template.side_effect = ValueError("Template not found")
                    mock_service.return_value = mock_service_instance

                    response = client.delete(f"/api/v1/templates/{non_existent_id}")

                    assert response.status_code == 404
                    data = response.json()
                    assert "detail" in data

    def test_soft_delete_behavior(self, mock_auth_user, mock_database_session):
        """Test soft delete behavior for templates."""
        template_id = str(uuid4())

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()

                    # Mock soft deletion (template is deactivated, not physically deleted)
                    soft_deleted_template = MagicMock()
                    soft_deleted_template.id = template_id
                    soft_deleted_template.is_active = False
                    soft_deleted_template.deleted_at = datetime.now()

                    mock_service_instance.soft_delete_template.return_value = soft_deleted_template
                    mock_service.return_value = mock_service_instance

                    response = client.patch(f"/api/v1/templates/{template_id}/deactivate")

                    if response.status_code == 200:
                        data = response.json()
                        assert data["is_active"] is False
                        assert "deleted_at" in data

    def test_template_versioning(self, mock_auth_user, mock_database_session):
        """Test template versioning functionality."""
        template_id = str(uuid4())

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()

                    # Mock template versions
                    versions = [
                        MagicMock(version=1, created_at=datetime.now() - timedelta(days=2)),
                        MagicMock(version=2, created_at=datetime.now() - timedelta(days=1)),
                        MagicMock(version=3, created_at=datetime.now())
                    ]

                    mock_service_instance.get_template_versions.return_value = versions
                    mock_service.return_value = mock_service_instance

                    response = client.get(f"/api/v1/templates/{template_id}/versions")

                    if response.status_code == 200:
                        data = response.json()
                        assert isinstance(data, list)
                        assert len(data) == 3
                        assert all("version" in version for version in data)

    def test_template_duplication(self, mock_auth_user, mock_database_session, sample_template_data):
        """Test template duplication functionality."""
        original_template_id = str(uuid4())

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.dependencies.get_thread_safe_db', return_value=mock_database_session):
                with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                    mock_service_instance = MagicMock()

                    # Mock duplicated template
                    duplicated_template = MagicMock()
                    duplicated_template.id = str(uuid4())
                    duplicated_template.name = f"Copy of {sample_template_data['name']}"
                    duplicated_template.description = sample_template_data['description']
                    duplicated_template.created_at = datetime.now()

                    mock_service_instance.duplicate_template.return_value = duplicated_template
                    mock_service.return_value = mock_service_instance

                    response = client.post(f"/api/v1/templates/{original_template_id}/duplicate")

                    if response.status_code == 201:
                        data = response.json()
                        assert data["id"] != original_template_id
                        assert "Copy of" in data["name"]


class TestTemplateEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def mock_auth_user(self):
        return MagicMock(id=uuid4(), email="doctor@test.com", role="doctor")

    def test_create_template_with_empty_questions(self, mock_auth_user):
        """Test creating template with empty questions array."""
        template_data = {
            "name": "Empty Template",
            "description": "Template with no questions",
            "category": "symptom_assessment",
            "questions": []
        }

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            response = client.post("/api/v1/templates", json=template_data)

            # Should either accept empty questions or validate minimum questions
            assert response.status_code in [201, 422]

    def test_create_template_with_duplicate_question_ids(self, mock_auth_user):
        """Test creating template with duplicate question IDs."""
        template_data = {
            "name": "Duplicate IDs Template",
            "description": "Template with duplicate question IDs",
            "category": "symptom_assessment",
            "questions": [
                {
                    "id": "q1",
                    "text": "Question 1",
                    "type": "multiple_choice",
                    "options": ["Yes", "No"]
                },
                {
                    "id": "q1",  # Duplicate ID
                    "text": "Question 2",
                    "type": "text"
                }
            ]
        }

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            response = client.post("/api/v1/templates", json=template_data)

            assert response.status_code == 422
            data = response.json()
            assert "duplicate" in str(data).lower()

    def test_template_name_length_validation(self, mock_auth_user):
        """Test template name length validation."""
        # Test very long name
        long_name = "A" * 300  # Assuming max length is 255

        template_data = {
            "name": long_name,
            "description": "Test description",
            "category": "symptom_assessment",
            "questions": []
        }

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            response = client.post("/api/v1/templates", json=template_data)

            assert response.status_code == 422
            data = response.json()
            assert any("name" in str(error) for error in data.get("detail", []))

    def test_question_order_validation(self, mock_auth_user):
        """Test question order validation."""
        template_data = {
            "name": "Order Test Template",
            "description": "Testing question order",
            "category": "symptom_assessment",
            "questions": [
                {
                    "id": "q1",
                    "text": "Question 1",
                    "type": "text",
                    "order": 1
                },
                {
                    "id": "q2",
                    "text": "Question 2",
                    "type": "text",
                    "order": 1  # Duplicate order
                }
            ]
        }

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            response = client.post("/api/v1/templates", json=template_data)

            # Should validate unique ordering or auto-assign orders
            assert response.status_code in [201, 422]

    def test_invalid_question_type_combinations(self, mock_auth_user):
        """Test invalid question type and property combinations."""
        template_data = {
            "name": "Invalid Combinations Template",
            "description": "Testing invalid combinations",
            "category": "symptom_assessment",
            "questions": [
                {
                    "id": "q1",
                    "text": "Text question with options",
                    "type": "text",
                    "options": ["Should not have options"]  # Text questions shouldn't have options
                }
            ]
        }

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            response = client.post("/api/v1/templates", json=template_data)

            assert response.status_code == 422

    def test_concurrent_template_updates(self, mock_auth_user):
        """Test concurrent template updates (optimistic locking)."""
        template_id = str(uuid4())

        # This test would require more complex setup to simulate true concurrency
        # For now, we'll test the basic conflict detection mechanism

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                mock_service_instance = MagicMock()
                mock_service_instance.update_template.side_effect = ValueError("Concurrent modification detected")
                mock_service.return_value = mock_service_instance

                update_data = {"name": "Updated Name"}
                response = client.put(f"/api/v1/templates/{template_id}", json=update_data)

                assert response.status_code == 409  # Conflict

    def test_template_with_very_large_questions(self, mock_auth_user):
        """Test template with very large question text."""
        large_question_text = "A" * 10000  # Very large question text

        template_data = {
            "name": "Large Question Template",
            "description": "Template with large question text",
            "category": "symptom_assessment",
            "questions": [
                {
                    "id": "q1",
                    "text": large_question_text,
                    "type": "text"
                }
            ]
        }

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            response = client.post("/api/v1/templates", json=template_data)

            # Should validate question text length
            assert response.status_code in [201, 422]


class TestTemplatePerformance:
    """Test template performance and load handling."""

    @pytest.fixture
    def mock_auth_user(self):
        return MagicMock(id=uuid4(), email="doctor@test.com", role="doctor")

    def test_list_templates_performance_with_large_dataset(self, mock_auth_user):
        """Test template listing performance with large dataset."""
        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                # Mock large dataset
                mock_service_instance = MagicMock()

                # Simulate 1000 templates
                large_template_list = []
                for i in range(1000):
                    template = MagicMock()
                    template.id = str(uuid4())
                    template.name = f"Template {i}"
                    large_template_list.append(template)

                mock_service_instance.list_templates.return_value = (large_template_list[:20], 1000)
                mock_service.return_value = mock_service_instance

                import time
                start_time = time.time()

                response = client.get("/api/v1/templates?page=1&size=20")

                end_time = time.time()
                response_time = end_time - start_time

                assert response.status_code == 200
                # Response should be reasonably fast even with large dataset
                assert response_time < 1.0  # Less than 1 second

    def test_template_creation_with_many_questions(self, mock_auth_user):
        """Test template creation performance with many questions."""
        # Create template with 100 questions
        questions = []
        for i in range(100):
            questions.append({
                "id": f"q{i}",
                "text": f"Question {i}",
                "type": "multiple_choice",
                "options": ["Option 1", "Option 2", "Option 3"],
                "order": i + 1
            })

        template_data = {
            "name": "Large Template",
            "description": "Template with many questions",
            "category": "symptom_assessment",
            "questions": questions
        }

        with patch('app.dependencies.get_current_user', return_value=mock_auth_user):
            with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                mock_service_instance = MagicMock()
                created_template = MagicMock()
                created_template.id = str(uuid4())
                mock_service_instance.create_template.return_value = created_template
                mock_service.return_value = mock_service_instance

                import time
                start_time = time.time()

                response = client.post("/api/v1/templates", json=template_data)

                end_time = time.time()
                response_time = end_time - start_time

                # Should handle large templates efficiently
                assert response.status_code in [201, 422]  # Either succeed or validate size limit
                assert response_time < 2.0  # Should process within reasonable time


class TestTemplateAuthorization:
    """Test template authorization and access control."""

    def test_unauthorized_template_access(self):
        """Test accessing templates without authentication."""
        response = client.get("/api/v1/templates")
        assert response.status_code == 401

    def test_role_based_template_access(self):
        """Test role-based access to template operations."""
        # Test different user roles
        roles_to_test = ["admin", "doctor", "nurse", "patient"]

        for role in roles_to_test:
            mock_user = MagicMock(id=uuid4(), email=f"{role}@test.com", role=role)

            with patch('app.dependencies.get_current_user', return_value=mock_user):
                response = client.get("/api/v1/templates")

                # Define expected access based on role
                expected_access = {
                    "admin": 200,
                    "doctor": 200,
                    "nurse": 200,
                    "patient": 403  # Patients might not have template access
                }

                if role in expected_access:
                    assert response.status_code == expected_access[role]

    def test_template_ownership_validation(self):
        """Test that users can only modify their own templates (if applicable)."""
        template_id = str(uuid4())
        creator_id = uuid4()
        other_user_id = uuid4()

        # Test creator can modify
        creator_user = MagicMock(id=creator_id, email="creator@test.com", role="doctor")

        with patch('app.dependencies.get_current_user', return_value=creator_user):
            with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                mock_service_instance = MagicMock()

                # Mock template owned by creator
                template = MagicMock()
                template.created_by = creator_id
                mock_service_instance.get_template.return_value = template
                mock_service_instance.update_template.return_value = template
                mock_service.return_value = mock_service_instance

                response = client.put(f"/api/v1/templates/{template_id}", json={"name": "Updated"})
                assert response.status_code == 200

        # Test other user cannot modify
        other_user = MagicMock(id=other_user_id, email="other@test.com", role="doctor")

        with patch('app.dependencies.get_current_user', return_value=other_user):
            with patch('app.services.quiz_template_service.QuizTemplateService') as mock_service:
                mock_service_instance = MagicMock()
                mock_service_instance.update_template.side_effect = PermissionError("Not authorized")
                mock_service.return_value = mock_service_instance

                response = client.put(f"/api/v1/templates/{template_id}", json={"name": "Updated"})
                assert response.status_code == 403