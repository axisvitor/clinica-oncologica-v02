"""
Specific Health Check Implementations

Production-ready health checks for various system components.
"""

import time
import asyncio
import psutil
from pathlib import Path
from typing import Dict, Any
from sqlalchemy import create_engine, text

from .checker import HealthCheck, HealthResult, HealthStatus


class DatabaseHealthCheck(HealthCheck):
    """Database connectivity and performance health check"""

    def __init__(
        self,
        database_url: str,
        name: str = "database",
        timeout: float = 10.0,
        slow_query_threshold: float = 1.0,
    ):
        super().__init__(name, timeout)
        self.database_url = database_url
        self.slow_query_threshold = slow_query_threshold

    async def check(self) -> HealthResult:
        """Perform database health check"""
        start_time = time.time()

        try:
            # Create engine for this check
            engine = create_engine(
                self.database_url, pool_pre_ping=True, pool_recycle=300
            )

            # Test basic connectivity
            with engine.connect() as conn:
                # Simple query to test connectivity
                query_start = time.time()
                conn.execute(text("SELECT 1"))
                query_duration = time.time() - query_start

                # Check if query is slow
                is_slow = query_duration > self.slow_query_threshold

                # Get additional database info
                db_info = self._get_database_info(conn)

                duration = time.time() - start_time

                if is_slow:
                    status = HealthStatus.DEGRADED
                    message = f"Database responding slowly ({query_duration:.3f}s)"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"Database healthy ({query_duration:.3f}s)"

                return HealthResult(
                    name=self.name,
                    status=status,
                    message=message,
                    duration=duration,
                    details={
                        "query_duration": query_duration,
                        "slow_query_threshold": self.slow_query_threshold,
                        "is_slow": is_slow,
                        **db_info,
                    },
                )

        except Exception as e:
            duration = time.time() - start_time
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                duration=duration,
                error=str(e),
            )

    def _get_database_info(self, conn) -> Dict[str, Any]:
        """Get additional database information"""
        try:
            # Get PostgreSQL version
            version_result = conn.execute(text("SELECT version()"))
            version = version_result.scalar()

            # Get connection count
            conn_result = conn.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            )
            active_connections = conn_result.scalar()

            # Get database size
            size_result = conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
            database_size = size_result.scalar()

            return {
                "version": version,
                "active_connections": active_connections,
                "database_size": database_size,
            }

        except Exception as e:
            return {"info_error": str(e)}


class DiskSpaceHealthCheck(HealthCheck):
    """Disk space health check"""

    def __init__(
        self,
        path: str = "/",
        warning_threshold: float = 80.0,
        critical_threshold: float = 90.0,
        name: str = "disk_space",
    ):
        super().__init__(name)
        self.path = Path(path)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    async def check(self) -> HealthResult:
        """Perform disk space health check"""
        start_time = time.time()

        try:
            # Get disk usage
            usage = psutil.disk_usage(str(self.path))

            total_gb = usage.total / (1024**3)
            used_gb = usage.used / (1024**3)
            free_gb = usage.free / (1024**3)
            used_percent = (usage.used / usage.total) * 100

            # Determine status
            if used_percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Disk space critical: {used_percent:.1f}% used"
            elif used_percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"Disk space warning: {used_percent:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space healthy: {used_percent:.1f}% used"

            duration = time.time() - start_time

            return HealthResult(
                name=self.name,
                status=status,
                message=message,
                duration=duration,
                details={
                    "path": str(self.path),
                    "total_gb": round(total_gb, 2),
                    "used_gb": round(used_gb, 2),
                    "free_gb": round(free_gb, 2),
                    "used_percent": round(used_percent, 1),
                    "warning_threshold": self.warning_threshold,
                    "critical_threshold": self.critical_threshold,
                },
            )

        except Exception as e:
            duration = time.time() - start_time
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Disk space check failed: {str(e)}",
                duration=duration,
                error=str(e),
            )


