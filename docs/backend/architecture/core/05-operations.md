# 5. Operations & Migrations

> **Scope:** Migration strategy, Backup/Restore procedures, Maintenance.
> **Source:** Consolidated from `guides/*`, `MIGRATION_ANALYSIS_REPORT.md`, `history/**`.

---

## 1. Migration Strategy

We use **Alembic** for schema migrations.

### Principles
1.  **Zero-Downtime:** Use `CONCURRENTLY` for index creation. Use "Expand-Contract" for column changes.
2.  **Idempotent:** Scripts should be safe to re-run.
3.  **Reversible:** Always implement `downgrade()`.
4.  **Review:** Migrations must be reviewed for locking behavior (e.g., adding NOT NULL to huge table).

### Recent Migration History (Highlights)
- `034`: Performance indexes with CONCURRENTLY support (patients, quiz_sessions, messages, appointments).
- `033`: Firebase user_sync_log schema fix (new columns: user_id, operation, sync_direction, changes, success).
- `ac193e8656c1`: Create Sessions Table.
- `032`: Account Security Columns.
- `031`: Performance Indexing (Total 479 indices).
- `028/030`: Full LGPD Data Encryption.
- `025`: Patient Idempotency.
- `022`: Cursor pagination indexes.

> **Note:** Migrations 033-034 use `CREATE INDEX CONCURRENTLY IF NOT EXISTS` for non-blocking index creation on production.

### Execution Guide
```bash
# Check current status
alembic current

# Create new revision
alembic revision -m "description"

# Apply pending
alembic upgrade head

# Rollback last
alembic downgrade -1
```

---

## 2. Backup & Restore

### Strategy
-   **Frequency:** Daily automated backups (Snapshot + WAL).
-   **Retention:** 7 days daily, 4 weeks weekly, 12 months monthly.
-   **Storage:** AWS S3 (Encrypted).

### Backup Tool (`scripts/backup_production_database.py`)
Custom script that:
1.  Dumps Schema + Data.
2.  **Redacts Sensitive Data** (Passwords, Keys) automatically.
3.  Captures `alembic_version` (Critical).
4.  Generates SHA256 checksum for integrity.

### Restore Procedure
1.  **Stop Application** to prevent writes.
2.  **Run Restore Script:**
    ```bash
    python scripts/restore_database_backup.py --backup backups/backup.json
    ```
    *Note: Script asks for explicit confirmation.*
3.  **Verify:** Check row counts and alembic version.

---

## 3. Maintenance Procedures

### Routine Tasks
1.  **Vacuuming:** Autovacuum is enabled on RDS. Manual `VACUUM ANALYZE` recommended after massive data deletions (e.g., archiving audit logs).
2.  **Key Rotation:** Run rotation script annually or after security incident.
3.  **Index Cleanup:** Remove unused indexes identified by performance analysis.

### Emergency Response
-   **Migration Lock:** If a migration hangs, check `pg_stat_activity` for locks. Kill blocking PID if safe.
-   **Connection Exhaustion:** Temporary fix -> Increase `DATABASE_POOL_MAX_OVERFLOW`. Long term -> Fix connection leaks / Add Read Replicas.

---

## 4. Environment Setup

### Variables (.env)
```bash
# Connection
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db

# Pool Configuration (environment-aware defaults in database_config.py)
# Only override if necessary:
# DATABASE_POOL_SIZE=10        # Default: 10 (dev), 10 (prod)
# DATABASE_POOL_MAX_OVERFLOW=15     # Default: 15 (dev), 10 (prod)
# WEB_CONCURRENCY=1      # Default: 1 (dev), 4 (prod) - workers

# Security
SECURITY_SECRET_KEY=...
SECURITY_CSRF_SECRET_KEY=...
PHI_ENCRYPTION_KEY=...
ENCRYPTION_KEY_CURRENT=...
HASH_SALT=...
```

> **Warning:** Do NOT set high pool values in development. The system automatically adjusts based on environment detection. Default dev config (1 worker × 25 connections = 25) is safe for RDS t3.micro (~80 max connections).

### Local Development
-   Use `docker-compose up db` for local PostgreSQL.
-   Run `alembic upgrade head` to sync schema.
-   Run `python scripts/seed_db.py` (if available) for test data.
