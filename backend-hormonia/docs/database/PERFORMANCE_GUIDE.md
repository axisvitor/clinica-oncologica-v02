# Database Performance & Optimization Guide

> Atualizado em **15/10/2025** com base no ambiente de produção PostgreSQL 17.4  
> Total de **244 índices** ativos para otimização de performance

## Status Atual dos Índices (Produção)

**Estatísticas Gerais:**
- **Total de índices**: 244
- **Tabelas com índices**: 45
- **Índices críticos**: 15 principais
- **Performance média**: < 60ms por consulta

**Índices Mais Utilizados:**
1. `error_logs.idx_error_logs_deduplication` - Prevenção de logs duplicados
2. `users.idx_users_email` - Autenticação e login
3. `users.idx_users_firebase_uid` - Integração Firebase
4. `alembic_version` PK - Controle de migrações
5. `patients` índices de paginação - Dashboard médico

## Índices Críticos por Tabela

### 1. Pacientes (`patients`) - 1 registro ativo

**Índices de Performance**:
```sql
-- Consultas por médico (dashboard)
CREATE INDEX idx_patients_doctor_id ON patients(doctor_id);

-- Filtros por estado do fluxo
CREATE INDEX idx_patients_flow_state ON patients(flow_state);

-- Paginação otimizada
CREATE INDEX idx_patients_pagination ON patients(created_at DESC, id);

-- Busca por telefone (WhatsApp)
CREATE INDEX idx_patients_phone ON patients(phone);

-- Filtros por tratamento
CREATE INDEX idx_patients_treatment_type ON patients(treatment_type);
CREATE INDEX idx_patients_treatment_phase ON patients(treatment_phase) 
WHERE treatment_phase IS NOT NULL;
```

**Uso**: Consultas de dashboard, filtros, paginação, integração WhatsApp

### 2. Estados de Fluxo (`patient_flow_states`)

**Índices de Performance**:
```sql
-- Agendamentos pendentes (Celery Beat)
CREATE INDEX idx_patient_flow_states_next_scheduled 
ON patient_flow_states(next_scheduled_at) 
WHERE status = 'active' AND next_scheduled_at IS NOT NULL;

-- Consultas por status
CREATE INDEX idx_patient_flow_states_status 
ON patient_flow_states(status, last_interaction_at);

-- Consultas por paciente
CREATE INDEX idx_patient_flow_states_patient 
ON patient_flow_states(patient_id);

-- Consultas por template
CREATE INDEX idx_patient_flow_states_template 
ON patient_flow_states(flow_template_version_id);
```

**Uso**: Agendamento de mensagens, dashboard de fluxos, analytics

### 3. Mensagens (`messages`)

**Índices de Performance**:
```sql
-- Histórico por paciente (otimizado)
CREATE INDEX idx_messages_patient_direction_created_desc 
ON messages(patient_id, direction, created_at DESC);

-- Mensagens agendadas (worker)
CREATE INDEX idx_messages_scheduled_for 
ON messages(scheduled_for);

-- Filtros por status
CREATE INDEX idx_messages_status 
ON messages(status, created_at DESC);

-- Busca por WhatsApp ID
CREATE INDEX idx_messages_whatsapp_id 
ON messages(whatsapp_id);

-- Mensagens pendentes
CREATE INDEX idx_messages_status_created_desc 
ON messages(status, created_at DESC);
```

**Uso**: Histórico de conversas, processamento de mensagens, webhooks

### 4. Sessões de Quiz (`quiz_sessions`)

**Índices de Performance**:
```sql
-- Uma sessão ativa por paciente
CREATE UNIQUE INDEX idx_quiz_session_unique_active 
ON quiz_sessions(patient_id, quiz_template_id) 
WHERE status = 'started';

-- Histórico por paciente
CREATE INDEX idx_quiz_sessions_patient_template_v2 
ON quiz_sessions(patient_id, quiz_template_id, started_at DESC);

-- Filtros por status
CREATE INDEX idx_quiz_sessions_status_v2 
ON quiz_sessions(status);

-- Analytics por template
CREATE INDEX idx_quiz_sessions_template_status_v2 
ON quiz_sessions(quiz_template_id, status);
```

**Uso**: Controle de sessões, histórico de quiz, analytics

### 5. Templates de Fluxo (`flow_template_versions`)

**Índices de Performance**:
```sql
-- Templates ativos por tipo
CREATE INDEX idx_flow_template_versions_active 
ON flow_template_versions(flow_kind_id, is_active) 
WHERE is_active = true;

-- Versões por tipo
CREATE INDEX idx_flow_template_versions_version 
ON flow_template_versions(flow_kind_id, version_number DESC);

-- Consultas por tipo
CREATE INDEX idx_flow_template_versions_flow_kind 
ON flow_template_versions(flow_kind_id);
```

**Uso**: Seleção de templates, versionamento, dashboard

### 6. Respostas de Quiz (`quiz_responses`)

**Índices de Performance**:
```sql
-- Analytics de respostas (cobertura)
CREATE INDEX idx_quiz_response_analytics_covering_index 
ON quiz_responses(quiz_template_id, question_id, response_value, responded_at);

-- Histórico por paciente
CREATE INDEX idx_quiz_response_patient_template_index 
ON quiz_responses(patient_id, quiz_template_id, responded_at DESC);

-- Consultas por sessão
CREATE INDEX idx_quiz_response_session_id 
ON quiz_responses(quiz_session_id);
```

**Uso**: Analytics de quiz, relatórios, dashboard

