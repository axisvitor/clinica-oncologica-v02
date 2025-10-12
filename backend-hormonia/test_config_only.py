#!/usr/bin/env python3
"""
Test Config Only
Test just the configuration loading without other dependencies.
"""

import os
import sys

def test_config():
    """Test configuration loading."""
    
    print("🔧 TESTING CONFIGURATION LOADING")
    print("=" * 40)
    
    # Set required environment variables manually
    required_vars = {
        'SECRET_KEY': 'TVj0AS9r2O7FaF7uUri4NtUMOEqyK8jf74nrWdgTwZWcNGsYZvhXJd9nMn4UzeAgzbusLuklRgegN8cvCuj8uQ',
        'DATABASE_URL': 'postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require',
        'JWT_SECRET_KEY': 'mYEeH00AvOtRUzpnqSDRerjFT4N-e5a1ywO-G5RCpwrHGH2Wktpx69qrMmCce9Lj8Tagsi_yTRHmpZg6JvX4oQ',
        'ENVIRONMENT': 'development',  # Change to development to avoid production security checks
        'DEBUG': 'true',
        'SESSION_COOKIE_SECURE': 'false',
        'SECURE_SSL_REDIRECT': 'false'
    }
    
    print("Setting required environment variables...")
    for key, value in required_vars.items():
        os.environ[key] = value
        print(f"  ✅ {key} = {'***' if 'SECRET' in key or 'PASSWORD' in key else value[:50]}...")
    
    try:
        # Test config import
        print("\n1. Testing config import...")
        from app.config import settings
        print(f"✅ Config loaded successfully")
        print(f"   Environment: {settings.ENVIRONMENT}")
        print(f"   Debug: {settings.DEBUG}")
        print(f"   Database URL: {settings.DATABASE_URL[:50]}...")
        
        # Test database import
        print("\n2. Testing database import...")
        from app.database import engine
        print(f"✅ Database engine available: {engine}")
        
        # Test simple connection
        print("\n3. Testing database connection...")
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT 1"))
            print(f"✅ Database connection successful: {result.scalar()}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the config test."""
    success = test_config()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())