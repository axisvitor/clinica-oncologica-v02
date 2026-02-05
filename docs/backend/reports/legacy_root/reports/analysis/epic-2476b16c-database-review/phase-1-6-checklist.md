# Fases 1, 5 e 6 - Checklist de Validacao

Fonte dos dados: `backend-hormonia/.env` (banco real). Data da coleta: 2026-01-09.

## Fase 1: Estrutura e Relacionamentos

### 1.1 Primary Keys e UUIDs
Status: PASS

Resultados:
- tables_without_pk: `alembic_version` (tabela padrao do Alembic, sem PK).
- UUIDs com default: webhooks alinhados com `gen_random_uuid()`.

Evidencia (SQL):
```sql
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename NOT IN (
    SELECT tablename FROM pg_indexes WHERE indexname LIKE '%_pkey'
);

SELECT table_name, column_name, column_default
FROM information_schema.columns
WHERE table_schema = 'public' 
AND column_name = 'id'
AND data_type = 'uuid';
```

### 1.2 Foreign Keys e Indices
Status: PASS

FKs sem indices: nenhum encontrado.

### 1.3 Constraints e Enums
Status: PASS

Resultado:
- Constraints listadas sem divergencias evidentes.
- Enum `flow_state` alinhado com `app/models/enums.py`.

Evidencia (SQL):
```sql
SELECT n.nspname AS schema, t.typname AS enum_name, e.enumlabel AS enum_value
FROM pg_type t 
JOIN pg_enum e ON t.oid = e.enumtypid  
JOIN pg_namespace n ON t.typnamespace = n.oid
WHERE n.nspname = 'public'
ORDER BY t.typname, e.enumsortorder;
```

### 1.4 Campos JSONB
Status: PASS

JSONB encontrados:
- `patients.metadata`
- `messages.message_metadata`
- `patient_onboarding_saga.execution_log`, `patient_onboarding_saga.step_data`, `patient_onboarding_saga.patient_data`
- `flow_states.state_data`
- `patient_flow_states.flow_metadata`, `patient_flow_states.step_data`

GIN indexes presentes para `patients`, `messages`, `patient_onboarding_saga`, `flow_states` e `patient_flow_states`.

Evidencia (SQL):
```sql
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema='public'
AND data_type='jsonb'
AND table_name IN ('patient_onboarding_saga','messages','flows','flow_states','patient_flow_states','patients')
ORDER BY table_name, column_name;

SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE indexdef ILIKE '%gin%'
AND tablename IN ('patients', 'patient_onboarding_saga', 'messages', 'flows', 'flow_states', 'patient_flow_states');
```

### 1.5 Soft Delete
Status: PARTIAL

Resultado:
- `deleted_at` presente em `patients` e `uploads`.
- Sem `deleted_at` em `users` (uso de `is_active` como soft delete logico).

Evidencia (SQL):
```sql
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'public'
AND column_name = 'deleted_at';

SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE indexdef LIKE '%deleted_at%';
```

## Fase 5: Integridade Referencial

### 5.1 ON DELETE Cascades
Status: PASS

Resultado:
- Cascades presentes em relacionamentos criticos (ex: alerts, appointments, whatsapp_delivery_failures).
- FKs com `SET NULL` para user_id onde apropriado.

Evidencia (SQL):
```sql
SELECT
    tc.table_name, 
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule,
    rc.update_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
JOIN information_schema.referential_constraints AS rc
  ON rc.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;
```

### 5.2 Relationships bidirecionais
Status: PASS

Referencias:
- `backend-hormonia/app/models/patient.py`
- `backend-hormonia/app/models/user.py`
- `backend-hormonia/app/models/message.py`

### 5.3 Orphan Records
Status: PASS

Resultado (counts):
- messages: 0
- patient_flow_states: 0
- patient_onboarding_saga: 0
- quiz_sessions: 0

Evidencia (SQL):
```sql
SELECT COUNT(*) AS orphan_messages
FROM messages m
LEFT JOIN patients p ON m.patient_id = p.id
WHERE p.id IS NULL;

SELECT COUNT(*) AS orphan_flow_states
FROM patient_flow_states fs
LEFT JOIN patients p ON fs.patient_id = p.id
WHERE p.id IS NULL;

SELECT COUNT(*) AS orphan_onboarding_sagas
FROM patient_onboarding_saga s
LEFT JOIN patients p ON s.patient_id = p.id
WHERE s.patient_id IS NOT NULL AND p.id IS NULL;

SELECT COUNT(*) AS orphan_quiz_sessions
FROM quiz_sessions qs
LEFT JOIN patients p ON qs.patient_id = p.id
WHERE p.id IS NULL;
```

### 5.4 Dependencias circulares
Status: PARTIAL

Resultado:
- Ciclo auto-referencial em `admin_users` (created_by/updated_by). Esperado.

Evidencia (SQL):
```sql
WITH RECURSIVE fk_tree AS (
    SELECT 
        tc.table_name AS from_table,
        ccu.table_name AS to_table,
        1 AS depth,
        ARRAY[tc.table_name] AS path
    FROM information_schema.table_constraints tc
    JOIN information_schema.constraint_column_usage ccu
      ON tc.constraint_name = ccu.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
    
    UNION ALL
    
    SELECT 
        fk.from_table,
        ccu.table_name,
        fk.depth + 1,
        fk.path || ccu.table_name
    FROM fk_tree fk
    JOIN information_schema.table_constraints tc
      ON tc.table_name = fk.to_table
    JOIN information_schema.constraint_column_usage ccu
      ON tc.constraint_name = ccu.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
    AND NOT ccu.table_name = ANY(fk.path)
    AND fk.depth < 10
)
SELECT * FROM fk_tree
WHERE to_table = from_table
ORDER BY depth;
```

## Fase 6: Normalizacao

### 6.1 Validacao de 3NF
Status: PASS

### 6.2 Denormalizacao justificada
Status: PASS

### 6.3 Campos calculados
Status: PASS

Notas:
- `patients.metadata` contem campos de cache (ex: doctor_name) por performance.
- `patients.current_day` calculado a partir de `treatment_start_date`.
- Atualizacao de `doctor_name` depende do fluxo de escrita na API (sem sync automatico no DB).
