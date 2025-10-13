# Database Schema Reference

## Tabelas Principais

### 1. Pacientes (`patients`)

**Propósito**: Armazena dados dos pacientes oncológicos

```sql
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id UUID NOT NULL REFERENCES users(id),
    phone VARCHAR NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    email VARCHAR,
    birth_date DATE,
    treatment_type VARCHAR,
    treatment_start_date DATE,
    treatment_phase VARCHAR,
    diagnosis TEXT,
    flow_state flow_state NOT NULL DEFAULT 'onboarding',
    current_day INTEGER NOT NULL DEFAULT 0,
    cpf VARCHAR UNIQUE,
    doctor_notes TEXT,
    patient_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);
```

**Índices Críticos**:
- `idx_patients_doctor_id` - Consultas por médico
- `idx_patients_flow_state` - Filtros por estado do fluxo
- `idx_patients_phone` - Busca por telefone
- `idx_patients_cpf_unique` - Validação de CPF único

### 2. Estados de Fluxo (`patient_flow_states`)

**Propósito**: Controla o progresso dos pacientes nos fluxos

```sql
CREATE TABLE patient_flow_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id),
    flow_template_version_id UUID NOT NULL REFERENCES flow_template_versions(id),
    current_step INTEGER DEFAULT 0,
    step_data JSONB DEFAULT '{}',
    status VARCHAR DEFAULT 'active',
    started_at TIMESTAMPTZ DEFAULT now(),
    last_interaction_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    next_scheduled_at TIMESTAMPTZ,
    flow_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(patient_id, flow_template_version_id)
);
```

**Índices Críticos**:
- `idx_patient_flow_states_next_scheduled` - Agendamentos pendentes
- `idx_patient_flow_states_status` - Filtros por status
- `unique_patient_flow` - Um fluxo por paciente

### 3. Templates de Fluxo (`flow_template_versions`)

**Propósito**: Versões dos templates de fluxo de acompanhamento

```sql
CREATE TABLE flow_template_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_kind_id UUID NOT NULL REFERENCES flow_kinds(id),
    version_number INTEGER NOT NULL,
    template_name VARCHAR NOT NULL,
    description TEXT,
    steps JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT false,
    is_draft BOOLEAN DEFAULT true,
    published_at TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(flow_kind_id, version_number)
);
```

**Índices Críticos**:
- `idx_flow_template_versions_active` - Templates ativos
- `idx_flow_template_versions_version` - Versões por tipo

### 4. Tipos de Fluxo (`flow_kinds`)

**Propósito**: Categorização dos tipos de fluxo disponíveis

```sql
CREATE TABLE flow_kinds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind_key VARCHAR NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**Dados Atuais**: 4 tipos de fluxo configurados

### 5. Templates de Quiz (`quiz_templates`)

**Propósito**: Templates dos quizzes mensais

```sql
CREATE TABLE quiz_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    version VARCHAR NOT NULL,
    description TEXT,
    questions JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    category VARCHAR,
    tags TEXT[],
    passing_score INTEGER,
    time_limit_minutes INTEGER,
    randomize_questions BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**Dados Atuais**: 1 template ativo

### 6. Sessões de Quiz (`quiz_sessions`)

**Propósito**: Sessões individuais de quiz dos pacientes

