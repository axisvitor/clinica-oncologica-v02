@echo off
echo ============================================================
echo 🚀 INICIANDO CELERY BEAT
echo ============================================================
echo.
echo 📋 Configuração:
echo    - Worker: Solo pool (Windows compatible)
echo    - Beat: Scheduler habilitado
echo    - Log Level: Info
echo.
echo ⏳ Iniciando...
echo.

cd /d "%~dp0.."
celery -A app.celery_app worker --beat --loglevel=info --pool=solo

pause
