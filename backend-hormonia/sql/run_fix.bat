@echo off
REM Script to run the migration fix directly on PostgreSQL
REM Usage: run_fix.bat

echo 🔧 Applying migration fixes directly to PostgreSQL...
echo ======================================================================

REM Check if .env file exists
if not exist "../.env" (
    echo ❌ Error: .env file not found in backend-hormonia directory
    echo Please ensure your .env file exists with DATABASE_URL
    pause
    exit /b 1
)

REM Read DATABASE_URL from .env file
for /f "tokens=2 delims==" %%a in ('findstr "DATABASE_URL" "../.env"') do set DATABASE_URL=%%a

REM Check if DATABASE_URL is set
if "%DATABASE_URL%"=="" (
    echo ❌ Error: DATABASE_URL not found in .env file
    echo Please set DATABASE_URL in your .env file
    pause
    exit /b 1
)

echo 📡 Connecting to database...
echo 🔧 Executing migration fixes...

REM Execute the SQL file
psql "%DATABASE_URL%" -f fix_migration_issues.sql

if %errorlevel% equ 0 (
    echo.
    echo ✅ Migration fixes applied successfully!
    echo 🎉 Your database is now ready to use.
    echo.
    echo Next steps:
    echo 1. Start your backend application
    echo 2. The migrations should now work correctly
    echo 3. If you still have issues, check the application logs
) else (
    echo.
    echo ❌ Error applying migration fixes
    echo Please check the error messages above
    pause
    exit /b 1
)

pause