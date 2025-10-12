#!/usr/bin/env python3
"""
Test the fixed endpoints to ensure they work without errors.
"""
import os
import sys
import asyncio
import time
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Import the FastAPI app
try:
    from app.main import app
    client = TestClient(app)
except ImportError as e:
    print(f"❌ Could not import FastAPI app: {e}")
    sys.exit(1)


def test_patients_endpoint():
    """Test the patients endpoint that was failing with column errors"""
    print("🔍 Testing GET /api/v1/patients...")
    
    try:
        start_time = time.time()
        response = client.get("/api/v1/patients")
        duration = (time.time() - start_time) * 1000
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {duration:.2f}ms")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Patients endpoint works! Returned {len(data.get('patients', []))} patients")
            return True
        else:
            print(f"❌ Patients endpoint failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Patients endpoint error: {str(e)}")
        return False


def test_analytics_dashboard():
    """Test the analytics dashboard that was failing with enum errors"""
    print("🔍 Testing GET /api/v1/analytics/dashboard...")
    
    try:
        start_time = time.time()
        response = client.get("/api/v1/analytics/dashboard")
        duration = (time.time() - start_time) * 1000
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {duration:.2f}ms")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Analytics dashboard works!")
            
            # Check for key metrics
            if 'quick_stats' in data:
                stats = data['quick_stats']
                print(f"  - Total patients: {stats.get('total_patients', 'N/A')}")
                print(f"  - Active flows: {stats.get('active_flows', 'N/A')}")
                print(f"  - Messages today: {stats.get('messages_today', 'N/A')}")
            
            return True
        else:
            print(f"❌ Analytics dashboard failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Analytics dashboard error: {str(e)}")
        return False


def test_circuit_breaker_status():
    """Check circuit breaker status"""
    print("🔍 Checking circuit breaker status...")
    
    try:
        from app.utils.db_retry import db_circuit_breaker
        
        print(f"Circuit State: {db_circuit_breaker.state}")
        print(f"Failure Count: {db_circuit_breaker.failure_count}")
        
        if db_circuit_breaker.state == "closed":
            print("✅ Circuit breaker is CLOSED (healthy)")
            return True
        else:
            print(f"⚠️  Circuit breaker is {db_circuit_breaker.state.upper()}")
            return False
            
    except Exception as e:
        print(f"❌ Circuit breaker check failed: {str(e)}")
        return False


def main():
    """Run all endpoint tests"""
    print("🚀 Testing Fixed Endpoints\n")
    
    tests = [
        ("Patients Endpoint", test_patients_endpoint),
        ("Analytics Dashboard", test_analytics_dashboard),
        ("Circuit Breaker Status", test_circuit_breaker_status),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    print("\n" + "="*50)
    print("ENDPOINT TEST SUMMARY")
    print("="*50)
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All endpoints are working correctly!")
        print("The enum and database fixes have been successfully applied.")
    else:
        print("\n⚠️  Some endpoints are still failing. Check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()