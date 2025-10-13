# Database Overview - Clínica Oncológica

## Visão Geral

O banco de dados PostgreSQL da Clínica Oncológica possui **50 tabelas** organizadas em módulos funcionais:

### Módulos Principais

1. **Gestão de Pacientes** (10 tabelas)
   - `patients` - Dados dos pacientes (0 registros ativos, 10 inseridos, 11 deletados)
   - `patient_flow_states` - Estados dos fluxos dos pacientes (0 registros ativos, 12 inseridos, 10 deletados)
   - `contacts` - Contatos relacionados (0 registros)
   - `medical_reports` - Relatórios médicos (0 registros)
   - `appointments` - Agendamentos (0 registros)
   - `alerts` - Alertas do sistema (0 registros)

2. **Sistema de Fluxos** (7 tabelas)
   - `flow_kinds` - Tipos de fluxos (4 registros)
   - `flow_template_versions` - Versões dos templates de fluxo (7 registros)
   - `flow_messages` - Mensagens dos fluxos (0 registros)
   - `flow_analytics` - Analytics dos fluxos (0 registros)
   - `flow_template_categories` - Categorias dos templates (0 registros)
   - `flow_template_shares` - Compartilhamento de templates (0 registros)
   - `flow_template_stats` - Estatísticas dos templates (0 registros)
   - `flow_states` - Estados dos fluxos (0 registros)

3. **Sistema de Quiz** (8 tabelas)
   - `quiz_templates` - Templates de quiz (1 registro)
   - `quiz_sessions` - Sessões de quiz (0 registros ativos, 10 inseridos, 10 deletados)
   - `quiz_responses` - Respostas dos pacientes (0 registros)
   - `quiz_template_versions_v2` - Versões v2 dos templates (0 registros)
   - `quiz_sessions_v2` - Sessões v2 (0 registros)
   - `quiz_template_performance_metrics` - Métricas de performance (0 registros)
   - `quiz_template_usage_stats` - Estatísticas de uso (0 registros)
   - `quiz_daily_activity_summary` - Resumo diário de atividades (0 registros)
   - `quiz_patient_engagement_stats` - Estatísticas de engajamento (0 registros)
   - `quiz_patient_latest_responses` - Últimas respostas dos pacientes (0 registros)

4. **Integração WhatsApp** (3 tabelas)
   - `whatsapp_instances` - Instâncias WhatsApp (1 registro)
   - `whatsapp_contacts` - Contatos WhatsApp (0 registros)
   - `whatsapp_messages` - Mensagens WhatsApp (0 registros)
   - `whatsapp_delivery_failures` - Falhas de entrega WhatsApp (0 registros)

5. **Sistema de Mensagens** (2 tabelas)
   - `messages` - Mensagens do sistema (0 registros ativos, 10 inseridos, 10 deletados)
   - `message_status_events` - Eventos de status das mensagens (0 registros)

6. **Gestão de Usuários** (3 tabelas)
   - `users` - Usuários do sistema (1 registro)
   - `user_profiles` - Perfis dos usuários (0 registros)
   - `user_sync_log` - Log de sincronização (0 registros)

7. **Sistema Administrativo** (10 tabelas)
   - `admin_users` - Usuários administrativos (0 registros)
   - `admin_roles` - Roles administrativos (0 registros)
   - `admin_permissions` - Permissões (0 registros)
   - `admin_sessions` - Sessões administrativas (0 registros)
   - `admin_audit_log` - Log de auditoria administrativa (0 registros)
   - `admin_security_events` - Eventos de segurança (0 registros)
   - `admin_ip_blacklist` - Lista negra de IPs (0 registros)
   - `admin_ip_whitelist` - Lista branca de IPs (0 registros)
   - `admin_role_permissions` - Permissões por role (0 registros)
   - `admin_user_permissions` - Permissões por usuário (0 registros)

8. **Auditoria e Logs** (4 tabelas)
   - `audit_logs` - Logs de auditoria (40 registros)
   - `audit_log_entries` - Entradas de auditoria (0 registros)
   - `audit_trail` - Trilha de auditoria (0 registros)
   - `security_audit_log` - Log de auditoria de segurança (0 registros)
   - `error_logs` - Logs de erro (3 registros)

