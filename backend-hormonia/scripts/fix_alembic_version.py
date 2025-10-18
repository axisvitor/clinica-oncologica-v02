#!/usr/bin/env python3
"""
Fix Alembic version table by updating to the correct revision.

This script directly updates the alembic_version table to resolve
conflicts when old migration files have been removed.

Usage:
    python scripts/fix_alembic_version.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config import settings

def fix_alembic_version():
    """Update alembic_version table to the correct revision."""
    
    # Target revision (most recent migration)
    target_revision = "002_patient_onboarding_saga"
    
    print(f"🔧 Fixing Alembic version table...")
    print(f"📍 Target revision: {target_revision}")
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                )
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("⚠️  alembic_version table does not exist. Creating it...")
                conn.execute(text("""
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(32) NOT NULL,
                        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                    )
                """))
                conn.commit()
                print("✅ Created alembic_version table")
            
            # Check current version
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current_version = result.scalar()
            
            if current_version:
                print(f"📌 Current version in database: {current_version}")
                
                # Delete old version
                conn.execute(text("DELETE FROM alembic_version"))
                conn.commit()
                print(f"🗑️  Deleted old version: {current_version}")
            else:
                print("📌 No version currently set in database")
            
            # Insert new version
            conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
                {"version": target_revision}
            )
            conn.commit()
            
            print(f"✅ Successfully set version to: {target_revision}")
            
            # Verify
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            new_version = result.scalar()
            print(f"✅ Verified - Current version: {new_version}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        engine.dispose()
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Alembic Version Fix Script")
    print("=" * 60)
    
    success = fix_alembic_version()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ SUCCESS - Alembic version table updated")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Run: py -m alembic current")
        print("2. Run: py -m alembic upgrade head")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ FAILED - Could not update alembic version")
        print("=" * 60)
        sys.exit(1)

