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
| **Migration Tool** | Alembic (22 migrations) |
| **Total Tables** | 55 |
| **Total Columns** | 797 |
| **Total Indexes** | 325 |
| **Foreign Keys** | 57 |
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
| **Medical** | 3 | Reports, appointments, alerts |
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

## 🔐 Security Features

- **CPF Encryption:** Patient CPF numbers are encrypted at rest (LGPD)
- **Audit Logging:** All data changes tracked in `audit_logs`
- **Admin 2FA:** Two-factor authentication for admin users
- **Session Management:** Secure session handling with IP whitelisting
- **Soft Deletes:** Data recovery possible via `deleted_at` timestamps

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
