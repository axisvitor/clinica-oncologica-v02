#!/bin/bash

# Frontend-v2 E2E Test Execution Script
#
# This script provides comprehensive end-to-end test execution for the Frontend-v2 application.
# It includes setup, execution, and reporting functionality with support for different environments.

set -e  # Exit on any error

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="$PROJECT_DIR/test-results/logs"
REPORT_DIR="$PROJECT_DIR/test-results/e2e-report"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_TIMEOUT=300
DEFAULT_WORKERS=4
DEFAULT_RETRIES=2

# Create required directories
mkdir -p "$LOG_DIR"
mkdir -p "$REPORT_DIR"

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_DIR/e2e_tests_$TIMESTAMP.log"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$LOG_DIR/e2e_tests_$TIMESTAMP.log"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}" | tee -a "$LOG_DIR/e2e_tests_$TIMESTAMP.log"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a "$LOG_DIR/e2e_tests_$TIMESTAMP.log"
}

# Help function
show_help() {
    echo "Frontend-v2 E2E Test Runner"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -e, --env ENV           Set environment (local, staging, production)"
    echo "  -t, --timeout SECONDS   Test timeout in seconds (default: $DEFAULT_TIMEOUT)"
    echo "  -w, --workers NUM       Number of parallel workers (default: $DEFAULT_WORKERS)"
    echo "  -r, --retries NUM       Number of retries for failed tests (default: $DEFAULT_RETRIES)"
    echo "  -p, --project PROJECT   Run specific project only (chrome, firefox, mobile, etc.)"
    echo "  -s, --spec PATTERN      Run tests matching pattern"
    echo "  -d, --debug             Run in debug mode (headed browser)"
    echo "  -u, --ui                Run with Playwright UI"
    echo "  -c, --check             Only check test setup without running tests"
    echo "  -v, --verbose           Verbose output"
    echo "  --headed                Run tests in headed mode"
    echo "  --trace                 Enable trace collection"
    echo "  --video                 Enable video recording"
    echo "  --screenshot            Enable screenshot on failure"
    echo "  --skip-build            Skip building the application"
    echo "  --skip-install          Skip installing dependencies"
    echo "  --report-only           Only generate and show report"
    echo ""
    echo "Examples:"
    echo "  $0                      # Run all tests"
    echo "  $0 --env staging        # Run tests against staging environment"
    echo "  $0 --project chrome     # Run only Chrome tests"
    echo "  $0 --spec smoke         # Run only smoke tests"
    echo "  $0 --debug              # Run in debug mode"
    echo "  $0 --ui                 # Run with Playwright UI"
    echo ""
}

# Parse command line arguments
ENVIRONMENT="local"
TIMEOUT=$DEFAULT_TIMEOUT
WORKERS=$DEFAULT_WORKERS
RETRIES=$DEFAULT_RETRIES
PROJECT=""
SPEC_PATTERN=""
DEBUG_MODE=false
UI_MODE=false
CHECK_ONLY=false
VERBOSE=false
HEADED=false
TRACE=false
VIDEO=false
SCREENSHOT=false
SKIP_BUILD=false
SKIP_INSTALL=false
REPORT_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -w|--workers)
            WORKERS="$2"
            shift 2
            ;;
        -r|--retries)
            RETRIES="$2"
            shift 2
            ;;
        -p|--project)
            PROJECT="$2"
            shift 2
            ;;
        -s|--spec)
            SPEC_PATTERN="$2"
            shift 2
            ;;
        -d|--debug)
            DEBUG_MODE=true
            shift
            ;;
        -u|--ui)
            UI_MODE=true
            shift
            ;;
        -c|--check)
            CHECK_ONLY=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --headed)
            HEADED=true
            shift
            ;;
        --trace)
            TRACE=true
            shift
            ;;
        --video)
            VIDEO=true
            shift
            ;;
        --screenshot)
            SCREENSHOT=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --skip-install)
            SKIP_INSTALL=true
            shift
            ;;
        --report-only)
            REPORT_ONLY=true
            shift
            ;;
        *)
            error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Change to project directory
cd "$PROJECT_DIR"

