@echo off
REM Comprehensive Deployment Validation Script for Windows
REM Runs all validation checks for critical bug fixes deployment

setlocal enabledelayedexpansion

REM Configuration
set "SCRIPT_DIR=%~dp0"
set "BACKEND_ROOT=%SCRIPT_DIR%.."
set "API_BASE_URL=%API_BASE_URL%"
if "%API_BASE_URL%"=="" set "API_BASE_URL=http://localhost:8000"
set "SKIP_API_TESTS=%SKIP_API_TESTS%"
if "%SKIP_API_TESTS%"=="" set "SKIP_API_TESTS=false"

echo 🚀 Starting Comprehensive Deployment Validation
echo    Backend Root: %BACKEND_ROOT%
echo    API Base URL: %API_BASE_URL%
echo    Skip API Tests: %SKIP_API_TESTS%
echo.

REM Change to backend directory
cd /d "%BACKEND_ROOT%"

REM Validation tracking
set "OVERALL_SUCCESS=true"
set "VALIDATION_COUNT=0"

REM Function to run validation (simulated with labels)
goto :start_validations

:run_validation
set "name=%~1"
set "command=%~2"
set "critical=%~3"
if "%critical%"=="" set "critical=true"

echo Running %name%...
%command% >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ %name% passed
) else (
    if "%critical%"=="true" (
        echo ❌ %name% failed ^(CRITICAL^)
        set "OVERALL_SUCCESS=false"
    ) else (
        echo ⚠️ %name% failed ^(NON-CRITICAL^)
    )
)
echo.
goto :eof

:start_validations

REM 1. Static Code Validations
echo 📋 Phase 1: Static Code Validations

echo Running Dependency Injection Patterns...
python scripts\validate_dependency_injection.py
if %errorlevel% neq 0 (
    echo ❌ Dependency Injection Patterns failed ^(CRITICAL^)
    set "OVERALL_SUCCESS=false"
) else (
    echo ✅ Dependency Injection Patterns passed
)
echo.

echo Running Role Enum Usage...
python scripts\validate_role_enums.py
if %errorlevel% neq 0 (
    echo ❌ Role Enum Usage failed ^(CRITICAL^)
    set "OVERALL_SUCCESS=false"
) else (
    echo ✅ Role Enum Usage passed
)
echo.

echo Running Database Model Compatibility...
python scripts\validate_db_models.py
if %errorlevel% neq 0 (
    echo ❌ Database Model Compatibility failed ^(CRITICAL^)
    set "OVERALL_SUCCESS=false"
) else (
    echo ✅ Database Model Compatibility passed
)
echo.

echo Running Date Parameter Handling...
python scripts\validate_date_parameters.py
if %errorlevel% neq 0 (
    echo ❌ Date Parameter Handling failed ^(CRITICAL^)
    set "OVERALL_SUCCESS=false"
) else (
    echo ✅ Date Parameter Handling passed
)
echo.

echo Running Critical Bug Fixes...
python scripts\validate_critical_fixes.py
if %errorlevel% neq 0 (
    echo ❌ Critical Bug Fixes failed ^(CRITICAL^)
    set "OVERALL_SUCCESS=false"
) else (
    echo ✅ Critical Bug Fixes passed
)
echo.

REM 2. Environment and Configuration Checks
echo ⚙️ Phase 2: Environment and Configuration

echo Running Environment Configuration...
python -c "from app.core.config import settings; print('Config loaded successfully')"
if %errorlevel% neq 0 (
    echo ❌ Environment Configuration failed ^(CRITICAL^)
    set "OVERALL_SUCCESS=false"
) else (
    echo ✅ Environment Configuration passed
)
echo.

REM 3. Import and Module Tests
echo 📦 Phase 3: Import and Module Tests

echo Running Critical Module Imports...
python -c "import app.main; import app.core.config; import app.models.user; import app.models.alert; print('All imports successful')"
if %errorlevel% neq 0 (
    echo ❌ Critical Module Imports failed ^(CRITICAL^)
    set "OVERALL_SUCCESS=false"
) else (
    echo ✅ Critical Module Imports passed
)
echo.

echo Running FastAPI Application Creation...
python -c "from app.main import app; print('FastAPI app created successfully')"
if %errorlevel% neq 0 (
    echo ❌ FastAPI Application Creation failed ^(CRITICAL^)
    set "OVERALL_SUCCESS=false"
) else (
    echo ✅ FastAPI Application Creation passed
)
echo.

REM 4. API Health Checks (if not skipped)
if not "%SKIP_API_TESTS%"=="true" (
    echo 🏥 Phase 4: API Health Checks
    
    echo Running Deployment Health Check...
    python scripts\validate_deployment_health.py --base-url %API_BASE_URL%
    if %errorlevel% neq 0 (
        echo ⚠️ Deployment Health Check failed ^(NON-CRITICAL^)
    ) else (
        echo ✅ Deployment Health Check passed
    )
    echo.
) else (
    echo ⚠️ Skipping API tests as requested
)

REM 5. Security and Performance Checks
echo 🔒 Phase 5: Security and Performance

echo Running Security Configuration...
python -c "from app.core.config import settings; assert settings.SECRET_KEY, 'SECRET_KEY required'; print('Security config OK')"
if %errorlevel% neq 0 (
    echo ❌ Security Configuration failed ^(CRITICAL^)
    set "OVERALL_SUCCESS=false"
) else (
    echo ✅ Security Configuration passed
)
echo.

REM 6. Database Schema Validation (if possible)
echo 🗄️ Phase 6: Database Schema Validation

echo Running Database Connection Test...
python -c "from app.database.session import get_db; next(get_db()); print('Database connection OK')"
if %errorlevel% neq 0 (
    echo ⚠️ Database Connection Test failed ^(NON-CRITICAL^)
) else (
    echo ✅ Database Connection Test passed
)
echo.

REM 7. Regression Tests
echo 🧪 Phase 7: Regression Tests

if exist "tests\test_regression_prevention.py" (
    echo Running Regression Prevention Tests...
    python -m pytest tests\test_regression_prevention.py -v
    if %errorlevel% neq 0 (
        echo ❌ Regression Prevention Tests failed ^(CRITICAL^)
        set "OVERALL_SUCCESS=false"
    ) else (
        echo ✅ Regression Prevention Tests passed
    )
    echo.
)

if exist "tests\test_dependency_injection_fix.py" (
    echo Running Dependency Injection Fix Tests...
    python -m pytest tests\test_dependency_injection_fix.py -v
    if %errorlevel% neq 0 (
        echo ❌ Dependency Injection Fix Tests failed ^(CRITICAL^)
        set "OVERALL_SUCCESS=false"
    ) else (
        echo ✅ Dependency Injection Fix Tests passed
    )
    echo.
)

REM 8. Generate Summary Report
echo 📊 Validation Summary Report

if "%OVERALL_SUCCESS%"=="true" (
    echo ✅ 🎉 All critical validations passed! Deployment is ready.
    echo %date% %time%: Deployment validation successful > deployment_validation_success.txt
    exit /b 0
) else (
    echo ❌ 💥 Critical validations failed! Deployment should not proceed.
    echo %date% %time%: Deployment validation failed > deployment_validation_failure.txt
    echo.
    echo Critical issues must be resolved before deployment.
    exit /b 1
)