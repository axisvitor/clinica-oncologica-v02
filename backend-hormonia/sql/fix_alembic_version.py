#!/usr/bin/env python3
"""
Fix Alembic version table to reflect correct migration state
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

def fix_alembic_version():
    """Fix Alembic version to match our applied migrations"""
    
    database_url = load_env()
    if not database_url:
        return
    
    # Fix DATABASE_URL format for psycopg2
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("🔧 Fixing Alembic version table...")
    
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            # Check current version
            cursor.execute("SELECT version_num FROM alembic_version;")
            result = cursor.fetchone()
            current_version = result[0] if result else None
            
            print(f"📊 Current version in database: {current_version}")
            
            # Check if security_audit_log table exists (indicates our fixes were applied)
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'security_audit_log'
                );
            """)
            
            security_table_exists = cursor.fetchone()[0]
            
            if security_table_exists:
                print("✅ security_audit_log table exists - our fixes were applied")
                
                # Update to the correct version
                target_version = '20251011_130000'
                
                cursor.execute("""
                    UPDATE alembic_version 
                    SET version_num = %s 
                    WHERE version_num = %s;
                """, (target_version, current_version))
                
                print(f"✅ Updated alembic_version from {current_version} to {target_version}")
                
                # Verify the update
                cursor.execute("SELECT version_num FROM alembic_version;")
                new_version = cursor.fetchone()[0]
                print(f"📊 New version in database: {new_version}")
                
            else:
                print("⚠️ security_audit_log table not found - fixes may not have been applied")
        
        conn.close()
        print("✅ Alembic version fix completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_alembic_version()