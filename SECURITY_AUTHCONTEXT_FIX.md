# Security Fix: AuthContext Token Cleanup

## Summary
- **Severity:** P0 (critical)
- **Status:** RESOLVED – fix landed on 2025-10-22
- **Primary file:** `frontend-hormonia/src/contexts/AuthContext.tsx`
- **Objective:** Keep the shared `apiClient` header-free so the app relies on httpOnly cookies after each token inspection.

## Issue Recap
Historically, `AuthContext` called `apiClient.setAuthToken(token)` inside:
1. `transformFirebaseUser`
2. The Firebase auth-state listener
3. The Firebase token-refresh listener

The token was never cleared, so any code path that checked the current user left the bearer token attached to the global client. That undermined the cookie-only hardening completed in `firebase-auth.ts` and reintroduced XSS/session hijack risk.

## Remediation (Applied)
- Wrapped the `/auth/me` validation in `transformFirebaseUser` with a nested `try/finally`, guaranteeing `apiClient.clearAuthToken()` executes on success and failure (`AuthContext.tsx:113-137`).
- Removed the extra `setAuthToken` calls from the auth-state listener so WebSocket connections still use the in-memory Firebase token but the shared HTTP client falls back to cookies (`AuthContext.tsx:209`).
- Updated the token-refresh listener to avoid reattaching the bearer header; it now simply updates the WebSocket bridge and session state (`AuthContext.tsx:251`).
- Dropped the redundant `setAuthToken` in the manual `refreshToken` helper (`AuthContext.tsx:467`).

### Before (vulnerable)
```typescript
apiClient.setAuthToken(token);
const response = await apiClient.auth.me();
return response?.data ?? null;
// No cleanup -> Authorization header persisted globally
```

### After (secure)
```typescript
try {
  apiClient.setAuthToken(token);
  const response = await apiClient.auth.me();
  return response?.data ?? null;
} finally {
  apiClient.clearAuthToken();
  logger.log("Cleared Firebase token after transformFirebaseUser - using cookie-only auth");
}
```

## Validation Steps
1. **Automated**
   - `npm run typecheck` (frontend)
   - `npm run lint` (frontend)
   - Upcoming: add a regression test that asserts `apiClient.getAuthToken()` returns `null` after calling `getCurrentUser`, `refreshToken`, and the auth-state observer.
2. **Manual**
   - Log into staging, open DevTools, and watch network requests for `/auth/me`, `/auth/refresh`, or any subsequent API call. After each inspection, the `Authorization` header must be absent; only cookies should authenticate the request.
   - Trigger a token refresh via idle-period waiting or manual `refreshToken()` invocation in the console and confirm the header is still missing.

## Follow-up Actions
- Backfill the regression tests listed above (tracked in release readiness checklist).
- Include HAR captures from staging that demonstrate the missing header after session validation.
- Communicate to QA and Security that the AuthContext blocker is closed; update the release checklist status accordingly.

## References
- Source of fix: `frontend-hormonia/src/contexts/AuthContext.tsx`
- Comparison implementation: `frontend-hormonia/src/services/firebase-auth.ts`
- Related release document: `REVIEW-2025/RELEASE_READINESS_PLAN.md`
