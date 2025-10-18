#!/usr/bin/env python3
"""
Reset Alembic version and apply migrations from scratch.

This script:
1. Resets alembic_version to None (no migrations applied)
2. Applies all migrations in order

Usage:
    python scripts/reset_and_apply_migrations.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config import settings
import subprocess

def reset_alembic_version():
    """Reset alembic_version table to None."""
    
    print(f"🔧 Resetting Alembic version...")
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Delete all versions
            conn.execute(text("DELETE FROM alembic_version"))
            conn.commit()
            print(f"✅ Alembic version reset to None")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        engine.dispose()
    
    return True

def apply_migrations():
    """Apply all migrations using alembic upgrade head."""
    
    print(f"\n🚀 Applying migrations...")
    
    try:
        # Run alembic upgrade head
        result = subprocess.run(
            ["py", "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(f"❌ Error applying migrations:")
            print(result.stderr)
            return False
        
        print(f"✅ Migrations applied successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def verify_migrations():
    """Verify that migrations were applied."""
    
    print(f"\n🔍 Verifying migrations...")
    
    try:
        # Run alembic current
        result = subprocess.run(
            ["py", "-m", "alembic", "current"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        if "002_patient_onboarding_saga (head)" in result.stdout:
            print(f"✅ Migrations verified - at head revision")
            return True
        else:
            print(f"⚠️  Warning - not at expected revision")
            return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Reset and Apply Migrations")
    print("=" * 60)
    
    # Step 1: Reset alembic version
    if not reset_alembic_version():
        print("\n❌ FAILED - Could not reset alembic version")
        sys.exit(1)
    
    # Step 2: Apply migrations
    if not apply_migrations():
        print("\n❌ FAILED - Could not apply migrations")
        sys.exit(1)
    
    # Step 3: Verify migrations
    if not verify_migrations():
        print("\n⚠️  WARNING - Migrations may not have been applied correctly")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ SUCCESS - All migrations applied")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run: py scripts/verify_database_schema.py")
    print("2. Run tests: py -m pytest")
    sys.exit(0)

