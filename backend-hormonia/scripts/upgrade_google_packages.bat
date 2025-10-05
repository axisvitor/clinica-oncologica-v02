@echo off
REM Script to upgrade Google packages and fix pkg_resources deprecation warning
REM Run this from the backend-hormonia directory

echo ============================================================
echo Upgrading Google packages to fix pkg_resources deprecation
echo ============================================================
echo.

echo Step 1: Checking current Python version...
py --version
echo.

echo Step 2: Backing up current package list...
py -m pip freeze > requirements.backup.txt
echo Backup saved to requirements.backup.txt
echo.

echo Step 3: Upgrading specific Google packages...
py -m pip install --upgrade "googleapis-common-protos>=1.70.0,<2.0.0"
py -m pip install --upgrade "google-api-core>=2.25.0,<3.0.0"
py -m pip install --upgrade "google-auth>=2.40.0,<3.0.0"
py -m pip install --upgrade "grpcio>=1.75.0,<2.0.0"
py -m pip install --upgrade "grpcio-status>=1.75.0,<2.0.0"
py -m pip install --upgrade "proto-plus>=1.26.0,<2.0.0"
py -m pip install --upgrade "firebase-admin>=6.9.0,<7.0.0"
echo.

echo Step 4: Installing all requirements (to catch any new dependencies)...
py -m pip install --upgrade -r requirements.txt
echo.

echo Step 5: Checking for package conflicts...
py -m pip check
echo.

echo Step 6: Running verification script...
py scripts\verify_pkg_resources_fix.py
echo.

echo ============================================================
echo Upgrade complete!
echo ============================================================
echo.
echo Next steps:
echo 1. Review the verification output above
echo 2. Test your application: py -m uvicorn app.main:app --reload
echo 3. Run tests: py -m pytest tests/ -v
echo.
echo If you encounter issues, restore from backup:
echo    py -m pip install -r requirements.backup.txt
echo.

pause
