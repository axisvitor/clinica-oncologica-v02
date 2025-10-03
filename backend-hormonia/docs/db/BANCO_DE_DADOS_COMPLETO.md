# 📊 Documentação Completa do Banco de Dados - Clínica Oncológica Hormonia

**Data de Geração:** 2025-10-02
**Versão do Sistema:** 2.0
**Status:** ✅ Produção Ativo
**Ambiente:** Supabase PostgreSQL 15

---

## 📑 Índice

1. [Visão Geral](#visão-geral)
2. [Estatísticas do Banco](#estatísticas-do-banco)
3. [Extensões PostgreSQL](#extensões-postgresql)
4. [Histórico de Migrações](#histórico-de-migrações)
5. [Tabelas do Sistema](#tabelas-do-sistema)
6. [Esquemas e Relacionamentos](#esquemas-e-relacionamentos)
7. [Segurança RLS](#segurança-rls)
8. [Performance e Índices](#performance-e-índices)
9. [Manutenção e Auditoria](#manutenção-e-auditoria)
10. [Guia de Desenvolvimento](#guia-de-desenvolvimento)

---

## 🎯 Visão Geral

### Descrição do Sistema

Sistema completo de gestão de clínica oncológica com foco em tratamento hormonal, incluindo:
- Gerenciamento de pacientes e médicos
- Fluxos conversacionais automatizados via WhatsApp
- Questionários dinâmicos de acompanhamento
- Relatórios médicos e analytics
- Sistema de administração com auditoria completa
- Segurança RLS baseada em Firebase JWT

### Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)                  │
│                    Firebase Auth + JWT                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ HTTPS + JWT Token
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Backend API (FastAPI + Python 3.13)             │
│              Supabase Client + psycopg v3                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ PostgreSQL Protocol + RLS
                       │
┌──────────────────────▼──────────────────────────────────────┐
│           Supabase PostgreSQL 15 + Extensões                 │
│   • 41 Tabelas                                               │
│   • 54 Migrações Aplicadas                                   │
│   • 23 Políticas RLS Ativas                                  │
│   • 8 Extensões Instaladas                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Estatísticas do Banco

### Resumo Geral

| Métrica | Valor | Status |
|---------|-------|--------|
| **Total de Tabelas** | 41 | ✅ |
| **Tabelas com RLS** | 11 | ✅ 27% |
| **Políticas RLS Ativas** | 23+ | ✅ |
| **Migrações Aplicadas** | 54 | ✅ |
| **Extensões Instaladas** | 8 | ✅ |
| **Índices Criados** | 80+ | ✅ |
| **Tamanho do Banco** | ~1.5 MB | ✅ |
| **Audit Trail** | 90 dias retenção | ✅ |

### Distribuição de Tabelas por Categoria

- **Core System (6):** users, patients, messages, message_status_events, webhook_events, alerts
- **Flow Management (13):** flow_kinds, flow_states, flow_templates_*, flow_messages, patient_flow_states, flow_analytics, flow_template_stats, flow_template_shares, flow_template_categories
- **Quiz System (6):** quiz_templates, quiz_sessions*, quiz_responses, quiz_template_versions*
- **Analytics (2):** flow_analytics, medical_reports
- **Admin System (10):** admin_users, admin_permissions, admin_roles, admin_sessions, admin_audit_log, admin_security_events, admin_ip_*, admin_role_permissions, admin_user_permissions
- **Metadata (7):** user_profiles, user_sync_log, audit_trail, audit_log_entries, alembic_version, contacts, appointments

**Nota:** flow_analytics está contabilizada tanto em "Flow Management" (contexto funcional) quanto em "Analytics" (tipo de dado). O total único de tabelas é 41.

---

## 🔌 Extensões PostgreSQL

### Extensões Instaladas (8)

| Extensão | Versão | Schema | Descrição |
|----------|--------|--------|-----------|
| **plpgsql** | 1.0 | pg_catalog | Linguagem procedural PL/pgSQL (default) |
| **pg_stat_statements** | 1.11 | extensions | Rastreamento de estatísticas de SQL |
| **uuid-ossp** | 1.1 | extensions | Geração de UUIDs |
| **pgcrypto** | 1.3 | extensions | Funções criptográficas |
| **pg_net** | 0.14.0 | extensions | HTTP client assíncrono |
| **pg_graphql** | 1.5.11 | graphql | Suporte a GraphQL |
| **supabase_vault** | 0.3.1 | vault | Gerenciamento de secrets |
| **pg_trgm** | 1.6 | public | Busca por similaridade de texto |

### Extensões Disponíveis Notáveis

- **postgis** (3.3.7) - Tipos e funções espaciais
- **pg_cron** (1.6) - Agendamento de tarefas no PostgreSQL
- **pgjwt** (0.2.0) - API de JSON Web Tokens
- **vector** (0.8.0) - Tipo de dado vetorial para AI/ML
- **http** (1.6) - Cliente HTTP no PostgreSQL
- **pgmq** (1.4.4) - Message queue leve
- **index_advisor** (0.2.0) - Assessor de índices

---

## 📜 Histórico de Migrações

### Total: 54 Migrações Aplicadas

#### Migrações Iniciais (1-5)
1. **003_create_user_profiles** (20250908035647)
2. **fix_user_profiles_permissions** (20250908044623)
3. **create_admin_system** (20250923025807)
4. **create_admin_permissions_and_roles** (20250923025909)
5. **create_admin_audit_and_security** (20250923025911)

#### Sistema Admin Completo (6-15)
6. **create_admin_functions** (20250923025914)
7. **insert_initial_permissions_and_roles** (20250923030015)
8. **create_rls_policies** (20250923030017)
9. **update_admin_password** (20250923093329)
10. **create_admin_user_in_users_table** (20250923093527)
11. **update_admin_password_8_rounds** (20250923093633)
12. **create_admin_user_correct_role** (20250923094037)
13. **update_admin_password_passlib** (20250923094140)
14. **add_other_text_column** (20250924065418)
15. **add_ai_audit_logs_indexes** (20250924065433)

#### Sistema de Fluxos (16-30)
16. **remove_nurse_role_keep_only_doctor_admin** (20250926071249)
17. **add_dynamic_flow_templates_system** (20250927012834)
18-24. **Otimizações Quiz** (add_quiz_*, optimize_quiz_*, create_quiz_materialized_views)
25. **create_hormonia_flow_templates** (20250927042613)
26-31. **Base Enums e Core Tables** (create_base_enums, create_enhanced_core_tables, create_optimized_indexes, etc.)

#### Flow Kinds e Versioning (32-38)
32. **create_flow_kinds_table** (20250928014328)
33. **recreate_flow_template_versions** (20250928014351)
34. **recreate_patient_flow_states_clean** (20250928014441)
35. **remove_legacy_flow_templates** (20250928014458)
36. **import_initial_flow_templates** (20250928015003)
37. **create_admin_profile_and_reset_password** (20250928084150)

#### RLS Rollout (39-50)
38-44. **Incremental RLS Phase 1-2** (incremental_rls_rollout, enable_rls_critical_tables, create_core_rls_policies, etc.)
45-50. **RLS Completo** (create_rls_policies_core_tables, create_additional_policies, fix_audit_trigger, etc.)

#### Auditoria e Performance (51-54)
51. **create_rls_policies_core_tables** (20251002042505)
52. **create_audit_retention_functions** (20251002042623) - Retenção 90 dias
53-54. **add_patients_columns_only** (20251002042838, 20251002063835) - Campos estruturados

---

## 📋 Tabelas do Sistema

### 1. Core System Tables (6 tabelas)

#### 1.1 users
**Propósito:** Profissionais de saúde (médicos e administradores)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    firebase_uid VARCHAR(255) UNIQUE,  -- Link com Firebase Auth
    full_name VARCHAR(255),
    role user_role NOT NULL DEFAULT 'doctor',  -- ENUM: 'doctor', 'admin'
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Constraints
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Índices
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_firebase_uid ON users(firebase_uid);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

-- RLS Policies (2)
-- 1. users_select_own: Usuários podem ver seu próprio perfil
-- 2. users_update_own: Usuários podem atualizar seu próprio perfil
```

**Relacionamentos:**
- 1:N com patients (doctor_id)
- 1:N com medical_reports (generated_by)
- 1:N com alerts (acknowledged_by)

---

#### 1.2 patients
**Propósito:** Pacientes em tratamento oncológico

```sql
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id UUID REFERENCES users(id) NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    birth_date DATE,

    -- Tratamento
    treatment_type VARCHAR(100),
    treatment_start_date DATE,
    treatment_phase VARCHAR(50),  -- Novo: fase do tratamento
    diagnosis TEXT,                -- Novo: diagnóstico estruturado

    -- Estado do fluxo
    flow_state flow_state DEFAULT 'onboarding' NOT NULL,
    current_day INTEGER DEFAULT 0 NOT NULL,

    -- Dados adicionais
    cpf VARCHAR(14) UNIQUE,        -- Novo: CPF estruturado
    doctor_notes TEXT,             -- Novo: notas do médico
    patient_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Constraints
    CONSTRAINT valid_phone CHECK (phone ~ '^\+?[1-9]\d{1,14}$')
);

-- Índices
CREATE INDEX idx_patients_doctor_id ON patients(doctor_id);
CREATE INDEX idx_patients_phone ON patients(phone);
CREATE INDEX idx_patients_flow_state ON patients(flow_state);
CREATE INDEX idx_patients_treatment_type ON patients(treatment_type);
CREATE INDEX idx_patients_treatment_phase ON patients(treatment_phase)
    WHERE treatment_phase IS NOT NULL;
CREATE UNIQUE INDEX idx_patients_cpf_unique ON patients(cpf)
    WHERE cpf IS NOT NULL;

-- RLS Policies (4)
-- 1. patients_select_own_doctor: Médicos vêem apenas seus pacientes
-- 2. patients_insert_doctor: Médicos podem criar pacientes
-- 3. patients_update_authorized: Médicos atualizam seus pacientes
-- 4. patients_delete_admin_only: Apenas admins podem deletar
```

**Enums:**
- flow_state: 'onboarding', 'active', 'paused', 'completed', 'inactive'

---

#### 1.3 messages
**Propósito:** Mensagens WhatsApp (enviadas e recebidas)

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    direction message_direction NOT NULL,  -- 'inbound', 'outbound'
    type message_type DEFAULT 'text' NOT NULL,
    content TEXT,
    message_metadata JSONB DEFAULT '{}',

    -- WhatsApp Integration
    whatsapp_id VARCHAR(255),
    status message_status DEFAULT 'pending' NOT NULL,

    -- Scheduling
    scheduled_for TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Índices
CREATE INDEX idx_messages_patient_id ON messages(patient_id);
CREATE INDEX idx_messages_whatsapp_id ON messages(whatsapp_id);
CREATE INDEX idx_messages_status ON messages(status);
CREATE INDEX idx_messages_direction ON messages(direction);
CREATE INDEX idx_messages_scheduled_for ON messages(scheduled_for);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);

-- RLS Policies (4)
-- 1. messages_select_authorized: Ver mensagens dos próprios pacientes
-- 2. messages_insert_authorized: Criar mensagens para próprios pacientes
-- 3. messages_update_authorized: Atualizar mensagens
-- 4. messages_delete_authorized: Deletar mensagens
```

**Enums:**
- message_direction: 'inbound', 'outbound'
- message_type: 'text', 'button', 'list', 'media', 'location'
- message_status: 'pending', 'sent', 'delivered', 'read', 'failed'

**Relacionamento:**
- 1:N com message_status_events

---

#### 1.4 message_status_events
**Propósito:** Rastreamento completo de mudanças de status das mensagens

```sql
CREATE TABLE message_status_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE NOT NULL,
    status VARCHAR(50) NOT NULL,
    previous_status VARCHAR(50),

    -- WhatsApp Data
    whatsapp_id VARCHAR(255),
    whatsapp_timestamp TIMESTAMP WITH TIME ZONE,

    -- Error Tracking
    error_code VARCHAR(50),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Event Metadata
    metadata JSONB DEFAULT '{}',
    evolution_event_type VARCHAR(100),
    evolution_payload JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Índices Compostos (Performance Otimizada)
CREATE INDEX idx_msg_status_msg_created
    ON message_status_events(message_id, created_at);
CREATE INDEX idx_msg_status_type_time
    ON message_status_events(status, created_at);
CREATE INDEX idx_msg_status_error_time
    ON message_status_events(error_code, created_at)
    WHERE error_code IS NOT NULL;
CREATE INDEX idx_msg_status_whatsapp
    ON message_status_events(whatsapp_id, status);
```

---

#### 1.5 webhook_events
**Propósito:** Armazenamento e replay de webhooks da Evolution API

```sql
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    source VARCHAR(100) NOT NULL DEFAULT 'evolution_api',
    payload JSONB NOT NULL,

    -- Processing Status
    processed BOOLEAN DEFAULT false NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE,

    -- Retry Mechanism
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMP WITH TIME ZONE,

    -- Error Tracking
    error_message TEXT,
    error_stack_trace TEXT,

    -- Related Records
    related_message_id UUID,
    related_patient_id UUID,

    -- Deduplication
    event_hash VARCHAR(64) UNIQUE NOT NULL,
    is_duplicate BOOLEAN DEFAULT false,
    original_event_id UUID,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Índices para Performance de Processamento
CREATE INDEX idx_webhook_type_processed
    ON webhook_events(event_type, processed, created_at);
CREATE INDEX idx_webhook_retry_schedule
    ON webhook_events(processed, next_retry_at)
    WHERE NOT processed AND retry_count < max_retries;
CREATE INDEX idx_webhook_source_time
    ON webhook_events(source, created_at);
CREATE INDEX idx_webhook_pending
    ON webhook_events(processed, retry_count, created_at)
    WHERE NOT processed;
CREATE INDEX idx_webhook_related_msg
    ON webhook_events(related_message_id, event_type);
CREATE INDEX idx_webhook_related_patient
    ON webhook_events(related_patient_id, event_type);
```

---

#### 1.6 alerts
**Propósito:** Alertas e notificações do sistema

```sql
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    type VARCHAR(100) NOT NULL,
    severity alert_severity NOT NULL,  -- 'low', 'medium', 'high', 'critical'
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}',

    -- Acknowledgment
    acknowledged BOOLEAN DEFAULT false NOT NULL,
    acknowledged_by UUID REFERENCES users(id),
    acknowledged_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Índices
CREATE INDEX idx_alerts_patient_id ON alerts(patient_id);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_acknowledged ON alerts(acknowledged);
CREATE INDEX idx_alerts_type ON alerts(type);

-- RLS Policies (4)
-- Similar a messages: acesso baseado em ownership de pacientes
```

---

### 2. Flow Management Tables (9 tabelas)

#### 2.1 flow_kinds
**Propósito:** Tipos de fluxos conversacionais disponíveis

```sql
CREATE TABLE flow_kinds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind_key VARCHAR(50) UNIQUE NOT NULL,  -- 'onboarding', 'daily_checkin', 'symptoms'
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_flow_kinds_kind_key ON flow_kinds(kind_key);
CREATE INDEX idx_flow_kinds_is_active ON flow_kinds(is_active);
```

---

#### 2.2 flow_template_versions
**Propósito:** Versões de templates de fluxos

```sql
CREATE TABLE flow_template_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_kind_id UUID REFERENCES flow_kinds(id) NOT NULL,
    version_number INTEGER NOT NULL,
    template_name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Configuração do Fluxo
    steps JSONB NOT NULL,  -- Array de steps do fluxo
    metadata JSONB DEFAULT '{}',

    -- Versionamento
    is_active BOOLEAN DEFAULT false,
    is_draft BOOLEAN DEFAULT true,
    published_at TIMESTAMP WITH TIME ZONE,
    deprecated_at TIMESTAMP WITH TIME ZONE,

    -- Auditoria
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_flow_version UNIQUE(flow_kind_id, version_number)
);

-- Índices
CREATE INDEX idx_flow_template_versions_flow_kind
    ON flow_template_versions(flow_kind_id);
CREATE INDEX idx_flow_template_versions_active
    ON flow_template_versions(flow_kind_id, is_active)
    WHERE is_active = true;
CREATE INDEX idx_flow_template_versions_version
    ON flow_template_versions(flow_kind_id, version_number DESC);
```

---

#### 2.3 patient_flow_states
**Propósito:** Estado atual de cada paciente em cada tipo de fluxo

```sql
CREATE TABLE patient_flow_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    flow_template_version_id UUID REFERENCES flow_template_versions(id) NOT NULL,

    -- Estado Atual
    current_step INTEGER DEFAULT 0,
    step_data JSONB DEFAULT '{}',  -- Dados específicos do step
    status VARCHAR(50) DEFAULT 'active',  -- 'active', 'completed', 'paused', 'failed'

    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_interaction_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    next_scheduled_at TIMESTAMP WITH TIME ZONE,

    -- Metadata
    flow_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_patient_flow UNIQUE(patient_id, flow_template_version_id)
);

-- Índices
CREATE INDEX idx_patient_flow_states_patient
    ON patient_flow_states(patient_id);
CREATE INDEX idx_patient_flow_states_template
    ON patient_flow_states(flow_template_version_id);
CREATE INDEX idx_patient_flow_states_status
    ON patient_flow_states(status, last_interaction_at);
CREATE INDEX idx_patient_flow_states_next_scheduled
    ON patient_flow_states(next_scheduled_at)
    WHERE status = 'active' AND next_scheduled_at IS NOT NULL;

-- RLS Policy (2)
-- Acesso baseado em ownership de pacientes
```

---

#### 2.4 flow_messages
**Propósito:** Templates de mensagens usadas nos fluxos

```sql
CREATE TABLE flow_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_template_version_id UUID REFERENCES flow_template_versions(id) NOT NULL,
    step_number INTEGER NOT NULL,
    message_key VARCHAR(100) NOT NULL,

    -- Conteúdo
    message_text TEXT NOT NULL,
    message_type VARCHAR(50) DEFAULT 'text',  -- 'text', 'button', 'list', 'media'

    -- Interatividade
    buttons JSONB,  -- Array de botões
    list_items JSONB,  -- Array de itens de lista

    -- Conditional Logic
    conditions JSONB,  -- Condições para exibir esta mensagem

    -- Timing
    delay_seconds INTEGER DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_flow_message UNIQUE(flow_template_version_id, step_number, message_key)
);

-- Índices
CREATE INDEX idx_flow_messages_template
    ON flow_messages(flow_template_version_id);
CREATE INDEX idx_flow_messages_step
    ON flow_messages(flow_template_version_id, step_number);
```

---

#### 2.5 flow_analytics
**Propósito:** Analytics e métricas dos fluxos

```sql
CREATE TABLE flow_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_template_version_id UUID REFERENCES flow_template_versions(id),
    patient_id UUID REFERENCES patients(id),

    -- Métricas
    total_steps INTEGER,
    completed_steps INTEGER,
    success_rate DECIMAL(5,2),
    avg_response_time_seconds INTEGER,

    -- Dados Agregados
    step_analytics JSONB,  -- Analytics por step
    interaction_patterns JSONB,  -- Padrões de interação

    -- Período
    period_start TIMESTAMP WITH TIME ZONE,
    period_end TIMESTAMP WITH TIME ZONE,

    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_flow_analytics_template
    ON flow_analytics(flow_template_version_id);
CREATE INDEX idx_flow_analytics_patient
    ON flow_analytics(patient_id);
CREATE INDEX idx_flow_analytics_period
    ON flow_analytics(period_start, period_end);
```

---

#### 2.6 flow_template_stats
**Propósito:** Estatísticas agregadas dos templates

```sql
CREATE TABLE flow_template_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_template_version_id UUID REFERENCES flow_template_versions(id) UNIQUE NOT NULL,

    -- Uso
    total_uses INTEGER DEFAULT 0,
    active_instances INTEGER DEFAULT 0,
    completed_instances INTEGER DEFAULT 0,

    -- Performance
    avg_completion_rate DECIMAL(5,2),
    avg_duration_hours DECIMAL(10,2),

    -- Ratings
    avg_rating DECIMAL(3,2),
    total_ratings INTEGER DEFAULT 0,

    last_calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

#### 2.7 flow_template_shares
**Propósito:** Compartilhamento de templates entre médicos/organizações

```sql
CREATE TABLE flow_template_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_template_version_id UUID REFERENCES flow_template_versions(id) NOT NULL,
    shared_by UUID REFERENCES users(id) NOT NULL,
    shared_with UUID REFERENCES users(id),  -- NULL = público

    -- Permissões
    can_view BOOLEAN DEFAULT true,
    can_edit BOOLEAN DEFAULT false,
    can_reshare BOOLEAN DEFAULT false,

    -- Metadata
    share_notes TEXT,

    shared_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT unique_share UNIQUE(flow_template_version_id, shared_by, shared_with)
);
```

---

#### 2.8 flow_template_categories
**Propósito:** Categorização de templates de fluxos

```sql
CREATE TABLE flow_template_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_key VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    icon VARCHAR(100),
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

#### 2.9 flow_states (Legacy)
**Propósito:** Tabela legacy de estados de fluxo (deprecated)

```sql
CREATE TABLE flow_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    flow_type VARCHAR(50) NOT NULL,
    current_step INTEGER DEFAULT 0 NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    state_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Índices
CREATE INDEX idx_flow_states_patient_id ON flow_states(patient_id);
CREATE INDEX idx_flow_states_flow_type ON flow_states(flow_type);
CREATE INDEX idx_flow_states_current_state ON flow_states(current_step);

-- Nota: Esta tabela está sendo substituída por patient_flow_states
```

---

### 3. Quiz System Tables (6 tabelas)

#### 3.1 quiz_templates
**Propósito:** Templates de questionários

```sql
CREATE TABLE quiz_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    description TEXT,
    questions JSONB NOT NULL,  -- Array de perguntas (legacy)
    is_active BOOLEAN DEFAULT true NOT NULL,

    -- Categorização
    category VARCHAR(100),
    tags TEXT[],

    -- Configuração
    passing_score INTEGER,
    time_limit_minutes INTEGER,
    randomize_questions BOOLEAN DEFAULT false,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Índices
CREATE INDEX idx_quiz_templates_is_active ON quiz_templates(is_active);
CREATE INDEX idx_quiz_templates_category ON quiz_templates(category);

-- RLS Policy (1)
-- quiz_templates_select_all: Todos usuários autenticados podem ver templates
```

---

#### 3.2 quiz_template_versions_v2
**Propósito:** Sistema de versionamento aprimorado de questionários

```sql
CREATE TABLE quiz_template_versions_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES quiz_templates(id) NOT NULL,
    version_number INTEGER NOT NULL,

    -- Conteúdo
    questions JSONB NOT NULL,
    scoring_rules JSONB,

    -- Status
    is_active BOOLEAN DEFAULT false,
    is_draft BOOLEAN DEFAULT true,
    published_at TIMESTAMP WITH TIME ZONE,

    -- Auditoria
    created_by UUID REFERENCES users(id),
    change_notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_template_version UNIQUE(template_id, version_number)
);

-- Índices
CREATE INDEX idx_quiz_template_versions_v2_template
    ON quiz_template_versions_v2(template_id);
CREATE INDEX idx_quiz_template_versions_v2_active
    ON quiz_template_versions_v2(template_id, is_active)
    WHERE is_active = true;
```

---

#### 3.3 quiz_sessions
**Propósito:** Sessões de questionários respondidos

```sql
CREATE TABLE quiz_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    quiz_template_id UUID REFERENCES quiz_templates(id) NOT NULL,

    -- Status da Sessão
    status VARCHAR(50) DEFAULT 'started',  -- 'started', 'in_progress', 'completed', 'abandoned'

    -- Progresso
    current_question INTEGER DEFAULT 0,
    total_questions INTEGER,
    answered_questions INTEGER DEFAULT 0,

    -- Scores
    score DECIMAL(5,2),
    max_score DECIMAL(5,2),
    passed BOOLEAN,

    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    time_spent_seconds INTEGER,

    -- Metadata
    session_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Índices Otimizados (N+1 Query Prevention)
CREATE INDEX idx_quiz_sessions_patient_id
    ON quiz_sessions(patient_id);
CREATE INDEX idx_quiz_sessions_quiz_template_id
    ON quiz_sessions(quiz_template_id);
CREATE INDEX idx_quiz_sessions_status
    ON quiz_sessions(status);
CREATE INDEX idx_quiz_session_active_patient
    ON quiz_sessions(patient_id, status, started_at DESC)
    WHERE status IN ('started', 'in_progress');
CREATE INDEX idx_quiz_session_completed_template
    ON quiz_sessions(quiz_template_id, completed_at DESC)
    WHERE status = 'completed';
CREATE INDEX idx_quiz_session_patient_template
    ON quiz_sessions(patient_id, quiz_template_id, started_at DESC);

-- RLS Policies (4)
-- Acesso baseado em ownership de pacientes + public insert
```

---

#### 3.4 quiz_sessions_v2 (Versão Aprimorada)
**Propósito:** Versão melhorada de sessões com suporte a versionamento

```sql
CREATE TABLE quiz_sessions_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    template_version_id UUID REFERENCES quiz_template_versions_v2(id) NOT NULL,

    -- Similar structure to quiz_sessions but with version reference
    status VARCHAR(50) DEFAULT 'started',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    session_data JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_quiz_sessions_v2_patient
    ON quiz_sessions_v2(patient_id);
CREATE INDEX idx_quiz_sessions_v2_template_version
    ON quiz_sessions_v2(template_version_id);
```

---

#### 3.5 quiz_responses
**Propósito:** Respostas individuais de questionários

```sql
CREATE TABLE quiz_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    quiz_template_id UUID REFERENCES quiz_templates(id) NOT NULL,
    session_id UUID REFERENCES quiz_sessions(id),  -- Link para sessão

    -- Pergunta
    question_id VARCHAR(100) NOT NULL,
    question_text TEXT NOT NULL,

    -- Resposta
    response_type VARCHAR(50) NOT NULL,  -- 'multiple_choice', 'text', 'scale', 'yes_no'
    response_value TEXT NOT NULL,

    -- Scoring
    is_correct BOOLEAN,
    points_earned DECIMAL(5,2),

    -- Metadata
    response_metadata JSONB DEFAULT '{}',

    -- Timing
    responded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    response_time_seconds INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Índices Otimizados (N+1 Query Prevention + Analytics)
CREATE INDEX idx_quiz_responses_patient_id
    ON quiz_responses(patient_id);
CREATE INDEX idx_quiz_responses_quiz_template_id
    ON quiz_responses(quiz_template_id);
CREATE INDEX idx_quiz_responses_responded_at
    ON quiz_responses(responded_at);
CREATE INDEX idx_quiz_response_session_id
    ON quiz_responses(session_id);
CREATE INDEX idx_quiz_response_patient_template_index
    ON quiz_responses(patient_id, quiz_template_id, responded_at DESC);
CREATE INDEX idx_quiz_response_analytics_covering_index
    ON quiz_responses(quiz_template_id, question_id, response_value, responded_at);

-- RLS Policies (4)
-- Acesso baseado em ownership de sessões + public insert
```

---

#### 3.6 Materialized Views para Performance

```sql
-- View Materializada: Respostas mais recentes por paciente
CREATE MATERIALIZED VIEW quiz_patient_latest_responses AS
SELECT DISTINCT ON (patient_id, quiz_template_id, question_id)
    patient_id,
    quiz_template_id,
    question_id,
    response_value,
    responded_at
FROM quiz_responses
ORDER BY patient_id, quiz_template_id, question_id, responded_at DESC;

-- Índice na view materializada
CREATE UNIQUE INDEX idx_quiz_latest_responses_unique
    ON quiz_patient_latest_responses(patient_id, quiz_template_id, question_id);

-- Refresh automático (pode ser configurado via trigger ou cron)
```

---

### 4. Analytics Tables (2 tabelas)

#### 4.1 medical_reports
**Propósito:** Relatórios médicos gerados

```sql
CREATE TABLE medical_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    generated_by UUID REFERENCES users(id) NOT NULL,

    -- Período do Relatório
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Conteúdo
    summary TEXT,
    insights JSONB DEFAULT '{}',
    charts_data JSONB DEFAULT '{}',
    alerts JSONB DEFAULT '{}',

    -- Metadata
    report_type VARCHAR(50),  -- 'monthly', 'quarterly', 'annual', 'custom'
    report_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Índices
CREATE INDEX idx_medical_reports_patient_id
    ON medical_reports(patient_id);
CREATE INDEX idx_medical_reports_generated_by
    ON medical_reports(generated_by);
CREATE INDEX idx_medical_reports_period
    ON medical_reports(period_start, period_end);

-- RLS Policies (3)
-- Acesso baseado em ownership de pacientes
```

---

### 5. Admin System Tables (10 tabelas)

#### 5.1 admin_users
**Propósito:** Usuários administradores do sistema

```sql
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role admin_role_type NOT NULL DEFAULT 'supervisor',
    department VARCHAR(100),
    phone_number VARCHAR(20),

    -- Security Fields
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    two_factor_enabled BOOLEAN DEFAULT false,
    two_factor_secret VARCHAR(255),
    must_change_password BOOLEAN DEFAULT true,

    -- Login Tracking
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    last_login_ip INET,
    last_password_change TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Session Management
    max_concurrent_sessions INTEGER DEFAULT 3,

    -- Audit Fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES admin_users(id),
    updated_by UUID REFERENCES admin_users(id),

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT positive_max_sessions CHECK (max_concurrent_sessions > 0),
    CONSTRAINT valid_failed_attempts CHECK (failed_login_attempts >= 0)
);

-- Índices
CREATE INDEX idx_admin_users_email ON admin_users(email);
CREATE INDEX idx_admin_users_role ON admin_users(role);
CREATE INDEX idx_admin_users_active ON admin_users(is_active);
CREATE INDEX idx_admin_users_locked ON admin_users(locked_until)
    WHERE locked_until IS NOT NULL;
CREATE INDEX idx_admin_users_last_login ON admin_users(last_login_at);

-- RLS Policies (4)
-- SELECT: Ver próprio perfil ou ser admin
-- INSERT: Apenas super_admin/admin
-- UPDATE: Own profile ou super_admin
-- DELETE: Apenas super_admin
```

**Enum:**
- admin_role_type: 'super_admin', 'admin', 'manager', 'supervisor'

---

#### 5.2 admin_permissions
**Propósito:** Permissões disponíveis no sistema

```sql
CREATE TABLE admin_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,  -- 'users', 'admins', 'patients', 'system', 'analytics'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_permission_name CHECK (name ~ '^[a-z0-9_]+\.[a-z0-9_]+$')
);

-- Índices
CREATE INDEX idx_admin_permissions_category ON admin_permissions(category);

-- Dados Iniciais (16 permissions)
INSERT INTO admin_permissions (name, description, category) VALUES
    ('users.view', 'View user information', 'users'),
    ('users.create', 'Create new users', 'users'),
    ('users.update', 'Update user information', 'users'),
    ('users.delete', 'Delete users', 'users'),
    ('admins.view', 'View admin information', 'admins'),
    ('admins.create', 'Create new admins', 'admins'),
    ('admins.update', 'Update admin information', 'admins'),
    ('admins.delete', 'Delete admins', 'admins'),
    ('patients.view', 'View patient information', 'patients'),
    ('patients.create', 'Create patient records', 'patients'),
    ('patients.update', 'Update patient records', 'patients'),
    ('patients.delete', 'Delete patient records', 'patients'),
    ('system.config', 'Configure system settings', 'system'),
    ('system.security', 'Manage security settings', 'system'),
    ('system.audit', 'Access audit logs', 'system'),
    ('system.reports', 'Generate system reports', 'system'),
    ('analytics.view', 'View analytics dashboards', 'analytics'),
    ('analytics.export', 'Export analytics data', 'analytics');
```

---

#### 5.3 admin_roles
**Propósito:** Roles do sistema admin

```sql
CREATE TABLE admin_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_system_role BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_role_name CHECK (name ~ '^[a-z0-9_]+$')
);

-- Dados Iniciais (4 roles)
INSERT INTO admin_roles (name, description, is_system_role) VALUES
    ('super_admin', 'Full system access with all permissions', true),
    ('admin', 'Administrative access with most permissions', true),
    ('manager', 'Management access with limited permissions', true),
    ('supervisor', 'Supervisory access with read-only permissions', true);
```

---

#### 5.4 admin_user_permissions
**Propósito:** Relacionamento many-to-many entre usuários e permissões

```sql
CREATE TABLE admin_user_permissions (
    admin_user_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES admin_permissions(id) ON DELETE CASCADE,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    granted_by UUID REFERENCES admin_users(id),

    PRIMARY KEY (admin_user_id, permission_id)
);

-- Índices
CREATE INDEX idx_admin_user_permissions_user
    ON admin_user_permissions(admin_user_id);
```

---

#### 5.5 admin_role_permissions
**Propósito:** Relacionamento many-to-many entre roles e permissões

```sql
CREATE TABLE admin_role_permissions (
    role_id UUID NOT NULL REFERENCES admin_roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES admin_permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (role_id, permission_id)
);

-- Índices
CREATE INDEX idx_admin_role_permissions_role
    ON admin_role_permissions(role_id);
```

---

#### 5.6 admin_sessions
**Propósito:** Sessões ativas de administradores

```sql
CREATE TABLE admin_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    ip_address INET,
    user_agent TEXT,
    device_fingerprint VARCHAR(255),

    -- Session Tracking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Session Metadata
    is_active BOOLEAN DEFAULT true,
    logout_reason VARCHAR(100),
    metadata JSONB DEFAULT '{}',

    CONSTRAINT valid_session_duration CHECK (expires_at > created_at)
);

-- Índices
CREATE INDEX idx_admin_sessions_user_id ON admin_sessions(admin_user_id);
CREATE INDEX idx_admin_sessions_token ON admin_sessions(session_token);
CREATE INDEX idx_admin_sessions_active
    ON admin_sessions(is_active, last_activity);
CREATE INDEX idx_admin_sessions_expires ON admin_sessions(expires_at);
CREATE INDEX idx_admin_sessions_ip ON admin_sessions(ip_address);

-- RLS Policies (4)
-- SELECT: Own sessions ou admin
-- INSERT: Own user_id only
-- UPDATE: Own sessions only
-- DELETE: Own sessions only
```

---

#### 5.7 admin_audit_log
**Propósito:** Log de auditoria completo de ações administrativas

```sql
CREATE TABLE admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES admin_users(id),
    session_id UUID REFERENCES admin_sessions(id),

    -- Event Details
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),

    -- Request Details
    ip_address INET,
    user_agent TEXT,
    endpoint VARCHAR(500),
    http_method http_method_type,

    -- Event Metadata
    details JSONB DEFAULT '{}',
    changes JSONB,
    success BOOLEAN DEFAULT true,
    error_message TEXT,

    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER,

    -- Security Classification
    severity severity_type DEFAULT 'low'
);

-- Índices
CREATE INDEX idx_admin_audit_user_id ON admin_audit_log(admin_user_id);
CREATE INDEX idx_admin_audit_timestamp ON admin_audit_log(timestamp);
CREATE INDEX idx_admin_audit_event_type ON admin_audit_log(event_type);
CREATE INDEX idx_admin_audit_ip ON admin_audit_log(ip_address);
CREATE INDEX idx_admin_audit_resource
    ON admin_audit_log(resource_type, resource_id);
CREATE INDEX idx_admin_audit_severity ON admin_audit_log(severity);

-- RLS Policies (2)
-- SELECT: Own logs, managers see team logs, admin see all
-- INSERT: All authenticated can insert
```

**Enums:**
- http_method_type: 'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'
- severity_type: 'low', 'medium', 'high', 'critical'

---

#### 5.8 admin_security_events
**Propósito:** Eventos de segurança detectados

```sql
CREATE TABLE admin_security_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    severity severity_type NOT NULL DEFAULT 'medium',

    -- Source Information
    ip_address INET,
    user_agent TEXT,
    admin_user_id UUID REFERENCES admin_users(id),
    session_id UUID REFERENCES admin_sessions(id),

    -- Event Details
    description TEXT,
    details JSONB DEFAULT '{}',
    endpoint VARCHAR(500),

    -- Detection and Response
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    auto_resolved BOOLEAN DEFAULT false,

    -- Risk Assessment
    risk_score INTEGER DEFAULT 0,
    threat_level severity_type DEFAULT 'low',

    CONSTRAINT valid_risk_score CHECK (risk_score >= 0 AND risk_score <= 100)
);

-- Índices
CREATE INDEX idx_security_events_timestamp
    ON admin_security_events(detected_at);
CREATE INDEX idx_security_events_severity
    ON admin_security_events(severity);
CREATE INDEX idx_security_events_ip
    ON admin_security_events(ip_address);
CREATE INDEX idx_security_events_user_id
    ON admin_security_events(admin_user_id);
CREATE INDEX idx_security_events_resolved
    ON admin_security_events(resolved_at)
    WHERE resolved_at IS NOT NULL;

-- RLS Policies (2)
-- SELECT: Only super_admin and admin
-- INSERT: All authenticated
```

---

#### 5.9 admin_ip_whitelist
**Propósito:** IPs permitidos para acesso admin

```sql
CREATE TABLE admin_ip_whitelist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip_address INET,
    ip_range CIDR,
    description TEXT,

    -- Management
    added_by UUID REFERENCES admin_users(id),
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Usage Tracking
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,

    CONSTRAINT unique_ip_or_range UNIQUE (ip_address, ip_range),
    CONSTRAINT ip_or_range_required
        CHECK (ip_address IS NOT NULL OR ip_range IS NOT NULL)
);

-- Índices
CREATE INDEX idx_ip_whitelist_active
    ON admin_ip_whitelist(is_active, ip_address);
CREATE INDEX idx_ip_whitelist_range
    ON admin_ip_whitelist USING gist(ip_range);

-- RLS Policies (1)
-- ALL: Only super_admin
```

---

#### 5.10 admin_ip_blacklist
**Propósito:** IPs bloqueados para acesso admin

```sql
CREATE TABLE admin_ip_blacklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip_address INET NOT NULL UNIQUE,
    reason VARCHAR(255) NOT NULL,

    -- Blacklist Details
    blocked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    blocked_by UUID REFERENCES admin_users(id),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_permanent BOOLEAN DEFAULT false,

    -- Incident Tracking
    incident_id UUID,
    threat_level severity_type DEFAULT 'medium',
    block_count INTEGER DEFAULT 1,

    -- Metadata
    details JSONB DEFAULT '{}',
    notes TEXT
);

-- Índices
CREATE INDEX idx_ip_blacklist_active
    ON admin_ip_blacklist(ip_address, expires_at);

-- RLS Policies (1)
-- ALL: Only super_admin
```

---

### 6. Metadata & System Tables (6 tabelas)

#### 6.1 user_profiles
**Propósito:** Perfis estendidos de usuários

```sql
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) UNIQUE NOT NULL,

    -- Profile Info
    bio TEXT,
    avatar_url VARCHAR(500),
    phone VARCHAR(20),

    -- Professional Info
    specialty VARCHAR(255),
    license_number VARCHAR(100),
    years_of_experience INTEGER,

    -- Preferences
    preferences JSONB DEFAULT '{}',
    notification_settings JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);

-- RLS Policy (2)
-- SELECT: View own profile
-- UPDATE: Update own profile
```

---

#### 6.2 user_sync_log
**Propósito:** Log de sincronização Firebase ↔ Supabase

```sql
CREATE TABLE user_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(255) NOT NULL,
    supabase_user_id UUID REFERENCES users(id),

    -- Sync Details
    sync_action VARCHAR(50) NOT NULL,  -- 'created', 'updated', 'synced', 'failed'
    sync_status VARCHAR(50) NOT NULL,  -- 'success', 'failed', 'pending'

    -- Data
    firebase_data JSONB,
    supabase_data JSONB,

    -- Error Handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Timing
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_user_sync_log_firebase_uid
    ON user_sync_log(firebase_uid);
CREATE INDEX idx_user_sync_log_supabase_user
    ON user_sync_log(supabase_user_id);
CREATE INDEX idx_user_sync_log_status
    ON user_sync_log(sync_status, synced_at);

-- RLS Policy (1)
-- SELECT: View own sync logs
```

---

#### 6.3 audit_trail
**Propósito:** Trail de auditoria geral do sistema

```sql
CREATE TABLE audit_trail (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(255) NOT NULL,
    record_id UUID NOT NULL,
    operation VARCHAR(50) NOT NULL,  -- 'INSERT', 'UPDATE', 'DELETE'

    -- Data Changes
    old_data JSONB,
    new_data JSONB,
    changes JSONB,  -- Diff of changes

    -- Actor Info
    actor_id UUID,  -- Can be user_id or admin_user_id
    actor_type VARCHAR(50),  -- 'user', 'admin', 'system'
    actor_subject VARCHAR(255),  -- Firebase UID or email

    -- Request Context
    ip_address INET,
    user_agent TEXT,
    endpoint VARCHAR(500),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_audit_trail_table_record
    ON audit_trail(table_name, record_id);
CREATE INDEX idx_audit_trail_actor
    ON audit_trail(actor_id, created_at DESC);
CREATE INDEX idx_audit_trail_created_at
    ON audit_trail(created_at);
CREATE INDEX idx_audit_trail_operation
    ON audit_trail(operation, created_at DESC);

-- Retenção: 90 dias (cleanup automático às 2 AM diariamente)
```

---

#### 6.4 audit_log_entries
**Propósito:** Entradas genéricas de log de auditoria

```sql
CREATE TABLE audit_log_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id UUID,

    -- User Context
    user_id UUID,

    -- Event Data
    old_values JSONB,
    new_values JSONB,
    metadata JSONB DEFAULT '{}',

    -- Request Context
    ip_address INET,
    user_agent TEXT,

    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_audit_log_entries_timestamp
    ON audit_log_entries(timestamp);
CREATE INDEX idx_audit_log_entries_user
    ON audit_log_entries(user_id, timestamp DESC);
CREATE INDEX idx_audit_log_entries_entity
    ON audit_log_entries(entity_type, entity_id);

-- Retenção: 90 dias (cleanup automático)
```

---

#### 6.5 alembic_version
**Propósito:** Controle de versão de migrações Alembic (Python backend)

```sql
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Nota: Gerenciado automaticamente pelo Alembic
-- Não possui políticas RLS (tabela de sistema)
```

---

#### 6.6 contacts
**Propósito:** Contatos gerais do sistema

```sql
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),

    -- Type
    contact_type VARCHAR(50),  -- 'patient', 'professional', 'vendor', 'other'

    -- Relationship
    related_patient_id UUID REFERENCES patients(id),
    related_user_id UUID REFERENCES users(id),

    -- Metadata
    notes TEXT,
    tags TEXT[],
    contact_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_contacts_phone ON contacts(phone);
CREATE INDEX idx_contacts_type ON contacts(contact_type);
```

---

#### 6.7 appointments (Tabela Futura)
**Propósito:** Agendamentos e consultas

```sql
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    doctor_id UUID REFERENCES users(id) NOT NULL,

    -- Appointment Details
    appointment_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'scheduled',

    -- Timing
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    completed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,

    -- Notes
    pre_appointment_notes TEXT,
    post_appointment_notes TEXT,

    -- Metadata
    appointment_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_doctor ON appointments(doctor_id);
CREATE INDEX idx_appointments_scheduled
    ON appointments(scheduled_at);
CREATE INDEX idx_appointments_status
    ON appointments(status, scheduled_at);
```

---

## 🔐 Segurança RLS (Row Level Security)

### Resumo de Políticas RLS

**Total: 23+ políticas ativas em 11 tabelas**

### Arquitetura de Autenticação

```
┌─────────────────────────────────────────┐
│         Frontend (Browser)               │
│   1. Login com Firebase Auth            │
│   2. Recebe JWT com firebase_uid         │
└───────────────┬─────────────────────────┘
                │
                │ Authorization: Bearer <jwt>
                │
┌───────────────▼─────────────────────────┐
│      Supabase Client (Frontend)          │
│   Header injection automático            │
│   via supabase-firebase-integration.ts   │
└───────────────┬─────────────────────────┘
                │
                │ HTTP Request + JWT
                │
┌───────────────▼─────────────────────────┐
│         Supabase PostgreSQL              │
│   1. Parse JWT do header                │
│   2. Extrai firebase_uid do JWT         │
│   3. Define request.jwt.claims           │
│   4. Avalia RLS policies                 │
│   5. Filtra resultados                   │
└──────────────────────────────────────────┘
```

### Funções Helper RLS

```sql
-- Extrai firebase_uid do JWT
CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid AS $$
    SELECT COALESCE(
        (current_setting('request.jwt.claims', true)::json->>'sub')::uuid,
        NULL
    );
$$ LANGUAGE sql STABLE;

-- Extrai role do JWT
CREATE OR REPLACE FUNCTION auth.role()
RETURNS text AS $$
    SELECT COALESCE(
        current_setting('request.jwt.claims', true)::json->>'role',
        'anon'::text
    );
$$ LANGUAGE sql STABLE;

-- Extrai email do JWT
CREATE OR REPLACE FUNCTION auth.email()
RETURNS text AS $$
    SELECT COALESCE(
        current_setting('request.jwt.claims', true)::json->>'email',
        NULL
    );
$$ LANGUAGE sql STABLE;
```

### Distribuição de Políticas por Tabela

| Tabela | SELECT | INSERT | UPDATE | DELETE | Total |
|--------|--------|--------|--------|--------|-------|
| users | ✅ | ❌ | ✅ | ❌ | 2 |
| patients | ✅ | ✅ | ✅ | ✅ | 4 |
| messages | ✅ | ✅ | ✅ | ✅ | 4 |
| medical_reports | ✅ | ✅ | ✅ | ❌ | 3 |
| quiz_templates | ✅ | ❌ | ❌ | ❌ | 1 |
| quiz_sessions | ✅ | ✅ (public) | ✅ | ❌ | 3 |
| quiz_responses | ✅ | ✅ (public) | ✅ | ❌ | 3 |
| flow_states | ✅ | ✅ | ✅ | ✅ | 4 |
| alerts | ✅ | ✅ | ✅ | ✅ | 4 |
| user_sync_log | ✅ | ✅ | ❌ | ❌ | 2 |
| patient_flow_states | ✅ | ✅ | ✅ | ❌ | 3 |

### Exemplos de Políticas Principais

#### 1. Política de Isolamento de Dados por Médico

```sql
-- Pacientes: Cada médico só vê seus próprios pacientes
CREATE POLICY "patients_select_own_doctor" ON public.patients
FOR SELECT TO authenticated
USING (
    doctor_id IN (
        SELECT id FROM public.users
        WHERE firebase_uid = current_setting('request.jwt.claims', true)::json->>'sub'
    )
);
```

#### 2. Política de Quiz Público (Pacientes via Link)

```sql
-- Quiz Sessions: Qualquer um pode criar (via shared link)
CREATE POLICY "quiz_sessions_insert_public" ON public.quiz_sessions
FOR INSERT TO anon, authenticated
WITH CHECK (true);

-- Mas só donos podem visualizar
CREATE POLICY "quiz_sessions_select_authorized" ON public.quiz_sessions
FOR SELECT TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.patients p
        WHERE p.id = patient_id
        AND (p.doctor_id = auth.uid() OR auth.role() = 'admin')
    )
);
```

#### 3. Política Admin Override

```sql
-- Admins podem ver TODOS os pacientes
CREATE POLICY "patients_select_own_doctor" ON public.patients
FOR SELECT TO authenticated
USING (
    doctor_id IN (
        SELECT id FROM public.users
        WHERE firebase_uid = current_setting('request.jwt.claims', true)::json->>'sub'
    )
    OR auth.role() = 'admin'  -- Admin override
);
```

### Testes de Segurança RLS

Arquivo: `tests/security/test_rls_policies.py`

```python
# Simula contexto Firebase JWT
await db_session.execute(
    text("SELECT set_config('request.jwt.claims', :jwt_claims, true);"),
    {"jwt_claims": '{"sub": "firebase_uid_doctor1", "role": "doctor"}'}
)

# Testa isolamento
patients = await db_session.execute(select(Patient))
# Deve retornar apenas pacientes do doctor1
```

---

## ⚡ Performance e Índices

### Índices por Categoria

#### 1. Índices de Chave Primária (41)
Todos os UUIDs PRIMARY KEY têm índice automático

#### 2. Índices de Foreign Key (30+)
- `idx_patients_doctor_id`
- `idx_messages_patient_id`
- `idx_quiz_responses_session_id`
- etc.

#### 3. Índices Compostos para Performance (20+)

**Prevenção N+1 Query:**
```sql
-- Quiz sessions do paciente ordenadas
CREATE INDEX idx_quiz_session_patient_template
    ON quiz_sessions(patient_id, quiz_template_id, started_at DESC);

-- Status events de uma mensagem
CREATE INDEX idx_msg_status_msg_created
    ON message_status_events(message_id, created_at);

-- Próximos agendamentos
CREATE INDEX idx_patient_flow_states_next_scheduled
    ON patient_flow_states(next_scheduled_at)
    WHERE status = 'active' AND next_scheduled_at IS NOT NULL;
```

**Analytics e Reporting:**
```sql
-- Análise de respostas de quiz
CREATE INDEX idx_quiz_response_analytics_covering_index
    ON quiz_responses(
        quiz_template_id,
        question_id,
        response_value,
        responded_at
    );

-- Relatórios por período
CREATE INDEX idx_medical_reports_period
    ON medical_reports(period_start, period_end);
```

#### 4. Índices Parciais (10+)

```sql
-- Apenas registros ativos
CREATE INDEX idx_quiz_template_versions_active
    ON flow_template_versions(flow_kind_id, is_active)
    WHERE is_active = true;

-- Apenas com erros
CREATE INDEX idx_msg_status_error_time
    ON message_status_events(error_code, created_at)
    WHERE error_code IS NOT NULL;

-- Apenas CPFs não nulos
CREATE UNIQUE INDEX idx_patients_cpf_unique
    ON patients(cpf)
    WHERE cpf IS NOT NULL;
```

#### 5. Índices GiST (2)

```sql
-- IP ranges para whitelist
CREATE INDEX idx_ip_whitelist_range
    ON admin_ip_whitelist USING gist(ip_range);

-- Full-text search (quando habilitado)
-- CREATE INDEX idx_patients_name_fts
--     ON patients USING gin(to_tsvector('portuguese', name));
```

### Estratégias de Otimização

1. **Materialized Views**
   - `quiz_patient_latest_responses`: Cache de respostas mais recentes
   - Refresh agendado ou via trigger

2. **Partitioning (Futuro)**
   - `audit_trail` por mês quando > 10M registros
   - `messages` por ano quando > 50M registros

3. **Covering Indexes**
   - Índices que contêm todos os campos necessários (INCLUDE)
   - Evitam lookup da tabela principal

---

## 🔄 Manutenção e Auditoria

### Sistema de Auditoria (90 dias de retenção)

#### Tabelas de Auditoria

1. **audit_trail** - Auditoria geral (triggers automáticos)
2. **audit_log_entries** - Logs de aplicação
3. **admin_audit_log** - Logs administrativos específicos

#### Funções de Cleanup

```sql
-- Cleanup audit_trail (> 90 dias)
CREATE OR REPLACE FUNCTION cleanup_old_audit_trail()
RETURNS TABLE(
    deleted_count INTEGER,
    space_before TEXT,
    space_after TEXT
) AS $$
DECLARE
    v_deleted_count INTEGER;
    v_size_before BIGINT;
    v_size_after BIGINT;
BEGIN
    -- Calcula tamanho antes
    SELECT pg_total_relation_size('audit_trail') INTO v_size_before;

    -- Deleta registros antigos
    DELETE FROM audit_trail
    WHERE created_at < NOW() - INTERVAL '90 days';

    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;

    -- Calcula tamanho depois
    SELECT pg_total_relation_size('audit_trail') INTO v_size_after;

    RETURN QUERY SELECT
        v_deleted_count,
        pg_size_pretty(v_size_before),
        pg_size_pretty(v_size_after);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Cleanup todas as tabelas de auditoria
CREATE OR REPLACE FUNCTION cleanup_all_audit_tables()
RETURNS TABLE(
    table_name TEXT,
    deleted_count INTEGER,
    space_before TEXT,
    space_after TEXT
) AS $$
BEGIN
    RETURN QUERY SELECT * FROM cleanup_old_audit_trail();
    RETURN QUERY SELECT * FROM cleanup_old_audit_log_entries();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

#### Cron Job Automático

**Backend:** APScheduler (Python)
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()
scheduler.add_job(
    AuditCleanupJob.run,
    trigger=CronTrigger(hour=2, minute=0),  # Diariamente às 2 AM
    id="audit_cleanup",
    replace_existing=True,
    max_instances=1
)
```

**Supabase:** pg_cron (Futuro)
```sql
-- Se pg_cron estiver disponível
SELECT cron.schedule(
    'cleanup-audit-trail',
    '0 2 * * *',  -- 2 AM todos os dias
    $$SELECT * FROM cleanup_all_audit_tables();$$
);
```

#### Endpoints Admin API

```
GET  /api/v1/admin/audit/stats       - Estatísticas de auditoria
POST /api/v1/admin/audit/cleanup     - Trigger manual cleanup
POST /api/v1/admin/audit/vacuum      - Trigger manual VACUUM
```

### VACUUM e Manutenção

```sql
-- VACUUM completo (recupera espaço)
VACUUM FULL ANALYZE audit_trail;

-- VACUUM incremental (menos bloqueio)
VACUUM ANALYZE audit_trail;

-- VACUUM automático configurado
-- (Supabase gerencia automaticamente)
```

---

## 💻 Guia de Desenvolvimento

### Conectando ao Banco

#### Frontend (TypeScript + Supabase Client)

```typescript
// src/lib/supabase-firebase-integration.ts
import { createClient } from '@supabase/supabase-js'
import { firebaseAuth } from './firebase'

export const supabase = createClient(
    import.meta.env.VITE_SUPABASE_URL,
    import.meta.env.VITE_SUPABASE_ANON_KEY,
    {
        global: {
            headers: async () => {
                const user = firebaseAuth.currentUser
                if (user) {
                    const token = await user.getIdToken()
                    return {
                        'Authorization': `Bearer ${token}`,
                        'X-Auth-Provider': 'firebase'
                    }
                }
                return {}
            }
        }
    }
)

// Uso
const { data, error } = await supabase
    .from('patients')
    .select('*')
// RLS filtra automaticamente baseado no JWT
```

#### Backend (Python + psycopg v3)

```python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine
import os

# IMPORTANTE: Usar postgresql+psycopg para psycopg v3
DATABASE_URL = os.getenv('DATABASE_URL')
# Formato: postgresql+psycopg://user:pass@host:5432/db

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "server_settings": {
            "application_name": "clinica-oncologica-backend"
        }
    }
)
```

### Queries Recomendadas

#### 1. Listar Pacientes do Médico Autenticado

```sql
-- Frontend (via Supabase client com RLS)
SELECT * FROM patients
ORDER BY created_at DESC;
-- RLS filtra automaticamente por doctor_id

-- Backend (simulando RLS manualmente)
SELECT * FROM patients
WHERE doctor_id = (
    SELECT id FROM users WHERE firebase_uid = :current_user_uid
)
ORDER BY created_at DESC;
```

#### 2. Buscar Histórico de Questionários de Paciente

```sql
SELECT
    qs.id,
    qs.started_at,
    qs.completed_at,
    qs.status,
    qt.name as quiz_name,
    COUNT(qr.id) as total_responses,
    qs.score
FROM quiz_sessions qs
JOIN quiz_templates qt ON qs.quiz_template_id = qt.id
LEFT JOIN quiz_responses qr ON qr.session_id = qs.id
WHERE qs.patient_id = :patient_id
GROUP BY qs.id, qt.name
ORDER BY qs.started_at DESC;
```

#### 3. Analytics de Fluxo por Template

```sql
SELECT
    ftv.template_name,
    COUNT(DISTINCT pfs.patient_id) as total_patients,
    AVG(pfs.current_step::decimal / JSONB_ARRAY_LENGTH(ftv.steps)) * 100 as avg_completion_rate,
    COUNT(CASE WHEN pfs.status = 'completed' THEN 1 END) as completed_count
FROM flow_template_versions ftv
LEFT JOIN patient_flow_states pfs ON pfs.flow_template_version_id = ftv.id
WHERE ftv.is_active = true
GROUP BY ftv.id, ftv.template_name
ORDER BY total_patients DESC;
```

#### 4. Próximos Fluxos Agendados

```sql
SELECT
    p.name as patient_name,
    p.phone,
    ftv.template_name,
    pfs.next_scheduled_at,
    pfs.current_step,
    EXTRACT(EPOCH FROM (pfs.next_scheduled_at - NOW())) / 60 as minutes_until_next
FROM patient_flow_states pfs
JOIN patients p ON p.id = pfs.patient_id
JOIN flow_template_versions ftv ON ftv.id = pfs.flow_template_version_id
WHERE pfs.status = 'active'
    AND pfs.next_scheduled_at IS NOT NULL
    AND pfs.next_scheduled_at > NOW()
    AND pfs.next_scheduled_at < NOW() + INTERVAL '24 hours'
ORDER BY pfs.next_scheduled_at ASC;
```

### Migrations com Alembic (Python)

```bash
# Criar nova migration
alembic revision --autogenerate -m "description"

# Revisar migration gerada
# alembic/versions/XXXXXX_description.py

# Aplicar migration
alembic upgrade head

# Rollback
alembic downgrade -1

# Ver histórico
alembic history
```

### Migrations com Supabase CLI

```bash
# Criar nova migration
supabase migration new description

# Aplicar migrations
supabase db push

# Reset (desenvolvimento local)
supabase db reset

# Diff com produção
supabase db diff --use-migra
```

---

## 📦 Backup e Restore

### Backup Completo

```bash
# Via Supabase Dashboard
# Settings → Database → Backup

# Via pg_dump (local)
pg_dump -h db.xxx.supabase.co \
    -U postgres \
    -d postgres \
    --format=custom \
    --file=backup_$(date +%Y%m%d).dump

# Backup apenas schema
pg_dump -h db.xxx.supabase.co \
    -U postgres \
    -d postgres \
    --schema-only \
    --file=schema_$(date +%Y%m%d).sql
```

### Restore

```bash
# Restore completo
pg_restore -h db.xxx.supabase.co \
    -U postgres \
    -d postgres \
    --clean \
    backup_20251002.dump

# Restore apenas dados
pg_restore -h db.xxx.supabase.co \
    -U postgres \
    -d postgres \
    --data-only \
    backup_20251002.dump
```

---

## 📚 Recursos Adicionais

### Documentos Relacionados

- [DATABASE_COMPLETE_REPORT.md](./DATABASE_COMPLETE_REPORT.md) - Relatório de segurança RLS
- [backend-hormonia/docs/database-schema-complete.md](./backend-hormonia/docs/database-schema-complete.md) - Esquema de tabelas específicas
- [init-db.sql](./backend-hormonia/init-db.sql) - Script de inicialização legacy

### Arquivos de Migração

- **Supabase Migrations:** Aplicadas via Supabase Dashboard
  - Total: 54 migrations em `supabase/migrations/`

- **Alembic Migrations:** Aplicadas via backend Python
  - Localização: `backend-hormonia/alembic/versions/`

- **SQL Scripts:** Scripts manuais e utilitários
  - Localização: `backend-hormonia/sql/`
  - Categorias: migrations, monitoring, migrations-archive

---

## 🎯 Próximos Passos

### Melhorias Planejadas

1. **Particionamento de Tabelas Grandes** (Q1 2025)
   - audit_trail particionado por mês
   - messages particionado por ano

2. **Full-Text Search** (Q1 2025)
   - Busca em patients.name com pg_trgm
   - Busca em medical_reports.summary

3. **Materialized Views Adicionais** (Q2 2025)
   - Dashboard analytics pré-calculado
   - KPIs por médico/clínica

4. **Replicação e HA** (Q2 2025)
   - Read replicas para analytics
   - Failover automático

5. **HIPAA Compliance Audit** (Q2 2025)
   - Verificação completa de conformidade
   - Certificação de segurança

---

## 📞 Suporte

**Documentação:** Este arquivo
**Issues:** GitHub Issues
**Email:** dev@clinica-oncologica.com

---

**Última Atualização:** 2025-10-02
**Versão do Documento:** 1.0
**Autor:** Claude AI + Time de Desenvolvimento
**Status:** ✅ Documentação Completa e Atualizada
