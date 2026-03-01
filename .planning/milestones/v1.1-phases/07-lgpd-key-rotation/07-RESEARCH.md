# Phase 7: LGPD Key Rotation - Research

**Researched:** 2026-02-23
**Domain:** Cryptographic key rotation, Celery batch processing, SQLAlchemy encrypted-field re-encryption
**Confidence:** HIGH — all findings come from direct codebase inspection

## Summary

The codebase has a fully operational encryption stack for LGPD-covered PII fields. The `UnifiedEncryptionService` (`app/services/encryption/service.py`) is the canonical singleton that provides AES-256-GCM encryption for all patient PII (CPF, email, phone). A `rotate_encryption_key()` method already exists on the service but its body contains a `# TODO: Implement batch re-encryption` stub — Phase 7 must replace that stub with a real Celery task.

Three encrypted columns exist on the `patients` table: `cpf_encrypted` (Text), `email_encrypted` (LargeBinary), and `phone_encrypted` (LargeBinary). Each has a companion `*_hash` column for searchable lookup. Key rotation requires: (1) decrypting each field with the old key, (2) re-encrypting with the new key, and (3) regenerating the hash with the same `HASH_SALT` (which does NOT change during key rotation). The `HASH_SALT` is tied to field lookup, not to encryption — the two are independent.

The Celery infrastructure is mature: `DatabaseTask` base class, `get_scoped_session()`, chunked batch patterns in `app/tasks/flows/flow_tasks.py`, and `app/tasks/lgpd_tasks.py` as the natural home for a new LGPD re-encryption task. The main implementation risk is the SQLAlchemy `before_insert/before_update` hook `validate_patient_encryption` that fires on every Patient save — the task must bypass or satisfy this hook during re-encryption.

**Primary recommendation:** Add `app/tasks/lgpd/reencrypt_patients.py` containing a single `batch_reencrypt_patients` Celery task that uses offset-based chunked pagination, a Redis idempotency marker per patient ID, and a dual-key `UnifiedEncryptionService` instance for decrypt-old / encrypt-new. Register the task in `celery_app.py` include list.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LGPD-04 | Batch re-encryption implemented via Celery task with chunked processing and idempotency to enable key rotation (LGPD Art. 46) | Direct codebase: `UnifiedEncryptionService.rotate_encryption_key()` has TODO stub; `DatabaseTask` + `get_scoped_session()` are the established patterns; offset pagination found in `flow_tasks.py`; idempotency via Redis is used throughout |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cryptography` | already in requirements | AES-256-GCM encrypt/decrypt | Already used for all PII fields |
| `celery` | already installed | Background task execution | Project's sole task provider |
| `sqlalchemy` (sync `Session`) | already installed | Database access in Celery tasks | Celery uses sync `SessionLocal`, not `AsyncSession` |
| `app.core.redis_manager` | internal | Idempotency markers, progress tracking | Canonical Redis client per project MEMORY.md |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `app.tasks.base.DatabaseTask` | internal | Base class for DB-touching Celery tasks | Always used for Celery tasks with DB access |
| `app.database.get_scoped_session` | internal | Context manager for sync DB sessions | Standard session pattern in all tasks |
| `app.services.encryption.get_unified_encryption_service` | internal | Singleton encryption service | Use for new-key operations; instantiate a separate service for old-key |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Offset pagination | Keyset pagination (by `id`) | Keyset is faster at scale but requires UUID-sortable primary key; offset is simpler and sufficient for <100k patients |
| Redis idempotency markers | Database `reencrypted_at` column | DB column is more durable but requires a migration; Redis is faster to implement and sufficient for single-run idempotency |
| Single monolithic task | Chained sub-tasks (one per patient) | Sub-tasks add queue overhead; chunked single task is correct pattern per existing `flow_tasks.py` |

## Architecture Patterns

### Recommended Project Structure
```
backend-hormonia/app/tasks/
├── lgpd_tasks.py              # existing — audit log tasks
└── lgpd/
    └── reencrypt_patients.py  # NEW — batch re-encryption task
```

Then register in `celery_app.py` `include` list and `task_queue.py` `_TASK_MODULES`.

### Pattern 1: Chunked Offset Pagination (from flow_tasks.py)
**What:** Query `N` records at `offset`, process, commit, increment offset, repeat
**When to use:** Any batch processing over a large table
**Example:**
```python
# Source: app/tasks/flows/flow_tasks.py (lines 113-121)
batch_size = max(1, FLOW_BATCH_SIZE)
for i in range(0, len(active_flows), batch_size):
    batch = active_flows[i : i + batch_size]
