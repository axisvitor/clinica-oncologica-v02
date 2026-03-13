#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    'Usage:' \
    '  bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report <backend|frontend|all>' \
    '  bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check <backend|frontend|all>'
}

MODE="${1:-}"
SCOPE="${2:-}"

case "$MODE" in
  --report|--check) ;;
  *)
    usage
    exit 64
    ;;
esac

case "$SCOPE" in
  backend|frontend|all) ;;
  *)
    usage
    exit 64
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
RESEARCH_FILE="$SCRIPT_DIR/S01-RESEARCH.md"
SUMMARY_FILE="$SCRIPT_DIR/S01-SUMMARY.md"
UAT_FILE="$SCRIPT_DIR/S01-UAT.md"
SELF_RELATIVE_PATH='.gsd/milestones/M003/slices/S01/verify-evidence-map.sh'

failures=()

relative_path() {
  local path="$1"
  printf '%s' "${path#$REPO_ROOT/}"
}

add_failure() {
  failures+=("$1")
}

line_count() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    printf '0'
    return
  fi
  wc -l < "$file" | tr -d ' '
}

rg_count() {
  local pattern="$1"
  shift
  (rg -o --no-messages "$pattern" "$@" || true) | wc -l | tr -d ' '
}

file_has_text() {
  local file="$1"
  local needle="$2"
  rg -F --quiet -- "$needle" "$file"
}

require_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    add_failure "missing file: $(relative_path "$file")"
  fi
}

require_text() {
  local file="$1"
  local needle="$2"
  local label="$3"

  if [[ ! -f "$file" ]]; then
    add_failure "missing file: $(relative_path "$file")"
    return
  fi

  if ! file_has_text "$file" "$needle"; then
    add_failure "missing ${label} in $(relative_path "$file"): ${needle}"
  fi
}

require_exact() {
  local file="$1"
  local label="$2"
  local format="$3"
  shift 3
  local needle
  printf -v needle "$format" "$@"
  require_text "$file" "$needle" "$label"
}

emit_heading() {
  printf '\n[%s]\n' "$1"
}

emit_metric() {
  printf '  - %s=%s\n' "$1" "$2"
}

emit_note() {
  printf '  - %s\n' "$1"
}

open_scaffold_count() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    printf '0'
    return
  fi
  (rg -n '\[ \]' "$file" || true) | wc -l | tr -d ' '
}

report_open_scaffolds() {
  local file="$1"
  local limit="${2:-5}"
  local count=0
  local line

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    count=$((count + 1))
    if (( count <= limit )); then
      add_failure "open scaffold item in $(relative_path "$file"): $line"
    fi
  done < <(rg -n '\[ \]' "$file" || true)

  if (( count > limit )); then
    add_failure "open scaffold items remaining in $(relative_path "$file"): ${count} total"
  fi
}

read_duplicate_export_data() {
  python3 - <<'PY'
import re
from pathlib import Path
files = [
    Path('frontend-hormonia/src/types/api.ts'),
    Path('frontend-hormonia/src/lib/api-client/types.ts'),
]
pattern = re.compile(r'^export\s+(?:interface|type|enum|class)\s+([A-Za-z0-9_]+)', re.M)
exports = [set(pattern.findall(path.read_text())) for path in files]
common = sorted(exports[0] & exports[1])
print(f"{len(common)}|{', '.join(common)}")
PY
}

cd "$REPO_ROOT"

IFS='|' read -r frontend_duplicate_exports frontend_duplicate_export_names <<< "$(read_duplicate_export_data)"

