# Makefile for Neoplasias Litoral Backend System

.PHONY: help install dev test clean docker-up docker-down migrate

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Install Python dependencies"
	@echo "  dev         - Start development server"
	@echo "  test        - Run tests"
	@echo "  clean       - Clean Python cache files"
	@echo "  docker-up   - Start Docker services (Redis, Celery)"
	@echo "  docker-down - Stop Docker services"
	@echo "  migrate     - Run database migrations"
	@echo "  migration   - Create new migration"
	@echo "  celery      - Start Celery worker"
	@echo "  beat        - Start Celery beat scheduler"
	@echo "  flower      - Start Celery flower monitoring"

# Install dependencies
install:
	pip install -r requirements.txt

# Start development server
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
test:
	pytest

# Run tests with coverage
test-cov:
	pytest --cov=app --cov-report=html

# Clean Python cache files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

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

# Start Celery worker
celery:
	celery -A app.celery_app worker --loglevel=info

# Start Celery beat scheduler
beat:
	celery -A app.celery_app beat --loglevel=info

# Start Celery flower monitoring
flower:
	celery -A app.celery_app flower --port=5555

# Format code
format:
	black app/ tests/
	isort app/ tests/

# Lint code
lint:
	flake8 app/ tests/

# Setup development environment
setup: install docker-up migrate
	@echo "Development environment setup complete!"
	@echo "Run 'make dev' to start the development server"

# Full development start
start: docker-up
	@echo "Starting all services..."
	@echo "Starting Celery worker in background..."
	@celery -A app.celery_app worker --loglevel=info --detach
	@echo "Starting Celery beat in background..."
	@celery -A app.celery_app beat --loglevel=info --detach
	@echo "Starting development server..."
	@uvicorn app.main:app --reload --host 0.0.0.0 --port 8000