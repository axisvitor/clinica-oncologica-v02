---
id: T04
parent: S03
milestone: M013
key_files:
  - backend-hormonia/app/domain/quizzes/session/token_manager.py
  - backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py
  - backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py
  - backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py
  - backend-hormonia/tests/api/v2/test_quiz_extensions.py
key_decisions:
  - Use generic `expired_token`/`invalid_token` TokenManager reasons instead of exception details or token-derived diagnostics.
  - Treat public quiz denial logging as best-effort observability that must not affect authorization outcomes.
  - Keep legacy local Postgres schema alignment test-only and transactional inside the regression suite.
duration: 
verification_result: mixed
completed_at: 2026-05-12T21:25:14.122Z
blocker_discovered: false
---

# T04: Sanitized quiz token/session denial diagnostics and proved S03 with the full quiz regression suite.

**Sanitized quiz token/session denial diagnostics and proved S03 with the full quiz regression suite.**

## What Happened

Replaced TokenManager verification warnings with generic reason-only diagnostics (`expired_token`/`invalid_token`) and removed exception-class-derived diagnostic content. Hardened the public quiz denial helper so logging failures are swallowed and authorization continues to return the intended generic denial. Extended focused tests with caplog/response assertions for invalid public tokens, token hash mismatch, raw session-cookie-only compatibility requests, and forged signed state cookies, verifying that tokens, token prefixes, PHI/question text, and cookie state values are absent while safe reasons/resource IDs remain available where applicable. During the full proof, the existing quiz_extensions regression file exposed legacy local Postgres schema drift (`quiz_templates.version` and `quiz_responses.quiz_template_id` missing); added a test-only autouse schema alignment fixture matching the current quiz ORM columns so the planned regression suite can run against local Postgres without weakening production validation.

## Verification

Focused denial diagnostics passed. The first full proof run failed on legacy test-schema drift in `test_quiz_extensions.py`; after adding the test-only schema alignment fixture, `pytest tests/api/v2/test_quiz_extensions.py -q` passed and the full planned S03 command plus planning-artifact audit passed. A final static audit confirmed no forbidden token diagnostic markers remain in the touched implementation files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py -q -k "invalid_public_token or token_hash_mismatch or raw_session_cookie_only or forged_state"` | 0 | ✅ pass | 28112ms |
| 2 | `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q && python - <<'PY'
from pathlib import Path
for path in [Path('tests/api/v2/test_quiz_link_session_boundary.py'), Path('tests/api/v2/test_monthly_quiz_compatibility.py')]:
    text = path.read_text()
    forbidden = ['.gsd/', '.planning/', '.audits/']
    assert not any(marker in text for marker in forbidden), f'{path} references planning artifacts'
PY` | 1 | ❌ fail (legacy local quiz test schema drift exposed) | 51418ms |
| 3 | `cd backend-hormonia && pytest tests/api/v2/test_quiz_extensions.py -q` | 0 | ✅ pass | 27899ms |
| 4 | `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q && python - <<'PY'
from pathlib import Path
for path in [Path('tests/api/v2/test_quiz_link_session_boundary.py'), Path('tests/api/v2/test_monthly_quiz_compatibility.py')]:
    text = path.read_text()
    forbidden = ['.gsd/', '.planning/', '.audits/']
    assert not any(marker in text for marker in forbidden), f'{path} references planning artifacts'
PY` | 0 | ✅ pass | 33365ms |
| 5 | `python - <<'PY'
from pathlib import Path
files = [
    Path('backend-hormonia/app/domain/quizzes/session/token_manager.py'),
    Path('backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py'),
]
for path in files:
    text = path.read_text()
    forbidden = ['token_prefix', 'token[:', 'raw token', 'token material']
    hits = [marker for marker in forbidden if marker in text]
    assert not hits, f'{path} contains forbidden diagnostic marker(s): {hits}'
    print(f'{path}: no forbidden token diagnostic markers')
PY` | 0 | ✅ pass | 56ms |

## Deviations

Modified `backend-hormonia/tests/api/v2/test_quiz_extensions.py` to add a Postgres test schema alignment fixture after the planned full proof surfaced legacy local schema drift in that regression file.

## Known Issues

The pytest run still emits the existing pytest-asyncio deprecation warning about `asyncio_default_fixture_loop_scope` being unset; it does not fail the suite.

## Files Created/Modified

- `backend-hormonia/app/domain/quizzes/session/token_manager.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`
- `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py`
- `backend-hormonia/tests/api/v2/test_quiz_extensions.py`
