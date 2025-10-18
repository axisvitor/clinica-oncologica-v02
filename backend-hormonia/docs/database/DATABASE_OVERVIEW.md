# Database Overview – Clínica Oncológica

> Atualizado em **15/10/2025** com base no snapshot do ambiente de produção.  
> O banco de produção utiliza **PostgreSQL 17.4**; a estrutura descrita abaixo é a mesma em todos os ambientes.

---

## Visão Geral

- **Motor**: PostgreSQL 17.4  
- **Quantidade de tabelas**: 45  
- **Principais módulos**: pacientes, fluxos, quiz mensal, mensagens/WhatsApp, administração, auditoria  
- **Chaves primárias**: todas as tabelas utilizam `UUID` (`gen_random_uuid()`)  
- **Relacionamentos**: 53 chaves estrangeiras ativas, com políticas `CASCADE`, `SET NULL` ou `NO ACTION` conforme a criticidade
- **Triggers**: 14 gatilhos mantêm carimbos de data/hora e integridade auxiliar
- **Enums personalizados**: 12 tipos (fluxos, severidade, status de mensagens, papéis de usuário, etc.)
- **Índices**: 244 índices para otimização de performance

---

## Módulos Principais

1. **Gestão de Pacientes** (10 tabelas)  
   `patients`, `patient_flow_states`, `contacts`, `medical_reports`, `appointments`, `alerts`…  
   - *Registros ativos no snapshot*: 1 paciente, 1 médico vinculado
2. **Sistema de Fluxos** (7 tabelas)  
   `flow_kinds`, `flow_template_versions`, `flow_messages`, `flow_analytics`…  
   - 4 tipos de fluxo e 7 versões de templates (4 ativas após limpeza de versões v1)
3. **Quiz Mensal** (até 10 tabelas)  
   `quiz_templates`, `quiz_sessions`, `quiz_responses`, tabelas de métricas e históricos  
   - 1 template de quiz ativo com 10 perguntas completas
4. **Integração WhatsApp** (3 tabelas)  
   `whatsapp_instances`, `whatsapp_contacts`, `whatsapp_messages`, `whatsapp_delivery_failures`
5. **Mensagens & Comunicação** (2 tabelas)  
   `messages`, `message_status_events`
6. **Gestão de Usuários** (3 tabelas)  
   `users`, `user_profiles`, `user_sync_log` (coluna legada `supabase_user_id` será renomeada)
7. **Administração** (10 tabelas)  
   `admin_users`, `admin_roles`, `admin_permissions`, `admin_sessions`, `admin_audit_log`…
8. **Auditoria e Logs** (5 tabelas)  
   `audit_logs`, `audit_log_entries`, `audit_trail`, `security_audit_log`, `error_logs`
9. **Webhooks & Eventos**  
   `webhook_events`
10. **Migrações**  
    `alembic_version`

---

## Status dos Dados (snapshot produção)

| Item                                    | Valor |
|-----------------------------------------|-------|
| Pacientes ativos                        | 1     |
| Templates de quiz                       | 1     |
| Tipos de fluxo                          | 4     |
| Versões de templates de fluxo           | 7     |
| Templates de fluxo ativos (após limpeza)| 4     |
| Usuários ativos                         | 1     |
| Instâncias WhatsApp configuradas        | 1     |
| Logs de auditoria                       | 44    |
| Logs de erro                            | 3     |
| Total de registros ativos (aprox.)      | 63    |
| Tamanho estimado do banco (produção)    | 13 MB |

> **Observação:** os números acima representam o estado atual de produção após limpeza de templates v1 e validação completa.

### Dados de teste removidos recentemente
- Pacientes: 10 inserções / 11 exclusões (validação do CASCADE)
- Sessões de quiz: 10 inserções / 10 exclusões
- Estados de fluxo: 12 inserções / 10 exclusões
- Mensagens: 10 inserções / 10 exclusões

---

## Arquitetura e Integridade

- **Metadados em JSONB**: campos `patient_data`, `flow_metadata`, `message_metadata`, `session_metadata`, `questions`
- **Relacionamentos relevantes**
  - `patients` é pai cascata para alerts, appointments, flow_states, quiz_responses/sessions, mensagens e logs
  - `users` relaciona-se com pacientes (médico responsável) e audit trails
- **Índices críticos (uso recente)**
  1. `error_logs.idx_error_logs_deduplication`
  2. `users.idx_users_email`
  3. `users.idx_users_firebase_uid`
  4. `alembic_version` PK
  5. Índices de paginação em `patients`
- **Políticas de segurança**
  - Auditoria completa (`audit_logs`, `admin_audit_log`, `security_audit_log`)
  - Controle por IP (`admin_ip_blacklist/whitelist`)
  - RLS configurado para sessões autenticadas (contexto JWT definido na aplicação)

---

## Notas sobre a Migração para AWS

- O cliente Supabase foi desativado; todas as conexões utilizam SQLAlchemy diretamente no RDS.
- Variáveis de ambiente `SUPABASE_*` permanecem apenas por compatibilidade com scripts antigos e serão eliminadas quando possível.
- A autenticação e autorização agora dependem exclusivamente do **Firebase Admin SDK** (tokens RS256). A coluna `user_sync_log.supabase_user_id` será renomeada em futura migração para refletir a nova origem do dado.

---

## Monitoramento e Métricas

- Métricas de quiz, fluxos e mensagens consolidadas em views e tabelas dedicadas.
- `pg_stat_statements` habilitado para análise de performance.
- Job de auditoria (`audit_cleanup`) revisa periodicamente os registros do módulo administrativo.
- Alertas automáticos para falhas de WhatsApp, eventos de segurança e integrações.

---

## Resumo Final

- **Motor**: PostgreSQL 17.4  
- **Estado geral**: ✅ operacional e consistente  
- **Última atualização**: 2025-10-15 01:15:00  
- **Tamanho (snapshot staging)**: 3.17 MB  
- **Próximos passos recomendados**:
  1. Renomear colunas herdadas de Supabase (ex.: `user_sync_log.supabase_user_id`).
  2. Ampliar métricas reais em produção (dashboards de auditoria e quiz).
  3. Automatizar export periódico de estatísticas (`pg_stat_statements`) para acompanhamento de performance.

