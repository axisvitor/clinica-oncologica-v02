#!/bin/bash
###############################################################################
# WebSocket Continuous Monitoring Script
# Monitors WebSocket connections and sends alerts on failures
#
# Usage:
#   ./monitor-websocket.sh [ws-url] [interval-seconds] [alert-webhook]
#   ./monitor-websocket.sh wss://api.example.com/ws 60 https://alerts.example.com/webhook
###############################################################################

set -e

# Configuration
WS_URL="${1:-wss://api.example.com/ws}"
INTERVAL="${2:-60}"
ALERT_WEBHOOK="${3:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/../logs/websocket-monitor"
MAX_CONSECUTIVE_FAILURES=3
CONSECUTIVE_FAILURES=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create log directory
mkdir -p "$LOG_DIR"

# Log file
LOG_FILE="$LOG_DIR/monitor_$(date +"%Y%m%d").log"

# Function to log messages
log_message() {
  local level=$1
  shift
  local message="$@"
  local timestamp=$(date +"%Y-%m-%d %H:%M:%S")

  echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Function to send alert
send_alert() {
  local message="$1"
  local severity="${2:-warning}"

  log_message "ALERT" "$message"

  # Send webhook alert if configured
  if [ -n "$ALERT_WEBHOOK" ]; then
    curl -X POST "$ALERT_WEBHOOK" \
      -H "Content-Type: application/json" \
      -d "{
        \"message\": \"$message\",
        \"severity\": \"$severity\",
        \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",
        \"source\": \"websocket-monitor\",
        \"url\": \"$WS_URL\"
      }" \
      --max-time 10 \
      --silent \
      --show-error || log_message "ERROR" "Failed to send webhook alert"
  fi

  # Log to syslog if available
  if command -v logger >/dev/null 2>&1; then
    logger -t websocket-monitor -p daemon.$severity "$message"
  fi
}

# Function to test WebSocket connection
test_connection() {
  local test_output

  # Try to connect with timeout
  if test_output=$(timeout 10 wscat -c "$WS_URL" --execute "ping" --wait 3 2>&1); then
    return 0
  else
    log_message "DEBUG" "Connection test output: $test_output"
    return 1
  fi
}

# Function to get connection metrics
get_metrics() {
  local start_time=$(date +%s%3N)

  if test_connection; then
    local end_time=$(date +%s%3N)
    local latency=$((end_time - start_time))
    echo "$latency"
    return 0
  else
    echo "-1"
    return 1
  fi
}

# Function to check system resources
check_system_resources() {
  local cpu_usage=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
  local mem_usage=$(free | grep Mem | awk '{print ($3/$2) * 100.0}')
  local disk_usage=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')

  log_message "INFO" "System: CPU=${cpu_usage}% MEM=${mem_usage}% DISK=${disk_usage}%"

  # Alert on high resource usage
  if (( $(echo "$cpu_usage > 90" | bc -l) )); then
    send_alert "High CPU usage: ${cpu_usage}%" "warning"
  fi

  if (( $(echo "$mem_usage > 90" | bc -l) )); then
    send_alert "High memory usage: ${mem_usage}%" "warning"
  fi

  if [ "$disk_usage" -gt 90 ]; then
    send_alert "High disk usage: ${disk_usage}%" "warning"
  fi
}

# Function to display status
display_status() {
  local status=$1
  local latency=$2
  local uptime=$3

  clear
  echo "╔═══════════════════════════════════════════════════════╗"
  echo "║       WebSocket Connection Monitor                    ║"
  echo "╚═══════════════════════════════════════════════════════╝"
  echo ""
  echo "  URL: $WS_URL"
  echo "  Interval: ${INTERVAL}s"
  echo "  Uptime: ${uptime}s"
  echo ""

  if [ "$status" == "OK" ]; then
    echo -e "  Status: ${GREEN}✓ Connected${NC}"
    echo "  Latency: ${latency}ms"
    echo "  Consecutive Failures: 0"
  else
    echo -e "  Status: ${RED}✗ Disconnected${NC}"
    echo "  Consecutive Failures: $CONSECUTIVE_FAILURES"
  fi

  echo ""
  echo "  Press Ctrl+C to stop monitoring"
  echo ""
  echo "Recent Log Entries:"
  echo "---------------------------------------------------"
  tail -10 "$LOG_FILE" | sed 's/^/  /'
  echo ""
}

# Function to cleanup on exit
cleanup() {
  log_message "INFO" "Monitor stopped"
  echo -e "\n${YELLOW}Monitoring stopped${NC}"
  exit 0
}

# Trap SIGINT and SIGTERM
trap cleanup SIGINT SIGTERM

# Main monitoring loop
main() {
  log_message "INFO" "Starting WebSocket monitor for $WS_URL (interval: ${INTERVAL}s)"

  # Check if wscat is installed
  if ! command -v wscat >/dev/null 2>&1; then
    log_message "ERROR" "wscat not found. Installing..."
    npm install -g wscat || {
      log_message "ERROR" "Failed to install wscat"
      exit 1
    }
  fi

  local start_time=$(date +%s)
  local check_count=0

  while true; do
    check_count=$((check_count + 1))
    local current_time=$(date +%s)
    local uptime=$((current_time - start_time))

    log_message "INFO" "Check #${check_count}: Testing connection..."

    # Get connection metrics
    local latency
    if latency=$(get_metrics); then
      # Connection successful
      log_message "INFO" "Connection OK (latency: ${latency}ms)"
      display_status "OK" "$latency" "$uptime"

      # Reset failure counter
      if [ $CONSECUTIVE_FAILURES -gt 0 ]; then
        send_alert "WebSocket connection recovered after $CONSECUTIVE_FAILURES failures" "info"
        CONSECUTIVE_FAILURES=0
      fi
    else
      # Connection failed
      CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
      log_message "ERROR" "Connection FAILED (attempt $CONSECUTIVE_FAILURES/$MAX_CONSECUTIVE_FAILURES)"
      display_status "FAILED" "-1" "$uptime"

      # Send alert on consecutive failures
      if [ $CONSECUTIVE_FAILURES -ge $MAX_CONSECUTIVE_FAILURES ]; then
        send_alert "WebSocket connection failed $CONSECUTIVE_FAILURES consecutive times" "critical"

        # Check system resources on persistent failures
        check_system_resources
      elif [ $CONSECUTIVE_FAILURES -eq 1 ]; then
        send_alert "WebSocket connection failed" "warning"
      fi
    fi

    # Sleep until next check
    sleep "$INTERVAL"
  done
}

# Start monitoring
echo "Starting WebSocket monitor..."
echo "URL: $WS_URL"
echo "Interval: ${INTERVAL}s"
echo "Log file: $LOG_FILE"
[ -n "$ALERT_WEBHOOK" ] && echo "Alert webhook: $ALERT_WEBHOOK"
echo ""

main
