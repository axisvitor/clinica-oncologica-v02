#!/usr/bin/env python3
"""
GIN Index performance testing script.
Part of MEDIUM-014: GIN Index on JSONB fields

This script measures the performance improvement from adding GIN indexes
to JSONB columns, particularly patients.metadata.

Usage:
    python scripts/test_gin_index_performance.py
"""

import asyncio
import asyncpg
import json
import time
import sys
from typing import Dict, List
from datetime import datetime
import statistics


async def create_test_data(conn: asyncpg.Connection, num_patients: int = 1000) -> None:
    """
    Create test patient data with JSONB metadata.

    Args:
        conn: Database connection
        num_patients: Number of test patients to create
    """

    print(f"📝 Creating {num_patients} test patients with JSONB metadata...")

    # Sample metadata variations
    metadata_templates = [
        {"consent": {"lgpd": True, "data_sharing": True}, "preferences": {"language": "pt-BR"}},
        {"consent": {"lgpd": True, "data_sharing": False}, "preferences": {"language": "en-US"}},
        {"consent": {"lgpd": False, "data_sharing": False}, "preferences": {"language": "pt-BR"}},
        {"consent": {"lgpd": True, "data_sharing": True}, "preferences": {"language": "es-ES", "notifications": True}},
        {"consent": {"lgpd": False}, "preferences": {"language": "pt-BR", "theme": "dark"}},
    ]

    # Create test patients
    for i in range(num_patients):
        metadata = metadata_templates[i % len(metadata_templates)].copy()
        metadata['test_id'] = i
        metadata['created_at'] = datetime.now().isoformat()

        await conn.execute("""
            INSERT INTO patients (name, email, phone, metadata, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (email) DO NOTHING
        """, f"Test Patient {i}", f"test{i}@example.com", f"+551199999{i:04d}", json.dumps(metadata))

    print(f"✅ Created {num_patients} test patients")


async def test_query_performance(
    conn: asyncpg.Connection,
    query: str,
    params: tuple = (),
    iterations: int = 10
) -> Dict:
    """
    Measure query performance over multiple iterations.

    Args:
        conn: Database connection
        query: SQL query to test
        params: Query parameters
        iterations: Number of times to run the query

    Returns:
        Dictionary with performance metrics
    """

    times = []

    for i in range(iterations):
        start = time.perf_counter()
        result = await conn.fetch(query, *params)
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)  # Convert to milliseconds

        # Small delay between iterations
        await asyncio.sleep(0.1)

    return {
        'min': min(times),
        'max': max(times),
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'p95': sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0],
        'count': len(result),
        'iterations': iterations
    }


async def test_without_index(conn: asyncpg.Connection) -> None:
    """Test JSONB queries WITHOUT GIN index."""

    print(f"\n{'='*80}")
    print("📊 Testing WITHOUT GIN Index")
    print(f"{'='*80}\n")

    # Drop GIN index if exists
    await conn.execute("DROP INDEX IF EXISTS idx_patient_metadata_gin;")
    await conn.execute("DROP INDEX IF EXISTS idx_patient_metadata_consent_gin;")
    await conn.execute("DROP INDEX IF EXISTS idx_patient_metadata_preferences_gin;")

    # Run ANALYZE to update query planner statistics
    await conn.execute("ANALYZE patients;")

    queries = [
        {
            'name': 'Contains query - Full consent object',
            'query': """
                SELECT id, name, email, metadata
                FROM patients
                WHERE metadata @> $1
            """,
            'params': (json.dumps({"consent": {"lgpd": True}}),)
        },
        {
            'name': 'Contains query - Nested preference',
            'query': """
                SELECT id, name, email, metadata
                FROM patients
                WHERE metadata @> $1
            """,
            'params': (json.dumps({"preferences": {"language": "pt-BR"}}),)
        },
        {
            'name': 'JSON path query - Extract value',
            'query': """
                SELECT id, name, email, metadata
                FROM patients
                WHERE metadata->'consent'->>'lgpd' = 'true'
            """,
            'params': ()
        },
        {
            'name': 'Complex query - Multiple conditions',
            'query': """
                SELECT id, name, email, metadata
                FROM patients
                WHERE metadata @> $1
                  AND metadata @> $2
            """,
            'params': (
                json.dumps({"consent": {"lgpd": True}}),
                json.dumps({"preferences": {"language": "pt-BR"}})
            )
        }
    ]

    results_without = []

    for test in queries:
        print(f"🔍 {test['name']}")

        # Get query plan
        plan = await conn.fetch(f"EXPLAIN {test['query']}", *test['params'])
        print("   Query Plan:")
        for row in plan:
            print(f"   {row[0]}")

        # Run performance test
        perf = await test_query_performance(conn, test['query'], test['params'])

        print(f"\n   Performance:")
        print(f"   - Mean: {perf['mean']:.2f}ms")
        print(f"   - Median: {perf['median']:.2f}ms")
        print(f"   - P95: {perf['p95']:.2f}ms")
        print(f"   - Min/Max: {perf['min']:.2f}ms / {perf['max']:.2f}ms")
        print(f"   - Rows: {perf['count']}\n")

        results_without.append({
            'name': test['name'],
            'perf': perf
        })

    return results_without


