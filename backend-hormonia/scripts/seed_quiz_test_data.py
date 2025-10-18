#!/usr/bin/env python3
"""
Seed Quiz Test Data
Creates test quiz sessions and responses for testing the Quiz Response Viewer
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def seed_quiz_test_data():
    """Seed quiz sessions and responses for testing"""

    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in environment")
        return

    print("🌱 Seeding quiz test data...")

    # Convert SQLAlchemy URL to psycopg format
    db_url = DATABASE_URL.replace('postgresql+psycopg://', 'postgresql://')

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Get first active patient and doctor
            cur.execute("""
                SELECT p.id, p.name, p.doctor_id
                FROM patients p
                WHERE p.doctor_id IS NOT NULL
                LIMIT 1
            """)
            patient_row = cur.fetchone()
            
            if not patient_row:
                print("❌ No patients found with assigned doctor")
                return
            
            patient_id, patient_name, doctor_id = patient_row
            print(f"✅ Using patient: {patient_name} ({patient_id})")
            
            # Get first active quiz template
            cur.execute("""
                SELECT id, name, version, questions
                FROM quiz_templates
                WHERE is_active = true
                LIMIT 1
            """)
            template_row = cur.fetchone()
            
            if not template_row:
                print("❌ No active quiz templates found")
                return
            
            template_id, template_name, template_version, questions_json = template_row
            questions = json.loads(questions_json) if isinstance(questions_json, str) else questions_json
            print(f"✅ Using template: {template_name} v{template_version}")
            
            # Create 3 quiz sessions with responses
            sessions_created = 0
            responses_created = 0
            
            for i in range(3):
                session_id = str(uuid4())
                
                # Create session (completed)
                started_at = datetime.now(timezone.utc) - timedelta(days=30 - (i * 10))
                completed_at = started_at + timedelta(hours=2)
                
                cur.execute("""
                    INSERT INTO quiz_sessions (
                        id, patient_id, quiz_template_id, status,
                        current_question, started_at, completed_at,
                        score, session_metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                """, (
                    session_id,
                    patient_id,
                    template_id,
                    'completed',
                    len(questions),
                    started_at,
                    completed_at,
                    75 + (i * 5),  # Scores: 75, 80, 85
                    json.dumps({
                        "template_version": template_version,
                        "completion_time_seconds": 7200
                    })
                ))
                
                if cur.fetchone():
                    sessions_created += 1
                    print(f"  ✅ Created session {i+1}: {session_id}")
                    
                    # Create responses for each question
                    for q_idx, question in enumerate(questions):
                        response_id = str(uuid4())
                        question_id = question.get('id', f'q{q_idx}')
                        question_text = question.get('text', f'Question {q_idx + 1}')
                        question_type = question.get('type', 'text')
                        
                        # Generate appropriate response based on question type
                        response_value = None
                        response_metadata = {}
                        
                        if question_type == 'scale':
                            response_value = str(7 + (i % 4))  # Values: 7-10
                            response_metadata = {
                                "min_value": question.get('min_value', 0),
                                "max_value": question.get('max_value', 10)
                            }
                        elif question_type == 'yes_no':
                            response_value = 'yes' if i % 2 == 0 else 'no'
                        elif question_type == 'multiple_choice':
                            options = question.get('options', [])
                            if options:
                                response_value = options[i % len(options)].get('value', 'option1')
                        elif question_type == 'single_choice':
                            options = question.get('options', [])
                            if options:
                                response_value = options[i % len(options)].get('value', 'option1')
                        else:
                            response_value = f'Test response {i+1} for question {q_idx+1}'
                        
                        # Add AI analysis metadata for some responses
                        if q_idx == 0:  # First question gets AI analysis
                            response_metadata.update({
                                "ai_analysis": {
                                    "risk_score": 0.3 + (i * 0.2),  # 0.3, 0.5, 0.7
                                    "sentiment_score": 0.5 - (i * 0.1),  # 0.5, 0.4, 0.3
                                    "concerns": [
                                        "Fadiga moderada relatada",
                                        "Possível necessidade de ajuste de medicação"
                                    ] if i == 2 else [],
                                    "recommendations": [
                                        "Agendar consulta de acompanhamento",
                                        "Monitorar sintomas diariamente"
                                    ] if i == 2 else ["Continuar tratamento atual"],
                                    "flagged": i == 2
                                }
                            })
                        
                        responded_at = started_at + timedelta(minutes=30 * (q_idx + 1))
                        
                        cur.execute("""
                            INSERT INTO quiz_responses (
                                id, patient_id, quiz_template_id, quiz_session_id,
                                question_id, question_text, response_type, response_value,
                                response_metadata, responded_at, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                            ON CONFLICT (id) DO NOTHING
                            RETURNING id
                        """, (
                            response_id,
                            patient_id,
                            template_id,
                            session_id,
                            question_id,
                            question_text,
                            question_type,
                            response_value,
                            json.dumps(response_metadata),
                            responded_at,
                            responded_at
                        ))
                        
                        if cur.fetchone():
                            responses_created += 1
            
            conn.commit()
            
            print(f"\n✅ Seed completed!")
            print(f"   Sessions created: {sessions_created}")
            print(f"   Responses created: {responses_created}")
            print(f"\n📊 Test the Quiz Response Viewer:")
            print(f"   1. Navigate to: http://localhost:5173/patients/{patient_id}")
            print(f"   2. Click on 'Respostas de Quiz' tab")
            print(f"   3. View quiz responses and AI analysis")

if __name__ == '__main__':
    try:
        seed_quiz_test_data()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

