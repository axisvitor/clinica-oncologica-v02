#!/usr/bin/env python3
"""
Apply performance indexes for dashboard analytics.
This script creates the indexes using SQLAlchemy instead of psql.
"""
import os
import sys
from sqlalchemy import text

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import get_db


def apply_indexes():
    """Apply performance indexes to the database"""
    print("🔍 Applying performance indexes...")
    
    indexes = [
        # Index for patient-specific message queries (charts/responses)
        """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_patient_created
           ON messages(patient_id, created_at DESC)""",
        
        # Index for direction-based message counts (daily/previous period trends)
        """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_direction_created
           ON messages(direction, created_at DESC)""",
        
        # Composite index for patient + direction queries
        """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_patient_direction_created
           ON messages(patient_id, direction, created_at DESC)""",
        
        # Index for alert status queries
        """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_status_created
           ON alerts(status, created_at DESC)""",
        
        # Index for message status queries (if needed for dashboard)
        """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_status_created
           ON messages(status, created_at DESC)""",
    ]
    
    analyze_queries = [
        "ANALYZE messages",
        "ANALYZE alerts"
    ]
    
    try:
        db = next(get_db())
        
        # Apply indexes
        for i, index_sql in enumerate(indexes, 1):
            try:
                print(f"Creating index {i}/{len(indexes)}...")
                db.execute(text(index_sql))
                db.commit()
                print(f"✅ Index {i} created successfully")
            except Exception as e:
                print(f"⚠️  Index {i} creation failed (may already exist): {str(e)}")
                db.rollback()
        
        # Run ANALYZE
        print("\nAnalyzing tables...")
        for analyze_sql in analyze_queries:
            try:
                db.execute(text(analyze_sql))
                db.commit()
                print(f"✅ {analyze_sql} completed")
            except Exception as e:
                print(f"❌ {analyze_sql} failed: {str(e)}")
                db.rollback()
        
        db.close()
        print("\n🎉 Performance indexes applied successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to apply indexes: {str(e)}")
        return False


def check_existing_indexes():
    """Check what indexes already exist"""
    print("🔍 Checking existing indexes...")
    
    try:
        db = next(get_db())
        
        result = db.execute(text("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE tablename IN ('messages', 'alerts')
            AND indexname LIKE 'idx_%'
            ORDER BY tablename, indexname
        """))
        
        indexes = result.fetchall()
        
        if indexes:
            print("Existing performance indexes:")
            for index in indexes:
                print(f"  - {index.indexname} on {index.tablename}")
        else:
            print("No performance indexes found")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to check indexes: {str(e)}")
        return False


def main():
    """Main function"""
    print("🚀 Performance Index Application Tool\n")
    
    # Check existing indexes first
    check_existing_indexes()
    print()
    
    # Apply new indexes
    success = apply_indexes()
    
    if success:
        print("\n✅ All done! Dashboard queries should be faster now.")
        print("\nNext steps:")
        print("1. Test the dashboard endpoint: GET /api/v1/analytics/dashboard")
        print("2. Test the patients endpoint: GET /api/v1/patients")
        print("3. Monitor query performance in logs")
    else:
        print("\n⚠️  Some indexes may not have been created. Check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()