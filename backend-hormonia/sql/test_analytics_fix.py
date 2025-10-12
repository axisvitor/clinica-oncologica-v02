#!/usr/bin/env python3
"""
Test that the analytics service can now query messages without errors.
"""
import os
import sys
sys.path.append('.')

from app.core.database import get_db_service_role
from app.services.analytics import AnalyticsService
from sqlalchemy import text

def test_analytics_fix():
    """Test that analytics queries work after adding delivery_status column."""
    db = next(get_db_service_role())
    
    try:
        # Test basic Message query
        print("Testing basic Message query...")
        result = db.execute(text("SELECT COUNT(*) FROM messages"))
        count = result.scalar()
        print(f"✅ Messages table has {count} records")
        
        # Test delivery_status column specifically
        print("Testing delivery_status column...")
        result = db.execute(text("SELECT delivery_status FROM messages LIMIT 1"))
        print("✅ delivery_status column is accessible")
        
        # Test analytics service
        print("Testing AnalyticsService...")
        analytics = AnalyticsService(db)
        
        # Test the method that was failing
        try:
            dashboard_data = analytics.get_dashboard_data()
            print("✅ Dashboard data generation successful!")
            print(f"   Total patients: {dashboard_data.total_patients}")
            print(f"   Messages today: {dashboard_data.messages_today}")
            print(f"   Active patients: {dashboard_data.active_patients}")
        except Exception as e:
            print(f"❌ Dashboard data generation failed: {e}")
            
    except Exception as e:
        print(f'❌ Test failed: {e}')
    finally:
        db.close()

if __name__ == '__main__':
    test_analytics_fix()