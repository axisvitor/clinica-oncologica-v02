# 🗃️ Estratégia de Deploy do Banco de Dados - Railway/Supabase

## 🎯 TL;DR (Resumo Executivo)

**Você NÃO precisa executar migrations!**

Você tem o arquivo `SCHEMA_MASTER_COMPLETO.sql` que já contém **TUDO**:
- Todas as 41 tabelas
- Todos os 110+ índices
- Todas as 10 ENUMs
- Todas as 5 materialized views
- Todas as funções e triggers
- Todas as políticas RLS

**Basta executar 1 único arquivo no Supabase SQL Editor.**

---

## 📊 Situação Atual

### Arquivos Disponíveis

```
backend-hormonia/sql/
├── SCHEMA_MASTER_COMPLETO.sql (66 KB) ← **ESTE É O QUE IMPORTA**
└── migrations/ (88 KB total) ← **PODEM SER DELETADOS**
    ├── 002_incremental_rls_rollout.sql (12 KB)
    ├── 003_rls_phase2_write_policies.sql (20 KB)
    ├── 20251002_add_auth_provider_enum.sql (4 KB)
    ├── 20251002_fix_rls_users_select.sql (4.5 KB)
    ├── 20251004_add_admin_rls_policies.sql (15 KB)
    ├── 20251004_add_foreign_key_cascade_rules.sql (17 KB)
    ├── 20251004_add_gin_indexes_jsonb.sql (11 KB)
    └── 20251004_expand_message_type_enum.sql (4.4 KB)
```

---

## 🤔 Por Que Temos Migrations E SCHEMA_MASTER_COMPLETO.sql?

### Analogia: Casa Pronta vs. Manual de Construção

**Migrations (pasta migrations/):**
```
📘 Manual de construção passo a passo:
Step 1: Construir fundação
Step 2: Erguer paredes
Step 3: Instalar telhado
Step 4: Pintar paredes
Step 5: Instalar portas
Step 6: Instalar janelas
Step 7: Fazer acabamento
Step 8: Paisagismo
```

**SCHEMA_MASTER_COMPLETO.sql:**
```
🏠 Casa completamente pronta:
✅ Fundação construída
✅ Paredes erguidas
✅ Telhado instalado
✅ Paredes pintadas
✅ Portas instaladas
✅ Janelas instaladas
✅ Acabamento feito
✅ Paisagismo completo

PRONTO PARA MORAR!
```

---

## ✅ O Que É SCHEMA_MASTER_COMPLETO.sql?

É um **snapshot completo** do banco de dados após **todas as 59 migrations** terem sido aplicadas.

### Conteúdo (linhas 1-1670):

```sql
-- ============================================================================
-- SCHEMA MASTER COMPLETO - CLÍNICA ONCOLÓGICA HORMONIA
-- ============================================================================
-- Versão: 2.2
-- Data: 2025-10-04
-- Última Atualização: 2025-10-04 (Quiz schema cleanup + materialized views rebuild)
-- Total de migrations: 59 (56 anteriores + 3 novas aplicadas em 2025-10-04)
-- ============================================================================

-- SEÇÃO 1: EXTENSÕES (4 extensões)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- SEÇÃO 2: ENUMS E TIPOS CUSTOMIZADOS (10 enums)
CREATE TYPE user_role AS ENUM ('doctor', 'admin');
CREATE TYPE flow_state AS ENUM ('onboarding', 'active', 'paused', 'completed', 'inactive');
CREATE TYPE message_direction AS ENUM ('inbound', 'outbound');
CREATE TYPE message_type AS ENUM ('text', 'button', 'list', 'media', ...); -- 13 valores
-- ... mais 6 enums

-- SEÇÃO 3: TABELAS CORE DO SISTEMA (6 tabelas)
CREATE TABLE users (...);
CREATE TABLE patients (...);
CREATE TABLE messages (...);
CREATE TABLE message_status_events (...);
CREATE TABLE webhook_events (...);
CREATE TABLE alerts (...);

-- SEÇÃO 4: TABELAS DE FLOW MANAGEMENT (9 tabelas)
CREATE TABLE flow_kinds (...);
CREATE TABLE flow_template_versions (...);
-- ... mais 7 tabelas

-- SEÇÃO 5: TABELAS DE QUIZ SYSTEM (6 tabelas)
CREATE TABLE quiz_templates (...);
CREATE TABLE quiz_sessions (...); -- Schema v2 com status-based
CREATE TABLE quiz_responses (...);
-- ... mais 3 tabelas + 5 materialized views

-- SEÇÃO 6: TABELAS DE ANALYTICS (2 tabelas)
CREATE TABLE medical_reports (...);

-- SEÇÃO 7: TABELAS DO SISTEMA ADMIN (10 tabelas)
CREATE TABLE admin_users (...);
CREATE TABLE admin_permissions (...);
-- ... mais 8 tabelas

-- SEÇÃO 8: TABELAS DE METADATA & SISTEMA (6 tabelas)
CREATE TABLE user_profiles (...);
CREATE TABLE audit_trail (...);
-- ... mais 4 tabelas

-- SEÇÃO 9: FUNÇÕES E TRIGGERS
CREATE FUNCTION update_updated_at_column() ...;
CREATE FUNCTION cleanup_old_audit_trail() ...;
-- ... mais funções
```

