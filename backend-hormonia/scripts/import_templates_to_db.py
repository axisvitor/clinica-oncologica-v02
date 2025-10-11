#!/usr/bin/env python3
"""
Template Import Script - YAML to PostgreSQL Database
=====================================================

Imports flow and quiz templates from YAML files to database tables for
full CRUD flexibility (create, read, update, delete).

Database Tables:
- quiz_templates: Quiz template storage
- flow_template_versions: Flow template storage
- flow_kinds: Flow type definitions

Usage:
    python scripts/import_templates_to_db.py

Environment:
    Requires DATABASE_URL from .env file
"""

import os
import sys
import yaml
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add backend root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment")

# Create database connection
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def load_yaml_template(template_path: str) -> Dict[str, Any]:
    """Load YAML template file"""
    with open(template_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def import_flow_template(session, template_path: str, flow_type: str):
    """Import flow template to database"""
    print(f"\n[FLOW] Importing flow template: {flow_type}")

    # Load template
    template = load_yaml_template(template_path)

    # First, check/create flow_kind
    flow_kind_query = text("""
        SELECT id FROM flow_kinds WHERE kind_key = :flow_type
    """)
    result = session.execute(flow_kind_query, {"flow_type": flow_type}).fetchone()

    if result:
        flow_kind_id = result[0]
        print(f"  [OK] Using existing flow_kind: {flow_kind_id}")
    else:
        # Create new flow_kind
        flow_kind_id = str(uuid.uuid4())
        insert_kind = text("""
            INSERT INTO flow_kinds (id, kind_key, display_name, description, is_active, created_at, updated_at)
            VALUES (:id, :kind_key, :display_name, :description, :is_active, :created_at, :updated_at)
        """)
        session.execute(insert_kind, {
            "id": flow_kind_id,
            "kind_key": flow_type,
            "display_name": template.get('name', flow_type),
            "description": template.get('description', ''),
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        })
        print(f"  [OK] Created new flow_kind: {flow_kind_id}")

    # Create flow_template_version
    version_id = str(uuid.uuid4())

    # Prepare template data - map to actual table columns
    # Store messages in steps column, metadata separately
    steps_data = template.get('messages', {})
    metadata_data = {
        'flow_type': template.get('flow_type', flow_type),
        'humanization_level': template.get('humanization_level', 'high'),
        'version': template.get('version', '1.0.0'),
        'full_template': template  # Keep full template for reference
    }

    template_data = {
        "id": version_id,
        "flow_kind_id": flow_kind_id,
        "version_number": 1,  # Integer version
        "template_name": template.get('name', flow_type),
        "description": template.get('description', ''),
        "steps": steps_data,
        "metadata": metadata_data,
        "is_active": template.get('is_active', True),
        "is_draft": False,
        "published_at": datetime.now(),
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }

    # Insert flow template version
    insert_version = text("""
        INSERT INTO flow_template_versions
        (id, flow_kind_id, version_number, template_name, description, steps, metadata, is_active, is_draft, published_at, created_at, updated_at)
        VALUES
        (:id, :flow_kind_id, :version_number, :template_name, :description, CAST(:steps AS jsonb), CAST(:metadata AS jsonb), :is_active, :is_draft, :published_at, :created_at, :updated_at)
    """)

    import json
    template_data['steps'] = json.dumps(template_data['steps'])
    template_data['metadata'] = json.dumps(template_data['metadata'])

    session.execute(insert_version, template_data)
    print(f"  [OK] Imported flow template version: {version_id}")
    print(f"    - Name: {template['name']}")
    print(f"    - Version: {template.get('version', '1.0.0')}")
    print(f"    - Messages: {len(template.get('messages', {}))}")

    return version_id


def import_quiz_template(session, template_path: str):
    """Import quiz template to database"""
    print(f"\n[QUIZ] Importing quiz template from: {template_path}")

    # Load template
    template = load_yaml_template(template_path)

    # Create quiz template
    template_id = str(uuid.uuid4())

    # Prepare quiz data - map to actual table columns
    metadata = template.get('metadata', {})

    quiz_data = {
        "id": template_id,
        "name": template.get('name', 'monthly_comprehensive'),
        "version": template.get('version', '1.0.0'),
        "description": template.get('description', ''),
        "is_active": template.get('is_active', True),
        "questions": template.get('questions', []),
        "category": metadata.get('categories', ['general'])[0] if metadata.get('categories') else 'general',
        "tags": metadata.get('categories', []),
        "passing_score": 0,  # Not specified in template
        "time_limit_minutes": metadata.get('estimated_duration_minutes', 10),
        "randomize_questions": False,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }

    # Insert quiz template
    insert_quiz = text("""
        INSERT INTO quiz_templates
        (id, name, version, description, is_active, questions, category, tags, passing_score, time_limit_minutes, randomize_questions, created_at, updated_at)
        VALUES
        (:id, :name, :version, :description, :is_active, CAST(:questions AS jsonb), :category, :tags, :passing_score, :time_limit_minutes, :randomize_questions, :created_at, :updated_at)
    """)

    import json
    quiz_data['questions'] = json.dumps(quiz_data['questions'])

    session.execute(insert_quiz, quiz_data)
    print(f"  [OK] Imported quiz template: {template_id}")
    print(f"    - Name: {template['name']}")
    print(f"    - Version: {template.get('version', '1.0.0')}")
    print(f"    - Questions: {len(template.get('questions', []))}")
    print(f"    - Estimated duration: {template.get('metadata', {}).get('estimated_duration_minutes', 'N/A')} minutes")

    return template_id


def verify_import(session):
    """Verify import success with row counts"""
    print("\n[VERIFY] Database Row Counts:")

    tables = ['flow_kinds', 'flow_template_versions', 'quiz_templates']

    for table in tables:
        count_query = text(f"SELECT COUNT(*) FROM {table}")
        count = session.execute(count_query).scalar()
        print(f"  - {table}: {count} records")


def main():
    """Main import execution"""
    print("=" * 60)
    print("Template Import Script - YAML to PostgreSQL")
    print("=" * 60)

    # Define template paths
    base_path = Path(__file__).parent.parent / "app" / "templates"

    flow_templates = [
        (base_path / "flows" / "initial_15_days.yaml", "initial_15_days"),
        (base_path / "flows" / "days_16_45.yaml", "days_16_45"),
        (base_path / "flows" / "monthly_recurring.yaml", "monthly_recurring")
    ]

    quiz_template = base_path / "quiz" / "monthly_comprehensive.yaml"

    # Start database session
    session = Session()

    try:
        # Import flow templates
        print("\n[IMPORT] Starting Flow Templates Import...")
        flow_ids = []
        for template_path, flow_type in flow_templates:
            if template_path.exists():
                flow_id = import_flow_template(session, str(template_path), flow_type)
                flow_ids.append(flow_id)
            else:
                print(f"  [WARN] Template not found: {template_path}")

        # Import quiz template
        print("\n[IMPORT] Starting Quiz Template Import...")
        if quiz_template.exists():
            quiz_id = import_quiz_template(session, str(quiz_template))
        else:
            print(f"  [WARN] Quiz template not found: {quiz_template}")

        # Commit transaction
        session.commit()
        print("\n[SUCCESS] All templates imported successfully!")

        # Verify import
        verify_import(session)

        # Summary
        print("\n" + "=" * 60)
        print("[SUMMARY] Import Summary:")
        print(f"  - Flow templates imported: {len(flow_ids)}")
        print(f"  - Quiz templates imported: 1")
        print(f"  - Total templates: {len(flow_ids) + 1}")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Error during import: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
