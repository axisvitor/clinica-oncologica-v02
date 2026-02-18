import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from app.api.v2.routers.flow_templates import list_flow_templates
from app.api.v2.routers.template_versions import rollback_template_version
from app.schemas.v2.templates import TemplateVersionRollbackRequest, FlowTemplateV2List
from app.models.flow import FlowTemplateVersion, FlowKind
from starlette.requests import Request
from fastapi import HTTPException

from app.utils.timezone import now_sao_paulo
@pytest.mark.asyncio
async def test_list_flow_templates_serialization_error():
    """
    Reproduction test for 'FlowTemplateVersion' object has no attribute 'template_metadata'
    during listing.
    """
    # Mock db session
    mock_db = MagicMock()
    
    # Mock FlowTemplateVersion object
    mock_template = MagicMock(spec=FlowTemplateVersion)
    mock_template.id = uuid4()
    mock_template.kind_id = uuid4()
    mock_template.version_number = 1
    mock_template.template_name = "Test Template"
    mock_template.description = "Test Description"
    mock_template.messages = {}
    mock_template.metadata_json = {"key": "val"}
    # Ensure template_metadata does NOT exist
    del mock_template.template_metadata
    
    mock_template.is_active = True
    mock_template.is_draft = False
    mock_template.published_at = now_sao_paulo()
    mock_template.created_at = now_sao_paulo()
    mock_template.updated_at = now_sao_paulo()
    mock_template.created_by = uuid4()
    
    # Mock Kind
    mock_kind = MagicMock(spec=FlowKind)
    mock_kind.kind_key = "onboarding"
    mock_kind.display_name = "Onboarding"
    mock_template.kind = mock_kind
    
    # Mock query result
    mock_query = mock_db.query.return_value
    mock_query.options.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = [mock_template]
    
    # Mock request and user
    mock_request = MagicMock(spec=Request)
    mock_user = {"id": str(uuid4()), "role": "admin"}
    
    # Run list_flow_templates
    result = await list_flow_templates(
        request=mock_request,
        db=mock_db,
        current_user=mock_user,
        cursor=None,
        limit=20,
        is_active=None,
        is_draft=None,
        kind_key=None,
        fields=None,
        include=None
    )
    
    assert result["data"] is not None
    assert len(result["data"]) == 1
    
    print(f"DEBUG keys: {result['data'][0].keys()}")
    
    # Verify schema validation (simulate FastAPI response validation)
    # This will fail if serializer produces 'metadata_json' but schema expects 'metadata'
    try:
        validated = FlowTemplateV2List(**result)
    except Exception as e:
        pytest.fail(f"Response validation failed: {e}")

@pytest.mark.asyncio
async def test_rollback_template_version_attribute_error():
    """
    Reproduction test for 'FlowTemplateVersion' object has no attribute 'template_metadata'
    during rollback.
    """
    # Mock db session
    mock_db = MagicMock()
    
    # Mock FlowTemplateVersion object (Source for rollback)
    mock_template = MagicMock(spec=FlowTemplateVersion)
    mock_template.id = uuid4()
    mock_template.kind_id = uuid4()
    mock_template.version_number = 1
    mock_template.template_name = "Test Template"
    mock_template.messages = {}
    mock_template.metadata_json = {"key": "value"}
    # Ensure template_metadata does NOT exist
    del mock_template.template_metadata
    
    # Mock query result
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.options.return_value = mock_query
    mock_query.scalar.return_value = 1  # Latest version number

    # First .first(): source version lookup
    # Second .first(): reload rollback version with relationship
    mock_rollback = MagicMock(spec=FlowTemplateVersion)
    mock_rollback.id = uuid4()
    mock_rollback.template_name = "Test Template (Rollback)"
    mock_rollback.metadata_json = {"key": "value"}
    mock_query.first.side_effect = [mock_template, mock_rollback]
    
    # Mock request and user
    mock_request = MagicMock(spec=Request)
    mock_user = {"id": str(uuid4()), "role": "admin"}
    
    rollback_data = TemplateVersionRollbackRequest(reason="Test", set_as_active=False)
    
    # Should SUCCEED now that we fixed it
    result = await rollback_template_version(
        request=mock_request,
        template_id=mock_template.id,
        rollback_data=rollback_data,
        db=mock_db,
        current_user=mock_user
    )
    
    assert result["template_name"] == "Test Template (Rollback)"
