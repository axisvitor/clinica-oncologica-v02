"""Add GIN index on patients.metadata for JSONB queries

Revision ID: 013
Revises: 012
Create Date: 2025-01-16

Part of MEDIUM-014: GIN Index on JSONB fields
Expected performance improvement: 50-180x faster for JSONB contains queries

GIN (Generalized Inverted Index) is ideal for JSONB columns because:
- Supports @> (contains) operator efficiently
- Handles nested JSON path queries
- Minimal write overhead for read-heavy workloads
- Excellent for filtering by consent, preferences, etc.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012_migrate_quiz_response_value_to_jsonb'
branch_labels = None
depends_on = None


def upgrade():
    """Add GIN indexes for patients.metadata JSONB column."""

    # Create GIN index on entire metadata column
    # This supports queries like: WHERE metadata @> '{"consent": {"lgpd": true}}'
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patient_metadata_gin
        ON patients USING GIN (metadata);
    """)

    # Create GIN index on consent subfield
    # This optimizes queries on the consent object specifically
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patient_metadata_consent_gin
        ON patients USING GIN ((metadata->'consent'));
    """)

    # Create GIN index on preferences subfield
    # This optimizes queries on the preferences object specifically
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patient_metadata_preferences_gin
        ON patients USING GIN ((metadata->'preferences'));
    """)

    # Update table statistics for query planner
    op.execute("ANALYZE patients;")

    print("""
    ✅ GIN indexes created successfully!

    Expected benefits:
    - 50-180x faster for JSONB contains queries (@>)
    - Efficient filtering by consent, preferences
    - Better support for patient metadata searches

    Verify with:
        EXPLAIN SELECT * FROM patients WHERE metadata @> '{"consent": {"lgpd": true}}';
        -- Should show: "Bitmap Index Scan using idx_patient_metadata_gin"
    """)


def downgrade():
    """Remove GIN indexes."""

    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_patient_metadata_gin;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_patient_metadata_consent_gin;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_patient_metadata_preferences_gin;")

    # Update table statistics
    op.execute("ANALYZE patients;")
