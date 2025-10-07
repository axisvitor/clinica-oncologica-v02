# 🚀 GUIA: Aplicar Migração Alembic Firebase no Supabase (PRODUÇÃO)

**Data:** 2025-10-07
**Arquivo Migration:** `backend-hormonia/alembic/versions/20250930_add_firebase_fields.py`
**Severidade:** 🔴 **CRÍTICA** - Login vai falhar sem essa migração

---

## ⚠️ POR QUE USAR ALEMBIC AO INVÉS DO SQL MANUAL?

A migração Alembic é **SUPERIOR** ao SQL manual porque:

1. ✅ Cria **tabela de auditoria** `user_sync_log` (faltando no SQL manual)
2. ✅ Índice unique **sem condição WHERE** (mais robusto)
3. ✅ Rastreamento de versão Alembic (facilita rollback)
4. ✅ Testado e validado no desenvolvimento

---

## 📋 PASSO A PASSO (Supabase Dashboard)

### 1️⃣ CONECTAR NO SUPABASE DASHBOARD

1. Acesse: https://supabase.com/dashboard
2. Selecione projeto: **clinica-oncologica-hormonia**
3. Navegue: **SQL Editor** (menu lateral esquerdo)

---

### 2️⃣ EXECUTAR MIGRATION SQL

**Copie e cole este SQL completo no SQL Editor:**

```sql
-- ============================================================================
-- FIREBASE AUTHENTICATION MIGRATION
-- ============================================================================
-- Source: backend-hormonia/alembic/versions/20250930_add_firebase_fields.py
-- Revision: add_firebase_fields
-- Date: 2025-09-30 16:54:00
-- ============================================================================

BEGIN;

-- Step 1: Add Firebase authentication columns
ALTER TABLE users
ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(255),
ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(50) NOT NULL DEFAULT 'local',
ADD COLUMN IF NOT EXISTS firebase_last_sign_in TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS firebase_created_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS firebase_email_verified BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS firebase_display_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS firebase_photo_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS firebase_custom_claims JSONB NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS last_firebase_sync TIMESTAMP WITH TIME ZONE;

-- Step 2: Make hashed_password nullable (Firebase users don't need password)
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- Step 3: Add unique constraint to firebase_uid
ALTER TABLE users ADD CONSTRAINT users_firebase_uid_key UNIQUE (firebase_uid);

-- Step 4: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid);
CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON users(auth_provider);

-- Step 5: Create audit table for sync operations
CREATE TABLE IF NOT EXISTS user_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(255) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    operation VARCHAR(50) NOT NULL,  -- create, update, link
    sync_direction VARCHAR(20) NOT NULL,  -- firebase_to_pg, pg_to_firebase
    changes JSONB NOT NULL DEFAULT '{}',
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Step 6: Create indexes for audit table
CREATE INDEX IF NOT EXISTS idx_user_sync_log_firebase_uid ON user_sync_log(firebase_uid);
CREATE INDEX IF NOT EXISTS idx_user_sync_log_user_id ON user_sync_log(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sync_log_created_at ON user_sync_log(created_at);

-- Step 7: Update Alembic version (se você usar Alembic em produção)
-- Se você NÃO tem tabela alembic_version, comente as linhas abaixo
INSERT INTO alembic_version (version_num)
VALUES ('add_firebase_fields')
ON CONFLICT (version_num) DO NOTHING;

COMMIT;
```

**Clique em "Run" para executar.**

---

### 3️⃣ VERIFICAR MIGRAÇÃO APLICADA

**Execute esta query de verificação:**

```sql
-- Verificar colunas criadas
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'users'
  AND column_name IN (
      'firebase_uid',
      'auth_provider',
      'firebase_custom_claims',
      'firebase_email_verified',
      'firebase_display_name',
      'firebase_photo_url',
      'firebase_last_sign_in',
      'firebase_created_at',
      'last_firebase_sync'
  )
ORDER BY ordinal_position;
```

**Resultado Esperado (9 linhas):**
```
column_name              | data_type                   | is_nullable | column_default
-------------------------+-----------------------------+-------------+----------------
firebase_uid             | character varying           | YES         | NULL
auth_provider            | character varying           | NO          | 'local'
firebase_last_sign_in    | timestamp with time zone    | YES         | NULL
firebase_created_at      | timestamp with time zone    | YES         | NULL
firebase_email_verified  | boolean                     | NO          | false
firebase_display_name    | character varying           | YES         | NULL
firebase_photo_url       | character varying           | YES         | NULL
firebase_custom_claims   | jsonb                       | NO          | '{}'
last_firebase_sync       | timestamp with time zone    | YES         | NULL
```

---

### 4️⃣ VERIFICAR ÍNDICES CRIADOS

```sql
-- Verificar índices
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'users'
  AND indexname LIKE '%firebase%'
ORDER BY indexname;
```

