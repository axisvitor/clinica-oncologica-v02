#!/usr/bin/env python3
"""
Check the quiz_templates table data to understand the validation rule format.
"""
import os
import sys
import psycopg
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_quiz_templates_data():
    """Check the quiz_templates table data."""
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
                # Check if quiz_templates table exists
                cur.execute('''
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'quiz_templates'
                    );
                ''')
                
                table_exists = cur.fetchone()[0]
                print(f'quiz_templates table exists: {table_exists}')
                
                if table_exists:
                    # Get sample data
                    cur.execute('''
                        SELECT id, name, version, questions
                        FROM quiz_templates 
                        LIMIT 1;
                    ''')
                    
                    row = cur.fetchone()
                    if row:
                        print(f'\nSample quiz template:')
                        print(f'  ID: {row[0]}')
                        print(f'  Name: {row[1]}')
                        print(f'  Version: {row[2]}')
                        
                        # Parse and examine questions JSON
                        questions = row[3]
                        if questions:
                            print(f'\nQuestions structure:')
                            if isinstance(questions, str):
                                questions = json.loads(questions)
                            
                            for i, question in enumerate(questions[:2]):  # Show first 2 questions
                                print(f'\nQuestion {i}:')
                                print(f'  ID: {question.get("id")}')
                                print(f'  Type: {question.get("type")}')
                                print(f'  Text: {question.get("text", "")[:50]}...')
                                
                                validation_rules = question.get("validation_rules", [])
                                if validation_rules:
                                    print(f'  Validation rules:')
                                    for j, rule in enumerate(validation_rules):
                                        print(f'    Rule {j}:')
                                        print(f'      Type: {rule.get("type")}')
                                        print(f'      Value: {rule.get("value")} (type: {type(rule.get("value"))})')
                                        print(f'      Message: {rule.get("message")}')
                    else:
                        print('No quiz templates found')
                else:
                    print('quiz_templates table does not exist')
                
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    check_quiz_templates_data()