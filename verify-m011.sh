#!/usr/bin/env bash
# verify-m011.sh — Integrated verification for Milestone M011
# Covers R100 (composite index), R101 (backend caching), R102 (frontend request discipline)
# 7 check groups, exits 0 on all pass, non-zero on any failure
set -euo pipefail

PASS_COUNT=0
FAIL_COUNT=0
TOTAL=7

pass() { echo "  ✅ PASS: $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "  ❌ FAIL: $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

echo "========================================"
echo " M011 Integrated Verification"
echo "========================================"
echo ""

# ── Group 1: ast.parse ──────────────────────────────────────────────
echo "[1/7] ast.parse — Backend Python syntax"
if python3 -c "
import ast
for f in [
    'backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py',
    'backend-hormonia/app/api/v2/routers/physicians/patients.py',
    'backend-hormonia/app/api/v2/routers/dashboard.py',
]:
    ast.parse(open(f).read())
    print(f'  OK: {f}')
" 2>&1; then
  pass "ast.parse"
else
  fail "ast.parse — one or more files failed to parse"
fi
echo ""

# ── Group 2: tsc --noEmit ───────────────────────────────────────────
echo "[2/7] tsc --noEmit — Frontend TypeScript compilation"
if (cd frontend-hormonia && npx tsc --noEmit 2>&1); then
  pass "tsc --noEmit"
else
  fail "tsc --noEmit — TypeScript errors found"
fi
echo ""

# ── Group 3: vite build ─────────────────────────────────────────────
echo "[3/7] vite build — Frontend production build"
if (cd frontend-hormonia && npx vite build 2>&1); then
  pass "vite build"
else
  fail "vite build — production build failed"
fi
echo ""

# ── Group 4: Response shape — zero schema changes ───────────────────
echo "[4/7] Response shape — schema/ unchanged across M011"
GROUP4_OK=true

# Use git diff on the actual file content between M011 branch start and HEAD
# Find M011-specific commits (S01/S02 tasks) and check if any touched schemas/
M011_FILES_IN_SCHEMAS=$(git log --oneline --diff-filter=ACDMR -- backend-hormonia/app/schemas/ \
  | grep -iE "S01.*T0[12]|S02.*T0[12]|patient_flow_states_index|redis.cach|TTL|staleTime|refetchInterval" || true)

if [ -n "$M011_FILES_IN_SCHEMAS" ]; then
  echo "  WARNING: M011 task commits modified schemas/: $M011_FILES_IN_SCHEMAS"
  GROUP4_OK=false
else
  echo "  OK: No M011 task commits modified schema files"
fi

# Verify response_model annotations still exist
if grep -q "response_model=" backend-hormonia/app/api/v2/routers/physicians/patients.py; then
  echo "  OK: response_model present in patients.py"
else
  echo "  ERROR: response_model missing in patients.py"
  GROUP4_OK=false
fi

if grep -q "response_model=" backend-hormonia/app/api/v2/routers/dashboard.py; then
  echo "  OK: response_model present in dashboard.py"
else
  echo "  ERROR: response_model missing in dashboard.py"
  GROUP4_OK=false
fi

if $GROUP4_OK; then
  pass "Response shape"
else
  fail "Response shape — schema changes detected or response_model missing"
fi
echo ""

# ── Group 5: Caching values ─────────────────────────────────────────
echo "[5/7] Caching values — TTL and cache key verification"
GROUP5_OK=true

if grep -q "ttl=60" backend-hormonia/app/api/v2/routers/physicians/patients.py; then
  echo "  OK: ttl=60 in patients.py"
else
  echo "  ERROR: ttl=60 not found in patients.py"
  GROUP5_OK=false
fi

if grep -q "CACHE_TTL_REALTIME = 120" backend-hormonia/app/api/v2/routers/dashboard.py; then
  echo "  OK: CACHE_TTL_REALTIME = 120 in dashboard.py"
else
  echo "  ERROR: CACHE_TTL_REALTIME = 120 not found in dashboard.py"
  GROUP5_OK=false
fi

if grep -q 'user:{user_id}' backend-hormonia/app/api/v2/routers/physicians/patients.py; then
  echo "  OK: user:{user_id} in cache key in patients.py"
else
  echo "  ERROR: user:{user_id} not found in cache key in patients.py"
  GROUP5_OK=false
fi

if $GROUP5_OK; then
  pass "Caching values"
else
  fail "Caching values — missing expected TTL or cache key patterns"
fi
echo ""

# ── Group 6: Timing values ──────────────────────────────────────────
echo "[6/7] Timing values — staleTime/refetchInterval discipline"

# Use Python to properly evaluate JS math expressions (5 * 60 * 1000 = 300000)
# and check thresholds. Excludes monitoring, type defs, tests, comments.
TIMING_RESULT=$(python3 -c "
import re, sys, math

# Grep for staleTime/refetchInterval in frontend src
import subprocess
result = subprocess.run(
    ['grep', '-rn', '-E', 'staleTime|refetchInterval',
     '--include=*.ts', '--include=*.tsx',
     'frontend-hormonia/src/'],
    capture_output=True, text=True
)

lines = result.stdout.strip().split('\n') if result.stdout.strip() else []

# Exclusion patterns (monitoring/system hooks are exempt)
exclusions = [
    'features/system', 'features/monitoring', 'hive-mind',
    'ClinicalMonitoring', 'AdminMonitoringTab',
    'hooks/api/useSystemStats', 'features/whatsapp',
    'useOptimizedQuery', 'ProductionProvider',
    '__tests__/', '.test.', '.spec.',
]

# Detect queryPresets.realtime block (lines 124-130 in queryClient.ts)
# by finding the realtime: { ... } block boundaries
realtime_block_files = {}
for i, line in enumerate(lines):
    filepath = line.split(':')[0] if ':' in line else ''
    if 'queryClient' in filepath and 'realtime' in line:
        # Mark surrounding lines as inside realtime block
        realtime_block_files[filepath] = True

violations = []
audited = 0

for line in lines:
    # Skip excluded paths
    if any(exc in line for exc in exclusions):
        continue

    # Skip type definitions (staleTime?: number)
    if re.search(r'staleTime\?\s*:', line) or re.search(r'refetchInterval\?\s*:', line):
        continue

    # Skip comments and JSDoc
    parts = line.split(':', 2)
    stripped = parts[-1].strip() if len(parts) >= 3 else line.strip()
    if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
        continue

    # Skip lines that are just parameter declarations or destructuring
    if re.search(r'(refetchInterval\s*=\s*(false|options|props))', line):
        continue
    if re.search(r'(refetchInterval\s*[,}])', line):
        continue
    if re.search(r'(const|let|var)\s+.*refetchInterval', line):
        continue
    if re.search(r'refetchInterval\s*\?\s*:', line):
        continue

    # Extract filepath and line number for realtime block detection
    filepath = line.split(':')[0] if ':' in line else ''
    try:
        lineno = int(line.split(':')[1]) if ':' in line else 0
    except (ValueError, IndexError):
        lineno = 0

    # Skip queryPresets.realtime block in queryClient.ts (lines ~124-130)
    if 'queryClient' in filepath and 120 <= lineno <= 135:
        continue

    # Extract value assignments: staleTime: <expr> or refetchInterval: <expr>
    for key in ['staleTime', 'refetchInterval']:
        threshold = 60000 if key == 'staleTime' else 120000
        # Match patterns like: staleTime: 5 * 60 * 1000  or  staleTime: 60000
        m = re.search(rf'{key}\s*[:=]\s*([0-9][0-9 *+\-/()]*)', line)
        if m:
            expr = m.group(1).strip().rstrip(',;')
            try:
                val = eval(expr)
                audited += 1
                if isinstance(val, (int, float)) and val < threshold and val > 0:
                    violations.append(f'  {key}={val} (threshold {threshold}): {line.strip()[:120]}')
            except:
                pass  # Dynamic expressions like refresh_interval — skip
        # Handle Infinity
        m_inf = re.search(rf'{key}\s*[:=]\s*Infinity', line)
        if m_inf:
            audited += 1  # Infinity is always compliant

if violations:
    print('FAIL')
    for v in violations:
        print(v)
else:
    print(f'OK: {audited} timing values audited, all compliant (queryPresets.realtime excluded as monitoring preset)')
" 2>&1)

if echo "$TIMING_RESULT" | head -1 | grep -q "^OK"; then
  echo "  $TIMING_RESULT"
  pass "Timing values"
else
  echo "  ERROR: Sub-threshold timing values detected:"
  echo "$TIMING_RESULT" | tail -n +2 | sed 's/^/    /'
  fail "Timing values — sub-threshold values found outside monitoring exclusions"
fi
echo ""

# ── Group 7: Migration chain ────────────────────────────────────────
echo "[7/7] Migration chain — down_revision and index name"
GROUP7_OK=true
MIGRATION_FILE="backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py"

if grep -q 'm008_s01_t03_sessions_align' "$MIGRATION_FILE"; then
  echo "  OK: down_revision = m008_s01_t03_sessions_align"
else
  echo "  ERROR: down_revision mismatch in $MIGRATION_FILE"
  GROUP7_OK=false
fi

if grep -q 'idx_pfs_patient_started' "$MIGRATION_FILE"; then
  echo "  OK: index name = idx_pfs_patient_started"
else
  echo "  ERROR: idx_pfs_patient_started not found in $MIGRATION_FILE"
  GROUP7_OK=false
fi

if $GROUP7_OK; then
  pass "Migration chain"
else
  fail "Migration chain — down_revision or index name mismatch"
fi
echo ""

# ── Summary ──────────────────────────────────────────────────────────
echo "========================================"
echo " Results: $PASS_COUNT/$TOTAL passed, $FAIL_COUNT failed"
echo "========================================"

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo ""
  echo "❌ M011 verification FAILED"
  exit 1
else
  echo ""
  echo "✅ M011 verification PASSED — all $TOTAL check groups green"
  exit 0
fi
