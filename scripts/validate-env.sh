#!/bin/bash
# ============================================================================
# SCRIPT: Validação de Variáveis de Ambiente
# Verifica se todos os .env estão configurados corretamente para produção local
# ============================================================================

set -e

echo "=========================================="
echo "  VALIDAÇÃO DE AMBIENTE - PRODUÇÃO LOCAL"
echo "=========================================="
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Função para validar arquivo
check_file() {
    local file=$1
    local name=$2

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $name existe"
        return 0
    else
        echo -e "${RED}✗${NC} $name não encontrado"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# Função para validar variável
check_var() {
    local file=$1
    local var=$2
    local required=$3

    if grep -q "^${var}=" "$file" 2>/dev/null; then
        value=$(grep "^${var}=" "$file" | cut -d '=' -f 2-)
        if [ -n "$value" ] && [ "$value" != "''" ] && [ "$value" != '""' ]; then
            echo -e "  ${GREEN}✓${NC} $var"
            return 0
        else
            if [ "$required" = "required" ]; then
                echo -e "  ${RED}✗${NC} $var (vazio)"
                ERRORS=$((ERRORS + 1))
                return 1
            else
                echo -e "  ${YELLOW}!${NC} $var (vazio - opcional)"
                WARNINGS=$((WARNINGS + 1))
                return 0
            fi
        fi
    else
        if [ "$required" = "required" ]; then
            echo -e "  ${RED}✗${NC} $var (não encontrado)"
            ERRORS=$((ERRORS + 1))
            return 1
        else
            echo -e "  ${YELLOW}!${NC} $var (não encontrado - opcional)"
            WARNINGS=$((WARNINGS + 1))
            return 0
        fi
    fi
}

echo "1. Verificando arquivos de ambiente..."
echo ""

check_file "backend-hormonia/.env.local.production" "Backend .env.local.production"
check_file "frontend-hormonia/.env.local.production" "Frontend .env.local.production"
check_file "quiz-mensal-interface/.env.local.production" "Quiz .env.local.production"

echo ""
echo "2. Validando variáveis críticas do Backend..."
echo ""

BACKEND_ENV="backend-hormonia/.env.local.production"
if [ -f "$BACKEND_ENV" ]; then
    check_var "$BACKEND_ENV" "APP_ENVIRONMENT" "required"
    check_var "$BACKEND_ENV" "DATABASE_URL" "required"
    check_var "$BACKEND_ENV" "REDIS_URL" "required"
    check_var "$BACKEND_ENV" "SECURITY_SECRET_KEY" "required"
    check_var "$BACKEND_ENV" "SECURITY_ENCRYPTION_KEY" "required"
    check_var "$BACKEND_ENV" "SECURITY_CSRF_SECRET_KEY" "required"
    check_var "$BACKEND_ENV" "FIREBASE_ADMIN_PROJECT_ID" "required"
    check_var "$BACKEND_ENV" "FIREBASE_ADMIN_PRIVATE_KEY" "required"
    check_var "$BACKEND_ENV" "AI_GEMINI_API_KEY" "required"
    check_var "$BACKEND_ENV" "QUIZ_TOKEN_SECRET" "required"
    check_var "$BACKEND_ENV" "CELERY_BROKER_URL" "required"
fi

echo ""
echo "3. Validando variáveis críticas do Frontend..."
echo ""

FRONTEND_ENV="frontend-hormonia/.env.local.production"
if [ -f "$FRONTEND_ENV" ]; then
    check_var "$FRONTEND_ENV" "VITE_API_BASE_URL" "required"
    check_var "$FRONTEND_ENV" "VITE_FIREBASE_API_KEY" "required"
    check_var "$FRONTEND_ENV" "VITE_FIREBASE_PROJECT_ID" "required"
    check_var "$FRONTEND_ENV" "VITE_FIREBASE_AUTH_DOMAIN" "required"
    check_var "$FRONTEND_ENV" "VITE_APP_ENVIRONMENT" "required"
fi

echo ""
echo "4. Validando variáveis críticas do Quiz..."
echo ""

QUIZ_ENV="quiz-mensal-interface/.env.local.production"
if [ -f "$QUIZ_ENV" ]; then
    check_var "$QUIZ_ENV" "NEXT_PUBLIC_API_URL" "required"
    check_var "$QUIZ_ENV" "QUIZ_SESSION_SECRET" "required"
    check_var "$QUIZ_ENV" "NODE_ENV" "required"
fi

echo ""
echo "=========================================="
echo "  RESULTADO"
echo "=========================================="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ Todas as validações passaram!${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}! $WARNINGS avisos (variáveis opcionais)${NC}"
    fi
    echo ""
    echo "Para usar os arquivos de produção local:"
    echo ""
    echo "  # Backend"
    echo "  cd backend-hormonia"
    echo "  cp .env.local.production .env"
    echo ""
    echo "  # Frontend"
    echo "  cd frontend-hormonia"
    echo "  cp .env.local.production .env"
    echo ""
    echo "  # Quiz"
    echo "  cd quiz-mensal-interface"
    echo "  cp .env.local.production .env"
    echo ""
    exit 0
else
    echo -e "${RED}✗ $ERRORS erros encontrados${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}! $WARNINGS avisos${NC}"
    fi
    echo ""
    echo "Corrija os erros antes de continuar."
    exit 1
fi
