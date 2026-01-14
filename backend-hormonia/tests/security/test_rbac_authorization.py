"""
RBAC Authorization Security Tests

Tests verify that Role-Based Access Control (RBAC) is properly enforced:
1. Admin-only endpoints reject doctor users
2. Doctor endpoints reject unauthenticated users
3. Role escalation is prevented
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from uuid import uuid4

from app.api.v2.routers.admin.dependencies import get_admin_user
from app.dependencies import RequestContext
from app.main import app
from app.models.user import UserRole
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_current_user_object_from_session,
    get_permissions_for_role,
)
from tests.conftest import create_test_user


def _build_session_user(user) -> dict:
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": role,
        "is_active": True,
        "permissions": get_permissions_for_role(role),
    }


@pytest.fixture
def admin_user(db):
    return create_test_user(
        db,
        email="admin_rbac@test.com",
        full_name="Admin RBAC User",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def doctor_user(db):
    return create_test_user(
        db,
        email="doctor_rbac@test.com",
        full_name="Doctor RBAC User",
        role=UserRole.DOCTOR,
    )


@pytest.fixture
def admin_headers(client: TestClient, admin_user):
    session_user = _build_session_user(admin_user)

    async def _override_session_user(*args, **kwargs):
        return session_user

    async def _override_user_object(*args, **kwargs):
        return admin_user

    app.dependency_overrides[get_current_user_from_session] = _override_session_user
    app.dependency_overrides[get_current_user_object_from_session] = _override_user_object
    headers = {"Authorization": f"Bearer session_{uuid4().hex}"}
    yield headers
    app.dependency_overrides.pop(get_current_user_from_session, None)
    app.dependency_overrides.pop(get_current_user_object_from_session, None)


@pytest.fixture
def doctor_headers(client: TestClient, doctor_user):
    session_user = _build_session_user(doctor_user)

    async def _override_session_user(*args, **kwargs):
        return session_user

    async def _override_user_object(*args, **kwargs):
        return doctor_user

    app.dependency_overrides[get_current_user_from_session] = _override_session_user
    app.dependency_overrides[get_current_user_object_from_session] = _override_user_object
    headers = {"Authorization": f"Bearer session_{uuid4().hex}"}
    yield headers
    app.dependency_overrides.pop(get_current_user_from_session, None)
    app.dependency_overrides.pop(get_current_user_object_from_session, None)


class TestRBACAuthorization:
    """Test suite for RBAC authorization security."""

    @pytest.mark.asyncio
    async def test_admin_endpoints_reject_doctor(self, doctor_user):
        with pytest.raises(HTTPException) as exc_info:
            await get_admin_user(current_user=doctor_user, context=RequestContext())
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_endpoints_accept_admin(self, admin_user):
        admin = await get_admin_user(current_user=admin_user, context=RequestContext())
        assert admin == admin_user

    def test_doctor_endpoints_reject_unauthenticated(self, client: TestClient):
        response = client.get("/api/v2/physicians/patients")
        assert response.status_code == 401

    def test_role_escalation_prevention(self, client: TestClient, doctor_headers):
        response = client.post(
            "/api/v2/admin/users",
            headers=doctor_headers,
            json={
                "email": "attacker@example.com",
                "role": "admin",
                "name": "Attacker",
            },
        )
        assert response.status_code in [401, 403, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
