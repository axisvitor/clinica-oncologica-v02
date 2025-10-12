#!/usr/bin/env python3
"""
Check current Alembic status in database
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

def check_alembic_status():
    """Check current Alembic status"""
    
    database_url = load_env()
    if not database_url:
        return
    
    # Fix DATABASE_URL format for psycopg2
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    try:
        conn = psycopg2.connect(database_url)
        
        with conn.cursor() as cursor:
            # Check if alembic_version table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                );
            """)
            
            if cursor.fetchone()[0]:
                print("✅ alembic_version table exists")
                
                # Get current version
                cursor.execute("SELECT version_num FROM alembic_version;")
                result = cursor.fetchone()
                
                if result:
                    current_version = result[0]
                    print(f"📊 Current version in database: {current_version}")
                else:
                    print("⚠️ No version found in alembic_version table")
            else:
                print("❌ alembic_version table does not exist")
            
            # Check which tables exist
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            print(f"\n📋 Tables in database ({len(tables)}):")
            for table in tables:
                print(f"  - {table}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_alembic_status()