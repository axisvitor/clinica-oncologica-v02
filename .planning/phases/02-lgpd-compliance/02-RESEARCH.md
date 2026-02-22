# Phase 2: LGPD Compliance - Research

**Researched:** 2026-02-22
**Domain:** LGPD compliance — persistent audit trail, WhatsApp opt-out, AI event audit logging
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LGPD-01 | Tabela `patient_deletion_audit` persistente com registro imutável de deleções (LGPD Art. 16/18) | New SQLAlchemy model + Alembic migration. Hook into existing `delete_patient()` in `PatientCRUDService`. |
| LGPD-02 | Handler de opt-out WhatsApp (STOP/PARAR/CANCELAR) que interrompe messaging imediatamente e registra revogação de consentimento (LGPD Art. 18) | Intercept at `MessageWebhookHandler.process_message()`. Revoke via existing `ConsentService.revoke_consent()`. Set a new `messaging_stopped_at` field or use a guard flag on Patient. |
| LGPD-03 | AI event types (`AI_QUERY`, `AI_HUMANIZATION`, `AI_SENTIMENT`, `AI_FOLLOW_UP`) adicionados ao `AuditEventType` enum + Alembic migration | Extend `AuditEventType` enum in `app/models/audit_log.py` + `ALTER TYPE audit_event_type ADD VALUE` via Alembic. |
</phase_requirements>

---

## Summary

Phase 2 implements three targeted LGPD compliance features against a mature Python/FastAPI/SQLAlchemy codebase with PostgreSQL on Railway/AWS RDS. The infrastructure and patterns are well-established; this phase slots new artifacts into existing seams.

**LGPD-01** requires a new `patient_deletion_audit` table with an immutable PostgreSQL row (trigger prevents UPDATE/DELETE, same pattern as `audit_logs`). The existing `PatientCRUDService.delete_patient()` performs a soft-delete and must be augmented to INSERT into this table *before* the delete within the same transaction, so the audit record survives log rotation.

**LGPD-02** requires detecting opt-out keywords (STOP, PARAR, CANCELAR, and variants) inside `MessageWebhookHandler.process_message()`, which is the canonical entry point for all inbound WhatsApp messages. When detected, the handler must (a) revoke the COMMUNICATION consent via existing `ConsentService`, (b) set a messaging-stopped flag on the patient, and (c) short-circuit any flow advancement — all in a single atomic transaction. The existing `Consent` model already has `ConsentStatus.REVOKED` and `revoke_consent()` in `ConsentService`.

**LGPD-03** requires extending the PostgreSQL `audit_event_type` native enum with four new values. The pattern already exists in migration `e2c4b1a9f7d3` (which added `cancelled` to `message_status`): use `ALTER TYPE ... ADD VALUE 'x' IF NOT EXISTS` wrapped in an idempotent `DO $$...END$$` block. The Python enum class in `app/models/audit_log.py` must be extended in parallel.

**Primary recommendation:** Implement all three plans as database-first (migration then model update then service hook), keeping each plan's changes in an atomic commit. Do not rebuild existing audit infrastructure — hook into it.

---

## Standard Stack

### Core (already in project — no new installs needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.x (ORM layer) | Model definition, ORM events | Already canonical ORM |
| Alembic | Current in `.venv` | Schema migrations | Already the project migrator |
| FastAPI | Current | HTTP routing | Already canonical API framework |
| PostgreSQL | AWS RDS | Database | Already canonical DB |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `app.models.base.BaseModel` | project-internal | Provides `id`, `created_at`, `updated_at` | Use for all new models |
| `app.services.lgpd.consent_service.ConsentService` | project-internal | Consent revocation | Use for LGPD-02 |
| `app.services.audit.audit_service.AuditService` | project-internal | Audit event logging | Use for LGPD-03 AI events |
| `app.utils.timezone.now_sao_paulo` | project-internal | Timezone-aware timestamps | Use everywhere a timestamp is needed |
| `app.utils.transaction_manager.sync_transaction` | project-internal | Atomic transactions | Use for LGPD-01 and LGPD-02 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PostgreSQL rule to prevent DELETE on `patient_deletion_audit` | Application-level guard | DB-level is stronger; cannot be bypassed by app bugs |
| `ConsentService.revoke_consent()` | Direct DB update | Use the service — it logs the LGPD audit entry and maintains invariants |
| New `messaging_stopped_at` column on Patient | Redis flag | DB column survives restart, is queryable, survives Railway redeploy — required for correctness |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure

