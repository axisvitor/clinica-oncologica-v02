"""
Simplified service provider dependency for debugging
"""

from fastapi import Depends
from sqlalchemy.orm import Session
from app.service_provider import ServiceProvider
from app.database import get_db
import logging

logger = logging.getLogger(__name__)


def get_simple_service_provider(db: Session = Depends(get_db)) -> ServiceProvider:
    """
    Simplified service provider dependency for debugging.

    This bypasses the complex session management system to isolate
    the problem.
    """
    try:
        logger.debug("Creating simple ServiceProvider")

        # Skip Redis for now to isolate the problem
        redis_client = None
        logger.debug("Skipping Redis client for debugging")

        # Create ServiceProvider
        provider = ServiceProvider(db, redis_client)
        logger.debug(f"Simple ServiceProvider created: {hex(id(provider))}")

        return provider

    except Exception as e:
        logger.error(f"Error creating simple ServiceProvider: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback

        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise
