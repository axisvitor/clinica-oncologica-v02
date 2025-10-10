#!/usr/bin/env python3
"""
Quick validation script for CORS test fixes
"""
import sys
import os
sys.path.insert(0, '.')

def validate_cors_config():
    """Validate CORS configuration matches tests"""
    from app.middleware.cors import configure_cors
    from fastapi import FastAPI

    app = FastAPI()
    configure_cors(app)

    # Get CORS middleware
    cors_middleware = None
    for middleware in app.user_middleware:
        if 'CORSMiddleware' in str(middleware.cls):
            cors_middleware = middleware
            break

    if cors_middleware:
        print("✅ CORS Middleware found")
        print(f"   Allow Origins: {cors_middleware.kwargs.get('allow_origins')}")
        print(f"   Allow Headers: {cors_middleware.kwargs.get('allow_headers')}")
        print(f"   Expose Headers: {cors_middleware.kwargs.get('expose_headers')}")
        print(f"   Max Age: {cors_middleware.kwargs.get('max_age')}")
        print(f"   Allow Credentials: {cors_middleware.kwargs.get('allow_credentials')}")
        return True
    else:
        print("❌ CORS Middleware not found")
        return False

if __name__ == "__main__":
    print("Validating CORS configuration...")
    success = validate_cors_config()
    sys.exit(0 if success else 1)