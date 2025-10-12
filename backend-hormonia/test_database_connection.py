#!/usr/bin/env python3
"""
Test database connection and circuit breaker status.
"""

import sys
import os
import asyncio
import logging

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import test_connection, get_pool_status
from app.utils.db_retry import db_circuit_breaker, reset_circuit_breaker
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_database():
    """Test database connection and circuit breaker."""
    
    print("🔍 Database Connection Test")
    print("=" * 50)
    
    # 1. Check circuit breaker status
    print(f"\n📊 Circuit Breaker Status:")
    print(f"   State: {db_circuit_breaker.state}")
    print(f"   Failure Count: {db_circuit_breaker.failure_count}")
    print(f"   Failure Threshold: {db_circuit_breaker.failure_threshold}")
    
    if db_circuit_breaker.state == "open":
        print("   ⚠️  Circuit breaker is OPEN - resetting...")
        reset_circuit_breaker()
        print("   ✅ Circuit breaker reset to CLOSED")
    
    # 2. Test basic connection
    print(f"\n🔌 Testing Database Connection:")
    try:
        connection_status = test_connection(use_service_role=True)
        print(f"   Status: {connection_status['status']}")
        print(f"   Test Query: {connection_status.get('test_query_result', 'N/A')}")
        print(f"   Timestamp: {connection_status.get('timestamp', 'N/A')}")
        
        if connection_status['status'] == 'healthy':
            print("   ✅ Database connection is healthy")
        else:
            print(f"   ❌ Database connection failed: {connection_status.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"   ❌ Connection test failed: {e}")
    
    # 3. Test pool status
    print(f"\n🏊 Connection Pool Status:")
    try:
        pool_status = get_pool_status(use_service_role=True)
        print(f"   Engine Type: {pool_status['engine_type']}")
        print(f"   Pool Size: {pool_status['pool_size']}")
        print(f"   Checked In: {pool_status['checked_in']}")
        print(f"   Checked Out: {pool_status['checked_out']}")
        print(f"   Overflow: {pool_status['overflow']}")
        
    except Exception as e:
        print(f"   ❌ Pool status check failed: {e}")
    
    # 4. Test simple query
    print(f"\n🔍 Testing Simple Query:")
    try:
        from app.core.database import get_scoped_session
        
        with get_scoped_session() as session:
            result = session.execute(text("SELECT 1 as test, current_timestamp as now")).fetchone()
            print(f"   Query Result: {result}")
            print("   ✅ Simple query successful")
            
    except Exception as e:
        print(f"   ❌ Simple query failed: {e}")
        logger.error(f"Query error details: {e}", exc_info=True)
    
    print(f"\n🎯 Test Complete!")

def main():
    """Run the database test."""
    try:
        asyncio.run(test_database())
        return 0
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())