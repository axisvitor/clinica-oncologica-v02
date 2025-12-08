#!/bin/bash
###############################################################################
# WebSocket Test Report Generator
# Generates comprehensive HTML and JSON reports from test results
#
# Usage:
#   ./generate-ws-report.sh [report-dir] [output-format]
#   ./generate-ws-report.sh reports/websocket html
###############################################################################

set -e

# Configuration
REPORT_DIR="${1:-$(dirname "$0")/../reports/websocket}"
OUTPUT_FORMAT="${2:-html}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="$REPORT_DIR/websocket-test-report.${OUTPUT_FORMAT}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "Generating WebSocket test report..."
echo "Report Directory: $REPORT_DIR"
echo "Output Format: $OUTPUT_FORMAT"
echo ""

# Create report directory if it doesn't exist
mkdir -p "$REPORT_DIR"

# Function to extract test results from log files
extract_results() {
  local total_tests=0
  local passed_tests=0
  local failed_tests=0

  # Find latest Node.js test log
  local nodejs_log=$(ls -t "$REPORT_DIR"/nodejs_*.log 2>/dev/null | head -1)

  if [ -n "$nodejs_log" ]; then
    # Extract test statistics
    passed_tests=$(grep -c "✓ PASSED" "$nodejs_log" || echo "0")
    failed_tests=$(grep -c "✗ FAILED" "$nodejs_log" || echo "0")
    total_tests=$((passed_tests + failed_tests))
  fi

  echo "$total_tests,$passed_tests,$failed_tests"
}

