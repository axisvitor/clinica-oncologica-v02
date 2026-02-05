"""
Restore quiz templates from YAML files
"""
import os
import sys
import json
import uuid
import yaml
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'templates', 'quiz')

def load_yaml_template(filename):
    filepath = os.path.join(TEMPLATES_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def main():
    print("="*60)
    print("RESTORING QUIZ TEMPLATES FROM YAML")
    print("="*60)
    
    with engine.connect() as conn:
        # Load the monthly comprehensive quiz template
        template_data = load_yaml_template('monthly_comprehensive.yaml')
        
        name = template_data.get('name', 'monthly_comprehensive')
        version = template_data.get('version', '1.0.0')
        
        # Check if exists by name AND version (unique constraint)
        result = conn.execute(
            text("SELECT id FROM quiz_templates WHERE name = :name AND version = :version"),
            {'name': name, 'version': version}
        ).fetchone()
        
        now = datetime.now(timezone.utc)
        questions_json = json.dumps(template_data.get('questions', []))
        metadata = template_data.get('metadata', {})
        
        if result:
            print(f"ℹ️  Template already exists: {name} v{version}")
        else:
            # Insert new - only use columns that exist in the model
            template_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO quiz_templates (id, name, version, questions, is_active, description, category, created_at, updated_at)
                VALUES (:id, :name, :version, CAST(:questions AS jsonb), true, :description, :category, :now, :now)
            """), {
                'id': template_id,
                'name': name,
                'version': version,
                'questions': questions_json,
                'description': template_data.get('description', ''),
                'category': template_data.get('category', 'monthly_comprehensive'),
                'now': now
            })
            print(f"✅ Created: {name} v{version} ({len(template_data.get('questions', []))} questions)")
        
        conn.commit()
    
    print("\n" + "="*60)
    print("✅ QUIZ TEMPLATES RESTORED!")
    print("="*60)

if __name__ == "__main__":
    main()
