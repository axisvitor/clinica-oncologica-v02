# Guia de Migração: Supabase → Railway PostgreSQL

## 📋 Visão Geral

Este guia detalha a migração do Supabase para Railway com **PostgreSQL em deploy separado**.

**Arquitetura:**
- **Service 1:** Backend FastAPI (Python)
- **Service 2:** PostgreSQL Database (separado)
- **Service 3:** Redis (opcional, pode usar Redis Cloud)

**Tempo estimado:** 2-3 horas
**Downtime:** ~15 minutos (durante migração de dados)

---

## 🎯 Pré-requisitos

### 1. Ferramentas Necessárias
```bash
# Railway CLI
npm install -g @railway/cli

# PostgreSQL client tools
# Windows: https://www.postgresql.org/download/windows/
# Mac: brew install postgresql
# Linux: sudo apt install postgresql-client

# Verificar instalação
railway --version
psql --version
pg_dump --version
```

### 2. Acessos Necessários
- [ ] Conta Railway (https://railway.app)
- [ ] Acesso ao Supabase (para backup)
- [ ] Credenciais do banco atual (`DATABASE_URL`)

---

## 📊 FASE 1: Análise e Backup

### 1.1 Analisar Configuração Atual

```bash
# Verificar tamanho do banco
psql $DATABASE_URL -c "SELECT
    pg_size_pretty(pg_database_size(current_database())) as db_size,
    count(*) as table_count
FROM information_schema.tables
WHERE table_schema = 'public';"

# Listar extensões PostgreSQL usadas
psql $DATABASE_URL -c "SELECT * FROM pg_extension;"

# Verificar versão PostgreSQL
psql $DATABASE_URL -c "SELECT version();"
```

**Resultado esperado:**
```
Database size: ~50-200MB
Tables: 41 tabelas
Extensions: uuid-ossp, pgcrypto, pg_trgm, pg_stat_statements
PostgreSQL: 15.x ou 16.x
```

### 1.2 Backup Completo do Supabase

```bash
# Criar diretório de backup
mkdir -p backups/$(date +%Y%m%d)
cd backups/$(date +%Y%m%d)

# Backup completo (schema + dados)
pg_dump $DATABASE_URL \
  --format=custom \
  --verbose \
  --file=hormonia_backup_$(date +%Y%m%d_%H%M%S).dump

# Backup SQL (para auditoria)
pg_dump $DATABASE_URL \
  --format=plain \
  --verbose \
  --file=hormonia_backup_$(date +%Y%m%d_%H%M%S).sql

# Verificar backup
ls -lh *.dump *.sql
```

**⚠️ CRÍTICO:** Teste o backup antes de prosseguir:
```bash
# Criar banco temporário local
createdb hormonia_test

# Restaurar backup
pg_restore -d hormonia_test hormonia_backup_*.dump

# Verificar dados
psql hormonia_test -c "SELECT count(*) FROM users;"
psql hormonia_test -c "SELECT count(*) FROM patients;"

# Limpar
dropdb hormonia_test
```

---

## 🚀 FASE 2: Configurar Railway

### 2.1 Criar Conta e Projeto Railway

```bash
# Login
railway login

# Criar novo projeto
railway init

# Nome sugerido: clinica-oncologica-hormonia
```

### 2.2 Provisionar PostgreSQL (Deploy Separado)

**Opção A: Via Railway Dashboard (Recomendado)**
1. Acesse https://railway.app/dashboard
2. Selecione seu projeto
3. Clique em **"+ New Service"**
4. Selecione **"Database" → "PostgreSQL"**
5. Aguarde provisionamento (~2 minutos)

**Opção B: Via CLI**
```bash
railway add --plugin postgres
```

### 2.3 Obter Credenciais Railway PostgreSQL

```bash
# Listar variáveis do PostgreSQL
railway variables --service postgres

# Salvar DATABASE_URL
railway variables --service postgres | grep DATABASE_URL
```

**Formato esperado:**
```
DATABASE_URL=postgresql://postgres:PASSWORD@containers-us-west-XXX.railway.app:PORT/railway
```

### 2.4 Configurar Extensões PostgreSQL

```bash
# Conectar ao Railway PostgreSQL
railway run --service postgres psql $DATABASE_URL

# Criar extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

# Verificar
\dx

# Sair
\q
```

---

## 📦 FASE 3: Migração de Dados

### 3.1 Restaurar Backup no Railway

```bash
# Método 1: Restaurar .dump (Recomendado - mais rápido)
pg_restore \
  --verbose \
  --no-owner \
  --no-acl \
  --dbname=$RAILWAY_DATABASE_URL \
  hormonia_backup_*.dump

# Método 2: Restaurar .sql (se .dump falhar)
psql $RAILWAY_DATABASE_URL < hormonia_backup_*.sql
```

### 3.2 Verificar Migração de Dados

```bash
# Conectar ao Railway PostgreSQL
psql $RAILWAY_DATABASE_URL

# Verificar contagem de registros
SELECT
    schemaname,
    tablename,
    n_tup_ins as total_rows
FROM pg_stat_user_tables
ORDER BY n_tup_ins DESC;

# Comparar com Supabase
# Execute a mesma query no Supabase e compare os números

# Verificar integridade das Foreign Keys
SELECT
    conname as constraint_name,
    conrelid::regclass as table_name
FROM pg_constraint
WHERE contype = 'f';

# Sair
\q
```

### 3.3 Executar Migrations (Alembic)

```bash
# Atualizar DATABASE_URL temporariamente para Railway
export DATABASE_URL=$RAILWAY_DATABASE_URL

# Verificar status das migrations
cd backend-hormonia
alembic current

# Se necessário, executar migrations pendentes
alembic upgrade head

# Verificar
alembic current
```

---

## ⚙️ FASE 4: Configurar Backend no Railway

### 4.1 Deploy do Backend FastAPI

```bash
# No diretório backend-hormonia
railway link  # Selecione o projeto criado

# Criar service para backend
# Via Dashboard: "+ New Service" → "GitHub Repo" ou "Empty Service"
```

### 4.2 Configurar Variáveis de Ambiente

**Via Railway Dashboard:**
1. Selecione o service "backend"
2. Vá em **"Variables"**
3. Adicione as seguintes variáveis:

```bash
# Database (usar Railway PostgreSQL)
DATABASE_URL=postgresql+psycopg://postgres:PASSWORD@containers-us-west-XXX.railway.app:PORT/railway?sslmode=require

# IMPORTANTE: Railway PostgreSQL usa sslmode=require por padrão
# Se falhar, tente: ?sslmode=prefer

# Application
DEBUG=false
ENVIRONMENT=production
SECRET_KEY=your-super-secret-key-change-this
JWT_SECRET_KEY=your-jwt-secret-key-change-this
ENCRYPTION_KEY=your-encryption-key-32-chars

# CORS
FRONTEND_URL=https://seu-frontend.railway.app
QUIZ_URL=https://seu-quiz.railway.app
ALLOWED_ORIGINS=https://seu-frontend.railway.app,https://seu-quiz.railway.app

# Redis (Railway Redis ou Redis Cloud)
REDIS_URL=rediss://default:PASSWORD@redis.railway.internal:6379
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required

# Firebase (manter suas configurações atuais)
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_PRIVATE_KEY=your-private-key
FIREBASE_ADMIN_CLIENT_EMAIL=your-service-account@project.iam.gserviceaccount.com

# Evolution API WhatsApp (manter configurações atuais)
EVOLUTION_API_URL=https://your-evolution-api.com
EVOLUTION_API_KEY=your-api-key

# Gemini AI (manter configurações atuais)
GEMINI_API_KEY=your-gemini-api-key

# Security
SESSION_COOKIE_SECURE=true
SECURE_SSL_REDIRECT=true

# REMOVER estas variáveis Supabase:
# SUPABASE_URL (não usar mais)
# SUPABASE_ANON_KEY (não usar mais)
# SUPABASE_SERVICE_ROLE_KEY (não usar mais)
```

**Via CLI:**
```bash
railway variables --service backend set DATABASE_URL="postgresql+psycopg://..."
railway variables --service backend set DEBUG=false
railway variables --service backend set ENVIRONMENT=production
# ... adicione todas as outras
```

### 4.3 Configurar railway.toml

Criar arquivo `railway.toml` na raiz do backend:

```toml
[build]
builder = "nixpacks"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "on-failure"
restartPolicyMaxRetries = 10

[env]
PYTHONUNBUFFERED = "1"
PORT = "8000"
```

### 4.4 Deploy Backend

```bash
# Via CLI
railway up --service backend

# Ou via GitHub (Recomendado)
# 1. Push código para GitHub
# 2. Conectar repositório no Railway Dashboard
# 3. Railway faz deploy automático
```

---

## 🔧 FASE 5: Remover Dependências do Supabase

### 5.1 Atualizar app/config.py

```bash
cd backend-hormonia
```

Editar [app/config.py](app/config.py):

```python
# REMOVER estas linhas:
# SUPABASE_URL: str = Field(...)
# SUPABASE_ANON_KEY: str = Field(...)
# SUPABASE_SERVICE_ROLE_KEY: str = Field(...)
# AUTO_PROVISION_SUPABASE_USERS: bool = Field(...)
# SUPABASE_USE_SERVICE_ROLE: bool = Field(...)
# SUPABASE_BYPASS_RLS: bool = Field(...)
# SUPABASE_JWT_HEADER_NAME: str = Field(...)
# SUPABASE_JWT_PREFIX: str = Field(...)

# REMOVER função:
# def get_supabase_config():
#     ...
```

### 5.2 Remover Imports Supabase

```bash
# Buscar arquivos que importam supabase
grep -r "from supabase" backend-hormonia/app/ --include="*.py"
grep -r "import supabase" backend-hormonia/app/ --include="*.py"

# Total encontrado: 15 arquivos
```

**Arquivos que precisam ser atualizados:**
1. `app/database.py` - Remover import supabase
2. `app/api/v1/auth.py` - Remover lógica Supabase Auth
3. `app/core/database.py` - Remover client supabase
4. Outros arquivos conforme necessário

### 5.3 Remover Dependência do requirements.txt

Editar `requirements.txt`:
```bash
# REMOVER linha:
# supabase>=2.3.4,<3.0.0
```

### 5.4 Atualizar .env.example

```bash
# REMOVER seções Supabase:
# - SUPABASE_URL
# - SUPABASE_ANON_KEY
# - SUPABASE_SERVICE_ROLE_KEY
# - SUPABASE_USE_SERVICE_ROLE
# - SUPABASE_BYPASS_RLS
# - SUPABASE_JWT_HEADER_NAME
# - SUPABASE_JWT_PREFIX
```

---

## ✅ FASE 6: Testes e Validação

### 6.1 Testes de Conexão

```bash
# Teste conexão Railway PostgreSQL
psql $RAILWAY_DATABASE_URL -c "SELECT count(*) FROM users;"
psql $RAILWAY_DATABASE_URL -c "SELECT count(*) FROM patients;"

# Teste backend Railway
curl https://seu-backend.railway.app/health
curl https://seu-backend.railway.app/api/v1/config/health
```

### 6.2 Testes Funcionais

```bash
# Login
curl -X POST https://seu-backend.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"senha"}'

# Listar pacientes (com token)
curl https://seu-backend.railway.app/api/v1/patients \
  -H "Authorization: Bearer $TOKEN"

# Criar paciente de teste
curl -X POST https://seu-backend.railway.app/api/v1/patients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone":"+5511999999999","name":"Teste Migração"}'
```

### 6.3 Checklist de Validação

- [ ] ✅ Todas as 41 tabelas migradas
- [ ] ✅ Contagem de registros idêntica ao Supabase
- [ ] ✅ Extensões PostgreSQL ativas
- [ ] ✅ Foreign Keys intactas
- [ ] ✅ Índices criados
- [ ] ✅ Triggers funcionando
- [ ] ✅ RLS policies ativas (se usado)
- [ ] ✅ Backend conecta ao Railway PostgreSQL
- [ ] ✅ Login funciona
- [ ] ✅ CRUD de pacientes funciona
- [ ] ✅ Firebase Auth integrado
- [ ] ✅ Redis funcionando
- [ ] ✅ Celery tasks executando
- [ ] ✅ Evolution API WhatsApp conectado
- [ ] ✅ Gemini AI respondendo

---

## 🔄 FASE 7: Plano de Rollback

### Se algo der errado durante a migração:

```bash
# 1. Reverter DATABASE_URL para Supabase
railway variables --service backend set DATABASE_URL="$SUPABASE_DATABASE_URL"

# 2. Redeploy backend
railway up --service backend

# 3. Verificar funcionamento
curl https://seu-backend.railway.app/health
```

### Backup de Emergência

```bash
# Backup Railway PostgreSQL (caso precise voltar)
pg_dump $RAILWAY_DATABASE_URL > railway_backup_$(date +%Y%m%d_%H%M%S).sql
```

---

## 💰 Estimativa de Custos Railway

### PostgreSQL Database
- **Starter:** $5/mês (512MB RAM, 1GB storage)
- **Pro:** $10/mês (1GB RAM, 10GB storage)
- **Scale:** $20+/mês (custom)

### Backend Service
- **Starter:** $5/mês (512MB RAM)
- **Pro:** $10/mês (1GB RAM)

### Redis (opcional)
- **Usar Redis Cloud Free:** $0/mês (30MB)
- **Railway Redis:** $5/mês

**Total Estimado:** $10-25/mês (vs Supabase $25-50/mês)

---

## 📝 Próximos Passos

1. **Monitoring:**
   - Configurar Sentry (já no requirements.txt)
   - Habilitar Railway Metrics
   - Configurar alertas de downtime

2. **Backups Automáticos:**
   ```bash
   # Configurar backup diário no Railway
   # Dashboard → PostgreSQL Service → Settings → Backups
   ```

3. **CI/CD:**
   - GitHub Actions para testes automáticos
   - Deploy automático via Railway GitHub integration

4. **Performance:**
   - Ativar Railway shared CPU → dedicated CPU se necessário
   - Configurar connection pooling (PgBouncer)

---

## 🆘 Troubleshooting

### Erro: SSL connection required
```bash
# Adicionar sslmode à connection string
DATABASE_URL="...?sslmode=require"
```

### Erro: Too many connections
```bash
# Reduzir pool size no config.py
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
```

### Erro: Extension uuid-ossp not found
```bash
# Instalar manualmente
psql $RAILWAY_DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
```

### Erro: Permission denied for schema public
```bash
# Dar permissões ao usuário Railway
psql $RAILWAY_DATABASE_URL -c "GRANT ALL ON SCHEMA public TO postgres;"
```

---

## 📞 Suporte

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- PostgreSQL Docs: https://www.postgresql.org/docs/

---

**Criado em:** 2025-10-07
**Última Atualização:** 2025-10-07
**Versão:** 1.0.0
