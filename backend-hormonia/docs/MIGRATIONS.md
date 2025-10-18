# Alembic Migrations Guide

## 📋 Visão Geral

Este documento descreve como trabalhar com migrations no sistema Hormonia usando Alembic.

**CRITICAL FIX #1**: Implementação de migrations para controle de schema e rollback seguro.

## 🎯 Por que Migrations?

### Problemas sem Migrations:
- ❌ Sem controle de versão do schema
- ❌ Rollback impossível em caso de problemas
- ❌ Sincronização difícil entre ambientes
- ❌ Risco de inconsistências em produção
- ❌ Difícil rastreamento de mudanças

### Benefícios com Migrations:
- ✅ Controle de versão completo do schema
- ✅ Rollback seguro e testado
- ✅ Sincronização automática entre ambientes
- ✅ Auditoria de mudanças
- ✅ CI/CD integrado

## 🚀 Quick Start

### 1. Criar Nova Migration

```bash
# Auto-generate migration baseada em mudanças de models
alembic revision --autogenerate -m "Add user email verification"

# Criar migration vazia (para dados ou operações complexas)
alembic revision -m "Populate initial data"
```

### 2. Aplicar Migrations

```bash
# Aplicar todas as migrations pendentes
alembic upgrade head

# Aplicar até uma versão específica
alembic upgrade <revision_id>

# Aplicar próxima migration
alembic upgrade +1
```

### 3. Fazer Rollback

```bash
# Voltar uma migration
alembic downgrade -1

# Voltar até versão específica
alembic downgrade <revision_id>

# Voltar tudo (CUIDADO!)
alembic downgrade base
```

### 4. Ver Status

```bash
# Ver versão atual
alembic current

# Ver histórico de migrations
alembic history

# Ver migrations pendentes
alembic history --verbose
```

## 📁 Estrutura de Arquivos

```
backend-hormonia/
├── alembic/
│   ├── versions/              # Migrations (versionadas no git)
│   │   ├── 001_initial_schema.py
│   │   ├── 002_add_user_metadata.py
│   │   └── 003_create_indexes.py
│   ├── env.py                 # Configuração do Alembic
│   └── script.py.mako         # Template para novas migrations
├── alembic.ini                # Configuração principal
└── scripts/
    └── create_initial_migration.py  # Helper para migration inicial
```

## 🔧 Criar Migration Inicial

### Usando Script Automático (Recomendado)

```bash
# Navegar para o backend
cd backend-hormonia

# Executar script de criação
python scripts/create_initial_migration.py
```

O script irá:
1. ✅ Validar conexão com banco de dados
2. ✅ Verificar schema existente
3. ✅ Gerar migration inicial
4. ✅ Validar sintaxe da migration
5. ✅ Fornecer próximos passos

### Usando Alembic Diretamente

```bash
# Gerar migration inicial
alembic revision --autogenerate -m "Initial schema with all models"

# Revisar arquivo gerado em alembic/versions/

# Aplicar migration
alembic upgrade head

# Testar rollback
alembic downgrade -1
alembic upgrade head
```

## 📝 Anatomia de uma Migration

```python
"""Add user email verification

Revision ID: abc123def456
Revises: previous_revision_id
Create Date: 2024-01-15 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = 'abc123def456'
down_revision = 'previous_revision_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema to this version."""
    # Add column
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=True))
    
    # Create index
    op.create_index('idx_users_email_verified', 'users', ['email_verified'])
    
    # Set default values
    op.execute("UPDATE users SET email_verified = false WHERE email_verified IS NULL")
    
    # Make column not nullable
    op.alter_column('users', 'email_verified', nullable=False)


def downgrade() -> None:
    """Rollback to previous version."""
    # Drop index
    op.drop_index('idx_users_email_verified', 'users')
    
    # Drop column
    op.drop_column('users', 'email_verified')
```

## 🎨 Boas Práticas

### 1. Sempre Revisar Auto-Generated Migrations

```bash
# NUNCA aplique migrations sem revisar!
alembic revision --autogenerate -m "Your message"

# Abra o arquivo gerado e revise:
# - Operações são corretas?
# - Downgrade está implementado?
# - Dados serão preservados?
# - Performance é aceitável?
```

### 2. Testar Upgrade e Downgrade

```bash
# Sempre teste o ciclo completo
alembic upgrade head      # Aplicar
alembic downgrade -1      # Reverter
alembic upgrade head      # Re-aplicar
```

### 3. Usar Transações

```python
def upgrade() -> None:
    # Use batch operations para melhor performance
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('new_field', sa.String(255)))
        batch_op.create_index('idx_new_field', ['new_field'])
```

### 4. Migration de Dados Sensíveis

```python
def upgrade() -> None:
    # 1. Adicionar coluna como nullable
    op.add_column('users', sa.Column('new_field', sa.String(255), nullable=True))
    
    # 2. Migrar dados
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE users SET new_field = old_field WHERE old_field IS NOT NULL")
    )
    
    # 3. Tornar not nullable (se necessário)
    op.alter_column('users', 'new_field', nullable=False)
    
    # 4. Remover coluna antiga (se necessário)
    # op.drop_column('users', 'old_field')
```

### 5. Indexes e Performance

```python
def upgrade() -> None:
    # Criar índice com CREATE INDEX CONCURRENTLY (não bloqueia)
    op.create_index(
        'idx_users_email',
        'users',
        ['email'],
        postgresql_concurrently=True  # PostgreSQL específico
    )

def downgrade() -> None:
    op.drop_index('idx_users_email', 'users')
```

