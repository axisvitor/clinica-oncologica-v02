#!/bin/bash
###############################################################################
# CORS Validation Script
# Purpose: Validate CORS configuration in all environments
# Usage: ./validate-cors.sh [API_URL] [FRONTEND_URL]
###############################################################################

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="${1:-http://localhost:8000}"
FRONTEND_URL="${2:-http://localhost:5173}"
ALLOWED_ORIGINS="${3:-$FRONTEND_URL}"
TEMP_DIR="/tmp/cors-validation-$$"
REPORT_FILE="$TEMP_DIR/cors-validation-report.txt"

# Test results counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"
}

print_test() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -e "\n${YELLOW}Test $TESTS_TOTAL: $1${NC}"
    echo "Test $TESTS_TOTAL: $1" >> "$REPORT_FILE"
}

print_success() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}✓ PASS:${NC} $1"
    echo "✓ PASS: $1" >> "$REPORT_FILE"
}

print_failure() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}✗ FAIL:${NC} $1"
    echo "✗ FAIL: $1" >> "$REPORT_FILE"
}

print_info() {
    echo -e "${BLUE}ℹ INFO:${NC} $1"
    echo "ℹ INFO: $1" >> "$REPORT_FILE"
}

check_header() {
    local response_file="$1"
    local header_name="$2"
    local expected_value="$3"

    local actual_value=$(grep -i "< $header_name:" "$response_file" | cut -d':' -f2- | tr -d '\r' | xargs)

    if [ -z "$actual_value" ]; then
        print_failure "Header '$header_name' not found"
        return 1
    fi

    if [ -n "$expected_value" ]; then
        if [[ "$actual_value" == *"$expected_value"* ]]; then
            print_success "Header '$header_name' = '$actual_value'"
            return 0
        else
            print_failure "Header '$header_name' = '$actual_value' (expected: $expected_value)"
            return 1
        fi
    else
        print_success "Header '$header_name' present: '$actual_value'"
        return 0
    fi
}

###############################################################################
# Test Functions
###############################################################################

test_preflight_request() {
    print_test "Preflight OPTIONS Request"

    local response_file="$TEMP_DIR/preflight-response.txt"

    curl -v -X OPTIONS "$API_URL/api/v2/patients" \
        -H "Origin: $FRONTEND_URL" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type,X-CSRF-Token" \
        -o /dev/null \
        -w "%{http_code}" \
        > "$TEMP_DIR/preflight-status.txt" 2> "$response_file"

    local status_code=$(cat "$TEMP_DIR/preflight-status.txt")

    print_info "HTTP Status: $status_code"

    # Check required CORS headers
    check_header "$response_file" "access-control-allow-origin" "$FRONTEND_URL"
    check_header "$response_file" "access-control-allow-credentials" "true"
    check_header "$response_file" "access-control-allow-methods" "POST"
    check_header "$response_file" "access-control-allow-headers" ""
    check_header "$response_file" "access-control-max-age" ""

    echo "" >> "$REPORT_FILE"
}

test_simple_get_request() {
    print_test "Simple GET Request with CORS"

    local response_file="$TEMP_DIR/get-response.txt"

    curl -v -X GET "$API_URL/api/v2/health" \
        -H "Origin: $FRONTEND_URL" \
        -o /dev/null \
        -w "%{http_code}" \
        > "$TEMP_DIR/get-status.txt" 2> "$response_file"

    local status_code=$(cat "$TEMP_DIR/get-status.txt")

    print_info "HTTP Status: $status_code"

    check_header "$response_file" "access-control-allow-origin" "$FRONTEND_URL"
    check_header "$response_file" "access-control-allow-credentials" "true"

    echo "" >> "$REPORT_FILE"
}

test_post_with_credentials() {
    print_test "POST Request with Credentials and CSRF Token"

    local response_file="$TEMP_DIR/post-response.txt"

    curl -v -X POST "$API_URL/api/v2/auth/refresh" \
        -H "Origin: $FRONTEND_URL" \
        -H "Content-Type: application/json" \
        -H "X-CSRF-Token: test-token-value" \
        --cookie "session_token=test-session" \
        -d '{"test": "data"}' \
        -o /dev/null \
        -w "%{http_code}" \
        > "$TEMP_DIR/post-status.txt" 2> "$response_file"

    local status_code=$(cat "$TEMP_DIR/post-status.txt")

    print_info "HTTP Status: $status_code"

    check_header "$response_file" "access-control-allow-origin" "$FRONTEND_URL"
    check_header "$response_file" "access-control-allow-credentials" "true"
    check_header "$response_file" "access-control-expose-headers" ""

    echo "" >> "$REPORT_FILE"
}

test_custom_headers() {
    print_test "Custom Headers Validation"

    local response_file="$TEMP_DIR/custom-headers-response.txt"

    curl -v -X OPTIONS "$API_URL/api/v2/patients" \
        -H "Origin: $FRONTEND_URL" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: X-CSRF-Token,X-Request-ID,X-Client-Version" \
        -o /dev/null \
        -w "%{http_code}" \
        > "$TEMP_DIR/custom-status.txt" 2> "$response_file"

    local status_code=$(cat "$TEMP_DIR/custom-status.txt")

    print_info "HTTP Status: $status_code"

    local allowed_headers=$(grep -i "< access-control-allow-headers:" "$response_file" | cut -d':' -f2- | tr -d '\r' | xargs)

    print_info "Allowed Headers: $allowed_headers"

    if [[ "$allowed_headers" == *"x-csrf-token"* ]] || [[ "$allowed_headers" == *"X-CSRF-Token"* ]]; then
        print_success "X-CSRF-Token is allowed"
    else
        print_failure "X-CSRF-Token not in allowed headers"
    fi

    echo "" >> "$REPORT_FILE"
}

