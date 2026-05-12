---
estimated_steps: 43
estimated_files: 6
skills_used: []
---

# T04: Sanitize quiz-token diagnostics and run the full S03 proof

---
estimated_steps: 6
estimated_files: 6
skills_used:
  - security-review
  - test
  - verify-before-complete
---

## Why
R011 requires denial diagnostics to be useful without leaking PHI, tokens, token prefixes, or secrets. The final task closes log redaction for the touched quiz token/session paths and proves S03 did not regress existing quiz compatibility/extension behavior.

## Files
- Modify `backend-hormonia/app/domain/quizzes/session/token_manager.py` if it still logs `token_prefix` or token material.
- Adjust `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py` and tests as needed for redacted diagnostics.
- Use existing regression files `backend-hormonia/tests/api/v2/test_quiz_extensions.py` and `backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py` in the proof command.

## Do
1. Replace token verification warnings that include raw token prefixes with reason-only diagnostics such as `reason='expired_token'` or `reason='invalid_token'`; include no token, prefix, secret, patient name/phone, response text, or custom message.
2. Ensure new public quiz security helpers log denial reasons with safe IDs only (`session_id`, `patient_id`, `quiz_template_id`, `reason`) and tolerate logging failures without affecting authorization.
3. Add/extend caplog and response-body tests for invalid token, token hash mismatch, raw cookie only, and forged state to assert forbidden values are absent.
4. Run the focused S03 suite and existing quiz regressions from the backend working directory.
5. Run the planning-artifact audit command against the new/updated focused test files.
6. Repair any legitimate regressions surfaced by the full proof without weakening the security invariants.

## Must-Haves
- [ ] No token prefix/token material remains in `TokenManager.verify_token` diagnostics.
- [ ] Public denial logs/responses are PHI-free and token-free under tests.
- [ ] Full S03 proof command exits 0.

## Failure Modes (Q5)
| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|-----------------------|
| Logging backend/caplog | Authorization result must be unchanged if logging fails | N/A | Log extras should be simple strings/IDs/reasons only |
| Regression test suite | Fix root cause or explicitly document a pre-existing skip/warning in task summary | Async pytest timeout should be rerun once with focused failing test before changes | Malformed test data should not relax production validation |

## Load Profile (Q6)
- Shared resources: test database, pytest process, token verification path.
- Per-operation cost: negligible logging changes; full proof includes several API modules.
- 10x breakpoint: not runtime-facing beyond token verification; avoid synchronous expensive diagnostics on denial paths.

## Negative Tests (Q7)
- Malformed inputs: invalid JWT, expired JWT, malformed state cookie.
- Error paths: token hash mismatch, raw session cookie, forged state.
- Boundary conditions: valid flow still logs no denial and completes; denied flow emits no forbidden token/PHI strings.

## Verify
- `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q`
- `cd backend-hormonia && python - <<'PY'\nfrom pathlib import Path\nfor path in [Path('tests/api/v2/test_quiz_link_session_boundary.py'), Path('tests/api/v2/test_monthly_quiz_compatibility.py')]:\n    text = path.read_text()\n    forbidden = ['.gsd/', '.planning/', '.audits/']\n    assert not any(marker in text for marker in forbidden), f'{path} references planning artifacts'\nPY`

## Done when
The full planned S03 verification passes, diagnostics are redacted under tests, and the final task summary records any existing skips/warnings without claiming unverified coverage.

## Inputs

- `backend-hormonia/app/domain/quizzes/session/token_manager.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`
- `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py`
- `backend-hormonia/tests/api/v2/test_quiz_extensions.py`
- `backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py`

## Expected Output

- `backend-hormonia/app/domain/quizzes/session/token_manager.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`
- `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q && python - <<'PY'
from pathlib import Path
for path in [Path('tests/api/v2/test_quiz_link_session_boundary.py'), Path('tests/api/v2/test_monthly_quiz_compatibility.py')]:
    text = path.read_text()
    forbidden = ['.gsd/', '.planning/', '.audits/']
    assert not any(marker in text for marker in forbidden), f'{path} references planning artifacts'
PY

## Observability Impact

Removes token-prefix leakage from token diagnostics and proves denial diagnostics expose only safe IDs/reasons while preserving enough signal for future debugging.