9. **Webhooks e Eventos** (1 tabela)
   - `webhook_events` - Eventos de webhook (0 registros)

10. **Sistema de Migração** (1 tabela)
    - `alembic_version` - Controle de versões do Alembic (1 registro)

## Status Atual dos Dados

### Dados Críticos Ativos
- ✅ **1 template de quiz ativo**
- ✅ **7 versões de templates de fluxo ativas**
- ✅ **4 tipos de fluxos ativos**
- ✅ **1 usuário ativo**
- ✅ **1 instância WhatsApp configurada**
- ✅ **40 logs de auditoria**
- ✅ **3 logs de erro**

### Distribuição de Dados
- **Logs de Auditoria**: 40 registros
- **Versões de Templates de Fluxo**: 7 registros
- **Tipos de Fluxos**: 4 registros
- **Logs de Erro**: 3 registros
- **Templates de Quiz**: 1 registro
- **Usuários**: 1 registro
- **Instâncias WhatsApp**: 1 registro
- **Controle de Migração**: 1 registro

### Dados de Teste Removidos
- **Pacientes**: 10 inseridos, 11 deletados (CASCADE DELETE funcionando)
- **Sessões de Quiz**: 10 inseridos, 10 deletados
- **Estados de Fluxo**: 12 inseridos, 10 deletados
- **Mensagens**: 10 inseridos, 10 deletados

## Arquitetura de Dados

### Chaves Primárias
- Todas as tabelas usam **UUID** como chave primária
- Geração automática com `gen_random_uuid()`

### Chaves Estrangeiras
- **53 relacionamentos** bem definidos entre módulos
- **Integridade referencial** mantida com CASCADE DELETE aplicado
- **Índices otimizados** para consultas de relacionamento

### Campos JSONB
- `patient_metadata` - Metadados dos pacientes
- `flow_metadata` - Metadados dos fluxos
- `message_metadata` - Metadados das mensagens
- `session_metadata` - Metadados das sessões
- `questions` - Questões dos quizzes (JSONB)

### Enums Personalizados (12 tipos)
- `admin_role_type`: super_admin, admin, manager, supervisor
- `alert_severity`: low, medium, high, critical
- `auth_provider`: local, firebase, google, apple
- `deliverystatus`: scheduled, queued, sending, sent, delivered, read, failed, cancelled
- `flow_state`: onboarding, active, paused, completed, inactive, cancelled
- `http_method_type`: GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD
- `message_direction`: inbound, outbound
- `message_status`: pending, sent, delivered, read, failed, scheduled, sending
- `message_type`: text, button, list, media, location, quiz_intro, quiz_question, quiz_encouragement, quiz_completion, monthly_quiz_link, monthly_quiz_reminder, monthly_quiz_expired, monthly_quiz_completed
- `messagestatus`: pending, scheduled, sending, sent, failed, delivered, read
- `severity_type`: low, medium, high, critical
- `user_role`: doctor, admin

## Performance e Otimização

### Tamanho Total do Banco
- **3.17 MB** de dados totais
- **Maior tabela**: messages (272 kB)
- **Tabelas principais**: error_logs (224 kB), patients (200 kB), audit_logs (192 kB)

### Índices Críticos (Top 10 mais utilizados)
1. `error_logs.idx_error_logs_deduplication`: 56 leituras, 31 fetches
2. `error_logs.error_logs_pkey`: 53 leituras, 28 fetches
3. `users.idx_users_email`: 43 leituras, 43 fetches
4. `alembic_version.alembic_version_pkc`: 43 leituras, 43 fetches
5. `audit_logs.audit_logs_pkey`: 40 leituras, 40 fetches
6. `users.idx_users_firebase_uid`: 18 leituras, 18 fetches
7. `flow_kinds.flow_kinds_pkey`: 12 leituras, 11 fetches
8. `patients.idx_patients_pagination`: 10 leituras, 0 fetches
9. `flow_template_versions.idx_flow_template_versions_version`: 8 leituras, 8 fetches
10. `whatsapp_instances.whatsapp_instances_name_key`: 2 leituras, 0 fetches

