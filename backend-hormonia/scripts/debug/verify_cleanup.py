"""Script to verify that all test doctors have been deleted"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    result = db.execute(text("SELECT count(*) FROM users WHERE role = 'doctor' AND (email ILIKE '%test%' OR email ILIKE '%debug%')"))
    count = result.scalar()
    
    if count == 0:
        print("\n✅ VERIFICATION SUCCESSFUL: 0 test doctors remaining.")
    else:
        print(f"\n❌ VERIFICATION FAILED: {count} test doctors still exist.")
        
finally:
    db.close()
