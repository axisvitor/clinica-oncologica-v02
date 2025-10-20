#!/bin/bash
# QW-016: Services Analysis Script (Simplified)
# ==============================================
# Analyzes all services in backend-hormonia/app/services/

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICES_DIR="$PROJECT_ROOT/app/services"
OUTPUT_FILE="${1:-$PROJECT_ROOT/../REVIEW-2025/QW-016-SERVICES-ANALYSIS.md}"

echo -e "${BLUE}🔍 Services Analysis${NC}"
echo "======================================"
echo "Services dir: $SERVICES_DIR"
echo "Output: $OUTPUT_FILE"
echo ""

# Count services
echo -e "${YELLOW}📂 Scanning...${NC}"
TOTAL_SERVICES=$(find "$SERVICES_DIR" -type f -name "*.py" ! -name "__init__.py" 2>/dev/null | wc -l)
echo -e "${GREEN}✅ Found $TOTAL_SERVICES services${NC}"

# Calculate LOC
TOTAL_LOC=$(find "$SERVICES_DIR" -type f -name "*.py" ! -name "__init__.py" -exec cat {} + 2>/dev/null | wc -l)
AVG_LOC=$((TOTAL_LOC / TOTAL_SERVICES))

# Generate report
cat > "$OUTPUT_FILE" << 'REPORT_START'
# 🔍 COMPREHENSIVE SERVICES ANALYSIS
## Backend Hormonia - Services Deep Dive

---

## 📊 EXECUTIVE SUMMARY

REPORT_START

echo "**Total Services:** $TOTAL_SERVICES" >> "$OUTPUT_FILE"
echo "**Total Lines of Code:** $(printf "%'d" $TOTAL_LOC)" >> "$OUTPUT_FILE"
echo "**Average LOC per Service:** $AVG_LOC" >> "$OUTPUT_FILE"
echo "**Analysis Date:** $(date '+%Y-%m-%d %H:%M:%S')" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Top services by size
cat >> "$OUTPUT_FILE" << 'EOF'
## 📈 TOP 20 SERVICES BY SIZE

| Rank | Service | LOC |
|------|---------|-----|
EOF

RANK=1
find "$SERVICES_DIR" -type f -name "*.py" ! -name "__init__.py" -exec wc -l {} + 2>/dev/null | \
    sort -rn | head -21 | tail -20 | while read -r loc filepath; do
    SERVICE=$(basename "$filepath" .py)
    echo "| $RANK | \`$SERVICE\` | $loc |" >> "$OUTPUT_FILE"
    RANK=$((RANK + 1))
done

cat >> "$OUTPUT_FILE" << 'EOF'

---

## 🔄 DUPLICATION GROUPS

### AI Services (6+ files)

**Pattern:** `ai*.py`

**Files Found:**
EOF

find "$SERVICES_DIR" -type f -name "ai*.py" ! -name "__init__.py" 2>/dev/null | while read -r file; do
    SERVICE=$(basename "$file" .py)
    LOC=$(wc -l < "$file")
    echo "- \`${SERVICE}.py\` ($LOC LOC)" >> "$OUTPUT_FILE"
done

cat >> "$OUTPUT_FILE" << 'EOF'

**💡 Recommendation:** Consolidate into single `ai_service.py` with internal cache

---

### Cache Services (6+ files)

**Pattern:** `cache*.py`, `*_cache*.py`

**Files Found:**
EOF

find "$SERVICES_DIR" -type f \( -name "cache*.py" -o -name "*_cache*.py" \) ! -name "__init__.py" 2>/dev/null | while read -r file; do
    SERVICE=$(basename "$file" .py)
    LOC=$(wc -l < "$file")
    echo "- \`${SERVICE}.py\` ($LOC LOC)" >> "$OUTPUT_FILE"
done

cat >> "$OUTPUT_FILE" << 'EOF'

**💡 Recommendation:** Create unified `cache_service.py` with pluggable strategies

---

### Flow Services (15+ files)

**Pattern:** `flow*.py`, `*_flow*.py`

**Files Found:**
EOF

