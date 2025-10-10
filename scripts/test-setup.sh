#!/bin/bash
# Test Setup Script for Clinica Oncológica v02
# This script sets up the testing environment and dependencies

set -e  # Exit on any error

echo "🚀 Setting up test environment for Clinica Oncológica v02..."

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running in CI environment
if [[ "$CI" == "true" ]]; then
    log_info "Running in CI environment"
    export TESTING=true
    export CI_MODE=true
fi

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    log_success "Python $PYTHON_VERSION found"

    # Check Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js is required but not installed"
        exit 1
    fi

    NODE_VERSION=$(node --version)
    log_success "Node.js $NODE_VERSION found"

    # Check npm
    if ! command -v npm &> /dev/null; then
        log_error "npm is required but not installed"
        exit 1
    fi

    NPM_VERSION=$(npm --version)
    log_success "npm $NPM_VERSION found"

    # Check Docker (optional)
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | sed 's/,//')
        log_success "Docker $DOCKER_VERSION found"
    else
        log_warning "Docker not found - some tests may not run"
    fi
}

# Set up Python virtual environment
setup_python_env() {
    log_info "Setting up Python environment..."

    if [[ ! -d "backend-hormonia" ]]; then
        log_warning "Backend directory not found, skipping Python setup"
        return 0
    fi

    cd backend-hormonia

    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv venv
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Upgrade pip
    log_info "Upgrading pip..."
    pip install --upgrade pip

    # Install requirements
    if [[ -f "requirements.txt" ]]; then
        log_info "Installing Python dependencies..."
        pip install -r requirements.txt
    fi

    # Install test dependencies
    log_info "Installing test dependencies..."
    pip install pytest pytest-cov pytest-benchmark bandit safety pytest-xdist pytest-mock

    # Install development dependencies
    pip install black isort flake8 mypy

    log_success "Python environment setup complete"
    cd ..
}

# Set up Node.js environment
setup_node_env() {
    log_info "Setting up Node.js environment..."

    if [[ ! -d "frontend-hormonia" ]]; then
        log_warning "Frontend directory not found, skipping Node.js setup"
        return 0
    fi

    cd frontend-hormonia

    # Install dependencies
    if [[ -f "package.json" ]]; then
        log_info "Installing Node.js dependencies..."
        npm ci
    fi

    # Install additional test dependencies
    log_info "Installing additional test dependencies..."
    npm install --save-dev @testing-library/jest-dom @testing-library/react @testing-library/user-event

    log_success "Node.js environment setup complete"
    cd ..
}

# Set up database for testing
setup_database() {
    log_info "Setting up test database..."

    # Check if PostgreSQL is available
    if command -v psql &> /dev/null; then
        log_info "PostgreSQL found, setting up test database..."

        # Create test database (ignore errors if it already exists)
        createdb test_clinica_oncologica 2>/dev/null || true

        # Set environment variables
        export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/test_clinica_oncologica"
        export TESTING=true

        log_success "Test database setup complete"
    elif command -v docker &> /dev/null; then
        log_info "PostgreSQL not found locally, starting Docker container..."

        # Start PostgreSQL container
        docker run -d \
            --name test-postgres \
            -e POSTGRES_PASSWORD=postgres \
            -e POSTGRES_DB=test_clinica_oncologica \
            -p 5432:5432 \
            postgres:15 2>/dev/null || true

        # Wait for database to be ready
        log_info "Waiting for database to be ready..."
        sleep 10

        export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/test_clinica_oncologica"
        export TESTING=true

        log_success "Test database container started"
    else
        log_warning "No PostgreSQL or Docker found - using SQLite for tests"
        export DATABASE_URL="sqlite:///test.db"
        export TESTING=true
    fi
}

# Set up Redis for testing
setup_redis() {
    log_info "Setting up Redis for testing..."

    if command -v redis-server &> /dev/null; then
        log_info "Redis found locally"
        export REDIS_URL="redis://localhost:6379"
    elif command -v docker &> /dev/null; then
        log_info "Starting Redis container..."

        docker run -d \
            --name test-redis \
            -p 6379:6379 \
            redis:7 2>/dev/null || true

        export REDIS_URL="redis://localhost:6379"
        log_success "Redis container started"
    else
        log_warning "No Redis found - some tests may be skipped"
    fi
}

