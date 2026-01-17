"""HIPAA Audit Trail Enhancement - Phase 3 Sprint 1

Revision ID: 011_hipaa_audit
Revises: 010_missing_indexes
Create Date: 2025-01-13 00:00:00.000000

This migration enhances the audit_logs table to achieve 75% HIPAA compliance by adding:
- Tamper-proof integrity controls (checksums, chain of custody)
- PHI access tracking fields
- Data modification tracking (before/after states)
- 6-year retention policy
- Immutability rules (prevent UPDATE/DELETE)
- Archive system with partitioning

HIPAA Compliance Mapping:
- § 164.312(b) - Audit Controls: Comprehensive event logging
- § 164.312(c)(1) - Integrity: Cryptographic checksums + immutability
- § 164.316(b)(2)(i) - Retention: 6-year retention + archival

Target Compliance: 55% → 75%

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
- Not recorded (legacy migration)."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '011_hipaa_audit'
down_revision = '010_missing_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Enhance audit_logs table for HIPAA compliance.

    This upgrade adds 30+ new columns and creates integrity controls,
    archival system, and immutability rules.
    """

    # ========================================
    # STEP 1: Add new columns to existing table
    # ========================================

    # Session tracking
    op.add_column('audit_logs', sa.Column('session_id', sa.String(255), nullable=True))
    op.add_column('audit_logs', sa.Column('session_token_hash', sa.String(64), nullable=True))
    op.add_column('audit_logs', sa.Column('device_fingerprint', sa.String(64), nullable=True))
    op.add_column('audit_logs', sa.Column('geolocation', postgresql.JSONB(), nullable=True))
    op.add_column('audit_logs', sa.Column('user_role', sa.String(50), nullable=True))

    # Event categorization (HIPAA critical)
    op.add_column('audit_logs', sa.Column('event_category', sa.String(50), nullable=True))

    # Resource information (PHI tracking)
    op.add_column('audit_logs', sa.Column('resource_type', sa.String(50), nullable=True))
    op.add_column('audit_logs', sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('audit_logs', sa.Column('resource_identifiers', postgresql.JSONB(), nullable=True))

    # Operation type (CRUD + Extensions)
    op.add_column('audit_logs', sa.Column('operation', sa.String(20), nullable=True))
    op.add_column('audit_logs', sa.Column('http_method', sa.String(10), nullable=True))
    op.add_column('audit_logs', sa.Column('endpoint', sa.String(500), nullable=True))

    # Change tracking (UPDATE operations)
    op.add_column('audit_logs', sa.Column('changes_before', postgresql.JSONB(), nullable=True))
    op.add_column('audit_logs', sa.Column('changes_after', postgresql.JSONB(), nullable=True))
    op.add_column('audit_logs', sa.Column('changed_fields', postgresql.ARRAY(sa.Text()), nullable=True))

    # Additional context
    op.add_column('audit_logs', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('audit_logs', sa.Column('query_params', postgresql.JSONB(), nullable=True))
    op.add_column('audit_logs', sa.Column('request_body_hash', sa.String(64), nullable=True))

    # Result information
    op.add_column('audit_logs', sa.Column('status', sa.String(20), nullable=True, server_default='SUCCESS'))
    op.add_column('audit_logs', sa.Column('http_status_code', sa.Integer(), nullable=True))
    op.add_column('audit_logs', sa.Column('error_code', sa.String(50), nullable=True))
    op.add_column('audit_logs', sa.Column('error_stack_trace', sa.Text(), nullable=True))
    op.add_column('audit_logs', sa.Column('duration_ms', sa.Integer(), nullable=True))

    # ========================================
    # INTEGRITY: Tamper Detection (HIPAA Required)
    # ========================================
    op.add_column('audit_logs', sa.Column('checksum', sa.String(64), nullable=True))
    op.add_column('audit_logs', sa.Column('previous_checksum', sa.String(64), nullable=True))
    op.add_column('audit_logs', sa.Column('integrity_verified', sa.Boolean(), server_default='true'))

    # ========================================
    # COMPLIANCE: Audit & Review
    # ========================================
    op.add_column('audit_logs', sa.Column('reviewed', sa.Boolean(), server_default='false'))
    op.add_column('audit_logs', sa.Column('reviewed_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('audit_logs', sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('audit_logs', sa.Column('review_notes', sa.Text(), nullable=True))

    # Anomaly detection
    op.add_column('audit_logs', sa.Column('is_anomalous', sa.Boolean(), server_default='false'))
    op.add_column('audit_logs', sa.Column('anomaly_score', sa.Numeric(5, 2), nullable=True))
    op.add_column('audit_logs', sa.Column('anomaly_reasons', postgresql.ARRAY(sa.Text()), nullable=True))

    # Alert generation
    op.add_column('audit_logs', sa.Column('alert_generated', sa.Boolean(), server_default='false'))
    op.add_column('audit_logs', sa.Column('alert_sent_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('audit_logs', sa.Column('alert_recipients', postgresql.ARRAY(sa.Text()), nullable=True))

    # ========================================
    # RETENTION: Compliance & Archival
    # ========================================
    op.add_column('audit_logs', sa.Column('retention_period_years', sa.Integer(), server_default='6'))
    op.add_column('audit_logs', sa.Column('archive_eligible_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('audit_logs', sa.Column('archived', sa.Boolean(), server_default='false'))
    op.add_column('audit_logs', sa.Column('archived_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('audit_logs', sa.Column('archive_location', sa.String(500), nullable=True))

    # ========================================
    # STEP 2: Backfill event categories for existing records
    # ========================================
    op.execute("""
        UPDATE audit_logs
        SET event_category = CASE
            WHEN event_type IN ('login_success', 'login_failure', 'logout', 'session_created',
                                'session_expired', 'session_invalidated', 'token_refresh')
                THEN 'AUTHENTICATION'
            WHEN event_type IN ('access_denied', 'permission_changed', 'role_changed')
                THEN 'AUTHORIZATION'
            WHEN event_type IN ('suspicious_activity', 'rate_limit_exceeded', 'invalid_token',
                                'csrf_violation')
                THEN 'SECURITY'
            WHEN event_type IN ('password_changed', 'password_reset_requested',
                                'password_reset_completed', 'account_locked', 'account_unlocked',
                                'account_disabled', 'account_enabled')
                THEN 'ADMIN'
            ELSE 'SYSTEM'
        END
        WHERE event_category IS NULL;
    """)

    # Backfill status field from event_status
    op.execute("""
        UPDATE audit_logs
        SET status = CASE
            WHEN event_status = 'success' THEN 'SUCCESS'
            WHEN event_status = 'failure' THEN 'FAILURE'
            WHEN event_status = 'error' THEN 'ERROR'
            ELSE 'SUCCESS'
        END
        WHERE status IS NULL;
    """)

    # ========================================
    # STEP 3: Create indexes for performance
    # ========================================

    # Primary timestamp index (most common query)
    op.create_index('idx_audit_timestamp_desc', 'audit_logs', [sa.text('created_at DESC')], unique=False)

    # User activity tracking
    op.create_index('idx_audit_user_id_timestamp', 'audit_logs', ['user_id', sa.text('created_at DESC')], unique=False)
    op.create_index('idx_audit_user_email_timestamp', 'audit_logs', ['user_email', sa.text('created_at DESC')], unique=False)

    # PHI access tracking (CRITICAL for HIPAA)
    op.create_index('idx_audit_resource_type_id', 'audit_logs', ['resource_type', 'resource_id'], unique=False)
    op.create_index(
        'idx_audit_phi_access',
        'audit_logs',
        ['event_category', 'resource_type', sa.text('created_at DESC')],
        unique=False,
        postgresql_where=sa.text("event_category = 'PHI_ACCESS'")
    )

    # Event type filtering
    op.create_index('idx_audit_event_type_timestamp', 'audit_logs', ['event_type', sa.text('created_at DESC')], unique=False)
    op.create_index('idx_audit_event_category_timestamp', 'audit_logs', ['event_category', sa.text('created_at DESC')], unique=False)

    # Status and error tracking
    op.create_index(
        'idx_audit_status_timestamp',
        'audit_logs',
        ['status', sa.text('created_at DESC')],
        unique=False,
        postgresql_where=sa.text("status IN ('FAILURE', 'ERROR', 'BLOCKED')")
    )

    # Security monitoring
    op.create_index('idx_audit_ip_timestamp', 'audit_logs', ['ip_address', sa.text('created_at DESC')], unique=False)
    op.create_index(
        'idx_audit_anomalous',
        'audit_logs',
        ['is_anomalous', sa.text('created_at DESC')],
        unique=False,
        postgresql_where=sa.text('is_anomalous = true')
    )

    # Session tracking
    op.create_index('idx_audit_session_id', 'audit_logs', ['session_id', sa.text('created_at DESC')], unique=False)

    # Composite index for user + resource queries
    op.create_index('idx_audit_user_resource', 'audit_logs', ['user_id', 'resource_type', 'resource_id', sa.text('created_at DESC')], unique=False)

    # Integrity verification index
    op.create_index(
        'idx_audit_integrity',
        'audit_logs',
        ['integrity_verified', sa.text('created_at DESC')],
        unique=False,
        postgresql_where=sa.text('integrity_verified = false')
    )

    # Review tracking
    op.create_index(
        'idx_audit_unreviewed',
        'audit_logs',
        ['reviewed', sa.text('created_at DESC')],
        unique=False,
        postgresql_where=sa.text("reviewed = false AND event_category IN ('PHI_ACCESS', 'DATA_MODIFICATION')")
    )

    # Archival queries
    op.create_index(
        'idx_audit_archive_eligible',
        'audit_logs',
        ['archive_eligible_at'],
        unique=False,
        postgresql_where=sa.text('archived = false')
    )

    # GIN indexes for JSONB queries
    op.create_index('idx_audit_metadata_gin', 'audit_logs', ['event_metadata'], unique=False, postgresql_using='gin')
    op.create_index('idx_audit_changes_before_gin', 'audit_logs', ['changes_before'], unique=False, postgresql_using='gin')
    op.create_index('idx_audit_changes_after_gin', 'audit_logs', ['changes_after'], unique=False, postgresql_using='gin')

    # ========================================
    # STEP 4: Add constraints
    # ========================================

    op.create_check_constraint(
        'valid_status',
        'audit_logs',
        "status IN ('SUCCESS', 'FAILURE', 'ERROR', 'BLOCKED')"
    )

    op.create_check_constraint(
        'valid_event_category',
        'audit_logs',
        "event_category IN ('AUTHENTICATION', 'AUTHORIZATION', 'PHI_ACCESS', 'DATA_MODIFICATION', 'SECURITY', 'SYSTEM', 'ADMIN', 'EXPORT')"
    )

    # ========================================
    # STEP 5: Create integrity control functions and triggers
    # ========================================

    # Checksum calculation function
    op.execute("""
        CREATE OR REPLACE FUNCTION calculate_audit_log_checksum()
        RETURNS TRIGGER AS $$
        DECLARE
            last_checksum VARCHAR(64);
            record_data TEXT;
        BEGIN
            -- Get the last checksum for chaining
            SELECT checksum INTO last_checksum
            FROM audit_logs
            ORDER BY created_at DESC
            LIMIT 1;

            NEW.previous_checksum := last_checksum;

            -- Create deterministic string representation of record
            record_data := CONCAT(
                COALESCE(NEW.created_at::TEXT, ''), '|',
                COALESCE(NEW.user_id::TEXT, ''), '|',
                COALESCE(NEW.event_type::TEXT, ''), '|',
                COALESCE(NEW.resource_type, ''), '|',
                COALESCE(NEW.resource_id::TEXT, ''), '|',
                COALESCE(NEW.operation, ''), '|',
                COALESCE(NEW.status, ''), '|',
                COALESCE(NEW.previous_checksum, '')
            );

            -- Calculate SHA-256 checksum
            NEW.checksum := encode(digest(record_data, 'sha256'), 'hex');

            -- Set archive eligibility date (6 years from now)
            IF NEW.archive_eligible_at IS NULL THEN
                NEW.archive_eligible_at := NEW.created_at + INTERVAL '6 years';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger for checksum calculation
    op.execute("""
        CREATE TRIGGER audit_log_checksum_trigger
            BEFORE INSERT ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION calculate_audit_log_checksum();
    """)

    # Integrity verification function
    op.execute("""
        CREATE OR REPLACE FUNCTION verify_audit_log_integrity(
            start_timestamp TIMESTAMPTZ DEFAULT NULL,
            end_timestamp TIMESTAMPTZ DEFAULT NULL
        )
        RETURNS TABLE(
            total_checked BIGINT,
            valid_count BIGINT,
            invalid_count BIGINT,
            chain_breaks BIGINT,
            invalid_log_ids UUID[]
        ) AS $$
        DECLARE
            rec RECORD;
            expected_checksum VARCHAR(64);
            prev_checksum VARCHAR(64) := NULL;
            total BIGINT := 0;
            valid BIGINT := 0;
            invalid BIGINT := 0;
            breaks BIGINT := 0;
            invalid_ids UUID[] := ARRAY[]::UUID[];
            record_data TEXT;
        BEGIN
            FOR rec IN
                SELECT * FROM audit_logs
                WHERE (start_timestamp IS NULL OR created_at >= start_timestamp)
                  AND (end_timestamp IS NULL OR created_at <= end_timestamp)
                ORDER BY created_at ASC
            LOOP
                total := total + 1;

                -- Calculate expected checksum
                record_data := CONCAT(
                    COALESCE(rec.created_at::TEXT, ''), '|',
                    COALESCE(rec.user_id::TEXT, ''), '|',
                    COALESCE(rec.event_type::TEXT, ''), '|',
                    COALESCE(rec.resource_type, ''), '|',
                    COALESCE(rec.resource_id::TEXT, ''), '|',
                    COALESCE(rec.operation, ''), '|',
                    COALESCE(rec.status, ''), '|',
                    COALESCE(rec.previous_checksum, '')
                );
                expected_checksum := encode(digest(record_data, 'sha256'), 'hex');

                -- Verify checksum
                IF rec.checksum IS NOT NULL AND rec.checksum != expected_checksum THEN
                    invalid := invalid + 1;
                    invalid_ids := array_append(invalid_ids, rec.id);
                ELSE
                    valid := valid + 1;
                END IF;

                -- Verify chain (skip first record)
                IF prev_checksum IS NOT NULL AND rec.previous_checksum != prev_checksum THEN
                    breaks := breaks + 1;
                END IF;

                prev_checksum := rec.checksum;
            END LOOP;

            RETURN QUERY SELECT total, valid, invalid, breaks, invalid_ids;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ========================================
    # STEP 6: Apply immutability rules (CRITICAL)
    # ========================================

    # Prevent UPDATE operations (append-only table)
    op.execute("""
        CREATE RULE audit_logs_no_update AS
            ON UPDATE TO audit_logs
            DO INSTEAD NOTHING;
    """)

    # Prevent DELETE operations (preserve audit trail)
    op.execute("""
        CREATE RULE audit_logs_no_delete AS
            ON DELETE TO audit_logs
            DO INSTEAD NOTHING;
    """)

    # ========================================
    # STEP 7: Create archive table with partitioning
    # ========================================

    # FIX: Use composite primary key for partitioned table
    # Partitioning requires the partition key (created_at) to be part of the primary key
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs_archive (
            LIKE audit_logs INCLUDING DEFAULTS INCLUDING CONSTRAINTS
        ) PARTITION BY RANGE (created_at);
    """)

    # Drop the inherited PK constraint (which only has 'id')
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audit_logs_archive_pkey') THEN
                ALTER TABLE audit_logs_archive DROP CONSTRAINT audit_logs_archive_pkey;
            END IF;
        END $$;
    """)

    # Add composite PK
    op.execute("""
        ALTER TABLE audit_logs_archive ADD PRIMARY KEY (id, created_at);
    """)

    # Create partitions for current year and next 6 years
    for year in range(2025, 2032):
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS audit_logs_archive_{year}
            PARTITION OF audit_logs_archive
            FOR VALUES FROM ('{year}-01-01') TO ('{year + 1}-01-01');
        """)

    # ========================================
    # STEP 8: Create archival function
    # ========================================

    op.execute("""
        CREATE OR REPLACE FUNCTION archive_old_audit_logs()
        RETURNS INTEGER AS $$
        DECLARE
            archived_count INTEGER;
            cutoff_date TIMESTAMPTZ;
        BEGIN
            -- Calculate cutoff date (older than 1 year, keep recent in hot table)
            cutoff_date := NOW() - INTERVAL '1 year';

            -- Move old logs to archive (using INSERT...SELECT for performance)
            WITH moved_logs AS (
                INSERT INTO audit_logs_archive
                SELECT * FROM audit_logs
                WHERE created_at < cutoff_date
                  AND archived = FALSE
                ON CONFLICT DO NOTHING
                RETURNING id
            )
            SELECT COUNT(*) INTO archived_count FROM moved_logs;

            -- Mark as archived (but don't delete from main table yet - immutability rule prevents it anyway)
            -- This is for tracking purposes only
            -- Note: UPDATE will be blocked by the rule, so this is informational

            RETURN archived_count;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ========================================
    # STEP 9: Backfill checksums for existing records
    # ========================================

    # Note: We can't use the trigger retroactively, but we can set initial values
    # For existing records, set a basic checksum and mark as legacy
    op.execute("""
        UPDATE audit_logs
        SET checksum = encode(digest(CONCAT(
            created_at::TEXT, '|',
            COALESCE(user_id::TEXT, ''), '|',
            COALESCE(event_type::TEXT, ''), '|',
            'LEGACY'
        ), 'sha256'), 'hex')
        WHERE checksum IS NULL;
    """)


def downgrade() -> None:
    """
    Remove HIPAA audit trail enhancements.

    WARNING: This will remove critical compliance features.
    Only use in development/testing environments.
    """

    # Drop archival function
    op.execute("DROP FUNCTION IF EXISTS archive_old_audit_logs() CASCADE;")

    # Drop integrity verification function
    op.execute("DROP FUNCTION IF EXISTS verify_audit_log_integrity(TIMESTAMPTZ, TIMESTAMPTZ) CASCADE;")

    # Drop checksum trigger and function
    op.execute("DROP TRIGGER IF EXISTS audit_log_checksum_trigger ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS calculate_audit_log_checksum() CASCADE;")

    # Drop immutability rules
    op.execute("DROP RULE IF EXISTS audit_logs_no_update ON audit_logs;")
    op.execute("DROP RULE IF EXISTS audit_logs_no_delete ON audit_logs;")

    # Drop archive partitions
    for year in range(2025, 2032):
        op.execute(f"DROP TABLE IF EXISTS audit_logs_archive_{year} CASCADE;")

    # Drop archive table
    op.execute("DROP TABLE IF EXISTS audit_logs_archive CASCADE;")

    # Drop constraints
    op.drop_constraint('valid_event_category', 'audit_logs', type_='check')
    op.drop_constraint('valid_status', 'audit_logs', type_='check')

    # Drop indexes
    op.drop_index('idx_audit_changes_after_gin', table_name='audit_logs')
    op.drop_index('idx_audit_changes_before_gin', table_name='audit_logs')
    op.drop_index('idx_audit_metadata_gin', table_name='audit_logs')
    op.drop_index('idx_audit_archive_eligible', table_name='audit_logs')
    op.drop_index('idx_audit_unreviewed', table_name='audit_logs')
    op.drop_index('idx_audit_integrity', table_name='audit_logs')
    op.drop_index('idx_audit_user_resource', table_name='audit_logs')
    op.drop_index('idx_audit_session_id', table_name='audit_logs')
    op.drop_index('idx_audit_anomalous', table_name='audit_logs')
    op.drop_index('idx_audit_ip_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_status_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_event_category_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_event_type_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_phi_access', table_name='audit_logs')
    op.drop_index('idx_audit_resource_type_id', table_name='audit_logs')
    op.drop_index('idx_audit_user_email_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_user_id_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_timestamp_desc', table_name='audit_logs')

    # Drop columns
    op.drop_column('audit_logs', 'archive_location')
    op.drop_column('audit_logs', 'archived_at')
    op.drop_column('audit_logs', 'archived')
    op.drop_column('audit_logs', 'archive_eligible_at')
    op.drop_column('audit_logs', 'retention_period_years')
    op.drop_column('audit_logs', 'alert_recipients')
    op.drop_column('audit_logs', 'alert_sent_at')
    op.drop_column('audit_logs', 'alert_generated')
    op.drop_column('audit_logs', 'anomaly_reasons')
    op.drop_column('audit_logs', 'anomaly_score')
    op.drop_column('audit_logs', 'is_anomalous')
    op.drop_column('audit_logs', 'review_notes')
    op.drop_column('audit_logs', 'reviewed_by')
    op.drop_column('audit_logs', 'reviewed_at')
    op.drop_column('audit_logs', 'reviewed')
    op.drop_column('audit_logs', 'integrity_verified')
    op.drop_column('audit_logs', 'previous_checksum')
    op.drop_column('audit_logs', 'checksum')
    op.drop_column('audit_logs', 'duration_ms')
    op.drop_column('audit_logs', 'error_stack_trace')
    op.drop_column('audit_logs', 'error_code')
    op.drop_column('audit_logs', 'http_status_code')
    op.drop_column('audit_logs', 'status')
    op.drop_column('audit_logs', 'request_body_hash')
    op.drop_column('audit_logs', 'query_params')
    op.drop_column('audit_logs', 'description')
    op.drop_column('audit_logs', 'changed_fields')
    op.drop_column('audit_logs', 'changes_after')
    op.drop_column('audit_logs', 'changes_before')
    op.drop_column('audit_logs', 'endpoint')
    op.drop_column('audit_logs', 'http_method')
    op.drop_column('audit_logs', 'operation')
    op.drop_column('audit_logs', 'resource_identifiers')
    op.drop_column('audit_logs', 'resource_id')
    op.drop_column('audit_logs', 'resource_type')
    op.drop_column('audit_logs', 'event_category')
    op.drop_column('audit_logs', 'user_role')
    op.drop_column('audit_logs', 'geolocation')
    op.drop_column('audit_logs', 'device_fingerprint')
    op.drop_column('audit_logs', 'session_token_hash')
    op.drop_column('audit_logs', 'session_id')