class MemoryHealthCheck(HealthCheck):
    """Memory usage health check"""

    def __init__(
        self,
        warning_threshold: float = 80.0,
        critical_threshold: float = 90.0,
        name: str = "memory",
    ):
        super().__init__(name)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    async def check(self) -> HealthResult:
        """Perform memory health check"""
        start_time = time.time()

        try:
            # Get memory usage
            memory = psutil.virtual_memory()

            total_gb = memory.total / (1024**3)
            used_gb = memory.used / (1024**3)
            available_gb = memory.available / (1024**3)
            used_percent = memory.percent

            # Determine status
            if used_percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Memory usage critical: {used_percent:.1f}%"
            elif used_percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"Memory usage warning: {used_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage healthy: {used_percent:.1f}%"

            duration = time.time() - start_time

            return HealthResult(
                name=self.name,
                status=status,
                message=message,
                duration=duration,
                details={
                    "total_gb": round(total_gb, 2),
                    "used_gb": round(used_gb, 2),
                    "available_gb": round(available_gb, 2),
                    "used_percent": used_percent,
                    "warning_threshold": self.warning_threshold,
                    "critical_threshold": self.critical_threshold,
                },
            )

        except Exception as e:
            duration = time.time() - start_time
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Memory check failed: {str(e)}",
                duration=duration,
                error=str(e),
            )


class CPUHealthCheck(HealthCheck):
    """CPU usage health check"""

    def __init__(
        self,
        warning_threshold: float = 80.0,
        critical_threshold: float = 95.0,
        interval: float = 1.0,
        name: str = "cpu",
    ):
        super().__init__(name)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.cpu_interval = interval

    async def check(self) -> HealthResult:
        """Perform CPU health check"""
        start_time = time.time()

        try:
            # Get CPU usage with interval
            cpu_percent = await asyncio.get_event_loop().run_in_executor(
                None, lambda: psutil.cpu_percent(interval=self.cpu_interval)
            )

            # Get CPU info
            cpu_count = psutil.cpu_count()
            cpu_count_logical = psutil.cpu_count(logical=True)

            # Get load averages (if available)
            try:
                load_avg = psutil.getloadavg()
                load_1min, load_5min, load_15min = load_avg
            except (AttributeError, OSError):
                # Not available on Windows
                load_1min = load_5min = load_15min = None

            # Determine status
            if cpu_percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"CPU usage critical: {cpu_percent:.1f}%"
            elif cpu_percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"CPU usage warning: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage healthy: {cpu_percent:.1f}%"

            duration = time.time() - start_time

            details = {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "cpu_count_logical": cpu_count_logical,
                "warning_threshold": self.warning_threshold,
                "critical_threshold": self.critical_threshold,
                "measurement_interval": self.cpu_interval,
            }

            # Add load averages if available
            if load_1min is not None:
                details.update(
                    {
                        "load_1min": load_1min,
                        "load_5min": load_5min,
                        "load_15min": load_15min,
                    }
                )

            return HealthResult(
                name=self.name,
                status=status,
                message=message,
                duration=duration,
                details=details,
            )

        except Exception as e:
            duration = time.time() - start_time
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"CPU check failed: {str(e)}",
                duration=duration,
                error=str(e),
            )


class RedisHealthCheck(HealthCheck):
    """Redis connectivity health check"""

    def __init__(self, redis_url: str, name: str = "redis", timeout: float = 5.0):
        super().__init__(name, timeout)
        self.redis_url = redis_url

    async def check(self) -> HealthResult:
        """Perform Redis health check"""
        start_time = time.time()

        try:
            import redis.asyncio as redis

            # Create Redis client
            redis_client = redis.from_url(self.redis_url)

            # Test ping
            ping_start = time.time()
            await redis_client.ping()
            ping_duration = time.time() - ping_start

            # Get Redis info
            info = await redis_client.info()

            # Close connection
            await redis_client.close()

            duration = time.time() - start_time

            return HealthResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message=f"Redis healthy (ping: {ping_duration:.3f}s)",
                duration=duration,
                details={
                    "ping_duration": ping_duration,
                    "redis_version": info.get("redis_version"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory_human": info.get("used_memory_human"),
                    "uptime_in_seconds": info.get("uptime_in_seconds"),
                },
            )

        except Exception as e:
            duration = time.time() - start_time
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis check failed: {str(e)}",
                duration=duration,
                error=str(e),
            )
