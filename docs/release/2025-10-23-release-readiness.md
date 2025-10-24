# Release Readiness and Security Audit — 2025-10-23

**Scope**: Clinica Oncologica v02 monorepo (`backend-hormonia`, `frontend-hormonia`, `quiz-mensal-interface`)  
**Prepared By**: Codex (GPT-5)  
**Objective**: Validate authentication hardening, eliminate token leakage risk, and confirm build hygiene before production deployment.

---

## Executive Summary
- Cookie-first authentication is enforced in `frontend-hormonia/src/services/firebase-auth.ts`, but the React context still mirrors Firebase tokens through several lifecycle paths. Those tokens must be cleared with the same `apiClient.clearAuthToken()` guarantees implemented in the service layer.
- Backend coverage artifacts (`coverage.json`, `coverage.lcov`, `htmlcov/`) were historically tracked. They are now ignored locally yet linger in git history; a cleanup plus pre-commit guard is required to keep the tree clean.
- Environment templates drifted alongside new Flow, Messaging, and Monitoring services. Each added `*_API_KEY` requires a rotation checklist before Go-Live.

**Release Blockers** (must resolve before prod):
1. Finish AuthContext token hygiene patch and extend regression tests.
2. Purge backend coverage artifacts from version control and document clean workflow.
3. Close environment variable audit (redis, firebase, messaging) and record rotation outcomes.

---

## Authentication Review

| Component | Current Behaviour | Gap | Required Action |
|-----------|------------------|-----|-----------------|
| `frontend-hormonia/src/contexts/AuthContext.tsx` | Fetches `/auth/me` with `apiClient.setAuthToken(token)` but only clears the header on a subset of paths. Mock mode still stores session tokens on the global client. | Token persistence during logout/error flows keeps Authorization headers alive beyond WebSocket needs. | Convert all “cleanup” calls to `apiClient.clearAuthToken()`; wrap every temporary token usage in `try/finally`; add explicit cleanups for logoutAll and error branches. |
| `frontend-hormonia/src/services/firebase-auth.ts` | Already clears credentials in `finally` blocks and during token refresh. | None, but tests do not assert cleanup. | Add Vitest coverage that spies on `apiClient.clearAuthToken` after login/refresh/logout. |
| Backend `/auth/session/*` routers | Validate cookies only; bearer tokens rejected. | Alignment OK. | Keep integration tests to confirm absence of Authorization header acceptance. |
| WebSocket manager (`frontend-hormonia/src/lib/websocket/index.ts`) | Still depends on raw Firebase ID token. | Expected (socket layer uses token). | Confirm token never persists outside memory; add reconnection tests after logout. |

### Token Cleanup Matrix

- **Initialization (`useEffect` on mount)**  
  - Fetch CSRF, attach Firebase listener. Ensure initial `apiClient.setAuthToken` usage clears in `finally`.

- **Login Success (mock vs firebase)**  
  - Mock mode continues to rely on mock tokens (acceptable).  
  - Firebase mode should avoid storing the ID token past WebSocket usage.

- **Logout / Logout All / Error Paths**  
  - Replace every `apiClient.setAuthToken(null)` with `apiClient.clearAuthToken()` for parity with the service layer.  
  - After `firebaseAuthLazy.signOut()` ensure WebSocket disconnect occurs before returning.

- **Token Refresh Listener**  
  - Remove redundant `apiClient.setAuthToken(newToken)`; rely on WebSocket update only.

### Required Test Updates
1. **Unit**: Extend `frontend-hormonia/tests/contexts/AuthContext.test.tsx` to spy on `apiClient.clearAuthToken` across login/logout and error flows.
2. **Integration**: Add Cypress or Playwright smoke step verifying that subsequent REST calls omit the Authorization header after login (cookie-only).
3. **Regression**: Confirm WebSocket still reconnects using in-memory Firebase tokens.

---

## Backend Coverage Artifact Hygiene

