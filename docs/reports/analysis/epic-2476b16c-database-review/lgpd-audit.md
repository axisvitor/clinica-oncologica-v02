# Auditoria de Conformidade LGPD

Fonte dos dados: `backend-hormonia/.env` (banco real). Data da coleta: 2026-01-09.

## Status de criptografia
- Plaintext columns (cpf/email/phone): nao existem.
- Colunas encrypted/hash: presentes.
- Contagem atual:
  - total_patients: 3
  - cpf_encrypted_count: 2
  - email_encrypted_count: 3
  - phone_encrypted_count: 3

Observacao: 1 paciente sem cpf_encrypted pode indicar CPF ausente (verificar obrigatoriedade).
Consistencia: nenhum registro com hash sem encrypted (ou vice-versa).

## Encryption service
- Algoritmo: Fernet (AES-128-CBC + HMAC-SHA256, conforme app/core/encryption.py).
- Hashing: SHA-256 com salt.
- Key management: variaveis de ambiente.

Referencias:
- `backend-hormonia/app/core/encryption.py`
- `backend-hormonia/app/core/encryption_types.py`
- `backend-hormonia/app/models/patient.py`

## Hashing para busca
- Indices unicos em cpf_hash, email_hash, phone_hash.
- Indices compostos com doctor_id.

## Audit trail
- `lgpd_audit` (esperado no spec): nao existe.
- `lgpd_audit_logs` (modelo atual): existe, mas sem registros.
- `lgpd_data_access_requests`: existe, mas sem registros.

Referencias:
- `backend-hormonia/app/models/lgpd_audit.py`
- `backend-hormonia/docs/guides/audit-archival-guide.md`

## Queries de validacao
```sql
-- Plaintext columns (deve retornar 0 rows)
SELECT column_name, table_name
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name = 'patients'
AND column_name IN ('cpf', 'email', 'phone');

-- Encrypted columns (6 rows)
SELECT column_name, table_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name = 'patients'
AND column_name IN (
    'cpf_encrypted', 'cpf_hash',
    'email_encrypted', 'email_hash',
    'phone_encrypted', 'phone_hash'
)
ORDER BY column_name;

-- Counts
SELECT 
    COUNT(*) AS total_patients,
    COUNT(cpf_encrypted) AS cpf_encrypted_count,
    COUNT(email_encrypted) AS email_encrypted_count,
    COUNT(phone_encrypted) AS phone_encrypted_count
FROM patients;

-- LGPD audit logs
SELECT COUNT(*) FROM lgpd_audit_logs;
SELECT action, COUNT(*) FROM lgpd_audit_logs GROUP BY action;
SELECT COUNT(*) FROM lgpd_data_access_requests;
```

## Findings
- Ver `docs/reports/analysis/epic-2476b16c-database-review/findings.md`.