test_blocked_origin() {
    print_test "Blocked Origin Validation"

    local response_file="$TEMP_DIR/blocked-response.txt"
    local malicious_origin="https://malicious-site.com"

    curl -v -X GET "$API_URL/api/v2/patients" \
        -H "Origin: $malicious_origin" \
        -o /dev/null \
        -w "%{http_code}" \
        > "$TEMP_DIR/blocked-status.txt" 2> "$response_file"

    local status_code=$(cat "$TEMP_DIR/blocked-status.txt")

    print_info "HTTP Status: $status_code"

    local cors_header=$(grep -i "< access-control-allow-origin:" "$response_file" | cut -d':' -f2- | tr -d '\r' | xargs)

    if [ -z "$cors_header" ]; then
        print_success "CORS header not present for unauthorized origin"
    elif [[ "$cors_header" != "$malicious_origin" ]]; then
        print_success "CORS header does not match malicious origin"
    else
        print_failure "CORS header present for unauthorized origin: $cors_header"
    fi

    echo "" >> "$REPORT_FILE"
}

test_methods_validation() {
    print_test "HTTP Methods Validation"

    local methods=("GET" "POST" "PUT" "DELETE" "PATCH")

    for method in "${methods[@]}"; do
        local response_file="$TEMP_DIR/method-$method-response.txt"

        curl -v -X OPTIONS "$API_URL/api/v2/patients" \
            -H "Origin: $FRONTEND_URL" \
            -H "Access-Control-Request-Method: $method" \
            -o /dev/null \
            2> "$response_file"

        local allowed_methods=$(grep -i "< access-control-allow-methods:" "$response_file" | cut -d':' -f2- | tr -d '\r' | xargs)

        if [[ "$allowed_methods" == *"$method"* ]]; then
            print_success "Method $method is allowed"
        else
            print_failure "Method $method not in allowed methods: $allowed_methods"
        fi
    done

    echo "" >> "$REPORT_FILE"
}

test_credentials_flag() {
    print_test "Credentials Flag Validation"

    local response_file="$TEMP_DIR/credentials-response.txt"

    curl -v -X GET "$API_URL/api/v2/health" \
        -H "Origin: $FRONTEND_URL" \
        --cookie "session_token=test" \
        -o /dev/null \
        2> "$response_file"

    local credentials=$(grep -i "< access-control-allow-credentials:" "$response_file" | cut -d':' -f2- | tr -d '\r' | xargs)

    if [[ "$credentials" == "true" ]]; then
        print_success "Credentials flag is set to 'true'"
    else
        print_failure "Credentials flag is not 'true': $credentials"
    fi

    echo "" >> "$REPORT_FILE"
}

test_vary_header() {
    print_test "Vary Header Validation"

    local response_file="$TEMP_DIR/vary-response.txt"

    curl -v -X GET "$API_URL/api/v2/health" \
        -H "Origin: $FRONTEND_URL" \
        -o /dev/null \
        2> "$response_file"

    local vary_header=$(grep -i "< vary:" "$response_file" | cut -d':' -f2- | tr -d '\r' | xargs)

    if [[ "$vary_header" == *"Origin"* ]]; then
        print_success "Vary header includes 'Origin': $vary_header"
    else
        print_failure "Vary header missing 'Origin': $vary_header"
    fi

    echo "" >> "$REPORT_FILE"
}

###############################################################################
# Main Execution
###############################################################################

main() {
    # Create temp directory
    mkdir -p "$TEMP_DIR"

    print_header "CORS Configuration Validation"

    echo "Configuration:" | tee "$REPORT_FILE"
    echo "  API URL: $API_URL" | tee -a "$REPORT_FILE"
    echo "  Frontend URL: $FRONTEND_URL" | tee -a "$REPORT_FILE"
    echo "  Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")" | tee -a "$REPORT_FILE"
    echo "" | tee -a "$REPORT_FILE"

    # Check if API is reachable
    print_info "Checking API availability..."
    if ! curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v2/health" > /dev/null 2>&1; then
        echo -e "${RED}ERROR: API is not reachable at $API_URL${NC}"
        echo "Please ensure the API is running and accessible."
        exit 1
    fi
    print_success "API is reachable"

    # Run all tests
    test_preflight_request
    test_simple_get_request
    test_post_with_credentials
    test_custom_headers
    test_blocked_origin
    test_methods_validation
    test_credentials_flag
    test_vary_header

    # Summary
    print_header "Test Summary"

    echo "Total Tests: $TESTS_TOTAL" | tee -a "$REPORT_FILE"
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}" | tee -a "$REPORT_FILE"
    echo -e "${RED}Failed: $TESTS_FAILED${NC}" | tee -a "$REPORT_FILE"

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "\n${GREEN}✓ All CORS validations passed!${NC}" | tee -a "$REPORT_FILE"
        exit_code=0
    else
        echo -e "\n${RED}✗ Some CORS validations failed!${NC}" | tee -a "$REPORT_FILE"
        exit_code=1
    fi

    # Save report
    local final_report="/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/cors-validation-report.txt"
    cp "$REPORT_FILE" "$final_report"
    echo -e "\n${BLUE}Full report saved to: $final_report${NC}"

    # Cleanup
    # rm -rf "$TEMP_DIR"

    exit $exit_code
}

# Run main function
main "$@"
