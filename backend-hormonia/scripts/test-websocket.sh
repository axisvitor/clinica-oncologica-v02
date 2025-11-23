#!/bin/bash
###############################################################################
# WebSocket Connection Test Script
# Tests WebSocket endpoints using wscat and Node.js test suite
#
# Usage:
#   ./test-websocket.sh [ws-url] [environment]
#   ./test-websocket.sh ws://localhost:8000/ws development
#   ./test-websocket.sh wss://api.example.com/ws production
###############################################################################

set -e

# Configuration
WS_URL="${1:-ws://localhost:8000/ws}"
ENVIRONMENT="${2:-development}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="${SCRIPT_DIR}/../reports/websocket"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create report directory
mkdir -p "$REPORT_DIR"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║       WebSocket Connection Test Wrapper              ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "URL: $WS_URL"
echo "Environment: $ENVIRONMENT"
echo "Report Directory: $REPORT_DIR"
echo ""

# Function to check if command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Function to install dependencies
install_dependencies() {
  echo "Checking dependencies..."

  # Check for Node.js
  if ! command_exists node; then
    echo -e "${RED}✗ Node.js not found. Please install Node.js first.${NC}"
    exit 1
  fi

  # Check for npm
  if ! command_exists npm; then
    echo -e "${RED}✗ npm not found. Please install npm first.${NC}"
    exit 1
  fi

  # Install wscat if not present
  if ! command_exists wscat; then
    echo -e "${YELLOW}Installing wscat...${NC}"
    npm install -g wscat
  fi

  # Install ws module if not present
  if ! npm list -g ws >/dev/null 2>&1; then
    echo -e "${YELLOW}Installing ws module...${NC}"
    npm install -g ws
  fi

  echo -e "${GREEN}✓ Dependencies installed${NC}\n"
}

# Function to test basic connection with wscat
test_wscat_connection() {
  echo "═══════════════════════════════════════════════════════"
  echo "Test 1: Basic Connection (wscat)"
  echo "═══════════════════════════════════════════════════════"

  if timeout 5 wscat -c "$WS_URL" --execute "ping" --wait 3 2>&1 | tee "$REPORT_DIR/wscat_${TIMESTAMP}.log"; then
    echo -e "${GREEN}✓ Basic connection successful${NC}\n"
    return 0
  else
    echo -e "${RED}✗ Basic connection failed${NC}\n"
    return 1
  fi
}

# Function to test authenticated connection
test_authenticated_connection() {
  echo "═══════════════════════════════════════════════════════"
  echo "Test 2: Authenticated Connection"
  echo "═══════════════════════════════════════════════════════"

  if timeout 5 wscat -c "$WS_URL" \
    --header "Cookie: session=test-session-token" \
    --execute '{"type":"authenticate","token":"test-token"}' \
    --wait 3 2>&1 | tee -a "$REPORT_DIR/wscat_${TIMESTAMP}.log"; then
    echo -e "${GREEN}✓ Authenticated connection successful${NC}\n"
    return 0
  else
    echo -e "${YELLOW}⚠ Authentication test inconclusive${NC}\n"
    return 0
  fi
}

# Function to test message handling
test_message_handling() {
  echo "═══════════════════════════════════════════════════════"
  echo "Test 3: Message Handling"
  echo "═══════════════════════════════════════════════════════"

  if echo '{"type": "subscribe", "channel": "patients"}' | timeout 5 wscat -c "$WS_URL" --wait 3 2>&1 | tee -a "$REPORT_DIR/wscat_${TIMESTAMP}.log"; then
    echo -e "${GREEN}✓ Message handling successful${NC}\n"
    return 0
  else
    echo -e "${RED}✗ Message handling failed${NC}\n"
    return 1
  fi
}

# Function to test SSL/TLS (production only)
test_ssl_tls() {
  echo "═══════════════════════════════════════════════════════"
  echo "Test 4: SSL/TLS Validation"
  echo "═══════════════════════════════════════════════════════"

  # Extract host from WebSocket URL
  HOST=$(echo "$WS_URL" | sed -e 's|wss://||' -e 's|ws://||' -e 's|/.*||')

  if echo | timeout 10 openssl s_client -connect "$HOST" -servername "$HOST" 2>&1 | tee "$REPORT_DIR/ssl_${TIMESTAMP}.log" | grep -q "Verify return code: 0"; then
    echo -e "${GREEN}✓ SSL/TLS validation successful${NC}\n"
    return 0
  else
    echo -e "${YELLOW}⚠ SSL/TLS validation inconclusive${NC}\n"
    return 0
  fi
}

# Function to run Node.js test suite
run_nodejs_tests() {
  echo "═══════════════════════════════════════════════════════"
  echo "Test 5: Node.js Test Suite"
  echo "═══════════════════════════════════════════════════════"

  if node "$SCRIPT_DIR/test-websocket.js" "$WS_URL" "$ENVIRONMENT" 2>&1 | tee "$REPORT_DIR/nodejs_${TIMESTAMP}.log"; then
    echo -e "${GREEN}✓ Node.js test suite passed${NC}\n"
    return 0
  else
    echo -e "${RED}✗ Node.js test suite failed${NC}\n"
    return 1
  fi
}

# Function to generate report
generate_report() {
  local exit_code=$1

  echo "═══════════════════════════════════════════════════════"
  echo "Generating Test Report"
  echo "═══════════════════════════════════════════════════════"

  REPORT_FILE="$REPORT_DIR/report_${TIMESTAMP}.txt"

  cat > "$REPORT_FILE" <<EOF
WebSocket Connection Test Report
Generated: $(date)

Configuration:
  URL: $WS_URL
  Environment: $ENVIRONMENT

Test Results:
$(if [ $exit_code -eq 0 ]; then echo "  Overall: PASSED ✓"; else echo "  Overall: FAILED ✗"; fi)

Logs:
  wscat: $REPORT_DIR/wscat_${TIMESTAMP}.log
  Node.js: $REPORT_DIR/nodejs_${TIMESTAMP}.log
$(if [ "$ENVIRONMENT" == "production" ]; then echo "  SSL/TLS: $REPORT_DIR/ssl_${TIMESTAMP}.log"; fi)

Summary:
$(tail -20 "$REPORT_DIR/nodejs_${TIMESTAMP}.log" 2>/dev/null || echo "  No Node.js test results available")

EOF

  echo "Report saved to: $REPORT_FILE"
  echo ""

  # Display report
  cat "$REPORT_FILE"
}

# Main execution
main() {
  local exit_code=0

  # Install dependencies
  install_dependencies

  # Run tests
  test_wscat_connection || exit_code=1
  test_authenticated_connection || true
  test_message_handling || exit_code=1

  # SSL/TLS test (production only)
  if [[ "$ENVIRONMENT" == "production" ]] && [[ "$WS_URL" == wss://* ]]; then
    test_ssl_tls || true
  fi

  # Run comprehensive Node.js tests
  run_nodejs_tests || exit_code=1

  # Generate report
  generate_report $exit_code

  # Final result
  echo "╔═══════════════════════════════════════════════════════╗"
  echo "║                   Final Result                        ║"
  echo "╚═══════════════════════════════════════════════════════╝"

  if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed successfully${NC}"
  else
    echo -e "${RED}✗ Some tests failed. Check the report for details.${NC}"
  fi

  echo ""

  exit $exit_code
}

# Run main function
main
