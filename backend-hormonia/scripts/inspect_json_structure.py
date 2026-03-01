import sys
import os
sys.path.append(os.getcwd())
from app.database import SessionLocal
from sqlalchemy import text
import json

def inspect_raw_structure():
    db = SessionLocal()
    try:
        print('=== Raw JSON Structure for onboarding ===\n')
        
        query = text("""
            SELECT ftv.steps
            FROM flow_template_versions ftv 
            JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id 
            WHERE fk.kind_key = 'onboarding' AND ftv.is_active = true
            ORDER BY ftv.version_number DESC
            LIMIT 1
        """)
        res = db.execute(query).fetchone()
        if res:
            steps = res[0]
            if isinstance(steps, str): 
                steps = json.loads(steps)
            
            # Print full structure for first 3 items
            print(f'Total steps in list: {len(steps)}')
            print(f'Type: {type(steps)}')
            print('\n--- First 3 steps (raw) ---')
            for i, step in enumerate(steps[:3]):
                print(f'\nStep {i+1}:')
                print(json.dumps(step, indent=2, ensure_ascii=False))
                
            # Check if there's a 'messages' array inside each step
            print('\n--- Checking for nested messages ---')
            for step in steps[:3]:
                if isinstance(step, dict):
                    if 'messages' in step:
                        print(f"Day {step.get('day')}: Found 'messages' array with {len(step['messages'])} items")
                    else:
                        print(f"Day {step.get('day')}: No 'messages' array - single message structure")
        else:
            print('No data found')

    finally:
        db.close()

if __name__ == "__main__":
    inspect_raw_structure()