# Environment-specific configuration
setup_environment() {
    log "Setting up environment: $ENVIRONMENT"

    case $ENVIRONMENT in
        "local")
            export PLAYWRIGHT_TEST_BASE_URL="http://localhost:4173"
            export VITE_API_URL="http://localhost:8000"
            export VITE_ENVIRONMENT="test"
            ;;
        "staging")
            export PLAYWRIGHT_TEST_BASE_URL="${STAGING_URL:-https://staging.exemplo.com}"
            export VITE_API_URL="${STAGING_API_URL:-https://api-staging.exemplo.com}"
            export VITE_ENVIRONMENT="staging"
            ;;
        "production")
            export PLAYWRIGHT_TEST_BASE_URL="${PRODUCTION_URL:-https://exemplo.com}"
            export VITE_API_URL="${PRODUCTION_API_URL:-https://api.exemplo.com}"
            export VITE_ENVIRONMENT="production"
            warning "Running tests against PRODUCTION environment!"
            read -p "Are you sure you want to continue? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                error "Aborted by user"
                exit 1
            fi
            ;;
        *)
            error "Unknown environment: $ENVIRONMENT"
            exit 1
            ;;
    esac

    # Set test-specific environment variables
    export NODE_ENV="test"
    export VITE_DEBUG_MODE="true"
    export TEST_TIMESTAMP="$TIMESTAMP"

    # Feature flags for testing
    export VITE_AI_CHAT_ENABLED="${VITE_AI_CHAT_ENABLED:-true}"
    export VITE_AI_ANALYTICS_ENABLED="${VITE_AI_ANALYTICS_ENABLED:-true}"
    export VITE_AI_INSIGHTS_ENABLED="${VITE_AI_INSIGHTS_ENABLED:-true}"
    export VITE_AI_RECOMMENDATIONS_ENABLED="${VITE_AI_RECOMMENDATIONS_ENABLED:-false}"

    log "Base URL: $PLAYWRIGHT_TEST_BASE_URL"
    log "API URL: $VITE_API_URL"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check Node.js version
    if ! command -v node &> /dev/null; then
        error "Node.js is not installed"
        return 1
    fi

    NODE_VERSION=$(node -v)
    log "Node.js version: $NODE_VERSION"

    # Check npm
    if ! command -v npm &> /dev/null; then
        error "npm is not installed"
        return 1
    fi

    NPM_VERSION=$(npm -v)
    log "npm version: $NPM_VERSION"

    # Check if package.json exists
    if [[ ! -f "package.json" ]]; then
        error "package.json not found. Are you in the correct directory?"
        return 1
    fi

    # Check Playwright installation
    if [[ ! -f "node_modules/@playwright/test/package.json" && "$SKIP_INSTALL" != true ]]; then
        warning "Playwright not found, will install dependencies"
    fi

    success "Prerequisites check completed"
    return 0
}

# Install dependencies
install_dependencies() {
    if [[ "$SKIP_INSTALL" == true ]]; then
        log "Skipping dependency installation"
        return 0
    fi

    log "Installing dependencies..."

    if [[ -f "package-lock.json" ]]; then
        npm ci --silent
    else
        npm install --silent
    fi

    # Install Playwright browsers if needed
    log "Installing Playwright browsers..."
    npx playwright install --with-deps

    success "Dependencies installed"
}

# Build application
build_application() {
    if [[ "$SKIP_BUILD" == true ]]; then
        log "Skipping application build"
        return 0
    fi

    log "Building application..."

    # Run type checking first
    log "Running type checking..."
    npm run typecheck

    # Build the application
    log "Building for testing..."
    npm run build

    success "Application built successfully"
}

# Health check
health_check() {
    log "Performing health check..."

    # Check if server is responsive
    local max_attempts=30
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s "$PLAYWRIGHT_TEST_BASE_URL" > /dev/null 2>&1; then
            success "Server is responsive"
            return 0
        fi

        log "Attempt $attempt/$max_attempts: Server not ready, waiting..."
        sleep 2
        ((attempt++))
    done

    error "Server health check failed after $max_attempts attempts"
    return 1
}

# Build Playwright command
build_playwright_command() {
    local cmd="npx playwright test"

    # Add project filter
    if [[ -n "$PROJECT" ]]; then
        cmd="$cmd --project=$PROJECT"
    fi

    # Add spec pattern
    if [[ -n "$SPEC_PATTERN" ]]; then
        cmd="$cmd $SPEC_PATTERN"
    fi

    # Add workers
    cmd="$cmd --workers=$WORKERS"

    # Add retries
    cmd="$cmd --retries=$RETRIES"

    # Add timeout
    cmd="$cmd --timeout=$((TIMEOUT * 1000))"

    # Debug mode
    if [[ "$DEBUG_MODE" == true ]]; then
        cmd="$cmd --debug"
    fi

    # UI mode
    if [[ "$UI_MODE" == true ]]; then
        cmd="$cmd --ui"
    fi

    # Headed mode
    if [[ "$HEADED" == true ]]; then
        cmd="$cmd --headed"
    fi

    # Trace
    if [[ "$TRACE" == true ]]; then
        cmd="$cmd --trace=on"
    fi

    # Video
    if [[ "$VIDEO" == true ]]; then
        cmd="$cmd --video=on"
    fi

    # Screenshot
    if [[ "$SCREENSHOT" == true ]]; then
        cmd="$cmd --screenshot=only-on-failure"
    fi

    # Verbose
    if [[ "$VERBOSE" == true ]]; then
        cmd="$cmd --verbose"
    fi

    echo "$cmd"
}

