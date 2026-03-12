---
estimated_steps: 4
estimated_files: 3
---

# T02: Implement local login and canonical session issuance

**Slice:** S01 — Local Auth Core
**Milestone:** M002

## Description

Replace the canonical v2 login path with first-party email/password authentication backed by the existing user table and session stack, while preserving cookie/session continuity semantics for the frontend cutover that depends on this slice.

## Steps

1. Extend `backend-hormonia/app/schemas/v2/auth.py` with explicit local-login request/response models that carry email/password input, remember-me intent, and normalized user/session output fields needed by `verify-session` parity.
2. Implement local credential verification in `backend-hormonia/app/services/auth.py`, using `hashed_password`, active/lock checks, and failed-attempt reset/record logic instead of Firebase token validation on the happy path.
3. Wire `POST /api/v2/auth/login` in `backend-hormonia/app/api/v2/routers/auth.py` to the new service path so it creates the DB session row, writes the Redis session, sets the canonical HttpOnly cookie, and returns normalized metadata; keep `/firebase/verify` clearly scoped as compatibility-only for later slices.
4. Run the API contract suite, fixing cookie flags, error codes, and response normalization until local login behavior matches the new tests.

## Must-Haves

- [ ] Login authenticates by email + password against locally stored credentials and never depends on Firebase token exchange.
- [ ] Successful login writes both the database session row and the Redis session record while keeping the canonical session cookie behavior.
- [ ] Invalid credentials, inactive users, and locked users return stable, non-secret-leaking auth errors.
- [ ] The login response shape is normalized enough for S03 frontend consumption instead of being a Firebase-specific compatibility payload.

## Verification

- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py -q`
- Spot-check that the response payload and `Set-Cookie` header do not contain password or hash data.

## Observability Impact

- Signals added/changed: Login failures become differentiated by stable API error code instead of a generic Firebase-auth failure bucket.
- How a future agent inspects this: Hit `POST /api/v2/auth/login` under test or debug mode and inspect the standardized error payload plus request ID.
- Failure state exposed: Credential mismatch, inactive account, and locked-account outcomes are distinguishable from session-write or unexpected server failures.

## Inputs

- `backend-hormonia/tests/api/v2/test_auth_local_login.py` — failing API contract that defines the slice’s public login behavior.
- `backend-hormonia/app/models/user.py` / `backend-hormonia/app/models/session.py` — existing password, auth-provider, and session persistence fields to reuse rather than redesign.

## Expected Output

- `backend-hormonia/app/services/auth.py` — local credential authentication and failure classification logic.
- `backend-hormonia/app/schemas/v2/auth.py` — local login request/response contract.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical v2 login route issuing first-party sessions.
