"""
Tests for day-config editor API (GET/PUT /flows/{template_id}/days).

Tests the projection (steps → day-configs) and hydration (day-configs → steps)
that power the physician-facing day editor.

Created in T01, fully populated in T02.
"""

from __future__ import annotations

import pytest

from app.schemas.v2.templates import DayConfigItem, DayConfigListUpdate
from app.api.v2.routers.flow_templates import (
    _hydrate_day_configs_to_steps,
    _project_steps_to_day_configs,
)
from app.services.flow.config_validation import validate_day_config


# ==================== Projection (steps → day-configs) ====================


class TestProjectStepsToDayConfigs:
    """Test _project_steps_to_day_configs helper."""

    def test_projects_standard_steps(self):
        steps = [
            {
                "day": 1,
                "send_mode": "single",
                "messages": [{"order": 1, "content": "Welcome!", "expects_response": False}],
                "intent": "day_1_message",
                "message_type": "question",
            },
            {
                "day": 3,
                "send_mode": "wait_each",
                "messages": [{"order": 1, "content": "How are you?", "expects_response": True}],
                "intent": "day_3_message",
                "message_type": "motivation",
            },
        ]
        result = _project_steps_to_day_configs(steps)
        assert len(result) == 2
        assert result[0].day_number == 1
        assert result[0].content == "Welcome!"
        assert result[0].message_type == "question"
        assert result[0].expects_response is False
        assert result[1].day_number == 3
        assert result[1].content == "How are you?"
        assert result[1].expects_response is True

    def test_projects_sorted_by_day(self):
        steps = [
            {"day": 5, "messages": [{"content": "Day 5"}]},
            {"day": 1, "messages": [{"content": "Day 1"}]},
            {"day": 3, "messages": [{"content": "Day 3"}]},
        ]
        result = _project_steps_to_day_configs(steps)
        assert [d.day_number for d in result] == [1, 3, 5]

    def test_fallback_content_from_step_keys(self):
        """Falls back to step.content / step.base_content / step.message when no messages list."""
        steps = [
            {"day": 1, "content": "from content key"},
            {"day": 2, "base_content": "from base_content key"},
            {"day": 3, "message": "from message key"},
        ]
        result = _project_steps_to_day_configs(steps)
        assert result[0].content == "from content key"
        assert result[1].content == "from base_content key"
        assert result[2].content == "from message key"

    def test_empty_steps_returns_empty(self):
        assert _project_steps_to_day_configs([]) == []

    def test_non_list_steps_returns_empty(self):
        assert _project_steps_to_day_configs({"day_1": {"content": "x"}}) == []

    def test_skips_invalid_steps(self):
        steps = [
            "not a dict",
            {"no_day_key": True},
            {"day": "abc"},  # invalid day number
            {"day": 1, "messages": [{"content": "Valid"}]},
        ]
        result = _project_steps_to_day_configs(steps)
        assert len(result) == 1
        assert result[0].day_number == 1

    def test_defaults_unknown_message_type_to_question(self):
        steps = [{"day": 1, "messages": [{"content": "Hello"}], "message_type": "unknown_type"}]
        result = _project_steps_to_day_configs(steps)
        assert result[0].message_type == "question"


# ==================== Hydration (day-configs → steps) ====================


class TestHydrateDayConfigsToSteps:
    """Test _hydrate_day_configs_to_steps helper."""

    def test_hydrates_single_item(self):
        items = [DayConfigItem(day_number=1, content="Hello!", message_type="question", expects_response=True)]
        steps = _hydrate_day_configs_to_steps(items)
        assert len(steps) == 1
        step = steps[0]
        assert step["day"] == 1
        assert step["send_mode"] == "wait_each"
        assert step["messages"] == [{"order": 1, "content": "Hello!", "expects_response": True}]
        assert step["intent"] == "day_1_message"
        assert step["message_type"] == "question"

    def test_hydrates_no_response_expected(self):
        items = [DayConfigItem(day_number=5, content="Reminder", message_type="reminder", expects_response=False)]
        steps = _hydrate_day_configs_to_steps(items)
        assert steps[0]["send_mode"] == "single"
        assert steps[0]["messages"][0]["expects_response"] is False

    def test_empty_list_returns_empty(self):
        assert _hydrate_day_configs_to_steps([]) == []

    def test_hydrated_steps_are_always_list(self):
        items = [DayConfigItem(day_number=1, content="Test", message_type="question")]
        result = _hydrate_day_configs_to_steps(items)
        assert isinstance(result, list)


# ==================== Round-trip & Loader compatibility ====================


class TestRoundTripAndValidation:
    """Test that hydration output passes validate_day_config and round-trips correctly."""

    def test_round_trip_preserves_data(self):
        original = DayConfigItem(day_number=7, content="Week check-in", message_type="motivation", expects_response=True)
        steps = _hydrate_day_configs_to_steps([original])
        projected = _project_steps_to_day_configs(steps)
        assert len(projected) == 1
        assert projected[0].day_number == original.day_number
        assert projected[0].content == original.content
        assert projected[0].message_type == original.message_type
        assert projected[0].expects_response == original.expects_response

    def test_hydrated_step_passes_validate_day_config(self):
        item = DayConfigItem(day_number=1, content="Hello!", message_type="question", expects_response=True)
        steps = _hydrate_day_configs_to_steps([item])
        for step in steps:
            validated = validate_day_config(step, flow_kind="test", day_number=step["day"])
            assert validated is not None

    def test_multiple_days_all_pass_validation(self):
        items = [
            DayConfigItem(day_number=1, content="Day 1", message_type="question", expects_response=False),
            DayConfigItem(day_number=7, content="Week check", message_type="motivation", expects_response=True),
            DayConfigItem(day_number=30, content="Month end", message_type="reminder", expects_response=False),
        ]
        steps = _hydrate_day_configs_to_steps(items)
        for step in steps:
            validate_day_config(step, flow_kind="test", day_number=step["day"])


# ==================== Schema validation ====================


class TestSchemaValidation:
    """Test DayConfigItem Pydantic validation."""

    def test_rejects_invalid_message_type(self):
        with pytest.raises(Exception):
            DayConfigItem(day_number=1, content="Test", message_type="invalid_type")

    def test_rejects_empty_content(self):
        with pytest.raises(Exception):
            DayConfigItem(day_number=1, content="", message_type="question")

    def test_rejects_day_zero(self):
        with pytest.raises(Exception):
            DayConfigItem(day_number=0, content="Test", message_type="question")

    def test_accepts_all_valid_message_types(self):
        for mt in ("question", "motivation", "reminder"):
            item = DayConfigItem(day_number=1, content="Test", message_type=mt)
            assert item.message_type == mt

    def test_duplicate_day_detection_logic(self):
        """DayConfigListUpdate allows duplicates at schema level; endpoint checks."""
        payload = DayConfigListUpdate(days=[
            DayConfigItem(day_number=1, content="A", message_type="question"),
            DayConfigItem(day_number=1, content="B", message_type="question"),
        ])
        day_numbers = [d.day_number for d in payload.days]
        assert len(day_numbers) != len(set(day_numbers))  # duplicates exist
