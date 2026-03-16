# S03: Purga final de bridges, tombstones, serviços mortos e narrativa operacional errada — UAT

**Milestone:** M006
**Written:** 2026-03-15

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S03 is static cleanup — no runtime behavior change beyond the SESSION_TTL_SECONDS rename. All proof is through absence scans, import checks, build/typecheck, and contract tests.

## Preconditions

- Working directory is the project root.
- Node.js and npm available for frontend build/typecheck/vitest.
- Python 3 available for backend import checks.
- `WHATSAPP_WUZAPI_TOKEN` set to any non-empty value (e.g. `test-token`) for backend import validation.

## Smoke Test

```bash
cd frontend-hormonia && npm run build && cd ../backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token python3 -c "from app.service_provider import ServiceProvider; print('ok')"
```
Both commands exit 0 — the post-cleanup tree compiles and imports cleanly.

## Test Cases

### 1. Dead backend files are absent

1. Run:
   ```bash
   ! test -f backend-hormonia/app/services/session_service.py && \
   ! test -f backend-hormonia/app/dependencies/auth_legacy_firebase.py && \
   ! test -f backend-hormonia/tests/unit/test_auth_dependency_module_split.py && \
   echo "PASS"
   ```
2. **Expected:** Prints `PASS`. All three files must not exist.

### 2. Dead frontend bridges, barrels, and Firebase Hosting residue are absent

1. Run:
   ```bash
   ! test -f frontend-hormonia/lib/flow-engine/FlowEngine.ts && \
   ! test -f frontend-hormonia/lib/flow-engine/TemplateManager.ts && \
   ! test -f frontend-hormonia/lib/types/flow.ts && \
   ! test -f frontend-hormonia/lib/types/ai.ts && \
   ! test -f frontend-hormonia/lib/types/api.ts && \
   ! test -f frontend-hormonia/lib/types/flow-designer.ts && \
   ! test -f frontend-hormonia/lib/types/messages.ts && \
   ! test -f frontend-hormonia/lib/types/message-types.ts && \
   ! test -f frontend-hormonia/firebase.json && \
   ! test -f frontend-hormonia/.firebaserc && \
   ! test -d frontend-hormonia/lib/flow-engine && \
   ! test -d frontend-hormonia/lib/types && \
   echo "PASS"
   ```
2. **Expected:** Prints `PASS`. All 10 files and 2 directories must not exist.

### 3. Frontend build and typecheck pass without deleted bridges

1. Run:
   ```bash
   cd frontend-hormonia && npm run build && npm run typecheck
   ```
2. **Expected:** Build exits 0. Typecheck may show 6 pre-existing errors in `tests/e2e/playwright.config.e2e.ts` (TS4111) — these predate S03 and are not regressions.

### 4. Frontend import-boundaries contract tests pass

1. Run:
   ```bash
   cd frontend-hormonia && npx vitest run tests/unit/import-boundaries/
   ```
2. **Expected:** 2 test files, 6 tests, all pass. The `dead-compat-cleanup.contract.test.ts` assertions confirm deleted files stay absent.

### 5. Backend imports clean after dead service removal

1. Run:
   ```bash
   cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token python3 -c "from app.service_provider import ServiceProvider; print('backend imports clean')"
   ```
2. **Expected:** Prints `backend imports clean` with exit 0.

### 6. S01 residue guard still green

1. Run:
   ```bash
   bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend
   ```
2. **Expected:** Output ends with `RESULT: --check backend OK`.

### 7. FIREBASE_SESSION_TTL_SECONDS gone from app code

1. Run:
   ```bash
   grep -r 'FIREBASE_SESSION_TTL_SECONDS' backend-hormonia/app/ --include='*.py' | grep -v __pycache__ | wc -l
   ```
2. **Expected:** Output is `0`.

### 8. WHATSAPP_EVOLUTION_ gone from Cloud Run manifests

1. Run:
   ```bash
   grep -r 'WHATSAPP_EVOLUTION_' backend-hormonia/config/cloud-run/ | wc -l
   ```
