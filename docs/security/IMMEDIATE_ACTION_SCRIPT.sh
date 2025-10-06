#!/bin/bash
# ============================================
# IMMEDIATE ACTION SCRIPT
# Critical Secret Rotation Automation
# ============================================
# 🚨 WARNING: This script performs CRITICAL security operations
# Review each step before executing!

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================
# HELPER FUNCTIONS
# ============================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

confirm() {
    read -p "$1 (yes/no): " response
    if [ "$response" != "yes" ]; then
        log_error "Operation cancelled by user"
        exit 1
    fi
}

# ============================================
# VALIDATION
# ============================================

log_warn "🚨 CRITICAL SECURITY INCIDENT RESPONSE SCRIPT"
log_warn "This script will generate NEW secrets to replace exposed credentials"
echo ""

confirm "Have you read the ENV_EXPOSURE_INCIDENT_REPORT.md?"
confirm "Are you authorized to perform secret rotation?"
confirm "Do you have access to Railway, Firebase, Supabase, and Redis Cloud?"

echo ""
log_info "Starting secret generation..."
echo ""

# ============================================
# GENERATE NEW SECRETS
# ============================================

log_info "Generating cryptographically secure secrets..."
echo ""

# Generate JWT secrets
log_info "1. Generating SECRET_KEY (64 bytes)..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
echo "SECRET_KEY=$SECRET_KEY"
echo ""

log_info "2. Generating JWT_SECRET_KEY (64 bytes)..."
JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
echo "JWT_SECRET_KEY=$JWT_SECRET_KEY"
echo ""

log_info "3. Generating ENCRYPTION_KEY (Fernet)..."
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "ENCRYPTION_KEY=$ENCRYPTION_KEY"
echo ""

log_info "4. Generating MONTHLY_QUIZ_TOKEN_SECRET (32 bytes)..."
QUIZ_TOKEN_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "MONTHLY_QUIZ_TOKEN_SECRET=$QUIZ_TOKEN_SECRET"
echo ""

log_info "5. Generating EVOLUTION_WEBHOOK_SECRET (32 bytes)..."
WEBHOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "EVOLUTION_WEBHOOK_SECRET=$WEBHOOK_SECRET"
echo ""

# ============================================
# SAVE TO SECURE FILE
# ============================================

SECRETS_FILE="secrets_$(date +%Y%m%d_%H%M%S).txt"
log_info "Saving secrets to: $SECRETS_FILE"

cat > "$SECRETS_FILE" << EOF
# ============================================
# GENERATED SECRETS - $(date)
# ============================================
# 🚨 WARNING: KEEP THIS FILE SECURE!
# Delete after updating Railway environment variables
# ============================================

# Backend Secrets (Update in Railway: backend-web service)
SECRET_KEY=$SECRET_KEY
JWT_SECRET_KEY=$JWT_SECRET_KEY
ENCRYPTION_KEY=$ENCRYPTION_KEY
MONTHLY_QUIZ_TOKEN_SECRET=$QUIZ_TOKEN_SECRET
EVOLUTION_WEBHOOK_SECRET=$WEBHOOK_SECRET

# ============================================
# MANUAL ROTATION REQUIRED
# ============================================

# Firebase Admin Credentials
# 1. Go to: https://console.firebase.google.com/project/sistema-oncologico-auth/settings/serviceaccounts
# 2. Delete service account: firebase-adminsdk-fbsvc@sistema-oncologico-auth.iam.gserviceaccount.com
# 3. Create new service account
# 4. Download JSON key
# 5. Update Railway variables:
#    - FIREBASE_ADMIN_PRIVATE_KEY
#    - FIREBASE_ADMIN_CLIENT_EMAIL

# Supabase Service Role Key
# 1. Go to: https://supabase.com/dashboard/project/rszpypytdciggybbpnrp/settings/api
# 2. Click "Reset service_role key"
# 3. Update Railway variable:
#    - SUPABASE_SERVICE_ROLE_KEY

# Database Password
# 1. Go to: https://supabase.com/dashboard/project/rszpypytdciggybbpnrp/settings/database
# 2. Reset database password
# 3. Update Railway variable:
#    - DATABASE_URL (update password in connection string)

# Redis Password
# 1. Go to: https://app.redislabs.com/
# 2. Navigate to database: redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
# 3. Reset password
# 4. Update Railway variables:
#    - REDIS_URL
#    - REDIS_PASSWORD
#    - CELERY_BROKER_URL
#    - CELERY_RESULT_BACKEND

