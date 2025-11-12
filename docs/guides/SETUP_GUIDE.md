# Setup and Installation Guide

**Project**: Clínica Oncológica - Sistema Hormonia
**Last Updated**: 2025-11-12

## Overview

This guide will help you set up the complete Sistema Hormonia development environment on your local machine. The process typically takes 30-60 minutes for a complete setup.

## Prerequisites

### Required Software

- **Python**: 3.13+ ([Download](https://www.python.org/downloads/))
- **Node.js**: 18+ ([Download](https://nodejs.org/))
- **PostgreSQL**: 14+ ([Download](https://www.postgresql.org/download/))
- **Redis**: 7.0+ ([Download](https://redis.io/download))
- **Git**: Latest version ([Download](https://git-scm.com/downloads))

### Optional Software

- **Docker**: For containerized development ([Download](https://www.docker.com/))
- **VS Code**: Recommended IDE ([Download](https://code.visualstudio.com/))

### System Requirements

- **OS**: Windows 10+, macOS 10.15+, or Linux
- **RAM**: 8GB minimum, 16GB recommended
- **Disk Space**: 5GB free space
- **Internet**: Required for initial setup

## Quick Start (All Components)

### 1. Clone Repository

```bash
git clone https://github.com/axisvitor/clinica-oncologica-v02.git
cd clinica-oncologica-v02-1
```

### 2. Setup Backend

```bash
cd backend-hormonia

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials (see Backend Configuration section)

# Initialize database
alembic upgrade head

# Start backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Setup Frontend

```bash
cd ../frontend-hormonia

# Install dependencies
npm install
# or
bun install

# Configure environment
cp .env.example .env
# Edit .env with your backend URL

# Start development server
npm run dev
# or
bun dev
```

### 4. Setup Quiz Interface

```bash
cd ../quiz-mensal-interface

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local with your backend URL

# Start development server
npm run dev
```

## Detailed Setup Instructions

### Backend Setup (Detailed)

#### 1. Python Environment

```bash
cd backend-hormonia

# Verify Python version
python --version  # Should be 3.13+

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows PowerShell:
venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat
# Linux/macOS:
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "from app.core.application_factory import create_application; print('✅ Setup OK')"
```

#### 2. Backend Configuration

Create `.env` file from template:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Application
DEBUG=true
ENVIRONMENT=development
SECRET_KEY=your-secret-key-here-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database (Supabase)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=
REDIS_MAX_CONNECTIONS=10

# Evolution API (WhatsApp)
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_INSTANCE_NAME=hormonia
EVOLUTION_API_KEY=your-evolution-api-key

# AI Services
GOOGLE_API_KEY=your-google-gemini-key
LANGCHAIN_API_KEY=your-langchain-key  # Optional

# Security
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# Logging
LOG_LEVEL=INFO
ENABLE_REQUEST_LOGGING=true
```

#### 3. Database Setup

```bash
# Run migrations
alembic upgrade head

# Verify database connection
python scripts/test_db_connection.py

# Populate test data (optional)
python scripts/populate_test_data.py
```

#### 4. Redis Setup

**Option A: Local Redis**

```bash
# Linux
sudo apt-get install redis-server
sudo systemctl start redis-server

# macOS (Homebrew)
brew install redis
brew services start redis

# Windows (using WSL or Redis for Windows)
# Download from: https://github.com/microsoftarchive/redis/releases
```

**Option B: Docker Redis**

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

Verify Redis:

```bash
redis-cli ping  # Should return "PONG"
```

#### 5. Celery Setup (Background Tasks)

```bash
# Terminal 1: Start Celery worker
celery -A app.celery_app worker --loglevel=info

# Terminal 2: Start Celery beat (scheduler)
celery -A app.celery_app beat --loglevel=info

# Terminal 3: Start Flower (monitoring) - Optional
celery -A app.celery_app flower --port=5555
```

### Frontend Setup (Detailed)

#### 1. Node.js Environment

```bash
cd frontend-hormonia

# Verify Node.js version
node --version  # Should be 18+
npm --version   # Should be 9+

# Install dependencies
npm install

# Or using Bun (faster)
npm install -g bun
bun install
```

#### 2. Frontend Configuration

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Backend API
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# Firebase (Authentication)
VITE_FIREBASE_API_KEY=your-firebase-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=your-app-id

# Environment
VITE_ENV=development
VITE_LOG_LEVEL=debug

# Feature Flags
VITE_ENABLE_MOCK_API=false
VITE_ENABLE_OFFLINE_MODE=false
```

#### 3. Run Frontend

```bash
# Development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run tests
npm test

# Run E2E tests
npm run test:e2e
```

### Quiz Interface Setup (Detailed)

#### 1. Next.js Setup

```bash
cd quiz-mensal-interface

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
```

#### 2. Quiz Configuration

Edit `.env.local`:

```env
# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_TIMEOUT=30000

# Session Configuration
SESSION_SECRET=your-session-secret-min-32-chars
CSRF_SECRET=your-csrf-secret-min-32-chars

# Environment
NODE_ENV=development
NEXT_PUBLIC_ENV=development
```

#### 3. Run Quiz Interface

```bash
# Development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Run tests
npm test
```

## Database Configuration

### Using Supabase (Recommended)

1. Create account at [supabase.com](https://supabase.com)
2. Create new project
3. Get connection details from Settings > Database
4. Copy URL and keys to `.env`

### Using Local PostgreSQL

```bash
# Create database
createdb hormonia_dev

# Create user
psql -c "CREATE USER hormonia WITH PASSWORD 'your-password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE hormonia_dev TO hormonia;"

# Update .env
DATABASE_URL=postgresql://hormonia:your-password@localhost:5432/hormonia_dev
```

## External Services Setup

### 1. Google Gemini API

1. Go to [Google AI Studio](https://makersuite.google.com/)
2. Create API key
3. Add to `.env`: `GOOGLE_API_KEY=your-key`

### 2. Evolution API (WhatsApp)

**Option A: Using Docker**

```bash
docker run -d \
  --name evolution-api \
  -p 8080:8080 \
  -e AUTHENTICATION_API_KEY=your-api-key \
  evolution-api:latest
```

**Option B: Self-hosted**

Follow instructions at: [Evolution API Docs](https://doc.evolution-api.com/)

### 3. Firebase Authentication

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create new project
3. Enable Authentication
4. Get configuration from Project Settings
5. Add credentials to `.env`

## Verification & Testing

### Backend Health Check

```bash
# Test backend is running
curl http://localhost:8000/health

# Test Redis connection
curl http://localhost:8000/api/v2/redis/health

# Test API authentication
curl -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'
```

### Frontend Health Check

```bash
# Visit in browser
http://localhost:3000

# Check console for errors
# Open DevTools (F12) and check Console tab
```

### Quiz Interface Health Check

```bash
# Visit in browser
http://localhost:3001

# Test quiz session
http://localhost:3001/quiz/test-session-id
```

### Run All Tests

```bash
# Backend tests
cd backend-hormonia
pytest --cov=app --cov-report=html

# Frontend tests
cd ../frontend-hormonia
npm test

# E2E tests
npm run test:e2e

# Quiz interface tests
cd ../quiz-mensal-interface
npm test
```

## Troubleshooting

### Common Issues

#### Python Version Issues

```bash
# Check Python version
python --version

# If using wrong version, specify explicitly
python3.13 -m venv venv
```

#### Database Connection Errors

```bash
# Test database connection
python scripts/test_db_connection.py

# Check PostgreSQL is running
pg_isready

# Verify credentials in .env
```

#### Redis Connection Errors

```bash
# Test Redis connection
redis-cli ping

# If not running, start Redis
sudo systemctl start redis-server  # Linux
brew services start redis           # macOS
```

#### Port Already in Use

```bash
# Find process using port 8000
# Linux/macOS:
lsof -i :8000
# Windows:
netstat -ano | findstr :8000

# Kill process
kill -9 <PID>  # Linux/macOS
taskkill /PID <PID> /F  # Windows
```

#### Module Import Errors

```bash
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

#### Frontend Build Errors

```bash
# Clear node modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear build cache
rm -rf .vite dist
```

## Development Tools Setup

### VS Code Extensions

Recommended extensions for development:

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "bradlc.vscode-tailwindcss",
    "prisma.prisma",
    "ms-azuretools.vscode-docker"
  ]
}
```

### Git Hooks Setup

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Docker Setup (Alternative)

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild services
docker-compose up --build -d
```

### Docker Compose Services

- **backend**: FastAPI application (port 8000)
- **frontend**: React application (port 3000)
- **quiz**: Next.js application (port 3001)
- **postgres**: PostgreSQL database (port 5432)
- **redis**: Redis cache (port 6379)
- **celery**: Background worker
- **flower**: Celery monitoring (port 5555)

## Next Steps

After successful setup:

1. **Read Documentation**
   - [Development Workflow](./DEVELOPMENT_WORKFLOW.md)
   - [Contributing Guidelines](../CONTRIBUTING.md)
   - [API Documentation](../backend-hormonia/docs/api/API.md)

2. **Explore Codebase**
   - Backend: `/backend-hormonia`
   - Frontend: `/frontend-hormonia`
   - Quiz: `/quiz-mensal-interface`

3. **Run Tests**
   - Backend: `pytest`
   - Frontend: `npm test`
   - E2E: `npm run test:e2e`

4. **Start Developing**
   - Create feature branch
   - Make changes
   - Write tests
   - Submit PR

## Support

- **Documentation**: Check `/docs` folder
- **Backend Issues**: See [backend troubleshooting](../backend-hormonia/docs/guides/troubleshooting/)
- **GitHub Issues**: Open an issue in the repository
- **Team Chat**: Contact development team

---

**Setup Guide Version**: 1.0
**Last Updated**: 2025-11-12
**Maintained By**: Development Team
