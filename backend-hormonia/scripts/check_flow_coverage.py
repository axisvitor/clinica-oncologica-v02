"""
Show all days with messages in each flow
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("=== DIAS COM MENSAGEM POR FLUXO ===\n")
    result = conn.execute(text("""
        SELECT fk.kind_key, ftv.steps 
        FROM flow_template_versions ftv 
        JOIN flow_kinds fk ON fk.id = ftv.flow_kind_id 
        ORDER BY fk.kind_key
    """))
    
    for row in result:
        kind_key = row[0]
        steps = row[1]
        days = sorted([s.get("day") for s in steps if s.get("day")])
        print(f"{kind_key}:")
        print(f"  Total: {len(days)} mensagens")
        print(f"  Dias: {days}")
        
        # Check for gaps
        if kind_key == "onboarding":
            expected = set(range(1, 16))  # Days 1-15
            actual = set(days)
            missing = expected - actual
            if missing:
                print(f"  ⚠️  Dias faltantes: {sorted(missing)}")
        elif kind_key == "daily_follow_up":
            expected = set(range(16, 46))  # Days 16-45
            actual = set(days)
            missing = expected - actual
            if missing:
                print(f"  ⚠️  Dias faltantes: {sorted(missing)}")
        print()
