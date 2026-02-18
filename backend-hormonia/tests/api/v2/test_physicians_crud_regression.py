"""
Regression tests for physicians CRUD boolean filters.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v2.routers.physicians import crud as physicians_crud
from app.models.user import User, UserRole
from app.schemas.v2.physicians import PhysicianStatus


@pytest.mark.asyncio
async def test_list_physicians_inactive_status_returns_only_inactive(db_session):
    """Regression for `not User.is_active`: inactive filter must return inactive rows."""
    marker = f"inactive-regression-{uuid4().hex[:8]}"

    active_physician = User(
        email=f"{marker}-active@test.com",
        full_name="Dr. Active Regression",
        role=UserRole.DOCTOR,
        is_active=True,
        firebase_uid=f"{marker}-active",
    )
    inactive_physician = User(
        email=f"{marker}-inactive@test.com",
        full_name="Dr. Inactive Regression",
        role=UserRole.DOCTOR,
        is_active=False,
        firebase_uid=f"{marker}-inactive",
    )
    db_session.add(active_physician)
    db_session.add(inactive_physician)
    db_session.commit()
    db_session.refresh(active_physician)
    db_session.refresh(inactive_physician)

    result = await physicians_crud.list_physicians(
        request=SimpleNamespace(state=SimpleNamespace()),
        db=db_session,
        current_user={"id": str(uuid4()), "role": UserRole.ADMIN.value},
        pagination={"cursor_data": None, "limit": 50},
        fields=None,
        include=None,
        specialty=None,
        status=PhysicianStatus.INACTIVE,
        workload=None,
        min_patients=None,
        max_patients=None,
        search=marker,
    )

    returned_ids = {row["id"] for row in result["data"]}
    assert str(inactive_physician.id) in returned_ids
    assert str(active_physician.id) not in returned_ids