### Otimizações Aplicadas
- Índices em foreign keys
- Índices em campos de data/hora
- Índices em campos de status
- Índices únicos para campos críticos (CPF, telefone, email)
- Índices de paginação para consultas eficientes

## Segurança

### Auditoria Completa
- **40 logs de auditoria** ativos
- Logs de todas as operações administrativas
- Trilha de auditoria para mudanças de dados
- Eventos de segurança monitorados
- Controle de acesso por IP

### Validações de Integridade
- Constraints de unicidade
- Validações de dados obrigatórios
- Relacionamentos referenciais com CASCADE DELETE
- Campos de timestamp automáticos
- **14 triggers** para atualização automática de timestamps

## Relacionamentos Principais

### CASCADE DELETE Aplicado
- `alerts.patient_id` → `patients.id` (CASCADE)
- `appointments.patient_id` → `patients.id` (CASCADE)
- `contacts.related_patient_id` → `patients.id` (CASCADE)
- `flow_analytics.patient_id` → `patients.id` (CASCADE)
- `flow_states.patient_id` → `patients.id` (CASCADE)
- `medical_reports.patient_id` → `patients.id` (CASCADE)
- `messages.patient_id` → `patients.id` (CASCADE)
- `patient_flow_states.patient_id` → `patients.id` (CASCADE)
- `quiz_responses.patient_id` → `patients.id` (CASCADE)
- `quiz_sessions.patient_id` → `patients.id` (CASCADE)
- `quiz_sessions_v2.patient_id` → `patients.id` (CASCADE)
- `security_audit_log.patient_id` → `patients.id` (CASCADE)
- `whatsapp_delivery_failures.patient_id` → `patients.id` (CASCADE)

### Relacionamentos de Usuários
- `patients.doctor_id` → `users.id` (NO ACTION)
- `audit_logs.user_id` → `users.id` (SET NULL)
- `contacts.related_user_id` → `users.id` (NO ACTION)
- `flow_template_versions.created_by` → `users.id` (NO ACTION)
- `flow_template_shares.shared_by` → `users.id` (NO ACTION)
- `flow_template_shares.shared_with` → `users.id` (NO ACTION)
- `medical_reports.generated_by` → `users.id` (NO ACTION)
- `quiz_template_versions_v2.created_by` → `users.id` (NO ACTION)
- `user_profiles.user_id` → `users.id` (NO ACTION)
- `user_sync_log.supabase_user_id` → `users.id` (NO ACTION)

## Monitoramento

### Métricas Disponíveis
- Estatísticas de uso de templates
- Métricas de performance de quiz
- Analytics de fluxos
- Logs de erro centralizados
- Resumos de atividade diária

### Alertas Configurados
- Sistema de alertas por paciente
- Monitoramento de eventos de segurança
- Tracking de falhas de mensagens
- Logs de sincronização de usuários

### Views do Sistema
- `pg_stat_statements` - Estatísticas de consultas SQL
- `pg_stat_statements_info` - Informações sobre estatísticas

## Status de Funcionamento

### ✅ Operacional
- **CASCADE DELETE** funcionando corretamente
- **Relacionamentos** íntegros
- **Índices** otimizados e funcionais
- **Triggers** atualizando timestamps automaticamente
- **Enums** bem definidos e utilizados

### 🔧 Melhorias Implementadas
- **Exclusão em cascata** para pacientes e dados relacionados
- **Validação flexível** de datas de tratamento (até 30 dias no futuro)
- **Hash de integridade** nos metadados dos pacientes
- **Paginação corrigida** nos endpoints de alerts e reports

---

**Última atualização**: 2025-10-13 20:12:25
**Total de tabelas**: 50
**Total de registros ativos**: 58
**Tamanho total**: 3.17 MB
**Status geral**: ✅ Operacional e bem estruturado