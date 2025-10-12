#!/usr/bin/env python3
"""
Quick test script to verify patients endpoint is working correctly.
"""

import requests
import json
import sys
from typing import Dict, Any

def test_patients_endpoint():
    """Test the patients endpoint with various parameters."""
    
    base_url = "http://localhost:8000"
    
    # Test cases
    test_cases = [
        {
            "name": "Normal request",
            "params": {"page": 1, "size": 20},
            "expected_status": [200, 401]  # 401 if not authenticated
        },
        {
            "name": "Large size parameter (should be clamped)",
            "params": {"page": 1, "size": 1000},
            "expected_status": [200, 401, 422]  # 422 for validation error
        },
        {
            "name": "Invalid size parameter",
            "params": {"page": 1, "size": -1},
            "expected_status": [200, 401, 422]
        },
        {
            "name": "Maximum allowed size",
            "params": {"page": 1, "size": 100},
            "expected_status": [200, 401]
        },
        {
            "name": "With search parameter",
            "params": {"page": 1, "size": 20, "search": "test"},
            "expected_status": [200, 401]
        }
    ]
    
    print("Testing patients endpoint...")
    print("=" * 50)
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print(f"Parameters: {test_case['params']}")
        
        try:
            response = requests.get(
                f"{base_url}/api/v1/patients",
                params=test_case['params'],
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code in test_case['expected_status']:
                print("✅ PASS - Expected status code")
            else:
                print(f"❌ FAIL - Expected {test_case['expected_status']}, got {response.status_code}")
            
            # Try to parse JSON response
            try:
                response_data = response.json()
                if response.status_code == 200:
                    print(f"Response keys: {list(response_data.keys())}")
                    if 'data' in response_data:
                        print(f"Number of patients: {len(response_data['data'])}")
                        print(f"Total: {response_data.get('total', 'N/A')}")
                        print(f"Page: {response_data.get('page', 'N/A')}")
                        print(f"Limit: {response_data.get('limit', 'N/A')}")
                elif response.status_code == 422:
                    print(f"Validation error: {response_data.get('detail', 'N/A')}")
                elif response.status_code == 401:
                    print("Authentication required (expected)")
                else:
                    print(f"Error response: {response_data}")
            except json.JSONDecodeError:
                print(f"Non-JSON response: {response.text[:200]}...")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
        
        print("-" * 30)
    
    print("\nTesting complete!")

def test_health_endpoint():
    """Test the health endpoint to verify server is running."""
    
    base_url = "http://localhost:8000"
    
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"Health check: {response.status_code}")
        if response.status_code == 200:
            print("✅ Server is running")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to server: {e}")
        return False

if __name__ == "__main__":
    print("Patients Endpoint Test Script")
    print("=" * 40)
    
    # First check if server is running
    if not test_health_endpoint():
        print("\n❌ Server is not running or not accessible.")
        print("Please start the server with: uvicorn app.main:app --reload")
        sys.exit(1)
    
    print()
    test_patients_endpoint()