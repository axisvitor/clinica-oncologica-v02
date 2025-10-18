#!/usr/bin/env python3
"""
Script to create initial Alembic migration safely.

CRITICAL FIX #1: Generate initial schema migration for all models.

This script:
1. Validates database connection
2. Checks current schema state
3. Generates initial migration
4. Validates migration syntax
5. Provides rollback instructions

Usage:
    python scripts/create_initial_migration.py
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import test_connection, get_pool_status, engine
from app.config import settings
from sqlalchemy import inspect, text


def print_banner(message: str, char: str = "=") -> None:
    """Print a formatted banner."""
    print("\n" + char * 80)
    print(f"  {message}")
    print(char * 80 + "\n")


def check_database_connection() -> bool:
    """
    Check if database connection is healthy.

    Returns:
        bool: True if connection is healthy, False otherwise
    """
    print("📡 Testing database connection...")
    try:
        result = test_connection()
        if result["status"] == "healthy":
            print("✅ Database connection: HEALTHY")
            print(f"   - Pool size: {result['connection_args']['pool_size']}")
            print(f"   - Checked in: {result['connection_args']['checked_in']}")
            print(f"   - Checked out: {result['connection_args']['checked_out']}")
            return True
        else:
            print(f"❌ Database connection: UNHEALTHY - {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def check_existing_tables() -> Dict[str, Any]:
    """
    Check what tables already exist in the database.

    Returns:
        dict: Information about existing tables
    """
    print("\n🔍 Checking existing database schema...")
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if tables:
            print(f"⚠️  Found {len(tables)} existing tables:")
            for table in sorted(tables):
                print(f"   - {table}")
            return {"exists": True, "tables": tables, "count": len(tables)}
        else:
            print("✅ No existing tables found (clean database)")
            return {"exists": False, "tables": [], "count": 0}
    except Exception as e:
        print(f"❌ Error checking tables: {e}")
        return {"exists": False, "tables": [], "count": 0, "error": str(e)}


def check_alembic_installed() -> bool:
    """
    Check if Alembic is installed and accessible.

    Returns:
        bool: True if Alembic is available, False otherwise
    """
    print("\n🔧 Checking Alembic installation...")
    try:
        result = subprocess.run(
            ["alembic", "--version"], capture_output=True, text=True, check=True
        )
        version = result.stdout.strip()
        print(f"✅ Alembic installed: {version}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Alembic not found. Install with: pip install alembic")
        return False


def check_alembic_versions() -> Dict[str, Any]:
    """
    Check existing Alembic migrations.

    Returns:
        dict: Information about existing migrations
    """
    print("\n📁 Checking existing migrations...")
    versions_dir = Path("alembic/versions")

    if not versions_dir.exists():
        print("❌ Migrations directory not found")
        return {"exists": False, "count": 0, "files": []}

    migration_files = [
        f
        for f in versions_dir.iterdir()
        if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"
    ]

    if migration_files:
        print(f"⚠️  Found {len(migration_files)} existing migrations:")
        for migration_file in sorted(migration_files):
            print(f"   - {migration_file.name}")
        return {"exists": True, "count": len(migration_files), "files": migration_files}
    else:
        print("✅ No existing migrations (ready for initial migration)")
        return {"exists": False, "count": 0, "files": []}


def check_alembic_current_version() -> Dict[str, Any]:
    """
    Check current Alembic version in database.

    Returns:
        dict: Information about current migration version
    """
    print("\n🔖 Checking current migration version...")
    try:
        result = subprocess.run(
            ["alembic", "current"], capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()

        if (
            not output
            or "(head)" in output.lower()
            or "no alembic_version" in output.lower()
        ):
            print("✅ No migrations applied yet")
            return {"applied": False, "version": None}
        else:
            print(f"⚠️  Current version: {output}")
            return {"applied": True, "version": output}
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Could not determine current version: {e}")
        return {"applied": False, "version": None, "error": str(e)}


def generate_migration(message: str = "Initial schema with all models") -> bool:
    """
    Generate the migration using Alembic autogenerate.

    Args:
        message: Migration message

    Returns:
        bool: True if successful, False otherwise
    """
    print_banner("GENERATING MIGRATION", "=")
    print(f"📝 Creating migration: '{message}'")

    try:
        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", message],
            capture_output=True,
            text=True,
            check=True,
        )
        print("✅ Migration generated successfully!")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration generation failed: {e}")
        print(f"Error output: {e.stderr}")
        return False


def validate_migration_files() -> bool:
    """
    Validate that migration files were created and are valid Python.

    Returns:
        bool: True if valid, False otherwise
    """
    print("\n🔍 Validating generated migration...")
    versions_dir = Path("alembic/versions")

    migration_files = [
        f
        for f in versions_dir.iterdir()
        if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"
    ]

    if not migration_files:
        print("❌ No migration files found after generation")
        return False

    # Get the most recent migration file
    latest_migration = max(migration_files, key=lambda f: f.stat().st_mtime)
    print(f"✅ Latest migration: {latest_migration.name}")

    # Validate Python syntax
    try:
        with open(latest_migration, "r", encoding="utf-8") as f:
            content = f.read()
            compile(content, latest_migration.name, "exec")
        print("✅ Migration syntax is valid")
        return True
    except SyntaxError as e:
        print(f"❌ Migration has syntax errors: {e}")
        return False


def print_next_steps() -> None:
    """Print instructions for next steps."""
    print_banner("NEXT STEPS", "=")
    print("1️⃣  Review the migration file:")
    print("    cd alembic/versions")
    print("    cat <migration_file>.py")
    print()
    print("2️⃣  Test the migration (upgrade):")
    print("    alembic upgrade head")
    print()
    print("3️⃣  Test rollback:")
    print("    alembic downgrade -1")
    print()
    print("4️⃣  Re-apply migration:")
    print("    alembic upgrade head")
    print()
    print("5️⃣  Commit the migration file to git:")
    print("    git add alembic/versions/<migration_file>.py")
    print("    git commit -m 'feat(migrations): add initial schema migration'")
    print()
    print_banner("IMPORTANT WARNINGS", "⚠")
    print("⚠️  ALWAYS review auto-generated migrations before applying!")
    print("⚠️  Test migrations on a non-production database first!")
    print("⚠️  Ensure you have a database backup before applying migrations!")
    print("⚠️  Never edit migrations that have been applied to production!")
    print()


def main() -> int:
    """
    Main execution function.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    print_banner("ALEMBIC INITIAL MIGRATION GENERATOR", "🚀")

    # Step 1: Check Alembic installation
    if not check_alembic_installed():
        return 1

    # Step 2: Check database connection
    if not check_database_connection():
        print("\n❌ Cannot proceed without database connection")
        print("   Check your DATABASE_URL environment variable")
        return 1

    # Step 3: Check existing tables
    tables_info = check_existing_tables()

    # Step 4: Check existing migrations
    migrations_info = check_alembic_versions()

    # Step 5: Check current version
    version_info = check_alembic_current_version()

    # Warn if tables exist but no migrations
    if tables_info["exists"] and not migrations_info["exists"]:
        print_banner("WARNING: EXISTING SCHEMA DETECTED", "⚠")
        print("Your database has existing tables but no Alembic migrations.")
        print("This suggests the schema was created with Base.metadata.create_all()")
        print()
        print("Options:")
        print("  1. Drop all tables and start fresh (DESTRUCTIVE)")
        print("  2. Create a baseline migration and mark as applied")
        print("  3. Cancel and manually review")
        print()
        choice = input("Enter choice (1/2/3): ").strip()

        if choice == "1":
            print(
                "\n⚠️  This will DROP ALL TABLES. Type 'DELETE EVERYTHING' to confirm:"
            )
            confirm = input().strip()
            if confirm != "DELETE EVERYTHING":
                print("❌ Cancelled")
                return 1

            from app.database import drop_tables, create_tables

            print("\n🗑️  Dropping all tables...")
            drop_tables()
            print("✅ Tables dropped")
        elif choice == "2":
            print("\n📝 Creating baseline migration...")
            print("⚠️  You will need to manually mark it as applied:")
            print("    alembic stamp head")
        elif choice == "3":
            print("❌ Cancelled by user")
            return 1
        else:
            print("❌ Invalid choice")
            return 1

    # Warn if migrations exist
    if migrations_info["exists"]:
        print_banner("WARNING: EXISTING MIGRATIONS DETECTED", "⚠")
        print(f"Found {migrations_info['count']} existing migrations.")
        print("Creating a new migration will add to the chain.")
        print()
        choice = input("Continue? (y/n): ").strip().lower()
        if choice != "y":
            print("❌ Cancelled by user")
            return 1

    # Generate the migration
    if not generate_migration():
        return 1

    # Validate the generated migration
    if not validate_migration_files():
        return 1

    # Print next steps
    print_next_steps()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
