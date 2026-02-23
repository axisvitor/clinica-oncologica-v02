"""
LGPD Batch Re-encryption Task.

Implements the Celery task for cryptographic key rotation of patient PII fields
(CPF, email, phone) as required by LGPD Art. 46.

This task processes patients in chunks using offset-based pagination to avoid
loading all records into memory, and uses Redis idempotency markers (scoped by
job_id) so that interrupted runs can be safely resumed without corrupting data.

IMPORTANT: HASH_SALT must NOT be changed during key rotation. Only the
PHI_ENCRYPTION_KEY (AES encryption key) is rotated. The hash salt is used for
searchable-hash generation and must remain constant to keep hashes consistent
across all records.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from app.celery_app import celery_app
from app.core.redis_manager import get_redis_manager
from app.database import get_scoped_session
from app.models.patient import Patient
from app.services.encryption.service import UnifiedEncryptionService
from app.tasks.base import DatabaseTask

logger = logging.getLogger(__name__)

# Redis key prefix for idempotency sets — scoped by job_id
_REDIS_COMPLETED_KEY = "lgpd:reencrypt:completed_ids:{job_id}"
# 7 days TTL for completed-ids set so interrupted jobs can be resumed
_IDEMPOTENCY_TTL_SECONDS = 7 * 24 * 60 * 60


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _make_encryption_service(master_key: str) -> UnifiedEncryptionService:
    """Construct a fully-initialized UnifiedEncryptionService from a raw master key.

    Args:
        master_key: Raw master key string (read from env var by the caller).

    Returns:
        Initialized UnifiedEncryptionService backed by the given master key.
    """
    svc = UnifiedEncryptionService(auto_initialize=False)
    salt = b"hormonia_unified_salt_2025"
    svc._keys["phi"] = svc._derive_key(master_key, salt)
    svc._keys["quiz"] = svc._derive_fernet_key(master_key)
    svc._initialize_algorithms()
    svc._initialize_field_encryptors()
    return svc


def _reencrypt_patient(
    patient: Any,
    old_svc: UnifiedEncryptionService,
    new_svc: UnifiedEncryptionService,
) -> bool:
    """Re-encrypt all PII fields on a single patient object.

    Decrypts each field with *old_svc* and re-encrypts with *new_svc*.
    Both the ``*_encrypted`` ciphertext column and the ``*_hash`` searchable
    hash column are updated on the patient object (but NOT committed here;
    the caller commits per chunk).

    Args:
        patient: SQLAlchemy Patient ORM instance.
        old_svc: Encryption service initialized with the old master key.
        new_svc: Encryption service initialized with the new master key.

    Returns:
        True if at least one field was changed, False if all were None/empty.

    Raises:
        Exception: Re-raises any decryption error after logging (caller decides
            whether to skip or abort).
    """
    changed = False

    # CPF
    if patient.cpf_encrypted is not None:
        try:
            plaintext = old_svc.decrypt_cpf(patient.cpf_encrypted)
        except Exception as exc:
            logger.error(
                "Failed to decrypt cpf_encrypted for patient %s: %s",
                patient.id,
                exc,
            )
            raise
        if plaintext:
            new_encrypted, new_hash = new_svc.encrypt_cpf(plaintext)
            patient.cpf_encrypted = new_encrypted
            patient.cpf_hash = new_hash
            changed = True

    # Email
    if patient.email_encrypted is not None:
        try:
            plaintext = old_svc.decrypt_email(patient.email_encrypted)
        except Exception as exc:
            logger.error(
                "Failed to decrypt email_encrypted for patient %s: %s",
                patient.id,
                exc,
            )
            raise
        if plaintext:
            new_encrypted, new_hash = new_svc.encrypt_email(plaintext)
            patient.email_encrypted = new_encrypted
            patient.email_hash = new_hash
            changed = True

    # Phone
    if patient.phone_encrypted is not None:
        try:
            plaintext = old_svc.decrypt_phone(patient.phone_encrypted)
        except Exception as exc:
            logger.error(
                "Failed to decrypt phone_encrypted for patient %s: %s",
                patient.id,
                exc,
            )
            raise
        if plaintext:
            new_encrypted, new_hash = new_svc.encrypt_phone(plaintext)
            patient.phone_encrypted = new_encrypted
            patient.phone_hash = new_hash
            changed = True

    return changed


def _already_processed(redis_client: Any, job_id: str, patient_id: Any) -> bool:
    """Check whether a patient has already been processed in this rotation job.

    Args:
        redis_client: Synchronous Redis client.
        job_id: Unique identifier for this rotation run.
        patient_id: Patient UUID or int primary key.

    Returns:
        True if the patient is already in the completed set.
    """
    key = _REDIS_COMPLETED_KEY.format(job_id=job_id)
    return bool(redis_client.sismember(key, str(patient_id)))


def _mark_processed(redis_client: Any, job_id: str, patient_id: Any) -> None:
    """Mark a patient as successfully re-encrypted in Redis.

    Uses SADD to add the patient_id to the completed set and EXPIRE to ensure
    the set is cleaned up after 7 days.

    Args:
        redis_client: Synchronous Redis client.
        job_id: Unique identifier for this rotation run.
        patient_id: Patient UUID or int primary key.
    """
    key = _REDIS_COMPLETED_KEY.format(job_id=job_id)
    redis_client.sadd(key, str(patient_id))
    redis_client.expire(key, _IDEMPOTENCY_TTL_SECONDS)


# ---------------------------------------------------------------------------
# Main task
# ---------------------------------------------------------------------------


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
    self: Any,
    *,
    old_key_env_var: str = "PHI_ENCRYPTION_KEY_PREVIOUS",
    new_key_env_var: str = "PHI_ENCRYPTION_KEY",
    job_id: str,
    chunk_size: int = 100,
    max_patients: int = 10000,
) -> Dict[str, Any]:
    """Celery task: batch re-encrypt patient PII fields for LGPD key rotation.

    Secrets are NOT accepted as task arguments to prevent them from appearing
    in the Celery result backend or broker logs.  Instead, the actual key
    values are read from environment variables named by *old_key_env_var* and
    *new_key_env_var*.

    The task processes patients in offset-based chunks of *chunk_size* rows and
    commits after each chunk.  Per-patient errors are counted and logged but do
    NOT abort the batch.  Redis idempotency markers (scoped by *job_id*) allow
    the task to be safely interrupted and re-invoked with the same *job_id* to
    resume where it left off.

    IMPORTANT: HASH_SALT must NOT be changed during key rotation.  Only the
    PHI_ENCRYPTION_KEY (AES encryption key) is rotated.

    Args:
        old_key_env_var: Environment variable name holding the previous master key.
        new_key_env_var: Environment variable name holding the new master key.
        job_id: Unique run identifier; used to scope Redis idempotency markers.
        chunk_size: Number of patients to process per DB query.
        max_patients: Hard upper bound on total patients processed in one run.

    Returns:
        Stats dict with keys:
            processed (int): Total patients visited.
            re_encrypted (int): Patients that had at least one field re-encrypted.
            skipped (int): Patients skipped due to idempotency marker.
            errors (int): Patients that raised an exception during re-encryption.
            has_more (bool): True if stopped at max_patients while more records exist.
    """
    # ----------------------------------------------------------------
    # 1. Read secrets from environment — NEVER accept as task args
    # ----------------------------------------------------------------
    old_master_key = os.environ.get(old_key_env_var)
    new_master_key = os.environ.get(new_key_env_var)

    assert old_master_key, (
        f"Environment variable '{old_key_env_var}' is required but not set. "
        "Set it before invoking the key rotation task."
    )
    assert new_master_key, (
        f"Environment variable '{new_key_env_var}' is required but not set. "
        "Set it before invoking the key rotation task."
    )

    hash_salt = os.environ.get("HASH_SALT")
    if not hash_salt:
        logger.warning(
            "HASH_SALT env var is not set. "
            "WARNING: HASH_SALT must NOT be changed during key rotation — "
            "all searchable hashes depend on it remaining constant. "
            "Ensure it is set and unchanged before running this task."
        )
    else:
        logger.info(
            "HASH_SALT is present. IMPORTANT: Do NOT change HASH_SALT during "
            "or after key rotation — hashes must remain consistent."
        )

    logger.info(
        "Starting batch re-encryption job_id=%s chunk_size=%d max_patients=%d "
        "old_key_env=%s new_key_env=%s",
        job_id,
        chunk_size,
        max_patients,
        old_key_env_var,
        new_key_env_var,
    )

    # ----------------------------------------------------------------
    # 2. Build encryption services
    # ----------------------------------------------------------------
    old_svc = _make_encryption_service(old_master_key)
    new_svc = _make_encryption_service(new_master_key)

    # ----------------------------------------------------------------
    # 3. Acquire Redis sync client for idempotency markers
    # ----------------------------------------------------------------
    redis_client = get_redis_manager().get_sync_client()

    # ----------------------------------------------------------------
    # 4. Chunked processing loop
    # ----------------------------------------------------------------
    processed = 0
    re_encrypted = 0
    skipped = 0
    errors = 0
    offset = 0
    has_more = False

    with get_scoped_session() as db:
        while processed < max_patients:
            batch = (
                db.query(Patient)
                .filter(Patient.deleted_at.is_(None))
                .order_by(Patient.id)
                .offset(offset)
                .limit(chunk_size)
                .all()
            )

            if not batch:
                break

            for patient in batch:
                if processed >= max_patients:
                    has_more = True
                    break

                if _already_processed(redis_client, job_id, patient.id):
                    skipped += 1
                    processed += 1
                    continue

                try:
                    changed = _reencrypt_patient(patient, old_svc, new_svc)
                    if changed:
                        re_encrypted += 1
                    _mark_processed(redis_client, job_id, patient.id)
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Error re-encrypting patient %s in job %s: %s",
                        patient.id,
                        job_id,
                        exc,
                        exc_info=True,
                    )
                    errors += 1

                processed += 1

            # Commit after every chunk regardless of per-patient errors
            db.commit()

            # Update Celery task state so callers can poll progress
            self.update_state(
                state="PROGRESS",
                meta={"processed": processed, "re_encrypted": re_encrypted},
            )

            if len(batch) < chunk_size:
                # Last chunk was smaller than chunk_size — no more rows
                break

            if has_more:
                break

            offset += chunk_size

    logger.info(
        "Completed batch re-encryption job_id=%s processed=%d re_encrypted=%d "
        "skipped=%d errors=%d has_more=%s",
        job_id,
        processed,
        re_encrypted,
        skipped,
        errors,
        has_more,
    )

    return {
        "processed": processed,
        "re_encrypted": re_encrypted,
        "skipped": skipped,
        "errors": errors,
        "has_more": has_more,
    }
