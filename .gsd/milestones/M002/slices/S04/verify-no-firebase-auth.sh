#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
cd "$ROOT_DIR"

failures=0

check_pattern() {
  local label="$1"
  local pattern="$2"
  shift 2

  local files=()
  for candidate in "$@"; do
    if [[ -e "$candidate" ]]; then
      files+=("$candidate")
    fi
  done

  if (( ${#files[@]} == 0 )); then
    return 0
  fi

  local matches
  matches="$(rg -n --no-heading -S -e "$pattern" -- "${files[@]}" || true)"

  if [[ -n "$matches" ]]; then
    echo "FAIL [$label]"
    echo "$matches"
    echo
    failures=$((failures + 1))
  fi
}

check_exists() {
  local label="$1"
  local file="$2"

  if [[ -e "$file" ]]; then
    echo "FAIL [$label]"
    echo "$file"
    echo
    failures=$((failures + 1))
  fi
}

check_pattern \
  "frontend auth api firebase bridge" \
  'createSession:|/api/v2/auth/firebase/verify|firebaseToken' \
  frontend-hormonia/src/lib/api-client/auth.ts

check_pattern \
  "frontend auth provider firebase token naming" \
  'getFirebaseToken' \
  frontend-hormonia/src/app/providers/AuthContext.tsx

check_pattern \
  "frontend password change firebase runtime" \
  'Firebase reauth|Firebase re-auth|Firebase reauthentication|firebase/auth|reauthenticateWithCredential|EmailAuthProvider|handles reauthentication via Firebase|Update password in Firebase' \
  frontend-hormonia/src/hooks/useSettings.ts \
  frontend-hormonia/src/hooks/usePasswordChange.ts \
  frontend-hormonia/src/features/settings/sections/SecuritySettings.tsx

check_pattern \
  "frontend runtime firebase env/config guidance" \
  'VITE_FIREBASE_|legacyFirebaseConfigured|Firebase Authentication' \
  frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx \
  frontend-hormonia/src/features/initialization/ServiceMonitor.tsx \
  frontend-hormonia/src/lib/runtime-config.ts \
  frontend-hormonia/src/lib/config-initializer.tsx \
  frontend-hormonia/vite.config.ts

check_pattern \
  "frontend package firebase dependency" \
  '"firebase"\s*:' \
  frontend-hormonia/package.json

check_pattern \
  "backend auth firebase verify seam" \
  '/firebase/verify|FirebaseTokenVerify|Verify Firebase token|verify_firebase_token as verify_token' \
  backend-hormonia/app/api/v2/routers/auth.py \
  backend-hormonia/app/schemas/v2/auth.py

check_pattern \
  "backend password change firebase semantics" \
  'Firebase UID not found|Update password in Firebase|firebase_admin\.auth|Firebase Admin SDK|Failed to change password\. Please try again\.' \
  backend-hormonia/app/api/v2/routers/auth.py

check_pattern \
  "backend debug firebase token inspection" \
  'verify_firebase_token|Firebase ID token|Firebase token' \
  backend-hormonia/app/api/v2/routers/debug/auth.py

check_pattern \
  "backend operational firebase requirements" \
  'Firebase Admin SDK is not fully configured|Configure Firebase for authentication features|Firebase not configured|authentication will not work|component_name == "firebase"|components_to_init = .*firebase|component_names = \["database", "redis", "firebase"\]|required_settings = \["FIREBASE_PROJECT_ID"' \
  backend-hormonia/app/routers/health.py \
  backend-hormonia/app/api/v2/routers/system/health.py \
  backend-hormonia/app/api/v2/routers/system/validation.py \
  backend-hormonia/app/api/v2/routers/system/initialization.py \
  backend-hormonia/app/api/v2/routers/system/helpers/health_checker.py \
  backend-hormonia/app/dependencies/auth_dependencies.py \
  backend-hormonia/app/schemas/v2/system.py

check_pattern \
  "backend public config firebase env publication" \
  'VITE_FIREBASE_|FIREBASE_WEB_|get_firebase_public_config|Firebase public configuration' \
  backend-hormonia/app/api/v2/routers/system/config.py \
  backend-hormonia/app/api/v2/routers/system/helpers/config_builder.py \
  backend-hormonia/app/schemas/v2/system.py

check_pattern \
  "docs and e2e guidance firebase staff-auth instructions" \
  'VITE_FIREBASE_|FIREBASE_ADMIN_|Firebase Authentication|Configure Firebase|Firebase web API key|Firebase project ID' \
  frontend-hormonia/tests/e2e/README.md \
  frontend-hormonia/tests/e2e/SETUP_INSTRUCTIONS.md \
  docs/frontend/guides/api/API_GUIDE.md \
  docs/frontend/guides/configuration/ENVIRONMENT_GUIDE.md \
  docs/frontend/guides/deployment/DEPLOYMENT_GUIDE.md \
  .env.example

check_exists \
  "legacy firebase-only frontend proof suite still present" \
  frontend-hormonia/tests/auth/firebase-auth-comprehensive.test.tsx

check_exists \
  "legacy firebase-only unit auth suite still present" \
  frontend-hormonia/tests/unit/services/firebase-auth.comprehensive.test.ts

if (( failures > 0 )); then
  echo "verify-no-firebase-auth.sh: ${failures} residue check(s) failed."
  exit 1
fi

echo "verify-no-firebase-auth.sh: session-first staff-auth hotspots are free of Firebase-auth residue."
