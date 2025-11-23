# Database Documentation

Welcome to the Hormonia Backend database documentation.

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

- **Type:** PostgreSQL 14+
- **ORM:** SQLAlchemy 2.0+
- **Migration Tool:** Alembic
- **Total Tables:** ~50
- **Key Features:**
    - JSONB storage for flexible metadata
    - Soft deletes (`deleted_at`)
    - Audit logging (HIPAA compliant)
    - Partitioned archive tables

## 📞 Support

For database issues, refer to the [Guides](./guides/) or check the [History](./history/) for context on past changes.