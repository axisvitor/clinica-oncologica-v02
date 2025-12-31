import sys
import os
sys.path.append(os.getcwd())
from app.core.database import SessionLocal
from sqlalchemy import text
import json

def verify_flows():
    db = SessionLocal()
    try:
        print('=== Analyzing Database Structure ===')
        
        def analyze_flow(kind_key):
            query = text(f"""
                SELECT ftv.steps, ftv.version_number
                FROM flow_template_versions ftv 
                JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id 
                WHERE fk.kind_key = '{kind_key}' AND ftv.is_active = true
                ORDER BY ftv.version_number DESC
                LIMIT 1
            """)
            res = db.execute(query).fetchone()
            if res:
                steps = res[0]
                version = res[1]
                if isinstance(steps, str): steps = json.loads(steps)
                
                days = []
                if isinstance(steps, list):
                    for item in steps:
                        if isinstance(item, dict) and 'day' in item:
                             days.append(item['day'])
                
                days.sort()
                print(f'{kind_key} (v{version}): Found {len(days)} steps. Days: {days}')
                return days
            else:
                print(f'{kind_key}: No active version found')
                return []

        print('\n--------------------------------')
        print('INITIAL 15 DAYS:')
        analyze_flow('initial_15_days')
        
        print('\n--------------------------------')
        print('DAYS 16-45:')
        analyze_flow('days_16_45')
        
        print('\n--------------------------------')
        print('MONTHLY RECURRING:')
        analyze_flow('monthly_recurring')
        print('\n--------------------------------')

    finally:
        db.close()

if __name__ == "__main__":
    verify_flows()
