#!/bin/bash

# Script de Validação dos Testes - LGPD & Idempotency
# AGENTE 4 - Tester Agent

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Validação de Testes - LGPD & Idempotency           ║${NC}"
echo -e "${BLUE}║   AGENTE 4 - Tester Agent                             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verificar diretório
if [ ! -d "tests" ]; then
    echo -e "${RED}❌ Erro: Execute este script do diretório raiz do projeto${NC}"
    exit 1
fi

# Contador
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# Função de check
check() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo -e "${RED}✗${NC} $2"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
}

echo -e "${YELLOW}📁 Verificando estrutura de arquivos...${NC}"
echo ""

# Verificar arquivos de teste
[ -f "tests/services/test_encryption_lgpd.py" ]
check $? "test_encryption_lgpd.py existe"

[ -f "tests/api/v2/test_idempotency.py" ]
check $? "test_idempotency.py existe"

[ -f "tests/services/test_saga_compensation.py" ]
check $? "test_saga_compensation.py existe"

[ -f "tests/middleware/test_lgpd_middleware.py" ]
check $? "test_lgpd_middleware.py existe"

# Verificar arquivos de suporte
[ -f "tests/pytest.ini" ]
check $? "pytest.ini existe"

[ -f "tests/RUN_TESTS.md" ]
check $? "RUN_TESTS.md existe"

[ -f "tests/IMPLEMENTATION_GUIDE.md" ]
check $? "IMPLEMENTATION_GUIDE.md existe"

# Verificar __init__.py
[ -f "tests/__init__.py" ]
check $? "tests/__init__.py existe"

[ -f "tests/services/__init__.py" ]
check $? "tests/services/__init__.py existe"

[ -f "tests/api/__init__.py" ]
check $? "tests/api/__init__.py existe"

[ -f "tests/api/v2/__init__.py" ]
check $? "tests/api/v2/__init__.py existe"

[ -f "tests/middleware/__init__.py" ]
check $? "tests/middleware/__init__.py existe"

echo ""
echo -e "${YELLOW}🔍 Verificando sintaxe Python...${NC}"
echo ""

# Verificar sintaxe
python3 -m py_compile tests/services/test_encryption_lgpd.py 2>/dev/null
check $? "test_encryption_lgpd.py compilável"

python3 -m py_compile tests/api/v2/test_idempotency.py 2>/dev/null
check $? "test_idempotency.py compilável"

python3 -m py_compile tests/services/test_saga_compensation.py 2>/dev/null
check $? "test_saga_compensation.py compilável"

python3 -m py_compile tests/middleware/test_lgpd_middleware.py 2>/dev/null
check $? "test_lgpd_middleware.py compilável"

echo ""
echo -e "${YELLOW}📊 Contando casos de teste...${NC}"
echo ""

# Contar classes de teste
encryption_classes=$(grep -c "^class Test" tests/services/test_encryption_lgpd.py || echo 0)
idempotency_classes=$(grep -c "^class Test" tests/api/v2/test_idempotency.py || echo 0)
saga_classes=$(grep -c "^class Test" tests/services/test_saga_compensation.py || echo 0)
lgpd_classes=$(grep -c "^class Test" tests/middleware/test_lgpd_middleware.py || echo 0)

total_classes=$((encryption_classes + idempotency_classes + saga_classes + lgpd_classes))

echo -e "  Classes de Teste:"
echo -e "    - Encryption: ${encryption_classes}"
echo -e "    - Idempotency: ${idempotency_classes}"
echo -e "    - Saga: ${saga_classes}"
echo -e "    - LGPD Middleware: ${lgpd_classes}"
echo -e "    ${GREEN}Total: ${total_classes}${NC}"

# Contar métodos de teste
encryption_tests=$(grep -c "    def test_" tests/services/test_encryption_lgpd.py || echo 0)
idempotency_tests=$(grep -c "    def test_" tests/api/v2/test_idempotency.py || echo 0)
saga_tests=$(grep -c "    def test_" tests/services/test_saga_compensation.py || echo 0)
lgpd_tests=$(grep -c "    def test_" tests/middleware/test_lgpd_middleware.py || echo 0)

total_tests=$((encryption_tests + idempotency_tests + saga_tests + lgpd_tests))

echo ""
echo -e "  Métodos de Teste:"
echo -e "    - Encryption: ${encryption_tests}"
echo -e "    - Idempotency: ${idempotency_tests}"
echo -e "    - Saga: ${saga_tests}"
echo -e "    - LGPD Middleware: ${lgpd_tests}"
echo -e "    ${GREEN}Total: ${total_tests}${NC}"

