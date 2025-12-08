#!/usr/bin/env python3
"""
Performance Profiler Script
Analyzes backend performance bottlenecks in real-time

Usage:
    python scripts/performance_profiler.py --mode all
    python scripts/performance_profiler.py --mode database
    python scripts/performance_profiler.py --mode cache
    python scripts/performance_profiler.py --mode endpoints
"""

import argparse
import asyncio
import sys
import time
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_scoped_session
from app.core.redis_unified import get_redis_client


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


class DatabaseProfiler:
    """Database performance profiler"""

    def __init__(self, db: Session):
        self.db = db

    def check_connection_pool(self) -> Dict:
        """Check database connection pool status"""
        print_header("DATABASE CONNECTION POOL ANALYSIS")

        try:
            # Get pool statistics
            pool = self.db.bind.pool
            pool_status = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "overflow_limit": pool._max_overflow,
            }

            total_connections = pool_status["size"] + pool_status["overflow"]
            max_connections = pool_status["size"] + pool_status["overflow_limit"]
            utilization = (pool_status["checked_out"] / max_connections) * 100

            print(f"Pool Size: {pool_status['size']}")
            print(f"Checked Out: {pool_status['checked_out']}")
            print(f"Checked In: {pool_status['checked_in']}")
            print(f"Overflow: {pool_status['overflow']} / {pool_status['overflow_limit']}")
            print(f"Utilization: {utilization:.1f}%")

            if utilization > 80:
                print_error(f"HIGH UTILIZATION: {utilization:.1f}% - Consider increasing pool size")
            elif utilization > 60:
                print_warning(f"MODERATE UTILIZATION: {utilization:.1f}% - Monitor closely")
            else:
                print_success(f"HEALTHY UTILIZATION: {utilization:.1f}%")

            return pool_status

        except Exception as e:
            print_error(f"Failed to check connection pool: {e}")
            return {}

    def check_slow_queries(self) -> List[Dict]:
        """Analyze slow queries from pg_stat_statements"""
        print_header("SLOW QUERIES ANALYSIS")

        try:
            query = text("""
                SELECT
                    LEFT(query, 100) as query_preview,
                    calls,
                    ROUND(total_time::numeric, 2) as total_time_ms,
                    ROUND(mean_time::numeric, 2) as mean_time_ms,
                    ROUND(max_time::numeric, 2) as max_time_ms,
                    rows
                FROM pg_stat_statements
                WHERE mean_time > 100  -- More than 100ms average
                ORDER BY mean_time DESC
                LIMIT 10
            """)

            result = self.db.execute(query)
            slow_queries = []

            print(f"{'Query Preview':<40} {'Calls':<8} {'Mean (ms)':<12} {'Max (ms)':<12}")
            print("-" * 80)

            for row in result:
                slow_queries.append(dict(row._mapping))
                query_preview = row.query_preview[:37] + "..." if len(row.query_preview) > 40 else row.query_preview
                print(f"{query_preview:<40} {row.calls:<8} {row.mean_time_ms:<12.1f} {row.max_time_ms:<12.1f}")

                if row.mean_time_ms > 1000:  # > 1 second
                    print_error(f"  → CRITICAL: Average execution time > 1 second")
                elif row.mean_time_ms > 500:
                    print_warning(f"  → WARNING: Average execution time > 500ms")

            if not slow_queries:
                print_info("No slow queries found (pg_stat_statements may not be enabled)")

            return slow_queries

        except Exception as e:
            print_error(f"Failed to analyze slow queries: {e}")
            print_info("Enable pg_stat_statements: CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")
            return []

    def check_index_usage(self) -> List[Dict]:
        """Check index usage statistics"""
        print_header("INDEX USAGE ANALYSIS")

        try:
            query = text("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                ORDER BY idx_scan ASC
                LIMIT 15
            """)

            result = self.db.execute(query)
            indexes = []

            print(f"{'Table':<25} {'Index':<35} {'Scans':<10} {'Size':<10}")
            print("-" * 80)

            for row in result:
                indexes.append(dict(row._mapping))
                print(f"{row.tablename:<25} {row.indexname:<35} {row.idx_scan:<10} {row.index_size:<10}")

                if row.idx_scan == 0:
                    print_warning(f"  → UNUSED INDEX: Consider dropping {row.indexname}")
                elif row.idx_scan < 100:
                    print_info(f"  → LOW USAGE: Only {row.idx_scan} scans")

            return indexes

        except Exception as e:
            print_error(f"Failed to check index usage: {e}")
            return []

    def check_table_bloat(self) -> List[Dict]:
        """Check for table bloat"""
        print_header("TABLE BLOAT ANALYSIS")

        try:
            query = text("""
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
                    n_live_tup as live_rows,
                    n_dead_tup as dead_rows,
                    ROUND(100 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_pct
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                    AND n_dead_tup > 1000
                ORDER BY n_dead_tup DESC
                LIMIT 10
            """)

            result = self.db.execute(query)
            bloated_tables = []

            print(f"{'Table':<25} {'Total Size':<12} {'Live Rows':<12} {'Dead %':<10}")
            print("-" * 80)

            for row in result:
                bloated_tables.append(dict(row._mapping))
                print(f"{row.tablename:<25} {row.total_size:<12} {row.live_rows:<12} {row.dead_pct:.1f}%")

                if row.dead_pct > 20:
                    print_error(f"  → HIGH BLOAT: Run VACUUM ANALYZE {row.tablename}")
                elif row.dead_pct > 10:
                    print_warning(f"  → MODERATE BLOAT: Consider vacuuming")

            if not bloated_tables:
                print_success("No significant table bloat detected")

            return bloated_tables

        except Exception as e:
            print_error(f"Failed to check table bloat: {e}")
            return []


class CacheProfiler:
    """Redis cache performance profiler"""

    def __init__(self):
        self.redis = get_redis_client('sync')

    def check_memory_usage(self) -> Dict:
        """Check Redis memory usage"""
        print_header("REDIS MEMORY USAGE")

        try:
            info = self.redis.info('memory')

            used_memory_mb = info['used_memory'] / (1024 * 1024)
            max_memory_mb = info.get('maxmemory', 0) / (1024 * 1024)
            mem_fragmentation = info.get('mem_fragmentation_ratio', 1.0)

            print(f"Used Memory: {used_memory_mb:.2f} MB")
            if max_memory_mb > 0:
                print(f"Max Memory: {max_memory_mb:.2f} MB")
                utilization = (used_memory_mb / max_memory_mb) * 100
                print(f"Utilization: {utilization:.1f}%")

                if utilization > 90:
                    print_error(f"CRITICAL: Redis memory at {utilization:.1f}%")
                elif utilization > 70:
                    print_warning(f"WARNING: Redis memory at {utilization:.1f}%")
                else:
                    print_success(f"HEALTHY: Redis memory at {utilization:.1f}%")

            print(f"Fragmentation Ratio: {mem_fragmentation:.2f}")
            if mem_fragmentation > 1.5:
                print_warning("HIGH FRAGMENTATION: Consider restarting Redis")

            return info

        except Exception as e:
            print_error(f"Failed to check Redis memory: {e}")
            return {}

    def check_keyspace(self) -> Dict:
        """Check Redis keyspace statistics"""
        print_header("REDIS KEYSPACE ANALYSIS")

        try:
            info = self.redis.info('keyspace')

            for db, stats in info.items():
                if db.startswith('db'):
                    print(f"\n{db.upper()}:")
                    print(f"  Keys: {stats['keys']}")
                    print(f"  Expires: {stats['expires']}")
                    print(f"  Avg TTL: {stats.get('avg_ttl', 0) / 1000:.1f}s")

                    if stats['keys'] > 100000:
                        print_warning(f"  → HIGH KEY COUNT: Consider cleanup or partitioning")

            # Sample keys by pattern
            print("\nKEY PATTERNS:")
            for pattern in ["patient:*", "flow:*", "cache:*", "session:*"]:
                count = len(self.redis.keys(pattern))
                print(f"  {pattern}: {count} keys")

            return info

        except Exception as e:
            print_error(f"Failed to check Redis keyspace: {e}")
            return {}

    def check_cache_hit_rate(self) -> Dict:
        """Calculate cache hit rate"""
        print_header("CACHE HIT RATE ANALYSIS")

        try:
            info = self.redis.info('stats')

            keyspace_hits = info.get('keyspace_hits', 0)
            keyspace_misses = info.get('keyspace_misses', 0)
            total_requests = keyspace_hits + keyspace_misses

            if total_requests > 0:
                hit_rate = (keyspace_hits / total_requests) * 100
                print(f"Total Requests: {total_requests:,}")
                print(f"Cache Hits: {keyspace_hits:,}")
                print(f"Cache Misses: {keyspace_misses:,}")
                print(f"Hit Rate: {hit_rate:.2f}%")

                if hit_rate > 85:
                    print_success(f"EXCELLENT: Cache hit rate {hit_rate:.1f}%")
                elif hit_rate > 70:
                    print_success(f"GOOD: Cache hit rate {hit_rate:.1f}%")
                elif hit_rate > 50:
                    print_warning(f"MODERATE: Cache hit rate {hit_rate:.1f}%")
                else:
                    print_error(f"LOW: Cache hit rate {hit_rate:.1f}% - Review caching strategy")

            return {
                'hit_rate': hit_rate if total_requests > 0 else 0,
                'hits': keyspace_hits,
                'misses': keyspace_misses
            }

        except Exception as e:
            print_error(f"Failed to check cache hit rate: {e}")
            return {}


async def profile_api_endpoints():
    """Profile API endpoint performance"""
    print_header("API ENDPOINT PERFORMANCE")

    try:
        import httpx

        base_url = "http://localhost:8000"
        endpoints = [
            ("/health", "GET"),
            ("/api/v2/patients", "GET"),
            ("/api/v2/doctors", "GET"),
        ]

        print(f"{'Endpoint':<40} {'Method':<8} {'Time (ms)':<12} {'Status':<10}")
        print("-" * 80)

        async with httpx.AsyncClient() as client:
            for endpoint, method in endpoints:
                start = time.time()
                try:
                    if method == "GET":
                        response = await client.get(f"{base_url}{endpoint}", timeout=10.0)
                    duration = (time.time() - start) * 1000

                    print(f"{endpoint:<40} {method:<8} {duration:<12.1f} {response.status_code:<10}")

                    if duration > 1000:
                        print_error(f"  → SLOW: Response time > 1 second")
                    elif duration > 500:
                        print_warning(f"  → WARNING: Response time > 500ms")

                except Exception as e:
                    print_error(f"{endpoint:<40} {method:<8} ERROR: {str(e)[:30]}")

    except ImportError:
        print_error("httpx not installed. Install: pip install httpx")
    except Exception as e:
        print_error(f"Failed to profile endpoints: {e}")


def main():
    """Main profiler entry point"""
    parser = argparse.ArgumentParser(description='Backend Performance Profiler')
    parser.add_argument(
        '--mode',
        choices=['all', 'database', 'cache', 'endpoints'],
        default='all',
        help='Profiling mode'
    )

    args = parser.parse_args()

    print_header("BACKEND PERFORMANCE PROFILER")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {args.mode}")

    # Database profiling
    if args.mode in ['all', 'database']:
        try:
            with get_scoped_session() as db:
                profiler = DatabaseProfiler(db)
                profiler.check_connection_pool()
                profiler.check_slow_queries()
                profiler.check_index_usage()
                profiler.check_table_bloat()
        except Exception as e:
            print_error(f"Database profiling failed: {e}")

    # Cache profiling
    if args.mode in ['all', 'cache']:
        try:
            profiler = CacheProfiler()
            profiler.check_memory_usage()
            profiler.check_keyspace()
            profiler.check_cache_hit_rate()
        except Exception as e:
            print_error(f"Cache profiling failed: {e}")

    # API endpoint profiling
    if args.mode in ['all', 'endpoints']:
        try:
            asyncio.run(profile_api_endpoints())
        except Exception as e:
            print_error(f"Endpoint profiling failed: {e}")

    print_header("PROFILING COMPLETE")
    print_info("Review output above for performance optimization opportunities")
    print_info("Full analysis: docs/performance/DEEP_PERFORMANCE_ANALYSIS.md")


if __name__ == "__main__":
    main()
