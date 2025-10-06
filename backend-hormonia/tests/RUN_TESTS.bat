@echo off
REM Windows batch script to run Wave 2 Phase 2 endpoint tests

echo ===================================
echo Wave 2 Phase 2 Endpoint Test Suite
echo ===================================
echo.

REM Check if pytest is available
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pytest not found. Installing...
    python -m pip install pytest pytest-cov pytest-asyncio
)

echo Running Admin System Stats tests...
python -m pytest tests\routes\test_admin_stats.py -v

echo.
echo Running Analytics Treatment Distribution tests...
python -m pytest tests\routes\test_analytics_treatment.py -v

echo.
echo Running Physician Risk Assessments tests...
python -m pytest tests\routes\test_physician_risk.py -v

echo.
echo Running Medico Dashboard Stats tests...
python -m pytest tests\routes\test_medico_stats.py -v

echo.
echo ===================================
echo Running ALL tests with coverage...
echo ===================================
python -m pytest tests\routes\test_admin_stats.py tests\routes\test_analytics_treatment.py tests\routes\test_physician_risk.py tests\routes\test_medico_stats.py --cov=app --cov-report=html --cov-report=term

echo.
echo ===================================
echo Tests complete! Check htmlcov\index.html for coverage report
echo ===================================

pause
