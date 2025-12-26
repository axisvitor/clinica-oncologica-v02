# Database Documentation

Welcome to the Hormonia Backend database documentation hub.

> **Current State (22/12/2025):**
> - **Total Tables:** 77
> - **Total Indexes:** 479+
> - **Migration Head:** `034_add_performance_indexes`
> - **Recent Fixes:** Pool config, N+1 queries, unbounded queries, FlowState enum consolidation
> - **Environment:** Production (AWS RDS sa-east-1)

## 📚 Core Documentation

The database documentation has been consolidated into 5 core guides:

1.  **[Schema & Models](01_SCHEMA_MODELS.md)**
    *   Table definitions, ORM mappings, Relationship diagrams.
    *   *Reference for:* Developers writing queries, designing features.

2.  **[Architecture & Patterns](02_ARCHITECTURE.md)**
    *   Connection pooling, Repository pattern, Service layer guidelines.
    *   *Reference for:* Architects, Backend Engineers.

3.  **[Security & Compliance](03_SECURITY_COMPLIANCE.md)**
    *   LGPD/HIPAA implementation, Encryption, RLS, Audit Logging.
    *   *Reference for:* Security Officers, Compliance audits.

4.  **[Performance & Optimization](04_PERFORMANCE.md)**
    *   Indexing strategy, Bottleneck analysis, Tuning guides.
    *   *Reference for:* DBAs, Performance tuning.

5.  **[Operations & Migrations](05_OPERATIONS.md)**
    *   Migration runbooks, Backup/Restore scripts, Maintenance.
    *   *Reference for:* DevOps, SREs.

## 🛠️ Quick Links

-   **Schema Diagram:** `reference/schema_diagram.mmd` (Visual ERD)
-   **Full Schema JSON:** `reference/complete_schema.json` (Machine readable)
-   **Migration Script:** `backend-hormonia/alembic`

## 🚀 Quick Commands

```bash
# Check Migration Status
cd backend-hormonia
alembic current

# Run Migrations
alembic upgrade head

# Generate Backup (Production)
python scripts/backup_production_database.py
```