#!/usr/bin/env python3
"""
Critical RLS Fix Application Script

This script applies the critical RLS policy migration to fix the security vulnerability.

Usage:
    python apply_rls_fix.py [--dry-run | --force]
"""

import os
import sys
import subprocess
import asyncio

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def run_verification(check_type: str = ""):
    """Run the RLS verification script."""
    script_path = os.path.join(os.path.dirname(__file__), "verify_rls_policies.py")
    cmd = [sys.executable, script_path]
    if check_type:
        cmd.append(f"--check-{check_type}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode


def run_alembic_migration(dry_run: bool = False):
    """Run the Alembic migration."""
    os.chdir(os.path.dirname(os.path.dirname(__file__)))  # Go to backend-hormonia directory

    if dry_run:
        print("🔍 DRY RUN: Showing what would be migrated...")
        cmd = ["alembic", "show", "20251011_130000"]
    else:
        print("🚀 Applying RLS fix migration...")
        cmd = ["alembic", "upgrade", "20251011_130000"]

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode


def main():
    """Main application function."""

    dry_run = False
    force = False

    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            print(__doc__)
            sys.exit(0)
        elif sys.argv[1] == '--dry-run':
            dry_run = True
        elif sys.argv[1] == '--force':
            force = True

    print("🔒 CRITICAL RLS SECURITY FIX")
    print("=" * 50)

    # Step 1: Check current status
    print("\n1️⃣ Checking current RLS status...")
    current_status = run_verification("before")

    if current_status == 0 and not force:
        print("✅ No RLS vulnerabilities detected. Use --force to apply anyway.")
        sys.exit(0)
    elif current_status == 1:
        print("🚨 RLS vulnerabilities detected. Proceeding with fix...")

    # Step 2: Apply migration
    if dry_run:
        print("\n2️⃣ Dry run - showing migration details...")
        migration_result = run_alembic_migration(dry_run=True)
    else:
        print("\n2️⃣ Applying migration...")
        migration_result = run_alembic_migration(dry_run=False)

    if migration_result != 0:
        print("❌ Migration failed!")
        sys.exit(1)

    if not dry_run:
        # Step 3: Verify fix
        print("\n3️⃣ Verifying RLS policies after migration...")
        final_status = run_verification("after")

        if final_status == 0:
            print("\n✅ SUCCESS: RLS security vulnerability fixed!")
            print("🛡️ All critical tables now have proper access policies.")
        else:
            print("\n❌ FAILURE: RLS policies not properly applied!")
            print("🚨 Manual intervention required!")
            sys.exit(1)

    print("\n🎉 RLS fix completed successfully!")


if __name__ == "__main__":
    main()