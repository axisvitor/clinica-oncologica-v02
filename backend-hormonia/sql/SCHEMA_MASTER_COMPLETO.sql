-- ============================================================================
-- SCHEMA MASTER COMPLETO - CLÍNICA ONCOLÓGICA HORMONIA
-- ============================================================================
-- Versão: 2.4
-- Data: 2025-10-07
-- Última Atualização: 2025-10-07 (Firebase authentication fields added to users table)
-- Descrição: Schema completo consolidado com todas as 41 tabelas do sistema
--
-- IMPORTANTE: Este arquivo NÃO deve ser executado diretamente em produção.
-- Use as migrations do Supabase para alterações incrementais.
-- Este arquivo serve como referência completa da estrutura atual.
--
-- CHANGELOG v2.4 (2025-10-07):
-- - CRITICAL FIX: Added 9 Firebase authentication fields to users table
--   * firebase_uid (already existed)
--   * auth_provider (already existed)
--   * firebase_last_sign_in (NEW)
--   * firebase_created_at (NEW)
--   * firebase_email_verified (NEW)
--   * firebase_display_name (NEW)
--   * firebase_photo_url (NEW)
--   * firebase_custom_claims (NEW - JSONB for role management)
--   * last_firebase_sync (NEW)
-- - Made hashed_password NULLABLE for Firebase-only users
-- - Added indexes for firebase_uid (partial) and auth_provider
-- - Source: migration 20250930_add_firebase_fields.py
-- - Total de migrations: 61 (60 anteriores + 1 nova: add_firebase_fields)
--
-- CHANGELOG v2.3 (2025-10-06):
-- - CRITICAL FIX: Added user_sync_log.updated_at column (migration applied via Supabase MCP)
-- - Added trigger function update_user_sync_log_updated_at() for auto-timestamp updates
-- - Added index idx_user_sync_log_updated_at for query performance
-- - Fixed Firebase authentication claim extraction (backend code)
-- - Total de migrations: 60 (59 anteriores + 1 nova aplicada em 2025-10-06)
--
-- CHANGELOG v2.2 (2025-10-04):
-- - Removidos campos deprecated de quiz_sessions (is_completed, current_question_index, total_score)
-- - Adicionado CHECK constraint quiz_sessions_status_check
-- - Reconstruídas 4 materialized views com novo schema (status-based)
-- - Criados 8 novos índices v2 otimizados para quiz_sessions
-- - Adicionado índice único para sessões ativas por paciente/template
-- ============================================================================

-- ============================================================================
-- SEÇÃO 1: EXTENSÕES
-- ============================================================================

-- Extensões instaladas no Supabase
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- Geração de UUIDs
CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- Funções criptográficas
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Busca por similaridade
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; -- Estatísticas SQL
CREATE EXTENSION IF NOT EXISTS "btree_gist";     -- Suporte a índices GIST para tipos como CIDR

-- ============================================================================
-- SEÇÃO 2: ENUMS E TIPOS CUSTOMIZADOS
-- ============================================================================

-- User roles
CREATE TYPE user_role AS ENUM ('doctor', 'admin');

-- Flow states
CREATE TYPE flow_state AS ENUM (
    'onboarding',
    'active',
    'paused',
    'completed',
    'inactive'
);

-- Message direction
CREATE TYPE message_direction AS ENUM ('inbound', 'outbound');

-- Message type (updated 2025-10-04: added quiz message types)
CREATE TYPE message_type AS ENUM (
    'text',
    'button',
    'list',
    'media',
    'location',
    'quiz_intro',
    'quiz_question',
    'quiz_encouragement',
    'quiz_completion',
    'monthly_quiz_link',
    'monthly_quiz_reminder',
    'monthly_quiz_expired',
    'monthly_quiz_completed'
);

-- Message status
CREATE TYPE message_status AS ENUM (
    'pending',
    'sent',
    'delivered',
    'read',
    'failed'
);

-- Alert severity
CREATE TYPE alert_severity AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

-- Auth provider (Firebase, Google, etc.)
CREATE TYPE auth_provider AS ENUM (
    'local',
    'firebase',
    'google',
    'apple'
);

-- Admin role type
CREATE TYPE admin_role_type AS ENUM (
    'super_admin',
    'admin',
    'manager',
    'supervisor'
);

-- Severity type (security events)
CREATE TYPE severity_type AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

-- HTTP method type
CREATE TYPE http_method_type AS ENUM (
    'GET',
    'POST',
    'PUT',
    'PATCH',
    'DELETE',
    'OPTIONS',
    'HEAD'
);

-- ============================================================================
-- SEÇÃO 3: TABELAS CORE DO SISTEMA (6 tabelas)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 3.1 USERS - Profissionais de Saúde (Updated 2025-10-07: Firebase fields)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,

    -- Password field (nullable for Firebase-only users)
    hashed_password VARCHAR(255),  -- NULLABLE for Firebase users

    -- Basic user info
    full_name VARCHAR(255),
    role user_role NOT NULL DEFAULT 'doctor',
    is_active BOOLEAN DEFAULT true NOT NULL,

    -- Firebase Authentication Fields (Added 2025-10-07)
    firebase_uid VARCHAR(255) UNIQUE,
    auth_provider auth_provider NOT NULL DEFAULT 'local',
    firebase_last_sign_in TIMESTAMP WITH TIME ZONE,
    firebase_created_at TIMESTAMP WITH TIME ZONE,
    firebase_email_verified BOOLEAN NOT NULL DEFAULT false,
    firebase_display_name VARCHAR(255),
    firebase_photo_url VARCHAR(500),
    firebase_custom_claims JSONB NOT NULL DEFAULT '{}',
    last_firebase_sync TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid) WHERE firebase_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON users(auth_provider);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- Comments
