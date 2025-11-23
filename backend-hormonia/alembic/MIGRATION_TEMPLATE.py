"""[Brief description of what this migration does]

Revision ID: [XXX_descriptive_name]
Revises: [previous_migration_id]
Create Date: [YYYY-MM-DD HH:MM:SS]

================================================================================
MIGRATION DOCUMENTATION TEMPLATE
================================================================================

📋 **REQUIRED SECTIONS** - Fill out ALL sections below before committing!

================================================================================
WHY: [Business justification]
================================================================================
Explain the business reason for this migration:
- What problem does this solve?
- What feature does this enable?
- What performance issue does this address?

Example:
  "Patient metadata queries are slow (~450ms) due to sequential scan on
   VARCHAR column. Need structured JSONB storage for complex queries."

================================================================================
WHAT: [Technical changes]
================================================================================
Describe the technical changes being made:
- Schema changes (ADD COLUMN, CREATE INDEX, ALTER TABLE, etc.)
- Data transformations (if any)
- Index creations
- Constraint additions

Example:
  "Add GIN index to patients.metadata_jsonb column to enable fast JSONB
   containment queries (@> operator). Converts VARCHAR to JSONB format."

================================================================================
IMPACT: [Performance and data impact]
================================================================================
Quantify the expected impact:
- Performance improvements (before/after metrics)
- Execution time estimate
- Data volume affected
- Table lock duration (if any)

Example:
  "Expected impact:
   - Query performance: 450ms → 5.2ms (87x speedup)
   - Migration duration: ~10 minutes for 250k rows
   - No table lock (uses CONCURRENTLY)
   - Affects ~250k patient records"

================================================================================
BENCHMARK: [Test results]
================================================================================
Document testing performed:
- Dataset size used for testing
- Actual execution times
- Before/after query plans
- Production data dump testing

Example:
  "Tested with 100k patient records:
   - Index creation: 42 seconds
   - Data backfill: 8 minutes (batched, 1000 rows/batch)
   - Tested on production data dump (500k rows): 18 minutes total"

================================================================================
ROLLBACK: [Rollback safety]
================================================================================
Describe the rollback safety:
- Is rollback safe?
- Will data be lost on rollback?
- Are there any dependencies?
- What happens to existing data?

Example:
  "Safe - drops index only, no data impact. JSONB data remains intact.
   Can recreate index anytime with no data loss."

OR:

  "⚠️  DESTRUCTIVE - Reverting JSONB to VARCHAR will lose nested structure.
   Backup recommended before downgrade."

================================================================================
RELATED: [Cross-references]
================================================================================
Link to related items:
- Related migrations (if part of multi-step process)
- GitHub issues/PRs
- Documentation
- JIRA tickets

Example:
  "Related issues: MEDIUM-014, P0-DATABASE-OPTIMIZATION
   Prerequisites: Migration 012 (JSONB column must exist)
   Follow-up: Migration 018 (drop old VARCHAR column)
   References:
   - PostgreSQL GIN indexes: https://www.postgresql.org/docs/current/gin.html
   - JSONB indexing guide: https://www.postgresql.org/docs/current/datatype-json.html#JSON-INDEXING"

================================================================================
MIGRATION TYPE: [Select one]
================================================================================
Choose the appropriate migration type:

[ ] Schema-Only (DDL changes, no data transformation)
    - Example: ADD COLUMN, CREATE INDEX, ADD CONSTRAINT

[ ] Data Transformation (schema + data backfill)
    - Example: VARCHAR → JSONB, split column, merge columns

[ ] Zero-Downtime Multi-Step (requires 2+ migrations)
    - Example: Adding NOT NULL constraint
    - Step 1: Add nullable column
    - Step 2: Backfill values
    - Step 3: Add NOT NULL constraint

[ ] Emergency (production hotfix, < 5 second execution)
    - Example: Add index for slow query
    - Requires immediate deployment

================================================================================
DEPLOYMENT CHECKLIST
================================================================================

PRE-DEPLOYMENT:
[ ] Migration tested on production data dump
[ ] Performance benchmarked on realistic dataset (run: ./scripts/benchmark_migration.py)
[ ] Downgrade tested and verified
[ ] No table locks on large tables (> 100k rows)
[ ] Estimated duration documented (< 5 minutes preferred)
[ ] Rollback plan documented
[ ] Monitoring alerts configured
[ ] Team notified of deployment window
[ ] Backup created before deployment

POST-DEPLOYMENT:
[ ] Migration completed successfully
[ ] No errors in application logs
[ ] Database performance metrics normal
[ ] All indexes created successfully
[ ] Foreign key constraints validated
[ ] Application functionality verified
[ ] Rollback tested in staging

================================================================================
EXAMPLE MIGRATIONS
================================================================================

See examples in docs/database/DATA_MIGRATION_STRATEGY.md:
- Schema-Only: Adding nullable column
- Data Transformation: VARCHAR to JSONB migration
- Zero-Downtime: Adding NOT NULL constraint (3-step)
- Emergency: Fast index creation

================================================================================
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # If using PostgreSQL-specific types

# revision identifiers, used by Alembic.
revision = '[XXX_descriptive_name]'
down_revision = '[previous_migration_id]'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Apply migration changes.

    IMPLEMENTATION GUIDELINES:
    1. Add detailed comments for each step
    2. Use CONCURRENTLY for indexes on large tables
    3. Batch large data transformations (1000-5000 rows/batch)
    4. Print progress for long-running operations
    5. Validate prerequisites before making changes
    """

    # Example: Adding indexed JSONB column
    # Uncomment and adapt to your needs

    # # Step 1: Add new column
    # print("Step 1/3: Adding new column...")
    # op.add_column(
    #     'table_name',
    #     sa.Column(
    #         'column_name',
    #         postgresql.JSONB(astext_type=sa.Text()),
    #         nullable=True,
    #         comment='Description of what this column stores'
    #     )
    # )
    #
    # # Step 2: Backfill data (if needed)
    # print("Step 2/3: Backfilling data...")
    # connection = op.get_bind()
    # batch_size = 1000
    # total_updated = 0
    #
    # while True:
    #     result = connection.execute(sa.text("""
    #         UPDATE table_name
    #         SET column_name = '{"key": "value"}'::jsonb
    #         WHERE id IN (
    #             SELECT id FROM table_name
    #             WHERE column_name IS NULL
    #             LIMIT :batch_size
    #         )
    #         RETURNING id
    #     """), {"batch_size": batch_size})
    #
    #     updated_count = result.rowcount
    #     total_updated += updated_count
    #
    #     if updated_count == 0:
    #         break
    #
    #     if (total_updated // batch_size) % 10 == 0:
    #         print(f"  Processed {total_updated:,} rows")
    #
    # print(f"Step 2/3: Backfill complete. {total_updated:,} rows processed")
    #
    # # Step 3: Create index (CONCURRENTLY to avoid table lock)
    # print("Step 3/3: Creating index...")
    # op.execute(
    #     "CREATE INDEX CONCURRENTLY idx_table_column_gin "
    #     "ON table_name USING GIN (column_name)"
    # )
    # print("Step 3/3: Index created successfully")

    pass  # Replace with actual migration code


