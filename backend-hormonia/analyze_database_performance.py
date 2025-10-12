#!/usr/bin/env python3
"""
Database Performance Analysis and Optimization
Analyzes current database structure and implements performance improvements.
"""

import os
import sys
import psycopg
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment variables."""
    db_url = (
        os.getenv('DATABASE_URL') or 
        os.getenv('POSTGRES_URL') or 
        os.getenv('DB_URL') or
        os.getenv('SUPABASE_DB_URL')
    )
    
    if not db_url:
        print("❌ No database URL found in environment variables")
        return None
    
    return db_url

def analyze_and_optimize_database():
    """Analyze database structure and implement performance optimizations."""
    
    print("🔍 DATABASE PERFORMANCE ANALYSIS & OPTIMIZATION")
    print("=" * 60)
    
    db_url = get_database_url()
    if not db_url:
        return False
    
    try:
        print(f"🔌 Connecting to database...")
        
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                print("✅ Connected to database")
                
                # 1. List all tables
                print("\n📋 ANALYZING DATABASE STRUCTURE")
                print("-" * 40)
                
                cur.execute("""
                    SELECT table_name, table_type 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """)
                
                tables = cur.fetchall()
                print(f"Found {len(tables)} tables:")
                for table_name, table_type in tables:
                    print(f"  - {table_name} ({table_type})")
                
                # 2. Analyze patients table specifically (the slow one)
                print(f"\n🔍 ANALYZING PATIENTS TABLE")
                print("-" * 40)
                
                # Check if patients table exists
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'patients'
                """)
                
                if cur.fetchone()[0] == 0:
                    print("❌ Patients table not found")
                    return False
                
                # Get table structure
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = 'patients'
                    ORDER BY ordinal_position
                """)
                
                columns = cur.fetchall()
                print(f"Patients table has {len(columns)} columns:")
                for col_name, data_type, nullable, default in columns:
                    print(f"  - {col_name}: {data_type} {'NULL' if nullable == 'YES' else 'NOT NULL'}")
                
                # 3. Check existing indexes
                print(f"\n📊 CURRENT INDEXES ON PATIENTS TABLE")
                print("-" * 40)
                
                cur.execute("""
                    SELECT 
                        indexname,
                        indexdef,
                        schemaname
                    FROM pg_indexes 
                    WHERE tablename = 'patients' AND schemaname = 'public'
                    ORDER BY indexname
                """)
                
                indexes = cur.fetchall()
                print(f"Found {len(indexes)} existing indexes:")
                for idx_name, idx_def, schema in indexes:
                    print(f"  - {idx_name}")
                    print(f"    {idx_def}")
                
                # 4. Get table statistics
                print(f"\n📈 TABLE STATISTICS")
                print("-" * 40)
                
                cur.execute("SELECT COUNT(*) FROM patients")
                row_count = cur.fetchone()[0]
                print(f"Total patients: {row_count}")
                
                # Check for common query patterns - always check columns regardless of row count
                # Check if created_at exists
                cur.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = 'patients' 
                    AND column_name IN ('created_at', 'updated_at', 'status', 'active', 'flow_state')
                """)
                
                available_cols = [row[0] for row in cur.fetchall()]
                print(f"Available indexable columns: {', '.join(available_cols)}")
                
                if row_count > 0:
                    print(f"Table has data - will create performance indexes")
                
                # 5. Implement performance optimizations
                print(f"\n🚀 IMPLEMENTING PERFORMANCE OPTIMIZATIONS")
                print("-" * 40)
                
                optimizations_applied = []
                
                # Create index on created_at if it exists and no index exists
                if 'created_at' in available_cols:
                    # Check if index already exists
                    cur.execute("""
                        SELECT COUNT(*) FROM pg_indexes 
                        WHERE tablename = 'patients' 
                        AND indexdef LIKE '%created_at%'
                    """)
                    
                    if cur.fetchone()[0] == 0:
                        print("Creating index on created_at...")
                        cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_patients_created_at 
                            ON patients(created_at DESC)
                        """)
                        optimizations_applied.append("idx_patients_created_at")
                        print("✅ Index on created_at created")
                    else:
                        print("✅ Index on created_at already exists")
                
                # Create index on status if it exists
                if 'status' in available_cols:
                    cur.execute("""
                        SELECT COUNT(*) FROM pg_indexes 
                        WHERE tablename = 'patients' 
                        AND indexdef LIKE '%status%'
                    """)
                    
                    if cur.fetchone()[0] == 0:
                        print("Creating index on status...")
                        cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_patients_status 
                            ON patients(status)
                        """)
                        optimizations_applied.append("idx_patients_status")
                        print("✅ Index on status created")
                    else:
                        print("✅ Index on status already exists")
                
                # Create composite index for common queries (pagination)
                if 'created_at' in available_cols:
                    cur.execute("""
                        SELECT COUNT(*) FROM pg_indexes 
                        WHERE tablename = 'patients' 
                        AND indexname = 'idx_patients_pagination'
                    """)
                    
                    if cur.fetchone()[0] == 0:
                        print("Creating composite index for pagination...")
                        if 'status' in available_cols:
                            cur.execute("""
                                CREATE INDEX IF NOT EXISTS idx_patients_pagination 
                                ON patients(flow_state, created_at DESC, id)
                            """)
                        else:
                            cur.execute("""
                                CREATE INDEX IF NOT EXISTS idx_patients_pagination 
                                ON patients(created_at DESC, id)
                            """)
                        optimizations_applied.append("idx_patients_pagination")
                        print("✅ Composite pagination index created")
                    else:
                        print("✅ Pagination index already exists")
                
                # 6. Analyze other slow tables if they exist
                print(f"\n🔍 ANALYZING OTHER TABLES FOR OPTIMIZATION")
                print("-" * 40)
                
                # Check messages table (likely to be queried frequently)
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'messages'
                """)
                
                if cur.fetchone()[0] > 0:
                    print("Optimizing messages table...")
                    
                    # Get messages table columns
                    cur.execute("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_schema = 'public' AND table_name = 'messages' 
                        AND column_name IN ('created_at', 'patient_id', 'status', 'message_type')
                    """)
                    
                    msg_cols = [row[0] for row in cur.fetchall()]
                    
                    # Create index on patient_id for foreign key lookups
                    if 'patient_id' in msg_cols:
                        cur.execute("""
                            SELECT COUNT(*) FROM pg_indexes 
                            WHERE tablename = 'messages' 
                            AND indexdef LIKE '%patient_id%'
                        """)
                        
                        if cur.fetchone()[0] == 0:
                            cur.execute("""
                                CREATE INDEX IF NOT EXISTS idx_messages_patient_id 
                                ON messages(patient_id)
                            """)
                            optimizations_applied.append("idx_messages_patient_id")
                            print("✅ Index on messages.patient_id created")
                    
                    # Create index on created_at for time-based queries
                    if 'created_at' in msg_cols:
                        cur.execute("""
                            SELECT COUNT(*) FROM pg_indexes 
                            WHERE tablename = 'messages' 
                            AND indexdef LIKE '%created_at%'
                        """)
                        
                        if cur.fetchone()[0] == 0:
                            cur.execute("""
                                CREATE INDEX IF NOT EXISTS idx_messages_created_at 
                                ON messages(created_at DESC)
                            """)
                            optimizations_applied.append("idx_messages_created_at")
                            print("✅ Index on messages.created_at created")
                
                # 7. Update table statistics
                print(f"\n📊 UPDATING TABLE STATISTICS")
                print("-" * 40)
                
                cur.execute("ANALYZE patients")
                print("✅ Patients table statistics updated")
                
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'messages'
                """)
                
                if cur.fetchone()[0] > 0:
                    cur.execute("ANALYZE messages")
                    print("✅ Messages table statistics updated")
                
                # Commit all changes
                conn.commit()
                print("\n✅ All optimizations committed successfully")
                
                # 8. Final verification
                print(f"\n🎯 OPTIMIZATION SUMMARY")
                print("-" * 40)
                print(f"Optimizations applied: {len(optimizations_applied)}")
                for opt in optimizations_applied:
                    print(f"  ✅ {opt}")
                
                if not optimizations_applied:
                    print("  ℹ️  All optimizations were already in place")
                
                return True
                
    except Exception as e:
        print(f"\n❌ Database optimization failed: {e}")
        logger.error(f"Database error: {e}", exc_info=True)
        return False

def main():
    """Run the database performance analysis and optimization."""
    
    success = analyze_and_optimize_database()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 DATABASE OPTIMIZATION COMPLETED!")
        print()
        print("✅ Performance indexes created")
        print("✅ Table statistics updated")
        print("✅ Query performance should be improved")
        print()
        print("Expected improvements:")
        print("  - Faster patient list queries")
        print("  - Better pagination performance")
        print("  - Optimized foreign key lookups")
        print("  - Reduced query execution time")
    else:
        print("❌ DATABASE OPTIMIZATION FAILED")
        print("Check the error messages above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())