# Run tests
run_tests() {
    log "Starting E2E test execution..."

    local playwright_cmd
    playwright_cmd=$(build_playwright_command)

    log "Playwright command: $playwright_cmd"

    # Export environment variables for Playwright
    export PLAYWRIGHT_SKIP_BUILD="$SKIP_BUILD"

    # Run the tests
    if eval "$playwright_cmd"; then
        success "All tests passed!"
        return 0
    else
        local exit_code=$?
        error "Some tests failed (exit code: $exit_code)"
        return $exit_code
    fi
}

# Generate and show report
show_report() {
    log "Generating test report..."

    # Show Playwright HTML report
    if [[ -d "$REPORT_DIR" && -f "$REPORT_DIR/index.html" ]]; then
        log "Opening test report..."
        if [[ "$CI" != "true" ]]; then
            npx playwright show-report "$REPORT_DIR" || true
        else
            log "Report available at: file://$REPORT_DIR/index.html"
        fi
    else
        warning "No test report found"
    fi

    # Show summary from JSON results if available
    local json_results="$PROJECT_DIR/test-results/e2e-results.json"
    if [[ -f "$json_results" ]] && command -v jq &> /dev/null; then
        log "Test summary:"
        jq -r '.suites[] | select(.title != "") | "  \(.title): \(.tests | length) tests, \([.tests[] | select(.results[].status == "passed")] | length) passed, \([.tests[] | select(.results[].status == "failed")] | length) failed"' "$json_results" || true
    fi
}

# Cleanup function
cleanup() {
    log "Performing cleanup..."

    # Kill any remaining processes
    if [[ -n "${SERVER_PID:-}" ]]; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi

    # Archive old test results
    if [[ -d "test-results" ]]; then
        local archive_dir="test-results/archive/$TIMESTAMP"
        mkdir -p "$archive_dir"

        # Move results but keep the latest report
        find test-results -name "*.json" -o -name "*.xml" -o -name "*.log" | while read -r file; do
            if [[ "$file" != *"/e2e-report/"* ]]; then
                mkdir -p "$archive_dir/$(dirname "${file#test-results/}")"
                mv "$file" "$archive_dir/${file#test-results/}"
            fi
        done 2>/dev/null || true
    fi

    log "Cleanup completed"
}

# Main execution flow
main() {
    log "Starting Frontend-v2 E2E Test Runner"
    log "Timestamp: $TIMESTAMP"
    log "Environment: $ENVIRONMENT"
    log "Project directory: $PROJECT_DIR"

    # Handle report-only mode
    if [[ "$REPORT_ONLY" == true ]]; then
        show_report
        exit 0
    fi

    # Trap cleanup on exit
    trap cleanup EXIT

    # Setup environment
    setup_environment

    # Check prerequisites
    if ! check_prerequisites; then
        error "Prerequisites check failed"
        exit 1
    fi

    # Check-only mode
    if [[ "$CHECK_ONLY" == true ]]; then
        success "Setup check completed successfully"
        exit 0
    fi

    # Install dependencies
    install_dependencies

    # Build application
    build_application

    # For local environment, perform health check
    if [[ "$ENVIRONMENT" == "local" ]]; then
        # Start server in background if not running
        if ! curl -f -s "$PLAYWRIGHT_TEST_BASE_URL" > /dev/null 2>&1; then
            log "Starting development server..."
            npm run preview > "$LOG_DIR/server_$TIMESTAMP.log" 2>&1 &
            SERVER_PID=$!
            log "Server PID: $SERVER_PID"

            # Wait for server to start
            sleep 5
        fi

        # Health check
        if ! health_check; then
            error "Health check failed"
            exit 1
        fi
    fi

    # Run tests
    local test_exit_code=0
    run_tests || test_exit_code=$?

    # Show report
    show_report

    # Final status
    if [[ $test_exit_code -eq 0 ]]; then
        success "E2E test execution completed successfully!"
    else
        error "E2E test execution completed with failures (exit code: $test_exit_code)"
    fi

    exit $test_exit_code
}

# Execute main function
main "$@"