backend_auth_lines="$(line_count backend-hormonia/app/dependencies/auth_dependencies.py)"
backend_auth_router_lines="$(line_count backend-hormonia/app/api/v2/routers/auth.py)"
backend_auth_session_lines="$(line_count backend-hormonia/app/routers/auth_session.py)"
backend_admin_dependencies_lines="$(line_count backend-hormonia/app/api/v2/routers/admin/dependencies.py)"
backend_reports_lines="$(line_count backend-hormonia/app/api/v2/routers/reports.py)"
backend_enhanced_reports_lines="$(line_count backend-hormonia/app/api/v2/routers/enhanced_reports.py)"
backend_roles_dependencies_lines="$(line_count backend-hormonia/app/api/v2/routers/roles/dependencies.py)"
backend_flows_lines="$(line_count backend-hormonia/app/api/v2/routers/flows.py)"
backend_message_handler_lines="$(line_count backend-hormonia/app/services/webhook/handlers/message_handler.py)"
backend_session_dependency_calls="$(rg_count 'Depends\(get_current_user_from_session\)' backend-hormonia/app)"
backend_user_object_dependency_calls="$(rg_count 'Depends\(get_current_user_object_from_session\)' backend-hormonia/app)"
backend_user_dependency_calls="$(rg_count 'Depends\(get_current_user\)' backend-hormonia/app)"
backend_admin_dependency_calls="$(rg_count 'Depends\(get_admin_user\)' backend-hormonia/app)"
backend_session_alias_refs="$(rg_count 'alias="session_id"|Cookie\([^\n]*session_id|cookies\.get\("session_id"' backend-hormonia/app)"
backend_verify_firebase_token_refs="$(rg_count 'verify_firebase_token' backend-hormonia)"
backend_get_doctor_user_refs="$(rg_count 'get_doctor_user' backend-hormonia)"
backend_get_current_user_websocket_refs="$(rg_count 'get_current_user_websocket' backend-hormonia)"

frontend_facade_lines="$(line_count frontend-hormonia/src/lib/api-client.ts)"
frontend_index_lines="$(line_count frontend-hormonia/src/lib/api-client/index.ts)"
frontend_types_lines="$(line_count frontend-hormonia/src/lib/api-client/types.ts)"
frontend_types_api_lines="$(line_count frontend-hormonia/src/types/api.ts)"
frontend_legacy_types_lines="$(line_count frontend-hormonia/src/lib/types/api.ts)"
frontend_legacy_api_lines="$(line_count frontend-hormonia/src/lib/api.ts)"
frontend_quiz_session_lines="$(line_count frontend-hormonia/src/hooks/use-quiz-session.ts)"
frontend_facade_imports="$(rg_count "from ['\"]@/lib/api-client['\"]|from ['\"][^'\"]*/lib/api-client['\"]" frontend-hormonia/src)"
frontend_types_imports="$(rg_count "from ['\"]@/lib/api-client/types['\"]|from ['\"][^'\"]*/lib/api-client/types['\"]" frontend-hormonia/src)"
frontend_types_api_imports="$(rg_count "from ['\"]@/types/api['\"]|from ['\"][^'\"]*/types/api['\"]" frontend-hormonia/src)"
frontend_legacy_types_imports="$(rg_count "from ['\"]@/lib/types/api['\"]|from ['\"][^'\"]*/lib/types/api['\"]" frontend-hormonia/src)"
frontend_legacy_api_imports="$(rg_count "from ['\"]@/lib/api['\"]|from ['\"][^'\"]*/lib/api['\"]" frontend-hormonia/src)"
frontend_risk_assessment_request_declarations="$(rg_count 'export (interface|type) RiskAssessmentRequest\b' frontend-hormonia/src/lib/api-client/types.ts frontend-hormonia/src/types/api.ts)"

backend_commands=(
  "bash ${SELF_RELATIVE_PATH} --report backend"
  "bash ${SELF_RELATIVE_PATH} --check backend"
  'cd backend-hormonia && pytest tests/auth/test_session_validation.py tests/auth/test_user_conversion.py tests/api/v2/test_auth_session_priority.py'
  'cd backend-hormonia && pytest tests/auth/test_user_conversion.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py'
  'cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py'
  'cd backend-hormonia && pytest tests/api/v2/test_admin.py tests/api/v2/test_dashboard.py tests/api/test_admin_contracts.py'
  'cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py'
)

backend_proof_commands=(
  'rg -n "verify_firebase_token" backend-hormonia/app backend-hormonia/tests backend-hormonia/docs'
  'rg -n "get_doctor_user" backend-hormonia/app backend-hormonia/tests'
  'rg -n "get_current_user_websocket" backend-hormonia/app backend-hormonia/tests'
  'rg -n "firebase_uid|verify_token|get_cached_token|get_cached_user" backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/api/v2/routers/roles/dependencies.py backend-hormonia/app/routers/auth_session.py'
  'rg -n "validate_session|logout_session|firebase_uid|permissions" backend-hormonia/app/routers/auth_session.py backend-hormonia/app/api/v2/routers/auth.py'
  'cd backend-hormonia && pytest tests/auth/test_session_validation.py tests/auth/test_user_conversion.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py'
  'cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_session_priority.py'
  'cd frontend-hormonia && npm run test -- tests/integration/realtime/session-websocket-cutover.test.ts'
)

