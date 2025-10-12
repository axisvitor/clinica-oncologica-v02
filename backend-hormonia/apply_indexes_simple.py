#!/usr/bin/env python3
"""
Apply performance indexes without CONCURRENTLY (for development).
"""
import os
import sys
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
from app.database import get_db


def apply_indexes():
    """Apply performance indexes to the database"""
    print("🔍 Applying performance indexes (non-concurrent)...")
    
    indexes = [
        # Composite indexes for dashboard performance
        """CREATE INDEX IF NOT EXISTS idx_messages_patient_created_desc
           ON messages(patient_id, created_at DESC)""",
        
        """CREATE INDEX IF NOT EXISTS idx_messages_direction_created_desc
           ON messages(direction, created_at DESC)""",
        
        """CREATE INDEX IF NOT EXISTS idx_messages_patient_direction_created_desc
           ON messages(patient_id, direction, created_at DESC)""",
        
        """CREATE INDEX IF NOT EXISTS idx_alerts_status_created_desc
           ON alerts(status, created_at DESC)""",
        
        """CREATE INDEX IF NOT EXISTS idx_messages_status_created_desc
           ON messages(status, created_at DESC)""",
    ]
    
    try:
        db = next(get_db())
        
        for i, index_sql in enumerate(indexes, 1):
            try:
                print(f"Creating index {i}/{len(indexes)}...")
                db.execute(text(index_sql))
                db.commit()
                print(f"✅ Index {i} created successfully")
            except Exception as e:
                print(f"⚠️  Index {i}: {str(e)}")
                db.rollback()
        
        # Analyze tables
        db.execute(text("ANALYZE messages"))
        db.execute(text("ANALYZE alerts"))
        db.commit()
        print("✅ Tables analyzed")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = apply_indexes()
    if success:
        print("\n🎉 Performance indexes applied! Dashboard should be faster now.")
    else:
        sys.exit(1)