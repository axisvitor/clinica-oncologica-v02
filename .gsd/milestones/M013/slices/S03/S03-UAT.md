# S03: Quiz Link/Session Boundary — UAT

**Milestone:** M013
**Written:** 2026-05-12T23:36:00.293Z

# UAT — S03 Quiz Link/Session Boundary

## UAT Type

Automated integration/security UAT using FastAPI route tests, DB fixtures, signed cookies/tokens, and regression suites. Manual browser/server UAT is not required for this slice because the contract is authorization/session integrity rather than visual behavior.

## Preconditions

1. Backend test dependencies are installed and the quiz regression DB fixture can run from `backend-hormonia`.
2. Two-doctor/two-patient fixtures exist, with Doctor A assigned to Patient A and Doctor B assigned to Patient B.
3. A legitimate monthly quiz fixture exists with a valid template, QuizSession, token hash metadata, active link state, and non-expired token/session/link timestamps.
4. Logging capture is enabled for public quiz denial paths.

## Steps and Expected Outcomes

1. **Authenticated ownership — link creation:** As Doctor A, request quiz link creation for Patient B. Expected: request is denied before any QuizSession/token side effect; response/logs do not include Patient B name/phone, tokens, token prefixes, response text, or secrets.
2. **Authenticated ownership — status/history:** As Doctor A, request Patient B quiz status/history. Expected: request fails closed with a generic authorization denial and no foreign quiz/session data. As Doctor A for Patient A, the legitimate status/history path still succeeds.
3. **Authenticated ownership — active links:** As Doctor A, list active quiz links. Expected: only Doctor A scoped patients are returned before PHI serialization; Patient B is absent. As admin, active-link visibility remains allowed across patients.
4. **Public current/access — valid fixture:** Use the legitimate fixture public token against the matching patient/template/session. Expected: current/access succeeds, validates stored token hash and active link metadata, returns only the appropriate quiz payload, and `/access` sets both legacy `quiz_session_id` and signed HttpOnly `quiz_session_state` cookies.
5. **Public token rejection matrix:** Try missing session_id, wrong patient, wrong template, wrong path quiz_id, wrong token type, mismatched session, mismatched stored token_hash, expired JWT, expired session/link metadata, cancelled link, and used/completed link. Expected: each request fails closed before payload read or response write; no QuizResponse row is created; denial responses are generic.
6. **Compatibility signed-state matrix:** Call `/session/active`, public submit, and mutating logout with only raw `quiz_session_id`, a forged signed state, or a signed state that does not match the legacy cookie/session. Expected: each unsafe state is rejected; logout remains safe/idempotent and does not cancel arbitrary raw-cookie-only sessions.
7. **Valid submit:** Submit the legitimate fixture quiz with matching token/session/state. Expected: answers are accepted, the expected response is written for the correct patient/session/template, the quiz completes, and link metadata is transitioned to used/terminal state.
8. **Diagnostic hygiene:** Inspect captured logs and response bodies for denied quiz paths. Expected: safe reason/resource IDs may appear; patient names/phones, quiz answers, raw tokens, token prefixes, secrets, raw cookies, and signed state values do not appear.

## Edge Cases Covered

- Foreign doctor patient_id tampering on creation/status/history/list endpoints.
- Active-link enumeration by a non-admin doctor.
- Replay/forgery of public quiz JWTs and non-authoritative token types.
- Valid token presented against a different patient/template/session/path.
- Stored token hash mismatch and inactive/expired/cancelled/used link metadata.
- Raw legacy cookie replay without signed state.
- Forged signed state, signed-state/session mismatch, and safe logout behavior.
- Best-effort denial logging failures must not change authorization outcomes.

## Not Proven By This UAT

- Private upload/report serving and generated PDF access controls; those are S04/S05.
- Consolidated F-01..F-11 evidence matrix; that is S06.
- Browser UI rendering or WhatsApp delivery behavior.
- Medium/proof-gap findings outside the critical/high S03 quiz boundary.
