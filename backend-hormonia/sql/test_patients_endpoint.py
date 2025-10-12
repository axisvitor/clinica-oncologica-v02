#!/usr/bin/env python3
"""
Test the patients endpoint to diagnose the 307 redirect issue.
"""
import os
import sys
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_patients_endpoint():
    """Test the patients endpoint to diagnose redirect issues."""
    
    # Get base URL from environment or use default
    base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    
    # Test different URL variations
    test_urls = [
        f"{base_url}/api/v1/patients",
        f"{base_url}/api/v1/patients/",
        f"{base_url.replace('http://', 'https://')}/api/v1/patients",
        f"{base_url.replace('http://', 'https://')}/api/v1/patients/",
    ]
    
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': 'Test-Client/1.0'
    }
    
    for url in test_urls:
        print(f"\n🔍 Testing URL: {url}")
        
        try:
            # Make request without following redirects
            response = requests.get(
                url, 
                headers=headers, 
                allow_redirects=False,
                timeout=10
            )
            
            print(f"   Status: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            
            if response.status_code in [301, 302, 307, 308]:
                location = response.headers.get('Location', 'No Location header')
                print(f"   Redirect to: {location}")
            
            if response.text:
                print(f"   Body: {response.text[:200]}...")
                
        except requests.exceptions.RequestException as e:
            print(f"   Error: {e}")
    
    # Test with authentication if available
    print(f"\n🔐 Testing with authentication...")
    
    # You would need to add actual authentication token here
    auth_headers = headers.copy()
    # auth_headers['Authorization'] = 'Bearer YOUR_TOKEN_HERE'
    
    try:
        response = requests.get(
            f"{base_url}/api/v1/patients",
            headers=auth_headers,
            allow_redirects=False,
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code in [301, 302, 307, 308]:
            location = response.headers.get('Location', 'No Location header')
            print(f"   Redirect to: {location}")
            
    except requests.exceptions.RequestException as e:
        print(f"   Error: {e}")

if __name__ == '__main__':
    test_patients_endpoint()