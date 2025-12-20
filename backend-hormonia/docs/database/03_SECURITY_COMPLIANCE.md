# 3. Security & Compliance

> **Scope:** LGPD/HIPAA Compliance, Encryption, Auditing, and Access Control.
> **Source:** Consolidated from `LGPD_COMPLIANCE.md` and Audit reports.

---

## 1. LGPD Compliance (Data Protection)

The system is architected to meet **Lei Geral de Proteção de Dados (LGPD)** requirements, specifically regarding sensitive personal data (health info).

### Encryption Strategy
All sensitive Personal Identifiable Information (PII) is encrypted **at rest**.

-   **Algorithm:** AES-256-GCM.
-   **Key Management:** Environment variable `ENCRYPTION_KEY` (32 bytes).
-   **Searchability:** Deterministic SHA-256/HMAC hashes stored alongside encrypted data to allow exact-match lookups without decryption.

| Field | Storage | Search Index |
|-------|---------|--------------|
| **CPF** | `cpf_encrypted` (Text) | `cpf_hash` (SHA-256) |
| **Email** | `email_encrypted` (Bytea) | `email_hash` (HMAC-SHA256) |
| **Phone** | `phone_encrypted` (Bytea) | `phone_hash` (HMAC-SHA256) |

*Note: Plaintext columns for these fields were removed in Migration 024 and 030.*

### Rights of the Data Subject
-   **Right to Access:** API provides full data export.
-   **Right to Delete (Art. 16):** `PatientRepository.hard_delete()` performs a hard delete of PII upon formal request, while maintaining anonymized stats if required. Standard deletion is "Soft Delete" (`deleted_at`).

---

## 2. Audit Trails (HIPAA/LGPD)

### Architecture
We implement an **Immutable Audit Log** system.

-   **Table:** `audit_logs`
-   **Trigger:** Automated checksums prevents undetected tampering.
-   **Retention:** 6 years (Partitioned by year in `audit_logs_archive`).
-   **Scope:** Tracks `WHO` (User ID), `WHAT` (Resource/Action), `WHEN` (Timestamp), `WHERE` (IP/Context).

### Middleware
`app/middleware/hipaa_middleware.py` automatically captures:
-   Modifications (POST/PUT/DELETE/PATCH).
-   Access to sensitive PHI (Read operations).
-   Before/After state diffs.

---

## 3. Row Level Security (RLS)

### Multi-Tenant Isolation
The database supports RLS to strictly isolate data between clinics/doctors at the database engine level.

**Mechanism:**
1.  API receives JWT.
2.  Middleware extracts claims (User ID, Role).
3.  DB Session initializes with `SET app.current_user_id = '...'`.
4.  PostgreSQL Policies enforce `WHERE doctor_id = current_setting('app.current_user_id')`.

*Implementation Status: Configured in `core/database.py`, policies applied via Migrations.*

---

## 4. Key Management & Rotation

-   **Storage:** Keys are never committed. They reside in AWS Secrets Manager / Environment Variables.
-   **Rotation:** A script exists to re-encrypt data with a new key:
    1.  Load data with Old Key.
    2.  Decrypt.
    3.  Encrypt with New Key.
    4.  Update DB.

---

## 5. Security Checklist

-   [x] **Encryption at Rest:** AES-256 for PII.
-   [x] **Encryption in Transit:** TLS 1.2+ enforced for DB connections.
-   [x] **Audit:** Comprehensive, immutable logs.
-   [x] **Least Privilege:** DB Users separated (Migration User vs App User).
-   [x] **Sanitization:** Parameterized queries via SQLAlchemy (No SQL Injection).
-   [x] **Idempotency:** Request deduplication prevents replay attacks.
