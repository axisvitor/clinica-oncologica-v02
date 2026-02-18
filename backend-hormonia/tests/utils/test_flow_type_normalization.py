from app.services.flow.types import FlowType, normalize_flow_type


def test_normalize_flow_type_keeps_canonical_values():
    assert normalize_flow_type("onboarding") == FlowType.ONBOARDING
    assert normalize_flow_type(FlowType.DAILY_FOLLOW_UP) == FlowType.DAILY_FOLLOW_UP
    assert normalize_flow_type("quiz_mensal") == FlowType.QUIZ_MENSAL


def test_normalize_flow_type_returns_custom_for_legacy_or_unknown():
    assert normalize_flow_type("daily_checkin") == FlowType.CUSTOM
    assert normalize_flow_type("monthly_quiz") == FlowType.CUSTOM
    assert normalize_flow_type("initial_15_days") == FlowType.CUSTOM
    assert normalize_flow_type("unknown_flow_kind") == FlowType.CUSTOM
    assert normalize_flow_type(None) == FlowType.CUSTOM
