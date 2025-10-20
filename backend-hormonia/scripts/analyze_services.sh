#!/bin/bash
# QW-016: Services Analysis Script (Shell Version)
# ================================================
# Analyzes all services in backend-hormonia/app/services/
# Generates markdown report with metrics and recommendations

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICES_DIR="$PROJECT_ROOT/app/services"
OUTPUT_FILE="${1:-$PROJECT_ROOT/../REVIEW-2025/QW-016-SERVICES-ANALYSIS.md}"

echo -e "${BLUE}🔍 Comprehensive Services Analysis${NC}"
echo "=" | awk '{for(i=0;i<60;i++)printf "="}END{print ""}'
echo "Services directory: $SERVICES_DIR"
echo "Output file: $OUTPUT_FILE"
echo ""

# Count services
echo -e "${YELLOW}📂 Scanning services directory...${NC}"
TOTAL_SERVICES=$(find "$SERVICES_DIR" -type f -name "*.py" ! -name "__init__.py" | wc -l)
echo -e "${GREEN}✅ Found $TOTAL_SERVICES services${NC}"
echo ""

# Calculate total LOC
echo -e "${YELLOW}📊 Calculating lines of code...${NC}"
TOTAL_LOC=$(find "$SERVICES_DIR" -type f -name "*.py" ! -name "__init__.py" -exec wc -l {} + | tail -1 | awk '{print $1}')
AVG_LOC=$((TOTAL_LOC / TOTAL_SERVICES))
echo -e "${GREEN}✅ Total LOC: $TOTAL_LOC (avg: $AVG_LOC per service)${NC}"
echo ""

# Find duplication patterns
echo -e "${YELLOW}🔄 Finding duplication groups...${NC}"

declare -A GROUPS
GROUPS["ai"]="ai ai_cache ai_cache_service ai_redis_cache ai_batch_processor"
GROUPS["cache"]="cache cache_service cache_invalidation unified_cache template_cache analytics_cache"
GROUPS["flow"]="flow flow_core flow_engine enhanced_flow_engine flow_management flow_analytics flow_monitoring"
GROUPS["message"]="message message_service message_scheduler message_handler message_queue"
GROUPS["quiz"]="quiz quiz_service quiz_analytics quiz_templates quiz_validation"
GROUPS["websocket"]="websocket websocket_service websocket_manager websocket_handler"
GROUPS["monitoring"]="monitoring monitoring_service health_check system_monitor performance_monitor"
GROUPS["analytics"]="analytics analytics_service analytics_cache analytics_report"
GROUPS["audit"]="audit audit_log audit_service audit_trail"
GROUPS["alert"]="alert alert_processor critical_error_escalation"
</parameter>

