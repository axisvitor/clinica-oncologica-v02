# Review Completa do Banco de Dados Supabase

**Data:** 2025-10-07 01:10
**Analyst:** Claude Code
**Status:** ✅ **Estrutura Correta com Pequenos Ajustes Necessários**

---

## 📊 Resumo Executivo

O banco de dados está **bem estruturado** com migrations adequadas via Alembic. Identificados alguns pontos de atenção:

### ✅ Pontos Positivos
- Enum `user_role` corrigido para lowercase (`doctor`, `admin`)
- Constraints e índices adequados
- RLS (Row Level Security) implementado
- Firebase integration fields presentes
- Audit logging system

### ⚠️ Pontos de Atenção
1. **Enum inicial tinha 3 valores** (`doctor`, `nurse`, `admin`) mas foi corrigido para 2
2. **Migrations precisam ser aplicadas** no Supabase production
3. **Falta coluna `auth_provider`** na tabela users (adicionada no model mas não na migration)

---

## 🗄️ Estrutura do Banco de Dados

### Tabela: `users` (Healthcare Providers)

**Propósito:** Armazenar médicos e administradores do sistema

#### Schema Atual (Migration 001)
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role user_role NOT NULL DEFAULT 'doctor',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

#### Campos Adicionais no Model Python (não na migration)
```python
# Firebase authentication fields
firebase_uid VARCHAR(255) UNIQUE  # ❌ FALTA NA MIGRATION
auth_provider auth_provider NOT NULL DEFAULT 'local'  # ❌ FALTA NA MIGRATION
firebase_last_sign_in TIMESTAMP WITH TIME ZONE
firebase_created_at TIMESTAMP WITH TIME ZONE
firebase_email_verified BOOLEAN DEFAULT false
firebase_display_name VARCHAR(255)
firebase_photo_url VARCHAR(500)
firebase_custom_claims JSONB DEFAULT '{}'
last_firebase_sync TIMESTAMP WITH TIME ZONE
```

### Tabela: `admin_users` (Sistema Administrativo Separado)

**Propósito:** Sistema administrativo completo com auditoria

```sql
CREATE TABLE admin_users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role admin_role_type NOT NULL DEFAULT 'supervisor',  -- super_admin, admin, manager, supervisor
    -- ... mais campos
);
```

**⚠️ ATENÇÃO:** Há **duas tabelas de usuários diferentes**:
- `users` → Healthcare providers (DOCTOR, ADMIN)
- `admin_users` → Sistema admin (super_admin, admin, manager, supervisor)

---

## 🔢 Enums Definidos

### 1. `user_role` (Healthcare Providers)

**Migração 004 (fix_user_role_enum.py):**
```sql
CREATE TYPE user_role AS ENUM ('doctor', 'admin');
```

**Status:** ✅ Correto - 2 valores apenas

**Histórico:**
- Migration 001: Tinha 3 valores (`'doctor', 'nurse', 'admin'`)
- Migration 004: Corrigido para 2 valores (`'doctor', 'admin'`)

### 2. `auth_provider` (Python Model)

**No código Python:**
```python
class AuthProvider(enum.Enum):
    LOCAL = "local"
    FIREBASE = "firebase"
```

**Status:** ❌ **FALTA CRIAR ENUM NO POSTGRES**

### 3. `admin_role_type` (Admin System)

**Migration supabase_admin_system_complete.sql:**
```sql
CREATE TYPE admin_role_type AS ENUM ('super_admin', 'admin', 'manager', 'supervisor');
```

**Status:** ✅ Correto

### 4. Outros Enums

```sql
-- Flow state for patients
CREATE TYPE flow_state AS ENUM ('onboarding', 'active', 'paused', 'completed', 'inactive');

-- Message management
CREATE TYPE message_direction AS ENUM ('inbound', 'outbound');
CREATE TYPE message_type AS ENUM ('text', 'button', 'list', 'media', 'location');
CREATE TYPE message_status AS ENUM ('pending', 'sent', 'delivered', 'read', 'failed');

-- Alerts
CREATE TYPE alert_severity AS ENUM ('low', 'medium', 'high', 'critical');

-- Admin system
CREATE TYPE severity_type AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE http_method_type AS ENUM ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD');
```

