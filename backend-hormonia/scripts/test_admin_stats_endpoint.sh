#!/bin/bash
# Test script for /api/v1/admin/system-stats endpoint
# Usage: ./scripts/test_admin_stats_endpoint.sh <ADMIN_TOKEN>

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
ADMIN_TOKEN="${1:-}"

echo "=========================================="
echo "Admin System Stats Endpoint Test"
echo "=========================================="
echo ""

if [ -z "$ADMIN_TOKEN" ]; then
    echo "❌ Error: Admin token required"
    echo "Usage: $0 <ADMIN_TOKEN>"
    echo ""
    echo "To get a token:"
    echo "1. Login as admin user"
    echo "2. Copy Firebase ID token"
    echo "3. Run: $0 <TOKEN>"
    exit 1
fi

echo "📍 Testing endpoint: ${BASE_URL}/api/v1/admin/system-stats"
echo ""

# Test 1: Unauthenticated request (should fail)
echo "Test 1: Unauthenticated request"
echo "Expected: 401 Unauthorized"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/v1/admin/system-stats")
if [ "$HTTP_CODE" = "401" ]; then
    echo "✅ PASS - Got 401 Unauthorized"
else
    echo "❌ FAIL - Expected 401, got ${HTTP_CODE}"
fi
echo ""

# Test 2: Authenticated request with admin token
echo "Test 2: Authenticated admin request"
echo "Expected: 200 OK"
RESPONSE=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    "${BASE_URL}/api/v1/admin/system-stats")

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ PASS - Got 200 OK"
    echo ""
    echo "Response body:"
    echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
    echo ""

    # Validate response structure
    echo "Validating response structure..."

    HAS_SYSTEM=$(echo "$BODY" | jq -e '.system' >/dev/null 2>&1 && echo "yes" || echo "no")
    HAS_USERS=$(echo "$BODY" | jq -e '.users' >/dev/null 2>&1 && echo "yes" || echo "no")
    HAS_DATABASE=$(echo "$BODY" | jq -e '.database' >/dev/null 2>&1 && echo "yes" || echo "no")
    HAS_TIMESTAMP=$(echo "$BODY" | jq -e '.timestamp' >/dev/null 2>&1 && echo "yes" || echo "no")

    if [ "$HAS_SYSTEM" = "yes" ] && [ "$HAS_USERS" = "yes" ] && \
       [ "$HAS_DATABASE" = "yes" ] && [ "$HAS_TIMESTAMP" = "yes" ]; then
        echo "✅ Response structure valid"
    else
        echo "❌ Response structure invalid"
        echo "   - system: $HAS_SYSTEM"
        echo "   - users: $HAS_USERS"
        echo "   - database: $HAS_DATABASE"
        echo "   - timestamp: $HAS_TIMESTAMP"
    fi
else
    echo "❌ FAIL - Expected 200, got ${HTTP_CODE}"
    echo "Response: $BODY"
fi
echo ""

# Test 3: Cache test (second request should have same timestamp)
echo "Test 3: Cache behavior (30s TTL)"
echo "Making second request within 30s..."
RESPONSE2=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    "${BASE_URL}/api/v1/admin/system-stats")

HTTP_CODE2=$(echo "$RESPONSE2" | tail -n 1)
BODY2=$(echo "$RESPONSE2" | sed '$d')

if [ "$HTTP_CODE2" = "200" ]; then
    TIMESTAMP1=$(echo "$BODY" | jq -r '.timestamp' 2>/dev/null || echo "")
    TIMESTAMP2=$(echo "$BODY2" | jq -r '.timestamp' 2>/dev/null || echo "")

    if [ "$TIMESTAMP1" = "$TIMESTAMP2" ] && [ -n "$TIMESTAMP1" ]; then
        echo "✅ PASS - Timestamps match (cached response)"
        echo "   Timestamp: $TIMESTAMP1"
    else
        echo "⚠️  WARNING - Timestamps don't match (cache might not be working)"
        echo "   First:  $TIMESTAMP1"
        echo "   Second: $TIMESTAMP2"
    fi
else
    echo "❌ FAIL - Second request failed with ${HTTP_CODE2}"
fi
echo ""

# Test 4: Metrics validation
echo "Test 4: Metrics validation"
CPU=$(echo "$BODY" | jq -r '.system.cpu_percent' 2>/dev/null || echo "")
MEMORY=$(echo "$BODY" | jq -r '.system.memory_percent' 2>/dev/null || echo "")
TOTAL_USERS=$(echo "$BODY" | jq -r '.users.total' 2>/dev/null || echo "")
CONNECTIONS=$(echo "$BODY" | jq -r '.database.connections' 2>/dev/null || echo "")

echo "System Metrics:"
echo "  - CPU: ${CPU}%"
echo "  - Memory: ${MEMORY}%"
echo ""
echo "User Metrics:"
echo "  - Total Users: ${TOTAL_USERS}"
echo ""
echo "Database Metrics:"
echo "  - Active Connections: ${CONNECTIONS}"
echo ""

if [ -n "$CPU" ] && [ -n "$MEMORY" ] && [ -n "$TOTAL_USERS" ] && [ -n "$CONNECTIONS" ]; then
    echo "✅ All metrics present"
else
    echo "❌ Some metrics missing"
fi
echo ""

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Endpoint: ${BASE_URL}/api/v1/admin/system-stats"
echo "Status: All critical tests completed"
echo ""
echo "Next steps:"
echo "1. Verify metrics in admin dashboard UI"
echo "2. Monitor cache hit rate in Redis logs"
echo "3. Check response times (target: <100ms)"
echo "=========================================="