# Function to generate HTML report
generate_html_report() {
  local results=$(extract_results)
  IFS=',' read -r total passed failed <<< "$results"

  local success_rate=0
  if [ "$total" -gt 0 ]; then
    success_rate=$(awk "BEGIN {printf \"%.2f\", ($passed / $total) * 100}")
  fi

  local status_class="success"
  local status_text="All Tests Passed"
  if [ "$failed" -gt 0 ]; then
    status_class="failure"
    status_text="Some Tests Failed"
  fi

  cat > "$OUTPUT_FILE" <<EOF
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WebSocket Test Report</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      padding: 20px;
      min-height: 100vh;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      background: white;
      border-radius: 10px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
      overflow: hidden;
    }
    .header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 30px;
      text-align: center;
    }
    .header h1 { font-size: 2.5em; margin-bottom: 10px; }
    .header .timestamp { opacity: 0.9; font-size: 0.9em; }
    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 20px;
      padding: 30px;
      background: #f8f9fa;
    }
    .metric {
      background: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      text-align: center;
    }
    .metric .value {
      font-size: 2.5em;
      font-weight: bold;
      margin: 10px 0;
    }
    .metric .label {
      color: #666;
      font-size: 0.9em;
      text-transform: uppercase;
      letter-spacing: 1px;
    }
    .metric.success .value { color: #28a745; }
    .metric.failure .value { color: #dc3545; }
    .metric.total .value { color: #007bff; }
    .metric.rate .value { color: #17a2b8; }
    .status-badge {
      display: inline-block;
      padding: 10px 20px;
      border-radius: 20px;
      font-weight: bold;
      margin: 20px 0;
    }
    .status-badge.success { background: #d4edda; color: #155724; }
    .status-badge.failure { background: #f8d7da; color: #721c24; }
    .details {
      padding: 30px;
    }
    .test-section {
      margin-bottom: 30px;
    }
    .test-section h2 {
      color: #333;
      border-bottom: 2px solid #667eea;
      padding-bottom: 10px;
      margin-bottom: 20px;
    }
    .test-item {
      display: flex;
      align-items: center;
      padding: 15px;
      margin-bottom: 10px;
      border-radius: 5px;
      background: #f8f9fa;
    }
    .test-item.passed { border-left: 4px solid #28a745; }
    .test-item.failed { border-left: 4px solid #dc3545; }
    .test-icon {
      font-size: 1.5em;
      margin-right: 15px;
      min-width: 30px;
      text-align: center;
    }
    .test-icon.passed { color: #28a745; }
    .test-icon.failed { color: #dc3545; }
    .test-name { flex-grow: 1; font-weight: 500; }
    .test-error {
      color: #721c24;
      font-size: 0.9em;
      margin-top: 5px;
      padding: 10px;
      background: #f8d7da;
      border-radius: 3px;
    }
    .logs-section {
      background: #f8f9fa;
      padding: 20px;
      border-radius: 5px;
      margin-top: 20px;
    }
    .log-link {
      display: inline-block;
      padding: 10px 20px;
      background: #667eea;
      color: white;
      text-decoration: none;
      border-radius: 5px;
      margin-right: 10px;
      margin-bottom: 10px;
    }
    .log-link:hover { background: #5568d3; }
    .footer {
      text-align: center;
      padding: 20px;
      color: #666;
      border-top: 1px solid #e0e0e0;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🔌 WebSocket Test Report</h1>
      <div class="timestamp">Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')</div>
      <div class="status-badge $status_class">$status_text</div>
    </div>

    <div class="summary">
      <div class="metric total">
        <div class="label">Total Tests</div>
        <div class="value">$total</div>
      </div>
      <div class="metric success">
        <div class="label">Passed</div>
        <div class="value">$passed</div>
      </div>
      <div class="metric failure">
        <div class="label">Failed</div>
        <div class="value">$failed</div>
      </div>
      <div class="metric rate">
        <div class="label">Success Rate</div>
        <div class="value">${success_rate}%</div>
      </div>
    </div>

    <div class="details">
      <div class="test-section">
        <h2>Test Results</h2>
EOF

  # Add individual test results
  local nodejs_log=$(ls -t "$REPORT_DIR"/nodejs_*.log 2>/dev/null | head -1)
  if [ -n "$nodejs_log" ]; then
    grep -E "^\[TEST\]|✓ PASSED|✗ FAILED" "$nodejs_log" | while read -r line; do
      if [[ $line =~ ^\[TEST\]\ (.+)\.\.\. ]]; then
        test_name="${BASH_REMATCH[1]}"
        echo "<div class=\"test-item\">" >> "$OUTPUT_FILE"
      elif [[ $line =~ ✓\ PASSED ]]; then
        echo "<div class=\"test-icon passed\">✓</div>" >> "$OUTPUT_FILE"
        echo "<div class=\"test-name\">$test_name</div>" >> "$OUTPUT_FILE"
        echo "</div>" >> "$OUTPUT_FILE"
      elif [[ $line =~ ✗\ FAILED:\ (.+) ]]; then
        error="${BASH_REMATCH[1]}"
        echo "<div class=\"test-icon failed\">✗</div>" >> "$OUTPUT_FILE"
        echo "<div class=\"test-name\">$test_name<div class=\"test-error\">$error</div></div>" >> "$OUTPUT_FILE"
        echo "</div>" >> "$OUTPUT_FILE"
      fi
    done
  fi

  cat >> "$OUTPUT_FILE" <<EOF
      </div>

      <div class="logs-section">
        <h3>Log Files</h3>
EOF

  # Add links to log files
  for log in "$REPORT_DIR"/*.log; do
    if [ -f "$log" ]; then
      basename_log=$(basename "$log")
      echo "<a href=\"$basename_log\" class=\"log-link\">📄 $basename_log</a>" >> "$OUTPUT_FILE"
    fi
  done

  cat >> "$OUTPUT_FILE" <<EOF
      </div>
    </div>

    <div class="footer">
      <p>WebSocket Connection Test Suite v1.0</p>
      <p>© $(date +%Y) - Automated Testing Infrastructure</p>
    </div>
  </div>
</body>
</html>
EOF

  echo -e "${GREEN}✓ HTML report generated: $OUTPUT_FILE${NC}"
}

# Function to generate JSON report
generate_json_report() {
  local results=$(extract_results)
  IFS=',' read -r total passed failed <<< "$results"

  local success_rate=0
  if [ "$total" -gt 0 ]; then
    success_rate=$(awk "BEGIN {printf \"%.2f\", ($passed / $total) * 100}")
  fi

  cat > "$OUTPUT_FILE" <<EOF
{
  "generated": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "summary": {
    "total": $total,
    "passed": $passed,
    "failed": $failed,
    "successRate": $success_rate
  },
  "tests": [
EOF

  # Extract individual test results
  local nodejs_log=$(ls -t "$REPORT_DIR"/nodejs_*.log 2>/dev/null | head -1)
  if [ -n "$nodejs_log" ]; then
    local first=true
    grep -E "^\[TEST\]|✓ PASSED|✗ FAILED" "$nodejs_log" | while read -r line; do
      if [[ $line =~ ^\[TEST\]\ (.+)\.\.\. ]]; then
        test_name="${BASH_REMATCH[1]}"
      elif [[ $line =~ ✓\ PASSED ]]; then
        [ "$first" = false ] && echo "," >> "$OUTPUT_FILE"
        echo "    {\"name\": \"$test_name\", \"status\": \"passed\"}" >> "$OUTPUT_FILE"
        first=false
      elif [[ $line =~ ✗\ FAILED:\ (.+) ]]; then
        error="${BASH_REMATCH[1]}"
        [ "$first" = false ] && echo "," >> "$OUTPUT_FILE"
        echo "    {\"name\": \"$test_name\", \"status\": \"failed\", \"error\": \"$error\"}" >> "$OUTPUT_FILE"
        first=false
      fi
    done
  fi

  cat >> "$OUTPUT_FILE" <<EOF

  ],
  "logs": [
EOF

  # Add log file references
  local first=true
  for log in "$REPORT_DIR"/*.log; do
    if [ -f "$log" ]; then
      [ "$first" = false ] && echo "," >> "$OUTPUT_FILE"
      echo "    \"$(basename "$log")\"" >> "$OUTPUT_FILE"
      first=false
    fi
  done

  cat >> "$OUTPUT_FILE" <<EOF

  ]
}
EOF

  echo -e "${GREEN}✓ JSON report generated: $OUTPUT_FILE${NC}"
}

# Generate report based on format
case "$OUTPUT_FORMAT" in
  html)
    generate_html_report
    ;;
  json)
    generate_json_report
    ;;
  *)
    echo -e "${RED}✗ Unsupported format: $OUTPUT_FORMAT${NC}"
    echo "Supported formats: html, json"
    exit 1
    ;;
esac

echo ""
echo "Report generation complete!"
