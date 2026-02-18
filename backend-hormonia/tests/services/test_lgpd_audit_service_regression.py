"""
Regression tests for LGPD audit service boolean SQLAlchemy filters.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.models.lgpd_audit import LGPDAuditLog, LGPDActionType, LGPDDataCategory
from app.services.lgpd.consent_service import LGPDAuditService


@pytest.mark.asyncio
async def test_get_failed_access_attempts_filters_success_false_only(
    db_session, monkeypatch
):
    """`success=False` rows must be returned; successful rows must be excluded."""
    frozen_now = datetime(2026, 1, 1, 12, 0, 0)
    monkeypatch.setattr(
        "app.services.lgpd.consent_service.now_sao_paulo", lambda: frozen_now
    )

    failed_log = LGPDAuditLog(
        action=LGPDActionType.ACCESS_DENIED.value,
        data_category=LGPDDataCategory.HEALTH.value,
        resource_type="patient",
        resource_id=str(uuid4()),
        purpose="failed access attempt",
        legal_basis="security_review",
        success=False,
        created_at=frozen_now - timedelta(hours=1),
    )
    success_log = LGPDAuditLog(
        action=LGPDActionType.VIEW.value,
        data_category=LGPDDataCategory.HEALTH.value,
        resource_type="patient",
        resource_id=str(uuid4()),
        purpose="successful access",
        legal_basis="consent",
        success=True,
        created_at=frozen_now - timedelta(hours=1),
    )

    db_session.add(failed_log)
    db_session.add(success_log)
    db_session.commit()
    db_session.refresh(failed_log)
    db_session.refresh(success_log)

    service = LGPDAuditService(db_session)
    failed_attempts = await service.get_failed_access_attempts(hours=24, limit=50)

    returned_ids = {entry.id for entry in failed_attempts}
    assert failed_log.id in returned_ids
    assert success_log.id not in returned_ids
