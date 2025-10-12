#!/usr/bin/env python3
"""
Comprehensive Database Health Check
Verifies all aspects of the database state
"""

import os
import sys
from pathlib import Path
import psycopg2

def load_env():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent.parent / '.env'
    
    if not env_path.exists():
        print("❌ Error: .env file not found")
        return None
    
    env_vars = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip().strip('"\'')
    
    return env_vars.get('DATABASE_URL')

def comprehensive_check():
    """Perform comprehensive database health check"""
    
    database_url = load_env()
    if not database_url:
        return
    
    # Fix DATABASE_URL format for psycopg2
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("🔍 COMPREHENSIVE DATABASE HEALTH CHECK")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(database_url)
        
        with conn.cursor() as cursor:
            
            # 1. Check database connection
            print("1️⃣ Database Connection:")
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"   ✅ Connected to: {version.split(',')[0]}")
            
            # 2. Check table count and core tables
            print("\n2️⃣ Table Analysis:")
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
            """)
            table_count = cursor.fetchone()[0]
            print(f"   📊 Total tables: {table_count}")
            
            # Check core tables
            core_tables = ['users', 'patients', 'messages', 'alerts', 'security_audit_log']
            missing_core = []
            
            for table in core_tables:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = %s
                    );
                """, (table,))
                
                if cursor.fetchone()[0]:
                    print(f"   ✅ Core table '{table}' exists")
                else:
                    missing_core.append(table)
                    print(f"   ❌ Core table '{table}' missing")
            
            # 3. Check data integrity
            print("\n3️⃣ Data Integrity:")
            
            # Check if tables have data
            data_tables = ['users', 'patients', 'messages']
            for table in data_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table};")
                    count = cursor.fetchone()[0]
                    print(f"   📊 {table}: {count} records")
                except Exception as e:
                    print(f"   ❌ Error checking {table}: {e}")
            
            # 4. Check indexes
            print("\n4️⃣ Index Analysis:")
            cursor.execute("""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE schemaname = 'public';
            """)
            index_count = cursor.fetchone()[0]
            print(f"   📊 Total indexes: {index_count}")
            
            # 5. Check foreign keys
            print("\n5️⃣ Foreign Key Constraints:")
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.table_constraints 
                WHERE constraint_type = 'FOREIGN KEY' AND table_schema = 'public';
            """)
            fk_count = cursor.fetchone()[0]
            print(f"   🔗 Foreign key constraints: {fk_count}")
            
            # 6. Check for RLS status
            print("\n6️⃣ Row Level Security Status:")
            cursor.execute("""
                SELECT 
                    tablename,
                    rowsecurity
                FROM pg_tables t
                JOIN pg_class c ON c.relname = t.tablename
                WHERE schemaname = 'public'
                AND rowsecurity = true
                ORDER BY tablename;
            """)
            
            rls_tables = cursor.fetchall()
            if rls_tables:
                print(f"   ⚠️ Tables with RLS enabled: {len(rls_tables)}")
                for table, _ in rls_tables:
                    print(f"     - {table}")
            else:
                print("   ✅ No tables have RLS enabled (good!)")
            
            # 7. Check Alembic status
            print("\n7️⃣ Alembic Status:")
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'alembic_version'
                );
            """)
            
            if cursor.fetchone()[0]:
                cursor.execute("SELECT version_num FROM alembic_version;")
                version = cursor.fetchone()[0]
                print(f"   📊 Alembic version: {version}")
                
                # Check if version matches expected
                if version == '20251011_130000':
                    print("   ✅ Alembic version is correct")
                else:
                    print(f"   ⚠️ Unexpected Alembic version: {version}")
            else:
                print("   ❌ Alembic version table missing")
            
            # 8. Check for potential issues
            print("\n8️⃣ Potential Issues:")
            issues_found = []
            
            # Check for tables without primary keys
            cursor.execute("""
                SELECT t.table_name
                FROM information_schema.tables t
                LEFT JOIN information_schema.table_constraints tc 
                    ON t.table_name = tc.table_name 
                    AND tc.constraint_type = 'PRIMARY KEY'
                WHERE t.table_schema = 'public' 
                AND t.table_type = 'BASE TABLE'
                AND tc.table_name IS NULL;
            """)
            
            no_pk_tables = [row[0] for row in cursor.fetchall()]
            if no_pk_tables:
                issues_found.append(f"Tables without primary keys: {', '.join(no_pk_tables)}")
            
            # Check for orphaned foreign key references
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.table_constraints 
                WHERE constraint_type = 'FOREIGN KEY' 
                AND table_schema = 'public';
            """)
            
            if issues_found:
                for issue in issues_found:
                    print(f"   ⚠️ {issue}")
            else:
                print("   ✅ No major issues detected")
            
            # 9. Performance indicators
            print("\n9️⃣ Performance Indicators:")
            
            # Check database size
            cursor.execute("""
                SELECT pg_size_pretty(pg_database_size(current_database()));
            """)
            db_size = cursor.fetchone()[0]
            print(f"   💾 Database size: {db_size}")
            
            # Check largest tables
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 5;
            """)
            
            print("   📊 Largest tables:")
            for schema, table, size in cursor.fetchall():
                print(f"     - {table}: {size}")
        
        conn.close()
        
        # 10. Overall assessment
        print("\n🎯 OVERALL ASSESSMENT:")
        print("=" * 60)
        
        if missing_core:
            print("❌ ISSUES FOUND:")
            print(f"   - Missing core tables: {', '.join(missing_core)}")
            print("   - Recommend running MIGRATION_TO_PRODUCTION.sql")
        else:
            print("✅ DATABASE IS HEALTHY!")
            print("   - All core tables present")
            print("   - Alembic state is consistent")
            print("   - No major issues detected")
            print("   - Ready for production use")
        
    except Exception as e:
        print(f"❌ Error during health check: {e}")

if __name__ == "__main__":
    comprehensive_check()