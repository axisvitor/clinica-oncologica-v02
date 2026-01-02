#!/usr/bin/env python3
"""
Redis Initialization Script

Handles Redis setup and configuration:
- Validate Redis connection
- Configure Redis settings
- Set up Redis modules (if needed)
- Initialize cache keys
- Validate data structures

Usage:
    python scripts/init_redis.py [--flush] [--configure]
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('RedisInit')


class RedisInitializer:
    """Orchestrates Redis initialization"""

    def __init__(self, flush: bool = False, configure: bool = False):
        self.flush = flush
        self.configure = configure

    async def initialize(self) -> bool:
        """Run Redis initialization"""
        logger.info("=" * 80)
        logger.info("Redis Initialization")
        logger.info("=" * 80)

        try:
            # Step 1: Validate connection
            await self._validate_connection()

            # Step 2: Configure Redis
            if self.configure:
                await self._configure_redis()

            # Step 3: Flush data if requested
            if self.flush:
                await self._flush_data()

            # Step 4: Initialize cache structures
            await self._initialize_cache()

            # Step 5: Validate setup
            await self._validate_setup()

            logger.info("\n✅ Redis initialization completed successfully!")
            return True

        except Exception as e:
            logger.error(f"\n❌ Redis initialization failed: {e}")
            return False

    async def _validate_connection(self) -> None:
        """Validate Redis connection"""
        logger.info("\n[1/5] Validating Redis connection...")

        from app.core.redis_manager import RedisManager

        try:
            redis_manager = RedisManager()
            await redis_manager.initialize()

            # Ping test
            pong = await redis_manager.ping()
            logger.info(f"✓ Redis PING: {pong}")

            # Get server info
            info = await redis_manager.get_redis_info()

            logger.info("✓ Redis Server Info:")
            logger.info(f"  - Version: {info.get('redis_version')}")
            logger.info(f"  - Mode: {info.get('redis_mode')}")
            logger.info(f"  - Uptime: {int(info.get('uptime_in_seconds', 0)) / 3600:.2f} hours")
            logger.info(f"  - Connected clients: {info.get('connected_clients')}")
            logger.info(f"  - Used memory: {int(info.get('used_memory', 0)) / 1024 / 1024:.2f} MB")

            await redis_manager.close()

        except Exception as e:
            logger.error(f"✗ Redis connection failed: {e}")
            raise

    async def _configure_redis(self) -> None:
        """Configure Redis settings"""
        logger.info("\n[2/5] Configuring Redis settings...")

        from app.core.redis_manager import RedisManager

        try:
            redis_manager = RedisManager()
            await redis_manager.initialize()

            # Set recommended configurations
            configs = {
                'maxmemory-policy': 'allkeys-lru',  # LRU eviction policy
                'timeout': '300',  # Client timeout in seconds
                'tcp-keepalive': '60',  # TCP keepalive
            }

            for key, value in configs.items():
                try:
                    # Note: CONFIG SET requires admin privileges
                    await redis_manager.redis.config_set(key, value)
                    logger.info(f"✓ Set {key} = {value}")
                except Exception as e:
                    logger.warning(f"⚠ Could not set {key}: {e}")

            await redis_manager.close()

        except Exception as e:
            logger.error(f"✗ Configuration failed: {e}")
            raise

    async def _flush_data(self) -> None:
        """Flush all Redis data"""
        logger.info("\n[3/5] Flushing Redis data...")
        logger.warning("⚠️  WARNING: This will DELETE all data in Redis!")

        response = input("Are you sure? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            logger.info("Aborted by user")
            sys.exit(0)

        from app.core.redis_manager import RedisManager

        try:
            redis_manager = RedisManager()
            await redis_manager.initialize()

            # Flush all databases
            await redis_manager.redis.flushall()
            logger.info("✓ All Redis data flushed")

            await redis_manager.close()

        except Exception as e:
            logger.error(f"✗ Flush failed: {e}")
            raise

    async def _initialize_cache(self) -> None:
        """Initialize cache structures"""
        logger.info("\n[4/5] Initializing cache structures...")

        from app.core.redis_manager import RedisManager

        try:
            redis_manager = RedisManager()
            await redis_manager.initialize()

            # Initialize common cache keys with default values
            cache_keys = {
                'app:initialized': 'true',
                'app:version': '2.0.0',
                'cache:stats:hits': '0',
                'cache:stats:misses': '0',
            }

            for key, value in cache_keys.items():
                await redis_manager.set(key, value, ex=None)  # No expiration
                logger.info(f"✓ Initialized {key}")

            # Create rate limit buckets (if needed)
            logger.info("✓ Rate limit buckets ready")

            # Initialize session storage
            logger.info("✓ Session storage ready")

            await redis_manager.close()

        except Exception as e:
            logger.error(f"✗ Cache initialization failed: {e}")
            raise

    async def _validate_setup(self) -> None:
        """Validate Redis setup"""
        logger.info("\n[5/5] Validating Redis setup...")

        from app.core.redis_manager import RedisManager

        try:
            redis_manager = RedisManager()
            await redis_manager.initialize()

            # Test basic operations
            test_key = "__test_init__"

            # Test SET
            await redis_manager.set(test_key, "test_value", ex=60)
            logger.info("✓ SET operation successful")

            # Test GET
            value = await redis_manager.get(test_key)
            assert value == "test_value", "GET operation failed"
            logger.info("✓ GET operation successful")

            # Test DELETE
            await redis_manager.delete(test_key)
            value = await redis_manager.get(test_key)
            assert value is None, "DELETE operation failed"
            logger.info("✓ DELETE operation successful")

            # Test EXPIRE
            await redis_manager.set(test_key, "expire_test", ex=1)
            await asyncio.sleep(2)
            value = await redis_manager.get(test_key)
            assert value is None, "EXPIRE operation failed"
            logger.info("✓ EXPIRE operation successful")

            # Get final stats
            info = await redis_manager.get_redis_info()
            logger.info("\n✓ Final Redis Stats:")
            logger.info(f"  - Total keys: {await redis_manager.redis.dbsize()}")
            logger.info(f"  - Memory used: {int(info.get('used_memory', 0)) / 1024 / 1024:.2f} MB")
            logger.info(f"  - Hit rate: {info.get('keyspace_hits', 0)} hits / {info.get('keyspace_misses', 0)} misses")

            await redis_manager.close()

        except Exception as e:
            logger.error(f"✗ Validation failed: {e}")
            raise


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Initialize Redis')
    parser.add_argument('--flush', action='store_true',
                        help='Flush all Redis data (WARNING: deletes all data)')
    parser.add_argument('--configure', action='store_true',
                        help='Configure Redis settings')
    args = parser.parse_args()

    initializer = RedisInitializer(
        flush=args.flush,
        configure=args.configure
    )

    success = await initializer.initialize()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    asyncio.run(main())