```

For re-encryption, the pattern must be DB-driven (not load-all-then-chunk) to avoid OOM:
```python
offset = 0
chunk_size = 100
while True:
    with get_scoped_session() as db:
        patients = db.query(Patient).filter(
            Patient.deleted_at.is_(None)
        ).order_by(Patient.id).offset(offset).limit(chunk_size).all()
        if not patients:
            break
        for patient in patients:
            _reencrypt_patient(patient, old_service, new_service)
        db.commit()
    offset += chunk_size
```

### Pattern 2: DatabaseTask Base Class (from lgpd_tasks.py)
**What:** Celery task inheriting from `DatabaseTask` with retry decorators
**When to use:** Any task that touches the database
**Example:**
```python
# Source: app/tasks/lgpd_tasks.py lines 380-391
@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="lgpd.batch_reencrypt_patients",
    queue="celery",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def batch_reencrypt_patients(self, new_master_key: str, chunk_size: int = 100, ...) -> dict:
```

### Pattern 3: Dual-Key Service Instantiation for Key Rotation
**What:** Instantiate two separate `UnifiedEncryptionService` objects — one with old key, one with new key — for decrypt-old / encrypt-new
**When to use:** Key rotation re-encryption
**Why:** The singleton `get_unified_encryption_service()` holds the CURRENT key. During rotation, you need the OLD key to decrypt and the NEW key to encrypt. Never mutate the singleton mid-task.
**Example:**
```python
from app.services.encryption.service import UnifiedEncryptionService
from app.services.encryption.types import EncryptionAlgorithm

# Old-key service: disable auto_initialize, manually inject old key
old_service = UnifiedEncryptionService(auto_initialize=False)
old_service._keys["phi"] = _derive_phi_key(old_master_key)
old_service._initialize_algorithms()
old_service._initialize_field_encryptors()

# New-key service: instantiate fresh with new master key from env
new_service = UnifiedEncryptionService(auto_initialize=False)
new_service._keys["phi"] = _derive_phi_key(new_master_key)
new_service._initialize_algorithms()
new_service._initialize_field_encryptors()
```

The `_derive_key()` call uses fixed salt `b"hormonia_unified_salt_2025"` — confirmed in `service.py` line 234.

### Pattern 4: Redis Idempotency Marker
**What:** Store `patient_id` in a Redis Set after successful re-encryption; skip on re-run
**When to use:** Resumable batch jobs where partial progress must be preserved
**Example:**
```python
from app.core.redis_manager import get_redis_manager

redis = get_redis_manager().get_sync_client()
IDEMPOTENCY_KEY = "lgpd:reencrypt:completed_ids:{job_id}"

def _already_processed(redis_client, job_id, patient_id):
    return redis_client.sismember(f"lgpd:reencrypt:completed_ids:{job_id}", str(patient_id))

def _mark_processed(redis_client, job_id, patient_id):
    redis_client.sadd(f"lgpd:reencrypt:completed_ids:{job_id}", str(patient_id))
    redis_client.expire(f"lgpd:reencrypt:completed_ids:{job_id}", 86400 * 7)  # 7 days
