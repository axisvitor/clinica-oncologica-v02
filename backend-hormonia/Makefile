# Makefile for Neoplasias Litoral Backend System

.PHONY: help install dev test clean clean-coverage docker-up docker-down migrate

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Install Python dependencies"
	@echo "  dev         - Start development server"
	@echo "  staging-api-local-evolution    - API em staging com Evolution local (real)"
	@echo "  staging-worker-local-evolution - Worker em staging com Evolution local (real)"
	@echo "  staging-beat-local-evolution   - Beat em staging com Evolution local (real)"
	@echo "  test        - Run tests"
	@echo "  test-fast   - Run fast test subset (skip slow/integration/performance)"
	@echo "  test-unit   - Run unit tests in parallel (xdist)"
	@echo "  test-all    - Run full test suite"
	@echo "  clean       - Clean Python cache files"
	@echo "  docker-up   - Start Docker services (Redis)"
	@echo "  docker-down - Stop Docker services"
	@echo "  migrate     - Run database migrations"
	@echo "  migration   - Create new migration"
	@echo "  taskiq-worker    - Start Taskiq worker"
	@echo "  taskiq-scheduler - Start Taskiq scheduler"

# Install dependencies
install:
	pip install -r requirements.txt

# Start development server
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

staging-api-local-evolution:
	APP_ENVIRONMENT=staging WHATSAPP_EVOLUTION_USE_MOCK=false WHATSAPP_EVOLUTION_API_URL=http://127.0.0.1:8080 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

staging-worker-local-evolution:
	APP_ENVIRONMENT=staging WHATSAPP_EVOLUTION_USE_MOCK=false WHATSAPP_EVOLUTION_API_URL=http://127.0.0.1:8080 taskiq worker app.taskiq_broker:broker

staging-beat-local-evolution:
	APP_ENVIRONMENT=staging WHATSAPP_EVOLUTION_USE_MOCK=false WHATSAPP_EVOLUTION_API_URL=http://127.0.0.1:8080 taskiq scheduler app.taskiq_broker:scheduler

# Run tests
test:
	pytest

test-fast:
	pytest -m "not slow and not integration and not performance"

test-unit:
	pytest -n auto -m "unit and not slow"

test-all:
	pytest

# Run tests with coverage
test-cov:
	pytest --cov=app --cov-report=html --cov-report=term-missing

# Clean Python cache files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

clean-coverage:
	@python -c "import pathlib, shutil; \
paths=[pathlib.Path('coverage.json'), pathlib.Path('coverage.lcov'), pathlib.Path('coverage.xml'), pathlib.Path('.coverage'), pathlib.Path('test_results.txt'), pathlib.Path('htmlcov')]; \
[shutil.rmtree(p, ignore_errors=True) if p.is_dir() else (p.unlink() if p.exists() else None) for p in paths]; \
print('Removed backend coverage artifacts.')" || py -c "import pathlib, shutil; \
paths=[pathlib.Path('coverage.json'), pathlib.Path('coverage.lcov'), pathlib.Path('coverage.xml'), pathlib.Path('.coverage'), pathlib.Path('test_results.txt'), pathlib.Path('htmlcov')]; \
[shutil.rmtree(p, ignore_errors=True) if p.is_dir() else (p.unlink() if p.exists() else None) for p in paths]; \
print('Removed backend coverage artifacts.')"

# Start Docker services
docker-up:
	docker-compose up -d

# Stop Docker services
docker-down:
	docker-compose down

# Run database migrations
migrate:
	alembic upgrade head

# Create new migration
migration:
	alembic revision --autogenerate -m "$(name)"

# Start Taskiq worker
taskiq-worker:
	taskiq worker app.taskiq_broker:broker

# Start Taskiq scheduler
taskiq-scheduler:
	taskiq scheduler app.taskiq_broker:scheduler

# Format code
format:
	black --line-length 100 app/ tests/
	isort --profile black --line-length 100 app/ tests/

format-check:
	black --check --line-length 100 app/ tests/
	isort --check --profile black --line-length 100 app/ tests/

# Lint code
lint:
	ruff check app/ tests/

lint-fix:
	ruff check app/ tests/ --fix

# Code Quality Tools
install-quality:
	pip install ruff black isort vulture eradicate interrogate autoflake radon bandit safety

quality: lint dead-code docstrings unused-imports
	@echo "✅ All quality checks complete"

quality-report:
	@echo "Generating comprehensive code quality report..."
	python scripts/generate_code_quality_report.py --json
	@echo "✅ Report generated: docs/code-quality/FINAL_REPORT.md"

dead-code:
	@echo "Detecting dead code..."
	python scripts/detect_dead_code.py --output dead_code_report.txt

docstrings:
	@echo "Checking docstring coverage..."
	python scripts/analyze_docstring_coverage.py --fail-under 95

unused-imports:
	@echo "Removing unused imports..."
	python scripts/remove_unused_imports.py

unused-imports-dry:
	@echo "Checking for unused imports (dry run)..."
	python scripts/remove_unused_imports.py --dry-run

commented-code:
	@echo "Detecting commented code..."
	python scripts/detect_commented_code.py --output commented_code_report.txt

regex-audit:
	@echo "Auditing hardcoded regex patterns..."
	python scripts/audit_regex_patterns.py --output regex_audit_report.txt

complexity:
	@echo "Calculating code complexity..."
	radon cc app/ -a -s

maintainability:
	@echo "Calculating maintainability index..."
	radon mi app/ -s

# Pre-commit hooks
pre-commit:
	@echo "Installing pre-commit hooks..."
	pip install pre-commit
	pre-commit install
	@echo "✅ Pre-commit hooks installed"

pre-commit-run:
	@echo "Running pre-commit on all files..."
	pre-commit run --all-files

# Setup development environment
setup: install docker-up migrate
	@echo "Development environment setup complete!"
	@echo "Run 'make dev' to start the development server"

# Full development start
start: docker-up
	@echo "Starting all services..."
	@echo "Starting Taskiq worker in background..."
	@taskiq worker app.taskiq_broker:broker &
	@echo "Starting Taskiq scheduler in background..."
	@taskiq scheduler app.taskiq_broker:scheduler &
	@echo "Starting development server..."
	@uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# All-in-one commands
check-all: quality test
	@echo "✅ All checks passed"

fix-all: format lint-fix unused-imports
	@echo "✅ All auto-fixes applied"