**Total:**
- ✅ 41 tabelas
- ✅ 110+ índices (incluindo 14 GIN indexes)
- ✅ 10 ENUMs
- ✅ 5 materialized views
- ✅ 12+ triggers
- ✅ 6+ funções

---

## 🚀 Como Fazer Deploy do Banco (MÉTODO CORRETO)

### Opção 1: Supabase SQL Editor (RECOMENDADO)

```
1. Acesse: https://app.supabase.com
2. Selecione seu projeto
3. Vá em: SQL Editor (menu lateral)
4. Clique em "New Query"
5. Abra SCHEMA_MASTER_COMPLETO.sql no VS Code
6. Copie TODO o conteúdo (1.670 linhas)
7. Cole no SQL Editor
8. Clique em "Run" (▶️)
9. Aguarde ~30-60 segundos
10. Verifique se executou sem erros
```

**Output esperado:**
```
✅ Created 4 extensions
✅ Created 10 custom types
✅ Created 41 tables
✅ Created 110+ indexes
✅ Created 5 materialized views
✅ Created 6 functions
✅ Created 12 triggers

Query executed successfully in 45.2s
```

### Opção 2: Supabase CLI

```bash
# 1. Fazer login
supabase login

# 2. Linkar com seu projeto
supabase link --project-ref seu-projeto-id

# 3. Executar o schema completo
supabase db execute --file backend-hormonia/sql/SCHEMA_MASTER_COMPLETO.sql
```

### Opção 3: psql (Avançado)

```bash
# Se você tem acesso direto ao PostgreSQL
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres" \
  -f backend-hormonia/sql/SCHEMA_MASTER_COMPLETO.sql
```

---

## ❓ E As Migrations? Posso Deletar?

### SIM, você pode deletar a pasta `migrations/`!

**Por quê?**

1. **SCHEMA_MASTER_COMPLETO.sql já contém tudo** que as migrations fazem
2. Migrations são úteis para **desenvolvimento incremental**, mas você já tem o resultado final
3. Migrations foram aplicadas durante desenvolvimento, e o resultado foi consolidado no SCHEMA_MASTER_COMPLETO.sql

### Quando Manter Migrations?

Mantenha migrations se:
- ✅ Você tem múltiplos ambientes (dev, staging, prod) e precisa aplicar mudanças incrementais
- ✅ Você usa ferramentas como Alembic/Flyway que gerenciam migrations automaticamente
- ✅ Você precisa rastrear histórico de mudanças para auditoria

### Quando Deletar Migrations?

Delete migrations se:
- ✅ Você está fazendo deploy inicial (banco vazio)
- ✅ Você tem SCHEMA_MASTER_COMPLETO.sql atualizado
- ✅ Você não precisa de histórico incremental
- ✅ Você quer simplificar deploy

---

## 📋 Procedimento Recomendado

### Opção A: Manter Ambos (Conservador)

```bash
# Estrutura:
backend-hormonia/sql/
├── SCHEMA_MASTER_COMPLETO.sql  # Para deploy inicial
└── migrations/                  # Para referência histórica (não usar)
    └── *.sql (mover para docs/database/migrations_archive/)
```

### Opção B: Usar Apenas SCHEMA_MASTER (Simplificado)

```bash
# Estrutura:
backend-hormonia/sql/
└── SCHEMA_MASTER_COMPLETO.sql  # Único arquivo necessário

# Deletar:
rm -rf backend-hormonia/sql/migrations/
```

**Recomendo Opção B para você** porque:
- ✅ Deploy mais simples (1 arquivo vs 8 arquivos)
- ✅ Sem risco de executar migrations fora de ordem
- ✅ SCHEMA_MASTER_COMPLETO.sql está atualizado (2025-10-04)
- ✅ Reduz confusão na documentação

---

## 🎯 Passo a Passo Completo de Deploy

### 1️⃣ Preparação (Antes do Deploy)

```bash
# Verificar se SCHEMA_MASTER_COMPLETO.sql existe
ls -lh backend-hormonia/sql/SCHEMA_MASTER_COMPLETO.sql
# Output: -rw-r--r-- 1 user 197609 66K out  4 11:27 SCHEMA_MASTER_COMPLETO.sql

# Opcional: Deletar migrations antigas
rm -rf backend-hormonia/sql/migrations/
```