def downgrade() -> None:
    """
    Revert migration changes.

    IMPORTANT:
    - Always implement downgrade (even if data is lost)
    - Document any data loss in ROLLBACK section above
    - Test downgrade path before deploying
    - Reverse operations in opposite order of upgrade
    """

    # Example: Removing column and index
    # Uncomment and adapt to your needs

    # # Drop index first
    # op.drop_index('idx_table_column_gin', table_name='table_name')
    #
    # # Drop column
    # op.drop_column('table_name', 'column_name')

    pass  # Replace with actual downgrade code


# ============================================================================
# HELPER FUNCTIONS (optional)
# ============================================================================

def _validate_prerequisites(connection) -> bool:
    """
    Validate prerequisites before running migration.

    Returns:
        True if all prerequisites are met, False otherwise

    Example:
        # Check if prerequisite migration was run
        result = connection.execute(sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'table' AND column_name = 'column'"
        ))
        if result.scalar() == 0:
            raise Exception("Prerequisite migration 012 not run. Deploy 012 first.")
    """
    return True


def _check_for_nulls(connection, table: str, column: str) -> int:
    """
    Check for NULL values before adding NOT NULL constraint.

    Args:
        connection: Database connection
        table: Table name
        column: Column name

    Returns:
        Count of NULL values

    Example:
        null_count = _check_for_nulls(connection, 'users', 'email_verified')
        if null_count > 0:
            raise Exception(f"Cannot add NOT NULL: {null_count} rows have NULL values")
    """
    result = connection.execute(sa.text(
        f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL"
    ))
    return result.scalar()


# ============================================================================
# TESTING COMMANDS (run before committing)
# ============================================================================
"""
1. Test upgrade:
   $ alembic upgrade head

2. Test downgrade:
   $ alembic downgrade -1

3. Test on production data dump:
   $ ./scripts/test_migration_prod_dump.sh [migration_id]

4. Benchmark performance:
   $ python scripts/benchmark_migration.py [migration_id]

5. Verify no table locks:
   $ EXPLAIN (ANALYZE, BUFFERS) [your queries]
   # Should show "Index Scan" or "Bitmap Index Scan", NOT "Seq Scan"
"""
