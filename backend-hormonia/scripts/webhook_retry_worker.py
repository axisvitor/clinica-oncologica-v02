#!/usr/bin/env python3
"""
Webhook Retry Worker - Background task for retrying failed webhooks.

P0 FIX #4: Simple background worker that periodically retries failed webhook events
with exponential backoff (60s, 120s, 240s).

Usage:
    python scripts/webhook_retry_worker.py

Configuration:
    - WEBHOOK_RETRY_INTERVAL: Seconds between retry cycles (default: 60)
    - WEBHOOK_RETRY_BATCH_SIZE: Max webhooks to process per cycle (default: 50)
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_db
from app.services.webhook_processor import WebhookProcessor
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/webhook_retry.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)


async def retry_cycle():
    """
    Execute one retry cycle for failed webhooks.

    Returns:
        Number of webhooks successfully retried
    """
    db = next(get_db())
    try:
        processor = WebhookProcessor(db)
        retried_count = await processor.retry_failed_webhooks()

        logger.info(
            f"Webhook retry cycle completed: {retried_count} webhooks retried",
            extra={"retried_count": retried_count, "timestamp": datetime.utcnow().isoformat()}
        )

        return retried_count

    except Exception as e:
        logger.error(f"Error in retry cycle: {e}", exc_info=True)
        return 0
    finally:
        db.close()


async def run_worker(interval_seconds: int = 60):
    """
    Run webhook retry worker in continuous loop.

    Args:
        interval_seconds: Seconds between retry cycles
    """
    logger.info(f"Starting webhook retry worker (interval={interval_seconds}s)")

    cycle_count = 0
    total_retried = 0

    try:
        while True:
            cycle_count += 1
            logger.info(f"Starting retry cycle #{cycle_count}")

            retried_count = await retry_cycle()
            total_retried += retried_count

            logger.info(
                f"Cycle #{cycle_count} complete. Total retried this session: {total_retried}",
                extra={"cycle": cycle_count, "session_total": total_retried}
            )

            # Wait for next cycle
            await asyncio.sleep(interval_seconds)

    except KeyboardInterrupt:
        logger.info(f"Webhook retry worker stopped by user (cycles={cycle_count}, total_retried={total_retried})")
    except Exception as e:
        logger.error(f"Fatal error in webhook retry worker: {e}", exc_info=True)
        raise


def main():
    """Main entry point for webhook retry worker."""
    # Get configuration from environment or use defaults
    interval = int(os.getenv('WEBHOOK_RETRY_INTERVAL', '60'))

    logger.info("=" * 80)
    logger.info("Webhook Retry Worker Starting")
    logger.info(f"Configuration:")
    logger.info(f"  - Retry interval: {interval}s")
    logger.info(f"  - Environment: {getattr(settings, 'ENVIRONMENT', 'development')}")
    logger.info(f"  - Database: {settings.DATABASE_URL[:30]}...")
    logger.info("=" * 80)

    try:
        asyncio.run(run_worker(interval_seconds=interval))
    except KeyboardInterrupt:
        logger.info("Shutting down webhook retry worker...")
    except Exception as e:
        logger.error(f"Webhook retry worker crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
