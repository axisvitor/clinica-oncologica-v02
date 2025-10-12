#!/usr/bin/env python3
"""
Test alerts schema compatibility after fixes.
"""
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config import get_settings

def test_alerts_compatibility():
    """Test that alerts table works with our model mappings."""
    print("🔍 Alerts Schema Compatibility Test")
    print("=" * 50)
    
    try:
        settings = get_settings()
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as conn:
            # Check if alerts table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alerts'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("❌ alerts table does not exist")
                return False
            
            print("✅ alerts table exists")
            
            # Check actual column names in database
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'alerts' 
                AND table_schema = 'public'
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
            
            print("\n📊 Actual Database Columns:")
            column_names = []
            for col in columns:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                print(f"   {col[0]}: {col[1]} ({nullable})")
                column_names.append(col[0])
            
            # Check for expected columns based on our model mapping
            expected_mappings = {
                'type': 'alert_type',  # DB column -> Model property
                'message': 'description',  # DB column -> Model property
                'acknowledged': 'status (virtual)',  # DB column -> Model property
                'data': 'quiz_session_id (via JSONB)'  # DB column -> Model property
            }
            
            print(f"\n📊 Column Mapping Validation:")
            for db_col, model_prop in expected_mappings.items():
                if db_col in column_names:
                    print(f"   ✅ {db_col} -> {model_prop}")
                else:
                    print(f"   ❌ {db_col} -> {model_prop} (MISSING)")
            
            # Test a simple query that our model would generate
            try:
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM alerts 
                    WHERE type IS NOT NULL 
                    AND message IS NOT NULL
                """))
                count = result.scalar()
                print(f"\n✅ Basic query works: {count} alerts found")
                
                # Test JSONB query for quiz_session_id
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM alerts 
                    WHERE data->>'quiz_session_id' IS NOT NULL
                """))
                jsonb_count = result.scalar()
                print(f"✅ JSONB query works: {jsonb_count} alerts with quiz_session_id")
                
            except Exception as e:
                print(f"❌ Query test failed: {e}")
                return False
            
    except Exception as e:
        print(f"❌ Error testing alerts compatibility: {e}")
        return False
    
    print(f"\n✅ Alerts compatibility test completed successfully")
    return True

if __name__ == "__main__":
    test_alerts_compatibility()