# Gemini API Key
# 1. Go to: https://console.cloud.google.com/apis/credentials
# 2. Delete key: AIzaSyBg8v_IuE16HjtCBF2VBlDUpQE55IDzs18
# 3. Create new API key
# 4. Update Railway variable:
#    - GEMINI_API_KEY

# Evolution API Credentials
# 1. Log into Evolution API dashboard: https://evolution.axisvanguard.site
# 2. Regenerate API key for instance: clinica_oncologica
# 3. Update Railway variables:
#    - EVOLUTION_API_KEY
#    - EVOLUTION_WEBHOOK_SECRET (use generated value above)

# ============================================
# RAILWAY UPDATE COMMANDS
# ============================================

# Install Railway CLI if not already installed:
# npm install -g @railway/cli
# railway login

# Update backend-web service variables:
railway variables --set SECRET_KEY="$SECRET_KEY"
railway variables --set JWT_SECRET_KEY="$JWT_SECRET_KEY"
railway variables --set ENCRYPTION_KEY="$ENCRYPTION_KEY"
railway variables --set MONTHLY_QUIZ_TOKEN_SECRET="$QUIZ_TOKEN_SECRET"
railway variables --set EVOLUTION_WEBHOOK_SECRET="$WEBHOOK_SECRET"

# ⚠️ WARNING: JWT rotation will invalidate all active sessions
# Users will need to re-login

# ============================================
# POST-ROTATION TASKS
# ============================================

# 1. Flush Redis cache:
#    redis-cli -h redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com -p 14149 -a <NEW_PASSWORD>
#    > FLUSHALL

# 2. Restart all Railway services:
#    - backend-web
#    - backend-worker
#    - backend-beat

# 3. Test authentication:
#    curl https://clinica-oncologica-v02-production.up.railway.app/health

# 4. Monitor logs for errors

# 5. Delete this file securely:
#    shred -u $SECRETS_FILE  # Linux
#    rm -P $SECRETS_FILE     # macOS
#    del $SECRETS_FILE       # Windows (then empty recycle bin)

EOF

log_info "Secrets saved to: $SECRETS_FILE"
echo ""

# ============================================
# INSTRUCTIONS
# ============================================

log_info "✅ Secret generation complete!"
echo ""
log_warn "NEXT STEPS:"
echo ""
echo "1. Review the generated secrets in: $SECRETS_FILE"
echo "2. Update Railway environment variables (see file for commands)"
echo "3. Manually rotate Firebase, Supabase, Redis, and Gemini credentials"
echo "4. Test all services after rotation"
echo "5. SECURELY DELETE $SECRETS_FILE after completion"
echo ""
log_warn "📋 Follow the detailed checklist in: ROTATION_CHECKLIST.md"
echo ""

# ============================================
# RAILWAY CLI HELPER
# ============================================

log_info "Railway CLI Helper"
echo ""
read -p "Do you want to update Railway variables now? (yes/no): " update_railway

if [ "$update_railway" = "yes" ]; then
    log_info "Checking Railway CLI..."

    if ! command -v railway &> /dev/null; then
        log_error "Railway CLI not found. Install with: npm install -g @railway/cli"
        exit 1
    fi

    log_info "Railway CLI found. Make sure you're logged in..."
    railway whoami

    confirm "Proceed with updating Railway variables?"

    log_info "Updating backend-web service variables..."

    # Select the correct service and environment
    log_warn "Make sure to select the correct Railway service (backend-web)"

    railway variables --set "SECRET_KEY=$SECRET_KEY"
    railway variables --set "JWT_SECRET_KEY=$JWT_SECRET_KEY"
    railway variables --set "ENCRYPTION_KEY=$ENCRYPTION_KEY"
    railway variables --set "MONTHLY_QUIZ_TOKEN_SECRET=$QUIZ_TOKEN_SECRET"
    railway variables --set "EVOLUTION_WEBHOOK_SECRET=$WEBHOOK_SECRET"

    log_info "✅ Railway variables updated!"
    log_warn "⚠️ All user sessions will be invalidated. Users must re-login."
    echo ""
fi

# ============================================
# COMPLETION
# ============================================

log_info "🎯 Script execution complete!"
echo ""
log_warn "IMPORTANT REMINDERS:"
echo "1. Complete manual rotations for Firebase, Supabase, Redis, Gemini"
echo "2. Test all services after rotation"
echo "3. Monitor logs for 24-48 hours"
echo "4. Securely delete $SECRETS_FILE"
echo "5. Update incident report with completion status"
echo ""
log_info "For detailed instructions, refer to:"
echo "  - ENV_EXPOSURE_INCIDENT_REPORT.md"
echo "  - ROTATION_CHECKLIST.md"
echo ""
