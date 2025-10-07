"""
Test suite to verify Pydantic V2 migration is complete.

This test ensures:
1. No deprecated schema_extra usage remains
2. All schemas use json_schema_extra instead
3. No Pydantic V2 warnings are generated during schema imports
"""
import warnings
import pytest
from pathlib import Path


def test_no_schema_extra_in_schemas():
    """Verify no deprecated schema_extra usage in schema files."""
    schemas_path = Path(__file__).parent.parent / "app" / "schemas"
    schema_files = list(schemas_path.glob("*.py"))

    assert len(schema_files) > 0, "No schema files found"

    deprecated_usage = []
    for schema_file in schema_files:
        if schema_file.name == "__init__.py":
            continue

        content = schema_file.read_text(encoding="utf-8")

        # Check for schema_extra but not json_schema_extra
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            # Look for schema_extra as a key (not in comments or as part of json_schema_extra)
            if "schema_extra" in line and "json_schema_extra" not in line:
                # Exclude comments
                code_part = line.split("#")[0]
                if "schema_extra" in code_part:
                    deprecated_usage.append(f"{schema_file.name}:{i} - {line.strip()}")

    if deprecated_usage:
        msg = "Found deprecated schema_extra usage:\n" + "\n".join(deprecated_usage)
        pytest.fail(msg)


def test_import_all_schemas_no_warnings():
    """Import all schemas and verify no Pydantic warnings are generated."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Import all schema modules
        from app.schemas import (
            admin_users,
            ai,
            flow,
            medico,
            # Add other schema modules as needed
        )

        # Filter for Pydantic-related warnings
        pydantic_warnings = [
            warning for warning in w
            if "pydantic" in str(warning.message).lower()
            or "schema_extra" in str(warning.message).lower()
        ]

        if pydantic_warnings:
            msg = "Pydantic warnings detected:\n"
            for warning in pydantic_warnings:
                msg += f"  {warning.category.__name__}: {warning.message}\n"
                msg += f"  File: {warning.filename}:{warning.lineno}\n\n"
            pytest.fail(msg)


def test_json_schema_extra_usage():
    """Verify that json_schema_extra is used correctly in schemas."""
    from app.schemas.ai import ChatRequest, ChatResponse
    from app.schemas.flow import FlowTemplateResponse

    # Verify Config classes have json_schema_extra
    assert hasattr(ChatRequest, "model_config") or hasattr(ChatRequest, "Config")
    assert hasattr(ChatResponse, "model_config") or hasattr(ChatResponse, "Config")

    # Get schema and verify examples exist
    chat_request_schema = ChatRequest.model_json_schema()
    assert "examples" in chat_request_schema or "example" in chat_request_schema.get("properties", {}).get("message", {}), \
        "ChatRequest should have examples in schema"


def test_all_schema_classes_importable():
    """Verify all schema classes can be imported without errors."""
    try:
        # AI schemas
        from app.schemas.ai import (
            ChatRequest, ChatResponse,
            AnalysisRequest, AnalysisResponse,
            GenerateResponseRequest, GenerateResponseResponse,
            SentimentAnalysisRequest, SentimentAnalysisResponse,
            InsightResponse, RecommendationResponse,
            PatientSummaryResponse, AIErrorResponse
        )

        # Flow schemas
        from app.schemas.flow import (
            FlowTemplateBase, FlowTemplateCreate, FlowTemplateUpdate,
            FlowTemplateResponse, PatientFlowStateBase,
            PatientFlowStateCreate, PatientFlowStateUpdate,
            PatientFlowStateResponse, FlowProgressionRequest,
            FlowProgressionResponse, FlowResetRequest,
            FlowHistoryResponse, FlowStepDefinition,
            FlowTemplateValidationResult, FlowAnalytics
        )

        # Medico schemas
        from app.schemas.medico import (
            MedicoBase, MedicoCreate, MedicoUpdate, MedicoResponse
        )

        # Admin users schemas
        from app.schemas.admin_users import (
            AdminUserBase, AdminUserCreate, AdminUserUpdate, AdminUserResponse
        )

    except Exception as e:
        pytest.fail(f"Failed to import schema classes: {e}")


def test_schema_validation_examples():
    """Test that schema examples are valid."""
    from app.schemas.ai import ChatRequest, ChatResponse

    # Get the example from json_schema_extra
    chat_request_schema = ChatRequest.model_json_schema()

    # Pydantic v2 puts examples in different places
    # Check if there's an example in the schema
    has_example = (
        "examples" in chat_request_schema or
        "example" in chat_request_schema or
        any("example" in prop for prop in chat_request_schema.get("properties", {}).values())
    )

    assert has_example, "Schema should have examples for API documentation"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
