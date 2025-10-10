@echo off
echo Running Backend Tests...
cd /d "%~dp0"
py -m pytest tests/ --cov=app --cov-report=term-missing --tb=short -x --maxfail=10 -q > test_results.txt 2>&1
type test_results.txt