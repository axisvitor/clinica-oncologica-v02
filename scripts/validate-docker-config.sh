#!/bin/bash
# Script de validação de configuração Docker
# Verifica se todos os arquivos necessários estão presentes e válidos

set -e

echo "🔍 Validando configuração Docker..."
echo ""

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Contadores
ERRORS=0
WARNINGS=0

# Função para verificar arquivo
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1 encontrado"
        return 0
    else
        echo -e "${RED}✗${NC} $1 NÃO encontrado"
        ((ERRORS++))
        return 1
    fi
}

# Função para verificar diretório
check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} Diretório $1 existe"
        return 0
    else
        echo -e "${RED}✗${NC} Diretório $1 NÃO existe"
        ((ERRORS++))
        return 1
    fi
}

# Verificar estrutura de diretórios
echo "📁 Verificando estrutura de diretórios..."
check_dir "backend-hormonia"
check_dir "frontend-hormonia"
echo ""

# Verificar Dockerfiles
echo "🐳 Verificando Dockerfiles..."
check_file "backend-hormonia/Dockerfile"
check_file "frontend-hormonia/Dockerfile"
check_file "docker-compose.yml"
echo ""

# Verificar arquivos de configuração
echo "⚙️  Verificando arquivos de configuração..."
check_file "frontend-hormonia/nginx.conf"
check_file "backend-hormonia/package.json"
check_file "frontend-hormonia/package.json"
echo ""

# Verificar variáveis de ambiente
echo "🔐 Verificando arquivo .env..."
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} .env encontrado"

    # Verificar variáveis essenciais
    if grep -q "SUPABASE_URL" .env && \
       grep -q "SUPABASE_ANON_KEY" .env; then
        echo -e "${GREEN}✓${NC} Variáveis essenciais presentes"
    else
        echo -e "${YELLOW}⚠${NC} Algumas variáveis essenciais podem estar faltando"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠${NC} .env não encontrado (use .env.example como referência)"
    ((WARNINGS++))
fi
echo ""

# Verificar sintaxe dos Dockerfiles
echo "🔍 Validando sintaxe dos Dockerfiles..."
if command -v docker &> /dev/null; then
    # Backend
    if docker build -f backend-hormonia/Dockerfile --dry-run backend-hormonia 2>&1 | grep -q "error"; then
        echo -e "${RED}✗${NC} Erro na sintaxe do Dockerfile do backend"
        ((ERRORS++))
    else
        echo -e "${GREEN}✓${NC} Dockerfile do backend válido"
    fi

    # Frontend
    if docker build -f frontend-hormonia/Dockerfile --dry-run frontend-hormonia 2>&1 | grep -q "error"; then
        echo -e "${RED}✗${NC} Erro na sintaxe do Dockerfile do frontend"
        ((ERRORS++))
    else
        echo -e "${GREEN}✓${NC} Dockerfile do frontend válido"
    fi
else
    echo -e "${YELLOW}⚠${NC} Docker não instalado - pulando validação de sintaxe"
    ((WARNINGS++))
fi
echo ""

# Verificar docker-compose.yml
echo "🔧 Validando docker-compose.yml..."
if command -v docker-compose &> /dev/null; then
    if docker-compose config > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} docker-compose.yml válido"
    else
        echo -e "${RED}✗${NC} Erro no docker-compose.yml"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}⚠${NC} docker-compose não instalado - pulando validação"
    ((WARNINGS++))
fi
echo ""

# Resumo final
echo "================================================"
echo "📊 RESUMO DA VALIDAÇÃO"
echo "================================================"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ Tudo OK! Configuração pronta para deploy${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ $WARNINGS avisos encontrados${NC}"
    echo "A configuração está funcional mas pode precisar de ajustes"
    exit 0
else
    echo -e "${RED}✗ $ERRORS erros encontrados${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠ $WARNINGS avisos encontrados${NC}"
    fi
    echo "Corrija os erros antes de fazer o deploy"
    exit 1
fi