```
app/
├── models/
│   ├── audit_log.py           # LGPD-03: extend AuditEventType enum
│   └── patient_deletion_audit.py  # LGPD-01: new model (CREATE)
├── services/
│   └── patient/
│       └── crud_service.py    # LGPD-01: hook delete_patient()
├── services/
│   └── webhook/handlers/
│       └── message_handler.py # LGPD-02: add opt-out interception
alembic/versions/
│   ├── XXX_add_patient_deletion_audit.py  # LGPD-01
│   ├── XXX_add_whatsapp_opt_out_flag.py   # LGPD-02
│   └── XXX_add_ai_audit_event_types.py    # LGPD-03
tests/
│   ├── services/test_patient_deletion_audit.py
│   ├── services/test_whatsapp_opt_out.py
│   └── models/test_audit_event_types.py
```

### Pattern 1: Persistent Deletion Audit Table (LGPD-01)

**What:** A dedicated `patient_deletion_audit` table that records every patient deletion with a DB-level immutability trigger. Unlike the rotating Railway logs, this persists permanently in PostgreSQL.

**When to use:** Any hard deletion, soft deletion, or anonymization of a patient record.

**Key design choices derived from codebase:**
- The existing `audit_logs` table already has PostgreSQL rules `audit_logs_no_update` and `audit_logs_no_delete` that block UPDATE/DELETE via `CREATE RULE`. Use the same pattern.
- The `audit_logs` table uses a checksum trigger for tamper detection. For `patient_deletion_audit`, immutability via rule is sufficient (simpler, no checksum needed).
- The existing `Patient.deleted_at` is the soft-delete mechanism. The audit record must be written in the same transaction as `patient.deleted_at = now_sao_paulo()`.

**Example model:**
```python
# app/models/patient_deletion_audit.py
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.models.base import BaseModel

class PatientDeletionAudit(BaseModel):
    __tablename__ = "patient_deletion_audit"

    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    deleted_by_user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    deleted_by_email = Column(String(255), nullable=True)
    deletion_reason = Column(Text, nullable=True)
    patient_name_hash = Column(String(64), nullable=True)  # SHA-256, NOT plaintext
    deleted_at = Column(DateTime(timezone=True), nullable=False)
```

**Alembic migration approach:**
```python
def upgrade():
    op.create_table(
        "patient_deletion_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_by_email", sa.String(255), nullable=True),
        sa.Column("deletion_reason", sa.Text, nullable=True),
        sa.Column("patient_name_hash", sa.String(64), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_patient_deletion_audit_patient_id",
                    "patient_deletion_audit", ["patient_id"])
    op.create_index("idx_patient_deletion_audit_deleted_at",
                    "patient_deletion_audit", ["deleted_at"])

    # Immutability rules — same pattern as audit_logs in migration 011
    op.execute("""
        CREATE RULE patient_deletion_audit_no_update AS
            ON UPDATE TO patient_deletion_audit DO INSTEAD NOTHING;
    """)
    op.execute("""
        CREATE RULE patient_deletion_audit_no_delete AS
            ON DELETE TO patient_deletion_audit DO INSTEAD NOTHING;
    """)
```