frontend_commands=(
  "bash ${SELF_RELATIVE_PATH} --report frontend"
  "bash ${SELF_RELATIVE_PATH} --check frontend"
  'cd frontend-hormonia && npm run typecheck && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts'
  'cd frontend-hormonia && npm run test -- tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx'
  'cd frontend-hormonia && npm run test -- tests/integration/admin-auth-flow.test.tsx tests/components/dashboard/QuickStats.test.tsx'
)

all_commands=(
  "bash ${SELF_RELATIVE_PATH} --report all"
  "bash ${SELF_RELATIVE_PATH} --check all"
  'cd frontend-hormonia && npx playwright test tests/e2e/auth/login.spec.ts tests/e2e/admin-dashboard-complete.spec.ts tests/e2e/websocket.spec.ts tests/e2e/test_whatsapp_integration_e2e.spec.ts'
)

check_research_common() {
  require_file "$RESEARCH_FILE"
  require_text "$RESEARCH_FILE" '## Ranked Hotspot Inventory' 'research section'
  require_text "$RESEARCH_FILE" '## Cleanup Guardrail Matrix' 'research section'
  require_text "$RESEARCH_FILE" '## Deletion Candidate Ledger' 'research section'
  require_text "$RESEARCH_FILE" '## Explicit Non-Candidates' 'research section'
  require_text "$RESEARCH_FILE" '## Downstream Verification Commands' 'research section'
}

check_backend_research() {
  check_research_common
  require_text "$RESEARCH_FILE" '### Backend verifier anchors' 'backend hotspot anchors heading'
  require_exact "$RESEARCH_FILE" 'backend hotspot anchor' '`backend-hormonia/app/dependencies/auth_dependencies.py` — `lines=%s`' "$backend_auth_lines"
  require_exact "$RESEARCH_FILE" 'backend hotspot anchor' '`backend-hormonia/app/api/v2/routers/auth.py` — `lines=%s`' "$backend_auth_router_lines"
  require_exact "$RESEARCH_FILE" 'backend hotspot anchor' '`backend-hormonia/app/routers/auth_session.py` — `lines=%s`' "$backend_auth_session_lines"
  require_exact "$RESEARCH_FILE" 'backend hotspot anchor' '`backend-hormonia/app/api/v2/routers/admin/dependencies.py` — `lines=%s`' "$backend_admin_dependencies_lines"
  require_exact "$RESEARCH_FILE" 'backend hotspot anchor' '`backend-hormonia/app/api/v2/routers/reports.py` — `lines=%s`' "$backend_reports_lines"
  require_exact "$RESEARCH_FILE" 'backend hotspot anchor' '`backend-hormonia/app/api/v2/routers/enhanced_reports.py` — `lines=%s`' "$backend_enhanced_reports_lines"
  require_exact "$RESEARCH_FILE" 'backend hotspot anchor' '`backend-hormonia/app/api/v2/routers/roles/dependencies.py` — `lines=%s`' "$backend_roles_dependencies_lines"
  require_exact "$RESEARCH_FILE" 'backend hotspot anchor' '`backend-hormonia/app/api/v2/routers/flows.py` — `lines=%s`' "$backend_flows_lines"
  require_exact "$RESEARCH_FILE" 'backend hotspot anchor' '`backend-hormonia/app/services/webhook/handlers/message_handler.py` — `lines=%s`' "$backend_message_handler_lines"
  require_exact "$RESEARCH_FILE" 'backend caller-count anchor' '`Depends(get_current_user_from_session)=%s`' "$backend_session_dependency_calls"
  require_exact "$RESEARCH_FILE" 'backend caller-count anchor' '`Depends(get_current_user_object_from_session)=%s`' "$backend_user_object_dependency_calls"
  require_exact "$RESEARCH_FILE" 'backend caller-count anchor' '`Depends(get_current_user)=%s`' "$backend_user_dependency_calls"
  require_exact "$RESEARCH_FILE" 'backend caller-count anchor' '`Depends(get_admin_user)=%s`' "$backend_admin_dependency_calls"
  require_exact "$RESEARCH_FILE" 'backend drift anchor' '`hardcoded_session_id_alias=%s`' "$backend_session_alias_refs"
  require_text "$RESEARCH_FILE" '### Backend S02 contract boundary' 'backend contract boundary heading'
  require_text "$RESEARCH_FILE" '`get_current_user_from_session()` returns **mapping-style session dicts**' 'backend dict contract note'
  require_text "$RESEARCH_FILE" '`get_current_user_object_from_session()` strips non-model keys like `permissions`' 'backend user contract note'
  require_text "$RESEARCH_FILE" '`request.state.session_id`, `request.state.user_id`, and `request.state.user_role`' 'backend request.state contract note'
  require_text "$RESEARCH_FILE" '### Backend wrapper drift constraints' 'backend wrapper drift heading'
  require_text "$RESEARCH_FILE" 'backend-hormonia/app/api/v2/routers/admin/dependencies.py' 'backend wrapper constraint'
  require_text "$RESEARCH_FILE" 'backend-hormonia/app/api/v2/routers/reports.py' 'backend wrapper constraint'
  require_text "$RESEARCH_FILE" 'backend-hormonia/app/api/v2/routers/enhanced_reports.py' 'backend wrapper constraint'
  require_text "$RESEARCH_FILE" 'backend-hormonia/app/api/v2/routers/roles/dependencies.py' 'backend wrapper constraint'
  require_text "$RESEARCH_FILE" '### Backend candidate verifier anchors' 'backend candidate anchors heading'
  require_exact "$RESEARCH_FILE" 'backend candidate anchor' '`verify_firebase_token` — `repo_refs=%s`' "$backend_verify_firebase_token_refs"
  require_exact "$RESEARCH_FILE" 'backend candidate anchor' '`get_doctor_user` — `repo_refs=%s`' "$backend_get_doctor_user_refs"
  require_exact "$RESEARCH_FILE" 'backend candidate anchor' '`get_current_user_websocket` — `repo_refs=%s`' "$backend_get_current_user_websocket_refs"
  require_text "$RESEARCH_FILE" '`backend_session_permissions_field` — `status=keep`' 'backend explicit non-candidate'
  require_text "$RESEARCH_FILE" '`backend_firebase_uid_compatibility` — `status=keep`' 'backend explicit non-candidate'

  local cmd
  for cmd in "${backend_commands[@]}"; do
    require_text "$RESEARCH_FILE" "$cmd" 'backend verification command'
  done

  for cmd in "${backend_proof_commands[@]}"; do
    require_text "$RESEARCH_FILE" "$cmd" 'backend proof-before-removal command'
  done
}