# Verificar se bate com esperado
[ $total_tests -ge 70 ]
check $? "Mínimo de 70 testes (encontrado: ${total_tests})"

echo ""
echo -e "${YELLOW}📏 Contando linhas de código...${NC}"
echo ""

encryption_lines=$(wc -l < tests/services/test_encryption_lgpd.py)
idempotency_lines=$(wc -l < tests/api/v2/test_idempotency.py)
saga_lines=$(wc -l < tests/services/test_saga_compensation.py)
lgpd_lines=$(wc -l < tests/middleware/test_lgpd_middleware.py)

total_lines=$((encryption_lines + idempotency_lines + saga_lines + lgpd_lines))

echo -e "  Linhas de Código:"
echo -e "    - Encryption: ${encryption_lines}"
echo -e "    - Idempotency: ${idempotency_lines}"
echo -e "    - Saga: ${saga_lines}"
echo -e "    - LGPD Middleware: ${lgpd_lines}"
echo -e "    ${GREEN}Total: ${total_lines}${NC}"

# Verificar mínimo de linhas
[ $total_lines -ge 1400 ]
check $? "Mínimo de 1400 linhas (encontrado: ${total_lines})"

echo ""
echo -e "${YELLOW}🔬 Verificando imports...${NC}"
echo ""

# Verificar imports comuns
grep -q "import pytest" tests/services/test_encryption_lgpd.py
check $? "Encryption: import pytest"

grep -q "from unittest.mock import" tests/api/v2/test_idempotency.py
check $? "Idempotency: unittest.mock imports"

grep -q "@pytest.mark.asyncio" tests/services/test_saga_compensation.py
check $? "Saga: pytest.mark.asyncio usado"

grep -q "from fastapi import Request" tests/middleware/test_lgpd_middleware.py
check $? "LGPD Middleware: FastAPI imports"

echo ""
echo -e "${YELLOW}📝 Verificando documentação...${NC}"
echo ""

# Verificar docstrings
encryption_docstrings=$(grep -c '"""' tests/services/test_encryption_lgpd.py || echo 0)
[ $encryption_docstrings -ge 10 ]
check $? "Encryption: docstrings (${encryption_docstrings})"

idempotency_docstrings=$(grep -c '"""' tests/api/v2/test_idempotency.py || echo 0)
[ $idempotency_docstrings -ge 10 ]
check $? "Idempotency: docstrings (${idempotency_docstrings})"

saga_docstrings=$(grep -c '"""' tests/services/test_saga_compensation.py || echo 0)
[ $saga_docstrings -ge 10 ]
check $? "Saga: docstrings (${saga_docstrings})"

lgpd_docstrings=$(grep -c '"""' tests/middleware/test_lgpd_middleware.py || echo 0)
[ $lgpd_docstrings -ge 10 ]
check $? "LGPD Middleware: docstrings (${lgpd_docstrings})"

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                  RESUMO DA VALIDAÇÃO                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Total de verificações: ${TOTAL_CHECKS}"
echo -e "  ${GREEN}Passou: ${PASSED_CHECKS}${NC}"
echo -e "  ${RED}Falhou: ${FAILED_CHECKS}${NC}"
echo ""

if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "${GREEN}✓ Todos os testes de validação passaram!${NC}"
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    ESTATÍSTICAS                        ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  📁 Arquivos de Teste: 4"
    echo -e "  📋 Classes de Teste: ${total_classes}"
    echo -e "  🧪 Casos de Teste: ${total_tests}"
    echo -e "  📏 Linhas de Código: ${total_lines}"
    echo -e "  📝 Docstrings: $((encryption_docstrings + idempotency_docstrings + saga_docstrings + lgpd_docstrings))"
    echo ""
    echo -e "${GREEN}✓ AGENTE 4: Missão cumprida com sucesso!${NC}"
    echo ""
    echo -e "  Próximos passos:"
    echo -e "    1. Executar testes: ${YELLOW}pytest tests/ -v${NC}"
    echo -e "    2. Ver guia: ${YELLOW}cat tests/RUN_TESTS.md${NC}"
    echo -e "    3. Implementar serviços: ${YELLOW}cat tests/IMPLEMENTATION_GUIDE.md${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Algumas verificações falharam!${NC}"
    echo ""
    echo -e "  Verifique os itens marcados com ${RED}✗${NC} acima"
    echo ""
    exit 1
fi
