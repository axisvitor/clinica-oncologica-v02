#!/usr/bin/env python3
"""
Remove Alembic setup and switch to direct SQL management
This script helps transition from Alembic to direct SQL schema management
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

def remove_alembic_from_database():
    """Remove Alembic version table from database"""
    
    database_url = load_env()
    if not database_url:
        return False
    
    # Fix DATABASE_URL format for psycopg2
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("🗑️ Removing Alembic version tracking from database...")
    
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        
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
                # Drop the alembic_version table
                cursor.execute("DROP TABLE alembic_version;")
                print("✅ Removed alembic_version table from database")
            else:
                print("ℹ️ alembic_version table doesn't exist")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error removing Alembic from database: {e}")
        return False

def create_schema_management_script():
    """Create a simple schema management script"""
    
    script_content = '''#!/usr/bin/env python3
"""
Simple Schema Management - Direct SQL Approach
Replaces Alembic with direct SQL execution
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

def execute_sql_file(sql_file_path):
    """Execute SQL file against the database"""
    
    database_url = load_env()
    if not database_url:
        return False
    
    # Fix DATABASE_URL format for psycopg2
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    try:
        # Read the SQL file
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print(f"📡 Executing SQL file: {sql_file_path}")
        
        # Connect to database
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        
        # Execute the SQL
        with conn.cursor() as cursor:
            cursor.execute(sql_content)
        
        conn.close()
        print("✅ SQL file executed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error executing SQL file: {e}")
        return False

def main():
    """Main function"""
    
    if len(sys.argv) != 2:
        print("Usage: python schema_manager.py <sql_file_path>")
        print("Example: python schema_manager.py sql/MIGRATION_TO_PRODUCTION.sql")
        sys.exit(1)
    
    sql_file = Path(sys.argv[1])
    
    if not sql_file.exists():
        print(f"❌ Error: SQL file not found: {sql_file}")
        sys.exit(1)
    
    success = execute_sql_file(sql_file)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
    
    script_path = Path(__file__).parent / 'schema_manager.py'
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"✅ Created schema management script: {script_path}")

def main():
    """Main function"""
    
    print("🔧 Transitioning from Alembic to Direct SQL Management")
    print("=" * 60)
    
    # Ask for confirmation
    response = input("Do you want to remove Alembic and switch to direct SQL? (y/N): ")
    
    if response.lower() != 'y':
        print("❌ Operation cancelled")
        return
    
    # Remove Alembic from database
    if remove_alembic_from_database():
        print("✅ Alembic removed from database")
    else:
        print("❌ Failed to remove Alembic from database")
        return
    
    # Create schema management script
    create_schema_management_script()
    
    print("\n" + "=" * 60)
    print("✅ TRANSITION COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print("Next steps:")
    print("1. Use 'python sql/schema_manager.py sql/MIGRATION_TO_PRODUCTION.sql' for schema updates")
    print("2. Create new SQL files for future schema changes")
    print("3. Remove Alembic configuration files if desired")
    print("4. Update your deployment scripts to use direct SQL")
    print("\nYour database is now managed with direct SQL - much simpler! 🎉")

if __name__ == "__main__":
    main()