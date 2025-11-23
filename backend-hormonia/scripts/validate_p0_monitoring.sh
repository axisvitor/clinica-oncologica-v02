#!/bin/bash
# P0 Monitoring Validation Script
# Validates monitoring infrastructure deployment and configuration
# Usage: ./scripts/validate_p0_monitoring.sh

set -e

echo "======================================================================"
echo "P0 MONITORING VALIDATION SCRIPT"
echo "======================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
    ((WARNINGS++))
}

info() {
    echo -e "ℹ INFO: $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ======================================================================
# 1. PREREQUISITE CHECKS
# ======================================================================
echo "1. Checking Prerequisites..."
echo "----------------------------------------------------------------------"

if command_exists docker; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    pass "Docker installed (version: $DOCKER_VERSION)"
else
    fail "Docker not installed"
fi

if command_exists docker-compose; then
    COMPOSE_VERSION=$(docker-compose --version | awk '{print $3}' | sed 's/,//')
    pass "Docker Compose installed (version: $COMPOSE_VERSION)"
else
    fail "Docker Compose not installed"
fi

if command_exists curl; then
    pass "curl installed"
else
    fail "curl not installed"
fi

if command_exists jq; then
    pass "jq installed"
else
    warn "jq not installed (optional, used for JSON parsing)"
fi

echo ""

# ======================================================================
# 2. CONFIGURATION FILE CHECKS
# ======================================================================
echo "2. Checking Configuration Files..."
echo "----------------------------------------------------------------------"

# Check Prometheus alert rules
if [ -f "monitoring/prometheus/p0_alerts.yml" ]; then
    pass "P0 alert rules file exists"

    # Validate YAML syntax
    if command_exists yamllint; then
        if yamllint -d relaxed monitoring/prometheus/p0_alerts.yml >/dev/null 2>&1; then
            pass "P0 alert rules YAML syntax valid"
        else
            fail "P0 alert rules YAML syntax invalid"
        fi
    else
        warn "yamllint not installed, skipping YAML validation"
    fi
else
    fail "P0 alert rules file missing: monitoring/prometheus/p0_alerts.yml"
fi

# Check Grafana dashboard
if [ -f "monitoring/grafana/dashboards/p0_dashboard.json" ]; then
    pass "P0 Grafana dashboard file exists"

    # Validate JSON syntax
    if cat monitoring/grafana/dashboards/p0_dashboard.json | jq empty >/dev/null 2>&1; then
        pass "P0 dashboard JSON syntax valid"
    else
        fail "P0 dashboard JSON syntax invalid"
    fi
else
    fail "P0 dashboard file missing: monitoring/grafana/dashboards/p0_dashboard.json"
fi

# Check Alertmanager config
if [ -f "monitoring/alertmanager/p0_config.yml" ]; then
    pass "Alertmanager P0 config file exists"
else
    fail "Alertmanager P0 config file missing: monitoring/alertmanager/p0_config.yml"
fi

# Check environment file
if [ -f "monitoring/.env" ]; then
    pass "Monitoring .env file exists"

    # Check required environment variables
    source monitoring/.env 2>/dev/null || true

    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        pass "SLACK_WEBHOOK_URL configured"
    else
        fail "SLACK_WEBHOOK_URL not set in .env"
    fi

    if [ -n "$GRAFANA_ADMIN_PASSWORD" ]; then
        pass "GRAFANA_ADMIN_PASSWORD configured"
    else
        warn "GRAFANA_ADMIN_PASSWORD not set (using default)"
    fi

    if [ -n "$PAGERDUTY_P0_CRITICAL_KEY" ]; then
        pass "PAGERDUTY_P0_CRITICAL_KEY configured"
    else
        warn "PAGERDUTY_P0_CRITICAL_KEY not set"
    fi
else
    fail "Monitoring .env file missing"
    info "Copy monitoring/.env.example to monitoring/.env and configure"
fi

echo ""

# ======================================================================
# 3. DOCKER SERVICE CHECKS
# ======================================================================
echo "3. Checking Docker Services..."
echo "----------------------------------------------------------------------"

# Check if monitoring stack is running
if docker-compose -f monitoring/docker-compose.monitoring.yml ps | grep -q "Up"; then
    pass "Monitoring stack is running"

    # Check individual services
    SERVICES=("prometheus" "grafana" "alertmanager" "node-exporter")
    for service in "${SERVICES[@]}"; do
        if docker-compose -f monitoring/docker-compose.monitoring.yml ps | grep -q "$service.*Up"; then
            pass "Service '$service' is running"
        else
            fail "Service '$service' is not running"
        fi
    done
else
    fail "Monitoring stack is not running"
    info "Start with: docker-compose -f monitoring/docker-compose.monitoring.yml up -d"
fi

echo ""

# ======================================================================
# 4. SERVICE HEALTH CHECKS
# ======================================================================
echo "4. Checking Service Health..."
echo "----------------------------------------------------------------------"

# Check Prometheus
if curl -s http://localhost:9090/-/healthy >/dev/null 2>&1; then
    pass "Prometheus health check OK"

    # Check if Prometheus is ready
    if curl -s http://localhost:9090/-/ready >/dev/null 2>&1; then
        pass "Prometheus ready check OK"
    else
        warn "Prometheus not ready yet"
    fi
else
    fail "Prometheus health check failed"
fi

# Check Grafana
if curl -s http://localhost:3000/api/health >/dev/null 2>&1; then
    pass "Grafana health check OK"
else
    fail "Grafana health check failed"
fi

# Check Alertmanager
if curl -s http://localhost:9093/-/healthy >/dev/null 2>&1; then
    pass "Alertmanager health check OK"
else
    fail "Alertmanager health check failed"
fi

echo ""

# ======================================================================
# 5. PROMETHEUS TARGET CHECKS
# ======================================================================
echo "5. Checking Prometheus Targets..."
echo "----------------------------------------------------------------------"

if command_exists jq; then
    TARGETS=$(curl -s http://localhost:9090/api/v1/targets 2>/dev/null | jq -r '.data.activeTargets[] | "\(.labels.job):\(.health)"')

    if [ -n "$TARGETS" ]; then
        echo "$TARGETS" | while read -r target; do
            JOB=$(echo "$target" | cut -d: -f1)
            HEALTH=$(echo "$target" | cut -d: -f2)

            if [ "$HEALTH" = "up" ]; then
                pass "Target '$JOB' is UP"
            else
                fail "Target '$JOB' is $HEALTH"
            fi
        done
    else
        warn "No Prometheus targets found or Prometheus not accessible"
    fi
else
    warn "Skipping target checks (jq not installed)"
fi

echo ""

# ======================================================================
# 6. ALERT RULE CHECKS
# ======================================================================
echo "6. Checking Alert Rules..."
echo "----------------------------------------------------------------------"

if command_exists jq; then
    RULES=$(curl -s http://localhost:9090/api/v1/rules 2>/dev/null | jq -r '.data.groups[] | "\(.name):\(.file)"')

    if echo "$RULES" | grep -q "p0_"; then
        pass "P0 alert rules loaded in Prometheus"

        # Count P0 rules
        P0_RULE_COUNT=$(curl -s http://localhost:9090/api/v1/rules 2>/dev/null | jq '[.data.groups[] | select(.name | startswith("p0_")) | .rules[]] | length')
        info "Loaded $P0_RULE_COUNT P0 alert rules"
    else
        fail "P0 alert rules not loaded"
        info "Check Prometheus logs and configuration"
    fi
else
    warn "Skipping alert rule checks (jq not installed)"
fi

echo ""

# ======================================================================
# 7. GRAFANA DASHBOARD CHECKS
# ======================================================================
echo "7. Checking Grafana Dashboards..."
echo "----------------------------------------------------------------------"

# Check if P0 dashboard is imported
if command_exists jq; then
    DASHBOARDS=$(curl -s -u admin:${GRAFANA_ADMIN_PASSWORD:-admin} http://localhost:3000/api/search?query=P0 2>/dev/null)

    if echo "$DASHBOARDS" | jq -e '. | length > 0' >/dev/null 2>&1; then
        DASHBOARD_TITLE=$(echo "$DASHBOARDS" | jq -r '.[0].title')
        pass "P0 dashboard imported: '$DASHBOARD_TITLE'"

        DASHBOARD_UID=$(echo "$DASHBOARDS" | jq -r '.[0].uid')
        info "Dashboard UID: $DASHBOARD_UID"
        info "Access at: http://localhost:3000/d/$DASHBOARD_UID"
    else
        warn "P0 dashboard not imported yet"
        info "Import from: monitoring/grafana/dashboards/p0_dashboard.json"
    fi
else
    warn "Skipping dashboard checks (jq not installed)"
fi

echo ""

# ======================================================================
# 8. ALERTMANAGER CONFIGURATION CHECKS
# ======================================================================
echo "8. Checking Alertmanager Configuration..."
echo "----------------------------------------------------------------------"

if command_exists jq; then
    AM_CONFIG=$(curl -s http://localhost:9093/api/v1/status 2>/dev/null)

    if [ -n "$AM_CONFIG" ]; then
        pass "Alertmanager configuration loaded"

        # Check receivers
        RECEIVERS=$(echo "$AM_CONFIG" | jq -r '.data.config.receivers[] | .name' 2>/dev/null || echo "")
        if echo "$RECEIVERS" | grep -q "p0-"; then
            pass "P0 alert receivers configured"
        else
            warn "P0 alert receivers not found"
        fi
    else
        fail "Cannot retrieve Alertmanager configuration"
    fi
else
    warn "Skipping Alertmanager checks (jq not installed)"
fi

echo ""

# ======================================================================
# 9. CONNECTIVITY TESTS
# ======================================================================
echo "9. Testing External Integrations..."
echo "----------------------------------------------------------------------"

# Test Slack webhook (if configured)
if [ -n "$SLACK_WEBHOOK_URL" ]; then
    if curl -s -X POST -H 'Content-type: application/json' \
        --data '{"text":"P0 Monitoring Validation Test"}' \
        "$SLACK_WEBHOOK_URL" >/dev/null 2>&1; then
        pass "Slack webhook test successful"
        info "Check your Slack channel for test message"
    else
        fail "Slack webhook test failed"
    fi
else
    warn "SLACK_WEBHOOK_URL not configured, skipping test"
fi

# Test SMTP (if configured)
if [ -n "$SMTP_HOST" ] && [ -n "$SMTP_PORT" ]; then
    if nc -zv "$SMTP_HOST" "$SMTP_PORT" >/dev/null 2>&1; then
        pass "SMTP server reachable ($SMTP_HOST:$SMTP_PORT)"
    else
        fail "SMTP server not reachable ($SMTP_HOST:$SMTP_PORT)"
    fi
else
    warn "SMTP not configured, skipping test"
fi

echo ""

# ======================================================================
# 10. SUMMARY
# ======================================================================
echo "======================================================================"
echo "VALIDATION SUMMARY"
echo "======================================================================"
echo ""
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Access Grafana: http://localhost:3000"
    echo "2. View P0 Dashboard: http://localhost:3000/d/p0-monitoring"
    echo "3. Check Prometheus: http://localhost:9090"
    echo "4. Monitor Alertmanager: http://localhost:9093"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some checks failed - please review above${NC}"
    echo ""
    echo "Common fixes:"
    echo "1. Start monitoring stack: docker-compose -f monitoring/docker-compose.monitoring.yml up -d"
    echo "2. Configure .env file: cp monitoring/.env.example monitoring/.env"
    echo "3. Import P0 dashboard in Grafana UI"
    echo "4. Check service logs: docker-compose -f monitoring/docker-compose.monitoring.yml logs"
    echo ""
    exit 1
fi
