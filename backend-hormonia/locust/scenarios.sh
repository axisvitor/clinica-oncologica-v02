#!/bin/bash
# Load Testing Scenarios for Backend Hormonia
#
# This script runs various load testing scenarios using Locust
# to validate system performance under different conditions.
#
# Usage:
#   ./scenarios.sh [scenario]
#
# Available scenarios:
#   smoke    - Quick validation (10 users, 1 min)
#   load     - Normal load (100 users, 5 min)
#   stress   - High load (500 users, 10 min)
#   spike    - Sudden traffic spike (1000 users, 3 min)
#   soak     - Endurance test (50 users, 30 min)
#   all      - Run all scenarios sequentially

set -e

# Configuration
HOST="${LOCUST_HOST:-http://localhost:8000}"
REPORTS_DIR="reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create reports directory
mkdir -p "$REPORTS_DIR"

# Helper function to print colored messages
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Locust is installed
check_locust() {
    if ! command -v locust &> /dev/null; then
        log_error "Locust is not installed"
        echo "Install with: pip install locust"
        exit 1
    fi
    log_success "Locust is installed"
}

# Check if backend is running
check_backend() {
    log_info "Checking if backend is running at $HOST..."

    if curl -s -f "$HOST/api/v2/health" > /dev/null; then
        log_success "Backend is running"
    else
        log_error "Backend is not responding at $HOST"
        echo "Start the backend with: docker-compose up -d"
        exit 1
    fi
}

# Smoke Test - Quick validation
run_smoke_test() {
    log_info "🔥 Running Smoke Test (10 users, 1 minute)"

    locust -f locustfile.py \
        --host="$HOST" \
        --headless \
        -u 10 \
        -r 2 \
        --run-time 1m \
        --html "$REPORTS_DIR/smoke_${TIMESTAMP}.html" \
        --csv "$REPORTS_DIR/smoke_${TIMESTAMP}"

    log_success "Smoke test completed"
}

# Load Test - Normal operational load
run_load_test() {
    log_info "📊 Running Load Test (100 users, 5 minutes)"

    locust -f locustfile.py \
        --host="$HOST" \
        --headless \
        -u 100 \
        -r 10 \
        --run-time 5m \
        --html "$REPORTS_DIR/load_${TIMESTAMP}.html" \
        --csv "$REPORTS_DIR/load_${TIMESTAMP}"

    log_success "Load test completed"
}

# Stress Test - High load
run_stress_test() {
    log_info "💪 Running Stress Test (500 users, 10 minutes)"

    locust -f locustfile.py \
        --host="$HOST" \
        --headless \
        -u 500 \
        -r 50 \
        --run-time 10m \
        --html "$REPORTS_DIR/stress_${TIMESTAMP}.html" \
        --csv "$REPORTS_DIR/stress_${TIMESTAMP}"

    log_success "Stress test completed"
}

# Spike Test - Sudden traffic spike
run_spike_test() {
    log_info "⚡ Running Spike Test (1000 users, 3 minutes)"

    locust -f locustfile.py \
        --host="$HOST" \
        --headless \
        -u 1000 \
        -r 100 \
        --run-time 3m \
        --html "$REPORTS_DIR/spike_${TIMESTAMP}.html" \
        --csv "$REPORTS_DIR/spike_${TIMESTAMP}"

    log_success "Spike test completed"
}

# Soak Test - Endurance test
run_soak_test() {
    log_info "🏃 Running Soak Test (50 users, 30 minutes)"
    log_warning "This test will run for 30 minutes..."

    locust -f locustfile.py \
        --host="$HOST" \
        --headless \
        -u 50 \
        -r 5 \
        --run-time 30m \
        --html "$REPORTS_DIR/soak_${TIMESTAMP}.html" \
        --csv "$REPORTS_DIR/soak_${TIMESTAMP}"

    log_success "Soak test completed"
}

# Interactive mode - Launch Locust web UI
run_interactive() {
    log_info "🌐 Launching Locust Web UI"
    log_info "Access at: http://localhost:8089"

    locust -f locustfile.py --host="$HOST"
}

# Generate summary report
generate_summary() {
    log_info "📋 Generating summary report..."

    SUMMARY_FILE="$REPORTS_DIR/summary_${TIMESTAMP}.txt"

    cat > "$SUMMARY_FILE" << EOF
# Load Test Summary
Generated: $(date)
Host: $HOST

## Test Results

EOF

    # Add results from CSV files
    for csv in "$REPORTS_DIR"/*_stats.csv; do
        if [ -f "$csv" ]; then
            echo "### $(basename "$csv" _stats.csv)" >> "$SUMMARY_FILE"
            head -20 "$csv" >> "$SUMMARY_FILE"
            echo "" >> "$SUMMARY_FILE"
        fi
    done

    log_success "Summary saved to $SUMMARY_FILE"
}

# Main execution
main() {
    check_locust
    check_backend

    SCENARIO="${1:-smoke}"

    case "$SCENARIO" in
        smoke)
            run_smoke_test
            ;;
        load)
            run_load_test
            ;;
        stress)
            run_stress_test
            ;;
        spike)
            run_spike_test
            ;;
        soak)
            run_soak_test
            ;;
        interactive|web)
            run_interactive
            ;;
        all)
            log_info "🚀 Running all test scenarios..."
            run_smoke_test
            sleep 5
            run_load_test
            sleep 10
            run_stress_test
            sleep 10
            run_spike_test
            generate_summary
            log_success "All tests completed!"
            ;;
        *)
            log_error "Unknown scenario: $SCENARIO"
            echo ""
            echo "Usage: $0 [scenario]"
            echo ""
            echo "Available scenarios:"
            echo "  smoke       - Quick validation (10 users, 1 min)"
            echo "  load        - Normal load (100 users, 5 min)"
            echo "  stress      - High load (500 users, 10 min)"
            echo "  spike       - Sudden spike (1000 users, 3 min)"
            echo "  soak        - Endurance (50 users, 30 min)"
            echo "  interactive - Launch web UI"
            echo "  all         - Run all scenarios"
            exit 1
            ;;
    esac

    log_success "Test scenario '$SCENARIO' completed!"
    log_info "Reports saved to: $REPORTS_DIR/"
}

# Run main function
main "$@"