check_frontend_research() {
  check_research_common
  require_text "$RESEARCH_FILE" '### Frontend verifier anchors' 'frontend hotspot anchors heading'
  require_exact "$RESEARCH_FILE" 'frontend hotspot anchor' '`frontend-hormonia/src/lib/api-client.ts` — `lines=%s`, `imports=%s`' "$frontend_facade_lines" "$frontend_facade_imports"
  require_exact "$RESEARCH_FILE" 'frontend hotspot anchor' '`frontend-hormonia/src/lib/api-client/index.ts` — `lines=%s`' "$frontend_index_lines"
  require_exact "$RESEARCH_FILE" 'frontend hotspot anchor' '`frontend-hormonia/src/lib/api-client/types.ts` — `lines=%s`, `imports=%s`' "$frontend_types_lines" "$frontend_types_imports"
  require_exact "$RESEARCH_FILE" 'frontend hotspot anchor' '`frontend-hormonia/src/types/api.ts` — `lines=%s`, `imports=%s`' "$frontend_types_api_lines" "$frontend_types_api_imports"
  require_exact "$RESEARCH_FILE" 'frontend hotspot anchor' '`frontend-hormonia/src/lib/types/api.ts` — `lines=%s`, `imports=%s`' "$frontend_legacy_types_lines" "$frontend_legacy_types_imports"
  require_exact "$RESEARCH_FILE" 'frontend duplicate-export anchor' '`duplicate_exports` — `count=%s`, `names=%s`' "$frontend_duplicate_exports" "$frontend_duplicate_export_names"
  require_text "$RESEARCH_FILE" '### Frontend candidate verifier anchors' 'frontend candidate anchors heading'
  require_exact "$RESEARCH_FILE" 'frontend candidate anchor' '`frontend-hormonia/src/lib/api.ts` — `lines=%s`, `internal_imports=%s`' "$frontend_legacy_api_lines" "$frontend_legacy_api_imports"
  require_exact "$RESEARCH_FILE" 'frontend candidate anchor' '`frontend-hormonia/src/lib/types/api.ts` — `internal_imports=%s`' "$frontend_legacy_types_imports"
  require_exact "$RESEARCH_FILE" 'frontend candidate anchor' '`frontend-hormonia/src/hooks/use-quiz-session.ts` — `lines=%s`' "$frontend_quiz_session_lines"
  require_exact "$RESEARCH_FILE" 'frontend candidate anchor' '`RiskAssessmentRequest` — `direct_declarations=%s`' "$frontend_risk_assessment_request_declarations"
  require_exact "$RESEARCH_FILE" 'frontend explicit non-candidate' '`frontend_api_client_facade` — `status=keep`, `internal_imports=%s`' "$frontend_facade_imports"

  local cmd
  for cmd in "${frontend_commands[@]}"; do
    require_text "$RESEARCH_FILE" "$cmd" 'frontend verification command'
  done
}

