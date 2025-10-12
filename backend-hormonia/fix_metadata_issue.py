#!/usr/bin/env python3
"""
Fix the metadata column issue and reset circuit breaker.
"""

import sys
import os
import subprocess
import logging

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.db_retry import reset_circuit_breaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the metadata column migration."""
    try:
        print("🔄 Running metadata column migration...")
        
        # Run alembic upgrade
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        if result.returncode == 0:
            print("✅ Migration completed successfully")
            print(result.stdout)
            return True
        else:
            print("❌ Migration failed")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        return False

def reset_circuit():
    """Reset the circuit breaker."""
    try:
        print("🔄 Resetting circuit breaker...")
        reset_circuit_breaker()
        print("✅ Circuit breaker reset successfully")
        return True
    except Exception as e:
        print(f"❌ Error resetting circuit breaker: {e}")
        return False

def test_connection():
    """Test database connection after fixes."""
    try:
        print("🔍 Testing database connection...")
        
        from app.core.database import get_scoped_session
        from sqlalchemy import text
        
        with get_scoped_session() as session:
            # Test basic query
            result = session.execute(text("SELECT 1 as test")).fetchone()
            print(f"   Basic query: {result}")
            
            # Test patients table query
            result = session.execute(text("SELECT COUNT(*) as count FROM patients")).fetchone()
            print(f"   Patients count: {result}")
            
            # Test metadata column specifically
            result = session.execute(text("SELECT metadata FROM patients LIMIT 1")).fetchone()
            print(f"   Metadata column accessible: ✅")
            
        print("✅ Database connection test successful")
        return True
        
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        logger.error(f"Connection test error: {e}", exc_info=True)
        return False

def main():
    """Run all fixes."""
    print("🚀 Fixing metadata column issue")
    print("=" * 50)
    
    success = True
    
    # 1. Run migration
    if not run_migration():
        success = False
    
    # 2. Reset circuit breaker
    if not reset_circuit():
        success = False
    
    # 3. Test connection
    if not test_connection():
        success = False
    
    if success:
        print("\n🎉 All fixes applied successfully!")
        print("The patients endpoint should now work correctly.")
    else:
        print("\n❌ Some fixes failed. Check the logs above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())