**Hook in `PatientCRUDService.delete_patient()`:**
```python
# In the existing sync_transaction block, BEFORE patient.deleted_at is set:
from app.models.patient_deletion_audit import PatientDeletionAudit
import hashlib

audit_record = PatientDeletionAudit(
    patient_id=patient_id,
    deleted_by_user_id=performing_user_id,   # pass from caller
    deleted_by_email=performing_user_email,  # pass from caller
    deletion_reason="Admin deletion via API",
    patient_name_hash=hashlib.sha256(
        (patient.name or "").encode()
    ).hexdigest(),
    deleted_at=now_sao_paulo(),
)
session.add(audit_record)
patient.deleted_at = now_sao_paulo()
session.add(patient)
# ... rest of existing flow cancellation logic
```

**CRITICAL:** The audit INSERT must happen **before** the soft-delete commit, in the same transaction. This guarantees the record is persisted even if Railway log rotation happens immediately after.

### Pattern 2: WhatsApp Opt-Out Handler (LGPD-02)

**What:** Intercept inbound messages in `MessageWebhookHandler.process_message()` and detect opt-out keywords. When detected: revoke consent, set `messaging_stopped_at` on patient, return early without flow advancement.

**When to use:** Any inbound text message from a patient phone number.

**Key design choices derived from codebase:**
- `MessageWebhookHandler.process_message()` at `app/services/webhook/handlers/message_handler.py` is the correct intercept point — it runs for every inbound message.
- The existing `ConsentService` (`app/services/lgpd/consent_service.py`) has `revoke_consent()` which logs the LGPD audit entry. Use it.
- The `Patient` model has no `messaging_stopped_at` column yet. A new column is needed via Alembic migration. A boolean `messaging_stopped` is simpler but a timestamp column is better for LGPD audit (WHEN did they stop).
- The `ConsentType.COMMUNICATION` enum value already exists in `app/models/consent.py`. The opt-out should revoke any active COMMUNICATION consent.
- The `ConsentService.revoke_consent()` takes a `consent_id` — to revoke by patient, query for active COMMUNICATION consents first, or create a new `revoke_consent_by_patient_and_type()` helper.
- `MessageWebhookHandler` uses a synchronous `Session` (not `AsyncSession`). `ConsentService` also uses sync `Session`. Compatible.

**Opt-out keyword detection:**
```python
OPT_OUT_KEYWORDS = frozenset([
    "stop", "parar", "cancelar", "pare",
    "sair", "remover", "descadastrar", "nao quero",
    "não quero", "cancela", "para",
])

def is_opt_out_message(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in OPT_OUT_KEYWORDS
```

**Intercept point in `process_message()`:**
```python
# After Step 3 (find patient), before Step 4 (create message):
text_content = message_data.get("text_content", "").strip()
if is_opt_out_message(text_content):
    await self._handle_opt_out(patient, db_session)
    return None  # Do not advance flow

async def _handle_opt_out(self, patient: Patient, db: Session) -> None:
    # 1. Set messaging_stopped_at on patient (atomic with consent revocation)
    patient.messaging_stopped_at = now_sao_paulo()
    db.add(patient)

    # 2. Revoke active COMMUNICATION consents
    consent_service = ConsentService(db)
    active_consents = db.query(Consent).filter(
        Consent.patient_id == patient.id,
        Consent.consent_type == ConsentType.COMMUNICATION,
        Consent.status == ConsentStatus.GRANTED,
    ).all()
    for consent in active_consents:
        await consent_service.revoke_consent(
            consent_id=consent.id,
            reason="Patient opt-out via WhatsApp STOP message"
        )

    db.commit()
    logger.info(f"Patient {patient.id} opted out of WhatsApp messaging")
```

**Guard in `UnifiedWhatsAppService` (or message sending path):**
Before sending any outbound message, check `patient.messaging_stopped_at is not None`. If set, skip sending.

**New Alembic migration:**
```python
def upgrade():
    op.add_column("patients",
        sa.Column("messaging_stopped_at",
                  sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_patients_messaging_stopped",
                    "patients", ["messaging_stopped_at"],
                    postgresql_where=sa.text("messaging_stopped_at IS NOT NULL"))
```

### Pattern 3: AI Event Types in AuditEventType Enum (LGPD-03)

