#!/usr/bin/env python3
"""
Validation script for the enum and database fixes.
Run this after applying the model changes to verify everything works.
"""
import os
import sys
import asyncio
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import get_db
from app.models.message import MessageDirection
from app.models.flow import PatientFlowState
from app.utils.db_retry import reset_circuit_breaker


async def validate_enum_fix():
    """Test that MessageDirection enum works with database"""
    print("🔍 Testing MessageDirection enum...")
    
    try:
        db = next(get_db())
        
        # Test enum value mapping
        assert MessageDirection.OUTBOUND.value == "outbound"
        assert MessageDirection.INBOUND.value == "inbound"
        print("✅ Enum values are correct")
        
        # Test database query with enum
        result = db.execute(
            text("SELECT COUNT(*) FROM messages WHERE direction = :direction"),
            {"direction": MessageDirection.OUTBOUND.value}
        ).scalar()
        print(f"✅ Database query with OUTBOUND enum works: {result} messages")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Enum test failed: {str(e)}")
        return False


async def validate_flow_state_fix():
    """Test that PatientFlowState column mapping works"""
    print("🔍 Testing PatientFlowState column mapping...")
    
    try:
        db = next(get_db())
        
        # Test that we can query flow states without column errors
        result = db.execute(
            text("SELECT COUNT(*) FROM patient_flow_states")
        ).scalar()
        print(f"✅ PatientFlowState query works: {result} flow states")
        
        # Test the model mapping
        flow_states = db.query(PatientFlowState).limit(1).all()
        print("✅ PatientFlowState model loads without column errors")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Flow state test failed: {str(e)}")
        return False


async def validate_circuit_breaker():
    """Test circuit breaker reset and status"""
    print("🔍 Testing circuit breaker...")
    
    try:
        # Reset circuit breaker
        reset_circuit_breaker()
        print("✅ Circuit breaker reset successfully")
        
        from app.utils.db_retry import db_circuit_breaker
        assert db_circuit_breaker.state == "closed"
        assert db_circuit_breaker.failure_count == 0
        print("✅ Circuit breaker is in CLOSED state")
        
        return True
        
    except Exception as e:
        print(f"❌ Circuit breaker test failed: {str(e)}")
        return False


async def main():
    """Run all validation tests"""
    print("🚀 Starting validation of database fixes...\n")
    
    tests = [
        ("Enum Fix", validate_enum_fix),
        ("Flow State Fix", validate_flow_state_fix),
        ("Circuit Breaker", validate_circuit_breaker),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    print("\n" + "="*50)
    print("VALIDATION SUMMARY")
    print("="*50)
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed! The fixes are working correctly.")
        print("\nNext steps:")
        print("1. Run the performance indexes: psql -f add_performance_indexes.sql")
        print("2. Test the dashboard endpoint: GET /api/v1/analytics/dashboard")
        print("3. Test the patients endpoint: GET /api/v1/patients")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())