#!/bin/sh
# Railway DNS Diagnostic Tool
# Analisa e diagnostica problemas de conexão frontend → backend

set -e

echo "🔍 Railway DNS & Networking Diagnostic Tool"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
success() { echo "${GREEN}✅ $1${NC}"; }
error() { echo "${RED}❌ $1${NC}"; }
warning() { echo "${YELLOW}⚠️  $1${NC}"; }
info() { echo "${BLUE}ℹ️  $1${NC}"; }

echo "📋 STEP 1: Environment Variables Check"
echo "--------------------------------------"

if [ -z "$BACKEND_HOST" ]; then
    error "BACKEND_HOST not set"
    warning "Using default: backend (may not work in Railway)"
    export BACKEND_HOST="backend"
else
    success "BACKEND_HOST = $BACKEND_HOST"
fi

if [ -z "$BACKEND_PORT" ]; then
    error "BACKEND_PORT not set"
    warning "Using default: 8000"
    export BACKEND_PORT="8000"
else
    success "BACKEND_PORT = $BACKEND_PORT"
fi

echo ""
echo "📋 STEP 2: Railway Service Variables"
echo "------------------------------------"

# Check for Railway-generated service variables
railway_vars=$(env | grep "^RAILWAY_SERVICE_" || true)

if [ -z "$railway_vars" ]; then
    warning "No RAILWAY_SERVICE_* variables found"
    info "This might indicate:"
    info "  - Backend not deployed in same Railway project"
    info "  - Services not linked"
    info "  - Need to use manual BACKEND_HOST configuration"
else
    success "Found Railway service variables:"
    echo "$railway_vars" | while read -r line; do
        echo "  ${GREEN}→${NC} $line"
    done
fi

echo ""
echo "📋 STEP 3: DNS Resolution Test"
echo "-------------------------------"

# Try to resolve backend hostname
info "Testing DNS resolution for: $BACKEND_HOST"

if command -v nslookup > /dev/null 2>&1; then
    if nslookup "$BACKEND_HOST" > /dev/null 2>&1; then
        success "DNS resolution successful"
        nslookup "$BACKEND_HOST" | grep -A1 "Name:" || true
    else
        error "DNS resolution FAILED"
        warning "Hostname '$BACKEND_HOST' cannot be resolved"
        info "Possible solutions:"
        info "  1. Check backend service name in Railway Dashboard"
        info "  2. Use format: [service-name].railway.internal"
        info "  3. Verify Private Networking is enabled"
    fi
else
    warning "nslookup not available (install with: apk add bind-tools)"
fi

# Try with dig if available
if command -v dig > /dev/null 2>&1; then
    dig "$BACKEND_HOST" +short
fi

echo ""
echo "📋 STEP 4: Network Connectivity Test"
echo "------------------------------------"

info "Testing connectivity to: $BACKEND_HOST:$BACKEND_PORT"

if command -v curl > /dev/null 2>&1; then
    if curl -s -f -m 5 "http://$BACKEND_HOST:$BACKEND_PORT/health" > /dev/null 2>&1; then
        success "Backend is reachable and responding"
        response=$(curl -s -m 5 "http://$BACKEND_HOST:$BACKEND_PORT/health")
        info "Response: $response"
    else
        error "Backend is NOT reachable"
        warning "Connection to http://$BACKEND_HOST:$BACKEND_PORT/health FAILED"
        info "Possible causes:"
        info "  1. Backend service is not running"
        info "  2. Backend is not listening on port $BACKEND_PORT"
        info "  3. Firewall/network policy blocking connection"
        info "  4. Healthcheck endpoint not configured"
    fi
else
    warning "curl not available (install with: apk add curl)"
fi

# Try with wget if curl not available
if command -v wget > /dev/null 2>&1 && ! command -v curl > /dev/null 2>&1; then
    if wget -q -O- --timeout=5 "http://$BACKEND_HOST:$BACKEND_PORT/health" > /dev/null 2>&1; then
        success "Backend is reachable (via wget)"
    else
        error "Backend connection failed (via wget)"
    fi