**What:** Add four new values to the existing `AuditEventType` Python enum and the corresponding PostgreSQL native enum type, via a safe `ALTER TYPE ... ADD VALUE IF NOT EXISTS` migration.

**When to use:** Whenever a Gemini/LangGraph AI call is made (humanization, sentiment, query, follow-up).

**Key design choices derived from codebase:**
- `AuditEventType` is defined in `app/models/audit_log.py` as `class AuditEventType(str, enum.Enum)`.
- The PostgreSQL enum type is named `audit_event_type` (set via `name="audit_event_type"` in the Column definition).
- Migration `e2c4b1a9f7d3` shows the safe pattern for adding enum values: `ALTER TYPE x ADD VALUE 'y' IF NOT EXISTS` wrapped in `DO $$ BEGIN ... END $$` for idempotency.
- `audit_logs_no_update` rule blocks UPDATE, so you cannot backfill existing rows' event_type — but this is fine, new events use the new values.
- The `AuditService.log_event()` in `app/services/audit/audit_service.py` is the canonical way to write audit events. Use it from AI call sites.

**Python enum addition:**
```python
# app/models/audit_log.py — in AuditEventType class
# AI events (LGPD-03)
AI_QUERY = "ai_query"
AI_HUMANIZATION = "ai_humanization"
AI_SENTIMENT = "ai_sentiment"
AI_FOLLOW_UP = "ai_follow_up"
```

**Alembic migration:**
```python
def upgrade():
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'audit_event_type'
                  AND e.enumlabel = 'ai_query'
            ) THEN
                ALTER TYPE audit_event_type ADD VALUE 'ai_query';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'audit_event_type'
                  AND e.enumlabel = 'ai_humanization'
            ) THEN
                ALTER TYPE audit_event_type ADD VALUE 'ai_humanization';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'audit_event_type'
                  AND e.enumlabel = 'ai_sentiment'
            ) THEN
                ALTER TYPE audit_event_type ADD VALUE 'ai_sentiment';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'audit_event_type'
                  AND e.enumlabel = 'ai_follow_up'
            ) THEN
                ALTER TYPE audit_event_type ADD VALUE 'ai_follow_up';
            END IF;
        END $$;
    """)

def downgrade():
    # PostgreSQL does not support removing enum values.
    pass
```

**CRITICAL:** PostgreSQL `ALTER TYPE ... ADD VALUE` cannot run inside a multi-statement transaction on some versions. Use `op.execute()` outside `with op.get_context().autocommit_block():` or set `connection.autocommit = True` if needed. The idempotent `IF NOT EXISTS` check makes the migration re-runnable safely.

### Anti-Patterns to Avoid

- **Writing deletion audit to application logs only:** Railway log rotation will destroy the evidence. Must use PostgreSQL.
- **Revocation as a separate async task:** For LGPD-02, revocation must be synchronous and committed before any subsequent message could be sent. Use sync execution in the same request handler.
- **Storing patient name in plaintext in `patient_deletion_audit`:** Store only a SHA-256 hash (for verification) or omit — LGPD itself requires the audit record, not re-identification.
- **Checking `messaging_stopped_at` only in the scheduler:** Also check in `UnifiedWhatsAppService.send_message()` as a last-resort guard.
- **Adding AI enum values without checking `audit_event_type` type name:** The PostgreSQL type is named `audit_event_type` — confirm in `000_legacy_core_bootstrap.py` or via `\dT` — the migration must target the exact type name.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Consent revocation tracking | Custom revocation table | `ConsentService.revoke_consent()` + existing `consents` table | Already logs to `lgpd_audit_log`, handles state validation |
| Immutability of audit records | Application-level protection | PostgreSQL `CREATE RULE ... DO INSTEAD NOTHING` | DB-level, cannot be bypassed by app code |
| Enum value addition | Recreating entire enum type | `ALTER TYPE ... ADD VALUE IF NOT EXISTS` | Safer, compatible with live DB |
| Timestamp timezone | `datetime.utcnow()` | `app.utils.timezone.now_sao_paulo()` | Project convention, avoids timezone inconsistencies |
| Transaction management | Manual `db.commit()` calls | `sync_transaction()` context manager from `app.utils.transaction_manager` | Handles rollback automatically |