check_handoff_artifacts() {
  require_file "$SUMMARY_FILE"
  require_file "$UAT_FILE"

  require_text "$SUMMARY_FILE" '# S01: Evidence Map And Cleanup Guardrails' 'summary heading'
  require_text "$SUMMARY_FILE" '## What Happened' 'summary section'
  require_text "$SUMMARY_FILE" '## Verification' 'summary section'
  require_text "$SUMMARY_FILE" '## Next Slice Execution Order' 'summary handoff section'
  require_text "$SUMMARY_FILE" '## Backend Handoff' 'summary handoff section'
  require_text "$SUMMARY_FILE" '## Frontend Handoff' 'summary handoff section'
  require_text "$SUMMARY_FILE" '## Deletion Proof Queue' 'summary handoff section'
  require_text "$SUMMARY_FILE" '## Exact Verification Commands' 'summary handoff section'
  require_text "$SUMMARY_FILE" '## Reviewer Focus' 'summary handoff section'
  require_text "$SUMMARY_FILE" '## Files Created/Modified' 'summary section'

  require_text "$UAT_FILE" '# S01: Evidence Map And Cleanup Guardrails — UAT' 'UAT heading'
  require_text "$UAT_FILE" '## UAT Type' 'UAT section'
  require_text "$UAT_FILE" '## Preconditions' 'UAT section'
  require_text "$UAT_FILE" '## Smoke Test' 'UAT section'
  require_text "$UAT_FILE" '## Test Cases' 'UAT section'
  require_text "$UAT_FILE" '## Edge Cases' 'UAT section'
  require_text "$UAT_FILE" '## Failure Signals' 'UAT section'
  require_text "$UAT_FILE" '## Requirements Proved By This UAT' 'UAT section'
  require_text "$UAT_FILE" '## Not Proven By This UAT' 'UAT section'
  require_text "$UAT_FILE" '## Notes for Tester' 'UAT section'
  require_text "$UAT_FILE" '## Reviewer Checklist' 'UAT reviewer section'

  local cmd
  for cmd in "${backend_commands[@]}" "${frontend_commands[@]}" "${all_commands[@]}"; do
    require_text "$SUMMARY_FILE" "$cmd" 'summary verification command'
    require_text "$UAT_FILE" "$cmd" 'UAT verification command'
  done

  report_open_scaffolds "$SUMMARY_FILE"
  report_open_scaffolds "$UAT_FILE"
}

