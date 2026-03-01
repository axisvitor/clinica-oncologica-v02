from __future__ import annotations

from pathlib import Path

from app.services.flow import _flow_functions
from app.services.flow import _flow_message_flow
from app.services.flow import _flow_orchestration_utils
from app.services.flow import _flow_response_flow


def test_legacy_flow_functions_exports_still_resolve() -> None:
    assert callable(_flow_functions.run_flow_message)
    assert callable(_flow_functions.run_flow_response)
    assert callable(_flow_functions.validate_flow_message_state)
    assert callable(_flow_functions.require_configurable_thread_id)


def test_split_modules_define_expected_boundaries() -> None:
    assert _flow_functions.run_flow_message is _flow_message_flow.run_flow_message
    assert _flow_functions.load_flow_context is _flow_message_flow.load_flow_context
    assert _flow_functions.dispatch_send_mode is _flow_message_flow.dispatch_send_mode

    assert _flow_functions.run_flow_response is _flow_response_flow.run_flow_response
    assert _flow_functions.load_response_context is _flow_response_flow.load_response_context
    assert (
        _flow_functions.dispatch_response_continuation
        is _flow_response_flow.dispatch_response_continuation
    )

    assert (
        _flow_functions.validate_flow_message_state
        is _flow_orchestration_utils.validate_flow_message_state
    )
    assert (
        _flow_functions.require_configurable_thread_id
        is _flow_orchestration_utils.require_configurable_thread_id
    )


def test_split_modules_stay_under_500_lines() -> None:
    base_dir = Path(__file__).resolve().parents[4] / "app" / "services" / "flow"
    module_paths = [
        base_dir / "_flow_message_flow.py",
        base_dir / "_flow_response_flow.py",
        base_dir / "_flow_orchestration_utils.py",
    ]

    for module_path in module_paths:
        line_count = len(module_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 500, f"{module_path.name} has {line_count} lines"
