---
estimated_steps: 48
estimated_files: 5
skills_used: []
---

# T02: Bind tokenized public quiz access and submit to stored link state

---
estimated_steps: 9
estimated_files: 5
skills_used:
  - tdd
  - api-design
  - security-review
  - verify-before-complete
---

## Why
The public `monthly/public/current` and `monthly/public/{quiz_id}/submit` routes currently verify only the JWT signature and may create/fallback to sessions. R005 requires the public token to match an existing active link/session, patient, template, token hash, and expiration before returning quiz payloads or writing responses.

## Files
- Modify `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`.
- Add `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py` unless a smaller in-file helper is clearly safer.
- Extend `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`.
- Align with `backend-hormonia/app/core/router_registry.py` short-link metadata semantics.

## Do
1. Create a shared validator that verifies JWTs via `TokenManager.verify_token()` and requires `type`, `patient_id`, `quiz_template_id`, `session_id`, and `exp`.
2. Load `QuizSession` by token `session_id` only; remove public fallback lookup/session creation from tokenized current/submit paths.
3. Require `session.patient_id == token.patient_id`, `session.quiz_template_id == token.quiz_template_id`, optional path `quiz_id` match, `session.status == 'started'`, not `session.is_expired`, and non-terminal metadata `link_status == 'active'`.
4. Require `session.session_metadata['token_hash'] == TokenManager.hash_token(token)`; do not accept previous tokens unless a future explicit grace-period policy and tests are introduced.
5. Compute effective expiry as the earliest of JWT `exp`, `session.expiration_date`, and metadata `expires_at`; reject at/after that boundary and do not write quiz responses.
6. Preserve quiz-template checks (`category == 'monthly_quiz'`, published status, quiz existence) after validator success, and sanitize questions as before.
7. Use the validated session/patient/template in submit; do not persist invalid statuses such as `in_progress` or `pending` to `QuizSession.status`.
8. Add tests proving one valid public token flow can read the quiz and submit, while mismatched patient/template/session, path quiz mismatch, token-hash mismatch, expired metadata/session/JWT, cancelled/completed/expired session, used/cancelled link status, and missing session_id fail without response writes.
9. Keep denial details generic and safe; no raw token or token prefix should appear in response bodies or new logs.

## Must-Haves
- [ ] Public access/submit never create a new quiz session from a token.
- [ ] Stored token hash and link/session state are authoritative.
- [ ] Rejected public submissions do not create or update `QuizResponse` rows.

## Failure Modes (Q5)
| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|-----------------------|
| TokenManager/JWT secret | 401 fail-closed | N/A | 401 fail-closed with generic detail |
| DB session/template lookup | 404/403/410-style fail-closed for missing/terminal state; 500 only for true DB failure | Test DB has no network timeout; production timeout must not write responses | Malformed UUID fields fail as invalid token payload |
| Link metadata JSON | Reject missing/malformed expiry/hash/link status rather than falling back open | N/A | Reject and log safe reason only |

## Load Profile (Q6)
- Shared resources: database session, JWT verification, optional Redis question cache.
- Per-operation cost: one token decode, one session lookup, one quiz lookup, and submit response query/count work.
- 10x breakpoint: public endpoints are already rate-limited; cache failures must only affect question transformation latency, never authorization.

## Negative Tests (Q7)
- Malformed inputs: non-JWT token, wrong token type, invalid UUID claims, missing session_id, invalid path quiz_id mismatch.
- Error paths: missing session, token hash mismatch, inactive/cancelled/expired/completed state, expired metadata/JWT/session.
- Boundary conditions: effective expiration uses earliest timestamp; valid started+active+hash-matching fixture still completes.

## Verify
- `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py -q -k "public_token or token_hash or link_state or expired"`

## Done when
Tokenized public current/submit routes only operate on an existing active hash-matching session and all planned negative token/link-state cases fail without side effects.

## Inputs

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`
- `backend-hormonia/app/domain/quizzes/session/token_manager.py`
- `backend-hormonia/app/models/quiz.py`
- `backend-hormonia/app/schemas/monthly_quiz.py`
- `backend-hormonia/app/core/router_registry.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py -q -k "public_token or token_hash or link_state or expired"

## Observability Impact

Introduces a single public quiz denial signal surface with safe reason/resource IDs and no token material; rejected submissions remain inspectable by absence of response rows and unchanged session state.