emit_backend_report() {
  emit_heading 'backend'
  emit_metric 'backend.auth_dependencies.lines' "$backend_auth_lines"
  emit_metric 'backend.auth_router.lines' "$backend_auth_router_lines"
  emit_metric 'backend.auth_session.lines' "$backend_auth_session_lines"
  emit_metric 'backend.admin_dependencies.lines' "$backend_admin_dependencies_lines"
  emit_metric 'backend.reports.lines' "$backend_reports_lines"
  emit_metric 'backend.enhanced_reports.lines' "$backend_enhanced_reports_lines"
  emit_metric 'backend.roles_dependencies.lines' "$backend_roles_dependencies_lines"
  emit_metric 'backend.flows.lines' "$backend_flows_lines"
  emit_metric 'backend.message_handler.lines' "$backend_message_handler_lines"
  emit_metric 'backend.depends.get_current_user_from_session' "$backend_session_dependency_calls"
  emit_metric 'backend.depends.get_current_user_object_from_session' "$backend_user_object_dependency_calls"
  emit_metric 'backend.depends.get_current_user' "$backend_user_dependency_calls"
  emit_metric 'backend.depends.get_admin_user' "$backend_admin_dependency_calls"
  emit_metric 'backend.hardcoded_session_id_alias' "$backend_session_alias_refs"
  emit_metric 'backend.candidate.verify_firebase_token.repo_refs' "$backend_verify_firebase_token_refs"
  emit_metric 'backend.candidate.get_doctor_user.repo_refs' "$backend_get_doctor_user_refs"
  emit_metric 'backend.candidate.get_current_user_websocket.repo_refs' "$backend_get_current_user_websocket_refs"
}

emit_frontend_report() {
  emit_heading 'frontend'
  emit_metric 'frontend.api_client_facade.lines' "$frontend_facade_lines"
  emit_metric 'frontend.api_client_facade.imports' "$frontend_facade_imports"
  emit_metric 'frontend.api_client_index.lines' "$frontend_index_lines"
  emit_metric 'frontend.api_client_types.lines' "$frontend_types_lines"
  emit_metric 'frontend.api_client_types.imports' "$frontend_types_imports"
  emit_metric 'frontend.types_api.lines' "$frontend_types_api_lines"
  emit_metric 'frontend.types_api.imports' "$frontend_types_api_imports"
  emit_metric 'frontend.legacy_types.lines' "$frontend_legacy_types_lines"
  emit_metric 'frontend.legacy_types.imports' "$frontend_legacy_types_imports"
  emit_metric 'frontend.legacy_api.lines' "$frontend_legacy_api_lines"
  emit_metric 'frontend.legacy_api.imports' "$frontend_legacy_api_imports"
  emit_metric 'frontend.use_quiz_session.lines' "$frontend_quiz_session_lines"
  emit_metric 'frontend.duplicate_exports.count' "$frontend_duplicate_exports"
  emit_metric 'frontend.risk_assessment_request.direct_declarations' "$frontend_risk_assessment_request_declarations"
  emit_note "frontend.duplicate_exports.names=${frontend_duplicate_export_names}"
}

emit_handoff_report() {
  emit_heading 'handoff'
  if [[ -f "$SUMMARY_FILE" ]]; then
    emit_metric 'handoff.summary.open_scaffold_items' "$(open_scaffold_count "$SUMMARY_FILE")"
  else
    emit_note "missing file: $(relative_path "$SUMMARY_FILE")"
  fi

  if [[ -f "$UAT_FILE" ]]; then
    emit_metric 'handoff.uat.open_scaffold_items' "$(open_scaffold_count "$UAT_FILE")"
  else
    emit_note "missing file: $(relative_path "$UAT_FILE")"
  fi
}

check_selected_scope() {
  case "$SCOPE" in
    backend)
      check_backend_research
      ;;
    frontend)
      check_frontend_research
      ;;
    all)
      check_backend_research
      check_frontend_research
      check_handoff_artifacts
      ;;
  esac
}

emit_selected_report() {
  case "$SCOPE" in
    backend)
      emit_backend_report
      ;;
    frontend)
      emit_frontend_report
      ;;
    all)
      emit_backend_report
      emit_frontend_report
      emit_handoff_report
      ;;
  esac
}

check_selected_scope
emit_selected_report

if ((${#failures[@]} == 0)); then
  printf '\nRESULT: %s %s OK\n' "$MODE" "$SCOPE"
  exit 0
fi

if [[ "$MODE" == '--report' ]]; then
  emit_heading 'drift-notes'
  for failure in "${failures[@]}"; do
    emit_note "$failure"
  done
  printf '\nRESULT: --report %s completed with %d drift note(s)\n' "$SCOPE" "${#failures[@]}"
  exit 0
fi

emit_heading 'failures'
for failure in "${failures[@]}"; do
  emit_note "$failure"
done
printf '\nRESULT: --check %s FAILED with %d issue(s)\n' "$SCOPE" "${#failures[@]}"
exit 1
