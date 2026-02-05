"""
Cache invalidation service usage examples.

This module demonstrates various usage patterns for the centralized
CacheInvalidationService.
"""

import asyncio
from uuid import UUID

from app.services.cache import (
    CacheInvalidationService,
    CacheKeyBuilder,
    InvalidationStrategy,
)


# Example 1: Basic single key invalidation
async def example_single_key_invalidation():
    """Invalidate a single cache key."""
    service = CacheInvalidationService()
    key_builder = CacheKeyBuilder()

    # Build and invalidate a single patient cache key
    patient_id = "123e4567-e89b-12d3-a456-426614174000"
    key = key_builder.build("patient", patient_id)

    success = await service.invalidate(
        key=key,
        strategy=InvalidationStrategy.SINGLE,
    )
    print(f"Single key invalidation: {success}")


# Example 2: Pattern-based invalidation
async def example_pattern_invalidation():
    """Invalidate all keys matching a pattern."""
    service = CacheInvalidationService()
    key_builder = CacheKeyBuilder()

    # Invalidate all patient list queries
    pattern = key_builder.build_pattern("patient", operation="list")

    success = await service.invalidate(
        pattern=pattern,
        strategy=InvalidationStrategy.PATTERN,
    )
    print(f"Pattern invalidation: {success}")


# Example 3: Tag-based invalidation
async def example_tag_invalidation():
    """Tag keys and invalidate by tags."""
    service = CacheInvalidationService()
    key_builder = CacheKeyBuilder()

    # Tag some keys
    patient_key = key_builder.build("patient", "123")
    await service.tag_key(patient_key, ["patient", "active", "oncology"])

    quiz_key = key_builder.build("quiz", "456")
    await service.tag_key(quiz_key, ["quiz", "active"])

    # Invalidate all active items
    success = await service.invalidate(
        tags=["active"],
        strategy=InvalidationStrategy.TAGS,
    )
    print(f"Tag-based invalidation: {success}")


# Example 4: Entity-level invalidation (recommended)
async def example_entity_invalidation():
    """Invalidate all caches for an entity."""
    service = CacheInvalidationService()

    # High-level entity invalidation - invalidates:
    # - patient:123
    # - patient:list:*
    # - patient:count:*
    # - patient:search:*
    success = await service.invalidate_entity(
        entity="patient",
        identifier="123",
        cascade=True,
    )
    print(f"Entity invalidation: {success}")


# Example 5: Cascade invalidation
async def example_cascade_invalidation():
    """Invalidate a key and all related keys."""
    service = CacheInvalidationService()
    key_builder = CacheKeyBuilder()

    patient_key = key_builder.build("patient", "123")

    success = await service.invalidate(
        key=patient_key,
        strategy=InvalidationStrategy.CASCADE,
    )
    print(f"Cascade invalidation: {success}")


# Example 6: Building complex keys with parameters
async def example_complex_keys():
    """Build cache keys with query parameters."""
    key_builder = CacheKeyBuilder()

    # Key for a filtered patient list
    params = {
        "status": "active",
        "treatment_type": "oncology",
        "page": 1,
        "limit": 20,
    }

    key = key_builder.build(
        entity="patient",
        operation="list",
        params=params,
    )
    print(f"Complex key: {key}")

    # Parse the key back
    components = key_builder.parse(key)
    print(f"Parsed components: {components}")


# Example 7: Multiple invalidation strategies together
async def example_combined_invalidation():
    """Combine multiple invalidation strategies."""
    service = CacheInvalidationService()
    key_builder = CacheKeyBuilder()

    patient_id = "123"

    # 1. Invalidate specific patient
    await service.invalidate(
        key=key_builder.build("patient", patient_id),
        strategy=InvalidationStrategy.SINGLE,
    )

    # 2. Invalidate all patient lists
    await service.invalidate(
        pattern=key_builder.build_pattern("patient", operation="list"),
        strategy=InvalidationStrategy.PATTERN,
    )

    # 3. Invalidate by tags
    await service.invalidate(
        tags=["patient_updated"],
        strategy=InvalidationStrategy.TAGS,
    )

    print("Combined invalidation complete")