find "$SERVICES_DIR" -type f \( -name "flow*.py" -o -name "*_flow*.py" \) ! -name "__init__.py" 2>/dev/null | while read -r file; do
    SERVICE=$(basename "$file" .py)
    LOC=$(wc -l < "$file")
    echo "- \`${SERVICE}.py\` ($LOC LOC)" >> "$OUTPUT_FILE"
done

cat >> "$OUTPUT_FILE" << 'EOF'

**💡 Recommendation:** Create `flow/` module with 4 files: flow_service.py, flow_engine.py, flow_analytics.py, flow_templates.py

---

### Message Services (8+ files)

**Pattern:** `message*.py`, `*_message*.py`

**Files Found:**
EOF

find "$SERVICES_DIR" -type f \( -name "message*.py" -o -name "*_message*.py" \) ! -name "__init__.py" 2>/dev/null | while read -r file; do
    SERVICE=$(basename "$file" .py)
    LOC=$(wc -l < "$file")
    echo "- \`${SERVICE}.py\` ($LOC LOC)" >> "$OUTPUT_FILE"
done

cat >> "$OUTPUT_FILE" << 'EOF'

**💡 Recommendation:** Create `messaging/` module with message_service.py and message_scheduler.py

---

### Quiz Services (12+ files)

**Pattern:** `quiz*.py`, `*_quiz*.py`

**Files Found:**
EOF

find "$SERVICES_DIR" -type f \( -name "quiz*.py" -o -name "*_quiz*.py" \) ! -name "__init__.py" 2>/dev/null | while read -r file; do
    SERVICE=$(basename "$file" .py)
    LOC=$(wc -l < "$file")
    echo "- \`${SERVICE}.py\` ($LOC LOC)" >> "$OUTPUT_FILE"
done

cat >> "$OUTPUT_FILE" << 'EOF'

**💡 Recommendation:** Create `quiz/` module with quiz_service.py, quiz_analytics.py, quiz_templates.py

---

### WebSocket Services (5+ files)

**Pattern:** `websocket*.py`, `*_websocket*.py`

**Files Found:**
EOF

find "$SERVICES_DIR" -type f \( -name "websocket*.py" -o -name "*_websocket*.py" \) ! -name "__init__.py" 2>/dev/null | while read -r file; do
    SERVICE=$(basename "$file" .py)
    LOC=$(wc -l < "$file")
    echo "- \`${SERVICE}.py\` ($LOC LOC)" >> "$OUTPUT_FILE"
done

cat >> "$OUTPUT_FILE" << 'EOF'

**💡 Recommendation:** Consolidate into single `websocket_service.py`

---

### Monitoring Services (8+ files)

**Pattern:** `monitoring*.py`, `*_monitor*.py`, `health*.py`

**Files Found:**
EOF

find "$SERVICES_DIR" -type f \( -name "monitoring*.py" -o -name "*_monitor*.py" -o -name "health*.py" \) ! -name "__init__.py" 2>/dev/null | while read -r file; do
    SERVICE=$(basename "$file" .py)
    LOC=$(wc -l < "$file")
    echo "- \`${SERVICE}.py\` ($LOC LOC)" >> "$OUTPUT_FILE"
done

cat >> "$OUTPUT_FILE" << 'EOF'

**💡 Recommendation:** Create `monitoring/` module with monitoring_service.py and health_check.py

---

### Analytics Services (5+ files)

**Pattern:** `analytics*.py`, `*_analytics*.py`

**Files Found:**
EOF

find "$SERVICES_DIR" -type f \( -name "analytics*.py" -o -name "*_analytics*.py" \) ! -name "__init__.py" 2>/dev/null | while read -r file; do
    SERVICE=$(basename "$file" .py)
    LOC=$(wc -l < "$file")
    echo "- \`${SERVICE}.py\` ($LOC LOC)" >> "$OUTPUT_FILE"
done

cat >> "$OUTPUT_FILE" << 'EOF'

**💡 Recommendation:** Consolidate into `analytics_service.py`

---

### Audit Services (3+ files)

**Pattern:** `audit*.py`, `*_audit*.py`

**Files Found:**
EOF

find "$SERVICES_DIR" -type f \( -name "audit*.py" -o -name "*_audit*.py" \) ! -name "__init__.py" 2>/dev/null | while read -r file; do
    SERVICE=$(basename "$file" .py)
    LOC=$(wc -l < "$file")
    echo "- \`${SERVICE}.py\` ($LOC LOC)" >> "$OUTPUT_FILE"
