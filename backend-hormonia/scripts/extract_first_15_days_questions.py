"""
Script to extract the first 15 days of questions from the flow templates.
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def extract_questions():
    """Extract questions from flow templates."""
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return
    
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("=" * 80)
    print("EXTRACTING FIRST 15 DAYS OF QUESTIONS")
    print("=" * 80)
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                
                # Get active flow templates
                print("\n📋 Finding active flow templates...")
                cur.execute("""
                    SELECT 
                        ftv.id,
                        ftv.version_number,
                        ftv.template_name,
                        fk.kind_key,
                        fk.display_name
                    FROM flow_template_versions ftv
                    JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
                    WHERE ftv.is_active = true
                    ORDER BY fk.kind_key, ftv.version_number DESC
                """)
                
                templates = cur.fetchall()
                print(f"Found {len(templates)} active templates\n")
                
                for template in templates:
                    template_id, version, name, kind_key, kind_display = template
                    
                    print("-" * 80)
                    print(f"Template: {name}")
                    print(f"Kind: {kind_display} ({kind_key})")
                    print(f"Version: {version}")
                    print("-" * 80)
                    
                    # Get messages for this template
                    cur.execute("""
                        SELECT 
                            step_number,
                            message_key,
                            message_text,
                            message_type,
                            buttons,
                            list_items,
                            conditions,
                            delay_seconds
                        FROM flow_messages
                        WHERE flow_template_version_id = %s
                        ORDER BY step_number
                    """, (template_id,))
                    
                    messages = cur.fetchall()
                    
                    if not messages:
                        print("  ⚠ No messages found for this template\n")
                        continue
                    
                    print(f"\nTotal steps: {len(messages)}")
                    print("\n" + "=" * 80)
                    
                    # Extract first 15 days (assuming 1 message per day)
                    days_to_show = min(15, len(messages))
                    
                    for i, msg in enumerate(messages[:days_to_show], 1):
                        step_num, key, text, msg_type, buttons, list_items, conditions, delay = msg
                        
                        print(f"\n📅 DIA {i} (Step {step_num})")
                        print(f"   Key: {key}")
                        print(f"   Type: {msg_type}")
                        
                        if delay:
                            hours = delay / 3600
                            print(f"   Delay: {delay}s ({hours:.1f}h)")
                        
                        print(f"\n   Mensagem:")
                        # Format message text with proper indentation
                        for line in text.split('\n'):
                            print(f"   {line}")
                        
                        # Show buttons if present
                        if buttons:
                            print(f"\n   Botões:")
                            if isinstance(buttons, str):
                                buttons = json.loads(buttons)
                            for btn in buttons:
                                print(f"     - {btn.get('text', btn)}")
                        
                        # Show list items if present
                        if list_items:
                            print(f"\n   Lista:")
                            if isinstance(list_items, str):
                                list_items = json.loads(list_items)
                            for item in list_items:
                                print(f"     - {item.get('title', item)}")
                        
                        # Show conditions if present
                        if conditions:
                            print(f"\n   Condições: {conditions}")
                        
                        print("-" * 80)
                    
                    if len(messages) > 15:
                        print(f"\n... e mais {len(messages) - 15} mensagens (dias 16-{len(messages)})")
                    
                    print("\n" + "=" * 80 + "\n")
                
                # Also check for quiz templates
                print("\n" + "=" * 80)
                print("QUIZ TEMPLATES")
                print("=" * 80)
                
                cur.execute("""
                    SELECT 
                        id,
                        name,
                        description,
                        category,
                        questions,
                        is_active
                    FROM quiz_templates
                    WHERE is_active = true
                    ORDER BY created_at DESC
                """)
                
                quizzes = cur.fetchall()
                
                if quizzes:
                    print(f"\nFound {len(quizzes)} active quiz templates\n")
                    
                    for quiz in quizzes:
                        quiz_id, name, desc, category, questions, is_active = quiz
                        
                        print("-" * 80)
                        print(f"Quiz: {name}")
                        print(f"Category: {category}")
                        print(f"Description: {desc}")
                        print("-" * 80)
                        
                        if questions:
                            if isinstance(questions, str):
                                questions = json.loads(questions)
                            
                            print(f"\nTotal questions: {len(questions)}")
                            
                            for i, q in enumerate(questions[:15], 1):
                                print(f"\n📝 Pergunta {i}:")
                                print(f"   {q.get('question', q.get('text', 'N/A'))}")
                                
                                if 'options' in q:
                                    print(f"   Opções:")
                                    for opt in q['options']:
                                        print(f"     - {opt}")
                        
                        print("\n" + "=" * 80 + "\n")
                else:
                    print("\n⚠ No active quiz templates found\n")
                
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    extract_questions()