COMMENT ON TABLE users IS 'Profissionais de saúde (médicos e administradores) - Supports local and Firebase authentication';
COMMENT ON COLUMN users.firebase_uid IS 'Firebase user UID from Firebase Authentication';
COMMENT ON COLUMN users.auth_provider IS 'Authentication provider: local (password) or firebase';
COMMENT ON COLUMN users.firebase_custom_claims IS 'Firebase custom claims including role (admin/doctor) and permissions';
COMMENT ON COLUMN users.hashed_password IS 'Password hash - NULL for Firebase-only users';
COMMENT ON COLUMN users.last_firebase_sync IS 'Timestamp of last sync with Firebase Authentication';

-- ----------------------------------------------------------------------------
-- 3.2 PATIENTS - Pacientes
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id UUID REFERENCES users(id) NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    birth_date DATE,

    -- Tratamento
    treatment_type VARCHAR(100),
    treatment_start_date DATE,
    treatment_phase VARCHAR(50),
    diagnosis TEXT,

    -- Estado do fluxo
    flow_state flow_state DEFAULT 'onboarding' NOT NULL,
    current_day INTEGER DEFAULT 0 NOT NULL,

    -- Dados estruturados (novos)
    cpf VARCHAR(14) UNIQUE,
    doctor_notes TEXT,

    -- Metadata legacy
    patient_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    CONSTRAINT valid_phone CHECK (phone ~ '^\+?[1-9]\d{1,14}$')
);

CREATE INDEX IF NOT EXISTS idx_patients_doctor_id ON patients(doctor_id);
CREATE INDEX IF NOT EXISTS idx_patients_phone ON patients(phone);
CREATE INDEX IF NOT EXISTS idx_patients_flow_state ON patients(flow_state);
CREATE INDEX IF NOT EXISTS idx_patients_treatment_type ON patients(treatment_type);
CREATE INDEX IF NOT EXISTS idx_patients_treatment_phase ON patients(treatment_phase)
    WHERE treatment_phase IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_cpf_unique ON patients(cpf)
    WHERE cpf IS NOT NULL;

COMMENT ON TABLE patients IS 'Pacientes em tratamento oncológico';

-- ----------------------------------------------------------------------------
-- 3.3 MESSAGES - Mensagens WhatsApp
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    direction message_direction NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_messages_patient_id ON messages(patient_id);
CREATE INDEX IF NOT EXISTS idx_messages_whatsapp_id ON messages(whatsapp_id);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_direction ON messages(direction);
CREATE INDEX IF NOT EXISTS idx_messages_scheduled_for ON messages(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);

COMMENT ON TABLE messages IS 'Mensagens WhatsApp (enviadas e recebidas)';

