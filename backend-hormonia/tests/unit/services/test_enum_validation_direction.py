from __future__ import annotations

import pytest

from app.models.message import MessageDirection
from app.services.enum_validation import EnumValidationError, MessageDirectionValidator


def test_validate_message_direction_normalizes_case() -> None:
    assert MessageDirectionValidator.validate("OUTBOUND") == MessageDirection.OUTBOUND
    assert MessageDirectionValidator.validate("inbound") == MessageDirection.INBOUND


def test_validate_message_direction_rejects_invalid_values() -> None:
    with pytest.raises(EnumValidationError):
        MessageDirectionValidator.validate("legacy_outbound")
