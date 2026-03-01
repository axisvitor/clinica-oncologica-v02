# Findings - Revisao Profunda (Componente 1: Banco de Dados)

## Resumo
| Prioridade | Quantidade |
| --- | --- |
| P0 | 0 |
| P1 | 0 |
| P2 | 1 |
| P3 | 1 |

---

### Finding #1: FKs sem indices (15 ocorrencias)

**Prioridade:** P1

**Arquivo/Migracao:** `backend-hormonia/app/models/` (varios) / `migration:21f306d5c4b8`

**Problema:**
15 constraints de FK nao possuem indice, o que impacta performance de joins e deletes.

**Impacto:**
- Risco de degradacao de performance em consultas e cascades
- Afeta tabelas administrativas e operacionais
- Severidade: ALTO

**Evidencia:**
```sql
SELECT 
    c.conname AS constraint_name,
    c.conrelid::regclass AS table_name,
    a.attname AS column_name,
    c.confrelid::regclass AS referenced_table
FROM pg_constraint c
JOIN pg_attribute a ON a.attnum = ANY(c.conkey) AND a.attrelid = c.conrelid
WHERE c.contype = 'f'
AND NOT EXISTS (
    SELECT 1 FROM pg_index i
    WHERE i.indrelid = c.conrelid
    AND a.attnum = ANY(i.indkey)
)
ORDER BY table_name, column_name;
```
Resultado atual: nenhum FK sem indice.

**Status:** RESOLVIDO (migration: 21f306d5c4b8)

**Recomendacao:**
- Curto prazo: criar migracao adicionando indices para cada FK.
- Longo prazo: padronizar indices de FK em modelos e revisao de migrations.

**Estimativa de Correcao:** 6-10 horas

---

### Finding #2: Enum flow_state divergente entre DB e Python

**Prioridade:** P1

**Arquivo/Migracao:** `backend-hormonia/app/models/enums.py`

**Problema:**
O enum `flow_state` no banco contem o valor `inactive`, ausente no enum Python `FlowState`.

**Impacto:**
- Risco de falhas de validacao/serializacao
- Inconsistencia entre DB e ORM
- Severidade: ALTO

**Evidencia:**
```sql
SELECT n.nspname AS schema, t.typname AS enum_name, e.enumlabel AS enum_value
FROM pg_type t 
JOIN pg_enum e ON t.oid = e.enumtypid  
JOIN pg_namespace n ON t.typnamespace = n.oid
WHERE n.nspname = 'public'
AND t.typname = 'flow_state'
ORDER BY e.enumsortorder;
```
Resultado:
```
public,flow_state,onboarding
public,flow_state,active
public,flow_state,paused
public,flow_state,completed
public,flow_state,inactive
public,flow_state,cancelled
```

**Recomendacao:**
- Curto prazo: adicionar `INACTIVE` ao enum Python ou remover/renomear valor no DB.
- Longo prazo: garantir sincronizacao automatica entre enums do ORM e do DB.

**Estimativa de Correcao:** 2-4 horas

**Status:** RESOLVIDO (FlowState atualizado em `backend-hormonia/app/models/enums.py`)

---

### Finding #3: GIN indexes ausentes para JSONB fora de patients

**Prioridade:** P2

**Arquivo/Migracao:** `backend-hormonia/app/models/message.py`, `backend-hormonia/app/models/patient_onboarding_saga.py`, `backend-hormonia/app/models/flow.py` / `migration:4697ee3a60f4`

**Problema:**
JSONB columns relevantes nao possuem GIN indexes.

**Impacto:**
- Queries JSONB podem degradar com crescimento de dados
- Afeta mensagens, saga e flow states
- Severidade: MEDIO

**Evidencia:**
```sql
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema='public'
AND data_type='jsonb'
AND table_name IN ('patient_onboarding_saga','messages','flow_states','patient_flow_states','patients')
ORDER BY table_name, column_name;

SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE indexdef ILIKE '%gin%'
AND tablename IN ('patients', 'patient_onboarding_saga', 'messages', 'flow_states', 'patient_flow_states');
```
Resultado: GIN indexes presentes apenas em `patients`.

**Recomendacao:**
- Curto prazo: criar indices GIN para `messages.message_metadata`, `patient_onboarding_saga.execution_log/step_data/patient_data`, `flow_states.state_data`, `patient_flow_states.flow_metadata/step_data`.
- Longo prazo: padronizar indices JSONB para campos consultados.

**Estimativa de Correcao:** 4-8 horas

**Status:** RESOLVIDO (migration: 4697ee3a60f4)

---

### Finding #4: Webhook tables sem default de UUID

**Prioridade:** P2

**Arquivo/Migracao:** `backend-hormonia/app/models/webhook.py` / `migration:f1878d0fb2fc`

**Problema:**
`webhook_endpoints.id`, `webhook_deliveries.id` e `webhook_logs.id` nao tem `gen_random_uuid()` como default.

**Impacto:**
- Risco de inserts falharem se o app nao seta IDs
- Inconsistencia com BaseModel
- Severidade: MEDIO

**Evidencia:**
```sql
SELECT table_name, column_name, column_default
FROM information_schema.columns
WHERE table_schema = 'public' 
AND column_name = 'id'
AND data_type = 'uuid';
```
Linhas com default vazio:
```
webhook_endpoints,id,
webhook_deliveries,id,
webhook_logs,id,
```

**Recomendacao:**
- Curto prazo: migracao para definir `gen_random_uuid()` e alinhar models com BaseModel.
- Longo prazo: padronizar defaults de UUID em todas as tabelas.

**Estimativa de Correcao:** 4-6 horas

**Status:** RESOLVIDO (migration: f1878d0fb2fc)

---

### Finding #5: lgpd_audit_logs sem registros

**Prioridade:** P2

**Arquivo/Migracao:** `backend-hormonia/app/models/lgpd_audit.py`

**Problema:**
Tabela `lgpd_audit_logs` existe, mas esta vazia.

**Impacto:**
- Risco de falta de audit trail efetivo
- Pode indicar middleware/logging desativado
- Severidade: MEDIO

**Evidencia:**
```sql
SELECT COUNT(*) FROM lgpd_audit_logs;
SELECT COUNT(*) FROM lgpd_data_access_requests;
```
Resultado: `0` (lgpd_audit_logs) e `0` (lgpd_data_access_requests)

**Recomendacao:**
- Curto prazo: validar middleware LGPD e geracao de logs com fluxo real.
- Longo prazo: monitorar preenchimento e criar alertas de ausencia de logs.

**Estimativa de Correcao:** 3-5 horas

**Status:** RESOLVIDO - Integrado Celery task `persist_lgpd_audit_log` em `app/tasks/lgpd_tasks.py` e atualizado `app/middleware/lgpd_middleware.py` para enfileirar registros de auditoria.


### Finding #6: Muitos indices sem uso (idx_scan = 0)

**Prioridade:** P3

**Arquivo/Migracao:** `pg_stat_user_indexes`

**Problema:**
Encontrados 445 indices com `idx_scan = 0`.

**Impacto:**
- Possivel overhead de manutencao (write amplification)
- Pode indicar stats reset ou indices redundantes
- Severidade: BAIXO

**Evidencia:**
```sql
SELECT
    schemaname,
    relname AS tablename,
    indexrelname AS indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE idx_scan = 0
AND schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;
```

**Recomendacao:**
- Curto prazo: verificar `pg_stat_statements` e tempo de uptime/stats reset.
- Longo prazo: revisar indices sem uso e remover os redundantes.

**Estimativa de Correcao:** 1-2 dias