# Example 8: Error handling and metrics
async def example_error_handling():
    """Handle errors and check metrics."""
    service = CacheInvalidationService(max_retries=3, retry_delay=0.1)

    try:
        # Attempt invalidation
        success = await service.invalidate_entity("patient", "123")

        # Get metrics
        metrics = await service.get_metrics()
        print(f"Cache metrics: {metrics}")

    except Exception as e:
        print(f"Invalidation failed: {e}")


# Example 9: Using in a service class
class PatientService:
    """Example service using cache invalidation."""

    def __init__(self):
        self.cache_invalidation = CacheInvalidationService()
        self.key_builder = CacheKeyBuilder()

    async def update_patient(self, patient_id: UUID, data: dict):
        """Update patient and invalidate caches."""
        # 1. Update in database
        # ... database update code ...

        # 2. Invalidate caches (best-effort)
        try:
            await self.cache_invalidation.invalidate_entity(
                entity="patient",
                identifier=str(patient_id),
                cascade=True,
            )
        except Exception as e:
            print(f"Cache invalidation warning: {e}")

        return True

    async def delete_patient(self, patient_id: UUID):
        """Delete patient and invalidate caches."""
        # 1. Soft delete in database
        # ... database delete code ...

        # 2. Invalidate caches with cascade
        try:
            key = self.key_builder.build("patient", str(patient_id))
            await self.cache_invalidation.invalidate(
                key=key,
                strategy=InvalidationStrategy.CASCADE,
            )
        except Exception as e:
            print(f"Cache invalidation warning: {e}")

        return True


# Example 10: Batch operations
async def example_batch_invalidation():
    """Invalidate multiple keys efficiently."""
    service = CacheInvalidationService()
    key_builder = CacheKeyBuilder()

    # Invalidate multiple patients
    patient_ids = ["123", "456", "789"]

    # Use pattern for efficiency
    for patient_id in patient_ids:
        pattern = key_builder.build_pattern("patient", patient_id)
        await service.invalidate(
            pattern=pattern,
            strategy=InvalidationStrategy.PATTERN,
        )

    print(f"Batch invalidation complete for {len(patient_ids)} patients")


# Example 11: Custom namespacing
async def example_custom_namespace():
    """Use custom namespaces for different environments."""
    # Production namespace
    prod_builder = CacheKeyBuilder(namespace="prod", version="v2")
    prod_key = prod_builder.build("patient", "123")
    print(f"Production key: {prod_key}")

    # Staging namespace
    staging_builder = CacheKeyBuilder(namespace="staging", version="v2")
    staging_key = staging_builder.build("patient", "123")
    print(f"Staging key: {staging_key}")


# Example 12: Monitoring and debugging
async def example_monitoring():
    """Monitor cache invalidation performance."""
    service = CacheInvalidationService()

    # Perform operations
    await service.invalidate_entity("patient", "123", cascade=True)
    await service.invalidate_entity("quiz", "456", cascade=True)

    # Get detailed metrics
    metrics = await service.get_metrics()
    print("Cache Invalidation Metrics:")
    print(f"  Total invalidations: {metrics['invalidations']}")
    print(f"  Retries: {metrics['retries']}")
    print(f"  Failures: {metrics['failures']}")
    print(f"  Fallbacks to local: {metrics['fallbacks']}")
    print(f"  Backend: {metrics['backend']}")
    print(f"  Timestamp: {metrics['timestamp']}")


async def run_all_examples():
    """Run all examples."""
    print("=== Cache Invalidation Service Examples ===\n")

    print("1. Single Key Invalidation")
    await example_single_key_invalidation()

    print("\n2. Pattern Invalidation")
    await example_pattern_invalidation()

    print("\n3. Tag-based Invalidation")
    await example_tag_invalidation()

    print("\n4. Entity Invalidation")
    await example_entity_invalidation()

    print("\n5. Cascade Invalidation")
    await example_cascade_invalidation()

    print("\n6. Complex Keys")
    await example_complex_keys()

    print("\n7. Combined Invalidation")
    await example_combined_invalidation()

    print("\n8. Error Handling")
    await example_error_handling()

    print("\n9. Batch Invalidation")
    await example_batch_invalidation()

    print("\n10. Custom Namespacing")
    await example_custom_namespace()

    print("\n11. Monitoring")
    await example_monitoring()


if __name__ == "__main__":
    asyncio.run(run_all_examples())
