"""
Script to populate flow templates from YAML files into the database.
"""
import os
import sys
import yaml
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def load_yaml_template(file_path: Path) -> dict:
    """Load and parse YAML template file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def populate_templates():
    """Populate flow templates from YAML files."""
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return False
    
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("=" * 80)
    print("POPULATING FLOW TEMPLATES FROM YAML FILES")
    print("=" * 80)
    
    # Template files to process
    template_files = [
        ("flows/initial_15_days.yaml", "initial_15_days", "Initial 15 Days Onboarding Flow"),
        ("flows/days_16_45.yaml", "days_16_45", "Days 16-45 Engagement Flow"),
        ("flows/monthly_recurring.yaml", "monthly_recurring", "Monthly Recurring Maintenance Flow"),
    ]
    
    templates_dir = Path(__file__).parent.parent / "app" / "templates"
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                
                for file_path, kind_key, kind_display in template_files:
                    full_path = templates_dir / file_path
                    
                    print(f"\n{'='*80}")
                    print(f"Processing: {file_path}")
                    print(f"{'='*80}")
                    
                    if not full_path.exists():
                        print(f"  ✗ File not found: {full_path}")
                        continue
                    
                    # Load YAML template
                    template_data = load_yaml_template(full_path)
                    
                    # 1. Ensure flow_kind exists
                    print(f"\n1. Checking flow_kind: {kind_key}")
                    cur.execute("""
                        SELECT id FROM flow_kinds WHERE kind_key = %s
                    """, (kind_key,))
                    
                    kind_result = cur.fetchone()
                    
                    if kind_result:
                        kind_id = kind_result[0]
                        print(f"   ✓ Flow kind exists: {kind_id}")
                    else:
                        # Create flow_kind
                        cur.execute("""
                            INSERT INTO flow_kinds (kind_key, display_name, description, is_active)
                            VALUES (%s, %s, %s, true)
                            RETURNING id
                        """, (
                            kind_key,
                            kind_display,
                            template_data.get('description', '')
                        ))
                        kind_id = cur.fetchone()[0]
                        conn.commit()
                        print(f"   ✓ Created flow kind: {kind_id}")
                    
                    # 2. Check if template version already exists
                    print(f"\n2. Checking template version")
                    cur.execute("""
                        SELECT id, version_number FROM flow_template_versions
                        WHERE flow_kind_id = %s
                        ORDER BY version_number DESC
                        LIMIT 1
                    """, (kind_id,))
                    
                    existing = cur.fetchone()
                    
                    if existing:
                        template_id, current_version = existing
                        print(f"   ⚠ Template already exists: {template_id} (v{current_version})")
                        print(f"   Updating existing template...")
                        
                        # Update existing template
                        cur.execute("""
                            UPDATE flow_template_versions
                            SET 
                                template_name = %s,
                                description = %s,
                                steps = %s,
                                metadata = %s,
                                is_active = true,
                                is_draft = false,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                            RETURNING id
                        """, (
                            template_data.get('name', kind_display),
                            template_data.get('description', ''),
                            psycopg.types.json.Jsonb(template_data.get('messages', {})),
                            psycopg.types.json.Jsonb(template_data.get('metadata', {})),
                            template_id
                        ))
                        
                        updated_id = cur.fetchone()[0]
                        conn.commit()
                        print(f"   ✓ Updated template: {updated_id}")
                        
                    else:
                        # Create new template
                        print(f"   Creating new template...")
                        
                        cur.execute("""
                            INSERT INTO flow_template_versions (
                                flow_kind_id,
                                version_number,
                                template_name,
                                description,
                                steps,
                                metadata,
                                is_active,
                                is_draft,
                                published_at,
                                created_by
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, true, false, CURRENT_TIMESTAMP, %s)
                            RETURNING id
                        """, (
                            kind_id,
                            2,  # Version 2 as per YAML
                            template_data.get('name', kind_display),
                            template_data.get('description', ''),
                            psycopg.types.json.Jsonb(template_data.get('messages', {})),
                            psycopg.types.json.Jsonb(template_data.get('metadata', {})),
                            None  # created_by (system)
                        ))
                        
                        new_id = cur.fetchone()[0]
                        conn.commit()
                        print(f"   ✓ Created template: {new_id}")
                    
                    # 3. Now populate flow_messages table
                    print(f"\n3. Populating flow_messages")
                    
                    # Get the template ID (either updated or newly created)
                    cur.execute("""
                        SELECT id FROM flow_template_versions
                        WHERE flow_kind_id = %s
                        ORDER BY version_number DESC
                        LIMIT 1
                    """, (kind_id,))
                    
                    template_id = cur.fetchone()[0]
                    
                    # Delete existing messages for this template
                    cur.execute("""
                        DELETE FROM flow_messages
                        WHERE flow_template_version_id = %s
                    """, (template_id,))
                    
                    deleted_count = cur.rowcount
                    if deleted_count > 0:
                        print(f"   Deleted {deleted_count} existing messages")
                    
                    # Insert messages
                    messages = template_data.get('messages', {})
                    inserted_count = 0
                    
                    for step_num, message_data in messages.items():
                        # Convert step_num to int if it's a string
                        step_number = int(step_num) if isinstance(step_num, str) else step_num
                        
                        # Extract message text from various possible fields
                        message_text = message_data.get('base_content', '')
                        if not message_text:
                            message_text = message_data.get('ai_instructions', '')
                        
                        # Extract message type
                        message_type = message_data.get('message_type', 'text')
                        
                        # Extract buttons if present
                        buttons = None
                        if 'interactive_elements' in message_data:
                            interactive = message_data['interactive_elements']
                            if interactive.get('type') == 'buttons' and 'options' in interactive:
                                buttons = psycopg.types.json.Jsonb(interactive['options'])
                        
                        # Extract list items if present
                        list_items = None
                        if 'interactive_elements' in message_data:
                            interactive = message_data['interactive_elements']
                            if interactive.get('type') == 'list' and 'options' in interactive:
                                list_items = psycopg.types.json.Jsonb(interactive['options'])
                        
                        # Extract delay
                        delay_seconds = 0
                        if 'follow_up' in message_data:
                            delay_seconds = message_data['follow_up'].get('delay_seconds', 0)
                        
                        # Create message key
                        message_key = f"{kind_key}_day_{step_number}"
                        
                        # Insert message
                        cur.execute("""
                            INSERT INTO flow_messages (
                                flow_template_version_id,
                                step_number,
                                message_key,
                                message_text,
                                message_type,
                                buttons,
                                list_items,
                                delay_seconds
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            template_id,
                            step_number,
                            message_key,
                            message_text,
                            message_type,
                            buttons,
                            list_items,
                            delay_seconds
                        ))
                        
                        inserted_count += 1
                    
                    conn.commit()
                    print(f"   ✓ Inserted {inserted_count} messages")
                    
                    print(f"\n✓ Successfully processed {file_path}")
                
                print("\n" + "=" * 80)
                print("SUMMARY")
                print("=" * 80)
                
                # Count total templates and messages
                cur.execute("SELECT COUNT(*) FROM flow_template_versions WHERE is_active = true")
                total_templates = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM flow_messages")
                total_messages = cur.fetchone()[0]
                
                print(f"\nActive templates: {total_templates}")
                print(f"Total messages: {total_messages}")
                
                print("\n✓ ALL TEMPLATES POPULATED SUCCESSFULLY!")
                print("=" * 80)
                
                return True
                
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = populate_templates()
    sys.exit(0 if success else 1)
