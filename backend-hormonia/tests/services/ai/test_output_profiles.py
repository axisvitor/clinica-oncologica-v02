import pytest

from app.services.ai.guardrails import OutputKind
from app.services.ai.output_profiles import (
    JSON_SENTIMENT,
    MESSAGE_HUMANIZED,
    list_output_profiles,
    resolve_output_profile,
)


def test_resolve_output_profile_by_name():
    profile = resolve_output_profile("json_sentiment")
    assert profile is not None
    assert profile.name == JSON_SENTIMENT.name
    assert profile.output_kind == OutputKind.JSON


def test_resolve_output_profile_object_passthrough():
    profile = resolve_output_profile(MESSAGE_HUMANIZED)
    assert profile is MESSAGE_HUMANIZED
    assert profile.require_ending_punctuation is True


def test_resolve_output_profile_unknown_raises():
    with pytest.raises(ValueError):
        resolve_output_profile("does_not_exist")


def test_list_output_profiles_contains_expected_profiles():
    profiles = list_output_profiles()
    assert "json_sentiment" in profiles
    assert "message_humanized" in profiles
