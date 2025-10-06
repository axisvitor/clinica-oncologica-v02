#!/bin/bash
# Linux/macOS script to run Wave 2 Phase 2 endpoint tests

echo "==================================="
echo "Wave 2 Phase 2 Endpoint Test Suite"
echo "==================================="
echo ""

# Check if pytest is available
if ! python3 -m pytest --version &> /dev/null; then
    echo "ERROR: pytest not found. Installing..."
    python3 -m pip install pytest pytest-cov pytest-asyncio
fi

echo "Running Admin System Stats tests..."
python3 -m pytest tests/routes/test_admin_stats.py -v

echo ""
echo "Running Analytics Treatment Distribution tests..."
python3 -m pytest tests/routes/test_analytics_treatment.py -v

echo ""
echo "Running Physician Risk Assessments tests..."
python3 -m pytest tests/routes/test_physician_risk.py -v

echo ""
echo "Running Medico Dashboard Stats tests..."
python3 -m pytest tests/routes/test_medico_stats.py -v

echo ""
echo "==================================="
echo "Running ALL tests with coverage..."
echo "==================================="
python3 -m pytest \
    tests/routes/test_admin_stats.py \
    tests/routes/test_analytics_treatment.py \
    tests/routes/test_physician_risk.py \
    tests/routes/test_medico_stats.py \
    --cov=app \
    --cov-report=html \
    --cov-report=term

echo ""
echo "==================================="
echo "Tests complete! Check htmlcov/index.html for coverage report"
echo "==================================="