async def test_with_index(conn: asyncpg.Connection) -> None:
    """Test JSONB queries WITH GIN index."""

    print(f"\n{'='*80}")
    print("📊 Testing WITH GIN Index")
    print(f"{'='*80}\n")

    print("🔨 Creating GIN indexes...")

    # Create GIN indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_patient_metadata_gin
        ON patients USING GIN (metadata);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_patient_metadata_consent_gin
        ON patients USING GIN ((metadata->'consent'));
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_patient_metadata_preferences_gin
        ON patients USING GIN ((metadata->'preferences'));
    """)

    # Run ANALYZE to update query planner statistics
    await conn.execute("ANALYZE patients;")

    print("✅ GIN indexes created\n")

    queries = [
        {
            'name': 'Contains query - Full consent object',
            'query': """
                SELECT id, name, email, metadata
                FROM patients
                WHERE metadata @> $1
            """,
            'params': (json.dumps({"consent": {"lgpd": True}}),)
        },
        {
            'name': 'Contains query - Nested preference',
            'query': """
                SELECT id, name, email, metadata
                FROM patients
                WHERE metadata @> $1
            """,
            'params': (json.dumps({"preferences": {"language": "pt-BR"}}),)
        },
        {
            'name': 'JSON path query - Extract value',
            'query': """
                SELECT id, name, email, metadata
                FROM patients
                WHERE metadata->'consent'->>'lgpd' = 'true'
            """,
            'params': ()
        },
        {
            'name': 'Complex query - Multiple conditions',
            'query': """
                SELECT id, name, email, metadata
                FROM patients
                WHERE metadata @> $1
                  AND metadata @> $2
            """,
            'params': (
                json.dumps({"consent": {"lgpd": True}}),
                json.dumps({"preferences": {"language": "pt-BR"}})
            )
        }
    ]

    results_with = []

    for test in queries:
        print(f"🔍 {test['name']}")

        # Get query plan
        plan = await conn.fetch(f"EXPLAIN {test['query']}", *test['params'])
        print("   Query Plan:")
        for row in plan:
            print(f"   {row[0]}")

        # Run performance test
        perf = await test_query_performance(conn, test['query'], test['params'])

        print(f"\n   Performance:")
        print(f"   - Mean: {perf['mean']:.2f}ms")
        print(f"   - Median: {perf['median']:.2f}ms")
        print(f"   - P95: {perf['p95']:.2f}ms")
        print(f"   - Min/Max: {perf['min']:.2f}ms / {perf['max']:.2f}ms")
        print(f"   - Rows: {perf['count']}\n")

        results_with.append({
            'name': test['name'],
            'perf': perf
        })

    return results_with


async def generate_comparison_report(results_without: List[Dict], results_with: List[Dict]) -> None:
    """Generate comparison report showing speedup from GIN indexes."""

    print(f"\n{'='*80}")
    print("📈 GIN INDEX PERFORMANCE COMPARISON")
    print(f"{'='*80}\n")

    print(f"{'Query':<45} {'Without (ms)':<15} {'With (ms)':<15} {'Speedup':<15}")
    print("-" * 90)

    total_speedup = []

    for without, with_idx in zip(results_without, results_with):
        without_time = without['perf']['mean']
        with_time = with_idx['perf']['mean']
        speedup = without_time / with_time if with_time > 0 else 0

        total_speedup.append(speedup)

        print(f"{without['name']:<45} {without_time:<15.2f} {with_time:<15.2f} {speedup:<15.1f}x")

    avg_speedup = statistics.mean(total_speedup)

    print("-" * 90)
    print(f"{'AVERAGE':<45} {'':<15} {'':<15} {avg_speedup:<15.1f}x")

    print(f"\n✅ RESULTS:")
    print(f"   Average speedup: {avg_speedup:.1f}x faster with GIN indexes")

    if avg_speedup >= 50:
        print(f"   🎉 EXCELLENT! Target achieved (>50x speedup)")
    elif avg_speedup >= 10:
        print(f"   ✅ GOOD! Significant improvement")
    else:
        print(f"   ⚠️  Speedup lower than expected. Check data volume and query patterns.")

    # Recommendations
    print(f"\n📋 RECOMMENDATIONS:")
    print(f"   1. Apply migration 013_add_gin_index_patient_metadata.py to production")
    print(f"   2. Monitor index usage with pg_stat_user_indexes")
    print(f"   3. Run ANALYZE after migration to update statistics")
    print(f"   4. Consider adding GIN indexes to other JSONB columns if heavily queried")


async def main():
    """Main entry point."""

    # Get database URL from environment
    import os
    from dotenv import load_dotenv

    load_dotenv()

    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not set in environment")
        sys.exit(1)

    # Convert to asyncpg format if needed
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')

    print("🔌 Connecting to database...")

    try:
        conn = await asyncpg.connect(database_url)

        print("✅ Connected to database\n")

        # Create test data
        await create_test_data(conn, num_patients=1000)

        # Test without index
        results_without = await test_without_index(conn)

        # Test with index
        results_with = await test_with_index(conn)

        # Generate comparison report
        await generate_comparison_report(results_without, results_with)

        # Save results
        results = {
            'timestamp': datetime.now().isoformat(),
            'without_index': results_without,
            'with_index': results_with
        }

        with open('backend-hormonia/scripts/gin_index_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\n💾 Results saved to: backend-hormonia/scripts/gin_index_results.json")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
