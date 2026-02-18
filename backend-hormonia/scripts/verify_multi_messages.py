import sys
import os
sys.path.append(os.getcwd())
from app.database import SessionLocal
from sqlalchemy import text
import json
from collections import defaultdict

def verify_multi_message_days():
    db = SessionLocal()
    try:
        print('=== Verificando Mensagens Múltiplas por Dia ===\n')
        
        def analyze_flow_messages(kind_key):
            query = text(f"""
                SELECT ftv.steps, ftv.version_number
                FROM flow_template_versions ftv 
                JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id 
                WHERE fk.kind_key = '{kind_key}' AND ftv.is_active = true
                ORDER BY ftv.version_number DESC
                LIMIT 1
            """)
            res = db.execute(query).fetchone()
            if not res:
                print(f'{kind_key}: No active version found')
                return
            
            steps = res[0]
            version = res[1]
            if isinstance(steps, str): 
                steps = json.loads(steps)
            
            print(f'--- {kind_key} (v{version}) ---')
            
            # Group by day
            messages_per_day = defaultdict(list)
            for step in steps:
                if isinstance(step, dict) and 'day' in step:
                    day = step['day']
                    msg_info = {
                        'order': step.get('message_order', step.get('order', 0)),
                        'delay': step.get('delay_seconds', 0),
                        'content_preview': str(step.get('base_content', step.get('content', '')))[:50]
                    }
                    messages_per_day[day].append(msg_info)
            
            # Print days with multiple messages
            for day in sorted(messages_per_day.keys()):
                msgs = messages_per_day[day]
                if len(msgs) > 1:
                    print(f'  Dia {day}: {len(msgs)} mensagens')
                    for i, m in enumerate(sorted(msgs, key=lambda x: x['order'])):
                        delay_info = f" (delay: {m['delay']}s)" if m['delay'] else ""
                        print(f"    [{i+1}] Order={m['order']}{delay_info}: {m['content_preview']}...")
                else:
                    print(f'  Dia {day}: 1 mensagem')
            
            print()

        analyze_flow_messages('onboarding')
        analyze_flow_messages('daily_follow_up')
        analyze_flow_messages('quiz_mensal')

    finally:
        db.close()

if __name__ == "__main__":
    verify_multi_message_days()
