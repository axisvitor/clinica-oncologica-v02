# Comprehensive Database Analysis Compendium

**Date:** December 2025
**Scope:** Backend Hormonia Database (Models, Schema, Messaging, Performance)
**Status:** Consolidated & Verified

## 1. Executive Summary

The Hormonia Backend database architecture demonstrates **strong foundational design**, particularly in LGPD compliance, indexing strategies, and relationship management. The system scores an estimated **7.5/10** in overall quality.

**Key Strengths:**
*   **Privacy First:** Robust AES-256 encryption for PII (CPF, email, phone) with hash-based lookups.
*   **Performance:** Extensive use of composite and partial indexes (479+ indexes).
*   **Auditability:** Comprehensive audit trails via `audit_logs` and `message_status_events`.
*   **Resilience:** Advanced messaging patterns including Idempotency keys and Dead Letter Queues (DLQ).

**Primary Risks:**
*   **Inconsistency:** Duplicate Enum definitions (e.g., `FlowState`) and inconsistent Base Class usage (`WebhookEndpoint` vs `BaseModel`).
*   **Gap Analysis:** Missing bidirectional relationships in analytics models and orphan columns.
*   **Technical Debt:** Approximately ~40 hours of estimated refactoring work on standardization.

---

## 2. Critical Findings & Issues

### 2.1 Critical Structural Issues (P0)
1.  **Duplicate Enum Definitions:** `FlowState` is defined independently in both `patient.py` and `flow.py`. Risk of divergence.
2.  **Inconsistent Inheritance:** `WebhookEndpoint`, `WebhookDelivery`, and `WebhookLog` inherit from `Base` instead of `BaseModel`, missing standard fields (`id`, `created_at`, `updated_at`).
3.  **Missing Constraints:** `WebhookEvent` table uses `related_message_id` (UUID) without a formal Foreign Key constraint.

### 2.2 Relationship Gaps
*   **FlowAnalytics ↔ FlowTemplateVersion:** Missing `back_populates` implementation prevents bidirectional navigation.
*   **Doctor vs Physician:** Confusing overlap between Pydantic-only `Doctor`/`Physician` models and the actual SQLAlchemy `User` model (role='doctor').

### 2.3 Naming Conflicts
*   **Metadata Column:** Multiple models use `metadata` (JSONB), but some deviate (`patient_data`, `interaction_patterns`).
    *   *Recommendation:* Standardize on `*_metadata` or `metadata` across all tables.
*   **Timestamp Duplication:** `Alert` model redefines `created_at`/`updated_at` despite inheriting them from `BaseModel`.

---

## 3. Deep Dive: Messaging & Notification Architecture

The messaging system is the core of the patient engagement platform, handling WhatsApp integration via the Evolution API.

### 3.1 Core Components
| Component | Table | Purpose |
| :--- | :--- | :--- |
| **Message Store** | `messages` | Primary storage for inbound/outbound messages. Tracks lifecycle (sent/delivered/read). |
| **Audit Trail** | `message_status_events` | Immutable log of status transitions. Maps Evolution API webhooks to internal states. |
| **Event DLQ** | `webhook_events` | Dead Letter Queue for raw webhooks. Supports event replay and deduplication. |
| **Failure DLQ** | `whatsapp_delivery_failures` | Permanent store for messages that exceeded max retries. Supports manual review. |
| **Templates** | `message_templates` | Reusable content with variable substitution (`{patient_name}`). |

### 3.2 Resilience Patterns
*   **Idempotency:** `messages.idempotency_key` and `webhook_events.event_hash` prevent duplicate processing.
*   **Retry Logic:** Exponential backoff strategy tracked via `retry_count` and `next_retry_at`.
*   **Loose Coupling:** Webhook events use nullable UUIDs to decouple ingestion from processing.

---

## 4. Privacy & LGPD Compliance

The schema implements a strict **Encryption-at-Rest** strategy for sensitive data.

### 4.1 Encryption Design
*   **Fields:** `cpf`, `email`, `phone_number`.
*   **Storage:**
    *   `*_encrypted`: AES-256 encrypted value (for retrieval).
    *   `*_hash`: SHA-256 hash (for exact-match searching).
*   **Validation:** Validation hooks ensure no plaintext PII leakage in the `patient_data` JSONB column.

### 4.2 Audit & Logs
*   **AuditLog:** Tracks all mutations to sensitive tables.
*   **Retention:** Policies needed for table partitioning of audit logs (Long-term Action).

---

## 5. Performance & Optimization

### 5.1 Indexing Strategy
The database is heavily indexed for read performance:
*   **Composite Indexes:** For common filtering patterns (e.g., `(user_id, is_active)`).
*   **Partial Indexes:** For high-selectivity queries (e.g., `WHERE error_code IS NOT NULL`).

### 5.2 Areas for Improvement
*   **JSONB Queries:** Large JSON blobs (`ABExperiment.detailed_results`) may impact fetch performance. Recommend pagination or JSON attributes projection.
*   **N+1 Risks:** `Patient -> Messages` relationship defaults to lazy loading. Should use `selectinload` for bulk fetching.

---

## 6. Action Plan & Recommendations

### Immediate (P0 - Critical)
- [ ] **Fix duplicate Enums:** Move `FlowState` to `app/models/enums.py`.
- [ ] **Standardize Webhooks:** Refactor `Webhook*` models to inherit `BaseModel`.
- [ ] **Fix Relationships:** Add missing `back_populates` to analytics and report models.

### Short-term (P1 - High)
- [ ] **Metadata Naming:** Rename inconsistent JSONB columns to `metadata` or `*_metadata`.
- [ ] **FK Constraints:** Add formal Foreign Keys to `WebhookEvent` table.
- [ ] **Documentation:** Add docstrings to `FlowTemplateVersion` and `FlowAnalytics`.

### Medium-term (P2)
- [ ] **Doctor Model Cleanup:** Clearly distinguish or merge `Doctor` Pydantic models with `User` entity.
- [ ] **JSON Schema:** Implement validation for complex JSONB columns.

---
*This document consolidates findings from Code Quality Analysis (Dec 22) and Messaging Tables Analysis.*
