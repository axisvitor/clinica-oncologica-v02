#!/usr/bin/env python3
"""
Emergency script to reset the database circuit breaker.
Use this when the circuit breaker is stuck in OPEN state.
"""

import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.db_retry import reset_circuit_breaker
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Reset the circuit breaker and print status."""
    try:
        logger.info("Resetting database circuit breaker...")
        reset_circuit_breaker()
        logger.info("✅ Circuit breaker has been reset to CLOSED state")
        logger.info("Database operations should now be allowed")
        return 0
    except Exception as e:
        logger.error(f"❌ Failed to reset circuit breaker: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())