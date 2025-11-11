"""
Script to verify current database schema.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def verify_schema():
    """Verify the current database schema."""
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return
    
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("=" * 70)
    print("DATABASE SCHEMA VERIFICATION")
    print("=" * 70)
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                
                # Check messages table
                print("\n📋 Messages Table")
                print("-" * 70)
                cur.execute("""
                    SELECT column_name, data_type, column_default, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'messages'
                    ORDER BY ordinal_position
                """)
                
                columns = cur.fetchall()
                print(f"Total columns: {len(columns)}\n")
                for col in columns:
                    nullable = "NULL" if col[3] == "YES" else "NOT NULL"
                    default = f"DEFAULT {col[2]}" if col[2] else ""
                    print(f"  {col[0]:<30} {col[1]:<25} {nullable:<10} {default}")
                
                # Check patient_onboarding_saga table
                print("\n📋 Patient Onboarding Saga Table")
                print("-" * 70)
                cur.execute("""
                    SELECT column_name, data_type, column_default, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'patient_onboarding_saga'
                    ORDER BY ordinal_position
                """)
                
                columns = cur.fetchall()
                print(f"Total columns: {len(columns)}\n")
                for col in columns:
                    nullable = "NULL" if col[3] == "YES" else "NOT NULL"
                    default = f"DEFAULT {col[2]}" if col[2] else ""
                    print(f"  {col[0]:<30} {col[1]:<25} {nullable:<10} {default}")
                
                # Check enums
                print("\n📋 Custom Enums")
                print("-" * 70)
                cur.execute("""
                    SELECT t.typname as enum_name, 
                           array_agg(e.enumlabel ORDER BY e.enumsortorder) as values
                    FROM pg_type t 
                    JOIN pg_enum e ON t.oid = e.enumtypid  
                    WHERE t.typname IN ('message_priority', 'saga_status')
                    GROUP BY t.typname
                    ORDER BY t.typname
                """)
                
                enums = cur.fetchall()
                for enum in enums:
                    print(f"\n  {enum[0]}:")
                    for val in enum[1]:
                        print(f"    - {val}")
                
                # Check indexes
                print("\n📋 Relevant Indexes")
                print("-" * 70)
                
                tables = ['messages', 'patient_onboarding_saga']
                for table in tables:
                    cur.execute("""
                        SELECT indexname, indexdef
                        FROM pg_indexes 
                        WHERE tablename = %s
                        ORDER BY indexname
                    """, (table,))
                    
                    indexes = cur.fetchall()
                    print(f"\n  {table} ({len(indexes)} indexes):")
                    for idx in indexes:
                        print(f"    - {idx[0]}")
                
                print("\n" + "=" * 70)
                print("✓ SCHEMA VERIFICATION COMPLETE")
                print("=" * 70)
                
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_schema()