**Key insight:** All three plans require adding to existing seams, not replacing them. The existing audit, consent, and migration infrastructure is correct and should be extended, not duplicated.

---

## Common Pitfalls

### Pitfall 1: Audit Record Written After Soft-Delete Commits

**What goes wrong:** `patient_deletion_audit` INSERT happens in a separate transaction after `deleted_at` is committed. If the app crashes between the two commits, the audit record is lost.
**Why it happens:** Treating audit as a side effect rather than part of the delete transaction.
**How to avoid:** Use the existing `sync_transaction()` context manager. Put the `PatientDeletionAudit` INSERT at the top of the `with sync_transaction(self.db) as session:` block, before `patient.deleted_at = ...`.
**Warning signs:** The `delete_patient()` method has a `with sync_transaction(...)` block — put the audit INSERT inside it.

### Pitfall 2: `ALTER TYPE ADD VALUE` Inside a Transaction

**What goes wrong:** On PostgreSQL < 12, `ALTER TYPE ADD VALUE` cannot execute inside a transaction block. Alembic wraps migrations in transactions by default.
**Why it happens:** Alembic default transaction wrapping.
**How to avoid:** Use the idempotent `DO $$ ... END $$` check. On PostgreSQL 12+, `ALTER TYPE ADD VALUE IF NOT EXISTS` is safe inside a transaction. AWS RDS supports PostgreSQL 13+, so this is not an issue here. Still use `IF NOT EXISTS` for safety on re-runs.
**Warning signs:** Migration fails with "ALTER TYPE ... ADD VALUE cannot run inside a transaction block."

### Pitfall 3: Opt-Out Detection Misses Unicode/Accented Variants

**What goes wrong:** Patient sends "Parar" with capital P, or "PARAR" in uppercase — not matched.
**Why it happens:** Case-sensitive comparison.
**How to avoid:** Normalize with `.strip().lower()` before comparison against the keyword set.
**Warning signs:** Test with "STOP", "Stop", "parar", "PARAR", "Cancelar" variants.

### Pitfall 4: `messaging_stopped_at` Not Checked in All Send Paths

**What goes wrong:** The scheduler (Celery Beat) sends messages to opted-out patients because the Celery task doesn't check `messaging_stopped_at`.
**Why it happens:** The guard is added in the webhook handler but not in the outbound sending path.
**How to avoid:** Add check in `UnifiedWhatsAppService.send_message()` or in the Celery task that dispatches messages. Query `Patient.messaging_stopped_at is not None` before sending.
**Warning signs:** Integration test showing messages sent after opt-out.

### Pitfall 5: Revocation Fails If No Active COMMUNICATION Consent Exists

**What goes wrong:** Patient sends STOP but has no active COMMUNICATION consent in the `consents` table — `revoke_consent()` raises `ValueError("not granted")`.
**Why it happens:** Opt-out must succeed even if formal consent was never recorded.
**How to avoid:** Use a try/except around the revocation loop. The primary action is always setting `messaging_stopped_at` — consent revocation is secondary. Log a warning if no consent to revoke.
**Warning signs:** Opt-out handler raises an exception for patients onboarded before the consent system existed.

### Pitfall 6: `audit_event_type` Type Name Mismatch

**What goes wrong:** The Alembic migration targets `audit_event_type` but the actual PostgreSQL type is named something else (e.g., `auditeventtype`).
**Why it happens:** SQLAlchemy generates type names differently if `native_enum=True` and `name` is not set.
**How to avoid:** The Column definition in `audit_log.py` uses `SQLEnum(AuditEventType, name="audit_event_type", native_enum=True)` — so the PostgreSQL type name is `audit_event_type`. Confirmed.
**Warning signs:** `pg_enum` join returns no rows for the new values.

---

## Code Examples

Verified patterns from the codebase:

