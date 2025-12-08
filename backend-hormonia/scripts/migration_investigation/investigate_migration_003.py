#!/usr/bin/env python3
"""
Migration 003 Investigation Script
==================================

Purpose: Check if migration 003 was applied but not recorded in alembic_version

Migration Details:
- ID: 003_add_last_retry_at
- Revises: 002_patient_onboarding_saga
- Creates: last_retry_at column in patient_onboarding_saga table
- Creates: idx_patient_onboarding_saga_last_retry index

Expected Database State:
- Column: patient_onboarding_saga.last_retry_at (timestamp with time zone)
- Index: idx_patient_onboarding_saga_last_retry

Current Production State:
- alembic_version contains: 002, 004 (missing 003!)
- This creates a gap in the migration chain
"""

import sys
import os
from pathlib import Path

# Add backend-hormonia to Python path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv
import json
from datetime import datetime

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found in environment")
    sys.exit(1)

# ANSI color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(title):
    """Print formatted section header"""
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}{title:^80}{RESET}")
    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")

def print_success(message):
    """Print success message"""
    print(f"{GREEN}✅ {message}{RESET}")

def print_error(message):
    """Print error message"""
    print(f"{RED}❌ {message}{RESET}")

def print_warning(message):
    """Print warning message"""
    print(f"{YELLOW}⚠️  {message}{RESET}")

def print_info(message):
    """Print info message"""
    print(f"{BLUE}ℹ️  {message}{RESET}")

def check_table_exists(conn, table_name):
    """Check if a table exists"""
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = :table_name
        )
    """), {"table_name": table_name})
    return result.scalar()

def check_column_exists(conn, table_name, column_name):
    """Check if a column exists in a table"""
    result = conn.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = :table_name
          AND column_name = :column_name
    """), {"table_name": table_name, "column_name": column_name})
    return result.fetchone()

def check_index_exists(conn, index_name):
    """Check if an index exists"""
    result = conn.execute(text("""
        SELECT indexname, tablename, indexdef
        FROM pg_indexes
        WHERE indexname = :index_name
    """), {"index_name": index_name})
    return result.fetchone()

def check_alembic_versions(conn):
    """Get all applied migrations from alembic_version"""
    result = conn.execute(text("""
        SELECT version_num
        FROM alembic_version
        ORDER BY version_num
    """))
    return [row[0] for row in result.fetchall()]

def get_table_row_count(conn, table_name):
    """Get row count for a table"""
    result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
    return result.scalar()

def check_data_integrity(conn):
    """Check if any data uses the last_retry_at column"""
    result = conn.execute(text("""
        SELECT COUNT(*)
        FROM patient_onboarding_saga
        WHERE last_retry_at IS NOT NULL
    """))
    return result.scalar()

