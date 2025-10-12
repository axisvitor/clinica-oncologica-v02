#!/usr/bin/env python3
"""
Test script to identify import issues in the application.
"""

import sys
import traceback

def test_import(module_path, description=""):
    """Test importing a module and report results."""
    try:
        __import__(module_path)
        print(f"✅ {module_path} - {description}")
        return True
    except Exception as e:
        print(f"❌ {module_path} - {description}")
        print(f"   Error: {e}")
        print(f"   Type: {type(e).__name__}")
        return False

def main():
    """Test critical imports."""
    print("🔍 Testing critical imports...")
    print("=" * 60)
    
    # Test basic imports
    imports_to_test = [
        ("app.config", "Application configuration"),
        ("app.database", "Database connectivity"),
        ("app.core.application_factory", "Application factory"),
        ("app.middleware.db_optimization", "DB optimization middleware"),
        ("app.api.v1.admin", "Admin API module"),
        ("app.api.v1.admin.users", "Admin users API"),
        ("app.models.admin", "Admin models"),
        ("app.services.admin_stats_service", "Admin stats service"),
        ("app.utils.cache", "Cache utilities"),
    ]
    
    failed_imports = []
    
    for module_path, description in imports_to_test:
        if not test_import(module_path, description):
            failed_imports.append(module_path)
    
    print("\n" + "=" * 60)
    
    if failed_imports:
        print(f"❌ {len(failed_imports)} imports failed:")
        for module in failed_imports:
            print(f"   - {module}")
        
        # Try to import the main app
        print("\n🔍 Testing main application import...")
        try:
            from app.main import app
            print("✅ Main application imported successfully")
        except Exception as e:
            print("❌ Main application import failed:")
            print(f"   Error: {e}")
            traceback.print_exc()
    else:
        print("✅ All imports successful!")
        
        # Try to import the main app
        print("\n🔍 Testing main application import...")
        try:
            from app.main import app
            print("✅ Main application imported successfully")
            print("🎉 Application should start without import errors!")
        except Exception as e:
            print("❌ Main application import failed:")
            print(f"   Error: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()