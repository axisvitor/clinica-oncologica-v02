#!/bin/bash
# Comprehensive Deployment Validation Script
# Runs all validation checks for critical bug fixes deployment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(dirname "$SCRIPT_DIR")"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
SKIP_API_TESTS="${SKIP_API_TESTS:-false}"

echo -e "${BLUE}🚀 Starting Comprehensive Deployment Validation${NC}"
echo -e "   Backend Root: $BACKEND_ROOT"
echo -e "   API Base URL: $API_BASE_URL"
echo -e "   Skip API Tests: $SKIP_API_TESTS"
echo ""

# Function to print section headers
print_section() {
    echo -e "${BLUE}$1${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

# Change to backend directory
cd "$BACKEND_ROOT"

# Validation results
VALIDATION_RESULTS=()
OVERALL_SUCCESS=true

# Function to run validation and track results
run_validation() {
    local name="$1"
    local command="$2"
    local critical="${3:-true}"
    
    print_section "Running $name..."
    
    if eval "$command"; then
        print_success "$name passed"
        VALIDATION_RESULTS+=("✅ $name: PASS")
    else
        if [ "$critical" = "true" ]; then
            print_error "$name failed (CRITICAL)"
            VALIDATION_RESULTS+=("❌ $name: FAIL (CRITICAL)")
            OVERALL_SUCCESS=false
        else
            print_warning "$name failed (NON-CRITICAL)"
            VALIDATION_RESULTS+=("⚠️ $name: FAIL (NON-CRITICAL)")
        fi
    fi
    echo ""
}

# 1. Static Code Validations
print_section "📋 Phase 1: Static Code Validations"

run_validation "Dependency Injection Patterns" \
    "python scripts/validate_dependency_injection.py" \
    true

run_validation "Role Enum Usage" \
    "python scripts/validate_role_enums.py" \
    true

run_validation "Database Model Compatibility" \
    "python scripts/validate_db_models.py" \
    true

run_validation "Date Parameter Handling" \
    "python scripts/validate_date_parameters.py" \
    true

run_validation "Critical Bug Fixes" \
    "python scripts/validate_critical_fixes.py" \
    true

# 2. Environment and Configuration Checks
print_section "⚙️ Phase 2: Environment and Configuration"

run_validation "Python Dependencies" \
    "pip check" \
    false

run_validation "Environment Configuration" \
    "python -c 'from app.core.config import settings; print(\"Config loaded successfully\")'" \
    true

run_validation "Database Migration Status" \
    "alembic current" \
    false

# 3. Import and Module Tests
print_section "📦 Phase 3: Import and Module Tests"

run_validation "Critical Module Imports" \
    "python -c 'import app.main; import app.core.config; import app.models.user; import app.models.alert; print(\"All imports successful\")'" \
    true

run_validation "FastAPI Application Creation" \
    "python -c 'from app.main import app; print(\"FastAPI app created successfully\")'" \
    true

# 4. API Health Checks (if not skipped)
if [ "$SKIP_API_TESTS" != "true" ]; then
    print_section "🏥 Phase 4: API Health Checks"
    
    run_validation "Deployment Health Check" \
        "python scripts/validate_deployment_health.py --base-url $API_BASE_URL" \
        false
    
    run_validation "Comprehensive Deployment Validation" \
        "python scripts/deployment_validation.py --base-url $API_BASE_URL" \
        false
else
    print_warning "Skipping API tests as requested"
fi

# 5. Security and Performance Checks
print_section "🔒 Phase 5: Security and Performance"

run_validation "Security Configuration" \
    "python -c 'from app.core.config import settings; assert settings.SECRET_KEY, \"SECRET_KEY required\"; print(\"Security config OK\")'" \
    true

# Check for common security issues
run_validation "Security Patterns Check" \
    "python -c 'import os; assert not any(\"password\" in k.lower() and \"test\" not in v.lower() for k,v in os.environ.items() if v), \"No hardcoded passwords\"; print(\"Security patterns OK\")'" \
    false

# 6. Database Schema Validation (if possible)
print_section "🗄️ Phase 6: Database Schema Validation"

# Try to connect to database and validate schema
run_validation "Database Connection Test" \
    "python -c 'from app.database.session import get_db; next(get_db()); print(\"Database connection OK\")'" \
    false

# 7. Regression Tests
print_section "🧪 Phase 7: Regression Tests"

if [ -f "tests/test_regression_prevention.py" ]; then
    run_validation "Regression Prevention Tests" \
        "python -m pytest tests/test_regression_prevention.py -v" \
        true
fi

if [ -f "tests/test_dependency_injection_fix.py" ]; then
    run_validation "Dependency Injection Fix Tests" \
        "python -m pytest tests/test_dependency_injection_fix.py -v" \
        true
fi

if [ -f "tests/test_role_enum_fixes.py" ]; then
    run_validation "Role Enum Fix Tests" \
        "python -m pytest tests/test_role_enum_fixes.py -v" \
        true
fi

# 8. Generate Summary Report
print_section "📊 Validation Summary Report"

echo "Validation Results:"
for result in "${VALIDATION_RESULTS[@]}"; do
    echo "  $result"
done

echo ""
if [ "$OVERALL_SUCCESS" = true ]; then
    print_success "🎉 All critical validations passed! Deployment is ready."
    
    # Create success marker file
    echo "$(date): Deployment validation successful" > deployment_validation_success.txt
    
    exit 0
else
    print_error "💥 Critical validations failed! Deployment should not proceed."
    
    # Create failure marker file
    echo "$(date): Deployment validation failed" > deployment_validation_failure.txt
    
    echo ""
    echo "Critical issues must be resolved before deployment:"
    for result in "${VALIDATION_RESULTS[@]}"; do
        if [[ "$result" == *"CRITICAL"* ]]; then
            echo "  $result"
        fi
    done
    
    exit 1
fi