```

### Pattern 5: Bypassing the SQLAlchemy Encryption Hook
**What:** The `validate_patient_encryption` event hook (`patient.py` lines 765-796) fires `before_insert/before_update` and raises `ValueError` if `*_encrypted` is set without `*_hash`. During re-encryption, both must always be updated together.
**When to use:** Every patient field update during re-encryption
**How to satisfy:** Always call `patient.set_cpf(plaintext)`, `patient.set_email(plaintext)`, `patient.set_phone(plaintext)` rather than writing raw to `*_encrypted` and `*_hash` columns separately. These setters on the `Patient` model call the encryption service and set both columns atomically.

**Alternative approach** (if performance is critical): Update encrypted column and hash column together in a raw SQL UPDATE via `db.execute()`, bypassing the ORM hooks entirely. This is faster for large batches but requires care to match the exact storage formats.

### Anti-Patterns to Avoid
- **Loading all patients into memory:** Query in chunks using `.offset().limit()` inside `get_scoped_session()`, not `db.query(Patient).all()`
- **Mutating the global singleton:** Never call `encryption_service._keys["phi"] = new_key` on the singleton; create a separate instance
- **Single large transaction:** Commit per-chunk, not one transaction for all patients — database lock escalation and transaction log growth
- **Re-computing the hash with a new HASH_SALT:** The `HASH_SALT` does NOT rotate with the encryption key. Hashes are computed from plaintext + HASH_SALT. If HASH_SALT changes, all lookup indexes break. Phase 7 only rotates `PHI_ENCRYPTION_KEY`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Database sessions | Custom session factory | `get_scoped_session()` from `app.database` | Already handles transaction scope, rollback, pool management |
| Encryption/decryption | Custom AES logic | `UnifiedEncryptionService` with separate instances | Handles prefix detection, algorithm dispatch, field normalization |
| Hash generation | SHA-256 direct | `SearchableHash.hash_cpf/email/phone()` | Applies normalization + HASH_SALT namespacing consistently |
| Task retry logic | Manual try/except retry | `autoretry_for` + `retry_backoff` on `@celery_app.task` | Built-in exponential backoff, max_retries, jitter |
| Redis client | Direct `redis.Redis()` | `get_redis_manager().get_sync_client()` | SSL, pooling, circuit breaker per MEMORY.md |

**Key insight:** The field setters on `Patient` (`set_cpf`, `set_email`, `set_phone`) already orchestrate encrypt + hash atomically. Use them — they are the idiomatic API.

## Common Pitfalls

### Pitfall 1: CBC Prefix Ambiguity
**What goes wrong:** Legacy records encrypted with AES-256-CBC have prefix `"encrypted:"` (no algorithm segment). New GCM records have `"encrypted:gcm:"`. The `decrypt_field()` method auto-detects by looking for `:gcm:` or `:fernet:` — otherwise falls back to CBC. If a CBC record is accidentally re-encrypted as GCM but the prefix detection logic is used with the wrong key, decryption fails silently.
**Why it happens:** The `decrypt_field()` in `service.py` lines 340-347 has this detection logic but it is key-agnostic — it tries the current key regardless of which algorithm was detected.
**How to avoid:** Before re-encrypting, always decrypt with `old_service.decrypt_field()` first. If decryption raises, log the patient ID and continue (skip that record, mark for manual review). Never write new encrypted value until old decryption succeeds.
**Warning signs:** High error count in task result dict; `InvalidToken` or `ValueError` exceptions during decryption phase.

### Pitfall 2: Phone/Email Stored as LargeBinary (bytes)
**What goes wrong:** `Patient.email_encrypted` and `Patient.phone_encrypted` are `LargeBinary` (bytea in PostgreSQL), not `Text`. The `EmailEncryptor.encrypt()` returns `Tuple[bytes, str]` — the encrypted value is `bytes`. But `CPFEncryptor.encrypt()` for CPF returns `Tuple[str, str]` since `cpf_encrypted` is `Text`.
**Why it happens:** Different columns use different types — confirmed in `patient.py` lines 103-114.
**How to avoid:** Use the model setters (`set_cpf`, `set_email`, `set_phone`) which handle the encoding correctly. If using raw column writes, match the storage type: CPF → `str`, email/phone → `bytes`.

### Pitfall 3: Hash Columns Must Also Be Regenerated
**What goes wrong:** After re-encryption with a new PHI_ENCRYPTION_KEY, the plaintext values are unchanged, so the hashes should remain identical if HASH_SALT is the same. BUT: if anyone also rotates HASH_SALT alongside key rotation, all lookup indexes break silently — patients become unsearchable by phone/email/CPF.
**Why it happens:** Key rotation and hash salt rotation are conflated.
**How to avoid:** Phase 7 scope is PHI_ENCRYPTION_KEY rotation ONLY. HASH_SALT must NOT change. Document this constraint explicitly in the task docstring. The task should assert that HASH_SALT is present and unchanged before starting.

### Pitfall 4: SQLAlchemy Event Hook Fires on Every UPDATE
**What goes wrong:** The `validate_patient_encryption` hook (lines 765-796 in `patient.py`) fires on every `before_update`. If re-encryption code sets `patient.cpf_encrypted` without setting `patient.cpf_hash`, the hook raises `ValueError: CPF encryption incomplete`.
**Why it happens:** The hook is a safety net ensuring both columns are always in sync.
**How to avoid:** Always use `patient.set_cpf(decrypted_value)` etc. — these setters update both columns atomically. Alternatively, update both columns in the same assignment before the commit flush.

### Pitfall 5: Celery Task Time Limit
**What goes wrong:** `task_time_limit=30 * 60` (30 minutes) is set globally in `celery_app.py`. If the batch is large (e.g., 50k patients at 100/chunk = 500 iterations), the task may exceed this limit.
**Why it happens:** A single monolithic task processes all records.
**How to avoid:** The task should accept a `max_patients` limit parameter (default 10,000 per invocation). For full rotation, invoke the task multiple times with offset continuation, tracked via Redis. Alternatively, the task can re-enqueue itself with an updated offset after each chunk.

### Pitfall 6: The Singleton UnifiedEncryptionService
**What goes wrong:** `get_unified_encryption_service()` returns a global singleton that holds the CURRENT `PHI_ENCRYPTION_KEY`. During key rotation, we need BOTH the old key (for decryption) and the new key (for encryption). Calling `rotate_encryption_key()` on the singleton replaces `_keys["phi"]` mid-execution, breaking any concurrent decryption.
**Why it happens:** The `rotate_encryption_key()` stub in `service.py` lines 587-626 already shows this problem — it saves old_key, derives new_key, sets `self._keys["phi"] = new_key`, then calls `_initialize_algorithms()`.
**How to avoid:** NEVER use `rotate_encryption_key()` on the singleton for the Celery task. Create two independent `UnifiedEncryptionService(auto_initialize=False)` instances with explicitly injected keys.

## Code Examples

Verified patterns from direct codebase inspection:

### Creating a Dual-Key Encryption Service
```python
# Source: app/services/encryption/service.py lines 104-132 (_derive_key) and 228-234 (_initialize_encryption_keys)
import base64
from app.services.encryption.service import UnifiedEncryptionService
from app.services.encryption.types import EncryptionAlgorithm