-- ----------------------------------------------------------------------------
-- 3.4 MESSAGE_STATUS_EVENTS - Histórico de Status de Mensagens
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS message_status_events (
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

CREATE INDEX IF NOT EXISTS idx_msg_status_msg_created
    ON message_status_events(message_id, created_at);
CREATE INDEX IF NOT EXISTS idx_msg_status_type_time
    ON message_status_events(status, created_at);
CREATE INDEX IF NOT EXISTS idx_msg_status_error_time
    ON message_status_events(error_code, created_at)
    WHERE error_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_msg_status_whatsapp
    ON message_status_events(whatsapp_id, status);

COMMENT ON TABLE message_status_events IS 'Rastreamento de mudanças de status de mensagens';

-- ----------------------------------------------------------------------------
-- 3.5 WEBHOOK_EVENTS - Eventos de Webhook
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS webhook_events (
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

CREATE INDEX IF NOT EXISTS idx_webhook_type_processed
    ON webhook_events(event_type, processed, created_at);
CREATE INDEX IF NOT EXISTS idx_webhook_retry_schedule
    ON webhook_events(processed, next_retry_at)
    WHERE NOT processed AND retry_count < max_retries;
CREATE INDEX IF NOT EXISTS idx_webhook_source_time
    ON webhook_events(source, created_at);
CREATE INDEX IF NOT EXISTS idx_webhook_pending
    ON webhook_events(processed, retry_count, created_at)
    WHERE NOT processed;
CREATE INDEX IF NOT EXISTS idx_webhook_related_msg
    ON webhook_events(related_message_id, event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_related_patient
    ON webhook_events(related_patient_id, event_type);

COMMENT ON TABLE webhook_events IS 'Armazenamento e replay de webhooks da Evolution API';

-- ----------------------------------------------------------------------------
-- 3.6 ALERTS - Alertas do Sistema
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    type VARCHAR(100) NOT NULL,
    severity alert_severity NOT NULL,
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}',

    -- Acknowledgment
    acknowledged BOOLEAN DEFAULT false NOT NULL,
    acknowledged_by UUID REFERENCES users(id),
    acknowledged_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_patient_id ON alerts(patient_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(type);

COMMENT ON TABLE alerts IS 'Alertas e notificações do sistema';

-- ============================================================================
-- SEÇÃO 4: TABELAS DE FLOW MANAGEMENT (9 tabelas)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 4.1 FLOW_KINDS - Tipos de Fluxos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flow_kinds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind_key VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flow_kinds_kind_key ON flow_kinds(kind_key);
CREATE INDEX IF NOT EXISTS idx_flow_kinds_is_active ON flow_kinds(is_active);

COMMENT ON TABLE flow_kinds IS 'Tipos de fluxos conversacionais disponíveis';

-- ----------------------------------------------------------------------------
-- 4.2 FLOW_TEMPLATE_VERSIONS - Versões de Templates de Fluxos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flow_template_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_kind_id UUID REFERENCES flow_kinds(id) NOT NULL,
    version_number INTEGER NOT NULL,
    template_name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Configuração do Fluxo
    steps JSONB NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_flow_template_versions_flow_kind
    ON flow_template_versions(flow_kind_id);
CREATE INDEX IF NOT EXISTS idx_flow_template_versions_active
    ON flow_template_versions(flow_kind_id, is_active)
    WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_flow_template_versions_version
    ON flow_template_versions(flow_kind_id, version_number DESC);

COMMENT ON TABLE flow_template_versions IS 'Versões de templates de fluxos conversacionais';

-- ----------------------------------------------------------------------------
-- 4.3 PATIENT_FLOW_STATES - Estado de Fluxos por Paciente
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patient_flow_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    flow_template_version_id UUID REFERENCES flow_template_versions(id) NOT NULL,

    -- Estado Atual
    current_step INTEGER DEFAULT 0,
    step_data JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active',

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

CREATE INDEX IF NOT EXISTS idx_patient_flow_states_patient
    ON patient_flow_states(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_flow_states_template
    ON patient_flow_states(flow_template_version_id);
CREATE INDEX IF NOT EXISTS idx_patient_flow_states_status
    ON patient_flow_states(status, last_interaction_at);
CREATE INDEX IF NOT EXISTS idx_patient_flow_states_next_scheduled
    ON patient_flow_states(next_scheduled_at)
    WHERE status = 'active' AND next_scheduled_at IS NOT NULL;

COMMENT ON TABLE patient_flow_states IS 'Estado atual de cada paciente em cada tipo de fluxo';

-- ----------------------------------------------------------------------------
-- 4.4 FLOW_MESSAGES - Templates de Mensagens nos Fluxos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flow_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_template_version_id UUID REFERENCES flow_template_versions(id) NOT NULL,
    step_number INTEGER NOT NULL,
    message_key VARCHAR(100) NOT NULL,

    -- Conteúdo
    message_text TEXT NOT NULL,
    message_type VARCHAR(50) DEFAULT 'text',

    -- Interatividade
    buttons JSONB,
    list_items JSONB,

    -- Conditional Logic
    conditions JSONB,

    -- Timing
    delay_seconds INTEGER DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_flow_message UNIQUE(flow_template_version_id, step_number, message_key)
);

CREATE INDEX IF NOT EXISTS idx_flow_messages_template
    ON flow_messages(flow_template_version_id);
CREATE INDEX IF NOT EXISTS idx_flow_messages_step
    ON flow_messages(flow_template_version_id, step_number);

COMMENT ON TABLE flow_messages IS 'Templates de mensagens usadas nos fluxos';

-- ----------------------------------------------------------------------------
-- 4.5 FLOW_ANALYTICS - Analytics dos Fluxos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flow_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_template_version_id UUID REFERENCES flow_template_versions(id),
    patient_id UUID REFERENCES patients(id),

    -- Métricas
    total_steps INTEGER,
    completed_steps INTEGER,
    success_rate DECIMAL(5,2),
    avg_response_time_seconds INTEGER,

    -- Dados Agregados
    step_analytics JSONB,
    interaction_patterns JSONB,

    -- Período
    period_start TIMESTAMP WITH TIME ZONE,
    period_end TIMESTAMP WITH TIME ZONE,

    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flow_analytics_template
    ON flow_analytics(flow_template_version_id);
CREATE INDEX IF NOT EXISTS idx_flow_analytics_patient
    ON flow_analytics(patient_id);
CREATE INDEX IF NOT EXISTS idx_flow_analytics_period
    ON flow_analytics(period_start, period_end);

COMMENT ON TABLE flow_analytics IS 'Analytics e métricas dos fluxos';

-- ----------------------------------------------------------------------------
-- 4.6 FLOW_TEMPLATE_STATS - Estatísticas de Templates
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flow_template_stats (
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

COMMENT ON TABLE flow_template_stats IS 'Estatísticas agregadas dos templates';

-- ----------------------------------------------------------------------------
-- 4.7 FLOW_TEMPLATE_SHARES - Compartilhamento de Templates
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flow_template_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_template_version_id UUID REFERENCES flow_template_versions(id) NOT NULL,
    shared_by UUID REFERENCES users(id) NOT NULL,
    shared_with UUID REFERENCES users(id),

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

COMMENT ON TABLE flow_template_shares IS 'Compartilhamento de templates entre médicos';

-- ----------------------------------------------------------------------------
-- 4.8 FLOW_TEMPLATE_CATEGORIES - Categorias de Templates
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flow_template_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_key VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    icon VARCHAR(100),
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE flow_template_categories IS 'Categorização de templates de fluxos';

-- ----------------------------------------------------------------------------
-- 4.9 FLOW_STATES - Legacy Table (Deprecated)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flow_states (
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

CREATE INDEX IF NOT EXISTS idx_flow_states_patient_id ON flow_states(patient_id);
CREATE INDEX IF NOT EXISTS idx_flow_states_flow_type ON flow_states(flow_type);

COMMENT ON TABLE flow_states IS 'Tabela legacy de estados de fluxo (substituída por patient_flow_states)';

-- ============================================================================
-- SEÇÃO 5: TABELAS DE QUIZ SYSTEM (6 tabelas)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 5.1 QUIZ_TEMPLATES - Templates de Questionários
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    description TEXT,
    questions JSONB NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_quiz_templates_is_active ON quiz_templates(is_active);
CREATE INDEX IF NOT EXISTS idx_quiz_templates_category ON quiz_templates(category);

COMMENT ON TABLE quiz_templates IS 'Templates de questionários para pacientes';

-- ----------------------------------------------------------------------------
-- 5.2 QUIZ_TEMPLATE_VERSIONS_V2 - Versionamento de Questionários
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_template_versions_v2 (
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

CREATE INDEX IF NOT EXISTS idx_quiz_template_versions_v2_template
    ON quiz_template_versions_v2(template_id);
CREATE INDEX IF NOT EXISTS idx_quiz_template_versions_v2_active
    ON quiz_template_versions_v2(template_id, is_active)
    WHERE is_active = true;

COMMENT ON TABLE quiz_template_versions_v2 IS 'Sistema de versionamento aprimorado de questionários';

-- ----------------------------------------------------------------------------
-- 5.3 QUIZ_SESSIONS - Sessões de Questionários (Schema v2 - Cleaned 2025-10-04)
-- ----------------------------------------------------------------------------
-- IMPORTANT: Deprecated fields removed (is_completed, current_question_index, total_score)
-- New schema uses status field ('started', 'completed', 'cancelled') with CHECK constraint
CREATE TABLE IF NOT EXISTS quiz_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    quiz_template_id UUID REFERENCES quiz_templates(id) NOT NULL,

    -- Status da Sessão (NEW SCHEMA v2)
    status VARCHAR(50) DEFAULT 'started' NOT NULL,

    -- Progresso
    current_question INTEGER DEFAULT 0,
    total_questions INTEGER,
    answered_questions INTEGER DEFAULT 0,

    -- Scores
    score NUMERIC(5,2),
    max_score NUMERIC(5,2),
    passed BOOLEAN,

    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    time_spent_seconds INTEGER,

    -- Metadata
    session_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Constraints
    CONSTRAINT quiz_sessions_status_check
        CHECK (status IN ('started', 'completed', 'cancelled'))
);

-- Optimized indexes (v2 - created 2025-10-04)
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_patient_id_v2
    ON quiz_sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_quiz_template_id_v2
    ON quiz_sessions(quiz_template_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_status_v2
    ON quiz_sessions(status);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_created_at_v2
    ON quiz_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_completed_at_v2
    ON quiz_sessions(completed_at DESC)
    WHERE completed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_patient_status_v2
    ON quiz_sessions(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_template_status_v2
    ON quiz_sessions(quiz_template_id, status);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_patient_template_v2
    ON quiz_sessions(patient_id, quiz_template_id, started_at DESC);

-- Unique constraint: one active session per patient per template
CREATE UNIQUE INDEX IF NOT EXISTS idx_quiz_session_unique_active
    ON quiz_sessions(patient_id, quiz_template_id)
    WHERE status = 'started';

COMMENT ON TABLE quiz_sessions IS 'Sessões de questionários respondidos por pacientes (Schema v2 - status-based)';

-- ----------------------------------------------------------------------------
-- 5.4 QUIZ_SESSIONS_V2 - Versão Aprimorada de Sessões
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_sessions_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    template_version_id UUID REFERENCES quiz_template_versions_v2(id) NOT NULL,

    -- Status
    status VARCHAR(50) DEFAULT 'started',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    session_data JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiz_sessions_v2_patient
    ON quiz_sessions_v2(patient_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_v2_template_version
    ON quiz_sessions_v2(template_version_id);

COMMENT ON TABLE quiz_sessions_v2 IS 'Versão melhorada de sessões com suporte a versionamento';

-- ----------------------------------------------------------------------------
-- 5.5 QUIZ_RESPONSES - Respostas de Questionários
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) NOT NULL,
    quiz_template_id UUID REFERENCES quiz_templates(id) NOT NULL,
    session_id UUID REFERENCES quiz_sessions(id),

    -- Pergunta
    question_id VARCHAR(100) NOT NULL,
    question_text TEXT NOT NULL,

    -- Resposta
    response_type VARCHAR(50) NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_quiz_responses_patient_id
    ON quiz_responses(patient_id);
CREATE INDEX IF NOT EXISTS idx_quiz_responses_quiz_template_id
    ON quiz_responses(quiz_template_id);
CREATE INDEX IF NOT EXISTS idx_quiz_responses_responded_at
    ON quiz_responses(responded_at);
CREATE INDEX IF NOT EXISTS idx_quiz_response_session_id
    ON quiz_responses(session_id);
CREATE INDEX IF NOT EXISTS idx_quiz_response_patient_template_index
    ON quiz_responses(patient_id, quiz_template_id, responded_at DESC);
CREATE INDEX IF NOT EXISTS idx_quiz_response_analytics_covering_index
    ON quiz_responses(quiz_template_id, question_id, response_value, responded_at);

COMMENT ON TABLE quiz_responses IS 'Respostas individuais de questionários';

-- ----------------------------------------------------------------------------
-- 5.6 MATERIALIZED VIEWS - Performance Optimization (Rebuilt 2025-10-04)
-- ----------------------------------------------------------------------------

-- Latest patient responses (performance cache)
CREATE MATERIALIZED VIEW IF NOT EXISTS quiz_patient_latest_responses AS
SELECT DISTINCT ON (patient_id, quiz_template_id, question_id)
    patient_id,
    quiz_template_id,
    question_id,
    response_value,
    responded_at
FROM quiz_responses
ORDER BY patient_id, quiz_template_id, question_id, responded_at DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_quiz_latest_responses_unique
    ON quiz_patient_latest_responses(patient_id, quiz_template_id, question_id);

COMMENT ON MATERIALIZED VIEW quiz_patient_latest_responses IS 'Cache de respostas mais recentes por paciente';

-- Template usage statistics (NEW - created 2025-10-04)
CREATE MATERIALIZED VIEW IF NOT EXISTS quiz_template_usage_stats AS
SELECT
    qt.id as template_id,
    qt.name as template_name,
    qt.version as template_version,
    COUNT(qs.id) FILTER (WHERE qs.status = 'completed') as completed_sessions,
    COUNT(qs.id) FILTER (WHERE qs.status = 'started') as active_sessions,
    COUNT(qs.id) FILTER (WHERE qs.status = 'cancelled') as cancelled_sessions,
    AVG(qs.score) FILTER (WHERE qs.status = 'completed') as avg_score,
    MAX(qs.score) FILTER (WHERE qs.status = 'completed') as max_score,
    MIN(qs.score) FILTER (WHERE qs.status = 'completed') as min_score,
    AVG(qs.time_spent_seconds) FILTER (WHERE qs.status = 'completed') as avg_time_seconds,
    COUNT(DISTINCT qs.patient_id) as unique_patients,
    MAX(qs.started_at) as last_used_at
FROM quiz_templates qt
LEFT JOIN quiz_sessions qs ON qt.id = qs.quiz_template_id
GROUP BY qt.id, qt.name, qt.version;

CREATE UNIQUE INDEX IF NOT EXISTS idx_quiz_template_usage_stats_template
    ON quiz_template_usage_stats(template_id);

COMMENT ON MATERIALIZED VIEW quiz_template_usage_stats IS 'Estatísticas de uso de templates de questionários';

-- Patient engagement statistics (NEW - created 2025-10-04)
CREATE MATERIALIZED VIEW IF NOT EXISTS quiz_patient_engagement_stats AS
SELECT
    p.id as patient_id,
    p.name as patient_name,
    COUNT(qs.id) as total_sessions,
    COUNT(qs.id) FILTER (WHERE qs.status = 'completed') as completed_sessions,
    COUNT(qs.id) FILTER (WHERE qs.status = 'started') as active_sessions,
    AVG(qs.score) FILTER (WHERE qs.status = 'completed') as avg_score,
    AVG(qs.time_spent_seconds) FILTER (WHERE qs.status = 'completed') as avg_completion_time_seconds,
    MAX(qs.started_at) as last_session_at,
    COUNT(DISTINCT qs.quiz_template_id) as unique_templates_attempted,
    ROUND(
        COUNT(qs.id) FILTER (WHERE qs.status = 'completed')::NUMERIC /
        NULLIF(COUNT(qs.id), 0) * 100,
        2
    ) as completion_rate_percent
FROM patients p
LEFT JOIN quiz_sessions qs ON p.id = qs.patient_id
GROUP BY p.id, p.name;

CREATE UNIQUE INDEX IF NOT EXISTS idx_quiz_patient_engagement_stats_patient
    ON quiz_patient_engagement_stats(patient_id);

COMMENT ON MATERIALIZED VIEW quiz_patient_engagement_stats IS 'Estatísticas de engajamento de pacientes em questionários';

-- Daily activity summary (NEW - created 2025-10-04)
CREATE MATERIALIZED VIEW IF NOT EXISTS quiz_daily_activity_summary AS
SELECT
    DATE(qs.started_at) as activity_date,
    COUNT(DISTINCT qs.patient_id) as unique_patients,
    COUNT(qs.id) as total_sessions_started,
    COUNT(qs.id) FILTER (WHERE qs.status = 'completed') as sessions_completed,
    COUNT(qs.id) FILTER (WHERE qs.status = 'cancelled') as sessions_cancelled,
    COUNT(DISTINCT qs.quiz_template_id) as unique_templates_used,
    AVG(qs.score) FILTER (WHERE qs.status = 'completed') as avg_score,
    AVG(qs.time_spent_seconds) FILTER (WHERE qs.status = 'completed') as avg_time_seconds,
    ROUND(
        COUNT(qs.id) FILTER (WHERE qs.status = 'completed')::NUMERIC /
        NULLIF(COUNT(qs.id), 0) * 100,
        2
    ) as completion_rate_percent
FROM quiz_sessions qs
GROUP BY DATE(qs.started_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_quiz_daily_activity_summary_date
    ON quiz_daily_activity_summary(activity_date DESC);

COMMENT ON MATERIALIZED VIEW quiz_daily_activity_summary IS 'Resumo diário de atividades em questionários';

-- Template performance metrics (NEW - created 2025-10-04)
CREATE MATERIALIZED VIEW IF NOT EXISTS quiz_template_performance_metrics AS
SELECT
    qt.id as template_id,
    qt.name as template_name,
    qt.category,
    COUNT(qs.id) FILTER (WHERE qs.status = 'completed' AND qs.started_at >= NOW() - INTERVAL '30 days') as completions_last_30d,
    COUNT(qs.id) FILTER (WHERE qs.status = 'completed' AND qs.started_at >= NOW() - INTERVAL '7 days') as completions_last_7d,
    AVG(qs.score) FILTER (WHERE qs.status = 'completed' AND qs.started_at >= NOW() - INTERVAL '30 days') as avg_score_30d,
    AVG(qs.time_spent_seconds) FILTER (WHERE qs.status = 'completed' AND qs.started_at >= NOW() - INTERVAL '30 days') as avg_time_30d,
    ROUND(
        COUNT(qs.id) FILTER (WHERE qs.status = 'completed' AND qs.started_at >= NOW() - INTERVAL '30 days')::NUMERIC /
        NULLIF(COUNT(qs.id) FILTER (WHERE qs.started_at >= NOW() - INTERVAL '30 days'), 0) * 100,
        2
    ) as completion_rate_30d,
    COUNT(DISTINCT qs.patient_id) FILTER (WHERE qs.started_at >= NOW() - INTERVAL '30 days') as unique_users_30d
FROM quiz_templates qt
LEFT JOIN quiz_sessions qs ON qt.id = qs.quiz_template_id
WHERE qt.is_active = true
GROUP BY qt.id, qt.name, qt.category;

CREATE UNIQUE INDEX IF NOT EXISTS idx_quiz_template_performance_metrics_template
    ON quiz_template_performance_metrics(template_id);

COMMENT ON MATERIALIZED VIEW quiz_template_performance_metrics IS 'Métricas de performance de templates (30 dias)';

-- ============================================================================
-- SEÇÃO 6: TABELAS DE ANALYTICS (2 tabelas)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 6.1 MEDICAL_REPORTS - Relatórios Médicos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medical_reports (
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
    report_type VARCHAR(50),
    report_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_medical_reports_patient_id
    ON medical_reports(patient_id);
CREATE INDEX IF NOT EXISTS idx_medical_reports_generated_by
    ON medical_reports(generated_by);
CREATE INDEX IF NOT EXISTS idx_medical_reports_period
    ON medical_reports(period_start, period_end);

COMMENT ON TABLE medical_reports IS 'Relatórios médicos gerados para pacientes';

-- ============================================================================
-- SEÇÃO 7: TABELAS DO SISTEMA ADMIN (10 tabelas)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 7.1 ADMIN_USERS - Usuários Administradores
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_users (
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
    CONSTRAINT valid_email_admin CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT positive_max_sessions CHECK (max_concurrent_sessions > 0),
    CONSTRAINT valid_failed_attempts CHECK (failed_login_attempts >= 0)
);

CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);
CREATE INDEX IF NOT EXISTS idx_admin_users_active ON admin_users(is_active);
CREATE INDEX IF NOT EXISTS idx_admin_users_locked ON admin_users(locked_until)
    WHERE locked_until IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_admin_users_last_login ON admin_users(last_login_at);

COMMENT ON TABLE admin_users IS 'Usuários administradores do sistema';

-- ----------------------------------------------------------------------------
-- 7.2 ADMIN_PERMISSIONS - Permissões do Sistema
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_permission_name CHECK (name ~ '^[a-z0-9_]+\.[a-z0-9_]+$')
);

CREATE INDEX IF NOT EXISTS idx_admin_permissions_category ON admin_permissions(category);

COMMENT ON TABLE admin_permissions IS 'Permissões disponíveis no sistema';

-- ----------------------------------------------------------------------------
-- 7.3 ADMIN_ROLES - Roles Administrativas
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_system_role BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_role_name CHECK (name ~ '^[a-z0-9_]+$')
);

COMMENT ON TABLE admin_roles IS 'Roles do sistema admin';

-- ----------------------------------------------------------------------------
-- 7.4 ADMIN_USER_PERMISSIONS - Many-to-Many (Users ↔ Permissions)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_user_permissions (
    admin_user_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES admin_permissions(id) ON DELETE CASCADE,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    granted_by UUID REFERENCES admin_users(id),

    PRIMARY KEY (admin_user_id, permission_id)
);

CREATE INDEX IF NOT EXISTS idx_admin_user_permissions_user
    ON admin_user_permissions(admin_user_id);

COMMENT ON TABLE admin_user_permissions IS 'Permissões diretas de usuários admin';

-- ----------------------------------------------------------------------------
-- 7.5 ADMIN_ROLE_PERMISSIONS - Many-to-Many (Roles ↔ Permissions)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_role_permissions (
    role_id UUID NOT NULL REFERENCES admin_roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES admin_permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (role_id, permission_id)
);

CREATE INDEX IF NOT EXISTS idx_admin_role_permissions_role
    ON admin_role_permissions(role_id);

COMMENT ON TABLE admin_role_permissions IS 'Permissões associadas a roles';

-- ----------------------------------------------------------------------------
-- 7.6 ADMIN_SESSIONS - Sessões de Administradores
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_sessions (
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

CREATE INDEX IF NOT EXISTS idx_admin_sessions_user_id ON admin_sessions(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_token ON admin_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_active
    ON admin_sessions(is_active, last_activity);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires ON admin_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_ip ON admin_sessions(ip_address);

COMMENT ON TABLE admin_sessions IS 'Sessões ativas de administradores';

-- ----------------------------------------------------------------------------
-- 7.7 ADMIN_AUDIT_LOG - Log de Auditoria Admin
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_audit_log (
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

CREATE INDEX IF NOT EXISTS idx_admin_audit_user_id ON admin_audit_log(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_timestamp ON admin_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_admin_audit_event_type ON admin_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_admin_audit_ip ON admin_audit_log(ip_address);
CREATE INDEX IF NOT EXISTS idx_admin_audit_resource
    ON admin_audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_severity ON admin_audit_log(severity);

COMMENT ON TABLE admin_audit_log IS 'Log de auditoria de ações administrativas';

-- ----------------------------------------------------------------------------
-- 7.8 ADMIN_SECURITY_EVENTS - Eventos de Segurança
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_security_events (
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

CREATE INDEX IF NOT EXISTS idx_security_events_timestamp
    ON admin_security_events(detected_at);
CREATE INDEX IF NOT EXISTS idx_security_events_severity
    ON admin_security_events(severity);
CREATE INDEX IF NOT EXISTS idx_security_events_ip
    ON admin_security_events(ip_address);
CREATE INDEX IF NOT EXISTS idx_security_events_user_id
    ON admin_security_events(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_security_events_resolved
    ON admin_security_events(resolved_at)
    WHERE resolved_at IS NOT NULL;

COMMENT ON TABLE admin_security_events IS 'Eventos de segurança detectados no sistema admin';

-- ----------------------------------------------------------------------------
-- 7.9 ADMIN_IP_WHITELIST - IPs Permitidos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_ip_whitelist (
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

CREATE INDEX IF NOT EXISTS idx_ip_whitelist_active
    ON admin_ip_whitelist(is_active, ip_address);
CREATE INDEX IF NOT EXISTS idx_ip_whitelist_range
    ON admin_ip_whitelist USING gist(ip_range);

COMMENT ON TABLE admin_ip_whitelist IS 'IPs permitidos para acesso admin';

-- ----------------------------------------------------------------------------
-- 7.10 ADMIN_IP_BLACKLIST - IPs Bloqueados
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_ip_blacklist (
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

CREATE INDEX IF NOT EXISTS idx_ip_blacklist_active
    ON admin_ip_blacklist(ip_address, expires_at);

COMMENT ON TABLE admin_ip_blacklist IS 'IPs bloqueados para acesso admin';

-- ============================================================================
-- SEÇÃO 8: TABELAS DE METADATA & SISTEMA (6 tabelas)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 8.1 USER_PROFILES - Perfis Estendidos de Usuários
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_profiles (
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

CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);

COMMENT ON TABLE user_profiles IS 'Perfis estendidos de usuários profissionais';

-- ----------------------------------------------------------------------------
-- 8.2 USER_SYNC_LOG - Log de Sincronização Firebase/Supabase (Updated 2025-10-06)
-- ----------------------------------------------------------------------------
-- UPDATED: Added updated_at column (migration 20251006_add_user_sync_log_updated_at)
CREATE TABLE IF NOT EXISTS user_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(255) NOT NULL,
    supabase_user_id UUID REFERENCES users(id),

    -- Sync Details
    sync_action VARCHAR(50) NOT NULL,
    sync_status VARCHAR(50) NOT NULL,

    -- Data
    firebase_data JSONB,
    supabase_data JSONB,

    -- Error Handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Timing
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL  -- ADDED 2025-10-06
);

CREATE INDEX IF NOT EXISTS idx_user_sync_log_firebase_uid
    ON user_sync_log(firebase_uid);
CREATE INDEX IF NOT EXISTS idx_user_sync_log_supabase_user
    ON user_sync_log(supabase_user_id);
CREATE INDEX IF NOT EXISTS idx_user_sync_log_status
    ON user_sync_log(sync_status, synced_at);
CREATE INDEX IF NOT EXISTS idx_user_sync_log_updated_at
    ON user_sync_log(updated_at);  -- ADDED 2025-10-06

COMMENT ON TABLE user_sync_log IS 'Log de sincronização Firebase ↔ Supabase';
COMMENT ON COLUMN user_sync_log.updated_at IS 'Auto-updated timestamp for record modifications (added 2025-10-06)';

-- ----------------------------------------------------------------------------
-- 8.3 AUDIT_TRAIL - Trilha de Auditoria Geral
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_trail (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(255) NOT NULL,
    record_id UUID NOT NULL,
    operation VARCHAR(50) NOT NULL,

    -- Data Changes
    old_data JSONB,
    new_data JSONB,
    changes JSONB,

    -- Actor Info
    actor_id UUID,
    actor_type VARCHAR(50),
    actor_subject VARCHAR(255),

    -- Request Context
    ip_address INET,
    user_agent TEXT,
    endpoint VARCHAR(500),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_trail_table_record
    ON audit_trail(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_audit_trail_actor
    ON audit_trail(actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_trail_created_at
    ON audit_trail(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_trail_operation
    ON audit_trail(operation, created_at DESC);

COMMENT ON TABLE audit_trail IS 'Trilha de auditoria geral (retenção: 90 dias)';

-- ----------------------------------------------------------------------------
-- 8.4 AUDIT_LOG_ENTRIES - Entradas Genéricas de Auditoria
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log_entries (
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

CREATE INDEX IF NOT EXISTS idx_audit_log_entries_timestamp
    ON audit_log_entries(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_entries_user
    ON audit_log_entries(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_entries_entity
    ON audit_log_entries(entity_type, entity_id);

COMMENT ON TABLE audit_log_entries IS 'Entradas genéricas de log de auditoria';

-- ----------------------------------------------------------------------------
-- 8.5 ALEMBIC_VERSION - Controle de Versão de Migrações (Python)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

COMMENT ON TABLE alembic_version IS 'Controle de versão de migrações Alembic (gerenciado automaticamente)';

-- ----------------------------------------------------------------------------
-- 8.6 CONTACTS - Contatos Gerais
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),

    -- Type
    contact_type VARCHAR(50),

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

CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);
CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type);

COMMENT ON TABLE contacts IS 'Contatos gerais do sistema';

-- ----------------------------------------------------------------------------
-- 8.7 APPOINTMENTS - Agendamentos (Tabela Futura)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appointments (
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

CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled
    ON appointments(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_appointments_status
    ON appointments(status, scheduled_at);

COMMENT ON TABLE appointments IS 'Agendamentos e consultas médicas';

-- ============================================================================
-- SEÇÃO 9: FUNÇÕES E TRIGGERS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 9.1 Função: Updated At Trigger
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_updated_at_column() IS 'Atualiza automaticamente a coluna updated_at';

-- Aplicar triggers em tabelas relevantes
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_messages_updated_at
    BEFORE UPDATE ON messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_flow_states_updated_at
    BEFORE UPDATE ON flow_states
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_quiz_templates_updated_at
    BEFORE UPDATE ON quiz_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_quiz_sessions_updated_at
    BEFORE UPDATE ON quiz_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_quiz_responses_updated_at
    BEFORE UPDATE ON quiz_responses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_medical_reports_updated_at
    BEFORE UPDATE ON medical_reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alerts_updated_at
    BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_users_updated_at
    BEFORE UPDATE ON admin_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_roles_updated_at
    BEFORE UPDATE ON admin_roles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 9.2 Função: User Sync Log Updated At Trigger (Added 2025-10-06)
-- ----------------------------------------------------------------------------
-- CRITICAL FIX: Auto-update timestamp trigger for user_sync_log table
-- Applied via migration 20251006_add_user_sync_log_updated_at

CREATE OR REPLACE FUNCTION update_user_sync_log_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_user_sync_log_updated_at() IS 'Atualiza automaticamente a coluna updated_at na tabela user_sync_log (added 2025-10-06)';

-- Apply trigger to user_sync_log table
CREATE TRIGGER trigger_user_sync_log_updated_at
    BEFORE UPDATE ON user_sync_log
    FOR EACH ROW EXECUTE FUNCTION update_user_sync_log_updated_at();

-- ----------------------------------------------------------------------------
-- 9.3 Funções: Audit Cleanup (Retenção 90 dias)
-- ----------------------------------------------------------------------------

-- Cleanup audit_trail
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
    SELECT pg_total_relation_size('audit_trail') INTO v_size_before;

    DELETE FROM audit_trail
    WHERE created_at < NOW() - INTERVAL '90 days';

    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;

    SELECT pg_total_relation_size('audit_trail') INTO v_size_after;

    RETURN QUERY SELECT
        v_deleted_count,
        pg_size_pretty(v_size_before),
        pg_size_pretty(v_size_after);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION cleanup_old_audit_trail() IS 'Remove entradas de audit_trail com mais de 90 dias';

-- Cleanup audit_log_entries
CREATE OR REPLACE FUNCTION cleanup_old_audit_log_entries()
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
    SELECT pg_total_relation_size('audit_log_entries') INTO v_size_before;

    DELETE FROM audit_log_entries
    WHERE timestamp < NOW() - INTERVAL '90 days';

    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;

    SELECT pg_total_relation_size('audit_log_entries') INTO v_size_after;

    RETURN QUERY SELECT
        v_deleted_count,
        pg_size_pretty(v_size_before),
        pg_size_pretty(v_size_after);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION cleanup_old_audit_log_entries() IS 'Remove entradas de audit_log_entries com mais de 90 dias';

-- Cleanup all audit tables
CREATE OR REPLACE FUNCTION cleanup_all_audit_tables()
RETURNS TABLE(
    table_name TEXT,
    deleted_count INTEGER,
    space_before TEXT,
    space_after TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 'audit_trail'::TEXT, * FROM cleanup_old_audit_trail()
    UNION ALL
    SELECT 'audit_log_entries'::TEXT, * FROM cleanup_old_audit_log_entries();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION cleanup_all_audit_tables() IS 'Remove entradas antigas de todas as tabelas de auditoria';

-- ============================================================================
-- FIM DO SCHEMA MASTER COMPLETO
-- ============================================================================

-- NOTAS:
-- 1. Este arquivo representa o estado completo do banco após 61 migrações aplicadas
--    - 56 migrations anteriores (até 2025-10-02)
--    - 3 migrations aplicadas em 2025-10-04:
--      a) 20251004_drop_rebuild_quiz_materialized_views (reconstrução de views com novo schema)
--      b) 20251004_final_quiz_sessions_cleanup (remoção de campos deprecated)
--      c) 20251004_expand_message_type_enum + add_gin_indexes_jsonb + add_foreign_key_cascade_rules
--    - 1 migration aplicada em 2025-10-06:
--      d) 20251006_add_user_sync_log_updated_at (adiciona coluna updated_at + trigger)
--    - 1 migration aplicada em 2025-10-07:
--      e) 20250930_add_firebase_fields (adiciona 9 campos Firebase à tabela users + user_sync_log)
-- 2. RLS policies não estão incluídas neste arquivo (veja migrations específicas e RELATORIO_REVISAO_RLS.md)
-- 3. Dados iniciais (seeds) não estão incluídos
-- 4. Para aplicar mudanças em produção, use migrations incrementais via Supabase
-- 5. Total de tabelas: 42 (41 documentadas + user_sync_log adicionada em v2.4)
-- 6. Total de ENUMs: 10 (user_role, flow_state, message_direction, message_type (13 valores), message_status,
--    alert_severity, auth_provider, admin_role_type, severity_type, http_method_type)
-- 7. Total de índices: 115+ (incluindo 14 GIN indexes para JSONB + 8 índices v2 quiz_sessions + 2 novos para Firebase)
-- 8. Total de Materialized Views: 5 (quiz_patient_latest_responses + 4 novas views de analytics)
-- 9. Retenção de auditoria: 90 dias (cleanup automático)
-- 10. RLS habilitado: 6+ tabelas críticas (users, patients, medical_reports, quiz_templates, messages, alerts)
-- 11. Última atualização: 2025-10-07 (Firebase authentication integration - 9 campos + user_sync_log)
-- 12. Schema v2 Changes (quiz_sessions):
--     - REMOVED: is_completed (boolean) → replaced by status ('started'|'completed'|'cancelled')
--     - REMOVED: current_question_index (integer) → renamed to current_question
--     - REMOVED: total_score (numeric) → renamed to score
--     - ADDED: CHECK constraint quiz_sessions_status_check for valid status values
--     - ADDED: Unique index for active sessions (one per patient/template)
--     - OPTIMIZED: 8 new v2 indexes replacing old index patterns
-- 13. Firebase Authentication Integration (v2.4):
--     - users.hashed_password agora é NULLABLE (para usuários Firebase-only)
--     - Adicionados 9 campos Firebase: firebase_uid, auth_provider, firebase_last_sign_in,
--       firebase_created_at, firebase_email_verified, firebase_display_name, firebase_photo_url,
--       firebase_custom_claims (JSONB), last_firebase_sync
--     - Criada tabela user_sync_log para auditoria de sincronização Firebase ↔ Supabase
--     - Índices otimizados: idx_users_firebase_uid (partial), idx_users_auth_provider

-- Para verificar a estrutura:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;

-- Para verificar índices:
-- SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname;

-- Para verificar funções:
-- SELECT routine_name FROM information_schema.routines WHERE routine_schema = 'public';
