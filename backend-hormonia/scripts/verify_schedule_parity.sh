#!/usr/bin/env bash
# =============================================================================
# verify_schedule_parity.sh — Schedule parity check: Celery beat_schedule ↔ Taskiq
#
# Proves 1:1 mapping between all beat_schedule entries in celery_app.py and
# schedule labels on @broker.task() decorators in *_taskiq.py modules.
#
# Exit 0 = all matched, Exit 1 = gaps found
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CELERY_APP="${BASE_DIR}/app/celery_app.py"
TASKIQ_DIR="${BASE_DIR}/app/tasks"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo " Schedule Parity Verification"
echo " Celery beat_schedule ↔ Taskiq schedule labels"
echo "=============================================="
echo ""

# ---------------------------------------------------------------------------
# 1. Extract Celery beat_schedule task names
# ---------------------------------------------------------------------------
echo "--- Celery beat_schedule entries ---"

CELERY_TASKS=$(python3 -c "
import re, sys

with open('${CELERY_APP}') as f:
    content = f.read()

tasks = re.findall(r'\"task\":\s*\"([^\"]+)\"', content)
for t in sorted(tasks):
    print(t)
")

CELERY_COUNT=$(echo "$CELERY_TASKS" | wc -l | tr -d ' ')
echo "Found ${CELERY_COUNT} beat_schedule entries"
echo ""

# ---------------------------------------------------------------------------
# 2. Extract Taskiq scheduled function names
# ---------------------------------------------------------------------------
echo "--- Taskiq scheduled functions ---"

TASKIQ_TASKS=$(python3 -c "
import re, glob, sys

files = sorted(glob.glob('${TASKIQ_DIR}/*_taskiq.py'))
results = []
for f in files:
    with open(f) as fh:
        lines = fh.readlines()
    for i, line in enumerate(lines):
        if 'schedule=[' in line:
            for j in range(i+1, min(i+10, len(lines))):
                match = re.match(r'\s*async def (\w+)\(', lines[j])
                if match:
                    results.append(match.group(1))
                    break
for r in sorted(results):
    print(r)
")

TASKIQ_COUNT=$(echo "$TASKIQ_TASKS" | wc -l | tr -d ' ')
echo "Found ${TASKIQ_COUNT} Taskiq scheduled functions"
echo ""

# ---------------------------------------------------------------------------
# 3. Build mapping and compare
#
# Celery uses dotted paths like app.tasks.messaging.process_scheduled_messages
# Taskiq uses bare function names like process_scheduled_messages
# The last segment of the Celery path should match the Taskiq function name,
# with known renamings handled explicitly.
# ---------------------------------------------------------------------------
echo "--- Matching ---"

# Known renamings: Celery task name suffix → Taskiq function name
# These are cases where the Celery task name's last segment differs from
# the Taskiq function name.
declare -A RENAMINGS=(
    # audit.refresh_performance_metrics → refresh_ai_performance_metrics
    ["refresh_performance_metrics"]="refresh_ai_performance_metrics"
    # quiz_flow.cleanup_tasks.cleanup_expired_quiz_sessions_task → cleanup_expired_quiz_sessions
    ["cleanup_expired_quiz_sessions_task"]="cleanup_expired_quiz_sessions"
    # lgpd.cleanup_expired_audit_logs → cleanup_expired_lgpd_audit_logs
    ["cleanup_expired_audit_logs"]="cleanup_expired_lgpd_audit_logs"
    # flow_automation.check_and_start_pending_flows → check_and_start_pending_flows (same)
    # quiz_link_tasks.check_expired_links → check_expired_links (same)
)

MATCHED=0
MISSING=0
MISSING_LIST=""

while IFS= read -r celery_task; do
    # Extract the last segment of the dotted path
    suffix="${celery_task##*.}"

    # Apply known renamings
    if [[ -n "${RENAMINGS[$suffix]+x}" ]]; then
        lookup="${RENAMINGS[$suffix]}"
    else
        lookup="$suffix"
    fi

    # Check if this function name exists in Taskiq scheduled functions
    if echo "$TASKIQ_TASKS" | grep -qx "$lookup"; then
        MATCHED=$((MATCHED + 1))
        echo -e "  ${GREEN}✓${NC} ${celery_task} → ${lookup}"
    else
        MISSING=$((MISSING + 1))
        MISSING_LIST="${MISSING_LIST}\n  ✗ ${celery_task} → ${lookup} (NOT FOUND)"
        echo -e "  ${RED}✗${NC} ${celery_task} → ${lookup} (NOT FOUND)"
    fi
done <<< "$CELERY_TASKS"

echo ""

# ---------------------------------------------------------------------------
# 4. Check for extra Taskiq schedules not in Celery
# ---------------------------------------------------------------------------
echo "--- Extra Taskiq schedules (not in Celery) ---"
EXTRA=0
while IFS= read -r taskiq_fn; do
    # Check if any Celery task maps to this function
    found=false
    while IFS= read -r celery_task; do
        suffix="${celery_task##*.}"
        if [[ -n "${RENAMINGS[$suffix]+x}" ]]; then
            lookup="${RENAMINGS[$suffix]}"
        else
            lookup="$suffix"
        fi
        if [[ "$lookup" == "$taskiq_fn" ]]; then
            found=true
            break
        fi
    done <<< "$CELERY_TASKS"

    if ! $found; then
        EXTRA=$((EXTRA + 1))
        echo -e "  ${YELLOW}?${NC} ${taskiq_fn} (no Celery equivalent)"
    fi
done <<< "$TASKIQ_TASKS"

if [[ $EXTRA -eq 0 ]]; then
    echo "  (none)"
fi
echo ""

# ---------------------------------------------------------------------------
# 5. Summary
# ---------------------------------------------------------------------------
echo "=============================================="
echo " RESULTS"
echo "=============================================="
echo -e "  Celery beat_schedule entries: ${CELERY_COUNT}"
echo -e "  Taskiq scheduled functions:   ${TASKIQ_COUNT}"
echo -e "  Matched:  ${GREEN}${MATCHED}${NC} / ${CELERY_COUNT}"
echo -e "  Missing:  ${RED}${MISSING}${NC}"
echo -e "  Extra:    ${YELLOW}${EXTRA}${NC}"
echo ""

if [[ $MISSING -eq 0 ]]; then
    echo -e "${GREEN}✓ PASS: All ${CELERY_COUNT} beat_schedule entries have matching Taskiq schedule labels${NC}"
    exit 0
else
    echo -e "${RED}✗ FAIL: ${MISSING} beat_schedule entries missing Taskiq equivalents${NC}"
    echo -e "$MISSING_LIST"
    exit 1
fi
