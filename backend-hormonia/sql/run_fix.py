#!/usr/bin/env python3
"""
Direct SQL Migration Fix - Python Version
Executes the migration fix SQL directly using Python and psycopg2
"""

import os
import sys
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def load_env():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent.parent / '.env'
    
    if not env_path.exists():
        print("❌ Error: .env file not found in backend-hormonia directory")
        print("Please ensure your .env file exists with DATABASE_URL")
        return None
    
    env_vars = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip().strip('"\'')
    
    return env_vars.get('DATABASE_URL')

def execute_sql_file(database_url, sql_file_path):
    """Execute SQL file against the database"""
    
    print("🔧 Applying migration fixes directly to PostgreSQL...")
    print("=" * 70)
    
    try:
        # Read the SQL file
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print("📡 Connecting to database...")
        
        # Fix DATABASE_URL format for psycopg2
        if database_url.startswith('postgresql+psycopg://'):
            database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
        
        print(f"🔗 Using connection: {database_url.split('@')[0]}@***")
        
        # Connect to database
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        print("🔧 Executing migration fixes...")
        
        # Execute the SQL
        with conn.cursor() as cursor:
            cursor.execute(sql_content)
        
        print("")
        print("✅ Migration fixes applied successfully!")
        print("🎉 Your database is now ready to use.")
        print("")
        print("Next steps:")
        print("1. Start your backend application")
        print("2. The migrations should now work correctly")
        print("3. If you still have issues, check the application logs")
        
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ Error: SQL file not found: {sql_file_path}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main function"""
    
    # Get database URL from .env
    database_url = load_env()
    if not database_url:
        sys.exit(1)
    
    # Path to SQL file
    sql_file = Path(__file__).parent / 'fix_migration_issues.sql'
    
    if not sql_file.exists():
        print(f"❌ Error: SQL file not found: {sql_file}")
        sys.exit(1)
    
    # Execute the SQL
    success = execute_sql_file(database_url, sql_file)
    
    if not success:
        print("")
        print("❌ Error applying migration fixes")
        print("Please check the error messages above")
        sys.exit(1)

if __name__ == "__main__":
    main()