SALT = b"hormonia_unified_salt_2025"  # fixed salt from service.py line 234

def _make_encryption_service(master_key: str) -> UnifiedEncryptionService:
    """Create UnifiedEncryptionService with a specific master key."""
    svc = UnifiedEncryptionService(auto_initialize=False)
    svc._keys["phi"] = svc._derive_key(master_key, SALT)
    quiz_secret = master_key  # quiz key not relevant for patient field re-encryption
    svc._keys["quiz"] = svc._derive_fernet_key(quiz_secret)
    svc._initialize_algorithms()
    svc._initialize_field_encryptors()
    return svc
```

### Per-Patient Re-encryption Function
```python
# Source: patient.py lines 466-488 (set_cpf), 546-569 (set_email), 604-628 (set_phone)
def _reencrypt_patient(patient, old_svc: UnifiedEncryptionService, new_svc: UnifiedEncryptionService) -> bool:
    """Re-encrypt one patient's PII fields. Returns True if any field was changed."""
    changed = False

    # CPF: Text storage
    if patient.cpf_encrypted:
        try:
            plaintext = old_svc.decrypt_cpf(patient.cpf_encrypted)
            if plaintext:
                encrypted, cpf_hash = new_svc.encrypt_cpf(plaintext)
                patient.cpf_encrypted = encrypted
                patient.cpf_hash = cpf_hash
                changed = True
        except Exception as exc:
            logger.error("Failed to re-encrypt CPF for patient %s: %s", patient.id, exc)
            raise

    # Email: LargeBinary storage (bytes)
    if patient.email_encrypted:
        try:
            plaintext = old_svc.decrypt_email(patient.email_encrypted)
            if plaintext:
                encrypted_bytes, email_hash = new_svc.encrypt_email(plaintext)
                patient.email_encrypted = encrypted_bytes
                patient.email_hash = email_hash
                changed = True
        except Exception as exc:
            logger.error("Failed to re-encrypt email for patient %s: %s", patient.id, exc)
            raise

    # Phone: LargeBinary storage (bytes)
    if patient.phone_encrypted:
        try:
            plaintext = old_svc.decrypt_phone(patient.phone_encrypted)
            if plaintext:
                encrypted_bytes, phone_hash = new_svc.encrypt_phone(plaintext)
                patient.phone_encrypted = encrypted_bytes
                patient.phone_hash = phone_hash
                changed = True
        except Exception as exc:
            logger.error("Failed to re-encrypt phone for patient %s: %s", patient.id, exc)
            raise

    return changed
