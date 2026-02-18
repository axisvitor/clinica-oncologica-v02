from app.services.ai.execution_policy import decide_ai_failure, is_real_ai_ready


def test_is_real_ai_ready_with_explicit_api_key():
    assert is_real_ai_ready("valid-key") is True
    assert is_real_ai_ready("  valid-key  ") is True
    assert is_real_ai_ready("") is False
    assert is_real_ai_ready("   ") is False


def test_decide_ai_failure_uses_explicit_allow_simulation_true():
    decision = decide_ai_failure("sentiment", allow_simulation=True)
    assert decision.use_simulation is True
    assert decision.status_code == 502


def test_decide_ai_failure_uses_explicit_allow_simulation_false():
    decision = decide_ai_failure(
        "sentiment",
        allow_simulation=False,
        detail="custom detail",
    )
    assert decision.use_simulation is False
    assert decision.status_code == 502
    assert decision.detail == "custom detail"


def test_decide_ai_failure_default_detail():
    decision = decide_ai_failure("insights", allow_simulation=False)
    assert decision.detail == "insights failed and simulation fallback is disabled."
