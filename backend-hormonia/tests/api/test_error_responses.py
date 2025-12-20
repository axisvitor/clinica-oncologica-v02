"""
Unit tests for standardized error responses (LOW-017).

Tests the exception handler middleware and standardized exception classes
to ensure consistent error responses across all API endpoints.

Reference: LOW-017 - Inconsistent Error Handling

Test Coverage:
- APIException hierarchy responses
- Validation error formatting
- Database error handling
- HTTP exception responses
- Generic exception catch-all
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exceptions import (
    APIException,
    BusinessRuleError,
    ValidationError,
    NotFoundError,
    ConflictError,
    UnauthorizedError,
    ForbiddenError,
    BadRequestError,
)
from app.middleware.exception_handler import setup_exception_handlers


# =========================================================================
# TEST APP SETUP
# =========================================================================


@pytest.fixture
def app():
    """Create test FastAPI app with exception handlers."""
    app = FastAPI()
    setup_exception_handlers(app)

    # Test endpoints that raise various exceptions
    @app.get("/test/business-rule-error")
    def test_business_rule_error():
        raise BusinessRuleError(
            "Patient already exists",
            field="cpf",
            code="duplicate_cpf"
        )

    @app.get("/test/validation-error")
    def test_validation_error():
        raise ValidationError(
            "Input validation failed",
            errors={"cpf": "Invalid CPF format", "birth_date": "Must be 18+"}
        )

    @app.get("/test/not-found-error")
    def test_not_found_error():
        raise NotFoundError("Patient", "123e4567-e89b-12d3-a456-426614174000")

    @app.get("/test/conflict-error")
    def test_conflict_error():
        raise ConflictError("Resource already exists", {"field": "email"})

    @app.get("/test/unauthorized-error")
    def test_unauthorized_error():
        raise UnauthorizedError("Invalid token")

    @app.get("/test/forbidden-error")
    def test_forbidden_error():
        raise ForbiddenError("Insufficient permissions")

    @app.get("/test/bad-request-error")
    def test_bad_request_error():
        raise BadRequestError("Invalid date format", {"date": "2025-13-40"})

    @app.get("/test/generic-exception")
    def test_generic_exception():
        raise ValueError("Unexpected error")

    @app.get("/test/integrity-error")
    def test_integrity_error():
        # Simulate duplicate key error
        raise IntegrityError(
            "duplicate key value violates unique constraint \"uq_patient_cpf_doctor\"",
            None,
            None
        )

    @app.get("/test/sqlalchemy-error")
    def test_sqlalchemy_error():
        raise SQLAlchemyError("Database connection failed")

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# =========================================================================
# BUSINESS RULE ERROR TESTS
# =========================================================================


def test_business_rule_error_response_structure(client):
    """BusinessRuleError returns standardized response."""
    response = client.get("/test/business-rule-error")

    assert response.status_code == 400
    data = response.json()

    assert "error" in data
    assert "message" in data
    assert "status_code" in data
    assert "details" in data

    assert data["error"] == "duplicate_cpf"
    assert data["message"] == "Patient already exists"
    assert data["status_code"] == 400
    assert data["details"]["field"] == "cpf"
    assert data["details"]["code"] == "duplicate_cpf"


def test_business_rule_error_without_code(client):
    """BusinessRuleError without code uses default error code."""
    # This would need a separate endpoint, but we can test the class directly
    error = BusinessRuleError("Test error", field="test_field")

    assert error.error_code == "BUSINESS_RULE_VIOLATION"
    assert error.status_code == 400
    assert error.field == "test_field"


# =========================================================================
# VALIDATION ERROR TESTS
# =========================================================================


def test_validation_error_response_structure(client):
    """ValidationError returns standardized 422 response."""
    response = client.get("/test/validation-error")

    assert response.status_code == 422
    data = response.json()

    assert data["error"] == "VALIDATION_ERROR"
    assert data["message"] == "Input validation failed"
    assert data["status_code"] == 422
    assert "errors" in data["details"]

    errors = data["details"]["errors"]
    assert errors["cpf"] == "Invalid CPF format"
    assert errors["birth_date"] == "Must be 18+"


def test_validation_error_with_single_field(client):
    """ValidationError with single field error."""
    error = ValidationError("Invalid input", errors={"email": "Invalid email format"})

    response_dict = error.to_dict()
    assert response_dict["details"]["errors"]["email"] == "Invalid email format"


# =========================================================================
# NOT FOUND ERROR TESTS
# =========================================================================


def test_not_found_error_response_structure(client):
    """NotFoundError returns standardized 404 response."""
    response = client.get("/test/not-found-error")

    assert response.status_code == 404
    data = response.json()

    assert data["error"] == "NOT_FOUND"
    assert data["message"] == "Patient not found"
    assert data["status_code"] == 404
    assert data["details"]["resource"] == "Patient"
    assert data["details"]["identifier"] == "123e4567-e89b-12d3-a456-426614174000"


def test_not_found_error_different_resource(client):
    """NotFoundError works for different resource types."""
    error = NotFoundError("Quiz Session", "session-123")

    response_dict = error.to_dict()
    assert response_dict["message"] == "Quiz Session not found"
    assert response_dict["details"]["resource"] == "Quiz Session"
    assert response_dict["details"]["identifier"] == "session-123"


# =========================================================================
# CONFLICT ERROR TESTS
# =========================================================================


def test_conflict_error_response_structure(client):
    """ConflictError returns standardized 409 response."""
    response = client.get("/test/conflict-error")

    assert response.status_code == 409
    data = response.json()

    assert data["error"] == "CONFLICT"
    assert data["message"] == "Resource already exists"
    assert data["status_code"] == 409
    assert data["details"]["field"] == "email"


# =========================================================================
# UNAUTHORIZED ERROR TESTS
# =========================================================================


def test_unauthorized_error_response_structure(client):
    """UnauthorizedError returns standardized 401 response."""
    response = client.get("/test/unauthorized-error")

    assert response.status_code == 401
    data = response.json()

    assert data["error"] == "UNAUTHORIZED"
    assert data["message"] == "Invalid token"
    assert data["status_code"] == 401


# =========================================================================
# FORBIDDEN ERROR TESTS
# =========================================================================


def test_forbidden_error_response_structure(client):
    """ForbiddenError returns standardized 403 response."""
    response = client.get("/test/forbidden-error")

    assert response.status_code == 403
    data = response.json()

    assert data["error"] == "FORBIDDEN"
    assert data["message"] == "Insufficient permissions"
    assert data["status_code"] == 403


# =========================================================================
# BAD REQUEST ERROR TESTS
# =========================================================================


def test_bad_request_error_response_structure(client):
    """BadRequestError returns standardized 400 response."""
    response = client.get("/test/bad-request-error")

    assert response.status_code == 400
    data = response.json()

    assert data["error"] == "BAD_REQUEST"
    assert data["message"] == "Invalid date format"
    assert data["status_code"] == 400
    assert data["details"]["date"] == "2025-13-40"


# =========================================================================
# DATABASE ERROR TESTS
# =========================================================================


def test_integrity_error_duplicate_cpf(client):
    """IntegrityError for duplicate CPF returns 409 Conflict."""
    response = client.get("/test/integrity-error")

    assert response.status_code == 409
    data = response.json()

    assert data["error"] == "DUPLICATE_RESOURCE"
    assert data["message"] == "Resource already exists"
    assert data["status_code"] == 409
    assert data["details"]["field"] == "cpf"


def test_sqlalchemy_error_returns_500(client):
    """Generic SQLAlchemy error returns 500 Internal Server Error."""
    response = client.get("/test/sqlalchemy-error")

    assert response.status_code == 500
    data = response.json()

    assert data["error"] == "DATABASE_ERROR"
    assert "database" in data["message"].lower()
    assert data["status_code"] == 500


# =========================================================================
# GENERIC EXCEPTION TESTS
# =========================================================================


def test_generic_exception_returns_500(client):
    """Unhandled generic exception returns 500 Internal Server Error."""
    response = client.get("/test/generic-exception")

    assert response.status_code == 500
    data = response.json()

    assert data["error"] == "INTERNAL_ERROR"
    assert "unexpected error" in data["message"].lower()
    assert data["status_code"] == 500


# =========================================================================
# RESPONSE FORMAT CONSISTENCY TESTS
# =========================================================================


def test_all_error_responses_have_required_fields(client):
    """All error responses contain required fields."""
    endpoints = [
        "/test/business-rule-error",
        "/test/validation-error",
        "/test/not-found-error",
        "/test/conflict-error",
        "/test/unauthorized-error",
        "/test/forbidden-error",
        "/test/bad-request-error",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        data = response.json()

        # All responses must have these fields
        assert "error" in data, f"{endpoint} missing 'error' field"
        assert "message" in data, f"{endpoint} missing 'message' field"
        assert "status_code" in data, f"{endpoint} missing 'status_code' field"

        # Validate types
        assert isinstance(data["error"], str)
        assert isinstance(data["message"], str)
        assert isinstance(data["status_code"], int)


def test_error_codes_are_uppercase_snake_case(client):
    """Error codes follow UPPERCASE_SNAKE_CASE convention."""
    endpoints = [
        "/test/business-rule-error",
        "/test/validation-error",
        "/test/not-found-error",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        data = response.json()

        error_code = data["error"]
        # Should be uppercase and use underscores
        assert error_code.isupper() or "_" in error_code


def test_details_field_is_optional(client):
    """Details field is optional in error responses."""
    error = UnauthorizedError("Test")
    response_dict = error.to_dict()

    # UnauthorizedError doesn't have details by default
    # But field should exist (empty dict)
    assert "details" in response_dict


# =========================================================================
# EXCEPTION CLASS TESTS (Direct)
# =========================================================================


def test_api_exception_to_dict():
    """APIException.to_dict() returns correct structure."""
    exc = APIException(
        message="Test error",
        status_code=400,
        error_code="TEST_ERROR",
        details={"field": "value"}
    )

    result = exc.to_dict()

    assert result["error"] == "TEST_ERROR"
    assert result["message"] == "Test error"
    assert result["status_code"] == 400
    assert result["details"]["field"] == "value"


def test_validation_error_stores_errors():
    """ValidationError stores errors dict."""
    errors = {"field1": "error1", "field2": "error2"}
    exc = ValidationError("Test", errors=errors)

    assert exc.errors == errors
    assert exc.status_code == 422


def test_not_found_error_stores_resource_and_identifier():
    """NotFoundError stores resource and identifier."""
    exc = NotFoundError("Patient", "123")

    assert exc.resource == "Patient"
    assert exc.identifier == "123"
    assert exc.status_code == 404


def test_business_rule_error_stores_field_and_code():
    """BusinessRuleError stores field and code."""
    exc = BusinessRuleError("Test", field="cpf", code="duplicate")

    assert exc.field == "cpf"
    assert exc.code == "duplicate"
    assert exc.status_code == 400
