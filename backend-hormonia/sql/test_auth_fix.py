#!/usr/bin/env python3
"""
Test the authentication fix after removing Supabase references.
"""
import requests
import json

def test_auth_endpoints():
    """Test authentication endpoints after fixing Supabase references."""
    
    base_url = "http://localhost:8000"
    
    # Test endpoints that require authentication
    test_cases = [
        {
            "name": "Patients (should be 401 without auth)",
            "url": f"{base_url}/api/v1/patients",
            "method": "GET",
            "expected_status": 401
        },
        {
            "name": "Auth Me (should be 401 without auth)",
            "url": f"{base_url}/api/v1/auth/me",
            "method": "GET", 
            "expected_status": 401
        },
        {
            "name": "CSRF Token (should work without auth)",
            "url": f"{base_url}/api/v1/csrf-token",
            "method": "GET",
            "expected_status": 200
        }
    ]
    
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    print("🔍 Testing authentication after Supabase removal...")
    
    for test in test_cases:
        print(f"\n📋 Testing: {test['name']}")
        print(f"   URL: {test['url']}")
        
        try:
            response = requests.request(
                test['method'],
                test['url'],
                headers=headers,
                allow_redirects=False,
                timeout=5
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == test['expected_status']:
                print(f"   ✅ Expected status {test['expected_status']}")
            else:
                print(f"   ❌ Expected {test['expected_status']}, got {response.status_code}")
            
            # Check for specific error messages
            if response.status_code == 500:
                print(f"   ❌ Server error - check logs for Supabase errors")
            elif response.status_code == 401:
                print(f"   ✅ Proper authentication required (no server errors)")
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Connection error: {e}")
    
    print(f"\n🎯 Summary:")
    print(f"   - Status 401 = Good (authentication working, no server errors)")
    print(f"   - Status 500 = Bad (server error, possibly Supabase references)")
    print(f"   - Status 200 = Good (endpoint working)")
    print(f"   - Connection errors = Bad (server not running)")

if __name__ == '__main__':
    test_auth_endpoints()