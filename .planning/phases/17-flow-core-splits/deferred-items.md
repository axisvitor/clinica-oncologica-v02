# Deferred Items - Phase 17 Flow Core Splits

## Out-of-scope Test Failure

- Command: `python3 -m pytest tests/unit/services/flow/test_sequential_message_handler.py -k "direct_function or run_flow_message or run_flow_response" -x`
- Issue: `Settings` model in test runtime rejects monkeypatching `AI_FLOW_FRAMEWORK` (`ValueError: "Settings" object has no field "AI_FLOW_FRAMEWORK"`).
- Scope note: This test failure is not introduced by the `_flow_functions` split and is outside this plan's targeted contract checks.
