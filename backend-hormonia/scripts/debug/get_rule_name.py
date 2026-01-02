"""Script to get the rule name for audit_logs delete rule"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # 4 = DELETE (reference: pg_rewrite.ev_type)
    result = db.execute(text("SELECT rulename, ev_type FROM pg_rewrite WHERE ev_class = 'audit_logs'::regclass"))
    rules = result.fetchall()
    print(f"Rules on audit_logs: {len(rules)}")
    for r in rules:
        type_map = {'1': 'SELECT', '2': 'UPDATE', '3': 'INSERT', '4': 'DELETE'}
        print(f"  Name: {r[0]} | Type: {type_map.get(r[1], r[1])}")
finally:
    db.close()