**Status:** ✅ Todos corretos

---

## 📋 Tabelas Principais

### Healthcare System Tables

1. **users** - Healthcare providers (doctors, admins)
2. **patients** - Hormone therapy patients
3. **messages** - WhatsApp communication
4. **flows** - Treatment flows/protocols
5. **flow_analytics** - Flow performance metrics
6. **ab_experiments** - A/B testing for flows
7. **alerts** - System alerts and notifications
8. **reports** - Medical reports
9. **quiz** - Patient questionnaires

### Admin System Tables

1. **admin_users** - Administrative users
2. **admin_permissions** - Permission system
3. **admin_roles** - Role definitions
4. **admin_sessions** - Session management
5. **admin_audit_logs** - Audit trail
6. **admin_login_history** - Login tracking
7. **admin_security_events** - Security monitoring

---

## 🔍 Problemas Identificados

### ❌ CRÍTICO: Campos Firebase Não Estão na Migration

**Model Python tem:**
```python
firebase_uid = Column(String(255), unique=True, nullable=True, index=True)
auth_provider = Column(Enum(AuthProvider, ...))
firebase_last_sign_in = Column(DateTime(timezone=True))
firebase_created_at = Column(DateTime(timezone=True))
firebase_email_verified = Column(Boolean, default=False)
firebase_display_name = Column(String(255))
firebase_photo_url = Column(String(500))
firebase_custom_claims = Column(JSONB, default={})
last_firebase_sync = Column(DateTime(timezone=True))
```

**Migration 001 NÃO tem esses campos!**

### ⚠️ MÉDIO: hashed_password NOT NULL mas Firebase Não Usa

**Migration 001:**
```sql
hashed_password VARCHAR(255) NOT NULL
```

**Deveria ser:**
```sql
hashed_password VARCHAR(255) NULLABLE  -- Para usuários Firebase
```

**Model Python já corrige:**
```python
hashed_password = Column(String(255), nullable=True)  # ✅ Correto
```

---

## ✅ Migration Necessária

Precisa criar migration para adicionar campos Firebase:

```sql
-- Migration: 011_add_firebase_fields_to_users.sql

-- Step 1: Create auth_provider enum
CREATE TYPE auth_provider AS ENUM ('local', 'firebase');

-- Step 2: Make hashed_password nullable
ALTER TABLE users
ALTER COLUMN hashed_password DROP NOT NULL;

-- Step 3: Add Firebase fields
ALTER TABLE users
ADD COLUMN firebase_uid VARCHAR(255) UNIQUE,
ADD COLUMN auth_provider auth_provider NOT NULL DEFAULT 'local',
ADD COLUMN firebase_last_sign_in TIMESTAMP WITH TIME ZONE,
ADD COLUMN firebase_created_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN firebase_email_verified BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN firebase_display_name VARCHAR(255),
ADD COLUMN firebase_photo_url VARCHAR(500),
ADD COLUMN firebase_custom_claims JSONB NOT NULL DEFAULT '{}',
ADD COLUMN last_firebase_sync TIMESTAMP WITH TIME ZONE;

-- Step 4: Create index on firebase_uid
CREATE INDEX idx_users_firebase_uid ON users(firebase_uid) WHERE firebase_uid IS NOT NULL;

-- Step 5: Add helpful comments
COMMENT ON COLUMN users.firebase_uid IS 'Firebase user UID from Firebase Authentication';
COMMENT ON COLUMN users.auth_provider IS 'Authentication provider: local (password) or firebase';
COMMENT ON COLUMN users.firebase_custom_claims IS 'Firebase custom claims including role and permissions';
```

---

## 🔒 Row Level Security (RLS)

### Admin System

**Status:** ✅ **Implementado completamente**

A migration `supabase_admin_system_complete.sql` inclui:

1. **RLS habilitado** em todas as tabelas admin
2. **Políticas de acesso** baseadas em roles
3. **Audit logging** automático
4. **Session validation** functions

