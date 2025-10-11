@echo off
REM ============================================================================
REM Smoke Test Script for API Contract Fixes
REM ============================================================================
REM
REM Quick validation script that tests all 5 API endpoint fixes:
REM 1. Admin users list returns {items, total}
REM 2. User activity endpoint exists and works
REM 3. Notifications return {items, unread_count}
REM 4. Dashboard returns trend deltas
REM 5. All responses match TypeScript interfaces
REM
REM Usage: smoke_test_api_fixes.bat [API_BASE_URL]
REM Example: smoke_test_api_fixes.bat http://localhost:8000
REM ============================================================================

setlocal enabledelayedexpansion

REM Configuration
set API_BASE_URL=%1
if "%API_BASE_URL%"=="" set API_BASE_URL=http://localhost:8000
set LOG_FILE=smoke_test_results_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
set LOG_FILE=%LOG_FILE: =0%

REM Colors for output (if supported)
set RED=[91m
set GREEN=[92m
set YELLOW=[93m
set NC=[0m

echo ============================================================================
echo API Contract Fixes - Smoke Test
echo ============================================================================
echo Base URL: %API_BASE_URL%
echo Log File: %LOG_FILE%
echo ============================================================================
echo.

REM Initialize counters
set PASSED=0
set FAILED=0
set TOTAL=0

REM Start logging
echo Smoke Test Started: %date% %time% > %LOG_FILE%
echo Base URL: %API_BASE_URL% >> %LOG_FILE%
echo. >> %LOG_FILE%

REM ============================================================================
REM Helper Functions
REM ============================================================================

:test_endpoint
    set /a TOTAL+=1
    set TEST_NAME=%~1
    set ENDPOINT=%~2
    set EXPECTED_FIELDS=%~3

    echo [%TOTAL%] Testing: %TEST_NAME%
    echo [%TOTAL%] Testing: %TEST_NAME% >> %LOG_FILE%

    REM Make request (using curl)
    curl -s -w "\nHTTP_CODE:%%{http_code}" "%API_BASE_URL%%ENDPOINT%" -o temp_response.json > temp_curl.txt 2>&1

    REM Extract HTTP code
    for /f "tokens=2 delims=:" %%a in ('findstr "HTTP_CODE" temp_curl.txt') do set HTTP_CODE=%%a

    REM Check if request succeeded
    if "%HTTP_CODE%"=="200" (
        echo %GREEN%  ✓ HTTP 200 OK%NC%
        echo   HTTP 200 OK >> %LOG_FILE%

        REM Validate response structure
        type temp_response.json | findstr /C:"%EXPECTED_FIELDS%" >nul
        if !errorlevel! equ 0 (
            echo %GREEN%  ✓ Response structure valid%NC%
            echo   Response structure valid >> %LOG_FILE%
            set /a PASSED+=1
            echo   STATUS: PASSED >> %LOG_FILE%
        ) else (
            echo %RED%  ✗ Response structure invalid%NC%
            echo   Response structure invalid >> %LOG_FILE%
            echo   Expected fields: %EXPECTED_FIELDS% >> %LOG_FILE%
            echo   Actual response: >> %LOG_FILE%
            type temp_response.json >> %LOG_FILE%
            set /a FAILED+=1
            echo   STATUS: FAILED >> %LOG_FILE%
        )
    ) else (
        echo %RED%  ✗ HTTP %HTTP_CODE%%NC%
        echo   HTTP %HTTP_CODE% >> %LOG_FILE%
        set /a FAILED+=1
        echo   STATUS: FAILED >> %LOG_FILE%
    )

    echo. >> %LOG_FILE%
    echo.
    goto :eof

REM ============================================================================
REM Test 1: Admin Users List - {items, total}
REM ============================================================================

echo ============================================================================ >> %LOG_FILE%
echo Test 1: Admin Users List >> %LOG_FILE%
echo ============================================================================ >> %LOG_FILE%

call :test_endpoint "Admin Users List Structure" "/api/v1/admin/users" "items.*total"

REM ============================================================================
REM Test 2: User Activity Endpoint
REM ============================================================================

echo ============================================================================ >> %LOG_FILE%
echo Test 2: User Activity Endpoint >> %LOG_FILE%
echo ============================================================================ >> %LOG_FILE%

call :test_endpoint "User Activity Endpoint" "/api/v1/admin/users/activity" "user_id.*action.*timestamp"

REM ============================================================================
REM Test 3: Notifications - {items, unread_count}
REM ============================================================================

echo ============================================================================ >> %LOG_FILE%
echo Test 3: Notifications Structure >> %LOG_FILE%
echo ============================================================================ >> %LOG_FILE%

call :test_endpoint "Notifications Structure" "/api/v1/notifications" "items.*unread_count"

REM ============================================================================
REM Test 4: Dashboard Stats with Trends
REM ============================================================================

echo ============================================================================ >> %LOG_FILE%
echo Test 4: Dashboard Statistics >> %LOG_FILE%
echo ============================================================================ >> %LOG_FILE%

call :test_endpoint "Dashboard Stats Trends" "/api/v1/admin/dashboard/stats" "trend.*percentage.*direction"

REM ============================================================================
REM Test 5: Pagination Parameters
REM ============================================================================

echo ============================================================================ >> %LOG_FILE%
echo Test 5: Pagination Support >> %LOG_FILE%
echo ============================================================================ >> %LOG_FILE%

call :test_endpoint "Pagination Parameters" "/api/v1/admin/users?skip=0&limit=10" "items.*total"

REM ============================================================================
REM Results Summary
REM ============================================================================

echo ============================================================================
echo Test Summary
echo ============================================================================
echo Total Tests: %TOTAL%
echo Passed: %GREEN%%PASSED%%NC%
echo Failed: %RED%%FAILED%%NC%
echo ============================================================================

echo. >> %LOG_FILE%
echo ============================================================================ >> %LOG_FILE%
echo Test Summary >> %LOG_FILE%
echo ============================================================================ >> %LOG_FILE%
echo Total Tests: %TOTAL% >> %LOG_FILE%
echo Passed: %PASSED% >> %LOG_FILE%
echo Failed: %FAILED% >> %LOG_FILE%
echo ============================================================================ >> %LOG_FILE%
echo Smoke Test Completed: %date% %time% >> %LOG_FILE%

REM Cleanup temp files
del temp_response.json temp_curl.txt 2>nul

REM Exit with appropriate code
if %FAILED% gtr 0 (
    echo.
    echo %RED%SMOKE TEST FAILED%NC%
    echo See log file for details: %LOG_FILE%
    exit /b 1
) else (
    echo.
    echo %GREEN%ALL TESTS PASSED%NC%
    exit /b 0
)

endlocal
