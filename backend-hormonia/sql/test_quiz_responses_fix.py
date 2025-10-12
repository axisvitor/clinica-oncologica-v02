#!/usr/bin/env python3
"""
Test that quiz_responses queries work after fixing the schema.
"""
import os
import sys
import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_quiz_responses_fix():
    """Test that quiz_responses queries work after schema fix."""
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
                # Test basic QuizResponse query
                print("Testing basic QuizResponse query...")
                cur.execute("SELECT COUNT(*) FROM quiz_responses")
                count = cur.fetchone()[0]
                print(f"✅ quiz_responses table has {count} records")
                
                # Test quiz_session_id column specifically
                print("Testing quiz_session_id column...")
                cur.execute("SELECT quiz_session_id FROM quiz_responses LIMIT 1")
                print("✅ quiz_session_id column is accessible")
                
                # Test other_text column
                print("Testing other_text column...")
                cur.execute("SELECT other_text FROM quiz_responses LIMIT 1")
                print("✅ other_text column is accessible")
                
                # Test the specific query that was failing in analytics
                print("Testing analytics query pattern...")
                cur.execute("""
                    SELECT quiz_responses.patient_id, quiz_responses.quiz_template_id, 
                           quiz_responses.quiz_session_id, quiz_responses.question_id,
                           quiz_responses.other_text
                    FROM quiz_responses 
                    JOIN patients ON patients.id = quiz_responses.patient_id 
                    WHERE quiz_responses.responded_at IS NOT NULL 
                    LIMIT 1
                """)
                print("✅ Analytics query pattern works!")
                
    except Exception as e:
        print(f'❌ Test failed: {e}')

if __name__ == '__main__':
    test_quiz_responses_fix()