```

### Task Skeleton (Celery + DatabaseTask pattern)
```python
# Source pattern: app/tasks/lgpd_tasks.py lines 380-391, 571-577
@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="lgpd.batch_reencrypt_patients",
    queue="celery",
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=300,
)
def batch_reencrypt_patients(
    self,
    old_master_key: str,
    new_master_key: str,
    job_id: str,
    offset: int = 0,
    chunk_size: int = 100,
    max_patients: int = 10000,
) -> dict:
    """
    Batch re-encrypt patient PII fields for LGPD key rotation.

    Args:
        old_master_key: Current PHI_ENCRYPTION_KEY (to decrypt existing data)
        new_master_key: New PHI_ENCRYPTION_KEY (to encrypt with new key)
        job_id: Unique identifier for this rotation job (for idempotency)
        offset: Starting record offset (enables resumability)
        chunk_size: Records per DB query (default 100)
        max_patients: Max patients to process per invocation (default 10000)

    Returns:
        Dict with stats: processed, re_encrypted, skipped, errors, has_more
    """
```

### Chunked Query Pattern (from flow_tasks.py adapted for patients)
```python
# Source: app/tasks/flows/flow_tasks.py lines 113-121 adapted
from app.database import get_scoped_session
from app.models.patient import Patient

processed = 0
re_encrypted = 0
errors = 0

while processed < max_patients:
    with get_scoped_session() as db:
        batch = (
            db.query(Patient)
            .filter(Patient.deleted_at.is_(None))
            .order_by(Patient.id)
            .offset(offset + processed)
            .limit(chunk_size)
            .all()
        )
        if not batch:
            break
        for patient in batch:
            if not _already_processed(redis, job_id, patient.id):
                try:
                    changed = _reencrypt_patient(patient, old_svc, new_svc)
                    if changed:
                        re_encrypted += 1
                    _mark_processed(redis, job_id, patient.id)
                except Exception:
                    errors += 1
        db.commit()
    processed += len(batch)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Plaintext CPF/email/phone columns | Encrypted columns + hash columns only (migration 030) | v1.0 | No plaintext fallback; re-encryption must fully succeed before old key is decommissioned |
| AES-128-CBC (Fernet) | AES-256-GCM (default) + legacy CBC detection | v1.0 consolidation | Must handle both CBC and GCM prefixes when decrypting with old key |
| `rotate_encryption_key()` stub | Needs real batch Celery task | NOW (Phase 7) | The stub at `service.py:609` contains only a comment — it updates the in-memory key but does not touch the database |

**Deprecated/outdated:**
- `EncryptionService` in `app/core/encryption.py`: Fernet-only legacy singleton. Still used for legacy decryption (ENCRYPTION_KEY_CURRENT env var). Separate from `UnifiedEncryptionService`. Phase 7 does NOT need to re-encrypt Fernet-stored data if those fields have already been migrated to GCM columns.
- `KeyManagementService` in `app/services/encryption/key_manager.py`: Reads ENCRYPTION_KEY_CURRENT / ENCRYPTION_KEY_PREVIOUS env vars. Provides Fernet keys. Relevant for the old `EncryptionService`, NOT for `UnifiedEncryptionService` which reads `PHI_ENCRYPTION_KEY`.

## Open Questions

1. **Does ENCRYPTION_KEY_CURRENT (Fernet) also need rotation alongside PHI_ENCRYPTION_KEY (AES-GCM)?**
   - What we know: `ENCRYPTION_KEY_CURRENT` is used by `EncryptionService` (Fernet), a legacy service in `app/core/encryption.py`. `PHI_ENCRYPTION_KEY` is used by `UnifiedEncryptionService` (AES-GCM). The Patient model columns (`email_encrypted`, `phone_encrypted`, `cpf_encrypted`) use the unified service (AES-GCM/CBC prefix format).
   - What's unclear: Are there any records in production that were encrypted by the old Fernet `EncryptionService` and never migrated to AES-GCM format? Migration 029/028 migrated data to encrypted columns but it is unclear whether it used Fernet or AES-GCM.
   - Recommendation: Inspect migration `029_migrate_email_phone_to_encrypted.py` to confirm the storage format. If it used Fernet (old `EncryptionService`), the batch task must also handle `"gAAAAAB..."` prefix decryption via `EncryptionService`. Phase 7 scope should focus on `PHI_ENCRYPTION_KEY` rotation; the planner should note this as a risk.

