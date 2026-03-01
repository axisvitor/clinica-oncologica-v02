#!/usr/bin/env python3
"""
Comprehensive Health Check Script

Validates system health across all components:
- Database connectivity and performance
- Redis connectivity and metrics
- Application API endpoints
- Service dependencies
- Resource utilization

Usage:
    python scripts/health_check.py [--timeout 30] [--json]
"""

import sys
import asyncio
import time
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.timezone import now_sao_paulo_naive


def _as_redis_string(value: Any) -> Optional[str]:
    """Normalize Redis responses to plain strings for roundtrip checks."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


@dataclass
class HealthStatus:
    """Health status for a component"""
    healthy: bool
    response_time_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = now_sao_paulo_naive().isoformat()


class HealthChecker:
    """Orchestrates comprehensive health checks"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.results: Dict[str, HealthStatus] = {}

    async def check_all(self) -> Dict[str, HealthStatus]:
        """Run all health checks"""
        await self._check_database()
        await self._check_redis()
        await self._check_api()
        await self._check_resources()
        return self.results

    async def _check_database(self) -> None:
        """Check database health"""
        start = time.time()
        try:
            from app.database import AsyncSessionLocal
            from sqlalchemy import text

            async with AsyncSessionLocal() as session:
                # Simple connectivity check
                await session.execute(text("SELECT 1"))

                # Check active connections
                result = await session.execute(text(
                    "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                ))
                active_connections = result.scalar()

                # Check database size
                result = await session.execute(text(
                    "SELECT pg_database_size(current_database())"
                ))
                db_size_bytes = result.scalar()

                response_time = (time.time() - start) * 1000

                self.results['database'] = HealthStatus(
                    healthy=True,
                    response_time_ms=response_time,
                    message="Database is healthy",
                    details={
                        'active_connections': active_connections,
                        'database_size_mb': round(db_size_bytes / 1024 / 1024, 2),
                        'response_time_ms': round(response_time, 2)
                    }
                )

        except Exception as e:
            response_time = (time.time() - start) * 1000
            self.results['database'] = HealthStatus(
                healthy=False,
                response_time_ms=response_time,
                message=f"Database health check failed: {str(e)}"
            )

    async def _check_redis(self) -> None:
        """Check Redis health"""
        start = time.time()
        try:
            test_key = "__health_check__"
            info: Dict[str, Any] = {}

            from app.core.redis_manager import get_async_redis_client

            redis_client = await get_async_redis_client()
            await redis_client.ping()
            raw_info = await redis_client.info()
            if isinstance(raw_info, dict):
                info = raw_info
            await redis_client.set(test_key, "ok", ex=10)
            value = await redis_client.get(test_key)
            await redis_client.delete(test_key)

            if _as_redis_string(value) != "ok":
                raise RuntimeError("Redis set/get roundtrip failed")

            response_time = (time.time() - start) * 1000

            self.results['redis'] = HealthStatus(
                healthy=True,
                response_time_ms=response_time,
                message="Redis is healthy",
                details={
                    'connected_clients': info.get('connected_clients'),
                    'used_memory_mb': round(int(info.get('used_memory', 0)) / 1024 / 1024, 2),
                    'uptime_days': round(int(info.get('uptime_in_seconds', 0)) / 86400, 2),
                    'response_time_ms': round(response_time, 2)
                }
            )

        except Exception as e:
            response_time = (time.time() - start) * 1000
            self.results['redis'] = HealthStatus(
                healthy=False,
                response_time_ms=response_time,
                message=f"Redis health check failed: {str(e)}"
            )

    async def _check_api(self) -> None:
        """Check API health"""
        start = time.time()
        try:
            import httpx
            api_url = os.getenv("HEALTH_CHECK_API_URL", "http://localhost:8000/health")

            # Check health endpoint
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(api_url)
                response.raise_for_status()

                response_time = (time.time() - start) * 1000
                data = response.json()

                self.results['api'] = HealthStatus(
                    healthy=True,
                    response_time_ms=response_time,
                    message="API is healthy",
                    details={
                        'status': data.get('status'),
                        'version': data.get('version'),
                        'response_time_ms': round(response_time, 2)
                    }
                )

        except Exception as e:
            response_time = (time.time() - start) * 1000
            self.results['api'] = HealthStatus(
                healthy=False,
                response_time_ms=response_time,
                message=f"API health check failed: {str(e)}"
            )

    async def _check_resources(self) -> None:
        """Check system resources"""
        start = time.time()
        try:
            import psutil

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()

            # Disk usage
            disk = psutil.disk_usage('/')

            response_time = (time.time() - start) * 1000

            # Determine health based on thresholds
            healthy = (
                cpu_percent < 80 and
                memory.percent < 85 and
                disk.percent < 90
            )

            self.results['resources'] = HealthStatus(
                healthy=healthy,
                response_time_ms=response_time,
                message="Resources within acceptable limits" if healthy else "Resources under pressure",
                details={
                    'cpu_percent': round(cpu_percent, 2),
                    'memory_percent': round(memory.percent, 2),
                    'memory_available_mb': round(memory.available / 1024 / 1024, 2),
                    'disk_percent': round(disk.percent, 2),
                    'disk_free_gb': round(disk.free / 1024 / 1024 / 1024, 2)
                }
            )

        except Exception as e:
            response_time = (time.time() - start) * 1000
            self.results['resources'] = HealthStatus(
                healthy=False,
                response_time_ms=response_time,
                message=f"Resource check failed: {str(e)}"
            )

    def is_healthy(self) -> bool:
        """Check if overall system is healthy"""
        return all(status.healthy for status in self.results.values())

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary"""
        return {
            'overall_healthy': self.is_healthy(),
            'timestamp': now_sao_paulo_naive().isoformat(),
            'components': {
                name: asdict(status)
                for name, status in self.results.items()
            }
        }


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Check system health')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Timeout in seconds (default: 30)')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')
    args = parser.parse_args()

    checker = HealthChecker(timeout=args.timeout)
    await checker.check_all()

    if args.json:
        print(json.dumps(checker.to_dict(), indent=2))
    else:
        print("\n" + "=" * 80)
        print("HEALTH CHECK RESULTS")
        print("=" * 80)

        for component, status in checker.results.items():
            symbol = "✓" if status.healthy else "✗"
            print(f"\n{symbol} {component.upper()}")
            print(f"  Status: {'HEALTHY' if status.healthy else 'UNHEALTHY'}")
            print(f"  Response Time: {status.response_time_ms:.2f}ms")
            print(f"  Message: {status.message}")

            if status.details:
                print("  Details:")
                for key, value in status.details.items():
                    print(f"    - {key}: {value}")

        print("\n" + "=" * 80)
        if checker.is_healthy():
            print("✅ Overall Status: HEALTHY")
            sys.exit(0)
        else:
            print("❌ Overall Status: UNHEALTHY")
            sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
