"""
Script to update database schema directly.
Usage: python scripts/update_schema.py
"""
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
# Import models to ensure they are registered
import app.models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting schema update...")
    try:
        # Create only the new tables
        from app.models.system_health import SystemHealthSnapshot, SystemIncident
        
        logger.info("Creating SystemHealthSnapshot table...")
        SystemHealthSnapshot.__table__.create(bind=engine, checkfirst=True)
        
        logger.info("Creating SystemIncident table...")
        SystemIncident.__table__.create(bind=engine, checkfirst=True)
        
        logger.info("Schema update completed successfully.")
    except Exception as e:
        logger.error(f"Schema update failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
