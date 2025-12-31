"""
Database Cleanup Script - Final Version
Lists tables with data and cleans them.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Tables to preserve (don't delete data from these)
PRESERVE_TABLES = {
    'alembic_version',
    'users',
    'message_templates',
}

print("="*60)
print("DATABASE CLEANUP - PRODUCTION")
print("="*60)

with engine.connect() as conn:
    # Get all tables with data
    result = conn.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """))
    
    tables = [row[0] for row in result]
    
    # Find tables with data
    tables_with_data = []
    for table in tables:
        try:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            if count > 0:
                tables_with_data.append((table, count))
        except:
            pass
    
    print(f"\nTables with data ({len(tables_with_data)}):")
    for t, c in tables_with_data:
        status = "[PRESERVE]" if t in PRESERVE_TABLES else "[CLEAN]"
        print(f"  {status} {t}: {c} rows")
    
    # Clean tables
    print("\n--- CLEANING ---")
    conn.execute(text("SET session_replication_role = 'replica';"))
    
    for table, count in tables_with_data:
        if table in PRESERVE_TABLES:
            print(f"○ SKIP {table} (preserved)")
            continue
        try:
            conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            print(f"✓ {table}: {count} rows deleted")
        except Exception as e:
            print(f"✗ {table}: {str(e)[:40]}")
    
    conn.execute(text("SET session_replication_role = 'origin';"))
    conn.commit()

print("\n" + "="*60)
print("CLEANUP COMPLETE")
print("="*60)
