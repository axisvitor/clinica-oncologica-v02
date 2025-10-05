#!/usr/bin/env python3
"""
Verification script for AI Redis Cache migration to unified RedisManager.
Tests that the migrated service works correctly with the new unified manager.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.services.ai_redis_cache import get_ai_cache_service
from app.core.redis_unified import get_async_redis, cleanup_redis
from uuid import uuid4


async def test_basic_operations():
    """Test basic cache operations."""
    print("\n=== Testing Basic Cache Operations ===")

    cache = await get_ai_cache_service()
    test_key = f"test:migration:{uuid4()}"
    test_data = {"test": "migration_data", "timestamp": "2025-10-04"}

    # Test set
    print(f"Setting cache key: {test_key}")
    success = await cache.set_cached(test_key, test_data, 60)
    print(f"  Set result: {'SUCCESS' if success else 'FAILED'}")

    # Test get
    print(f"Getting cache key: {test_key}")
    result = await cache.get_cached(test_key)
    print(f"  Get result: {result}")
    print(f"  Data matches: {result == test_data if result else False}")

    return success and result == test_data


async def test_unified_manager():
    """Test that we're using the unified manager."""
    print("\n=== Testing Unified Manager Integration ===")

    cache = await get_ai_cache_service()

    # Get client from cache service
    cache_client = await cache.get_client()
    print(f"Cache client type: {type(cache_client).__name__}")

    # Get client from unified manager
    unified_client = await get_async_redis()
    print(f"Unified client type: {type(unified_client).__name__}")

    # Both should be Redis clients
    same_type = type(cache_client) == type(unified_client)
    print(f"Same client type: {same_type}")

    # Test ping
    if cache_client:
        pong = await cache_client.ping()
        print(f"Cache client ping: {pong}")

    return same_type and pong


async def test_metrics():
    """Test metrics collection."""
    print("\n=== Testing Metrics Collection ===")

    cache = await get_ai_cache_service()

    # Perform some operations
    await cache.get_cached(f"test:miss:{uuid4()}")  # Miss
    await cache.set_cached(f"test:hit:{uuid4()}", {"data": "value"}, 60)

    # Get metrics
    metrics = await cache.get_metrics()
    print(f"Metrics: {metrics}")

    # Verify structure
    has_cache_metrics = "cache_metrics" in metrics
    has_redis_available = "redis_available" in metrics
    has_ttl_config = "ttl_config" in metrics

    print(f"Has cache_metrics: {has_cache_metrics}")
    print(f"Has redis_available: {has_redis_available}")
    print(f"Has ttl_config: {has_ttl_config}")

    return all([has_cache_metrics, has_redis_available, has_ttl_config])


async def test_health_check():
    """Test health check."""
    print("\n=== Testing Health Check ===")

    cache = await get_ai_cache_service()
    health = await cache.health_check()

    print(f"Health status: {health}")

    is_healthy = health.get("status") == "healthy"
    is_connected = health.get("redis_connected") == True

    print(f"Is healthy: {is_healthy}")
    print(f"Is connected: {is_connected}")

    return is_healthy and is_connected


async def test_patient_operations():
    """Test patient-specific cache operations."""
    print("\n=== Testing Patient Cache Operations ===")

    cache = await get_ai_cache_service()
    patient_id = uuid4()

    # Test cache warming
    insights_data = {"insights": ["insight1", "insight2"]}
    recs_data = {"recommendations": ["rec1", "rec2"]}

    print(f"Warming cache for patient: {patient_id}")
    warmed = await cache.warm_patient_cache(patient_id, insights_data, recs_data)
    print(f"  Warmed entries: {warmed}")

    # Test invalidation
    print(f"Invalidating cache for patient: {patient_id}")
    invalidated = await cache.invalidate_patient_cache(patient_id)
    print(f"  Invalidated entries: {invalidated}")

    return warmed >= 2 and invalidated >= 2


async def verify_no_close_method():
    """Verify that close() method was removed."""
    print("\n=== Verifying No Close Method ===")

    cache = await get_ai_cache_service()
    has_close = hasattr(cache, 'close')

    print(f"Has close() method: {has_close}")
    print(f"Status: {'FAILED - close() should not exist' if has_close else 'SUCCESS - close() removed'}")

    return not has_close


async def main():
    """Run all verification tests."""
    print("=" * 60)
    print("AI Redis Cache Migration Verification")
    print("=" * 60)

    results = {}

    try:
        # Run tests
        results['basic_ops'] = await test_basic_operations()
        results['unified_manager'] = await test_unified_manager()
        results['metrics'] = await test_metrics()
        results['health_check'] = await test_health_check()
        results['patient_ops'] = await test_patient_operations()
        results['no_close'] = await verify_no_close_method()

        # Print summary
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)

        for test_name, passed in results.items():
            status = "PASSED" if passed else "FAILED"
            symbol = "✓" if passed else "✗"
            print(f"{symbol} {test_name:20s}: {status}")

        # Overall result
        all_passed = all(results.values())
        print("\n" + "=" * 60)
        if all_passed:
            print("SUCCESS: All verification tests passed!")
            print("The AI Redis Cache migration is complete and working correctly.")
        else:
            print("FAILURE: Some verification tests failed!")
            print("Please review the failed tests above.")
        print("=" * 60)

        return 0 if all_passed else 1

    except Exception as e:
        print(f"\nERROR during verification: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup
        print("\nCleaning up Redis connections...")
        await cleanup_redis()
        print("Cleanup complete.")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
