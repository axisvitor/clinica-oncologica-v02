# Tickets - Revisao Profunda (Componente 1: Banco de Dados)

# [P1] Adicionar indices para FKs sem cobertura

## Descricao
15 FKs nao possuem indices. Isso afeta performance de joins e cascades.

## Impacto
Performance degradada em consultas e operacoes de delete/update.

## Acceptance Criteria
- [x] Criar migracao adicionando indices para todas as FKs listadas. (migration: 21f306d5c4b8)
- [ ] Validar `pg_stat_user_indexes` com idx_scan > 0 apos uso real.
- [ ] Atualizar documentacao de indices em SCHEMA.md.

## Estimativa
6-10 horas

## Referencias
- Finding: #1
- Arquivos: `backend-hormonia/app/models/`
- Migracoes: `migration:21f306d5c4b8`

## Status
RESOLVIDO (migracao aplicada em producao)

---

# [P1] Alinhar enum flow_state entre DB e Python

## Descricao
DB possui valor `inactive` em `flow_state`, ausente em `FlowState` do ORM.

## Impacto
Falhas de validacao/serializacao e inconsistencias no fluxo do paciente.

## Acceptance Criteria
- [x] Definir estrategia (adicionar INACTIVE no ORM ou remover do DB).
- [x] Atualizar enum no DB via migracao, se aplicavel. (nao necessario; DB ja tinha valor)
- [ ] Ajustar testes/validacoes que dependem do enum.

## Estimativa
2-4 horas

## Referencias
- Finding: #2
- Arquivos: `backend-hormonia/app/models/enums.py`
- Migracoes: `migration:n/a`

## Status
RESOLVIDO (FlowState alinhado no ORM)

---

# [P2] Adicionar GIN indexes para JSONB em mensagens/sagas/flow_states

## Descricao
JSONB columns relevantes nao possuem GIN indexes (fora de patients).

## Impacto
Consultas JSONB podem degradar com crescimento de dados.

## Acceptance Criteria
- [x] Criar indices GIN para `messages.message_metadata`.
- [x] Criar indices GIN para `patient_onboarding_saga.execution_log`, `step_data`, `patient_data`.
- [x] Criar indice GIN para `flow_states.state_data`.
- [x] Criar indices GIN para `patient_flow_states.flow_metadata` e `patient_flow_states.step_data`.

## Estimativa
4-8 horas

## Referencias
- Finding: #3
- Arquivos: `backend-hormonia/app/models/message.py`, `backend-hormonia/app/models/patient_onboarding_saga.py`, `backend-hormonia/app/models/flow.py`
- Migracoes: `migration:4697ee3a60f4`

## Status
RESOLVIDO (migration: 4697ee3a60f4)

---

# [P2] Definir default UUID para webhook tables

## Descricao
`webhook_endpoints`, `webhook_deliveries`, `webhook_logs` nao possuem `gen_random_uuid()`.

## Impacto
Inserts podem falhar caso o ID nao seja setado na aplicacao.

## Acceptance Criteria
- [x] Criar migracao adicionando default `gen_random_uuid()` para IDs. (migration: f1878d0fb2fc)
- [ ] Alinhar modelos para herdar `BaseModel` se aplicavel.
- [ ] Validar inserts sem ID explicito.

## Estimativa
4-6 horas

## Referencias
- Finding: #4
- Arquivos: `backend-hormonia/app/models/webhook.py`
- Migracoes: `migration:f1878d0fb2fc`

## Status
RESOLVIDO (defaults alinhados; modelos mantidos em Base)

---

# [P2] Verificar pipeline de logs LGPD (lgpd_audit_logs vazio)

## Descricao
Tabela `lgpd_audit_logs` existe, mas sem registros.

## Impacto
Risco de nao conformidade com audit trail LGPD.

## Acceptance Criteria
- [ ] Validar middleware e pontos de escrita de logs.
- [ ] Executar fluxo real e confirmar inserts na tabela.
- [ ] Criar alerta caso a tabela fique vazia por periodo prolongado.

## Estimativa
3-5 horas

## Referencias
- Finding: #5
- Arquivos: `backend-hormonia/app/models/lgpd_audit.py`

---

# [P3] Revisar indices com idx_scan = 0

## Descricao
Ha 445 indices sem uso segundo `pg_stat_user_indexes`.

## Impacto
Overhead em writes e manutencao de indices.

## Acceptance Criteria
- [ ] Verificar se stats foram resetados recentemente.
- [ ] Rodar analise apos periodo de uso real.
- [ ] Remover indices redundantes se confirmado.

## Estimativa
1-2 dias

## Referencias
- Finding: #6