### Healthcare System

**Status:** ⚠️ **Não verificado** (MCP timeout)

Precisa verificar se há RLS policies para:
- `users`
- `patients`
- `messages`
- `flows`

---

## 📈 Índices e Performance

### Índices Existentes (Migration 001)

```sql
-- users table
CREATE UNIQUE INDEX ON users(email);  -- ✅ Performance

-- patients table
CREATE UNIQUE INDEX ON patients(phone);  -- ✅ Performance
CREATE INDEX ON patients(doctor_id);     -- ✅ FK performance

-- messages table
CREATE INDEX ON messages(patient_id);    -- ✅ FK performance
```

### Índices Recomendados Adicionais

```sql
-- Para queries de autenticação
CREATE INDEX idx_users_firebase_uid ON users(firebase_uid)
WHERE firebase_uid IS NOT NULL;  -- ✅ JÁ INCLUÍDO NA MIGRATION SUGERIDA

-- Para filtrar usuários ativos
CREATE INDEX idx_users_active ON users(is_active)
WHERE is_active = true;

-- Para queries por role
CREATE INDEX idx_users_role ON users(role);
```

---

## 🎯 Checklist de Correções

### Imediato (Antes de Produção)

- [ ] **Criar migration 011** para adicionar campos Firebase
- [ ] **Aplicar migration** no Supabase production via CLI
- [ ] **Verificar RLS policies** para tabelas healthcare
- [ ] **Testar autenticação** após migration

### Recomendado (Médio Prazo)

- [ ] Adicionar índices de performance adicionais
- [ ] Implementar RLS policies para healthcare tables
- [ ] Criar função de auto-update para `updated_at`
- [ ] Implementar soft delete (deleted_at) ao invés de hard delete

### Opcional (Longo Prazo)

- [ ] Consolidar `users` e `admin_users` em uma tabela (se aplicável)
- [ ] Implementar particionamento para tabelas grandes (messages, logs)
- [ ] Adicionar materialized views para analytics

---

## 🚀 Como Aplicar as Correções

### 1. Criar Migration Local

```bash
cd backend-hormonia
alembic revision -m "add_firebase_fields_to_users"
```

### 2. Editar Migration

Copiar SQL da seção "Migration Necessária" acima

### 3. Aplicar no Supabase

```bash
# Via Supabase CLI
supabase db push

# Ou via MCP tool
mcp__supabase__apply_migration(
    name="011_add_firebase_fields",
    query="<SQL aqui>"
)
```

### 4. Validar

```bash
# Verificar estrutura
supabase db diff

# Testar autenticação
pytest tests/integration/auth/
```

---

## 📊 Estatísticas

### Tabelas
- **Healthcare System:** 9 tabelas principais
- **Admin System:** 7 tabelas
- **Total:** ~16 tabelas

### Enums
- **Healthcare:** 6 enums
- **Admin:** 3 enums
- **Total:** 9 enums

### Migrations
- **Alembic:** 10+ migrations aplicadas
- **Supabase:** 2 migrations SQL
- **Status:** ⚠️ Desincronizado (campos Firebase faltando)

---

## ✅ Conclusão

**Status Geral:** 🟡 **BOM com Ajustes Necessários**

### Pontos Fortes
✅ Estrutura bem planejada com separação clara de responsabilidades
✅ Enums corrigidos para valores corretos
✅ Admin system completo com auditoria
✅ Índices básicos de performance

### Pontos de Melhoria
❌ **CRÍTICO:** Campos Firebase não estão na migration
⚠️ **IMPORTANTE:** RLS policies precisam validação
⚠️ **RECOMENDADO:** Índices adicionais de performance

### Próxima Ação
**Criar e aplicar migration 011** para adicionar campos Firebase à tabela users antes de ir para produção.

---

**Relatório gerado em:** 2025-10-07 01:10 UTC
**Ferramentas:** Alembic migrations analysis + Model inspection
**Limitação:** MCP Supabase com timeout - análise baseada em código local
