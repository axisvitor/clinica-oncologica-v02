#!/bin/bash
# ============================================================================
# Script de Migração: Supabase → Railway PostgreSQL
# ============================================================================
# Descrição: Automatiza backup e verificações pré-migração
# Uso: ./scripts/migrate-to-railway.sh
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Functions
# ============================================================================

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 não encontrado. Instale antes de continuar."
        exit 1
    fi
    print_success "$1 instalado"
}

# ============================================================================
# FASE 1: Verificar Pré-requisitos
# ============================================================================

print_header "FASE 1: Verificando Pré-requisitos"

# Check required commands
check_command "psql"
check_command "pg_dump"
check_command "railway"

# Check environment variables
if [ -z "$DATABASE_URL" ]; then
    print_error "DATABASE_URL não configurado (Supabase)"
    echo "Execute: export DATABASE_URL='postgresql://...'"
    exit 1
fi
print_success "DATABASE_URL configurado"

# ============================================================================
# FASE 2: Análise do Banco Atual
# ============================================================================

print_header "FASE 2: Analisando Banco Supabase"

echo "Conectando ao Supabase..."

# Get database size
DB_SIZE=$(psql "$DATABASE_URL" -t -c "SELECT pg_size_pretty(pg_database_size(current_database()));")
print_success "Tamanho do banco: $DB_SIZE"

# Get table count
TABLE_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
print_success "Total de tabelas: $TABLE_COUNT"

# Get record counts
echo -e "\n${BLUE}Contagem de registros por tabela:${NC}"
psql "$DATABASE_URL" -c "
SELECT
    schemaname,
    tablename,
    n_tup_ins as total_rows
FROM pg_stat_user_tables
ORDER BY n_tup_ins DESC
LIMIT 10;
"

# Check extensions
echo -e "\n${BLUE}Extensões PostgreSQL instaladas:${NC}"
psql "$DATABASE_URL" -c "SELECT * FROM pg_extension;"

# Check PostgreSQL version
PG_VERSION=$(psql "$DATABASE_URL" -t -c "SELECT version();")
print_success "Versão PostgreSQL: $PG_VERSION"

# ============================================================================
# FASE 3: Backup
# ============================================================================

print_header "FASE 3: Criando Backup do Supabase"

# Create backup directory
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cd "$BACKUP_DIR"

print_success "Diretório de backup criado: $BACKUP_DIR"

# Backup in custom format (.dump)
DUMP_FILE="hormonia_supabase_$(date +%Y%m%d_%H%M%S).dump"
echo "Criando backup .dump (formato otimizado)..."
pg_dump "$DATABASE_URL" \
    --format=custom \
    --verbose \
    --file="$DUMP_FILE" 2>&1 | grep -E "completed|finished|dumping"

print_success "Backup .dump criado: $DUMP_FILE"

# Backup in SQL format (for audit)
SQL_FILE="hormonia_supabase_$(date +%Y%m%d_%H%M%S).sql"
echo "Criando backup .sql (formato texto)..."
pg_dump "$DATABASE_URL" \
    --format=plain \
    --verbose \
    --file="$SQL_FILE" 2>&1 | grep -E "completed|finished|dumping"

print_success "Backup .sql criado: $SQL_FILE"

# Get file sizes
DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
SQL_SIZE=$(du -h "$SQL_FILE" | cut -f1)

echo -e "\n${BLUE}Backups criados:${NC}"
echo "  - $DUMP_FILE ($DUMP_SIZE)"
echo "  - $SQL_FILE ($SQL_SIZE)"

# ============================================================================
# FASE 4: Validar Backup
# ============================================================================

print_header "FASE 4: Validando Backup"

# Check if files exist and are not empty
if [ ! -s "$DUMP_FILE" ]; then
    print_error "Backup .dump está vazio ou não existe!"
    exit 1
fi
print_success "Backup .dump válido"

if [ ! -s "$SQL_FILE" ]; then
    print_error "Backup .sql está vazio ou não existe!"
    exit 1
fi
print_success "Backup .sql válido"

