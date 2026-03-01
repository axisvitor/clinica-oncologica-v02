"""Tests for the LGPD batch re-encryption Celery task.

Covers:
- Full batch processing of all patients
- Idempotency: patients already in the Redis completed set are skipped
- Chunked processing commits once per non-empty chunk
- Per-patient decryption errors do not abort the batch
- Task reads keys from environment variables, not from task arguments
- has_more flag when max_patients limit is reached mid-stream
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import Mock, patch


# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------


def _make_patient(
    patient_id: int,
    *,
    cpf_encrypted: str | None = "encrypted:gcm:cpf_ciphertext",
    email_encrypted: bytes | None = b"encrypted:gcm:email_ciphertext",
    phone_encrypted: bytes | None = b"encrypted:gcm:phone_ciphertext",
) -> Mock:
    """Create a mock Patient ORM object."""
    p = Mock()
    p.id = patient_id
    p.deleted_at = None
    p.cpf_encrypted = cpf_encrypted
    p.cpf_hash = None
    p.email_encrypted = email_encrypted
    p.email_hash = None
    p.phone_encrypted = phone_encrypted
    p.phone_hash = None
    return p


@contextmanager
def _scoped_session(db: Mock):
    """Context manager that yields *db* — mirrors get_scoped_session signature."""
    yield db


def _build_query_mock(db: Mock, batches: list) -> None:
    """Configure db.query(...).filter(...).order_by(...).offset(...).limit(...).all()
    to return successive *batches* on each call."""
    call_count = {"n": 0}
    all_batches = list(batches)

    limit_mock = Mock()

    def _all_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        if idx < len(all_batches):
            return all_batches[idx]
        return []

    limit_mock.all.side_effect = _all_side_effect

    offset_mock = Mock()
    offset_mock.limit.return_value = limit_mock

    order_by_mock = Mock()
    order_by_mock.offset.return_value = offset_mock

    filter_mock = Mock()
    filter_mock.order_by.return_value = order_by_mock

    query_mock = Mock()
    query_mock.filter.return_value = filter_mock

    db.query.return_value = query_mock


def _make_svc(label: str) -> Mock:
    """Create a mock UnifiedEncryptionService for testing."""
    svc = Mock()
    svc.decrypt_cpf.return_value = f"cpf-plain-{label}"
    svc.decrypt_email.return_value = f"email-plain-{label}"
    svc.decrypt_phone.return_value = f"phone-plain-{label}"
    svc.encrypt_cpf.return_value = (f"enc-cpf-{label}", f"hash-cpf-{label}")
    svc.encrypt_email.return_value = (f"enc-email-{label}", f"hash-email-{label}")
    svc.encrypt_phone.return_value = (f"enc-phone-{label}", f"hash-phone-{label}")
    svc._keys = {}
    svc._derive_key = Mock(return_value=b"derived-key")
    svc._derive_fernet_key = Mock(return_value=b"fernet-key")
    svc._initialize_algorithms = Mock()
    svc._initialize_field_encryptors = Mock()
    return svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_batch_reencrypt_processes_all_patients():
    """All 3 patients are re-encrypted when Redis sismember returns False for all."""
    from app.tasks.lgpd.reencrypt_patients import batch_reencrypt_patients

    patients = [_make_patient(i) for i in range(1, 4)]
    db = Mock()
    _build_query_mock(db, [patients, []])  # first batch: 3 patients; second: empty

    redis_client = Mock()
    redis_client.sismember.return_value = False

    old_svc = _make_svc("old")
    new_svc = _make_svc("new")

    with (
        patch(
            "app.tasks.lgpd.reencrypt_patients.get_scoped_session",
            return_value=_scoped_session(db),
        ),
        patch(
            "app.tasks.lgpd.reencrypt_patients.get_redis_manager",
        ) as mock_rm,
        patch.dict(
            "os.environ",
            {
                "PHI_ENCRYPTION_KEY_PREVIOUS": "old-key-value",
                "PHI_ENCRYPTION_KEY": "new-key-value",
            },
        ),
        patch(
            "app.tasks.lgpd.reencrypt_patients._make_encryption_service",
            side_effect=[old_svc, new_svc],
        ),
        patch.object(batch_reencrypt_patients, "update_state"),
    ):
        mock_rm.return_value.get_sync_client.return_value = redis_client

        result = batch_reencrypt_patients.run(
            old_key_env_var="PHI_ENCRYPTION_KEY_PREVIOUS",
            new_key_env_var="PHI_ENCRYPTION_KEY",
            job_id="test-job-1",
        )

    assert result["re_encrypted"] == 3, f"Expected 3 re-encrypted, got {result}"
    assert result["errors"] == 0
    assert result["skipped"] == 0
    assert result["processed"] == 3
    db.commit.assert_called_once()


def test_idempotency_skips_already_processed():
    """Patients 1 and 3 have idempotency markers; only patient 2 is re-encrypted."""
    from app.tasks.lgpd.reencrypt_patients import batch_reencrypt_patients

    p1 = _make_patient(1)
    p2 = _make_patient(2)
    p3 = _make_patient(3)
    patients = [p1, p2, p3]

    db = Mock()
    _build_query_mock(db, [patients, []])

    redis_client = Mock()
    # sismember returns True for patient 1 and 3, False for patient 2
    redis_client.sismember.side_effect = lambda _key, patient_id: patient_id in {"1", "3"}

    old_svc = _make_svc("old")
    new_svc = _make_svc("new")

    with (
        patch(
            "app.tasks.lgpd.reencrypt_patients.get_scoped_session",
            return_value=_scoped_session(db),
        ),
        patch(
            "app.tasks.lgpd.reencrypt_patients.get_redis_manager",
        ) as mock_rm,
        patch.dict(
            "os.environ",
            {
                "PHI_ENCRYPTION_KEY_PREVIOUS": "old-key-value",
                "PHI_ENCRYPTION_KEY": "new-key-value",
            },
        ),
        patch(
            "app.tasks.lgpd.reencrypt_patients._make_encryption_service",
            side_effect=[old_svc, new_svc],
        ),
        patch.object(batch_reencrypt_patients, "update_state"),
    ):
        mock_rm.return_value.get_sync_client.return_value = redis_client

        result = batch_reencrypt_patients.run(
            old_key_env_var="PHI_ENCRYPTION_KEY_PREVIOUS",
            new_key_env_var="PHI_ENCRYPTION_KEY",
            job_id="test-job-idempotency",
        )

    assert result["re_encrypted"] == 1, f"Expected 1 re-encrypted, got {result}"
    assert result["skipped"] == 2, f"Expected 2 skipped, got {result}"
    assert result["processed"] == 3


def test_chunked_processing_commits_per_chunk():
    """db.commit() is called once per non-empty chunk (3 chunks for 5 patients, chunk_size=2)."""
    from app.tasks.lgpd.reencrypt_patients import batch_reencrypt_patients

    p1, p2, p3, p4, p5 = [_make_patient(i) for i in range(1, 6)]
    # chunk_size=2 → batches: [p1,p2], [p3,p4], [p5], []
    batches = [[p1, p2], [p3, p4], [p5], []]

    db = Mock()
    _build_query_mock(db, batches)

    redis_client = Mock()
    redis_client.sismember.return_value = False

    old_svc = _make_svc("old")
    new_svc = _make_svc("new")

    with (
        patch(
            "app.tasks.lgpd.reencrypt_patients.get_scoped_session",
            return_value=_scoped_session(db),
        ),
        patch(
            "app.tasks.lgpd.reencrypt_patients.get_redis_manager",
        ) as mock_rm,
        patch.dict(
            "os.environ",
            {
                "PHI_ENCRYPTION_KEY_PREVIOUS": "old-key-value",
                "PHI_ENCRYPTION_KEY": "new-key-value",
            },
        ),
        patch(
            "app.tasks.lgpd.reencrypt_patients._make_encryption_service",
            side_effect=[old_svc, new_svc],
        ),
        patch.object(batch_reencrypt_patients, "update_state"),
    ):
        mock_rm.return_value.get_sync_client.return_value = redis_client

        result = batch_reencrypt_patients.run(
            old_key_env_var="PHI_ENCRYPTION_KEY_PREVIOUS",
            new_key_env_var="PHI_ENCRYPTION_KEY",
            job_id="test-job-chunks",
            chunk_size=2,
        )

    # 3 non-empty chunks → 3 commits
    assert db.commit.call_count == 3, f"Expected 3 commits, got {db.commit.call_count}"
    assert result["processed"] == 5


def test_per_patient_error_does_not_abort_batch():
    """A decryption error on patient 2 should not prevent patients 1 and 3 from being processed."""
    from app.tasks.lgpd.reencrypt_patients import batch_reencrypt_patients

    p1 = _make_patient(1)
    p2 = _make_patient(2)
    p3 = _make_patient(3)

    db = Mock()
    _build_query_mock(db, [[p1, p2, p3], []])

    redis_client = Mock()
    redis_client.sismember.return_value = False

    old_svc = Mock()
    new_svc = Mock()
    old_svc._keys = {}
    new_svc._keys = {}

    call_counter = {"n": 0}

    def _decrypt_cpf_side_effect(val):
        call_counter["n"] += 1
        if call_counter["n"] == 2:
            raise ValueError("Simulated decryption error for patient 2")
        return "plain-cpf"

    old_svc.decrypt_cpf.side_effect = _decrypt_cpf_side_effect
    old_svc.decrypt_email.return_value = "plain-email"
    old_svc.decrypt_phone.return_value = "plain-phone"
    new_svc.encrypt_cpf.return_value = ("enc-cpf", "hash-cpf")
    new_svc.encrypt_email.return_value = ("enc-email", "hash-email")
    new_svc.encrypt_phone.return_value = ("enc-phone", "hash-phone")

    with (
        patch(
            "app.tasks.lgpd.reencrypt_patients.get_scoped_session",
            return_value=_scoped_session(db),
        ),
        patch(
            "app.tasks.lgpd.reencrypt_patients.get_redis_manager",
        ) as mock_rm,
        patch.dict(
            "os.environ",
            {
                "PHI_ENCRYPTION_KEY_PREVIOUS": "old-key-value",
                "PHI_ENCRYPTION_KEY": "new-key-value",
            },
        ),
        patch(
            "app.tasks.lgpd.reencrypt_patients._make_encryption_service",
            side_effect=[old_svc, new_svc],
        ),
        patch.object(batch_reencrypt_patients, "update_state"),
    ):
        mock_rm.return_value.get_sync_client.return_value = redis_client

        result = batch_reencrypt_patients.run(
            old_key_env_var="PHI_ENCRYPTION_KEY_PREVIOUS",
            new_key_env_var="PHI_ENCRYPTION_KEY",
            job_id="test-job-errors",
        )

    assert result["errors"] == 1, f"Expected 1 error, got {result}"
    assert result["re_encrypted"] == 2, f"Expected 2 re-encrypted, got {result}"
    assert result["processed"] == 3


def test_keys_read_from_env_vars_not_args():
    """The task must read key material from env vars, not from task arguments."""
    from app.tasks.lgpd.reencrypt_patients import batch_reencrypt_patients
    import inspect

    sig = inspect.signature(batch_reencrypt_patients.run)
    params = sig.parameters

    # Verify there is no parameter that accepts the raw key value directly
    # (only env var *names* are accepted, not the key values themselves)
    assert "old_key_env_var" in params, "old_key_env_var parameter missing"
    assert "new_key_env_var" in params, "new_key_env_var parameter missing"
    # There must be no parameter called 'old_key', 'new_key', 'master_key', etc.
    forbidden = {"old_key", "new_key", "master_key", "phi_key", "encryption_key"}
    for p in params:
        assert p not in forbidden, (
            f"Parameter '{p}' exposes a raw key — "
            "keys must only be read from env vars inside the task body."
        )

    # Verify the task body reads from os.environ
    source = inspect.getsource(batch_reencrypt_patients.run)
    assert "os.environ" in source, "Task must read from os.environ"


def test_has_more_flag_when_max_patients_reached():
    """has_more is True when max_patients is reached but more patients exist."""
    from app.tasks.lgpd.reencrypt_patients import batch_reencrypt_patients

    # 15 patients, max_patients=10, chunk_size=5
    patients = [_make_patient(i) for i in range(1, 16)]
    # Batches of 5: [1-5], [6-10], [11-15]
    batches = [patients[0:5], patients[5:10], patients[10:15], []]

    db = Mock()
    _build_query_mock(db, batches)

    redis_client = Mock()
    redis_client.sismember.return_value = False

    old_svc = _make_svc("old")
    new_svc = _make_svc("new")

    with (
        patch(
            "app.tasks.lgpd.reencrypt_patients.get_scoped_session",
            return_value=_scoped_session(db),
        ),
        patch(
            "app.tasks.lgpd.reencrypt_patients.get_redis_manager",
        ) as mock_rm,
        patch.dict(
            "os.environ",
            {
                "PHI_ENCRYPTION_KEY_PREVIOUS": "old-key-value",
                "PHI_ENCRYPTION_KEY": "new-key-value",
            },
        ),
        patch(
            "app.tasks.lgpd.reencrypt_patients._make_encryption_service",
            side_effect=[old_svc, new_svc],
        ),
        patch.object(batch_reencrypt_patients, "update_state"),
    ):
        mock_rm.return_value.get_sync_client.return_value = redis_client

        result = batch_reencrypt_patients.run(
            old_key_env_var="PHI_ENCRYPTION_KEY_PREVIOUS",
            new_key_env_var="PHI_ENCRYPTION_KEY",
            job_id="test-job-has-more",
            chunk_size=5,
            max_patients=10,
        )

    assert result["has_more"] is True, f"Expected has_more=True, got {result}"
    assert result["processed"] == 10, f"Expected processed=10, got {result}"
