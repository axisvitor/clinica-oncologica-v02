#!/usr/bin/env python3
"""
GIN Index Verification Script

This script verifies that GIN indexes on the patients table are:
1. Created successfully
2. Being used by query planner
3. Providing expected performance improvements

Usage:
    python scripts/verify_gin_indexes.py
    python scripts/verify_gin_indexes.py --benchmark
"""

import sys
import time
from pathlib import Path

# Add backend-hormonia to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from app.database import engine, SessionLocal
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_indexes_exist() -> dict:
    """Check if GIN indexes exist on patients table."""
    logger.info("🔍 Checking if GIN indexes exist...")

    query = text("""
        SELECT
            indexname,
            indexdef,
            pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
        FROM pg_indexes
        WHERE tablename = 'patients'
        AND indexname LIKE '%gin%'
        ORDER BY indexname;
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        indexes = result.fetchall()

    if not indexes:
        logger.error("❌ No GIN indexes found on patients table!")
        return {"exists": False, "indexes": []}

    logger.info(f"✅ Found {len(indexes)} GIN indexes:")
    for idx in indexes:
        logger.info(f"   - {idx[0]}: {idx[2]}")

    return {
        "exists": True,
        "count": len(indexes),
        "indexes": [{"name": idx[0], "definition": idx[1], "size": idx[2]} for idx in indexes]
    }


def check_index_usage() -> dict:
    """Verify that indexes are being used by query planner."""
    logger.info("\n🔍 Checking if GIN indexes are being used by query planner...")

    # Test query that should use idx_patients_metadata_gin
    test_query = text("""
        EXPLAIN ANALYZE
        SELECT id, name FROM patients
        WHERE metadata @> '{"no_ai_messages": true}'::jsonb
        LIMIT 10;
    """)

    with engine.connect() as conn:
        result = conn.execute(test_query)
        plan = result.fetchall()

    plan_text = "\n".join([row[0] for row in plan])

    # Check if index scan is used
    using_index = "idx_patients_metadata_gin" in plan_text
    is_index_scan = "Index Scan" in plan_text or "Bitmap" in plan_text
    is_seq_scan = "Seq Scan" in plan_text and not is_index_scan

    if using_index and is_index_scan:
        logger.info("✅ GIN index IS being used (Index Scan detected)")
        status = "optimal"
    elif is_seq_scan:
        logger.warning("⚠️  Sequential scan detected - index NOT being used!")
        logger.warning("   This might be expected if table has < 100 rows")
        status = "not_used"
    else:
        logger.info("⚡ Query plan:")
        for line in plan:
            logger.info(f"   {line[0]}")
        status = "unknown"

    # Extract execution time
    execution_time = None
    for line in plan:
        if "Execution Time:" in line[0]:
            execution_time = line[0].split("Execution Time:")[1].strip()

    return {
        "using_index": using_index,
        "is_index_scan": is_index_scan,
        "is_seq_scan": is_seq_scan,
        "execution_time": execution_time,
        "status": status,
        "plan": plan_text
    }


def get_index_statistics() -> dict:
    """Get usage statistics for GIN indexes."""
    logger.info("\n📊 Fetching index usage statistics...")

    query = text("""
        SELECT
            schemaname,
            tablename,
            indexname,
            idx_scan as times_used,
            idx_tup_read as tuples_read,
            idx_tup_fetch as tuples_fetched
        FROM pg_stat_user_indexes
        WHERE tablename = 'patients'
        AND indexname LIKE '%gin%'
        ORDER BY idx_scan DESC;
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        stats = result.fetchall()

    if not stats:
        logger.warning("⚠️  No usage statistics available yet (indexes may be newly created)")
        return {"available": False, "stats": []}

    logger.info("✅ Index usage statistics:")
    for stat in stats:
        logger.info(f"   - {stat[2]}: Used {stat[3]} times, Read {stat[4]} tuples")

    return {
        "available": True,
        "stats": [
            {
                "index_name": stat[2],
                "times_used": stat[3],
                "tuples_read": stat[4],
                "tuples_fetched": stat[5]
            }
            for stat in stats
        ]
    }


def benchmark_performance() -> dict:
    """Benchmark query performance with and without GIN index."""
    logger.info("\n⚡ Benchmarking query performance...")

    # Count patients for context
    count_query = text("SELECT COUNT(*) FROM patients;")
    with engine.connect() as conn:
        patient_count = conn.execute(count_query).scalar()

    logger.info(f"   Table size: {patient_count} patients")

    if patient_count < 100:
        logger.warning("⚠️  Table has < 100 rows - index may not be used (expected behavior)")

    test_query = text("""
        SELECT id, name FROM patients
        WHERE metadata @> '{"no_ai_messages": true}'::jsonb;
    """)

    # Benchmark WITH index
    with engine.connect() as conn:
        conn.execute(text("SET enable_indexscan = on;"))
        conn.execute(text("SET enable_bitmapscan = on;"))

        start = time.time()
        result_with_index = conn.execute(test_query)
        rows_with_index = len(result_with_index.fetchall())
        time_with_index = time.time() - start

    logger.info(f"   WITH index: {time_with_index*1000:.2f}ms ({rows_with_index} rows)")

    # Benchmark WITHOUT index (sequential scan)
    with engine.connect() as conn:
        conn.execute(text("SET enable_indexscan = off;"))
        conn.execute(text("SET enable_bitmapscan = off;"))

        start = time.time()
        result_without_index = conn.execute(test_query)
        rows_without_index = len(result_without_index.fetchall())
        time_without_index = time.time() - start

        # Reset settings
        conn.execute(text("SET enable_indexscan = on;"))
        conn.execute(text("SET enable_bitmapscan = on;"))

    logger.info(f"   WITHOUT index: {time_without_index*1000:.2f}ms ({rows_without_index} rows)")

    if time_without_index > time_with_index:
        speedup = time_without_index / time_with_index if time_with_index > 0 else 1
        logger.info(f"   ✅ SPEEDUP: {speedup:.1f}x faster with index")
    else:
        logger.warning(f"   ⚠️  No speedup detected (table may be too small)")

    return {
        "patient_count": patient_count,
        "time_with_index_ms": time_with_index * 1000,
        "time_without_index_ms": time_without_index * 1000,
        "speedup": time_without_index / time_with_index if time_with_index > 0 else 1,
        "rows_returned": rows_with_index
    }


def check_table_statistics() -> dict:
    """Check if table statistics are up to date."""
    logger.info("\n📈 Checking table statistics...")

    query = text("""
        SELECT
            schemaname,
            tablename,
            last_analyze,
            last_autoanalyze,
            n_live_tup as row_count
        FROM pg_stat_user_tables
        WHERE tablename = 'patients';
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        stats = result.fetchone()

    if not stats:
        logger.warning("⚠️  No statistics available")
        return {"available": False}

    logger.info(f"   Last ANALYZE: {stats[2]}")
    logger.info(f"   Last Auto-ANALYZE: {stats[3]}")
    logger.info(f"   Live rows: {stats[4]}")

    if stats[2] is None and stats[3] is None:
        logger.warning("⚠️  Table has never been analyzed - run ANALYZE patients;")
        needs_analyze = True
    else:
        needs_analyze = False

    return {
        "available": True,
        "last_analyze": str(stats[2]) if stats[2] else None,
        "last_autoanalyze": str(stats[3]) if stats[3] else None,
        "row_count": stats[4],
        "needs_analyze": needs_analyze
    }


def main():
    """Run all verification checks."""
    logger.info("=" * 70)
    logger.info("GIN INDEX VERIFICATION SCRIPT")
    logger.info("=" * 70)

    try:
        # Check 1: Do indexes exist?
        index_check = check_indexes_exist()

        if not index_check["exists"]:
            logger.error("\n❌ VERIFICATION FAILED: GIN indexes not found!")
            logger.error("   Run migration: backend-hormonia/migrations/003_add_gin_indexes_patient_metadata.sql")
            return 1

        # Check 2: Are indexes being used?
        usage_check = check_index_usage()

        # Check 3: Table statistics
        stats_check = check_table_statistics()

        if stats_check.get("needs_analyze"):
            logger.warning("\n⚠️  RECOMMENDATION: Run ANALYZE patients; to update statistics")

        # Check 4: Usage statistics
        index_stats = get_index_statistics()

        # Check 5: Benchmark (if requested)
        if "--benchmark" in sys.argv:
            benchmark = benchmark_performance()

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"✅ GIN Indexes Exist: {index_check['count']} indexes")
        logger.info(f"{'✅' if usage_check['using_index'] else '⚠️ '} Index Being Used: {usage_check['status']}")
        logger.info(f"{'✅' if index_stats['available'] else '⚠️ '} Usage Statistics: {'Available' if index_stats['available'] else 'Not yet available'}")

        if usage_check['status'] == 'optimal':
            logger.info("\n🎉 SUCCESS: GIN indexes are properly configured and being used!")
            return 0
        elif usage_check['status'] == 'not_used':
            logger.warning("\n⚠️  WARNING: Indexes exist but are not being used")
            logger.warning("   This is normal for tables with < 100 rows")
            logger.warning("   PostgreSQL prefers sequential scan for small tables")
            return 0
        else:
            logger.warning("\n⚠️  Verification completed with warnings - review output above")
            return 0

    except Exception as e:
        logger.error(f"\n❌ ERROR during verification: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
