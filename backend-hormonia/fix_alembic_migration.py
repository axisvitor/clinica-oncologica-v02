#!/usr/bin/env python3
"""
Fix Alembic migration chain and apply metadata column fix.
"""

import sys
import os
import subprocess
import logging

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_alembic_status():
    """Check current Alembic migration status."""
    try:
        print("🔍 Checking Alembic migration status...")
        
        # Check current revision
        result = subprocess.run([
            sys.executable, "-m", "alembic", "current"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        print("Current revision:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        # Check migration history
        result = subprocess.run([
            sys.executable, "-m", "alembic", "history"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        print("\nMigration history:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error checking Alembic status: {e}")
        return False

def run_migration():
    """Run the metadata column migration."""
    try:
        print("🔄 Running Alembic upgrade...")
        
        # Run alembic upgrade
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        print("Migration output:")
        print(result.stdout)
        
        if result.returncode == 0:
            print("✅ Migration completed successfully")
            return True
        else:
            print("❌ Migration failed")
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        return False

def reset_circuit_breaker():
    """Reset the circuit breaker."""
    try:
        print("🔄 Resetting circuit breaker...")
        from app.utils.db_retry import reset_circuit_breaker
        reset_circuit_breaker()
        print("✅ Circuit breaker reset successfully")
        return True
    except Exception as e:
        print(f"❌ Error resetting circuit breaker: {e}")
        return False

def test_metadata_column():
    """Test if metadata column is accessible."""
    try:
        print("🔍 Testing metadata column access...")
        
        from app.core.database import get_scoped_session
        from sqlalchemy import text
        
        with get_scoped_session() as session:
            # Test metadata column specifically
            result = session.execute(text("SELECT metadata FROM patients LIMIT 1")).fetchone()
            print(f"   ✅ Metadata column accessible")
            
            # Test full patient query (like SQLAlchemy ORM does)
            result = session.execute(text("SELECT * FROM patients LIMIT 1")).fetchone()
            print(f"   ✅ Full patient query works")
            
        return True
        
    except Exception as e:
        print(f"❌ Metadata column test failed: {e}")
        logger.error(f"Metadata test error: {e}", exc_info=True)
        return False

def main():
    """Run all fixes."""
    print("🚀 Fixing Alembic migration and metadata column issue")
    print("=" * 60)
    
    success = True
    
    # 1. Check Alembic status
    print("\n1. Checking Alembic Status:")
    if not check_alembic_status():
        print("   ⚠️ Alembic status check had issues, continuing...")
    
    # 2. Run migration
    print("\n2. Running Migration:")
    if not run_migration():
        success = False
    
    # 3. Reset circuit breaker
    print("\n3. Resetting Circuit Breaker:")
    if not reset_circuit_breaker():
        success = False
    
    # 4. Test metadata column
    print("\n4. Testing Metadata Column:")
    if not test_metadata_column():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All fixes applied successfully!")
        print("The patients endpoint should now work correctly.")
    else:
        print("❌ Some fixes failed. Check the logs above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())