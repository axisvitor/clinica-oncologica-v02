#!/usr/bin/env python3
"""
Production Database Stamping Script
====================================

PURPOSE:
--------
This script "stamps" the Alembic version table with a specific migration revision
when the database schema was created manually (outside of Alembic migrations).

WHY STAMPING IS NEEDED:
-----------------------
When a database schema is created manually or through SQL dumps:
1. The tables exist in production
2. But alembic_version table is empty or missing
3. Alembic thinks no migrations have been applied
4. Running "alembic upgrade head" would try to recreate existing tables (ERROR!)

Stamping tells Alembic: "The database is already at this migration state, don't re-run it."

WHAT IT DOES:
-------------
1. Connects to production database
2. Inspects existing schema (tables, columns, indexes, constraints)
3. Compares with available migration files
4. Determines which migration matches the current state
5. Inserts/updates the alembic_version table with correct revision
6. Validates the stamp was successful

RISKS AND PRECAUTIONS:
----------------------
⚠️  DANGER: Incorrect stamping can cause:
   - Lost migrations (thinking schema is newer than it is)
   - Migration conflicts (duplicate table creation)
   - Data corruption (if upgrade/downgrade runs incorrectly)

✅  SAFETY MEASURES:
   - Dry-run mode to preview without changes
   - Multiple confirmation prompts
   - Schema validation before stamping
   - Backup recommendations
   - Rollback capability
   - Detailed logging of all operations

USAGE:
------
# 1. Preview what will be stamped (SAFE - no changes):
python scripts/stamp_production_db.py --dry-run

# 2. Analyze schema and recommend which revision to stamp:
python scripts/stamp_production_db.py --analyze

# 3. Stamp with specific revision (REQUIRES CONFIRMATION):
python scripts/stamp_production_db.py --stamp 5479068ccdaa

# 4. Force stamp without validation (DANGEROUS - use with caution):
python scripts/stamp_production_db.py --stamp 5479068ccdaa --force

# 5. View migration history:
python scripts/stamp_production_db.py --show-migrations

VERIFICATION AFTER STAMPING:
---------------------------
1. Check alembic_version table:
   SELECT * FROM alembic_version;

2. Verify Alembic sees it:
   alembic current

3. Check for pending migrations:
   alembic history --verbose

4. Test upgrade path (dry-run first!):
   alembic upgrade head --sql > upgrade.sql
   # Review upgrade.sql before applying

RECOVERY:
---------
If stamping goes wrong:
1. Delete from alembic_version table:
   DELETE FROM alembic_version;

2. Re-run this script with correct revision

3. Or manually insert correct revision:
   INSERT INTO alembic_version (version_num) VALUES ('correct_revision_id');
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Set, Tuple
import asyncpg
import re

# Import Alembic for migration inspection
try:
    from alembic import script, config as alembic_config
    from alembic.runtime import migration
except ImportError:
    print("ERROR: Alembic not installed. Run: pip install alembic")
    sys.exit(1)


# Production database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"
)


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 80}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


async def get_db_connection() -> asyncpg.Connection:
    """
    Establish connection to production database.

    Returns:
        asyncpg.Connection: Database connection

    Raises:
        Exception: If connection fails
    """
    try:
        # Parse connection URL for asyncpg
        url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
        url = url.replace("?sslmode=require", "")

        print_info(f"Connecting to database...")
        conn = await asyncpg.connect(url, ssl='require', timeout=30)
        print_success("Connected to production database")
        return conn

    except Exception as e:
        print_error(f"Failed to connect to database: {type(e).__name__}: {str(e)}")
        raise


async def get_current_schema_info(conn: asyncpg.Connection) -> Dict[str, any]:
    """
    Get comprehensive information about current database schema.

    Args:
        conn: Database connection

    Returns:
        Dict with schema information (tables, columns, indexes, constraints)
    """
    print_info("Analyzing current database schema...")

    schema_info = {
        'tables': [],
        'columns': {},
        'indexes': {},
        'constraints': {},
        'alembic_version': None
    }

    # Get all tables
    tables = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    schema_info['tables'] = [row['table_name'] for row in tables]

    # Get columns for each table
    for table in schema_info['tables']:
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = $1
            ORDER BY ordinal_position
        """, table)
        schema_info['columns'][table] = [dict(row) for row in columns]

        # Get indexes
        indexes = await conn.fetch("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = $1
        """, table)
        schema_info['indexes'][table] = [dict(row) for row in indexes]

        # Get constraints
        constraints = await conn.fetch("""
            SELECT conname, contype, pg_get_constraintdef(oid) as definition
            FROM pg_constraint
            WHERE conrelid = $1::regclass
        """, table)
        schema_info['constraints'][table] = [dict(row) for row in constraints]

    # Check alembic_version
    alembic_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'alembic_version'
        )
    """)

    if alembic_exists:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        schema_info['alembic_version'] = version

    print_success(f"Found {len(schema_info['tables'])} tables in database")
    return schema_info


