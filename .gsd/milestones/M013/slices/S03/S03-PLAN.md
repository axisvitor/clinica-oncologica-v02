# S03: Quiz Link/Session Boundary

**Goal:** Close the Quiz Link/Session Boundary for M013 by enforcing assigned-doctor/admin ownership on authenticated quiz link/status/list endpoints and by requiring public quiz access/submission to prove a signed token, stored token hash, quiz session, patient/template binding, active link state, effective expiration, and signed compatibility session state before any quiz payload or response write is allowed.
**Demo:** Quiz link creation, status/history, active links and public submit reject foreign, expired, forged or mismatched state while a legitimate fixture quiz still completes.

## Must-Haves

- ## Owned / Supporting Requirements
- Owns R004: `POST /api/v2/quiz-extensions/links/`, `GET /patients/{patient_id}/status`, `GET /patients/{patient_id}/history`, and `GET /links/active/` enforce admin-or-assigned-doctor patient ownership and never return foreign patient quiz/session data to another doctor.
- Owns R005: public quiz current/access/submit/session endpoints reject foreign, expired, forged, cancelled/used, token-hash mismatched, patient/template/session mismatched, and raw-cookie-only states; one legitimate fixture quiz still completes.
- Supports R010/R011: reuses the S02 two-doctor/two-patient fixture pattern and keeps denial diagnostics ID/reason-only with no patient names/phones, quiz response text, tokens, token prefixes, or secrets.
- ## Threat Surface (Q3)
- Abuse: patient_id tampering by authenticated doctors, global active-link enumeration, replay of an old quiz JWT, use of a valid token against a different session/patient/template, forged raw `quiz_session_id` cookies, forged/mismatched signed state cookies, and submitting after expiration/cancellation/completion.
- Data exposure: patient names in active-link lists, quiz payload/session IDs, response values, tokens/cookies, and link metadata.
- Input trust: query token, path quiz_id, POST JSON answers, public cookies, and authenticated patient_id parameters are all untrusted until DB/session/link validation succeeds.
- ## Requirement Impact (Q4)
- Requirements touched: R004, R005, supporting R010/R011.
- Re-verify: monthly quiz compatibility tests, public quiz token tests, quiz extensions smoke/regression tests, and quiz-adjacent phase25 async tests.
- Decisions revisited: D009 records the shared public quiz security seam and signed session-state cookie policy for this slice.
- ## Slice Verification (defined before task execution)
- `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q`
- `cd backend-hormonia && python - <<'PY'\nfrom pathlib import Path\nfor path in [Path('tests/api/v2/test_quiz_link_session_boundary.py'), Path('tests/api/v2/test_monthly_quiz_compatibility.py')]:\n    text = path.read_text()\n    forbidden = ['.gsd/', '.planning/', '.audits/']\n    assert not any(marker in text for marker in forbidden), f'{path} references planning artifacts'\nPY`
- ## Done When
- Authenticated foreign-doctor quiz link creation/status/history/active-link reads fail closed without creating sessions or leaking patient names.
- Public tokenized current/submit routes use only an existing, active `QuizSession` whose stored metadata matches the submitted token hash and expiry/link state.
- Compatibility `/access` sets both legacy `quiz_session_id` and signed `quiz_session_state`, while `/session/active`, `/submit`, and mutating `/logout` reject raw/forged/mismatched state.
- Denial logs/responses for touched quiz paths exclude PHI, tokens, token prefixes, and secrets while retaining safe IDs/reason fields.

## Proof Level

- This slice proves: Contract + integration proof with executable pytest coverage against the mounted FastAPI routes. No manual UAT required; real runtime server not required because TestClient/DB fixtures exercise routing, dependencies, DB writes, cookies, token signing, and denial side effects.

## Integration Closure

Consumes S02's `load_patient_with_access` helper and two-doctor/two-patient fixture pattern. Introduces ownership wiring in `monthly_quiz_operations/crud.py` and a shared public quiz validation/state seam for `monthly_quiz_operations/public.py`. Leaves private upload/report serving (S04) and report ownership (S05) for downstream slices; S06 will consume S03's focused proof in the final evidence matrix.

## Verification

- Public and authenticated quiz denials should be observable through structured/safe warning logs containing reason plus non-PHI resource identifiers only. Token verification diagnostics must not include raw tokens, token prefixes, patient names/phones, response text, or secrets. Cache misses/failures for transformed questions remain non-authorizing and must not bypass session/link validation.

## Tasks

- [x] **T01: Gate authenticated quiz link/status/history lists by patient ownership** `est:2h`
  ---
  estimated_steps: 8
  estimated_files: 4
  skills_used:
    - tdd
    - api-design
    - security-review
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py`, `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`, `backend-hormonia/tests/api/v2/security_boundary_helpers.py`, `backend-hormonia/app/api/v2/patients_shared_helpers.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py -q -k "authenticated or active_links or patient_status or patient_history"

- [ ] **T02: Bind tokenized public quiz access and submit to stored link state** `est:3h`
  ---
  estimated_steps: 9
  estimated_files: 5
  skills_used:
    - tdd
    - api-design
    - security-review
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`, `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py`, `backend-hormonia/app/domain/quizzes/session/token_manager.py`, `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`, `backend-hormonia/app/core/router_registry.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py -q -k "public_token or token_hash or link_state or expired"

- [ ] **T03: Require signed quiz session state for compatibility cookies** `est:3h`
  ---
  estimated_steps: 9
  estimated_files: 5
  skills_used:
    - tdd
    - api-design
    - security-review
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`, `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py`, `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py`, `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`, `backend-hormonia/app/config/settings.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_link_session_boundary.py -q -k "compatibility or session_state or raw_session or forged_state or logout"

- [ ] **T04: Sanitize quiz-token diagnostics and run the full S03 proof** `est:1.5h`
  ---
  estimated_steps: 6
  estimated_files: 6
  skills_used:
    - security-review
    - test
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/domain/quizzes/session/token_manager.py`, `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py`, `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`, `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py`, `backend-hormonia/tests/api/v2/test_quiz_extensions.py`, `backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q && python - <<'PY'
from pathlib import Path
for path in [Path('tests/api/v2/test_quiz_link_session_boundary.py'), Path('tests/api/v2/test_monthly_quiz_compatibility.py')]:
    text = path.read_text()
    forbidden = ['.gsd/', '.planning/', '.audits/']
    assert not any(marker in text for marker in forbidden), f'{path} references planning artifacts'
PY

## Files Likely Touched

- backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py
- backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py
- backend-hormonia/tests/api/v2/security_boundary_helpers.py
- backend-hormonia/app/api/v2/patients_shared_helpers.py
- backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py
- backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py
- backend-hormonia/app/domain/quizzes/session/token_manager.py
- backend-hormonia/app/core/router_registry.py
- backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py
- backend-hormonia/app/config/settings.py
- backend-hormonia/tests/api/v2/test_quiz_extensions.py
- backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py