**Resultado Esperado (2-3 índices):**
```
indexname                      | indexdef
-------------------------------+--------------------------------------------------
idx_users_firebase_uid         | CREATE INDEX idx_users_firebase_uid ON...
idx_users_auth_provider        | CREATE INDEX idx_users_auth_provider ON...
users_firebase_uid_key         | CREATE UNIQUE INDEX users_firebase_uid_key ON...
```

---

### 5️⃣ VERIFICAR TABELA DE AUDITORIA

```sql
-- Verificar tabela user_sync_log criada
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'user_sync_log'
ORDER BY ordinal_position;
```

**Resultado Esperado (9 colunas):**
```
table_name      | column_name      | data_type
----------------+------------------+---------------------------
user_sync_log   | id               | uuid
user_sync_log   | firebase_uid     | character varying
user_sync_log   | user_id          | uuid
user_sync_log   | operation        | character varying
user_sync_log   | sync_direction   | character varying
user_sync_log   | changes          | jsonb
user_sync_log   | success          | boolean
user_sync_log   | error_message    | text
user_sync_log   | created_at       | timestamp with time zone
```

---

### 6️⃣ VERIFICAR CONSTRAINT hashed_password NULLABLE

```sql
-- Verificar hashed_password agora é nullable
SELECT
    column_name,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'users'
  AND column_name = 'hashed_password';
```

**Resultado Esperado:**
```
column_name      | is_nullable | column_default
-----------------+-------------+----------------
hashed_password  | YES         | NULL
```

✅ `is_nullable = YES` significa que usuários Firebase **NÃO PRECISAM** de senha local.

---

## ✅ CHECKLIST DE VALIDAÇÃO

Após executar a migration, confirme:

- [ ] ✅ **9 colunas Firebase** adicionadas na tabela `users`
- [ ] ✅ **2-3 índices** criados (`firebase_uid`, `auth_provider`)
- [ ] ✅ **Tabela `user_sync_log`** criada com 9 colunas
- [ ] ✅ **3 índices** na tabela `user_sync_log`
- [ ] ✅ **hashed_password** agora é `nullable = YES`
- [ ] ✅ **Constraint unique** em `firebase_uid`
- [ ] ✅ Nenhum erro retornado durante execução

---

## 🔄 ROLLBACK (SE NECESSÁRIO)

**Se precisar reverter a migração:**

```sql
BEGIN;

-- Drop audit table
DROP INDEX IF EXISTS idx_user_sync_log_created_at;
DROP INDEX IF EXISTS idx_user_sync_log_user_id;
DROP INDEX IF EXISTS idx_user_sync_log_firebase_uid;
DROP TABLE IF EXISTS user_sync_log;

-- Drop indexes
DROP INDEX IF EXISTS idx_users_auth_provider;
DROP INDEX IF EXISTS idx_users_firebase_uid;

-- Remove Firebase columns
ALTER TABLE users DROP COLUMN IF EXISTS last_firebase_sync;
ALTER TABLE users DROP COLUMN IF EXISTS firebase_custom_claims;
ALTER TABLE users DROP COLUMN IF EXISTS firebase_photo_url;
ALTER TABLE users DROP COLUMN IF EXISTS firebase_display_name;
ALTER TABLE users DROP COLUMN IF EXISTS firebase_email_verified;
ALTER TABLE users DROP COLUMN IF EXISTS firebase_created_at;
ALTER TABLE users DROP COLUMN IF EXISTS firebase_last_sign_in;
ALTER TABLE users DROP COLUMN IF EXISTS auth_provider;
ALTER TABLE users DROP COLUMN IF EXISTS firebase_uid;

-- Restore hashed_password as required
ALTER TABLE users ALTER COLUMN hashed_password SET NOT NULL;

-- Remove Alembic version
DELETE FROM alembic_version WHERE version_num = 'add_firebase_fields';

COMMIT;
```

---

## 🎯 PRÓXIMOS PASSOS

Após aplicar a migration:

1. ✅ Atualizar variáveis Railway (SSL configs)
2. ✅ Testar login flow end-to-end
3. ✅ Verificar sessão criada no Redis
4. ✅ Verificar user criado com `firebase_uid` populated
5. ✅ Escrever testes de integração

---

## 📞 SUPORTE

**Problemas durante execução:**
- Erro de permissão: Verificar se você é owner do projeto Supabase
- Constraint violation: Verificar se existem dados conflitantes na tabela users
- Timeout: Executar em partes (comentar seções e executar separadamente)

**Dúvidas:**
- Consulte: `docs/deployment/FIREBASE_REDIS_ARCHITECTURE.md`
- Revisar: `backend-hormonia/alembic/versions/20250930_add_firebase_fields.py`

---

**Tempo Estimado:** 5-10 minutos
**Risco:** Baixo (operação idempotente com `IF NOT EXISTS`)
**Impacto:** Alto (login VAI FALHAR sem essa migration)
