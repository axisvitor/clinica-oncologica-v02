# Analise de Performance de Queries

Fonte dos dados: `backend-hormonia/.env` (banco real). Data da coleta: 2026-01-09.

## Resumo
- pg_stat_statements: habilitado.
- Queries > 100ms: 0 entradas no momento da coleta.
- Seq scans: 20 tabelas, tamanhos pequenos (maior ~80 kB).
- Indices nao utilizados: 445 (idx_scan = 0) - revisar e validar stats reset/uso real.

## Top queries lentas (> 100ms)
Nao ha queries com mean_exec_time > 100ms registradas no momento da coleta.

## Indices nao utilizados (idx_scan = 0)
- Total: 445
- Top por tamanho:
  - patients.idx_patients_name_trgm (56 kB)
  - patients.idx_patient_metadata_preferences_gin (24 kB)
  - patients.idx_patients_metadata_gin (24 kB)
  - patients.idx_patient_metadata_gin (24 kB)
  - patients.idx_patient_metadata_consent_gin (24 kB)
  - users.ix_users_permissions_gin (24 kB)

Recomendacao: validar `pg_stat_user_indexes` apos janela de uso real e revisar remocoes.

## Seq scans
Top 10 (todas tabelas pequenas):
```
public,messages,12938,86706,7276,4626,80 kB
public,patients,6555,70194,376,1823,16 kB
public,users,3944,14531,454,289,16 kB
public,flow_template_versions,1485,4477,2594,2685,16 kB
public,quiz_sessions,1273,3756,1056,155,8192 bytes
public,patient_flow_states,1113,2971,212,116,8192 bytes
public,alembic_version,910,757,0,0,8192 bytes
public,alerts,755,0,267,0,0 bytes
public,quiz_responses,650,1400,92,56,8192 bytes
public,patient_onboarding_saga,560,2017,211,138,24 kB
```

## JSONB e GIN
GIN indexes presentes em:
- `patients.metadata` (e subpaths)
- `messages.message_metadata`
- `patient_onboarding_saga.execution_log`, `patient_onboarding_saga.step_data`, `patient_onboarding_saga.patient_data`
- `flow_states.state_data`
- `patient_flow_states.flow_metadata`, `patient_flow_states.step_data`

## EXPLAIN ANALYZE (JSONB)
Nao executado em producao.

## Queries de validacao
```sql
SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements') AS enabled;

SELECT 
    queryid,
    calls,
    total_exec_time,
    mean_exec_time,
    max_exec_time,
    stddev_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY mean_exec_time DESC
LIMIT 20;

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

SELECT 
    schemaname,
    relname AS tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(schemaname||'.'||relname)) AS table_size
FROM pg_stat_user_tables
WHERE schemaname = 'public'
AND seq_scan > 0
ORDER BY seq_scan DESC
LIMIT 20;
```
