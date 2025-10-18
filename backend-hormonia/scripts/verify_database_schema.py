#!/usr/bin/env python3
"""
Verify database schema - check if expected tables exist.

This script verifies that all expected tables from migrations exist in the database.

Usage:
    python scripts/verify_database_schema.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from app.config import settings

def verify_database_schema():
    """Verify that expected tables exist in the database."""
    
    # Expected tables from migrations
    expected_tables = [
        "alembic_version",
        "messages",
        "patient_onboarding_saga",
        "patients",
        "patient_flow_states",
        "flow_kinds",
        "flow_template_versions",
    ]
    
    print(f"🔍 Verifying database schema...")
    print(f"📊 Expected tables: {len(expected_tables)}")
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        # Use SQLAlchemy inspector
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        print(f"\n📋 Tables in database: {len(existing_tables)}")
        
        # Check each expected table
        missing_tables = []
        found_tables = []
        
        for table in expected_tables:
            if table in existing_tables:
                found_tables.append(table)
                print(f"  ✅ {table}")
            else:
                missing_tables.append(table)
                print(f"  ❌ {table} - MISSING")
        
        # Check for patient_onboarding_saga specifically
        print(f"\n🎯 Critical Table Check:")
        if "patient_onboarding_saga" in existing_tables:
            print(f"  ✅ patient_onboarding_saga table EXISTS")
            
            # Get column info
            columns = inspector.get_columns("patient_onboarding_saga")
            print(f"  📊 Columns ({len(columns)}):")
            for col in columns:
                print(f"     - {col['name']}: {col['type']}")
        else:
            print(f"  ❌ patient_onboarding_saga table DOES NOT EXIST")
        
        # Check for idempotency_key in messages table
        print(f"\n🔑 Idempotency Key Check:")
        if "messages" in existing_tables:
            columns = inspector.get_columns("messages")
            column_names = [col['name'] for col in columns]
            
            if "idempotency_key" in column_names:
                print(f"  ✅ messages.idempotency_key column EXISTS")
            else:
                print(f"  ❌ messages.idempotency_key column MISSING")
                print(f"  📋 Available columns: {', '.join(column_names)}")
        
        # Summary
        print(f"\n" + "=" * 60)
        print(f"📊 Summary:")
        print(f"  ✅ Found: {len(found_tables)} tables")
        print(f"  ❌ Missing: {len(missing_tables)} tables")
        
        if missing_tables:
            print(f"\n⚠️  Missing tables:")
            for table in missing_tables:
                print(f"     - {table}")
            print(f"\n💡 These tables may need to be created by running migrations.")
            return False
        else:
            print(f"\n✅ All expected tables exist!")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("=" * 60)
    print("Database Schema Verification")
    print("=" * 60)
    
    success = verify_database_schema()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ SUCCESS - Database schema is valid")
        print("=" * 60)
        sys.exit(0)
    else:
        print("⚠️  WARNING - Some tables are missing")
        print("=" * 60)
        print("\nRecommended actions:")
        print("1. Check if migrations need to be created")
        print("2. Run: py -m alembic revision --autogenerate -m 'description'")
        print("3. Run: py -m alembic upgrade head")
        sys.exit(1)

