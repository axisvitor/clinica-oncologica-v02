# 2. Database Architecture & Patterns

> **Scope:** Connection pooling, Repository pattern, Service layer usage, and Query patterns.
> **Source:** Consolidated from `connection_analysis.md`, `repository_analysis.md`, `SERVICE_LAYER_AUDIT_REPORT.md`.

---

## 1. Connection Management

**Infrastructure:** PostgreSQL on AWS RDS (sa-east-1).
**Driver:** `psycopg` (Async SQLAlchemy 2.0).

### Pooling Strategy
We use a **Dual-Engine Architecture** to handle Row-Level Security (RLS) and System tasks separately.

1.  **Service Role Engine:**
    -   **Usage:** Background tasks, Migrations, System ops.
    -   **Pool:** ~30 connections/worker.
    -   **Privilege:** Bypasses RLS policies.
    -   **Recycle:** 3600s.

2.  **RLS Context Engine:**
    -   **Usage:** User-facing API requests.
    -   **Pool:** ~15 connections/worker.
    -   **Security:** Injects JWT claims into `current_setting`.
    -   **Recycle:** 1800s (Matches typical token lifecycles).

**Environment Scaling:**
-   **Prod:** 10 pool + 10 overflow per worker (Strict limits for RDS t3.micro).
-   **Dev:** 20 pool + 30 overflow (Generous for local dev).

---

## 2. Repository Layer

**Status:** ✅ Excellent (9.2/10 Health Score).
**Pattern:** Generic BaseRepository + Specialized Domain Repositories.

### Key Features
-   **Generic CRUD:** `BaseRepository[Model]` handles standard ops.
-   **Eager Loading:** Enabled by default on retrieval methods (`joinedload`, `selectinload`) to prevent N+1 queries.
-   **Soft Delete:** Built-in filtering for `deleted_at IS NULL`.
-   **Cursor Pagination:** Optimized `list_v2` methods using composite indexes.
-   **Caching:** Redis caching decorator `@cached_query` for expensive reads (Quizzes, Reports).

### Flow & Template Patterns
- **Single Active Version Policy:** O `FlowTemplateVersionRepository` garante que, ao ativar uma nova versão de template, todas as versões anteriores do mesmo `flow_kind_id` sejam automaticamente desativadas.
- **Flexible Step Normalization:** O `EnhancedTemplateLoader` e os repositórios suportam a entrada de `steps` tanto como lista (padrão do Frontend Designer) quanto como dicionário indexado (padrão de armazenamento otimizado no RDS), realizando a conversão automática.
- **DB-Only Mode:** O sistema de templates opera em modo puramente orientado ao banco de dados, ignorando arquivos de configuração locais (YAML) para garantir que a interface de Admin seja a única fonte de verdade.

### Repository Catalog
-   `PatientRepository`: Cursor pagination, complex filtering.
-   `MessageRepository`: DB-level aggregation for stats, integrity checks.
-   `QuizRepository`: Cached sessions and templates.
-   `AppointmentRepository`: Conflict detection logic.

### Known Anti-Patterns (To Fix)
-   ⚠️ `TemplateRepository.list_active()` is unbounded (no limit).
-   ⚠️ Some complex filter logic in `PatientRepository` is duplicated.

---

## 3. Service Layer Analysis

**Status:** ⚠️ Good (B+), but with mixed access patterns.

### Patterns
-   **Repository Usage:** 80% of services use Repositories properly.
-   **Direct DB Access:** 20% of services (Legacy/Analytics) use raw `db.query`.

### Critical Findings
1.  **PatientCreationService:** ✅ Excellent race condition handling with flush/commit.
2.  **AuditService:** ✅ Tamper-proof chain implementation.
3.  **EnhancedAnalyticsService:** ⚠️ High coupling, direct complex joins. Should move to Read Replicas or Materialized Views.
4.  **Transaction Boundaries:** ⚠️ Some services have multiple commits per operation (Non-atomic). Need refactoring to Transaction Decorators.

---

## 4. Query Patterns

### Optimized Patterns ✅
-   **Aggregation:** Using `func.count` and `group_by` in DB instead of Python.
-   **Keyset Pagination:** `WHERE (created_at, id) < (cursor_time, cursor_id)` (O(1)).
-   **Bulk Updates:** `db.query(Model).filter(...).update(...)` for batch ops.

### Performance Risks ⚠️
-   **N+1 Risks:** Identified in `template_versions` (fixed in recent patch) and some conversation lists.
-   **Unbounded IN clauses:** Generally avoided, but needs monitoring in Analytics.

---

## 5. Recommendations

1.  **Refactor Transactions:** Implement `@transactional` decorator to ensure atomicity in Service layer.
2.  **Migrate Analytics:** Move `EnhancedAnalyticsService` raw queries to a specialized Analytics Repository or Views.
3.  **Enforce Repositories:** Disallow `db.query` in Service layer via linting rules.
