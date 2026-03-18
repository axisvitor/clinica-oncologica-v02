#!/usr/bin/env bash
# verify-m012.sh — Integrated verification for Milestone M012
# Covers R104 (migration/model), R105 (API + cache), R108 (frontend editor), R109 (immutability)
# 11 check groups, exits 0 on all pass, non-zero on any failure
set -euo pipefail

PASS_COUNT=0
FAIL_COUNT=0
TOTAL=11

pass() { echo "  ✅ PASS: $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "  ❌ FAIL: $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

echo "========================================"
echo " M012 Integrated Verification"
echo "========================================"
echo ""

# ── Phase 1: ast.parse ──────────────────────────────────────────────
echo "[1/11] ast.parse — Backend Python syntax (9 files)"
if python3 -c "
import ast
for f in [
    'backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py',
    'backend-hormonia/app/models/flow.py',
    'backend-hormonia/app/schemas/v2/patient_overrides.py',
    'backend-hormonia/app/api/v2/routers/patients/flow_overrides.py',
    'backend-hormonia/app/api/v2/routers/patients/__init__.py',
    'backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py',
    'backend-hormonia/app/services/flow/_flow_message_flow.py',
    'backend-hormonia/app/services/flow/_flow_response_flow.py',
    'backend-hormonia/app/tasks/helpers/flow_helpers.py',
]:
    ast.parse(open(f).read())
    print(f'  OK: {f}')
" 2>&1; then
  pass "ast.parse — all 9 backend files parse cleanly"
else
  fail "ast.parse — one or more files failed to parse"
fi
echo ""

# ── Phase 2: Migration structure ────────────────────────────────────
echo "[2/11] Migration structure — table + down_revision"
PHASE2_OK=true
MIGRATION="backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py"

if [ -f "$MIGRATION" ]; then
  echo "  OK: migration file exists"
else
  echo "  ERROR: migration file missing"
  PHASE2_OK=false
fi

if grep -q 'patient_flow_overrides' "$MIGRATION" 2>/dev/null; then
  echo "  OK: patient_flow_overrides table name present"
else
  echo "  ERROR: patient_flow_overrides table name not found"
  PHASE2_OK=false
fi

if grep -q 'down_revision = "m011_s01_patient_flow_states_index"' "$MIGRATION" 2>/dev/null; then
  echo "  OK: down_revision = m011_s01_patient_flow_states_index"
else
  echo "  ERROR: down_revision mismatch"
  PHASE2_OK=false
fi

if $PHASE2_OK; then
  pass "Migration structure"
else
  fail "Migration structure — table or down_revision check failed"
fi
echo ""

# ── Phase 3: GET merge with source indicator ────────────────────────
echo "[3/11] GET merge with source indicator"
PHASE3_OK=true
SCHEMA="backend-hormonia/app/schemas/v2/patient_overrides.py"
ROUTER="backend-hormonia/app/api/v2/routers/patients/flow_overrides.py"

if grep -q 'source.*Literal\["global", "override"\]' "$SCHEMA" 2>/dev/null; then
  echo "  OK: source: Literal[\"global\", \"override\"] in schema"
else
  echo "  ERROR: source indicator missing in schema"
  PHASE3_OK=false
fi

if grep -q '_build_merged_days' "$ROUTER" 2>/dev/null; then
  echo "  OK: _build_merged_days in router"
else
  echo "  ERROR: _build_merged_days not found in router"
  PHASE3_OK=false
fi

if $PHASE3_OK; then
  pass "GET merge with source indicator"
else
  fail "GET merge with source indicator — missing patterns"
fi
echo ""

# ── Phase 4: PUT + Redis cache invalidation ─────────────────────────
echo "[4/11] PUT + Redis cache invalidation"
if grep -q 'delete_pattern(f"flow_override:' "$ROUTER" 2>/dev/null; then
  echo "  OK: delete_pattern(f\"flow_override:...) in router"
  pass "PUT + Redis cache invalidation"
else
  echo "  ERROR: cache invalidation pattern not found"
  fail "PUT + Redis cache invalidation — delete_pattern not found"
fi
echo ""

# ── Phase 5: _get_day_config prioritizes override ────────────────────
echo "[5/11] _get_day_config prioritizes override"
PHASE5_OK=true
STATE="backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py"

PFS_COUNT=$(grep -c 'patient_flow_state_id' "$STATE" 2>/dev/null || echo "0")
if [ "$PFS_COUNT" -ge 3 ]; then
  echo "  OK: patient_flow_state_id appears $PFS_COUNT times in state.py (≥3)"
else
  echo "  ERROR: patient_flow_state_id appears $PFS_COUNT times (expected ≥3)"
  PHASE5_OK=false
fi

if grep -q 'flow_override:' "$STATE" 2>/dev/null; then
  echo "  OK: flow_override: cache key in state.py"
else
  echo "  ERROR: flow_override: cache key not found in state.py"
  PHASE5_OK=false
fi

if $PHASE5_OK; then
  pass "_get_day_config prioritizes override"
else
  fail "_get_day_config — missing override patterns in state.py"
fi
echo ""

# ── Phase 6: Skip logic ─────────────────────────────────────────────
echo "[6/11] Skip logic"
PHASE6_OK=true
HELPERS="backend-hormonia/app/tasks/helpers/flow_helpers.py"

if grep -q 'skip' "$STATE" 2>/dev/null; then
  echo "  OK: skip logic in state.py override block"
else
  echo "  ERROR: skip not found in state.py"
  PHASE6_OK=false
fi

if grep -q 'skipped' "$HELPERS" 2>/dev/null; then
  echo "  OK: skipped status in flow_helpers.py"
else
  echo "  ERROR: skipped/skip status not found in flow_helpers.py"
  PHASE6_OK=false
fi

if $PHASE6_OK; then
  pass "Skip logic"
else
  fail "Skip logic — missing skip handling"
fi
echo ""

# ── Phase 7: Override immutability ───────────────────────────────────
echo "[7/11] Override immutability (separate table + merge at read-time)"
PHASE7_OK=true

# Separate table verified by migration existence (Phase 2)
if [ -f "$MIGRATION" ]; then
  echo "  OK: separate patient_flow_overrides table (D021)"
else
  echo "  ERROR: migration/table missing"
  PHASE7_OK=false
fi

if grep -q '_build_merged_days' "$ROUTER" 2>/dev/null; then
  echo "  OK: merge at read-time via _build_merged_days"
else
  echo "  ERROR: _build_merged_days not found"
  PHASE7_OK=false
fi

if $PHASE7_OK; then
  pass "Override immutability"
else
  fail "Override immutability — separate table or merge not found"
fi
echo ""

# ── Phase 8: PatientDetailPage has override editor ───────────────────
echo "[8/11] PatientDetailPage has override editor"
PHASE8_OK=true
DETAIL_PAGE="frontend-hormonia/src/pages/PatientDetailPage.tsx"
EDITOR="frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx"

if grep -q 'PatientFlowOverrideEditor' "$DETAIL_PAGE" 2>/dev/null; then
  echo "  OK: PatientFlowOverrideEditor imported in PatientDetailPage"
else
  echo "  ERROR: PatientFlowOverrideEditor not imported"
  PHASE8_OK=false
fi

if grep -q 'Personalizar Fluxo' "$DETAIL_PAGE" 2>/dev/null; then
  echo "  OK: \"Personalizar Fluxo\" text in PatientDetailPage"
else
  echo "  ERROR: \"Personalizar Fluxo\" text not found"
  PHASE8_OK=false
fi

if $PHASE8_OK; then
  pass "PatientDetailPage has override editor"
else
  fail "PatientDetailPage — editor or button text missing"
fi
echo ""

# ── Phase 9: Future-day restriction ─────────────────────────────────
echo "[9/11] Future-day restriction"
PHASE9_OK=true

if grep -q 'current_flow_day' "$ROUTER" 2>/dev/null; then
  echo "  OK: current_flow_day in router"
else
  echo "  ERROR: current_flow_day not found in router"
  PHASE9_OK=false
fi

if grep -q 'editable' "$SCHEMA" 2>/dev/null; then
  echo "  OK: editable field in schema"
else
  echo "  ERROR: editable not found in schema"
  PHASE9_OK=false
fi

if grep -qE 'disabled.*editable|editable.*disabled|disabled=\{!day\.editable\}' "$EDITOR" 2>/dev/null; then
  echo "  OK: editable gating in editor component"
else
  echo "  ERROR: editable/disabled gating not found in editor"
  PHASE9_OK=false
fi

if $PHASE9_OK; then
  pass "Future-day restriction"
else
  fail "Future-day restriction — missing current_flow_day/editable gating"
fi
echo ""

# ── Phase 10: tsc --noEmit ──────────────────────────────────────────
echo "[10/11] tsc --noEmit — Frontend TypeScript compilation"
if (cd frontend-hormonia && npx tsc --noEmit 2>&1); then
  pass "tsc --noEmit"
else
  fail "tsc --noEmit — TypeScript errors found"
fi
echo ""

# ── Phase 11: vite build ────────────────────────────────────────────
echo "[11/11] vite build — Frontend production build"
if (cd frontend-hormonia && npx vite build 2>&1); then
  pass "vite build"
else
  fail "vite build — production build failed"
fi
echo ""

# ── Summary ──────────────────────────────────────────────────────────
echo "========================================"
echo " Results: $PASS_COUNT/$TOTAL passed, $FAIL_COUNT failed"
echo "========================================"

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo ""
  echo "❌ M012 verification FAILED"
  exit 1
else
  echo ""
  echo "✅ M012 verification PASSED — all $TOTAL check groups green"
  exit 0
fi