```sql
CREATE TABLE quiz_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id),
    quiz_template_id UUID NOT NULL REFERENCES quiz_templates(id),
    status VARCHAR DEFAULT 'started',
    current_question INTEGER DEFAULT 0,
    total_questions INTEGER,
    answered_questions INTEGER DEFAULT 0,
    score NUMERIC,
    max_score NUMERIC,
    passed BOOLEAN,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    time_spent_seconds INTEGER,
    session_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**Índices Críticos**:
- `idx_quiz_session_unique_active` - Uma sessão ativa por paciente
- `idx_quiz_sessions_patient_template_v2` - Histórico por paciente

### 7. Mensagens (`messages`)

**Propósito**: Mensagens enviadas e recebidas via WhatsApp

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id),
    direction message_direction NOT NULL,
    type message_type DEFAULT 'text',
    content TEXT,
    message_metadata JSONB DEFAULT '{}',
    whatsapp_id VARCHAR,
    status message_status DEFAULT 'pending',
    scheduled_for TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    delivery_status message_delivery_status,
    retry_count INTEGER DEFAULT 0,
    last_retry_at TIMESTAMPTZ,
    failure_reason TEXT,
    next_retry_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Índices Críticos**:
- `idx_messages_patient_direction_created_desc` - Histórico por paciente
- `idx_messages_status` - Filtros por status
- `idx_messages_scheduled_for` - Mensagens agendadas

### 8. Usuários (`users`)

**Propósito**: Usuários do sistema (médicos e administradores)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR NOT NULL UNIQUE,
    hashed_password VARCHAR,
    full_name VARCHAR,
    role user_role DEFAULT 'doctor',
    is_active BOOLEAN DEFAULT true,
    firebase_uid VARCHAR UNIQUE,
    auth_provider auth_provider DEFAULT 'local',
    firebase_last_sign_in TIMESTAMPTZ,
    firebase_created_at TIMESTAMPTZ,
    firebase_email_verified BOOLEAN DEFAULT false,
    firebase_display_name VARCHAR,
    firebase_photo_url VARCHAR,
    firebase_custom_claims JSONB DEFAULT '{}',
    last_firebase_sync TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Dados Atuais**: 1 usuário ativo

### 9. Instâncias WhatsApp (`whatsapp_instances`)

**Propósito**: Configuração das instâncias WhatsApp

```sql
CREATE TABLE whatsapp_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL UNIQUE,
    api_url VARCHAR NOT NULL,
    api_token VARCHAR NOT NULL,
    webhook_url VARCHAR,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**Dados Atuais**: 1 instância configurada

## Enums Personalizados

### Estados de Fluxo (`flow_state`)
```sql
CREATE TYPE flow_state AS ENUM (
    'onboarding',
    'active',
    'paused',
    'completed',
    'cancelled',
    'inactive' -- legacy alias retained for backward compatibility
);
```

### Roles de Usuário (`user_role`)
```sql
CREATE TYPE user_role AS ENUM (
    'doctor',
    'admin',
    'nurse',
    'coordinator'
);
```

### Tipos de Mensagem (`message_type`)
```sql
CREATE TYPE message_type AS ENUM (
    'text',
    'image',
    'document',
    'audio',
    'video',
    'location',
    'contact',
    'template',
    'button',
    'list',
    'media',
    'quiz_intro',
    'quiz_question',
    'quiz_encouragement',
    'quiz_completion',
    'monthly_quiz_link',
    'monthly_quiz_reminder',
    'monthly_quiz_expired',
    'monthly_quiz_completed'
);
```

### Status de Mensagem (`message_status`)
```sql
CREATE TYPE message_status AS ENUM (
    'pending',
    'scheduled',
    'sending',
    'sent',
    'delivered',
    'read',
    'failed',
    'cancelled'
);
```

### Direção de Mensagem (`message_direction`)
```sql
CREATE TYPE message_direction AS ENUM (
    'inbound',
    'outbound'
);
```

## Relacionamentos Críticos

### Hierarquia de Fluxos
```
flow_kinds (1) -> flow_template_versions (N) -> patient_flow_states (N) -> patients (1)
```

### Hierarquia de Quiz
```
quiz_templates (1) -> quiz_sessions (N) -> quiz_responses (N) -> patients (1)
```

### Comunicação
```
patients (1) -> messages (N) -> whatsapp_instances (1)
```

### Auditoria
```
users (1) -> audit_logs (N)
patients (1) -> security_audit_log (N)
```

## Constraints de Integridade

### Unicidade
- CPF único por paciente
- Telefone único por paciente
- Email único por usuário
- Uma sessão ativa de quiz por paciente
- Um fluxo ativo por paciente por template

### Referenciais
- Todos os foreign keys têm constraints
- Cascade apropriado para deleções
- Validação de dados obrigatórios

## Performance

### Índices Compostos
- Consultas por paciente + data
- Filtros por status + data
- Buscas por médico + estado

### Índices Parciais
- Apenas registros ativos
- Apenas registros não processados
- Apenas registros com erro

### Índices GIN
- Campos JSONB para consultas complexas
- Arrays para busca em tags
- Metadados para filtros avançados
