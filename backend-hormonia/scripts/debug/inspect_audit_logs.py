"""Script to inspect rules and triggers on audit_logs"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("Checking Rules on 'audit_logs':")
    result = db.execute(text("""
        SELECT 
            r.rulename,
            pg_get_ruledef(r.oid)
        FROM pg_rewrite r
        JOIN pg_class c ON c.oid = r.ev_class
        WHERE c.relname = 'audit_logs'
    """))
    rules = result.fetchall()
    if not rules:
        print("  None")
    for r in rules:
        print(f"  Rule: {r[0]}")
        print(f"  Def:  {r[1]}")

    print("\nChecking Triggers on 'audit_logs':")
    result = db.execute(text("""
        SELECT tgname, pg_get_triggerdef(oid)
        FROM pg_trigger
        WHERE tgrelid = 'audit_logs'::regclass
    """))
    triggers = result.fetchall()
    if not triggers:
        print("  None")
    for t in triggers:
        print(f"  Trigger: {t[0]}")
        print(f"  Def:     {t[1]}")

    # Also check if it's a view?
    result = db.execute(text("SELECT relkind FROM pg_class WHERE relname = 'audit_logs'"))
    row = result.fetchone()
    if row:
        kind = row[0]
        kinds = {'r': 'tables', 'v': 'view', 'm': 'matview', 'f': 'foreign table'}
        print(f"\nRelKind: {kinds.get(kind, kind)}")

finally:
    db.close()
