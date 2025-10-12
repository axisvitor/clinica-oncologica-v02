#!/usr/bin/env python3
"""
Check if the metadata column exists in the patients table.
"""

import sys
import os
import asyncio
import logging

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, inspect
from app.core.database import get_scoped_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_metadata_column():
    """Check if metadata column exists in patients table."""
    
    print("🔍 Checking metadata column in patients table")
    print("=" * 50)
    
    try:
        with get_scoped_session() as session:
            # Check table structure
            inspector = inspect(session.bind)
            
            # Get columns for patients table
            columns = inspector.get_columns('patients')
            
            print(f"\n📊 Patients table columns:")
            column_names = []
            for col in columns:
                column_names.append(col['name'])
                print(f"   - {col['name']} ({col['type']})")
            
            # Check if metadata column exists
            if 'metadata' in column_names:
                print(f"\n✅ metadata column EXISTS in patients table")
                
                # Test querying the column
                try:
                    result = session.execute(text("SELECT metadata FROM patients LIMIT 1")).fetchone()
                    print(f"   ✅ Can query metadata column successfully")
                except Exception as e:
                    print(f"   ❌ Error querying metadata column: {e}")
                    
            else:
                print(f"\n❌ metadata column MISSING from patients table")
                print(f"   Available columns: {', '.join(column_names)}")
                
                # Suggest adding the column
                print(f"\n💡 To fix this, run:")
                print(f"   ALTER TABLE patients ADD COLUMN metadata JSONB DEFAULT '{{}}';")
            
            # Check if we can query all columns (like SQLAlchemy does)
            try:
                result = session.execute(text("SELECT * FROM patients LIMIT 1")).fetchone()
                print(f"\n✅ Can query all columns (SELECT *) successfully")
            except Exception as e:
                print(f"\n❌ Error with SELECT * query: {e}")
                
    except Exception as e:
        print(f"\n❌ Database connection error: {e}")
        logger.error(f"Connection error details: {e}", exc_info=True)
        return False
    
    return True

def main():
    """Run the column check."""
    try:
        success = check_metadata_column()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Check failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())