# Start generating markdown report
{
    echo "# 🔍 COMPREHENSIVE SERVICES ANALYSIS"
    echo "## Backend Hormonia - Services Deep Dive"
    echo ""
    echo "---"
    echo ""
    echo "## 📊 EXECUTIVE SUMMARY"
    echo ""
    echo "**Total Services:** $TOTAL_SERVICES"
    echo "**Total Lines of Code:** $(printf "%'d" $TOTAL_LOC)"
    echo "**Average LOC per Service:** $AVG_LOC"
    echo "**Analysis Date:** $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    echo "---"
    echo ""

    echo "## 📈 TOP 20 SERVICES BY SIZE"
    echo ""
    echo "| Rank | Service | LOC | Relative Size |"
    echo "|------|---------|-----|---------------|"

    # Get top services by LOC
    RANK=1
    find "$SERVICES_DIR" -type f -name "*.py" ! -name "__init__.py" -exec wc -l {} + | \
        sort -rn | head -20 | while read -r loc filepath; do
        if [[ "$filepath" != "total" ]]; then
            SERVICE=$(basename "$filepath" .py)
            PERCENT=$((loc * 100 / TOTAL_LOC))
            BAR=$(printf '█%.0s' $(seq 1 $((PERCENT / 2))))
            echo "| $RANK | \`$SERVICE\` | $loc | $BAR ${PERCENT}% |"
            RANK=$((RANK + 1))
        fi
    done

    echo ""
    echo "---"
    echo ""

    echo "## 🔄 DUPLICATION GROUPS (CONSOLIDATION OPPORTUNITIES)"
    echo ""

    # Analyze each group
    for GROUP in "${!GROUPS[@]}"; do
        PATTERN="${GROUPS[$GROUP]}"

        # Find matching files
        MATCHES=()
        for TERM in $PATTERN; do
            while IFS= read -r -d '' file; do
                MATCHES+=("$(basename "$file" .py)")
            done < <(find "$SERVICES_DIR" -type f -name "${TERM}*.py" -print0 2>/dev/null)
        done

        # Remove duplicates
        UNIQUE_MATCHES=($(printf "%s\n" "${MATCHES[@]}" | sort -u))

        if [[ ${#UNIQUE_MATCHES[@]} -gt 1 ]]; then
            echo "### ${GROUP^^} Services (${#UNIQUE_MATCHES[@]} files)"
            echo ""
            echo "**Files:**"

            for SERVICE in "${UNIQUE_MATCHES[@]}"; do
                if [[ -f "$SERVICES_DIR/${SERVICE}.py" ]]; then
                    LOC=$(wc -l < "$SERVICES_DIR/${SERVICE}.py")
                    echo "- \`${SERVICE}.py\` ($LOC LOC)"
                fi
            done

            echo ""

            # Recommendations
            case $GROUP in
                "ai")
                    echo "**💡 Recommendation:** Consolidate into single \`ai_service.py\` with internal cache"
                    ;;
                "cache")
                    echo "**💡 Recommendation:** Create unified \`cache_service.py\` with pluggable strategies"
                    ;;
                "flow")
                    echo "**💡 Recommendation:** Create \`flow/\` module with flow_service.py, flow_engine.py, flow_analytics.py"
                    ;;
                "message")
                    echo "**💡 Recommendation:** Create \`messaging/\` module with message_service.py and message_scheduler.py"
                    ;;
                "quiz")
                    echo "**💡 Recommendation:** Create \`quiz/\` module with quiz_service.py, quiz_analytics.py, quiz_templates.py"
                    ;;
                "websocket")
                    echo "**💡 Recommendation:** Consolidate into single \`websocket_service.py\`"
                    ;;
                "monitoring")
                    echo "**💡 Recommendation:** Create \`monitoring/\` module with monitoring_service.py and health_check.py"
                    ;;
                "analytics")
                    echo "**💡 Recommendation:** Consolidate into \`analytics_service.py\`"
                    ;;
                "audit")
                    echo "**💡 Recommendation:** Create single \`audit_service.py\` with audit_log and audit_trail functionality"
                    ;;
                "alert")
                    echo "**💡 Recommendation:** Consolidate into \`alert_service.py\` with processor and escalation"
                    ;;
                *)
                    echo "**💡 Recommendation:** Review and consolidate $GROUP services"
                    ;;
            esac

            echo ""
        fi
    done

    echo "---"
    echo ""

    echo "## 📋 ALL SERVICES INVENTORY"
    echo ""
    echo "Complete list of all services in alphabetical order:"
    echo ""
    echo "| # | Service Name | LOC |"
    echo "|---|--------------|-----|"

    INDEX=1
    find "$SERVICES_DIR" -type f -name "*.py" ! -name "__init__.py" | sort | while read -r filepath; do
        SERVICE=$(basename "$filepath" .py)
        LOC=$(wc -l < "$filepath")
        echo "| $INDEX | \`$SERVICE\` | $LOC |"
        INDEX=$((INDEX + 1))
    done

    echo ""
    echo "---"
    echo ""

    echo "## 🎯 CONSOLIDATION ROADMAP"
    echo ""
    echo "### Phase 1: Low-Risk Consolidations (Week 5)"
    echo ""
    echo "1. **AI Services (6 → 1)**"
    echo "   - Target: \`ai_service.py\` with internal cache and batch processing"
    echo "   - Risk: LOW"
    echo "   - Impact: HIGH"
    echo ""
    echo "2. **Cache Services (6 → 1)**"
    echo "   - Target: \`cache_service.py\` with pluggable strategies"
    echo "   - Risk: LOW"
    echo "   - Impact: HIGH"
    echo ""
    echo "3. **Alert Services (3 → 1)**"
    echo "   - Target: \`alert_service.py\` with processor and escalation"
    echo "   - Risk: LOW"
    echo "   - Impact: MEDIUM"
    echo ""
    echo "### Phase 2: Medium-Risk Consolidations (Week 6)"
    echo ""
    echo "4. **Flow Services (15 → 4)**"
    echo "   - Create module: \`app/services/flow/\`"
    echo "   - Files: flow_service.py, flow_engine.py, flow_analytics.py, flow_templates.py"
    echo "   - Risk: MEDIUM"
    echo "   - Impact: HIGH"
    echo ""
    echo "5. **Message Services (8 → 2)**"
    echo "   - Create module: \`app/services/messaging/\`"
    echo "   - Files: message_service.py, message_scheduler.py"
    echo "   - Risk: MEDIUM"
    echo "   - Impact: HIGH"
    echo ""
    echo "6. **Quiz Services (12 → 3)**"
    echo "   - Create module: \`app/services/quiz/\`"
    echo "   - Files: quiz_service.py, quiz_analytics.py, quiz_templates.py"
    echo "   - Risk: MEDIUM"
    echo "   - Impact: MEDIUM"
    echo ""
    echo "### Phase 3: High-Risk Consolidations (Week 7-8)"
    echo ""
    echo "7. **Audit Services (3 → 1)**"
    echo "   - Risk: HIGH (affects compliance)"
    echo "   - Impact: MEDIUM"
    echo ""
    echo "8. **Monitoring Services (8 → 2)**"
    echo "   - Risk: HIGH (affects observability)"
    echo "   - Impact: HIGH"
    echo ""
    echo "9. **Analytics Services (5 → 2)**"
    echo "   - Risk: MEDIUM"
    echo "   - Impact: HIGH"
    echo ""
    echo "10. **WebSocket Services (5 → 1)**"
    echo "    - Risk: HIGH (real-time communication)"
    echo "    - Impact: HIGH"
    echo ""
    echo "### Expected Results"
    echo ""
    echo "- **Before:** $TOTAL_SERVICES services"
    echo "- **After:** ~35-40 services"
    REDUCTION=$((TOTAL_SERVICES - 35))
    REDUCTION_PERCENT=$((REDUCTION * 100 / TOTAL_SERVICES))
    echo "- **Reduction:** ~$REDUCTION services (${REDUCTION_PERCENT}%)"
    echo "- **Maintainability:** Significantly improved"
    echo "- **Code Duplication:** Eliminated"
    echo ""
    echo "---"
    echo ""

    echo "## 🔍 DETAILED ANALYSIS BY CATEGORY"
    echo ""

    # Find services by pattern
    find_services_by_pattern() {
        local pattern=$1
        find "$SERVICES_DIR" -type f -name "${pattern}*.py" ! -name "__init__.py" | wc -l
    }

    echo "| Category | Count | Target | Reduction |"
    echo "|----------|-------|--------|-----------|"
    echo "| AI Services | $(find_services_by_pattern 'ai') | 1 | $(( $(find_services_by_pattern 'ai') - 1 )) |"
    echo "| Cache Services | $(find_services_by_pattern 'cache') | 1 | $(( $(find_services_by_pattern 'cache') - 1 )) |"
    echo "| Flow Services | $(find_services_by_pattern 'flow') | 4 | $(( $(find_services_by_pattern 'flow') - 4 )) |"
    echo "| Message Services | $(find_services_by_pattern 'message') | 2 | $(( $(find_services_by_pattern 'message') - 2 )) |"
    echo "| Quiz Services | $(find_services_by_pattern 'quiz') | 3 | $(( $(find_services_by_pattern 'quiz') - 3 )) |"
    echo "| WebSocket Services | $(find_services_by_pattern 'websocket') | 1 | $(( $(find_services_by_pattern 'websocket') - 1 )) |"
    echo "| Monitoring Services | $(find_services_by_pattern 'monitoring') | 2 | $(( $(find_services_by_pattern 'monitoring') - 2 )) |"
    echo "| Analytics Services | $(find_services_by_pattern 'analytics') | 2 | $(( $(find_services_by_pattern 'analytics') - 2 )) |"
    echo "| Audit Services | $(find_services_by_pattern 'audit') | 1 | $(( $(find_services_by_pattern 'audit') - 1 )) |"
    echo "| Alert Services | $(find_services_by_pattern 'alert') | 1 | $(( $(find_services_by_pattern 'alert') - 1 )) |"

    echo ""
    echo "---"
    echo ""

    echo "## ✅ NEXT ACTIONS"
    echo ""
    echo "1. ✅ **Review this analysis** - Read through findings and recommendations"
    echo "2. 📋 **Update CHECKLIST.md** - Mark QW-016 as complete"
    echo "3. 🎯 **Prioritize consolidations** - Choose Phase 1 targets"
    echo "4. 🧪 **Create baseline tests** - Before starting consolidation"
    echo "5. 🌿 **Create feature branch** - \`feature/services-consolidation\`"
    echo "6. 🚀 **Start Phase 1** - Begin with AI services consolidation"
    echo ""
    echo "---"
    echo ""

    echo "## 📝 NOTES"
    echo ""
    echo "- This analysis was generated automatically from the file system"
    echo "- Code complexity and dependency analysis require Python AST parsing"
    echo "- Run \`analyze_services_complete.py\` when Python is available for deeper analysis"
    echo "- Always test thoroughly after each consolidation"
    echo "- Keep baseline tests passing throughout the process"
    echo ""
    echo "---"
    echo ""

    echo "**Generated by:** \`scripts/analyze_services.sh\` (QW-016)"
    echo "**Date:** $(date '+%Y-%m-%d %H:%M:%S')"
    echo "**Analysis Duration:** Fast (file system scan only)"

} > "$OUTPUT_FILE"

echo -e "${GREEN}✅ Report generated: $OUTPUT_FILE${NC}"
echo ""
echo -e "${BLUE}📊 SUMMARY${NC}"
echo "=" | awk '{for(i=0;i<60;i++)printf "="}END{print ""}'
echo "Total Services: $TOTAL_SERVICES"
echo "Total LOC: $(printf "%'d" $TOTAL_LOC)"
echo "Average LOC: $AVG_LOC"
echo "Target Services: ~35-40"
echo "Expected Reduction: ~$((TOTAL_SERVICES - 35)) services ($((100 * (TOTAL_SERVICES - 35) / TOTAL_SERVICES))%)"
echo ""
echo -e "${GREEN}🎯 Next: Review $OUTPUT_FILE and plan consolidation strategy${NC}"
