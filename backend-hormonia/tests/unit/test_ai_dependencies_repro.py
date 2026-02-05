import pytest
from fastapi import HTTPException
from app.api.v2.routers.ai.dependencies import verify_physician_or_admin
from app.models.user import UserRole

@pytest.mark.asyncio
async def test_verify_physician_or_admin_dict_success():
    """
    Verification test for fix of AttributeError: 'dict' object has no attribute 'role'
    """
    # Simulate current_user as a dict
    current_user = {
        "id": "test-uuid",
        "role": "doctor"
    }
    
    # This should now succeed and return the dict
    result = await verify_physician_or_admin(current_user=current_user)
    assert result == current_user

@pytest.mark.asyncio
async def test_verify_physician_or_admin_unauthorized():
    """
    Verify it still raises 403 for unauthorized roles in dict format
    """
    current_user = {
        "id": "test-uuid",
        "role": "patient"
    }
    
    with pytest.raises(HTTPException) as excinfo:
        await verify_physician_or_admin(current_user=current_user)
    
    assert excinfo.value.status_code == 403