### 2️⃣ Deploy do Backend no Railway

```bash
# Railway detecta automaticamente o Dockerfile
# Backend sobe SEM criar tabelas (banco ainda vazio)
```

### 3️⃣ Criar Schema no Supabase

```
1. Acesse Supabase Dashboard
2. SQL Editor → New Query
3. Copie/cole SCHEMA_MASTER_COMPLETO.sql
4. Run (▶️)
5. Aguarde confirmação de sucesso
```

### 4️⃣ Validar Schema

```sql
-- Verificar tabelas criadas (deve retornar 41)
SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema = 'public';

-- Verificar índices criados (deve retornar 110+)
SELECT COUNT(*) FROM pg_indexes
WHERE schemaname = 'public';

-- Verificar materialized views (deve retornar 5)
SELECT COUNT(*) FROM pg_matviews
WHERE schemaname = 'public';

-- Testar uma query simples
SELECT COUNT(*) FROM users;
-- Output: 0 (tabela vazia, mas existente)
```

### 5️⃣ Deploy do Frontend no Railway

```bash
# Frontend sobe normalmente
# BACKEND_URL aponta para backend Railway
```

### 6️⃣ Smoke Test

```bash
# Testar health check
curl https://backend-hormonia.railway.app/health

# Testar criação de usuário (via Postman/Insomnia)
POST https://backend-hormonia.railway.app/api/v1/auth/register
{
  "email": "teste@clinica.com",
  "password": "senha123",
  "full_name": "Dr. Teste"
}
```

---

## ⚠️ Erros Comuns

### Erro 1: "relation already exists"

**Causa**: Você tentou executar SCHEMA_MASTER_COMPLETO.sql 2 vezes

**Solução**:
```sql
-- Dropar tudo e recomeçar
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;

-- Agora execute SCHEMA_MASTER_COMPLETO.sql novamente
```

### Erro 2: "permission denied for schema public"

**Causa**: Permissões incorretas

**Solução**:
```sql
-- Conceder permissões
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO anon;
GRANT ALL ON SCHEMA public TO authenticated;
GRANT ALL ON SCHEMA public TO service_role;
```

### Erro 3: Backend não conecta ao banco

**Causa**: SUPABASE_URL ou SUPABASE_SERVICE_KEY incorretos

**Solução**:
```bash
# Verificar variáveis no Railway
railway variables

# Atualizar se necessário
railway variables set SUPABASE_URL=https://...
railway variables set SUPABASE_SERVICE_KEY=eyJ...
```

---

## 📊 Comparação: Migrations vs SCHEMA_MASTER

| Aspecto | Migrations (8 arquivos) | SCHEMA_MASTER (1 arquivo) |
|---------|-------------------------|---------------------------|
| **Deploy Inicial** | ❌ Executar 8 arquivos em ordem | ✅ Executar 1 arquivo |
| **Risco de Erro** | ⚠️ Alto (ordem incorreta) | ✅ Baixo (arquivo único) |
| **Tempo de Execução** | ⏱️ ~2-3 minutos | ⏱️ ~30-60 segundos |
| **Simplicidade** | ❌ Complexo (8 passos) | ✅ Simples (1 passo) |
| **Manutenção** | ⚠️ Difícil (múltiplos arquivos) | ✅ Fácil (arquivo único) |
| **Histórico** | ✅ Rastreável | ❌ Snapshot consolidado |
| **Ideal Para** | Desenvolvimento incremental | Deploy inicial/produção |

---

## 🎓 Conclusão

### Você Deve:

1. ✅ **Usar SCHEMA_MASTER_COMPLETO.sql para deploy inicial**
2. ✅ **Executar 1 único arquivo no Supabase SQL Editor**
3. ✅ **Deletar pasta migrations/ para simplificar** (opcional, mas recomendado)
4. ✅ **Validar com queries de verificação**

### Você NÃO Deve:

1. ❌ **Executar migrations individuais**
2. ❌ **Se preocupar com ordem de execução**
3. ❌ **Aplicar migrations incrementais em banco vazio**

---

## 📞 Próximos Passos

Agora que você entendeu, o fluxo correto é:

```
1. Deploy Backend no Railway (código Python) ✅
2. Executar SCHEMA_MASTER_COMPLETO.sql no Supabase (1 arquivo) ✅
3. Deploy Frontend no Railway ✅
4. Atualizar CORS no backend (.env) ✅
5. Smoke test completo ✅

DEPLOY COMPLETO!
```

**Tempo estimado**: 15-20 minutos (vs 45-60 minutos com migrations)

---

**Tem alguma dúvida sobre SCHEMA_MASTER_COMPLETO.sql vs migrations?**