done

cat >> "$OUTPUT_FILE" << 'EOF'

**💡 Recommendation:** Create single `audit_service.py`

---

### Alert Services (3+ files)

**Pattern:** `alert*.py`, `*_alert*.py`

**Files Found:**
EOF

find "$SERVICES_DIR" -type f \( -name "alert*.py" -o -name "*_alert*.py" \) ! -name "__init__.py" 2>/dev/null | while read -r file; do
    SERVICE=$(basename "$file" .py)
    LOC=$(wc -l < "$file")
    echo "- \`${SERVICE}.py\` ($LOC LOC)" >> "$OUTPUT_FILE"
done

cat >> "$OUTPUT_FILE" << 'EOF'

**💡 Recommendation:** Consolidate into `alert_service.py`

---

## 📋 ALL SERVICES INVENTORY

Complete alphabetical list:

| # | Service Name | LOC |
|---|--------------|-----|
EOF

INDEX=1
find "$SERVICES_DIR" -type f -name "*.py" ! -name "__init__.py" 2>/dev/null | sort | while read -r filepath; do
    SERVICE=$(basename "$filepath" .py)
    LOC=$(wc -l < "$filepath")
    echo "| $INDEX | \`$SERVICE\` | $LOC |" >> "$OUTPUT_FILE"
    INDEX=$((INDEX + 1))
done

cat >> "$OUTPUT_FILE" << EOF

---

## 🎯 CONSOLIDATION ROADMAP

### Phase 1: Low-Risk Consolidations (Week 5)

1. **AI Services (6 → 1)** - Risk: LOW, Impact: HIGH
2. **Cache Services (6 → 1)** - Risk: LOW, Impact: HIGH
3. **Alert Services (3 → 1)** - Risk: LOW, Impact: MEDIUM

### Phase 2: Medium-Risk Consolidations (Week 6)

4. **Flow Services (15 → 4)** - Risk: MEDIUM, Impact: HIGH
5. **Message Services (8 → 2)** - Risk: MEDIUM, Impact: HIGH
6. **Quiz Services (12 → 3)** - Risk: MEDIUM, Impact: MEDIUM

### Phase 3: High-Risk Consolidations (Week 7-8)

7. **Audit Services (3 → 1)** - Risk: HIGH, Impact: MEDIUM
8. **Monitoring Services (8 → 2)** - Risk: HIGH, Impact: HIGH
9. **Analytics Services (5 → 2)** - Risk: MEDIUM, Impact: HIGH
10. **WebSocket Services (5 → 1)** - Risk: HIGH, Impact: HIGH

### Expected Results

- **Before:** $TOTAL_SERVICES services
- **After:** ~35-40 services
- **Reduction:** ~$((TOTAL_SERVICES - 35)) services ($((100 * (TOTAL_SERVICES - 35) / TOTAL_SERVICES))%)
- **Maintainability:** Significantly improved
- **Code Duplication:** Eliminated

---

## ✅ NEXT ACTIONS

1. ✅ **Review this analysis** with team
2. 📋 **Mark QW-016 complete** in CHECKLIST.md
3. 🎯 **Prioritize Phase 1** consolidations
4. 🧪 **Create baseline tests** before refactoring
5. 🌿 **Create branch** \`feature/services-consolidation\`
6. 🚀 **Start with AI services** (lowest risk, highest impact)

---

**Generated by:** \`scripts/analyze_services_simple.sh\` (QW-016)
**Date:** $(date '+%Y-%m-%d %H:%M:%S')
**Tool:** Shell script (fast file system scan)

EOF

echo -e "${GREEN}✅ Report generated!${NC}"
echo ""
echo -e "${BLUE}📊 SUMMARY${NC}"
echo "======================================"
echo "Total Services: $TOTAL_SERVICES"
echo "Total LOC: $TOTAL_LOC"
echo "Average: $AVG_LOC LOC/service"
echo "Target: ~35-40 services"
echo "Reduction: ~$((TOTAL_SERVICES - 35)) services"
echo ""
echo -e "${GREEN}📄 Report: $OUTPUT_FILE${NC}"