- **Problem**: Running `make test-cov` creates `coverage.json`, `coverage.lcov`, and `htmlcov/`; these were tracked historically, causing noisy diffs.
- **State**: `.gitignore` now contains the patterns, but git history still lists the artifacts. Working tree shows deletions (`git status` reports `D backend-hormonia/coverage.json` etc.).
- **Remediation Plan**:
  1. `git rm --cached backend-hormonia/coverage.json backend-hormonia/coverage.lcov backend-hormonia/htmlcov/**`.
  2. Commit removal with `chore(backend): drop coverage artifacts`.
  3. Add a `make clean-coverage` target that deletes `backend-hormonia/{coverage.json,coverage.lcov,htmlcov/}`.
  4. Document in `backend-hormonia/README.md` that coverage reports are ephemeral and regenerated via `make test-cov`.

---

## Environment and Secret Audit

| Area | Variables Introduced (Oct 2025) | Risk | Action |
|------|---------------------------------|------|--------|
| Flow Services | `FLOW_API_KEY`, `FLOW_WEBHOOK_SECRET` | Keys stored only in `.env.local`. | Rotate keys, update `.env.example`, confirm encryption in deployment pipeline. |
| Messaging (WhatsApp/SMS) | `WHATSAPP_API_TOKEN`, `TWILIO_AUTH_TOKEN` | Mixed staging/production usage. | Ensure stage + prod tokens unique; document rotation cadence. |
| Monitoring | `DATADOG_API_KEY`, `SENTRY_DSN_BACKEND` | Partial documentation. | Add to `.env.example` and release checklist; verify dashboards before cutover. |
| Firebase | `FIREBASE_SERVICE_ACCOUNT_KEY` | Rotated during cookie migration. | Confirm key uploaded to CI secret store; re-run staging login smoke test. |
| Redis | `REDIS_URL`, `REDIS_PASSWORD` | New simple session service introduced. | Validate TLS configuration; ensure `redis://` credentials not logged. |

**Verification Tasks**
- Diff `.env.example` versus production `.env` (team to verify manually).
- Run `make migrate` dry-run to ensure no missing env stops migrations.
- Capture approvals for each rotation in change log.

---

## Validation Checklist Before Release

### Security
- [ ] Merge AuthContext token hygiene patch.
- [ ] Confirm automated tests around cookie-only auth pass (`npm run quality`).
- [ ] Run `npm run test:e2e:smoke` focusing on login/logout flows.
- [ ] Trigger manual XSS scan on login page (Burp or OWASP ZAP) to validate absence of bearer tokens in headers.

### Backend Quality Gates
- [ ] `make lint` and `make format` clean.
- [ ] `make test-cov` passes with coverage ≥ 80% (target 85%). Document percentage in this report once executed.
- [ ] `make clean-coverage` executed post-test (keeps tree clean).

### Frontend / Quiz Apps
- [ ] `frontend-hormonia`: `npm run quality`, `npm run test:e2e:smoke`.
- [ ] `quiz-mensal-interface`: `pnpm test:coverage`, `pnpm type-check`.

### Operations
- [ ] `docker compose up` (via `make docker-up`) logs show healthy Celery and Redis.
- [ ] `/health/ready` returns 200 on staging.
- [ ] Monitoring dashboards reviewed (Sentry, DataDog).
- [ ] Backup & rollback procedures rehearsed (Postgres dump + Redis snapshot).

---

## Recommended Timeline
1. **2025-10-23 (Today)**  
   - Land AuthContext cleanup patch; regenerate unit tests.  
   - Execute backend coverage cleanup (`git rm --cached` + commit).  
   - Update `.env.example` with any missing keys and capture review sign-offs.
2. **2025-10-24**  
   - Run full regression suite across backend/frontend/quiz.  
   - Complete security scan (dependency audit + ZAP).
3. **2025-10-25**  
   - Freeze code, tag release, and kick off deployment runbook after QA sign-off.

---

## Sign-Off Fields
- **Security Lead**: _____________________ (Date: ________________)
- **Backend Lead**: ______________________ (Date: ________________)
- **Frontend Lead**: _____________________ (Date: ________________)
- **Product Owner**: _____________________ (Date: ________________)

---

*Store this document alongside test evidence (coverage reports, Playwright artifacts) in `validation-reports/2025-10-23/` once generated.*
