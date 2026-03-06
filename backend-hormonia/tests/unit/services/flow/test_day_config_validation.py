from __future__ import annotations

import pytest

from app.services.flow.config_validation import (
    DayConfigValidationError,
    validate_day_config,
)


def _valid_day_config() -> dict:
    return {
        "day": 1,
        "send_mode": "wait_each",
        "messages": [
            {
                "content": "Hello {patient_name}!",
                "expects_response": True,
                "delay_seconds": 3.0,
            }
        ],
    }


def test_validate_day_config_accepts_valid_messages() -> None:
    day_config = _valid_day_config()

    result = validate_day_config(
        day_config,
        flow_kind="onboarding",
        day_number=1,
    )

    assert result == day_config


def test_validate_day_config_rejects_non_dict_configs() -> None:
    with pytest.raises(DayConfigValidationError) as exc_info:
        validate_day_config(["not", "a", "dict"])

    assert "day_config must be a dict" in str(exc_info.value)
    assert exc_info.value.errors == ["day_config must be a dict"]


def test_validate_day_config_requires_messages_key() -> None:
    day_config = {"day": 1, "send_mode": "single"}

    with pytest.raises(DayConfigValidationError) as exc_info:
        validate_day_config(day_config)

    assert "'messages' key is missing" in str(exc_info.value)
    assert exc_info.value.errors == ["'messages' key is missing from day_config"]


def test_validate_day_config_requires_messages_list() -> None:
    day_config = {"day": 1, "send_mode": "single", "messages": "hello"}

    with pytest.raises(DayConfigValidationError) as exc_info:
        validate_day_config(day_config)

    assert "'messages' must be a list" in str(exc_info.value)
    assert exc_info.value.errors == ["'messages' must be a list, got str"]


def test_validate_day_config_rejects_empty_messages_list() -> None:
    day_config = {"day": 1, "send_mode": "single", "messages": []}

    with pytest.raises(DayConfigValidationError) as exc_info:
        validate_day_config(day_config)

    assert "messages list is empty" in str(exc_info.value)
    assert exc_info.value.errors == ["'messages' list is empty - no messages to send"]


def test_validate_day_config_requires_message_content() -> None:
    day_config = {
        "day": 1,
        "send_mode": "single",
        "messages": [{}],
    }

    with pytest.raises(DayConfigValidationError) as exc_info:
        validate_day_config(day_config)

    assert "messages[0]" in str(exc_info.value)
    assert exc_info.value.errors == ["messages[0] missing required 'content' key"]


def test_validate_day_config_requires_content_to_be_string() -> None:
    day_config = {
        "day": 1,
        "send_mode": "single",
        "messages": [{"content": 123}],
    }

    with pytest.raises(DayConfigValidationError) as exc_info:
        validate_day_config(day_config)

    assert "messages[0].content must be a string" in str(exc_info.value)
    assert exc_info.value.errors == ["messages[0].content must be a string, got int"]


def test_validate_day_config_rejects_blank_content() -> None:
    day_config = {
        "day": 1,
        "send_mode": "single",
        "messages": [{"content": "   "}],
    }

    with pytest.raises(DayConfigValidationError) as exc_info:
        validate_day_config(day_config)

    assert "messages[0].content is empty" in str(exc_info.value)
    assert exc_info.value.errors == ["messages[0].content is empty"]


def test_validate_day_config_rejects_invalid_send_mode() -> None:
    day_config = {
        "day": 1,
        "send_mode": "invalid-mode",
        "messages": [{"content": "Hello"}],
    }

    with pytest.raises(DayConfigValidationError) as exc_info:
        validate_day_config(day_config)

    assert "Invalid send_mode 'invalid-mode'" in str(exc_info.value)
    assert "sequential_auto" in str(exc_info.value)


def test_validate_day_config_accepts_optional_fields() -> None:
    day_config = {
        "day": 1,
        "title": "Day 1 Greeting",
        "description": "Warm introduction",
        "send_mode": "wait_each",
        "messages": [
            {
                "content": "Hello {patient_name}!",
                "expects_response": False,
                "delay_seconds": 1.5,
            }
        ],
    }

    result = validate_day_config(day_config)

    assert result["title"] == "Day 1 Greeting"
    assert result["messages"][0]["delay_seconds"] == 1.5
    assert result["messages"][0]["expects_response"] is False


def test_validate_day_config_coerces_expects_response_to_bool() -> None:
    day_config = {
        "day": 1,
        "send_mode": "single",
        "messages": [
            {
                "content": "Hello",
                "expects_response": "true",
            }
        ],
    }

    result = validate_day_config(day_config)

    assert result["messages"][0]["expects_response"] is True


def test_validate_day_config_accumulates_multiple_errors() -> None:
    day_config = {
        "day": 1,
        "send_mode": "bad-mode",
        "messages": [{"content": "   "}, {"expects_response": True}],
    }

    with pytest.raises(DayConfigValidationError) as exc_info:
        validate_day_config(day_config, flow_kind="onboarding", day_number=1)

    assert len(exc_info.value.errors) == 3
    assert "Invalid send_mode 'bad-mode'" in exc_info.value.errors[0]
    assert "messages[0].content is empty" in exc_info.value.errors[1]
    assert "messages[1] missing required 'content' key" in exc_info.value.errors[2]
