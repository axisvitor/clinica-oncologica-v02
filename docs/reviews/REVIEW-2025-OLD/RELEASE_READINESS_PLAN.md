Release Readiness & Security Audit – 2025-10-22
==============================================

Context
-------
- Target deploy date: pending confirmation, assume no later than 2025-10-31.
- Current branch: `docs-refactor-py313`, 16 commits ahead of `origin/docs-refactor-py313`.
- Key focus: ensure Firebase auth hardening truly removes bearer token leakage, clean leftover coverage artifacts, and validate infrastructure integrations (Celery, Redis, Firebase, Gemini, WhatsApp).

Authentication Hardening Verification
------------------------------------
- [x] `frontend-hormonia/src/services/firebase-auth.ts#getCurrentUser` clears `Authorization` in a `finally` block after `/auth/me`.
- [x] `frontend-hormonia/src/contexts/AuthContext.tsx#transformFirebaseUser` wraps `/auth/me` with `try/finally` and clears `apiClient` token.
- [x] Token refresh listeners avoid re-attaching the bearer token to the global client; WebSocket bridge keeps an in-memory token only.
- [ ] Audit any custom hooks/services that call `apiClient.setAuthToken(session.access_token)` to ensure they either operate in mock mode or clear tokens immediately after privileged calls.
- [ ] Write regression tests asserting `apiClient.getAuthToken()` returns `null` after `getCurrentUser`, auth initialization, token refresh, manual `refreshToken()`, and logout flows.
- [ ] Validate the browser network trace in staging: requests after session inspection should omit the `Authorization` header.

Security Checklist
------------------
- Authentication
  - [ ] Confirm Firebase Admin secrets rotation schedule; update `.env.example` notes if new keys were introduced during refactor.
  - [ ] Ensure JWT-related config (`FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`, etc.) present in staging/prod environment stores.
  - [ ] Re-run Playwright smoke tests with intercepted headers to ensure cookie-only auth.
- Backend
  - [ ] Rebuild containers with `make docker-up` in staging; inspect `docker compose logs` for Celery/Redis connectivity errors.
  - [ ] Apply pending Alembic migrations via `make migrate`; double-check `alembic_version` matches HEAD.
  - [ ] Run `make lint`, `make test`, and `make test-cov`; capture reports (exclude `coverage.*` from git).
- Frontend / Quiz
  - [ ] Execute `npm run quality`, `npm run test:e2e:smoke`, and `pnpm test:coverage`.
  - [ ] Verify `frontend-hormonia/src/lib/api-client/core.ts` keeps `Authorization` cleared when session payloads are loaded.
- Observability
  - [ ] Confirm alerting hooks (Sentry/DataDog) use new tokenless requests.
  - [ ] Validate WebSocket handshake rejects stale bearer tokens after logout-all.

Testing & QA Evidence
---------------------
- Collect latest coverage summaries (backend ≥80%, frontend ≥80%, quiz thresholds per `package.json`).
- Attach Playwright smoke artifacts in `frontend-hormonia/test-results/` (clean previous runs first).
- Provide manual QA checklist covering:
  - Login, logout, logout-all, session refresh.
  - Monthly quiz start/submit flow.
  - AI assistant pathways hitting `/services/flow` endpoints.

Operational Readiness
---------------------
- [ ] Remove generated artifacts before merge: `backend-hormonia/coverage.json`, `backend-hormonia/coverage.lcov`, `backend-hormonia/test_results.txt`, `backend-hormonia/flow_test_results.txt`.
- [ ] Update `.gitignore` if coverage outputs can still be produced by CI.
- [ ] Confirm new directories under `backend-hormonia/app/services/flow/` have corresponding tests in `backend-hormonia/tests/`.
- [ ] Review `.env.example` updates with DevOps; ensure Railway/Render secrets updated.
- [ ] Document required feature flags / toggles in `docs/`.

Open Items & Owners
-------------------
- Security regression tests for token cleanup – **Frontend team**.
- Coverage artifact cleanup & gitignore update – **Backend team** (owners of `make test-cov` pipeline).
- Infrastructure validation (Celery, Redis, Gemini integrations) – **DevOps**.
- Final sign-off on Firebase config (service accounts + auth domains) – **Security**.

Approval Gates
--------------
1. ✅ Code review: pending final confirmation on auth cleanup tests.
2. ⏳ Automated test suite (backend/frontend/quiz + Playwright smoke).
3. ⏳ Infrastructure validation report (logs + health checks).
4. ⏳ Security sign-off (header inspection + secrets audit).
5. ⏳ Release manager go/no-go with evidence links uploaded to `REVIEW-2025/`.

Next Actions (as of 2025-10-22)
-------------------------------
- Finish token cleanup test cases and capture HAR evidence from staging.
- Delete committed coverage artifacts, enforce `.gitignore`, rerun tests locally to regenerate artifacts for reference only.
- Produce final `SECURITY_FIXES_SUMMARY.md` entry referencing this plan and the AuthContext fix.
- Schedule staging smoke test window; attach results to release checklist.
