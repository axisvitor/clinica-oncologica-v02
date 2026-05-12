---
estimated_steps: 47
estimated_files: 5
skills_used: []
---

# T03: Require signed quiz session state for compatibility cookies

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
The compatibility frontend flow needs cookies for refresh/session recovery, but raw `quiz_session_id` is not proof of authorization. This task keeps `/access` compatible while making `/session/active`, `/submit`, and mutating `/logout` require signed/opaque state bound to the same active quiz session.

## Files
- Modify `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` and the new security helper.
- Update `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py` for the new cookie contract.
- Extend `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py` with raw/forged/mismatched cookie tests.

## Do
1. After `/access` validates the access token through the T02 helper, set the legacy HttpOnly `quiz_session_id` cookie and a new HttpOnly `quiz_session_state` cookie.
2. Sign `quiz_session_state` with the quiz token secret or a clearly equivalent existing secret, with claims at minimum: `type='quiz_session_state'`, `session_id`, `patient_id`, `quiz_template_id`, and an expiry no later than the T02 effective expiration.
3. Validate `quiz_session_state` on `/session/active` and `/submit`; raw `quiz_session_id` alone must return 401 and must not reveal whether that UUID exists.
4. If both cookies are present, require the raw `quiz_session_id` to match the signed state `session_id`; mismatches fail closed.
5. Reuse the same session/link-state validator semantics for state-cookie flows: session must be `started`, not expired, link metadata active, and patient/template bound.
6. Update `/access` so it no longer creates a session; link creation remains the session creation boundary.
7. Update `/logout` to always clear both cookies but only cancel a started session when signed state validates; malformed/absent state must not mutate arbitrary sessions.
8. Preserve cookie attributes (`httponly`, `secure` according to settings, `samesite` consistent with existing code) and set max_age from the effective expiry rather than a hard-coded year.
9. Add compatibility tests: access sets both cookies; valid state recovers active session; valid state submit writes/updates expected response; raw cookie only fails; forged state fails; state/raw mismatch fails; logout clears both and does not cancel a raw-cookie-only foreign session.

## Must-Haves
- [ ] Raw `quiz_session_id` alone is insufficient for active-session recovery or submit.
- [ ] Valid `/access` response remains usable by the existing frontend/client test path.
- [ ] Logout cannot cancel a session named only by an attacker-controlled raw cookie.

## Failure Modes (Q5)
| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|-----------------------|
| State-cookie JWT verification | 401 fail-closed and clear nothing except explicit logout clear | N/A | 401 fail-closed; no UUID existence leak |
| Browser/client cookie handling | Keep legacy `quiz_session_id` for compatibility, but require state for authorization | N/A | Missing/mismatched cookies fail closed |
| Redis question cache | Ignore cache failures after authorization; transform questions directly | 1s existing timeout remains non-authorizing | Malformed cache payload falls back to transformation or safe failure, never auth success |

## Load Profile (Q6)
- Shared resources: JWT signing/verification, DB session, Redis question cache.
- Per-operation cost: `/access` one access-token validation plus state signing; active/submit one state decode and session/template lookup.
- 10x breakpoint: public rate limits and DB lookup volume; avoid extra unbounded queries and avoid per-request global scans.

## Negative Tests (Q7)
- Malformed inputs: missing state cookie, malformed JWT state, invalid UUID cookie, wrong state token type.
- Error paths: state session mismatch, raw cookie mismatch, expired state, cancelled/completed session.
- Boundary conditions: valid state with no raw cookie can either be accepted if deliberately chosen or rejected consistently; if raw cookie is required for legacy, tests must document the chosen contract.

## Verify
- `cd backend-hormonia && pytest tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_link_session_boundary.py -q -k "compatibility or session_state or raw_session or forged_state or logout"`

## Done when
The compatibility flow works only with signed state and all raw/forged/mismatched cookie paths fail without quiz response or cancellation side effects.

## Inputs

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py`
- `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`
- `backend-hormonia/app/config/settings.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py`
- `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_link_session_boundary.py -q -k "compatibility or session_state or raw_session or forged_state or logout"

## Observability Impact

Adds a debuggable state-cookie boundary: failures identify reason/session resource only, while logout remains safe and idempotent even for malformed cookies.
