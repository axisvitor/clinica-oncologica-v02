===============================================================
 RAILWAY VARIABLES UPDATE GUIDE - WAVE 2 DEPLOYMENT
===============================================================

This guide explains the exact process to sync environment variables
from the local .env files to Railway (production). It assumes:
- Wave 2 backend/frontend changes are already merged locally;
- You have Railway CLI installed and authenticated (`railway login`).

FILES & SCRIPT
--------------
- Script: scripts\update-railway-vars.ps1
- Backend env source: backend-hormonia\.env.FINAL
- Frontend env source: frontend-hormonia\.env.FINAL
- Manual update still needed: FIREBASE_ADMIN_PRIVATE_KEY

USAGE
-----
1. Open PowerShell and navigate to the repository root.
2. Set execution policy if needed:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```
3. Run in dry-run mode to preview:
   ```powershell
   .\scripts\update-railway-vars.ps1 -DryRun
   ```
4. Execute for production:
   ```powershell
   .\scripts\update-railway-vars.ps1 `
       -Environment production `
       -BackendService backend-hormonia `
       -FrontendService frontend-hormonia
   ```

SCRIPT BEHAVIOR
---------------
- Validates Railway CLI.
- Reads specific keys from .env.FINAL files (backend & frontend).
- Displays the values (truncated) before update.
- In dry-run, prints equivalent Railway CLI commands only.
- In live mode, executes `railway variables set` per key.
- Prints summary and reminder for manual FIREBASE_ADMIN_PRIVATE_KEY update.

TRICKY DETAILS
--------------
- Backend: ALLOWED_ORIGINS uses HTTPS URIs; ensure brackets/quotes remain.
- Backend: FIREBASE_BLOCK_PUBLIC_DOMAINS stays `false` in Railway.
- Backend: AUTO_PROVISION_SUPABASE_USERS removed automatically.
- Frontend: Supabase auth flags set to false; Firebase flag set to true.
- Manual step: FIREBASE_ADMIN_PRIVATE_KEY cannot be set via CLI because of multiline.

MANUAL STEP
-----------
1. Open https://railway.app and log in.
2. Project → Backend Service → Variables tab.
3. Edit FIREBASE_ADMIN_PRIVATE_KEY.
4. Copy entire PEM value from backend-hormonia\.env (lines 39-67).
5. Save and redeploy backend service.

VERIFICATION
------------
- After updates, tail logs to confirm services read the new env vars:
  ```powershell
  railway logs --service backend --tail
  railway logs --service frontend --tail
  ```
- Confirm CORS, Firebase auth, and feature flags behave as expected.

TROUBLESHOOTING
---------------
- `Railway CLI não encontrado`: install via `npm i -g @railway/cli`.
- `Key not found`: ensure target key exists in .env.FINAL source files.
- `ExitCode != 0`: rerun with `-DryRun` to confirm command syntax.
- Private key issues: verify manual step executed correctly.

===============================================================
