#!/usr/bin/env python3
"""
Check the quiz_responses table schema to identify missing columns.
"""
import os
import sys
import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_quiz_responses_schema():
    """Check the quiz_responses table schema."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not found in environment")
        return
    
    # Convert SQLAlchemy URL to psycopg format
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                # Check if quiz_responses table exists
                cur.execute('''
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'quiz_responses'
                    );
                ''')
                
                table_exists = cur.fetchone()[0]
                print(f'quiz_responses table exists: {table_exists}')
                
                if table_exists:
                    # Check quiz_responses columns
                    cur.execute('''
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns 
                        WHERE table_name = 'quiz_responses' 
                        AND table_schema = 'public'
                        ORDER BY ordinal_position;
                    ''')
                    
                    columns = cur.fetchall()
                    print('\nQuiz_responses table columns:')
                    for col in columns:
                        print(f'  {col[0]} - {col[1]} (nullable: {col[2]})')
                    
                    # Check specifically for quiz_session_id
                    has_quiz_session_id = any(col[0] == 'quiz_session_id' for col in columns)
                    print(f'\nquiz_session_id column exists: {has_quiz_session_id}')
                else:
                    print('quiz_responses table does not exist')
                
                # Check alembic version
                cur.execute('SELECT version_num FROM alembic_version;')
                version = cur.fetchone()
                print(f'\nCurrent alembic version: {version[0] if version else "None"}')
                
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    check_quiz_responses_schema()