# Test backup integrity (optional - cria banco temporário)
read -p "Deseja testar a integridade do backup? (cria banco temporário local) [y/N]: " TEST_BACKUP

if [[ "$TEST_BACKUP" =~ ^[Yy]$ ]]; then
    TEST_DB="hormonia_backup_test_$(date +%s)"
    echo "Criando banco temporário: $TEST_DB"

    createdb "$TEST_DB" 2>/dev/null || print_warning "Não foi possível criar banco temporário (pule este teste se não tiver PostgreSQL local)"

    if psql -lqt | cut -d \| -f 1 | grep -qw "$TEST_DB"; then
        echo "Restaurando backup no banco temporário..."
        pg_restore -d "$TEST_DB" "$DUMP_FILE" 2>&1 | grep -E "completed|finished|restoring"

        # Verify data
        TEST_COUNT=$(psql "$TEST_DB" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")

        if [ "$TEST_COUNT" -eq "$TABLE_COUNT" ]; then
            print_success "Backup válido! $TEST_COUNT tabelas restauradas."
        else
            print_error "Backup pode estar corrompido. Esperado: $TABLE_COUNT, Encontrado: $TEST_COUNT"
        fi

        # Cleanup
        echo "Removendo banco temporário..."
        dropdb "$TEST_DB"
    fi
else
    print_warning "Teste de integridade pulado"
fi

# ============================================================================
# FASE 5: Informações para Railway
# ============================================================================

print_header "FASE 5: Próximos Passos - Railway"

echo -e "${YELLOW}Backup concluído com sucesso!${NC}"
echo -e "\n${BLUE}Arquivos criados em: $(pwd)${NC}"
echo "  - $DUMP_FILE"
echo "  - $SQL_FILE"

echo -e "\n${GREEN}PRÓXIMOS PASSOS:${NC}"
echo "1. Criar projeto no Railway:"
echo "   ${BLUE}railway login${NC}"
echo "   ${BLUE}railway init${NC}"
echo ""
echo "2. Adicionar PostgreSQL no Railway:"
echo "   ${BLUE}railway add --plugin postgres${NC}"
echo "   Ou via Dashboard: + New Service → Database → PostgreSQL"
echo ""
echo "3. Obter credenciais Railway:"
echo "   ${BLUE}railway variables --service postgres${NC}"
echo ""
echo "4. Restaurar backup no Railway:"
echo "   ${BLUE}export RAILWAY_DATABASE_URL='postgresql://...'${NC}"
echo "   ${BLUE}pg_restore --verbose --no-owner --no-acl --dbname=\$RAILWAY_DATABASE_URL $DUMP_FILE${NC}"
echo ""
echo "5. Verificar migração:"
echo "   ${BLUE}psql \$RAILWAY_DATABASE_URL -c \"SELECT count(*) FROM users;\"${NC}"
echo ""
echo "6. Consultar guia completo:"
echo "   ${BLUE}docs/deployment/RAILWAY_MIGRATION_GUIDE.md${NC}"

# ============================================================================
# Summary
# ============================================================================

print_header "RESUMO DA MIGRAÇÃO"

echo -e "${GREEN}✓ Pré-requisitos verificados${NC}"
echo -e "${GREEN}✓ Banco analisado: $TABLE_COUNT tabelas, $DB_SIZE${NC}"
echo -e "${GREEN}✓ Backup criado: $DUMP_FILE ($DUMP_SIZE)${NC}"
echo -e "${GREEN}✓ Backup SQL: $SQL_FILE ($SQL_SIZE)${NC}"
echo -e "${GREEN}✓ Pronto para migrar para Railway!${NC}"

echo -e "\n${YELLOW}⚠ IMPORTANTE:${NC}"
echo "  - Guarde estes backups em local seguro"
echo "  - NÃO delete o banco Supabase até confirmar que Railway está funcionando"
echo "  - Teste todas as funcionalidades no Railway antes de desativar Supabase"

cd - > /dev/null  # Return to original directory

print_success "Script concluído!"
