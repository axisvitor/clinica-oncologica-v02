# T04: Template day_config validation

**Slice:** S01 — **Milestone:** M001

## Description

Validate template day_config at flow start so malformed configs fail fast with clear errors.

Purpose: Currently, `load_flow_context` in `_flow_message_flow.py` does minimal validation of the day_config returned by `handler._get_day_config()`. It checks if it is a dict, if messages is a list, and if send_mode is valid. But it does not validate the structure of individual messages (e.g., missing `content` field, invalid `expects_response` type) or detect completely empty configs that should not silently skip. This plan creates a dedicated `validate_day_config` function that performs thorough validation and is called early in `load_flow_context`, failing fast with a `DayConfigValidationError` that includes specific details about what is wrong.

Output: New `config_validation.py` module, modified `_flow_message_flow.py` with early validation, and comprehensive tests.

## Must-Haves

- [ ] "When a flow starts with malformed or missing template day_config, it fails immediately with a clear error instead of proceeding with broken config"
- [ ] "The validation error includes the specific field that is malformed (e.g., missing messages, wrong type, invalid send_mode)"
- [ ] "A structured warning log is emitted with patient_id, flow_kind, day_number, and validation errors when day_config fails validation"

## Files

- `backend-hormonia/app/services/flow/config_validation.py`
- `backend-hormonia/app/services/flow/_flow_message_flow.py`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py`
- `backend-hormonia/tests/unit/services/flow/test_day_config_validation.py`