2. **What is the approximate patient count?**
   - What we know: No count available without running a query. The system serves oncology patients for multiple doctors.
   - What's unclear: Could be 50 or 50,000.
   - Recommendation: The task design should work correctly at any scale. The chunk_size=100 + max_patients=10000 per invocation approach with Redis resumability handles this transparently. Default to 100 records/chunk as a conservative starting point.

3. **Should the task accept the old master key as a parameter, or read it from a separate env var?**
   - What we know: Passing secrets as Celery task parameters is a security risk (they appear in task result backend, broker logs, and Flower UI). The project uses env vars for all secrets.
   - What's unclear: The preferred invocation pattern for key rotation in this project.
   - Recommendation: The task should accept an `old_key_env_var` parameter (name of the env var containing the old key) rather than the key itself, OR read both current and new key from env vars (`PHI_ENCRYPTION_KEY_PREVIOUS` and `PHI_ENCRYPTION_KEY`). This mirrors the `ENCRYPTION_KEY_PREVIOUS` pattern already established in `key_manager.py`.

4. **Transaction isolation during concurrent reads while re-encryption runs?**
   - What we know: PostgreSQL defaults to READ COMMITTED. The Celery worker processes records sequentially. FastAPI API processes run concurrently.
   - What's unclear: If a FastAPI request decrypts a patient's phone while the Celery task is mid-update, it would read the old encrypted value correctly (READ COMMITTED sees committed data only).
   - Recommendation: Commit per-chunk (not per-patient) for efficiency, but use `REPEATABLE READ` or `SELECT FOR UPDATE` if exact consistency is required during re-encryption. For a maintenance-window operation, READ COMMITTED is acceptable — partial re-encryption is handled by idempotency markers.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `backend-hormonia/app/services/encryption/service.py` — full encryption service with rotate stub
- Direct codebase inspection — `backend-hormonia/app/services/encryption/key_manager.py` — key management patterns
- Direct codebase inspection — `backend-hormonia/app/core/encryption.py` — legacy Fernet service
- Direct codebase inspection — `backend-hormonia/app/models/patient.py` — encrypted columns, setters, validation hook
- Direct codebase inspection — `backend-hormonia/app/tasks/lgpd_tasks.py` — LGPD Celery task pattern
- Direct codebase inspection — `backend-hormonia/app/tasks/base.py` — DatabaseTask, BaseTask
- Direct codebase inspection — `backend-hormonia/app/tasks/flows/flow_tasks.py` — chunked batch processing pattern
- Direct codebase inspection — `backend-hormonia/app/celery_app.py` — task registration, time limits, queue config
- Direct codebase inspection — `backend-hormonia/app/core/searchable_hash.py` — HASH_SALT usage, field namespacing
- Direct codebase inspection — `backend-hormonia/app/config/settings/security.py` — key env var names and descriptions
- Direct codebase inspection — `backend-hormonia/app/services/encryption/algorithms/aes_gcm.py` — GCM prefix format
- Direct codebase inspection — `backend-hormonia/app/services/encryption/algorithms/aes_cbc.py` — CBC prefix format
- Direct codebase inspection — `backend-hormonia/app/services/encryption/fields/email.py` — LargeBinary return type
- Direct codebase inspection — `backend-hormonia/app/services/encryption/fields/base.py` — field encryptor interface

### Secondary (MEDIUM confidence)
- `REQUIREMENTS.md` — LGPD-04 requirement text: "chunked processing e idempotencia"
- `ROADMAP.md` — Phase 7 success criteria: "idempotencia verificada por teste"
- `STATE.md` — Phase 6 completion context; AsyncSession decisions not relevant to Phase 7 (Celery tasks use sync Session)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use; no external dependencies needed
- Architecture: HIGH — task pattern directly modeled on `lgpd_tasks.py`; dual-key pattern derivable from `service.py` constructor
- Pitfalls: HIGH — based on direct code reading (LargeBinary types, hook logic, CBC prefix ambiguity confirmed in source)
- Open questions: MEDIUM — require either DB query or architectural decision to resolve

**Research date:** 2026-02-23
**Valid until:** Stable — until encryption service is significantly refactored
