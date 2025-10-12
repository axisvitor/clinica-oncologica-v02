#!/usr/bin/env python3
"""
Clean up Alembic version table duplicates
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

def clean_alembic_version():
    """Clean up Alembic version table"""
    
    database_url = load_env()
    if not database_url:
        return
    
    # Fix DATABASE_URL format for psycopg2
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("🔧 Cleaning up Alembic version table...")
    
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            # Check all versions in the table
            cursor.execute("SELECT version_num FROM alembic_version ORDER BY version_num;")
            versions = [row[0] for row in cursor.fetchall()]
            
            print(f"📊 Current versions in database: {versions}")
            
            if len(versions) > 1:
                print("⚠️ Multiple versions found - cleaning up...")
                
                # Delete all versions
                cursor.execute("DELETE FROM alembic_version;")
                print("🗑️ Deleted all existing versions")
                
                # Insert the correct version
                target_version = '20251011_130000'
                cursor.execute("INSERT INTO alembic_version (version_num) VALUES (%s);", (target_version,))
                print(f"✅ Inserted correct version: {target_version}")
                
            elif len(versions) == 1:
                current_version = versions[0]
                target_version = '20251011_130000'
                
                if current_version != target_version:
                    cursor.execute("UPDATE alembic_version SET version_num = %s;", (target_version,))
                    print(f"✅ Updated version from {current_version} to {target_version}")
                else:
                    print(f"✅ Version is already correct: {current_version}")
            
            else:
                # No versions - insert the correct one
                target_version = '20251011_130000'
                cursor.execute("INSERT INTO alembic_version (version_num) VALUES (%s);", (target_version,))
                print(f"✅ Inserted version: {target_version}")
            
            # Verify final state
            cursor.execute("SELECT version_num FROM alembic_version;")
            final_version = cursor.fetchone()[0]
            print(f"📊 Final version in database: {final_version}")
        
        conn.close()
        print("✅ Alembic version cleanup completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    clean_alembic_version()