## Otimizações Específicas

### 1. Índices Parciais

**Mensagens Pendentes**:
```sql
CREATE INDEX idx_messages_pending 
ON messages(created_at) 
WHERE status = 'pending';
```

**Fluxos Ativos**:
```sql
CREATE INDEX idx_patient_flow_states_active 
ON patient_flow_states(last_interaction_at) 
WHERE status = 'active';
```

**Usuários Ativos**:
```sql
CREATE INDEX idx_users_active 
ON users(email) 
WHERE is_active = true;
```

### 2. Índices GIN para JSONB

**Metadados de Pacientes**:
```sql
CREATE INDEX idx_patients_metadata_gin 
ON patients USING gin(patient_metadata);
```

**Dados de Passos**:
```sql
CREATE INDEX idx_patient_flow_states_step_data_gin 
ON patient_flow_states USING gin(step_data);
```

**Metadados de Sessão**:
```sql
CREATE INDEX idx_quiz_sessions_metadata_gin 
ON quiz_sessions USING gin(session_metadata);
```

### 3. Índices Compostos Otimizados

**Dashboard de Pacientes**:
```sql
CREATE INDEX idx_patients_dashboard 
ON patients(doctor_id, flow_state, created_at DESC);
```

**Analytics de Quiz**:
```sql
CREATE INDEX idx_quiz_analytics 
ON quiz_sessions(quiz_template_id, status, completed_at DESC) 
WHERE completed_at IS NOT NULL;
```

**Mensagens por Período**:
```sql
CREATE INDEX idx_messages_period 
ON messages(patient_id, created_at DESC, direction);
```

## Consultas Otimizadas

### 1. Dashboard de Pacientes
```sql
-- Pacientes por médico com paginação
SELECT p.*, pfs.status as flow_status, pfs.current_step
FROM patients p
LEFT JOIN patient_flow_states pfs ON p.id = pfs.patient_id
WHERE p.doctor_id = $1
ORDER BY p.created_at DESC
LIMIT 20 OFFSET $2;
```

### 2. Mensagens Agendadas
```sql
-- Mensagens para envio (worker)
SELECT m.*, p.phone, p.name
FROM messages m
JOIN patients p ON m.patient_id = p.id
WHERE m.scheduled_for <= now()
AND m.status = 'pending'
ORDER BY m.scheduled_for ASC
LIMIT 100;
```

### 3. Fluxos Pendentes
```sql
-- Fluxos para processamento
SELECT pfs.*, p.name, p.phone
FROM patient_flow_states pfs
JOIN patients p ON pfs.patient_id = p.id
WHERE pfs.next_scheduled_at <= now()
AND pfs.status = 'active'
ORDER BY pfs.next_scheduled_at ASC;
```

### 4. Analytics de Quiz
```sql
-- Estatísticas de quiz por template
SELECT 
    qt.name,
    COUNT(qs.id) as total_sessions,
    COUNT(CASE WHEN qs.passed = true THEN 1 END) as passed_sessions,
    AVG(qs.score) as avg_score
FROM quiz_templates qt
LEFT JOIN quiz_sessions qs ON qt.id = qs.quiz_template_id
WHERE qt.is_active = true
GROUP BY qt.id, qt.name;
```

## Monitoramento de Performance

### 1. Consultas Lentas
```sql
-- Identificar consultas lentas
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    rows
FROM pg_stat_statements
WHERE mean_time > 1000  -- > 1 segundo
ORDER BY mean_time DESC
LIMIT 10;
```

### 2. Índices Não Utilizados
```sql
-- Índices não utilizados
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE idx_tup_read = 0
AND schemaname = 'public';
```

### 3. Tabelas com Mais Atividade
```sql
-- Tabelas mais acessadas
SELECT 
    schemaname,
    tablename,
    seq_tup_read,
    seq_tup_returned,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY seq_tup_read + idx_tup_read DESC;
```

## Recomendações de Manutenção

### 1. Análise Regular
- Executar `ANALYZE` semanalmente
- Monitorar crescimento de tabelas
- Verificar fragmentação de índices

### 2. Limpeza de Dados
- Arquivar logs antigos (> 1 ano)
- Limpar sessões de quiz antigas
- Remover mensagens processadas antigas

### 3. Otimizações Futuras
- Considerar particionamento por data
- Implementar cache para consultas frequentes
- Otimizar consultas de analytics

---

## Resumo de Performance (Produção)

**Status Atual:**
- ✅ **244 índices** ativos e otimizados
- ✅ **Performance média** < 60ms por consulta
- ✅ **Índices críticos** funcionando corretamente
- ✅ **Monitoramento** ativo com `pg_stat_statements`

**Próximos Passos:**
1. Monitorar crescimento dos índices com aumento de dados
2. Implementar análise automática de performance
3. Considerar otimizações específicas para templates de fluxo

## Métricas de Performance Atuais

### Tabelas com Mais Registros
- `pg_stat_statements`: 4,920 registros
- `audit_logs`: 20 registros
- `patients`: 10 registros
- `quiz_sessions`: 10 registros
- `patient_flow_states`: 10 registros

### Status de Índices
- ✅ Todos os foreign keys indexados
- ✅ Índices compostos otimizados
- ✅ Índices parciais implementados
- ✅ Índices GIN para JSONB
- ✅ Constraints de unicidade

### Performance Geral
- ✅ Estrutura otimizada para crescimento
- ✅ Consultas principais indexadas
- ✅ Relacionamentos bem definidos
- ✅ Sem problemas críticos identificados
