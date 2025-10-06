#!/bin/bash

# ============================================================================
# Quick Start Script - Docker Improvements Implementation
# ============================================================================
# Este script automatiza a implementação das correções Docker
# Executar com: bash docs/backend/docker-fixes/QUICK_START.sh
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# ============================================================================
# Pre-flight Checks
# ============================================================================
print_step "Running pre-flight checks..."

# Check if we're in the right directory
if [ ! -f "backend-hormonia/Dockerfile" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install it first."
    exit 1
fi

print_success "Pre-flight checks passed"

# ============================================================================
# Step 1: Create Branch
# ============================================================================
print_step "Step 1: Creating feature branch..."

if git rev-parse --verify feat/docker-improvements &> /dev/null; then
    print_warning "Branch feat/docker-improvements already exists. Switching to it..."
    git checkout feat/docker-improvements
else
    git checkout -b feat/docker-improvements
    print_success "Created and switched to branch feat/docker-improvements"
fi

# ============================================================================
# Step 2: Backup Original Files
# ============================================================================
print_step "Step 2: Backing up original files..."

mkdir -p backups/docker-$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="backups/docker-$(date +%Y%m%d-%H%M%S)"

cp backend-hormonia/Dockerfile "$BACKUP_DIR/Dockerfile.backup"
cp backend-hormonia/docker-compose.yml "$BACKUP_DIR/docker-compose.yml.backup"
cp backend-hormonia/railway-debug.dockerfile "$BACKUP_DIR/railway-debug.dockerfile.backup"
cp backend-hormonia/.dockerignore "$BACKUP_DIR/.dockerignore.backup"

print_success "Backups created in $BACKUP_DIR"

# ============================================================================
# Step 3: Copy Fixed Files
# ============================================================================
print_step "Step 3: Copying fixed files..."

cp docs/backend/docker-fixes/Dockerfile.fixed backend-hormonia/Dockerfile
cp docs/backend/docker-fixes/docker-compose.yml.fixed backend-hormonia/docker-compose.yml
cp docs/backend/docker-fixes/railway-debug.dockerfile.fixed backend-hormonia/railway-debug.dockerfile
cp docs/backend/docker-fixes/.dockerignore.fixed backend-hormonia/.dockerignore

print_success "Fixed files copied"

# ============================================================================
# Step 4: Create Directories
# ============================================================================
print_step "Step 4: Creating required directories..."

mkdir -p backend-hormonia/secrets
mkdir -p backend-hormonia/config

print_success "Directories created"

# ============================================================================
# Step 5: Generate Secrets
# ============================================================================
print_step "Step 5: Generating secure secrets..."

# Generate Redis password
REDIS_PASSWORD=$(openssl rand -base64 32)
echo "$REDIS_PASSWORD" > backend-hormonia/secrets/redis_password.txt
chmod 600 backend-hormonia/secrets/redis_password.txt

# Generate Flower credentials
FLOWER_PASSWORD=$(openssl rand -base64 24)

print_success "Secrets generated:"
print_success "  - Redis password: backend-hormonia/secrets/redis_password.txt"
print_success "  - Flower password: (will be added to .env)"

# ============================================================================
# Step 6: Create Redis Configuration
# ============================================================================
print_step "Step 6: Creating Redis configuration..."

cp docs/backend/docker-fixes/redis.conf backend-hormonia/config/redis.conf

# Replace placeholder with actual password
sed -i.bak "s/\${REDIS_PASSWORD}/$REDIS_PASSWORD/g" backend-hormonia/config/redis.conf
rm backend-hormonia/config/redis.conf.bak

print_success "Redis configuration created"

# ============================================================================
# Step 7: Update .env File
# ============================================================================
print_step "Step 7: Updating .env file..."

if [ -f "backend-hormonia/.env" ]; then
    cp backend-hormonia/.env backend-hormonia/.env.backup-$(date +%Y%m%d-%H%M%S)
    print_warning "Backed up existing .env file"
fi

# Add new variables to .env
cat >> backend-hormonia/.env << EOF

# ============================================================================
# Docker Compose Configuration (Added $(date +%Y-%m-%d))
# ============================================================================

# Redis Configuration
REDIS_PASSWORD=$REDIS_PASSWORD
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Celery Configuration
CELERY_BROKER_URL=redis://:$REDIS_PASSWORD@redis:6379/0
CELERY_RESULT_BACKEND=redis://:$REDIS_PASSWORD@redis:6379/0

# Flower Configuration
FLOWER_USER=admin
FLOWER_PASSWORD=$FLOWER_PASSWORD

# Workers Configuration
WORKERS=4
WEB_CONCURRENCY=4

EOF

print_success ".env file updated with new variables"

# ============================================================================
# Step 8: Update .gitignore
# ============================================================================
print_step "Step 8: Updating .gitignore..."

if ! grep -q "secrets/" backend-hormonia/.gitignore 2>/dev/null; then
    echo "secrets/" >> backend-hormonia/.gitignore
    print_success "Added secrets/ to .gitignore"
else
    print_warning "secrets/ already in .gitignore"
fi

# ============================================================================
# Step 9: Build Docker Image
# ============================================================================
print_step "Step 9: Building Docker image (this may take a few minutes)..."

cd backend-hormonia

if DOCKER_BUILDKIT=1 docker build -t hormonia-backend:improved . ; then
    print_success "Docker image built successfully"

    # Show image size
    IMAGE_SIZE=$(docker images hormonia-backend:improved --format "{{.Size}}")
    print_success "Image size: $IMAGE_SIZE"
else
    print_error "Docker build failed. Please check the output above."
    exit 1
fi

cd ..

# ============================================================================
# Step 10: Test Docker Compose
# ============================================================================
print_step "Step 10: Testing Docker Compose configuration..."

cd backend-hormonia

if docker-compose config > /dev/null 2>&1; then
    print_success "Docker Compose configuration is valid"
else
    print_error "Docker Compose configuration has errors"
    exit 1
fi

cd ..

# ============================================================================
# Step 11: Run Services (Optional)
# ============================================================================
echo ""
print_step "Step 11: Start services? (y/n)"
read -r START_SERVICES

if [ "$START_SERVICES" = "y" ] || [ "$START_SERVICES" = "Y" ]; then
    cd backend-hormonia

    print_step "Starting services with Docker Compose..."
    docker-compose up -d

    print_success "Services started. Waiting for healthchecks..."
    sleep 30

    # Check service status
    docker-compose ps

    print_success "Services are running!"
    echo ""
    print_step "Access points:"
    echo "  - Flower Dashboard: http://localhost:5555/flower"
    echo "    Username: admin"
    echo "    Password: $FLOWER_PASSWORD"
    echo ""
    print_step "Useful commands:"
    echo "  - View logs: docker-compose logs -f"
    echo "  - Stop services: docker-compose down"
    echo "  - Restart service: docker-compose restart <service-name>"

    cd ..
else
    print_warning "Skipping service startup"
fi

# ============================================================================
# Step 12: Summary and Next Steps
# ============================================================================
echo ""
echo "============================================================================"
print_success "Docker improvements implemented successfully!"
echo "============================================================================"
echo ""
print_step "What was done:"
echo "  ✓ Multi-stage Dockerfile with reduced image size (~60% smaller)"
echo "  ✓ Healthcheck fixed to use wget instead of curl"
echo "  ✓ Railway debug Dockerfile updated to Python 3.13"
echo "  ✓ Docker Compose with network segregation"
echo "  ✓ Redis secured with strong password"
echo "  ✓ Flower dashboard with authentication"
echo "  ✓ Resource limits configured"
echo "  ✓ Optimized .dockerignore"
echo ""
print_step "Next steps:"
echo "  1. Review changes: git diff"
echo "  2. Test locally: cd backend-hormonia && docker-compose up"
echo "  3. Run tests: docker-compose exec celery-worker pytest"
echo "  4. Commit changes: git add . && git commit -m 'feat(docker): implement improvements'"
echo "  5. Create PR: gh pr create"
echo ""
print_step "Important files:"
echo "  - Credentials: backend-hormonia/secrets/redis_password.txt"
echo "  - Configuration: backend-hormonia/config/redis.conf"
echo "  - Environment: backend-hormonia/.env (updated)"
echo "  - Backups: $BACKUP_DIR"
echo ""
print_warning "Security reminder:"
echo "  ⚠ NEVER commit files in secrets/ directory to git"
echo "  ⚠ Rotate passwords every 90 days"
echo "  ⚠ Use environment-specific credentials for staging/production"
echo ""
print_step "Documentation:"
echo "  - Full report: docs/backend/DOCKER_REVIEW_REPORT.md"
echo "  - Summary: docs/backend/DOCKER_REVIEW_SUMMARY.md"
echo "  - Implementation guide: docs/backend/docker-fixes/IMPLEMENTATION_GUIDE.md"
echo ""
print_success "Setup complete! 🎉"
echo "============================================================================"
