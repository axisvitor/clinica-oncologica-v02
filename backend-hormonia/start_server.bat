@echo off
cd /d C:\exclusivo\clinica-oncologica-v01\Backend
echo Starting Backend Server...
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause