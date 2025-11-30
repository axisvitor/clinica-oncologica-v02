# Database Documentation

Welcome to the Hormonia Backend database documentation.

> **Last Updated:** 2025-11-25 11:47:15

## 📂 Directory Structure

### 📘 [Reference](./reference/)
**The current source of truth for the database schema.**
- **[SCHEMA_DOCUMENTATION.md](./reference/SCHEMA_DOCUMENTATION.md)**: Human-readable documentation of all tables and columns.
- **[TABLES_REFERENCE.md](./reference/TABLES_REFERENCE.md)**: Detailed reference for tables.
- **[complete_schema.json](./reference/complete_schema.json)**: Machine-readable full schema export.
- **[schema_diagram.mmd](./reference/schema_diagram.mmd)**: Mermaid ER diagram.

### 📗 [Guides](./guides/)
**Operational guides and procedures.**
- **[BACKUP_RESTORE_GUIDE.md](./guides/BACKUP_RESTORE_GUIDE.md)**: How to backup and restore the database.
- **[DATA_MIGRATION_STRATEGY.md](./guides/DATA_MIGRATION_STRATEGY.md)**: Strategy for data migrations.
- **[KEY_ROTATION_GUIDE.md](./guides/KEY_ROTATION_GUIDE.md)**: Encryption key rotation procedures.
- **[AUDIT_ARCHIVAL_GUIDE.md](./guides/AUDIT_ARCHIVAL_GUIDE.md)**: Audit log archival and retention.

### 📜 [History](./history/)
**Archives of past migration projects and logs.**
- **[2025-11-migration-project](./history/2025-11-migration-project/)**: Logs and reports from the major migration project (Nov 2025).
- **[Legacy](./history/legacy/)**: Old manual documentation and archives.

## 🚀 Quick Start

1.  **View the Schema:** Check [SCHEMA_DOCUMENTATION.md](./reference/SCHEMA_DOCUMENTATION.md).
2.  **Visualize:** Render [schema_diagram.mmd](./reference/schema_diagram.mmd) in VS Code or GitHub.
3.  **Manage Migrations:** Use Alembic in the `backend-hormonia` directory.

```bash
# Check current revision
alembic current

# Upgrade to head
alembic upgrade head
```

## 📊 Database Overview

| Metric | Value |
|--------|-------|
| **Type** | PostgreSQL 14+ on **Amazon RDS** (sa-east-1) |
| **ORM** | SQLAlchemy 2.0+ (async support) |
| **Migration Tool** | Alembic (29 migrations) |
| **Total Tables** | 56 |
| **Total Columns** | ~820 |
| **Total Indexes** | ~350 |
| **Foreign Keys** | 58 |
| **Custom Enums** | 17 PostgreSQL enums |
| **Authentication** | Firebase Admin SDK |
| **Cache** | Redis Cloud |

### Key Features

- ✅ JSONB storage for flexible metadata
- ✅ Soft deletes (`deleted_at`) 
- ✅ Audit logging (HIPAA/LGPD compliant)
- ✅ Partitioned archive tables (2025-2031)
- ✅ Cursor-based pagination for V2 API
- ✅ CPF encryption (LGPD compliance)
- ✅ Row-level security ready

### Table Categories

| Category | Tables | Description |
|----------|--------|-------------|
| **Core** | 4 | Patients, Users, Profiles, Contacts |
| **Admin & Security** | 10 | Admin users, roles, permissions, sessions |
| **Messaging** | 4 | Messages, templates, status tracking |
| **WhatsApp** | 5 | Evolution API integration |
| **Flows** | 9 | Treatment flow management |
| **Quiz** | 6 | Patient questionnaires |
| **Medical** | 4 | Reports, appointments, alerts, AI summaries |
| **Audit & Logging** | 5 | Audit trails, error logs |
| **System** | 5 | Health, incidents, migrations |

### PostgreSQL Enums (17)

```sql
-- Key enums used in the schema
admin_role_type: super_admin, admin, manager, supervisor
flow_state: onboarding, active, paused, completed, inactive, cancelled
message_status: pending, sent, delivered, read, failed, scheduled, sending
message_type: text, button, list, media, quiz_intro, quiz_question, ...
saga_status: STARTED, STEP_1_PATIENT_CREATED, ..., COMPLETED, FAILED
alert_severity: low, medium, high, critical
user_role: doctor, admin
```

## 🔐 Security & Compliance Features

### LGPD Compliance (Migrations 020, 024)
- **CPF Encryption:** AES-256-GCM encryption for CPF data
- **Searchable Hash:** SHA-256 hash enables queries without decryption
- **Plaintext Removal:** Original CPF column permanently deleted (Migration 024)
- **Encryption Key:** Stored securely in environment variable `ENCRYPTION_KEY`

### Security Features
- **Audit Logging:** All data changes tracked in `audit_logs`
- **Admin 2FA:** Two-factor authentication for admin users
- **Session Management:** Secure session handling with IP whitelisting
- **Soft Deletes:** Data recovery possible via `deleted_at` timestamps
- **RBAC Permissions:** Granular user permissions via `users.permissions` (Migration 023)

### Performance Optimizations (Migration 022)
- **Cursor Pagination:** 8 composite indexes for efficient deep pagination
- **Query Speed:** 99% improvement (450ms → 5ms for deep pagination)
- **Affected Tables:** Messages, patients, quiz responses, audit logs, alerts

## 📋 Recent Migrations

| # | Migration | Description |
|---|-----------|-------------|
| 027 | consolidate_duplicates | Documenta migrations duplicadas (005/013, 014/022) |
| 028 | encrypt_email_phone | Adiciona criptografia LGPD para email e telefone |
| 029 | (próxima) | Planejada conforme necessidade |

## 📈 Current Data Statistics

> *As of 2025-11-25*

| Table | Row Count |
|-------|-----------|
| `patients` | 1 |
| `users` | 2 |
| `messages` | 1 |
| `audit_logs` | 111 |

## 📞 Support

For database issues, refer to the [Guides](./guides/) or check the [History](./history/) for context on past changes.

---

*Documentation auto-generated from live database schema.*