2. **Expected:** Output is `0`.

### 9. Firebase Hosting CORS origins gone from security.py

1. Run:
   ```bash
   grep -r 'firebaseapp\.com\|web\.app' backend-hormonia/app/config/settings/security.py | wc -l
   ```
2. **Expected:** Output is `0`.

### 10. Historical archive marker exists

1. Run:
   ```bash
   test -f backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md && echo "PASS"
   ```
2. **Expected:** Prints `PASS`.

### 11. Workflows free of Firebase Admin narrative

1. Run:
   ```bash
   grep -l 'Firebase Admin' .github/workflows/rls-api-tests.yml .github/workflows/postman-tests.yml 2>/dev/null | wc -l
   ```
2. **Expected:** Output is `0`.

### 12. Architecture docs free of Firebase Admin SDK narrative

1. Run:
   ```bash
   grep -c 'Firebase Admin SDK' docs/backend/architecture/overview.md
   ```
2. **Expected:** Output is `0`.

### 13. Pre-commit Firebase API key scan preserved

1. Run:
   ```bash
   grep -c -i 'firebase.*api.*key' .github/workflows/pre-commit-validation.yml
   ```
2. **Expected:** Output is > 0 (the scan is intentionally kept).

### 14. Merge markers absent from active test paths

1. Run:
   ```bash
   rg -l '^<<<<<<<|^=======$|^>>>>>>>' backend-hormonia/tests frontend-hormonia/tests frontend-hormonia/src --glob '!**/node_modules/**' | wc -l
   ```
2. **Expected:** Output is `0`.

## Edge Cases

### FIREBASE_ADMIN_* intentionally preserved in env templates

1. Run:
   ```bash
   grep -c 'FIREBASE_ADMIN' backend-hormonia/.env.example
   ```
2. **Expected:** Output is > 0. These vars are still consumed by live code (`firebase_user_sync_service.py`, `security.py`) and must NOT be removed until that code is deleted.

### /session/* tombstone intentionally preserved

1. Run:
   ```bash
   grep -c '/session/' backend-hormonia/app/api/v2/routers/auth_session.py
   ```
2. **Expected:** Output is > 0. The root `/session/*` 410 tombstone is an explicit retirement contract, not dead code.

### firebase_user_sync_service.py intentionally preserved

1. Run:
   ```bash
   test -f backend-hormonia/app/services/firebase_user_sync_service.py && echo "PRESERVED"
   ```
2. **Expected:** Prints `PRESERVED`. This service is explicitly out of scope for S03 deletion.

## Failure Signals

- Any deleted file reappearing (caught by contract tests and absence scans).
- `FIREBASE_SESSION_TTL_SECONDS` appearing in backend app code (old env name leaked back).
- `WHATSAPP_EVOLUTION_*` appearing in Cloud Run manifests (old naming leaked back).
- `Firebase Admin` appearing in workflow files (stale narrative reintroduced).
- S01 residue guard failing `--check backend` (anchor drift from deleted files).
- Frontend build or import-boundaries tests failing (deleted bridge was actually a live dependency).

## Requirements Proved By This UAT

- R052 (partial) — S03 proves dead backend services, dead frontend bridges, Firebase Hosting residue, config defaults, deployment manifests, workflows, and docs are cleaned to canonical state. Full R052 validation awaits S04 closeout pack.

## Not Proven By This UAT

- Assembled mounted stack still works post-purga (S04 scope — mounted proof runner).
- Final-schema replay `fresh`/`existing` still green post-purga (S04 scope).
- Runtime behavior of SESSION_TTL_SECONDS rename (no live runtime exercised — static rename only).

## Notes for Tester

- The 6 pre-existing TypeScript errors in `playwright.config.e2e.ts` are cosmetic (TS4111 index signature access) and predate S03. Ignore them.
- `ServiceProvider()` requires a `db` argument — the import-level check is the practical substitute for instantiation.
- Set `WHATSAPP_WUZAPI_TOKEN` to any value before running backend import checks; unset triggers intentional startup validation failure (CFG-02).