fi

echo ""
echo "📋 STEP 5: Nginx Configuration Check"
echo "------------------------------------"

if [ -f /etc/nginx/nginx.conf ]; then
    success "nginx.conf exists"

    # Extract upstream configuration
    upstream_config=$(grep -A 3 "upstream backend" /etc/nginx/nginx.conf || true)

    if [ -n "$upstream_config" ]; then
        info "Upstream backend configuration:"
        echo "$upstream_config" | while read -r line; do
            echo "  ${BLUE}→${NC} $line"
        done

        # Check if it has the variable or actual value
        if echo "$upstream_config" | grep -q "\${BACKEND_HOST}"; then
            error "Variables NOT substituted in nginx.conf"
            warning "envsubst might have failed"
        else
            success "Variables properly substituted"
        fi
    else
        error "No 'upstream backend' block found in nginx.conf"
    fi
else
    error "nginx.conf NOT found at /etc/nginx/nginx.conf"

    if [ -f /etc/nginx/nginx.conf.template ]; then
        warning "Template exists but nginx.conf not created"
        info "envsubst might have failed"
    fi
fi

echo ""
echo "📋 STEP 6: Alternative Hostname Detection"
echo "------------------------------------------"

info "Attempting to auto-detect backend hostname..."

# Try common Railway patterns
common_patterns=(
    "backend.railway.internal"
    "backend-hormonia.railway.internal"
    "api.railway.internal"
    "backend-production.railway.internal"
)

for pattern in "${common_patterns[@]}"; do
    info "Trying: $pattern"
    if command -v nslookup > /dev/null 2>&1; then
        if nslookup "$pattern" > /dev/null 2>&1; then
            success "FOUND: $pattern resolves!"
            info "Suggestion: Set BACKEND_HOST=$pattern"
        fi
    fi
done

echo ""
echo "📋 STEP 7: Recommendations"
echo "--------------------------"

if [ "$BACKEND_HOST" = "backend" ]; then
    error "Using default hostname 'backend'"
    echo ""
    info "${YELLOW}RECOMMENDED ACTIONS:${NC}"
    echo "1. In Railway Dashboard, find your backend service name"
    echo "2. Set environment variable in Frontend service:"
    echo "   ${GREEN}BACKEND_HOST=[backend-service-name].railway.internal${NC}"
    echo "   ${GREEN}BACKEND_PORT=8000${NC}"
    echo ""
    echo "3. Or use Railway Service Reference Variables:"
    echo "   ${GREEN}export BACKEND_HOST=\$RAILWAY_SERVICE_BACKEND_URL${NC}"
    echo ""
fi

echo ""
echo "📋 STEP 8: Summary"
echo "------------------"

# Build summary
issues_found=0

if [ "$BACKEND_HOST" = "backend" ]; then
    issues_found=$((issues_found + 1))
    error "Issue 1: Using default hostname"
fi

if ! command -v nslookup > /dev/null 2>&1 || ! nslookup "$BACKEND_HOST" > /dev/null 2>&1; then
    issues_found=$((issues_found + 1))
    error "Issue 2: DNS resolution failing"
fi

if ! command -v curl > /dev/null 2>&1 || ! curl -s -f -m 5 "http://$BACKEND_HOST:$BACKEND_PORT/health" > /dev/null 2>&1; then
    issues_found=$((issues_found + 1))
    error "Issue 3: Backend not reachable"
fi

if [ $issues_found -eq 0 ]; then
    success "No critical issues found!"
    success "Backend connection should work"
else
    warning "Found $issues_found issue(s)"
    info "Review recommendations above to fix"
fi

echo ""
echo "📚 Documentation:"
echo "  - RAILWAY_DNS_ERROR_ANALYSIS.md"
echo "  - RAILWAY_NETWORKING_GUIDE.md"
echo "  - RAILWAY_DNS_FIX_CHECKLIST.md"
echo ""
echo "============================================"
echo "🏁 Diagnostic Complete"
