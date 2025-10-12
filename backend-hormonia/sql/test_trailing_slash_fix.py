#!/usr/bin/env python3
"""
Test the trailing slash fix for API endpoints.
"""
import requests
import json

def test_endpoints():
    """Test various endpoints to verify trailing slash fix."""
    
    base_url = "http://localhost:8000"
    
    # Test endpoints that were fixed
    test_cases = [
        {
            "name": "Patients GET",
            "url": f"{base_url}/api/v1/patients",
            "method": "GET",
            "expected_no_redirect": True
        },
        {
            "name": "Patients GET with slash",
            "url": f"{base_url}/api/v1/patients/",
            "method": "GET",
            "expected_no_redirect": True
        },
        {
            "name": "Messages GET",
            "url": f"{base_url}/api/v1/messages",
            "method": "GET",
            "expected_no_redirect": True
        },
        {
            "name": "Admin Users GET",
            "url": f"{base_url}/api/v1/admin/users",
            "method": "GET",
            "expected_no_redirect": True
        }
    ]
    
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    print("🔍 Testing trailing slash fix...")
    
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
            
            if response.status_code in [301, 302, 307, 308]:
                location = response.headers.get('Location', 'No Location header')
                print(f"   ❌ REDIRECT to: {location}")
                if test['expected_no_redirect']:
                    print(f"   ❌ UNEXPECTED REDIRECT!")
            elif response.status_code in [200, 401, 403]:
                print(f"   ✅ No redirect (expected)")
            else:
                print(f"   ⚠️  Unexpected status: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n🎯 Summary:")
    print(f"   - If you see ✅ 'No redirect' for all tests, the fix worked!")
    print(f"   - If you see ❌ 'REDIRECT', there are still issues")
    print(f"   - Status 401/403 is OK (authentication required)")
    print(f"   - Status 200 is perfect (working endpoint)")

if __name__ == '__main__':
    test_endpoints()