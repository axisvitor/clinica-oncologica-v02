---
id: T02
parent: S05
milestone: M007
provides:
  - Contract-level test proof for the complete alert→notification chain
key_files:
  - backend-hormonia/tests/unit/services/flow/test_quiz_alert_notifications.py
key_decisions:
  - Used _non_triggering_responses() helper with explicit sleep_quality=10 to suppress sleep_disturbance rule (triggers on sleep_quality ≤ 3, default 0) and isolate specific rule triggers
  - Tests mock AlertRepository.create() and _notify_medical_team() to test only the _create_alert→Notification creation chain without websocket/email side effects
patterns_established:
  - Mock DB shim with side_effect list for sequenced query().filter().first() calls (duplicate check → patient lookup) to test multi-query flows
observability_surfaces:
  - Test failures surface as pytest assertion errors pinpointing which contract link broke (severity mapping, doctor targeting, duplicate guard, serializer shape)
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Focused tests proving alert→notification chain

**Created 14 focused tests proving the complete quiz response → Alert → Notification → doctor targeting chain with all edge cases**

## What Happened

Replaced the T01 skeleton test file (2 real tests + 3 placeholders) with 14 focused tests organized in a single `TestQuizAlertNotificationChain` class. The tests cover:

1. **Alert creation with correct JSONB data** — pain_scale=9 triggers `pain_score_critical`, alert has `alert_type="quiz_response"`, `severity=CRITICAL`, and data contains `quiz_session_id`, `triggered_rule_id`, `rule_name`, `recommendation`.
2. **Notification→doctor targeting** — after alert creation, `db.add()` is called with a `Notification` instance where `user_id == patient.doctor_id`, `related_patient_id == patient_id`, `notification_type == ALERT`.
3. **Severity mapping (5 sub-tests)** — CRITICAL→URGENT, HIGH→HIGH, MEDIUM→MEDIUM instance method tests; config→model map validation; full NOTIFICATION_PRIORITY_MAP coverage including LOW→LOW.
4. **Missing doctor_id** — alert IS created but NO Notification, with warning logged.
5. **Duplicate prevention** — existing alert returned, no new alert or notification created, "Duplicate" logged.
6. **No rules trigger** — empty alerts list, risk_score=0.0, no notifications.
7. **Serializer output shape** — `_serialize_alert()` returns `title` from `data.rule_name`, `message` from `description`, `recommendation` from `data.recommendation`.
8. **Serializer fallback** — when `data=None`, title falls back to `alert_type`, recommendation to `""`.
9. **fever_with_chills rule** — `has_fever=True + has_chills=True` triggers CRITICAL alert.
10. **Risk score** — CRITICAL alert produces risk_score ≥ 50.

Key design choice: `_non_triggering_responses()` helper explicitly sets `sleep_quality=10` to suppress the `sleep_disturbance` rule (which triggers on `sleep_quality ≤ 3`, and the helper function `_get_numeric_value` defaults to 0.0 for missing keys).

## Verification

**Task-level:**
- `python3 -m pytest tests/unit/services/flow/test_quiz_alert_notifications.py -v` → **14 passed** ✅
- `python3 -m pytest tests/api/v2/test_alerts.py -v` → **42 passed** ✅ (0 regressions)
- `python3 -m pytest tests/unit/services/flow/ -v` → **168 passed, 4 skipped** ✅ (1 pre-existing failure: `sequencing.py` line count 521 > 500 limit — unrelated to S05)

**Slice-level verification (final task — all checked):**
- ✅ `test_quiz_alert_notifications.py` — 14/14 pass
- ✅ `test_alerts.py` — 42/42 pass
- ✅ Flow tests — 168/168 pass (4 skipped, 1 pre-existing unrelated failure)
- ✅ `npx tsc --noEmit` — app source typechecks green (6 pre-existing errors in e2e playwright config only)
- ✅ Diagnostic failure-path check: evaluator errors caught in `complete_quiz_session()` (try/except at L235-260)
- ✅ `_serialize_alert()` returns `title`, `message`, `recommendation` keys (proven by test)

## Diagnostics

- Run `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_quiz_alert_notifications.py -v` to re-verify the chain contract.
- If any test fails, the assertion message identifies which link in the chain broke.
- Pre-existing flow test failure (`test_split_files_under_500_lines`) is tracked separately.

## Deviations

- Plan referenced `critical_pain` rule_id but actual rule_id is `pain_score_critical` (and threshold is ≥ 7, not ≥ 8). Tests use the real rule_ids from `quiz_alert_rules.py`.
- Plan estimated 7 tests; delivered 14 (including 5 severity sub-tests, serializer fallback, fever_with_chills, and risk score).
- Added `_non_triggering_responses()` helper with explicit `sleep_quality=10` to suppress default-triggered `sleep_disturbance` rule.

## Known Issues

- Pre-existing: `test_split_files_under_500_lines` fails because `sequencing.py` has 521 lines (not caused by S05 changes).
- Pre-existing: `playwright.config.e2e.ts` has 6 TS errors on `process.env.CI` access pattern (unrelated to S05).

## Files Created/Modified

- `backend-hormonia/tests/unit/services/flow/test_quiz_alert_notifications.py` — Complete rewrite: 14 focused tests proving alert→notification chain
- `.gsd/milestones/M007/slices/S05/tasks/T02-PLAN.md` — Added Observability Impact section (pre-flight fix)
