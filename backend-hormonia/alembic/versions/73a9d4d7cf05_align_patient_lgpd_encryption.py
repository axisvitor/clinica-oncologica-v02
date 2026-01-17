"""Align patient LGPD encryption columns, hashes, and audit tables.

Revision ID: 73a9d4d7cf05
Revises: 29016a88ebf0
Create Date: 2026-01-09

Ensures patient encrypted columns exist, migrates plaintext data, enforces
hash-based constraints/indexes, and removes plaintext PII columns. Also
backfills LGPD audit tables if missing.

WHY:
- Not recorded (legacy migration).

WHAT:
- Not recorded (legacy migration).

IMPACT:
- Not recorded (legacy migration).

BENCHMARK:
- Not recorded (legacy migration).

ROLLBACK:
- Not recorded (legacy migration).

RELATED:
- Not recorded (legacy migration).

MIGRATION TYPE:
- Not recorded (legacy migration).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.dialects import postgresql


# revision identifiers
revision = "73a9d4d7cf05"
down_revision = "29016a88ebf0"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _unique_constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        constraint["name"] == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _create_index_if_missing(
    bind,
    index_name: str,
    table_name: str,
    columns,
    *,
    unique: bool = False,
    where: str | None = None,
    where_columns: list[str] | None = None,
    required_columns: list[str] | None = None,
) -> None:
    if not _table_exists(bind, table_name):
        return

    if _index_exists(bind, table_name, index_name):
        return

    existing_cols = {col["name"] for col in sa.inspect(bind).get_columns(table_name)}
    if required_columns and not all(col in existing_cols for col in required_columns):
        return

    if where and where_columns and not all(col in existing_cols for col in where_columns):
        where = None

    op.create_index(
        index_name,
        table_name,
        columns,
        unique=unique,
        postgresql_where=sa.text(where) if where else None,
    )


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "patients"):
        return

    # Add encrypted/hash columns if missing
    if not _column_exists(bind, "patients", "cpf_encrypted"):
        op.add_column("patients", sa.Column("cpf_encrypted", sa.Text(), nullable=True))
    if not _column_exists(bind, "patients", "cpf_hash"):
        op.add_column("patients", sa.Column("cpf_hash", sa.String(64), nullable=True))
    if not _column_exists(bind, "patients", "email_encrypted"):
        op.add_column("patients", sa.Column("email_encrypted", sa.LargeBinary(), nullable=True))
    if not _column_exists(bind, "patients", "email_hash"):
        op.add_column("patients", sa.Column("email_hash", sa.String(64), nullable=True))
    if not _column_exists(bind, "patients", "phone_encrypted"):
        op.add_column("patients", sa.Column("phone_encrypted", sa.LargeBinary(), nullable=True))
    if not _column_exists(bind, "patients", "phone_hash"):
        op.add_column("patients", sa.Column("phone_hash", sa.String(64), nullable=True))

    if bind.dialect.name == "postgresql":
        if _column_exists(bind, "patients", "email_encrypted"):
            op.execute(
                "COMMENT ON COLUMN patients.email_encrypted IS "
                "'Encrypted email using AES-256-GCM for LGPD compliance.'"
            )
        if _column_exists(bind, "patients", "email_hash"):
            op.execute(
                "COMMENT ON COLUMN patients.email_hash IS "
                "'SHA-256 hash of email for searchable encryption.'"
            )

    # Hash indexes and unique constraints
    _create_index_if_missing(
        bind,
        "ix_patients_cpf_hash",
        "patients",
        ["cpf_hash"],
        required_columns=["cpf_hash"],
    )
    _create_index_if_missing(
        bind,
        "ix_patients_email_hash",
        "patients",
        ["email_hash"],
        required_columns=["email_hash"],
    )
    _create_index_if_missing(
        bind,
        "ix_patients_phone_hash",
        "patients",
        ["phone_hash"],
        required_columns=["phone_hash"],
    )

    _create_index_if_missing(
        bind,
        "ix_patients_cpf_hash_doctor",
        "patients",
        ["cpf_hash", "doctor_id"],
        where="cpf_hash IS NOT NULL",
        where_columns=["cpf_hash"],
        required_columns=["cpf_hash", "doctor_id"],
    )
    _create_index_if_missing(
        bind,
        "ix_patients_email_hash_doctor",
        "patients",
        ["email_hash", "doctor_id"],
        unique=True,
        where="email_hash IS NOT NULL AND deleted_at IS NULL",
        where_columns=["email_hash", "deleted_at"],
        required_columns=["email_hash", "doctor_id"],
    )
    _create_index_if_missing(
        bind,
        "ix_patients_phone_hash_doctor",
        "patients",
        ["phone_hash", "doctor_id"],
        unique=True,
        where="phone_hash IS NOT NULL AND deleted_at IS NULL",
        where_columns=["phone_hash", "deleted_at"],
        required_columns=["phone_hash", "doctor_id"],
    )

    op.execute("ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_cpf_doctor")
    op.execute("ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_email_doctor")
    op.execute("ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_phone_doctor")
    op.execute("ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_email_hash_doctor")
    op.execute("ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_phone_hash_doctor")
    if not _unique_constraint_exists(bind, "patients", "uq_patient_cpf_hash_doctor"):
        op.execute(
            "ALTER TABLE patients ADD CONSTRAINT uq_patient_cpf_hash_doctor UNIQUE (cpf_hash, doctor_id)"
        )

    # Migrate plaintext data if plaintext columns exist
    has_cpf = _column_exists(bind, "patients", "cpf")
    has_email = _column_exists(bind, "patients", "email")
    has_phone = _column_exists(bind, "patients", "phone")

    if has_cpf or has_email or has_phone:
        session = Session(bind=bind)
        try:
            from app.services.encryption import (
                get_cpf_encryption_service,
                get_lgpd_encryption_service,
            )

            cpf_service = get_cpf_encryption_service()
            lgpd_service = get_lgpd_encryption_service()

            select_columns = ["id"]
            if has_cpf:
                select_columns.append("cpf")
            if has_email:
                select_columns.append("email")
            if has_phone:
                select_columns.append("phone")

            where_parts = []
            if has_cpf:
                where_parts.append("(cpf IS NOT NULL AND cpf_encrypted IS NULL)")
            if has_email:
                where_parts.append("(email IS NOT NULL AND email_encrypted IS NULL)")
            if has_phone:
                where_parts.append("(phone IS NOT NULL AND phone_encrypted IS NULL)")

            where_clause = " OR ".join(where_parts)
            query = text(
                f"SELECT {', '.join(select_columns)} FROM patients WHERE {where_clause}"
            )

            for row in session.execute(query):
                updates = {}
                if has_cpf and row.cpf:
                    encrypted_cpf, cpf_hash = cpf_service.encrypt_cpf(row.cpf)
                    updates["cpf_encrypted"] = encrypted_cpf
                    updates["cpf_hash"] = cpf_hash
                if has_email and row.email:
                    encrypted_email, email_hash = lgpd_service.encrypt_email(row.email)
                    updates["email_encrypted"] = encrypted_email
                    updates["email_hash"] = email_hash
                if has_phone and row.phone:
                    encrypted_phone, phone_hash = lgpd_service.encrypt_phone(row.phone)
                    updates["phone_encrypted"] = encrypted_phone
                    updates["phone_hash"] = phone_hash

                if updates:
                    updates["id"] = str(row.id)
                    update_stmt = text(
                        """
                        UPDATE patients
                        SET cpf_encrypted = COALESCE(:cpf_encrypted, cpf_encrypted),
                            cpf_hash = COALESCE(:cpf_hash, cpf_hash),
                            email_encrypted = COALESCE(:email_encrypted, email_encrypted),
                            email_hash = COALESCE(:email_hash, email_hash),
                            phone_encrypted = COALESCE(:phone_encrypted, phone_encrypted),
                            phone_hash = COALESCE(:phone_hash, phone_hash),
                            updated_at = NOW()
                        WHERE id = :id
                        """
                    )
                    session.execute(update_stmt, updates)

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Drop plaintext indexes and columns
    op.execute("DROP INDEX IF EXISTS idx_patients_phone")
    op.execute("DROP INDEX IF EXISTS idx_patients_email")
    op.execute("DROP INDEX IF EXISTS idx_patient_cpf_doctor")
    op.execute("DROP INDEX IF EXISTS idx_patient_email_doctor")
    op.execute("DROP INDEX IF EXISTS idx_patient_phone_doctor")

    op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS cpf")
    op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS email")
    op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS phone")

    # Ensure LGPD audit tables exist
    if not _table_exists(bind, "lgpd_audit_logs"):
        op.create_table(
            "lgpd_audit_logs",
            sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=True),
            sa.Column("user_email", sa.String(length=255), nullable=True),
            sa.Column("user_role", sa.String(length=50), nullable=True),
            sa.Column("patient_id", sa.UUID(), nullable=True),
            sa.Column("patient_identifier", sa.String(length=255), nullable=True),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("data_category", sa.String(length=50), nullable=False),
            sa.Column("resource_type", sa.String(length=100), nullable=False),
            sa.Column("resource_id", sa.String(length=255), nullable=True),
            sa.Column("fields_accessed", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("fields_modified", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("purpose", sa.String(length=255), nullable=True),
            sa.Column("legal_basis", sa.String(length=100), nullable=True),
            sa.Column("ip_address", postgresql.INET(), nullable=True),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            sa.Column("session_id", sa.String(length=255), nullable=True),
            sa.Column("request_id", sa.String(length=255), nullable=True),
            sa.Column("additional_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("success", sa.Boolean(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("can_be_deleted", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_lgpd_audit_action_time", "lgpd_audit_logs", ["action", "created_at"])
        op.create_index("ix_lgpd_audit_failures", "lgpd_audit_logs", ["created_at"], postgresql_where=sa.text("NOT success"))
        op.create_index("ix_lgpd_audit_patient_time", "lgpd_audit_logs", ["patient_id", "created_at"])
        op.create_index("ix_lgpd_audit_session", "lgpd_audit_logs", ["session_id", "created_at"])
        op.create_index("ix_lgpd_audit_user_time", "lgpd_audit_logs", ["user_id", "created_at"])

    if not _table_exists(bind, "lgpd_data_access_requests"):
        op.create_table(
            "lgpd_data_access_requests",
            sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("patient_id", sa.UUID(), nullable=False),
            sa.Column("requested_by", sa.String(length=255), nullable=True),
            sa.Column("verified", sa.Boolean(), nullable=False),
            sa.Column("request_type", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("assigned_to_id", sa.UUID(), nullable=True),
            sa.Column("response", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("evidence_url", sa.String(length=500), nullable=True),
            sa.Column("evidence_hash", sa.String(length=64), nullable=True),
            sa.Column("request_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_dsar_status_deadline", "lgpd_data_access_requests", ["status", "deadline_at"])


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "lgpd_data_access_requests"):
        op.drop_table("lgpd_data_access_requests")

    if _table_exists(bind, "lgpd_audit_logs"):
        op.drop_table("lgpd_audit_logs")

    if _table_exists(bind, "patients"):
        if not _column_exists(bind, "patients", "cpf"):
            op.add_column("patients", sa.Column("cpf", sa.String(), nullable=True))
        if not _column_exists(bind, "patients", "email"):
            op.add_column("patients", sa.Column("email", sa.String(), nullable=True))
        if not _column_exists(bind, "patients", "phone"):
            op.add_column("patients", sa.Column("phone", sa.String(), nullable=True))

        op.execute("ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_cpf_hash_doctor")
        op.execute("ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_cpf_doctor")
        op.execute("ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_email_doctor")
        op.execute("ALTER TABLE patients DROP CONSTRAINT IF EXISTS uq_patient_phone_doctor")
        op.execute(
            "ALTER TABLE patients ADD CONSTRAINT uq_patient_cpf_doctor UNIQUE (cpf, doctor_id)"
        )
        op.execute(
            "ALTER TABLE patients ADD CONSTRAINT uq_patient_email_doctor UNIQUE (email, doctor_id)"
        )
        op.execute(
            "ALTER TABLE patients ADD CONSTRAINT uq_patient_phone_doctor UNIQUE (phone, doctor_id)"
        )

        op.execute("DROP INDEX IF EXISTS ix_patients_cpf_hash_doctor")
        op.execute("DROP INDEX IF EXISTS ix_patients_email_hash_doctor")
        op.execute("DROP INDEX IF EXISTS ix_patients_phone_hash_doctor")
        op.execute("DROP INDEX IF EXISTS ix_patients_cpf_hash")
        op.execute("DROP INDEX IF EXISTS ix_patients_email_hash")
        op.execute("DROP INDEX IF EXISTS ix_patients_phone_hash")

        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_patient_cpf_doctor ON patients (cpf, doctor_id) "
            "WHERE cpf IS NOT NULL"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_patient_email_doctor ON patients (email, doctor_id) "
            "WHERE email IS NOT NULL"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_patient_phone_doctor ON patients (phone, doctor_id)"
        )
        op.execute("CREATE INDEX IF NOT EXISTS idx_patients_email ON patients (email)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_patients_phone ON patients (phone)")

        op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS cpf_encrypted")
        op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS cpf_hash")
        op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS email_encrypted")
        op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS email_hash")
        op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS phone_encrypted")
        op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS phone_hash")
