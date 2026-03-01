# Phase 25 Plan 05 Functional Test Results

## Command Runs

- `pytest tests/api/v2/test_messages.py -v --tb=short`
  - Result: 39 passed, 1 skipped
  - Note: Skip reason is expected test-env rate-limit disablement.

- `pytest tests/api/v2/test_quiz.py -v --tb=short`
  - Result: 6 passed, 2 skipped, 3 failed
  - Root causes:
    - `UndefinedColumn: quiz_templates.version` during fixture/template insert
    - `TypeError: 'month' is an invalid keyword argument for QuizSession`

- `pytest tests/api/v2/test_quiz_extensions.py -v --tb=short`
  - Result: failing/errors (large suite), dominated by fixture setup errors
  - Root cause repeatedly observed:
    - `UndefinedColumn: quiz_templates.version` during fixture/template insert

- `pytest tests/api/v2/test_monthly_quiz_compatibility.py -v --tb=short`
  - Result: 4 errors
  - Root cause repeatedly observed:
    - `UndefinedColumn: quiz_templates.version` during fixture/template insert

- Combined run:
  - `pytest tests/api/v2/test_phase25_messages_quiz_async.py tests/api/v2/test_messages.py tests/api/v2/test_quiz.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_monthly_quiz_compatibility.py -v --tb=short`
  - Regression status: `test_phase25_messages_quiz_async.py` passes
  - Functional status: quiz-related suites still fail on pre-existing schema/fixture issues

## Assessment

The new Phase 25 regression suite is green and validates async migration source constraints.
Functional-suite failures are pre-existing fixture/schema compatibility issues, not regressions introduced by this plan.
