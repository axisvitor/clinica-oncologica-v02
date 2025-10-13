# Database Overview - Clínica Oncológica

## Visão Geral

O banco de dados PostgreSQL da Clínica Oncológica possui **44 tabelas** organizadas em módulos funcionais:

### Módulos Principais

1. **Gestão de Pacientes** (10 tabelas)
   - `patients` - Dados dos pacientes (10 registros)
   - `patient_flow_states` - Estados dos fluxos dos pacientes (10 registros)
   - `contacts` - Contatos relacionados
   - `medical_reports` - Relatórios médicos
   - `appointments` - Agendamentos
   - `alerts` - Alertas do sistema

2. **Sistema de Fluxos** (7 tabelas)
   - `flow_kinds` - Tipos de fluxos (4 registros)
   - `flow_template_versions` - Versões dos templates de fluxo (7 registros)
   - `flow_messages` - Mensagens dos fluxos
   - `flow_analytics` - Analytics dos fluxos
   - `flow_template_categories` - Categorias dos templates
   - `flow_template_shares` - Compartilhamento de templates
   - `flow_template_stats` - Estatísticas dos templates

3. **Sistema de Quiz** (8 tabelas)
   - `quiz_templates` - Templates de quiz (1 registro)
   - `quiz_sessions` - Sessões de quiz (10 registros)
   - `quiz_responses` - Respostas dos pacientes
   - `quiz_template_versions_v2` - Versões v2 dos templates
   - `quiz_sessions_v2` - Sessões v2
   - `quiz_template_performance_metrics` - Métricas de performance
   - `quiz_template_usage_stats` - Estatísticas de uso
   - `quiz_daily_activity_summary` - Resumo diário de atividades
   - `quiz_patient_engagement_stats` - Estatísticas de engajamento
   - `quiz_patient_latest_responses` - Últimas respostas dos pacientes

4. **Integração WhatsApp** (3 tabelas)
   - `whatsapp_instances` - Instâncias WhatsApp (1 registro)
   - `whatsapp_contacts` - Contatos WhatsApp
   - `whatsapp_messages` - Mensagens WhatsApp

5. **Sistema de Mensagens** (2 tabelas)
   - `messages` - Mensagens do sistema (10 registros)
   - `message_status_events` - Eventos de status das mensagens

6. **Gestão de Usuários** (3 tabelas)
   - `users` - Usuários do sistema (1 registro)
   - `user_profiles` - Perfis dos usuários
   - `user_sync_log` - Log de sincronização

7. **Sistema Administrativo** (10 tabelas)
   - `admin_users` - Usuários administrativos
   - `admin_roles` - Roles administrativos
   - `admin_permissions` - Permissões
   - `admin_sessions` - Sessões administrativas
   - `admin_audit_log` - Log de auditoria administrativa
   - `admin_security_events` - Eventos de segurança
   - `admin_ip_blacklist` - Lista negra de IPs
   - `admin_ip_whitelist` - Lista branca de IPs
   - `admin_role_permissions` - Permissões por role
   - `admin_user_permissions` - Permissões por usuário

8. **Auditoria e Logs** (4 tabelas)
   - `audit_logs` - Logs de auditoria (20 registros)
   - `audit_log_entries` - Entradas de auditoria
   - `audit_trail` - Trilha de auditoria
   - `security_audit_log` - Log de auditoria de segurança
   - `error_logs` - Logs de erro (2 registros)

9. **Webhooks e Eventos** (1 tabela)
   - `webhook_events` - Eventos de webhook

## Status Atual dos Dados

### Dados Críticos Ativos
- ✅ **1 template de quiz ativo**
- ✅ **7 versões de templates de fluxo ativas**
- ✅ **10 pacientes com fluxos ativos**
- ✅ **1 usuário administrador ativo**
- ✅ **1 instância WhatsApp configurada**

### Distribuição de Dados
- **Pacientes**: 10 registros
- **Sessões de Quiz**: 10 registros
- **Estados de Fluxo**: 10 registros
- **Mensagens**: 10 registros
- **Logs de Auditoria**: 20 registros
- **Logs de Erro**: 2 registros

## Arquitetura de Dados

### Chaves Primárias
- Todas as tabelas usam **UUID** como chave primária
- Geração automática com `gen_random_uuid()`

### Chaves Estrangeiras
- Relacionamentos bem definidos entre módulos
- Integridade referencial mantida
- Índices otimizados para consultas de relacionamento

### Campos JSONB
- `patient_metadata` - Metadados dos pacientes
- `flow_metadata` - Metadados dos fluxos
- `message_metadata` - Metadados das mensagens
- `session_metadata` - Metadados das sessões
- `questions` - Questões dos quizzes (JSONB)

### Enums Personalizados
- `flow_state` - Estados dos fluxos
- `user_role` - Roles dos usuários
- `auth_provider` - Provedores de autenticação
- `message_type` - Tipos de mensagem
- `message_status` - Status das mensagens
- `message_direction` - Direção das mensagens

## Performance e Otimização

### Índices Críticos
- **Índices compostos** para consultas frequentes
- **Índices parciais** para filtros específicos
- **Índices GIN** para campos JSONB
- **Índices de cobertura** para consultas analíticas

### Otimizações Aplicadas
- Índices em foreign keys
- Índices em campos de data/hora
- Índices em campos de status
- Índices únicos para campos críticos (CPF, telefone, email)

## Segurança

### Auditoria Completa
- Logs de todas as operações administrativas
- Trilha de auditoria para mudanças de dados
- Eventos de segurança monitorados
- Controle de acesso por IP

### Validações de Integridade
- Constraints de unicidade
- Validações de dados obrigatórios
- Relacionamentos referenciais
- Campos de timestamp automáticos

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

---

**Última atualização**: $(date)
**Total de tabelas**: 44
**Status geral**: ✅ Operacional e bem estruturado
