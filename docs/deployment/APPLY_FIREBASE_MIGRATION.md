# 🔧 Aplicar Migration de Campos Firebase

**Data:** 2025-10-07
**Status:** ⚠️ **CRÍTICO - Necessário para Login Funcionar**
**Prioridade:** 🔴 **ALTA**

---

## 📋 Problema Identificado

Durante a revisão do banco de dados, descobrimos que a migration **20250930_add_firebase_fields.py** existe no código mas **NÃO FOI APLICADA** no Supabase production.

**Sintomas:**
- Código Python tenta inserir em colunas `firebase_uid`, `auth_provider`, etc.
- Essas colunas **não existem** na tabela `users` no Supabase
- Resultado: **Login falha** com erro de coluna inexistente

---

## ✅ Solução: Aplicar Migration Manualmente

### Opção 1: Via Supabase Dashboard (RECOMENDADO)

1. **Acesse o Supabase Dashboard:**
   - URL: https://supabase.com/dashboard/project/YOUR_PROJECT_ID
   - Menu: **SQL Editor** → **New query**

2. **Cole o SQL abaixo:**

```sql
-- ============================================================
-- MIGRATION: Add Firebase Authentication Fields to Users Table
-- File: backend-hormonia/alembic/versions/20250930_add_firebase_fields.py
-- ============================================================

-- Step 1: Add Firebase authentication columns
ALTER TABLE users
ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(255) UNIQUE,
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

-- Step 3: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid) WHERE firebase_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON users(auth_provider);

-- Step 4: Create audit table for sync operations
CREATE TABLE IF NOT EXISTS user_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(255) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    operation VARCHAR(50) NOT NULL,  -- create, update, link
    sync_direction VARCHAR(20) NOT NULL,  -- firebase_to_pg, pg_to_firebase
    changes JSONB NOT NULL DEFAULT '{}',
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Step 5: Create indexes for audit table
CREATE INDEX IF NOT EXISTS idx_user_sync_log_firebase_uid ON user_sync_log(firebase_uid);
CREATE INDEX IF NOT EXISTS idx_user_sync_log_user_id ON user_sync_log(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sync_log_created_at ON user_sync_log(created_at);

-- Step 6: Add helpful comments
COMMENT ON COLUMN users.firebase_uid IS 'Firebase user UID from Firebase Authentication';
COMMENT ON COLUMN users.auth_provider IS 'Authentication provider: local (password) or firebase';
COMMENT ON COLUMN users.firebase_custom_claims IS 'Firebase custom claims including role and permissions';
COMMENT ON TABLE user_sync_log IS 'Audit log for Firebase user synchronization operations';

-- Step 7: Create trigger for updated_at on user_sync_log
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_sync_log_updated_at BEFORE UPDATE ON user_sync_log
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

3. **Execute a query** (botão **Run** ou `Ctrl+Enter`)

4. **Verifique o resultado:**
   - Deve retornar "Success. No rows returned" (normal para ALTER TABLE)
   - Não deve mostrar erros

### Opção 2: Via Supabase CLI (Alternativa)

```bash
# 1. Conectar ao projeto
supabase link --project-ref YOUR_PROJECT_REF

# 2. Aplicar migration
supabase db push

# 3. Verificar
supabase db diff
```

---

## 🔍 Verificar se Migration Foi Aplicada

Execute no **SQL Editor** do Supabase:

```sql
-- Verificar colunas da tabela users
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users'
ORDER BY ordinal_position;
```

**Resultado esperado:** Deve incluir as colunas:
- `firebase_uid` (VARCHAR 255, nullable)
- `auth_provider` (VARCHAR 50, NOT NULL, default 'local')
- `firebase_last_sign_in` (TIMESTAMP WITH TIME ZONE, nullable)
- `firebase_created_at` (TIMESTAMP WITH TIME ZONE, nullable)
- `firebase_email_verified` (BOOLEAN, NOT NULL, default false)
- `firebase_display_name` (VARCHAR 255, nullable)
- `firebase_photo_url` (VARCHAR 500, nullable)
- `firebase_custom_claims` (JSONB, NOT NULL, default '{}')
- `last_firebase_sync` (TIMESTAMP WITH TIME ZONE, nullable)

---

## ✅ Após Aplicar a Migration

1. **Verificar no Railway:**
   ```bash
   railway logs -s backend
   ```

   **Esperado:** Não deve mais ter erros de "column does not exist"

2. **Testar Login:**
   - Acesse: https://seu-frontend.railway.app/login
   - Tente fazer login com Firebase
   - Deve funcionar sem timeout ou erro 401

3. **Verificar usuário criado:**
   ```sql
   SELECT id, email, firebase_uid, auth_provider, role, is_active
   FROM users
   ORDER BY created_at DESC
   LIMIT 5;
   ```

---

## 🚨 Troubleshooting

### Erro: "column 'firebase_uid' already exists"

**Solução:** A migration já foi aplicada parcialmente. Execute apenas as linhas que faltam.

### Erro: "permission denied for table users"

**Solução:** Use o **service_role** key do Supabase (Settings → API → service_role key).

### Erro: "relation 'user_sync_log' already exists"

**Solução:** A tabela de auditoria já existe. Pule o `CREATE TABLE user_sync_log`.

---

## 📊 O Que Esta Migration Faz

### 1. Adiciona Campos Firebase (9 colunas)
```sql
firebase_uid              → UID do Firebase Authentication
auth_provider             → 'local' ou 'firebase'
firebase_last_sign_in     → Último login via Firebase
firebase_created_at       → Data criação conta Firebase
firebase_email_verified   → Email verificado?
firebase_display_name     → Nome de exibição Firebase
firebase_photo_url        → URL da foto do perfil
firebase_custom_claims    → Claims customizadas (role, permissions)
last_firebase_sync        → Última sincronização
```

### 2. Torna `hashed_password` Nullable
- Usuários Firebase **não precisam** de senha local
- Apenas usuários com `auth_provider='local'` terão senha

### 3. Cria Índices de Performance
```sql
idx_users_firebase_uid     → Busca rápida por Firebase UID
idx_users_auth_provider    → Filtrar por tipo de autenticação
```

### 4. Cria Tabela de Auditoria
```sql
user_sync_log → Registra todas operações de sincronização Firebase ↔ PostgreSQL
```

---

## 📝 Checklist de Aplicação

- [ ] Acessar Supabase Dashboard → SQL Editor
- [ ] Executar SQL da migration completa
- [ ] Verificar que não houve erros
- [ ] Confirmar que colunas foram criadas (query de verificação)
- [ ] Testar login no frontend
- [ ] Verificar logs do Railway (sem erros de coluna)
- [ ] Confirmar usuário criado no banco com `firebase_uid` preenchido

---

## 🎯 Próximo Passo Após Aplicar

Uma vez que a migration for aplicada:

1. **Backend detectará automaticamente** as novas colunas
2. **Login Firebase funcionará** criando usuários com:
   - `firebase_uid` preenchido
   - `auth_provider = 'firebase'`
   - `hashed_password = NULL`
   - Role extraída de `firebase_custom_claims`

3. **Autenticação será rápida** (< 1 segundo):
   - Fast-path: Usuario existe → retorna imediatamente
   - Slow-path: Usuario novo → cria registro mínimo e retorna

---

**Instruções criadas:** 2025-10-07 02:15 UTC
**Migration source:** backend-hormonia/alembic/versions/20250930_add_firebase_fields.py
**Status:** Aguardando aplicação manual no Supabase Dashboard