### 6. Migrations Grandes

```python
def upgrade() -> None:
    # Para operações grandes, use batches
    connection = op.get_bind()
    
    # Processar em lotes de 1000
    batch_size = 1000
    offset = 0
    
    while True:
        result = connection.execute(
            sa.text(f"""
                UPDATE users 
                SET processed = true 
                WHERE id IN (
                    SELECT id FROM users 
                    WHERE processed = false 
                    LIMIT {batch_size}
                )
            """)
        )
        
        if result.rowcount == 0:
            break
        
        offset += batch_size
```

## 🚨 Regras Críticas

### ❌ NUNCA FAÇA:

1. **Nunca edite migrations já aplicadas em produção**
   ```bash
   # ❌ ERRADO: Editar migration já aplicada
   # ✅ CORRETO: Criar nova migration com correção
   ```

2. **Nunca remova migrations aplicadas**
   ```bash
   # ❌ ERRADO: Deletar arquivo de migration
   # ✅ CORRETO: Criar migration de rollback
   ```

3. **Nunca aplique migrations sem backup**
   ```bash
   # ❌ ERRADO: alembic upgrade head (em produção sem backup)
   # ✅ CORRETO: Fazer backup primeiro
   pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME > backup_before_migration.sql
   alembic upgrade head
   ```

4. **Nunca faça operações destrutivas sem confirmação**
   ```python
   # ❌ ERRADO
   def upgrade():
       op.drop_table('important_data')
   
   # ✅ CORRETO
   def upgrade():
       # Primeiro criar backup ou nova tabela
       op.execute("CREATE TABLE important_data_backup AS SELECT * FROM important_data")
       op.drop_table('important_data')
   ```

### ✅ SEMPRE FAÇA:

1. **Sempre teste localmente primeiro**
2. **Sempre implemente downgrade()**
3. **Sempre documente mudanças complexas**
4. **Sempre revise auto-generated migrations**
5. **Sempre faça backup antes de aplicar em produção**

## 🔄 Workflow de Development

### 1. Feature Branch

```bash
# 1. Criar branch
git checkout -b feature/add-user-metadata

# 2. Modificar models
# Edit app/models/user.py

# 3. Gerar migration
alembic revision --autogenerate -m "Add user metadata fields"

# 4. Revisar migration gerada
cat alembic/versions/<revision>_add_user_metadata.py

# 5. Testar localmente
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# 6. Commit
git add alembic/versions/<revision>_add_user_metadata.py
git commit -m "feat(migrations): add user metadata fields"

# 7. Push e criar PR
git push origin feature/add-user-metadata
```

### 2. Code Review

Revisor deve verificar:
- [ ] Migration tem upgrade() e downgrade()
- [ ] Operações são idempotentes
- [ ] Dados são preservados
- [ ] Performance é aceitável
- [ ] Documentação está clara
- [ ] Testes passam

### 3. Deploy

```bash
# 1. Fazer backup do banco
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Ver migrations pendentes
alembic current
alembic history

# 3. Aplicar migrations
alembic upgrade head

# 4. Verificar aplicação
alembic current

# 5. Testar aplicação
curl http://localhost:8000/health

# 6. Se problemas, rollback
alembic downgrade -1
```

## 🐛 Troubleshooting

### Problema: "Target database is not up to date"

```bash
# Ver versão atual
alembic current

# Ver histórico
alembic history

# Forçar stamp (CUIDADO!)
alembic stamp head
```

### Problema: "Can't locate revision identified by..."

```bash
# Verificar arquivo de migration existe
ls alembic/versions/

# Re-clonar repositório se arquivo falta
git pull origin main

# Verificar branches desatualizadas
git fetch --all
```

### Problema: Migration falhando

```bash
# Ver erro detalhado
alembic upgrade head --verbose

# Tentar manualmente no psql
psql $DATABASE_URL
# Executar comandos SQL da migration manualmente

# Marcar como aplicada (se já aplicou manualmente)
alembic stamp <revision_id>
```

### Problema: Conflito de Branches

```bash
# Duas migrations com mesmo parent
# Resolver com merge

# Criar migration de merge
alembic merge -m "Merge migrations" <rev1> <rev2>

# Aplicar
alembic upgrade head
```

## 📊 Monitoring em Produção

### Health Check de Migrations

```python
# app/api/v1/health.py
from alembic import command
from alembic.config import Config

@router.get("/migrations/status")
async def migration_status():
    """Check migration status."""
    try:
        alembic_cfg = Config("alembic.ini")
        # Get current version
        # Return status
        return {"status": "up-to-date", "version": current_version}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### Alertas

Configure alertas para:
- ⚠️ Migrations pendentes em produção
- ⚠️ Falhas de migration
- ⚠️ Tempo de execução > 5 minutos
- ⚠️ Downgrade aplicado em produção

## 📚 Recursos Adicionais

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Core](https://docs.sqlalchemy.org/en/14/core/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## 🆘 Suporte

Se tiver problemas com migrations:

1. Verifique logs: `alembic upgrade head --verbose`
2. Consulte esta documentação
3. Verifique issues conhecidos no repositório
4. Contate o time de backend

---

**Última Atualização**: Janeiro 2024  
**Versão**: 1.0  
**Autor**: Sistema Hormonia - Backend Team