# Create test configuration files
create_test_configs() {
    log_info "Creating test configuration files..."

    # Create pytest.ini for backend
    if [[ -d "backend-hormonia" && ! -f "backend-hormonia/pytest.ini" ]]; then
        cat > backend-hormonia/pytest.ini << EOF
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --strict-markers
    --disable-warnings
    --tb=short
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
    benchmark: Performance benchmark tests
EOF
        log_success "Created pytest.ini"
    fi

    # Create vitest config for frontend (if not exists)
    if [[ -d "frontend-hormonia" && ! -f "frontend-hormonia/vitest.config.ts" ]]; then
        cat > frontend-hormonia/vitest.config.ts << 'EOF'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        'dist/',
        'build/'
      ],
      thresholds: {
        global: {
          branches: 80,
          functions: 80,
          lines: 80,
          statements: 80
        }
      }
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  }
})
EOF
        log_success "Created vitest.config.ts"
    fi

    # Create test environment file
    cat > .env.test << EOF
# Test Environment Configuration
NODE_ENV=test
TESTING=true

# Database
DATABASE_URL=${DATABASE_URL:-sqlite:///test.db}
REDIS_URL=${REDIS_URL:-}

# API Configuration
API_BASE_URL=http://localhost:8000
API_TIMEOUT=10000

# Security
SECRET_KEY=test-secret-key-for-testing-only
JWT_SECRET_KEY=test-jwt-secret-key

# External Services (mock endpoints for testing)
FIREBASE_PROJECT_ID=test-project
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=test-key

# Feature Flags
ENABLE_CACHE=false
ENABLE_RATE_LIMITING=false
DEBUG=true
EOF
    log_success "Created .env.test"
}

# Set up test data and fixtures
setup_test_data() {
    log_info "Setting up test data and fixtures..."

    # Create test data directory
    mkdir -p test-data/{fixtures,mocks,snapshots}

    # Create sample test fixtures
    cat > test-data/fixtures/users.json << EOF
{
  "test_admin": {
    "email": "admin@test.com",
    "password": "test_password",
    "role": "admin",
    "name": "Test Admin"
  },
  "test_doctor": {
    "email": "doctor@test.com",
    "password": "test_password",
    "role": "medico",
    "name": "Dr. Test"
  },
  "test_patient": {
    "email": "patient@test.com",
    "password": "test_password",
    "role": "paciente",
    "name": "Test Patient"
  }
}
EOF

    cat > test-data/fixtures/patients.json << EOF
{
  "patient_1": {
    "nome": "João Silva",
    "email": "joao@test.com",
    "cpf": "12345678901",
    "data_nascimento": "1980-01-01",
    "telefone": "11999999999"
  },
  "patient_2": {
    "nome": "Maria Santos",
    "email": "maria@test.com",
    "cpf": "98765432109",
    "data_nascimento": "1975-05-15",
    "telefone": "11888888888"
  }
}
EOF

    log_success "Test data setup complete"
}

# Run pre-test validations
run_validations() {
    log_info "Running pre-test validations..."

    # Check if test runner script exists
    if [[ ! -f "run_complete_tests.py" ]]; then
        log_error "Test runner script not found"
        exit 1
    fi

    # Validate Python syntax
    if [[ -d "backend-hormonia" ]]; then
        log_info "Validating Python syntax..."
        find backend-hormonia -name "*.py" -exec python3 -m py_compile {} \; || {
            log_error "Python syntax validation failed"
            exit 1
        }
        log_success "Python syntax validation passed"
    fi

    # Validate TypeScript/JavaScript syntax
    if [[ -d "frontend-hormonia" ]]; then
        log_info "Validating TypeScript/JavaScript syntax..."
        cd frontend-hormonia
        npm run typecheck || {
            log_error "TypeScript validation failed"
            exit 1
        }
        cd ..
        log_success "TypeScript validation passed"
    fi
}

# Clean up previous test artifacts
cleanup_previous_runs() {
    log_info "Cleaning up previous test runs..."

    # Remove old test reports
    rm -rf test-reports/
    rm -rf backend-hormonia/htmlcov/
    rm -rf backend-hormonia/.coverage
    rm -rf frontend-hormonia/coverage/

    # Clean up Docker containers (if running)
    if command -v docker &> /dev/null; then
        docker rm -f test-postgres test-redis 2>/dev/null || true
    fi

    log_success "Cleanup complete"
}

# Main setup function
main() {
    log_info "Starting test environment setup..."

    cleanup_previous_runs
    check_requirements
    setup_python_env
    setup_node_env
    setup_database
    setup_redis
    create_test_configs
    setup_test_data
    run_validations

    log_success "Test environment setup complete!"
    log_info "You can now run tests using: python run_complete_tests.py"

    # Show environment status
    echo ""
    echo "📊 Environment Status:"
    echo "======================"
    echo "Python: $(python3 --version)"
    echo "Node.js: $(node --version)"
    echo "npm: $(npm --version)"
    echo "Database: ${DATABASE_URL:-Not configured}"
    echo "Redis: ${REDIS_URL:-Not configured}"
    echo "Test Mode: ${TESTING:-false}"
    echo ""
}

# Run main function
main "$@"