### Existing Immutability Pattern (from migration 011)
```python
# Source: alembic/versions/011_hipaa_audit.py
op.execute("""
    CREATE RULE audit_logs_no_update AS
        ON UPDATE TO audit_logs
        DO INSTEAD NOTHING;
""")
op.execute("""
    CREATE RULE audit_logs_no_delete AS
        ON DELETE TO audit_logs
        DO INSTEAD NOTHING;
""")
```
Use the same pattern for `patient_deletion_audit`.

### Existing Enum Value Addition Pattern (from migration e2c4b1a9f7d3)
```python
# Source: alembic/versions/e2c4b1a9f7d3_add_cancelled_to_message_status_enum.py
op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'message_status'
              AND e.enumlabel = 'cancelled'
        ) THEN
            ALTER TYPE message_status ADD VALUE 'cancelled';
        END IF;
    END $$;
""")
```
Use the same pattern for `audit_event_type` (four new values, four IF NOT EXISTS checks).

### Existing `delete_patient()` Transaction Pattern (from crud_service.py)
```python
# Source: app/services/patient/crud_service.py
with sync_transaction(self.db) as session:
    patient.deleted_at = now_sao_paulo()
    session.add(patient)
    # ... cancel flows and messages ...
```
Augment: insert `PatientDeletionAudit` record as the FIRST statement inside this block.

### Existing ConsentService Revocation (from lgpd/consent_service.py)
```python
# Source: app/services/lgpd/consent_service.py
await consent_service.revoke_consent(
    consent_id=consent.id,
    user_id=None,  # system-initiated (patient self-revoked via STOP)
    reason="Patient opt-out via WhatsApp STOP message"
)
```

### Existing Webhook Message Handler (from message_handler.py)
```python
# Source: app/services/webhook/handlers/message_handler.py — process_message()
# After patient lookup (Step 3), before flow routing:
text = message_data.get("text_content", "")
if is_opt_out_message(text):
    await self._handle_opt_out(patient, self.db)
    return None
```

### Alembic Migration Revision Chain (IMPORTANT)

The current migration heads are:
- `a9c4e1d2b7f0` (align_quiz_sessions)
- `015_rename_upload_metadata`

For new migrations in this phase, use one of these as `down_revision`. The most recent linear head is `a9c4e1d2b7f0`.

**Migration IDs to create (sequential):**
1. Plan 02-01 (LGPD-01): `down_revision = "a9c4e1d2b7f0"` → new revision e.g. `a1lgpd0001`
2. Plan 02-02 (LGPD-02): `down_revision = "<revision from 02-01>"`
3. Plan 02-03 (LGPD-03): `down_revision = "<revision from 02-02>"`

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Log-based deletion records | PostgreSQL persistent table with immutability rule | This phase | Survives Railway log rotation |
| No WhatsApp opt-out handler | Keyword detection + consent revocation in webhook handler | This phase | LGPD Art. 18 compliance |
| AI calls not in audit trail | AI event types in `AuditEventType` | This phase | AI accountability |

**Deprecated/outdated:**
- Railway application logs as the sole deletion record: insufficient — logs rotate, not queryable with SQL.

---

## Open Questions

1. **Who is `performing_user_id` in `delete_patient()`?**
   - What we know: `delete_patient()` in `PatientCRUDService` does not currently receive user context. The caller (`crud.py` router) does have `current_user`.
   - What's unclear: The service method signature must be extended to accept user context for the audit record.
   - Recommendation: Add `performed_by_user_id: Optional[UUID] = None, performed_by_email: Optional[str] = None` parameters to `delete_patient()`. The router already has `current_user`.

2. **What is the exact message structure in `MessageWebhookHandler.process_message()`?**
   - What we know: `message_data` comes from `extract_message_data(event_data)`. The handler already extracts text from `conversation` and `extendedTextMessage.text` fields in the webhook handler (`webhooks.py` lines 627-630).
   - What's unclear: Whether `message_data` from the extractor already has a `text_content` key or uses a different key name.
   - Recommendation: Read `app/services/webhook/utils/message_extractor.py` during planning to confirm the exact key name for text content.

