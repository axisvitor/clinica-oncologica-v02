@echo off
REM Authentication Tests Runner for Windows
REM Quick script to run all authentication tests

setlocal enabledelayedexpansion

echo.
echo =================================
echo    Authentication Tests Runner
echo =================================
echo.

REM Get project root
set "PROJECT_ROOT=%~dp0.."
set "BACKEND_DIR=%PROJECT_ROOT%\backend-hormonia"
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend-hormonia"

REM Default options
set RUN_BACKEND=1
set RUN_FRONTEND=1
set RUN_E2E=0
set COVERAGE=0

REM Parse arguments
:parse_args
if "%~1"=="" goto run_tests
if /i "%~1"=="--backend-only" (
    set RUN_FRONTEND=0
    set RUN_E2E=0
    shift
    goto parse_args
)
if /i "%~1"=="--frontend-only" (
    set RUN_BACKEND=0
    set RUN_E2E=0
    shift
    goto parse_args
)
if /i "%~1"=="--e2e-only" (
    set RUN_BACKEND=0
    set RUN_FRONTEND=0
    set RUN_E2E=1
    shift
    goto parse_args
)
if /i "%~1"=="--coverage" (
    set COVERAGE=1
    shift
    goto parse_args
)
if /i "%~1"=="--all" (
    set RUN_BACKEND=1
    set RUN_FRONTEND=1
    set RUN_E2E=1
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    echo Usage: run-auth-tests.cmd [options]
    echo.
    echo Options:
    echo   --backend-only    Run only backend tests
    echo   --frontend-only   Run only frontend unit tests
    echo   --e2e-only        Run only E2E tests
    echo   --coverage        Generate coverage reports
    echo   --all             Run all tests including E2E
    echo   --help            Show this help message
    echo.
    exit /b 0
)
echo Unknown option: %~1
echo Use --help for usage information
exit /b 1

:run_tests

REM Backend Tests
if %RUN_BACKEND%==1 (
    echo [34m▶ Running Backend Authentication Tests[0m
    cd /d "%BACKEND_DIR%"

    if %COVERAGE%==1 (
        pytest tests/unit/services/test_firebase_auth_service.py -v --cov=app.services.firebase_auth_service --cov-report=term-missing --cov-report=html:htmlcov/auth
        if !errorlevel! equ 0 (
            echo [32m✓ Backend tests completed with coverage[0m
            echo    Coverage report: %BACKEND_DIR%\htmlcov\auth\index.html
        ) else (
            echo [31m✗ Backend tests failed[0m
            exit /b 1
        )
    ) else (
        pytest tests/unit/services/test_firebase_auth_service.py -v
        if !errorlevel! equ 0 (
            echo [32m✓ Backend tests completed[0m
        ) else (
            echo [31m✗ Backend tests failed[0m
            exit /b 1
        )
    )
    echo.
)

REM Frontend Unit Tests
if %RUN_FRONTEND%==1 (
    echo [34m▶ Running Frontend Unit Tests[0m
    cd /d "%FRONTEND_DIR%"

    if %COVERAGE%==1 (
        call npm run test -- tests/unit/lib/test_firebase_client.ts --coverage
        if !errorlevel! equ 0 (
            echo [32m✓ Frontend unit tests completed with coverage[0m
            echo    Coverage report: %FRONTEND_DIR%\coverage\index.html
        ) else (
            echo [31m✗ Frontend unit tests failed[0m
            exit /b 1
        )
    ) else (
        call npm run test -- tests/unit/lib/test_firebase_client.ts
        if !errorlevel! equ 0 (
            echo [32m✓ Frontend unit tests completed[0m
        ) else (
            echo [31m✗ Frontend unit tests failed[0m
            exit /b 1
        )
    )
    echo.
)

REM E2E Tests
if %RUN_E2E%==1 (
    echo [34m▶ Running E2E Authentication Tests[0m
    cd /d "%FRONTEND_DIR%"

    REM Check if Playwright is installed
    npx playwright --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [34m▶ Installing Playwright browsers...[0m
        call npx playwright install
    )

    call npx playwright test tests/e2e/auth/login.spec.ts --reporter=list
    if !errorlevel! equ 0 (
        echo [32m✓ E2E tests completed[0m
        echo    View report: npx playwright show-report
    ) else (
        echo [31m✗ E2E tests failed[0m
        exit /b 1
    )
    echo.
)

REM Summary
echo =================================
echo [32m✓ Test execution completed![0m
echo.

if %COVERAGE%==1 (
    echo 📊 Coverage Reports:
    if %RUN_BACKEND%==1 echo    Backend:  %BACKEND_DIR%\htmlcov\auth\index.html
    if %RUN_FRONTEND%==1 echo    Frontend: %FRONTEND_DIR%\coverage\index.html
    echo.
)

echo 📚 Next Steps:
echo    - Review test results above
if %COVERAGE%==1 echo    - Open coverage reports in browser
if %RUN_E2E%==1 echo    - View E2E report: cd frontend-hormonia ^&^& npx playwright show-report
echo    - Fix any failing tests
echo.

endlocal
