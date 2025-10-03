"""Add full-text search indexes for patient and message content

Revision ID: 039_fulltext_search
Revises: 038_jsonb_indexes
Create Date: 2025-09-29 21:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '039_fulltext_search'
down_revision = '038_jsonb_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add full-text search (FTS) capabilities using PostgreSQL's tsvector.
    Enables fast text searches across patient names, diagnoses, and message content.
    """

    # Install Portuguese language support for better medical term matching
    op.execute("""
        CREATE EXTENSION IF NOT EXISTS unaccent;
    """)

    # Create text search configuration for Portuguese medical content
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_ts_config WHERE cfgname = 'portuguese_medical'
            ) THEN
                CREATE TEXT SEARCH CONFIGURATION portuguese_medical (COPY = portuguese);
                -- Add medical term handling
                ALTER TEXT SEARCH CONFIGURATION portuguese_medical
                    ALTER MAPPING FOR asciiword, asciihword, hword_asciipart, word, hword, hword_part
                    WITH unaccent, portuguese_stem;
            END IF;
        END $$;
    """)

    # Add tsvector columns for full-text search
    op.execute("""
        -- Patients full-text search column
        ALTER TABLE patients
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('portuguese_medical', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('portuguese_medical', coalesce(diagnosis, '')), 'B') ||
            setweight(to_tsvector('portuguese_medical', coalesce(treatment_type, '')), 'C') ||
            setweight(to_tsvector('portuguese_medical', coalesce(doctor_notes, '')), 'D')
        ) STORED;
    """)

    op.execute("""
        -- Messages full-text search column
        ALTER TABLE messages
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('portuguese_medical', coalesce(content, ''))
        ) STORED;
    """)

    op.execute("""
        -- Quiz responses full-text search column
        ALTER TABLE quiz_responses
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('portuguese_medical', coalesce(question_text, '')), 'A') ||
            setweight(to_tsvector('portuguese_medical', coalesce(response_value, '')), 'B') ||
            setweight(to_tsvector('portuguese_medical', coalesce(other_text, '')), 'C')
        ) STORED;
    """)

    op.execute("""
        -- Medical reports full-text search column
        ALTER TABLE medical_reports
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('portuguese_medical', coalesce(summary, ''))
        ) STORED;
    """)

    op.execute("""
        -- Alerts full-text search column
        ALTER TABLE alerts
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('portuguese_medical', coalesce(alert_type, '')), 'A') ||
            setweight(to_tsvector('portuguese_medical', coalesce(description, '')), 'B')
        ) STORED;
    """)

    # Create GIN indexes on tsvector columns for fast full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patients_search_vector
        ON patients USING GIN (search_vector);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_search_vector
        ON messages USING GIN (search_vector);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_quiz_responses_search_vector
        ON quiz_responses USING GIN (search_vector);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_medical_reports_search_vector
        ON medical_reports USING GIN (search_vector);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_search_vector
        ON alerts USING GIN (search_vector);
    """)

    # Create trigram indexes for fuzzy name matching (typo tolerance)
    op.execute("""
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patients_name_trgm
        ON patients USING GIN (name gin_trgm_ops);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_patients_phone_trgm
        ON patients USING GIN (phone gin_trgm_ops);
    """)

    # Create helper functions for full-text search
    op.execute("""
        CREATE OR REPLACE FUNCTION search_patients(search_query text)
        RETURNS TABLE (
            patient_id uuid,
            patient_name text,
            diagnosis text,
            relevance real
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                p.id,
                p.name,
                p.diagnosis,
                ts_rank(p.search_vector, plainto_tsquery('portuguese_medical', search_query)) as relevance
            FROM patients p
            WHERE p.search_vector @@ plainto_tsquery('portuguese_medical', search_query)
            ORDER BY relevance DESC, p.name;
        END;
        $$ LANGUAGE plpgsql;

        COMMENT ON FUNCTION search_patients(text) IS
        'Full-text search across patient names, diagnoses, and treatment notes';
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION search_messages(search_query text, patient_filter uuid DEFAULT NULL)
        RETURNS TABLE (
            message_id uuid,
            patient_id uuid,
            content text,
            direction text,
            created_at timestamptz,
            relevance real
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                m.id,
                m.patient_id,
                m.content,
                m.direction::text,
                m.created_at,
                ts_rank(m.search_vector, plainto_tsquery('portuguese_medical', search_query)) as relevance
            FROM messages m
            WHERE
                m.search_vector @@ plainto_tsquery('portuguese_medical', search_query)
                AND (patient_filter IS NULL OR m.patient_id = patient_filter)
            ORDER BY relevance DESC, m.created_at DESC;
        END;
        $$ LANGUAGE plpgsql;

        COMMENT ON FUNCTION search_messages(text, uuid) IS
        'Full-text search across message content with optional patient filter';
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION fuzzy_search_patient_name(name_query text, similarity_threshold real DEFAULT 0.3)
        RETURNS TABLE (
            patient_id uuid,
            patient_name text,
            phone text,
            similarity real
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                p.id,
                p.name,
                p.phone,
                similarity(p.name, name_query) as sim
            FROM patients p
            WHERE similarity(p.name, name_query) > similarity_threshold
            ORDER BY sim DESC, p.name
            LIMIT 20;
        END;
        $$ LANGUAGE plpgsql;

        COMMENT ON FUNCTION fuzzy_search_patient_name(text, real) IS
        'Fuzzy name matching for patients with typo tolerance using trigrams';
    """)

    # Add documentation comments
    op.execute("""
        COMMENT ON COLUMN patients.search_vector IS
        'Full-text search vector for patient name, diagnosis, treatment, and notes';
    """)

    op.execute("""
        COMMENT ON COLUMN messages.search_vector IS
        'Full-text search vector for message content';
    """)


def downgrade():
    """
    Drop full-text search indexes and helper functions.
    """
    # Drop helper functions
    op.execute("DROP FUNCTION IF EXISTS fuzzy_search_patient_name(text, real);")
    op.execute("DROP FUNCTION IF EXISTS search_messages(text, uuid);")
    op.execute("DROP FUNCTION IF EXISTS search_patients(text);")

    # Drop trigram indexes
    op.execute("DROP INDEX IF EXISTS idx_patients_phone_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_patients_name_trgm;")

    # Drop full-text search indexes
    op.execute("DROP INDEX IF EXISTS idx_alerts_search_vector;")
    op.execute("DROP INDEX IF EXISTS idx_medical_reports_search_vector;")
    op.execute("DROP INDEX IF EXISTS idx_quiz_responses_search_vector;")
    op.execute("DROP INDEX IF EXISTS idx_messages_search_vector;")
    op.execute("DROP INDEX IF EXISTS idx_patients_search_vector;")

    # Drop tsvector columns
    op.execute("ALTER TABLE alerts DROP COLUMN IF EXISTS search_vector;")
    op.execute("ALTER TABLE medical_reports DROP COLUMN IF EXISTS search_vector;")
    op.execute("ALTER TABLE quiz_responses DROP COLUMN IF EXISTS search_vector;")
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS search_vector;")
    op.execute("ALTER TABLE patients DROP COLUMN IF EXISTS search_vector;")

    # Drop text search configuration
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS portuguese_medical;")

    # Note: Extensions are NOT dropped in downgrade as they may be used by other features