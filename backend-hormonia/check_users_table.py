#!/usr/bin/env python3
"""
Check Users Table Structure
"""

import os
import psycopg

def get_database_url():
    db_url = (
        os.getenv('DATABASE_URL') or 
        os.getenv('POSTGRES_URL') or 
        os.getenv('DB_URL') or
        os.getenv('SUPABASE_DB_URL')
    )
    return db_url

def check_users_table():
    db_url = get_database_url()
    if not db_url:
        return False
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                print("🔍 Checking users table structure...")
                
                # Get table structure
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = 'users'
                    ORDER BY ordinal_position
                """)
                
                columns = cur.fetchall()
                print(f"Users table has {len(columns)} columns:")
                for col_name, data_type, nullable, default in columns:
                    print(f"  - {col_name}: {data_type} {'NULL' if nullable == 'YES' else 'NOT NULL'}")
                
                # Get sample data
                print(f"\nSample users data:")
                cur.execute("SELECT * FROM users LIMIT 3")
                users = cur.fetchall()
                
                if users:
                    # Get column names
                    col_names = [desc[0] for desc in cur.description]
                    print(f"Columns: {col_names}")
                    
                    for i, user in enumerate(users):
                        print(f"  User {i+1}: {dict(zip(col_names, user))}")
                else:
                    print("  No users found")
                
                return True
                
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    check_users_table()