def main():
    """Main investigation function"""
    print_header("MIGRATION 003 INVESTIGATION REPORT")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden'}")

    engine = create_engine(DATABASE_URL)

    findings = {
        "timestamp": datetime.now().isoformat(),
        "migration_id": "003_add_last_retry_at",
        "table_checked": "patient_onboarding_saga",
        "column_checked": "last_retry_at",
        "index_checked": "idx_patient_onboarding_saga_last_retry",
        "checks": {}
    }

    try:
        with engine.connect() as conn:
            # 1. Check alembic_version table
            print_header("1. ALEMBIC VERSION CHECK")
            versions = check_alembic_versions(conn)
            print_info(f"Applied migrations: {', '.join(versions)}")

            migration_recorded = "003_add_last_retry_at" in versions
            findings["checks"]["migration_recorded"] = migration_recorded

            if migration_recorded:
                print_success("Migration 003 is recorded in alembic_version")
            else:
                print_error("Migration 003 is NOT recorded in alembic_version")
                print_warning("This creates a gap: 002 → ??? → 004")

            # 2. Check if table exists
            print_header("2. TABLE EXISTENCE CHECK")
            table_exists = check_table_exists(conn, "patient_onboarding_saga")
            findings["checks"]["table_exists"] = table_exists

            if table_exists:
                print_success("Table 'patient_onboarding_saga' exists")
                row_count = get_table_row_count(conn, "patient_onboarding_saga")
                print_info(f"Table contains {row_count} rows")
                findings["checks"]["table_row_count"] = row_count
            else:
                print_error("Table 'patient_onboarding_saga' does NOT exist")
                print_error("This is a critical error - migration 002 should have created this table!")
                findings["recommendation"] = "CRITICAL: Table missing - check migration 002 status"
                return findings

            # 3. Check if column exists
            print_header("3. COLUMN EXISTENCE CHECK")
            column_info = check_column_exists(conn, "patient_onboarding_saga", "last_retry_at")
            column_exists = column_info is not None
            findings["checks"]["column_exists"] = column_exists

            if column_exists:
                print_success("Column 'last_retry_at' exists")
                print_info(f"  Column name: {column_info[0]}")
                print_info(f"  Data type: {column_info[1]}")
                print_info(f"  Nullable: {column_info[2]}")
                print_info(f"  Default: {column_info[3] or 'NULL'}")
                findings["checks"]["column_details"] = {
                    "name": column_info[0],
                    "type": column_info[1],
                    "nullable": column_info[2],
                    "default": column_info[3]
                }
            else:
                print_error("Column 'last_retry_at' does NOT exist")

            # 4. Check if index exists
            print_header("4. INDEX EXISTENCE CHECK")
            index_info = check_index_exists(conn, "idx_patient_onboarding_saga_last_retry")
            index_exists = index_info is not None
            findings["checks"]["index_exists"] = index_exists

            if index_exists:
                print_success("Index 'idx_patient_onboarding_saga_last_retry' exists")
                print_info(f"  Table: {index_info[1]}")
                print_info(f"  Definition: {index_info[2]}")
                findings["checks"]["index_details"] = {
                    "name": index_info[0],
                    "table": index_info[1],
                    "definition": index_info[2]
                }
            else:
                print_error("Index 'idx_patient_onboarding_saga_last_retry' does NOT exist")

            # 5. Check data integrity
            if column_exists:
                print_header("5. DATA INTEGRITY CHECK")
                rows_with_data = check_data_integrity(conn)
                findings["checks"]["rows_with_last_retry_at"] = rows_with_data

                if rows_with_data > 0:
                    print_warning(f"{rows_with_data} rows have last_retry_at values")
                    print_info("The column is actively being used")
                else:
                    print_info("No rows have last_retry_at values (column not yet used)")

            # 6. Generate recommendation
            print_header("6. ANALYSIS & RECOMMENDATION")

            if column_exists and index_exists and not migration_recorded:
                print_warning("SCENARIO: Migration 003 was APPLIED but NOT RECORDED")
                print_info("\nThis likely happened because:")
                print_info("  1. Migration was applied directly to database (manual SQL)")
                print_info("  2. Migration was applied but alembic_version update failed")
                print_info("  3. Database restore from backup that had schema but not version table")

                findings["scenario"] = "applied_not_recorded"
                findings["recommendation"] = "insert_into_alembic_version"

                print_info("\n📋 RECOMMENDED ACTION:")
                print_success("Manually insert migration 003 into alembic_version table")
                print_info("\nSQL to execute:")
                print(f"{BOLD}INSERT INTO alembic_version (version_num) VALUES ('003_add_last_retry_at');{RESET}")

            elif not column_exists and not index_exists and not migration_recorded:
                print_error("SCENARIO: Migration 003 was NEVER APPLIED")
                print_info("\nThis means:")
                print_info("  1. Migration 004 was applied BEFORE migration 003")
                print_info("  2. This violates the migration chain dependency")
                print_info("  3. Migration 003 expects 002 → 003 → 004 sequence")

                findings["scenario"] = "never_applied"
                findings["recommendation"] = "apply_migration_with_caution"

                print_info("\n📋 RECOMMENDED ACTION:")
                print_warning("CAUTION: Applying migration 003 now may cause issues")
                print_info("\nOptions:")
                print_info("  A) Apply migration 003 manually (if safe)")
                print_info("  B) Create a new migration that adds the column (safer)")
                print_info("  C) Accept the gap and document it (least disruptive)")

            elif column_exists and not index_exists:
                print_warning("SCENARIO: Column exists but index is missing")
                findings["scenario"] = "partial_application"
                findings["recommendation"] = "create_missing_index"

                print_info("\n📋 RECOMMENDED ACTION:")
                print_success("Create the missing index manually")
                print_info("\nSQL to execute:")
                sql = """CREATE INDEX idx_patient_onboarding_saga_last_retry
    ON patient_onboarding_saga (last_retry_at);
INSERT INTO alembic_version (version_num) VALUES ('003_add_last_retry_at');"""
                print(f"{BOLD}{sql}{RESET}")

            elif migration_recorded and column_exists and index_exists:
                print_success("SCENARIO: Everything is correct!")
                print_info("Migration 003 is properly applied and recorded")
                findings["scenario"] = "correct_state"
                findings["recommendation"] = "no_action_needed"

            else:
                print_error("SCENARIO: Inconsistent state detected")
                findings["scenario"] = "inconsistent"
                findings["recommendation"] = "manual_investigation_required"
                print_warning("Manual investigation required to determine correct action")

    except Exception as e:
        print_error(f"Investigation failed: {str(e)}")
        findings["error"] = str(e)
        findings["recommendation"] = "fix_database_connection_or_permissions"

    # 7. Save findings to JSON
    print_header("7. SAVING FINDINGS")
    output_file = backend_dir / "docs" / "database" / "MIGRATION_003_INVESTIGATION.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(findings, f, indent=2)

    print_success(f"Findings saved to: {output_file}")

    return findings

if __name__ == "__main__":
    try:
        findings = main()

        # Exit code based on scenario
        if findings.get("scenario") == "correct_state":
            sys.exit(0)  # Success
        elif findings.get("scenario") == "applied_not_recorded":
            sys.exit(1)  # Needs manual fix (insert into alembic_version)
        elif findings.get("scenario") == "never_applied":
            sys.exit(2)  # Critical issue (migration missing)
        else:
            sys.exit(3)  # Unknown/inconsistent state

    except KeyboardInterrupt:
        print("\n\nInvestigation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Fatal error: {str(e)}")
        sys.exit(255)