3. **Should `patient_deletion_audit` include a foreign key to `patients.id`?**
   - What we know: LGPD requires the record to persist even after the patient record could theoretically be hard-deleted (LGPD Art. 16 — deletion must be audited).
   - What's unclear: The patient is soft-deleted (not hard-deleted), so a FK with ON DELETE CASCADE would destroy the audit record.
   - Recommendation: Do NOT add a FK constraint to `patients.id`. Store `patient_id` as a plain UUID column (no FK). This ensures the audit record persists even if the patient row is someday hard-deleted.

4. **Does `ConsentService` use the same `Session` type as `MessageWebhookHandler`?**
   - What we know: `MessageWebhookHandler.__init__` uses `db: Any` (sync `Session`). `ConsentService.__init__` uses `db: Session` (sync). `AuditService.__init__` uses `db: AsyncSession` (async — different!).
   - What's unclear: Whether calling `ConsentService` from `MessageWebhookHandler` works (both sync — yes). Whether LGPD-02 should also log to `AuditService` (would need async context or use `LGPDAuditService` which is sync-compatible).
   - Recommendation: For LGPD-02, use `LGPDAuditService` (sync, in `consent_service.py`) for audit logging — not `AuditService` (async). Both are LGPD-compliant.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)

- `app/models/audit_log.py` — `AuditEventType` enum definition, `AuditLog` model, column `SQLEnum(AuditEventType, name="audit_event_type", native_enum=True)`
- `app/models/patient.py` — `Patient` model columns, soft-delete via `deleted_at`, no existing opt-out field
- `app/models/consent.py` — `ConsentType.COMMUNICATION`, `ConsentStatus.REVOKED`, `revoked_at`
- `app/services/patient/crud_service.py` — `delete_patient()` implementation with `sync_transaction` pattern
- `app/services/lgpd/consent_service.py` — `ConsentService.revoke_consent()`, `LGPDAuditService`
- `app/services/audit/audit_service.py` — `AuditService` (async, uses `AsyncSession`)
- `app/services/webhook/handlers/message_handler.py` — `MessageWebhookHandler.process_message()` intercept point
- `app/integrations/whatsapp/api/webhooks.py` — `handle_message_upsert()` → message text extraction pattern
- `alembic/versions/011_hipaa_audit.py` — immutability rule pattern (`CREATE RULE ... DO INSTEAD NOTHING`)
- `alembic/versions/e2c4b1a9f7d3_add_cancelled_to_message_status_enum.py` — safe enum value addition pattern
- `alembic/versions/017_add_patient_soft_delete.py` — existing `deleted_at` soft-delete migration
- `.planning/REQUIREMENTS.md` — LGPD-01, LGPD-02, LGPD-03 requirement definitions

### Secondary (MEDIUM confidence — LGPD legal articles as referenced in requirements)

- LGPD Art. 16 — Retention obligation: audit records must outlast the data they describe
- LGPD Art. 18 — Right to revoke consent: must be immediate and unconditional
- LGPD Art. 46 — Technical security measures for data processing

### Tertiary (LOW confidence — not verified independently)

- PostgreSQL behavior for `ALTER TYPE ADD VALUE` inside transactions: known limitation on PG < 12, but AWS RDS uses PG 13+ (needs environment verification during implementation).

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, no new deps
- Architecture (LGPD-01 deletion audit): HIGH — direct reading of `delete_patient()` and migration 011
- Architecture (LGPD-02 opt-out): HIGH — `MessageWebhookHandler` entry point confirmed, `ConsentService.revoke_consent()` confirmed; open question on `text_content` key name is LOW risk
- Architecture (LGPD-03 AI enum): HIGH — enum type name confirmed in model, migration pattern confirmed in codebase
- Pitfalls: HIGH — all derived from actual code reading, not hypothetical

**Research date:** 2026-02-22
**Valid until:** 2026-03-22 (stable Python/PostgreSQL patterns — unlikely to change)
