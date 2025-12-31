"""Check quiz_responses table columns"""
import sys
sys.path.insert(0, '.')
from app.database import engine
from sqlalchemy import inspect

insp = inspect(engine)
cols = insp.get_columns('quiz_responses')

print("quiz_responses columns:")
for c in cols:
    print(f"  {c['name']}: nullable={c['nullable']}, type={c['type']}")
