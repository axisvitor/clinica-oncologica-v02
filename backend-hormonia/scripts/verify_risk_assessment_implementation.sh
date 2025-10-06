#!/bin/bash
#
# Verification Script: Physician Risk Assessment Implementation
#
# This script verifies that all files are correctly created and configured
# for the new GET /api/v1/physician/risk-assessments endpoint.
#
# Usage: bash scripts/verify_risk_assessment_implementation.sh
#

set -e  # Exit on error

echo "=================================================="
echo "Physician Risk Assessment Implementation Verification"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} File exists: $1"
        return 0
    else
        echo -e "${RED}✗${NC} File missing: $1"
        return 1
    fi
}

check_content() {
    if grep -q "$2" "$1" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Content found in $1: '$2'"
        return 0
    else
        echo -e "${RED}✗${NC} Content missing in $1: '$2'"
        return 1
    fi
}

echo "1. Checking Core Implementation Files"
echo "--------------------------------------"
check_file "app/models/physician.py"
check_file "app/services/risk_assessment_service.py"
check_file "app/api/v1/physician.py"
check_file "alembic/versions/20251006_add_risk_assessment_indexes.py"
echo ""

echo "2. Checking Test Files"
echo "----------------------"
check_file "tests/test_risk_assessment_endpoint.py"
echo ""

echo "3. Checking Documentation"
echo "------------------------"
check_file "docs/api/PHYSICIAN_RISK_ASSESSMENT_ENDPOINT.md"
check_file "docs/IMPLEMENTATION_PHYSICIAN_RISK_ASSESSMENT.md"
echo ""

echo "4. Checking Configuration Files"
echo "-------------------------------"
check_content "app/models/__init__.py" "from app.models.physician import"
check_content "app/core/router_registry.py" "physician"
echo ""

echo "5. Verifying Model Exports"
echo "-------------------------"
check_content "app/models/__init__.py" "RiskAssessment"
check_content "app/models/__init__.py" "PatientRiskProfile"
check_content "app/models/__init__.py" "RiskAssessmentsResponse"
check_content "app/models/__init__.py" "AlertStatus"
echo ""

echo "6. Verifying Router Registration"
echo "--------------------------------"
check_content "app/core/router_registry.py" "physician.router"
check_content "app/core/router_registry.py" "Physician endpoints registered"
echo ""

echo "7. Checking Database Migration"
echo "------------------------------"
if [ -f "alembic/versions/20251006_add_risk_assessment_indexes.py" ]; then
    echo -e "${GREEN}✓${NC} Migration file exists"

    # Check migration content
    if grep -q "idx_patients_physician_id" "alembic/versions/20251006_add_risk_assessment_indexes.py"; then
        echo -e "${GREEN}✓${NC} Index: idx_patients_physician_id"
    else
        echo -e "${RED}✗${NC} Missing index: idx_patients_physician_id"
    fi

    if grep -q "idx_alerts_patient_status_created" "alembic/versions/20251006_add_risk_assessment_indexes.py"; then
        echo -e "${GREEN}✓${NC} Index: idx_alerts_patient_status_created"
    else
        echo -e "${RED}✗${NC} Missing index: idx_alerts_patient_status_created"
    fi
else
    echo -e "${RED}✗${NC} Migration file not found"
fi
echo ""

echo "8. Python Import Test"
echo "--------------------"
# Test if Python can import the new modules
if command -v python3 &> /dev/null; then
    echo "Testing Python imports..."

    # Test models
    python3 -c "from app.models.physician import RiskAssessment, PatientRiskProfile, RiskAssessmentsResponse" 2>/dev/null && \
        echo -e "${GREEN}✓${NC} Models import successfully" || \
        echo -e "${RED}✗${NC} Models import failed"

    # Test service
    python3 -c "from app.services.risk_assessment_service import RiskAssessmentService" 2>/dev/null && \
        echo -e "${GREEN}✓${NC} Service import successfully" || \
        echo -e "${RED}✗${NC} Service import failed"

    # Test router
    python3 -c "from app.api.v1 import physician" 2>/dev/null && \
        echo -e "${GREEN}✓${NC} Router import successfully" || \
        echo -e "${RED}✗${NC} Router import failed"
else
    echo -e "${YELLOW}⚠${NC} Python3 not found, skipping import tests"
fi
echo ""

echo "9. API Documentation Checks"
echo "--------------------------"
check_content "docs/api/PHYSICIAN_RISK_ASSESSMENT_ENDPOINT.md" "GET /api/v1/physician/risk-assessments"
check_content "docs/api/PHYSICIAN_RISK_ASSESSMENT_ENDPOINT.md" "Performance"
check_content "docs/api/PHYSICIAN_RISK_ASSESSMENT_ENDPOINT.md" "Risk Scoring Algorithm"
echo ""

echo "10. Implementation Summary"
echo "-------------------------"
check_content "docs/IMPLEMENTATION_PHYSICIAN_RISK_ASSESSMENT.md" "Implementation Complete"
check_content "docs/IMPLEMENTATION_PHYSICIAN_RISK_ASSESSMENT.md" "Performance Metrics"
echo ""

echo "=================================================="
echo "Verification Complete!"
echo "=================================================="
echo ""
echo "Next Steps:"
echo "1. Apply migration: alembic upgrade head"
echo "2. Restart backend: uvicorn app.main:app --reload"
echo "3. Test endpoint: curl -H 'Authorization: Bearer \$TOKEN' http://localhost:8000/api/v1/physician/risk-assessments"
echo "4. Run tests: pytest tests/test_risk_assessment_endpoint.py -v"
echo ""