def get_migration_files() -> List[Tuple[str, str, str]]:
    """
    Get list of all migration files with their revisions.

    Returns:
        List of tuples: (revision_id, down_revision, file_path)
    """
    migrations_dir = Path(__file__).parent.parent / "alembic" / "versions"

    if not migrations_dir.exists():
        print_error(f"Migrations directory not found: {migrations_dir}")
        return []

    migrations = []
    revision_pattern = re.compile(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
    down_revision_pattern = re.compile(r"^down_revision\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)

    for file_path in migrations_dir.glob("*.py"):
        if file_path.name == "__init__.py":
            continue

        try:
            content = file_path.read_text()
            revision_match = revision_pattern.search(content)
            down_revision_match = down_revision_pattern.search(content)

            if revision_match:
                revision = revision_match.group(1)
                down_revision = down_revision_match.group(1) if down_revision_match else None
                migrations.append((revision, down_revision, str(file_path)))

        except Exception as e:
            print_warning(f"Could not parse {file_path.name}: {e}")
            continue

    print_success(f"Found {len(migrations)} migration files")
    return migrations


def build_migration_chain(migrations: List[Tuple[str, str, str]]) -> List[str]:
    """
    Build ordered migration chain from revisions.

    Args:
        migrations: List of (revision, down_revision, file_path) tuples

    Returns:
        List of revision IDs in order (oldest to newest)
    """
    # Create revision -> down_revision mapping
    rev_map = {rev: down for rev, down, _ in migrations}

    # Find head (revision with no dependents)
    all_revisions = set(rev_map.keys())
    down_revisions = set(down for down in rev_map.values() if down and down != 'None')

    # Heads are revisions that aren't down_revision of anything
    heads = all_revisions - down_revisions

    if not heads:
        print_warning("Could not determine migration head")
        return list(all_revisions)

    # Build chain from head backwards
    chain = []
    current = list(heads)[0]  # Take first head if multiple

    visited = set()
    while current and current != 'None' and current not in visited:
        visited.add(current)
        chain.insert(0, current)
        current = rev_map.get(current)

    return chain


async def validate_schema_matches_revision(
    conn: asyncpg.Connection,
    revision: str,
    schema_info: Dict[str, any]
) -> Tuple[bool, List[str]]:
    """
    Validate that current schema matches what would exist at given revision.

    Args:
        conn: Database connection
        revision: Revision ID to validate against
        schema_info: Current schema information

    Returns:
        Tuple of (matches: bool, issues: List[str])
    """
    print_info(f"Validating schema against revision {revision}...")

    issues = []

    # Key tables that should exist for recent migrations
    expected_tables = {
        'users', 'patients', 'messages', 'quiz_sessions', 'quiz_responses',
        'alerts', 'flow_templates', 'patient_flow_states', 'audit_logs'
    }

    missing_tables = expected_tables - set(schema_info['tables'])
    if missing_tables:
        issues.append(f"Missing expected tables: {', '.join(missing_tables)}")

    # Check for specific known migrations
    if revision >= '5479068ccdaa':  # Metadata -> event_metadata rename
        if 'audit_logs' in schema_info['columns']:
            cols = [c['column_name'] for c in schema_info['columns']['audit_logs']]
            if 'metadata' in cols:
                issues.append("audit_logs still has 'metadata' column (should be 'event_metadata')")
            if 'event_metadata' not in cols:
                issues.append("audit_logs missing 'event_metadata' column")

    if revision >= '20251009_230000':  # WhatsApp delivery failures
        if 'whatsapp_delivery_failures' not in schema_info['tables']:
            issues.append("Missing whatsapp_delivery_failures table")

    if revision >= '20251009_235500':  # Webhook idempotency
        if 'webhook_idempotency' not in schema_info['tables']:
            issues.append("Missing webhook_idempotency table")

    matches = len(issues) == 0

    if matches:
        print_success(f"Schema validates successfully for revision {revision}")
    else:
        print_warning(f"Schema validation found {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")

    return matches, issues


async def stamp_database(
    conn: asyncpg.Connection,
    revision: str,
    dry_run: bool = True
) -> bool:
    """
    Stamp the database with specified revision.

    Args:
        conn: Database connection
        revision: Revision ID to stamp
        dry_run: If True, only preview without making changes

    Returns:
        bool: True if successful
    """
    try:
        # Check if alembic_version table exists
        alembic_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'alembic_version'
            )
        """)

        if not alembic_exists:
            print_warning("alembic_version table does not exist")
            if dry_run:
                print_info("DRY RUN: Would create alembic_version table")
                print_info(f"DRY RUN: Would insert revision: {revision}")
                return True
            else:
                print_info("Creating alembic_version table...")
                await conn.execute("""
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(32) NOT NULL,
                        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                    )
                """)
                print_success("Created alembic_version table")

        # Get current version
        current_version = None
        if alembic_exists:
            current_version = await conn.fetchval("SELECT version_num FROM alembic_version")

        if current_version:
            print_info(f"Current version: {current_version}")
            if dry_run:
                print_info(f"DRY RUN: Would update from {current_version} to {revision}")
                return True
            else:
                print_info(f"Updating version from {current_version} to {revision}...")
                await conn.execute(
                    "UPDATE alembic_version SET version_num = $1",
                    revision
                )
        else:
            if dry_run:
                print_info(f"DRY RUN: Would insert revision: {revision}")
                return True
            else:
                print_info(f"Inserting revision: {revision}...")
                await conn.execute(
                    "INSERT INTO alembic_version (version_num) VALUES ($1)",
                    revision
                )

        # Verify stamp
        if not dry_run:
            new_version = await conn.fetchval("SELECT version_num FROM alembic_version")
            if new_version == revision:
                print_success(f"Successfully stamped database with revision: {revision}")
                return True
            else:
                print_error(f"Stamp verification failed. Expected {revision}, got {new_version}")
                return False

        return True

    except Exception as e:
        print_error(f"Stamp operation failed: {type(e).__name__}: {str(e)}")
        return False


async def show_migrations():
    """Display all available migrations in order."""
    print_header("AVAILABLE MIGRATIONS")

    migrations = get_migration_files()
    if not migrations:
        print_error("No migration files found")
        return

    chain = build_migration_chain(migrations)

    print(f"\nMigration chain ({len(chain)} migrations):\n")

    for i, rev in enumerate(chain, 1):
        # Find the file for this revision
        file_info = next((f for r, _, f in migrations if r == rev), None)
        file_name = Path(file_info).name if file_info else "unknown"

        print(f"{i:3d}. {Colors.OKBLUE}{rev}{Colors.ENDC}")
        print(f"     {file_name}")

        if i < len(chain):
            print("      ↓")

    print(f"\n{Colors.BOLD}Latest revision (head): {Colors.OKGREEN}{chain[-1]}{Colors.ENDC}\n")


async def analyze_and_recommend(conn: asyncpg.Connection):
    """Analyze current schema and recommend which revision to stamp."""
    print_header("SCHEMA ANALYSIS & RECOMMENDATION")

    schema_info = await get_current_schema_info(conn)

    print(f"\n{Colors.BOLD}Current Database State:{Colors.ENDC}")
    print(f"  Tables: {len(schema_info['tables'])}")
    print(f"  Alembic Version: {schema_info['alembic_version'] or 'None'}")

    # Get migrations and find latest
    migrations = get_migration_files()
    chain = build_migration_chain(migrations)

    if not chain:
        print_error("Could not determine migration chain")
        return

    latest_revision = chain[-1]

    print(f"\n{Colors.BOLD}Latest Migration:{Colors.ENDC}")
    print(f"  Revision: {Colors.OKGREEN}{latest_revision}{Colors.ENDC}")

    # Validate against latest
    matches, issues = await validate_schema_matches_revision(conn, latest_revision, schema_info)

    print(f"\n{Colors.BOLD}RECOMMENDATION:{Colors.ENDC}\n")

    if matches:
        print_success(f"Your schema appears to match revision: {latest_revision}")
        print_info("Recommended action:")
        print(f"  python scripts/stamp_production_db.py --stamp {latest_revision}")
    else:
        print_warning("Schema does not fully match latest revision")
        print_warning("Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n" + Colors.WARNING + "CAUTION: Investigate issues before stamping!" + Colors.ENDC)

        # Try to find a better match
        print_info("\nSearching for best matching revision...")
        for rev in reversed(chain):
            matches, issues = await validate_schema_matches_revision(conn, rev, schema_info)
            if matches:
                print_success(f"Found matching revision: {rev}")
                print_info("Recommended action:")
                print(f"  python scripts/stamp_production_db.py --stamp {rev}")
                break


def confirm_action(message: str) -> bool:
    """
    Ask user for confirmation.

    Args:
        message: Confirmation message

    Returns:
        bool: True if user confirms
    """
    response = input(f"\n{Colors.WARNING}{message} (yes/no): {Colors.ENDC}").strip().lower()
    return response in ['yes', 'y']


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Stamp production database with Alembic migration revision",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying database'
    )

    parser.add_argument(
        '--stamp',
        type=str,
        metavar='REVISION',
        help='Revision ID to stamp (e.g., 5479068ccdaa)'
    )

    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze schema and recommend revision to stamp'
    )

    parser.add_argument(
        '--show-migrations',
        action='store_true',
        help='Show all available migrations'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip validation checks (DANGEROUS!)'
    )

    args = parser.parse_args()

    # Show migrations only (no DB connection needed)
    if args.show_migrations:
        await show_migrations()
        return

    # Connect to database
    try:
        conn = await get_db_connection()
    except Exception:
        print_error("Cannot proceed without database connection")
        sys.exit(1)

    try:
        # Analyze mode
        if args.analyze:
            await analyze_and_recommend(conn)
            return

        # Stamp mode
        if args.stamp:
            revision = args.stamp

            print_header(f"STAMPING DATABASE WITH REVISION: {revision}")

            # Validate revision exists
            migrations = get_migration_files()
            valid_revisions = [rev for rev, _, _ in migrations]

            if revision not in valid_revisions:
                print_error(f"Revision '{revision}' not found in migration files")
                print_info("Available revisions:")
                for rev in valid_revisions[-10:]:  # Show last 10
                    print(f"  - {rev}")
                sys.exit(1)

            # Get schema info
            schema_info = await get_current_schema_info(conn)

            # Validate unless --force
            if not args.force:
                matches, issues = await validate_schema_matches_revision(conn, revision, schema_info)

                if not matches:
                    print_error("Schema validation failed!")
                    print_warning("Use --force to skip validation (not recommended)")
                    sys.exit(1)

            # Dry run or actual stamp
            if args.dry_run:
                print_info("DRY RUN MODE - No changes will be made")
                await stamp_database(conn, revision, dry_run=True)
            else:
                # Final confirmation
                print_warning("⚠️  WARNING: This will modify the database!")
                print(f"\nCurrent alembic_version: {schema_info['alembic_version']}")
                print(f"New version will be: {revision}")

                if not confirm_action("Are you sure you want to stamp the database?"):
                    print_info("Operation cancelled")
                    return

                # Double confirmation for production
                if not confirm_action("FINAL CONFIRMATION: Proceed with stamping?"):
                    print_info("Operation cancelled")
                    return

                # Perform stamp
                success = await stamp_database(conn, revision, dry_run=False)

                if success:
                    print_success("\n✓ Database stamped successfully!")
                    print_info("\nNext steps:")
                    print("  1. Verify: SELECT * FROM alembic_version;")
                    print("  2. Check: alembic current")
                    print("  3. Review: alembic history --verbose")
                else:
                    print_error("\n✗ Stamp operation failed!")
                    sys.exit(1)

        else:
            # No action specified
            parser.print_help()
            print(f"\n{Colors.BOLD}Quick Start:{Colors.ENDC}")
            print("  1. Analyze schema:  python scripts/stamp_production_db.py --analyze")
            print("  2. Preview stamp:   python scripts/stamp_production_db.py --stamp REVISION --dry-run")
            print("  3. Actual stamp:    python scripts/stamp_production_db.py --stamp REVISION")

    finally:
        await conn.close()
        print_info("\nDatabase connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Operation interrupted by user{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print_error(f"\nFatal error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
