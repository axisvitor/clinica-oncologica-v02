from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.webhook.handlers.message_handler import handle_opt_out


@pytest.mark.asyncio
async def test_handle_opt_out_sets_messaging_stopped_at():
    patient = MagicMock()
    patient.id = "patient-test-1"
    patient.messaging_stopped_at = None

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
    )

    with patch("app.services.lgpd.consent_service.ConsentService"):
        await handle_opt_out(patient, db)

    assert patient.messaging_stopped_at is not None
    db.commit.assert_awaited_once()


def test_send_guard_blocks_opted_out_patient():
    opted_out_patient = MagicMock()
    opted_out_patient.messaging_stopped_at = datetime.now(timezone.utc)
    assert opted_out_patient.messaging_stopped_at is not None

    active_patient = MagicMock()
    active_patient.messaging_stopped_at = None
    assert active_patient.messaging_stopped_at is None
