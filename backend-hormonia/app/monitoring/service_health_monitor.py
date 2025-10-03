"""
Service Health Monitoring
Monitor API endpoints, databases, and external services.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis import asyncio as aioredis

logger = logging.getLogger(__name__)


class ServiceType(str, Enum):
    """Service type categories"""
    API = "api"
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL = "external"
    MESSAGING = "messaging"


class HealthStatus(str, Enum):
    """Health check status"""
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    service_name: str
    service_type: ServiceType
    status: HealthStatus
    response_time_ms: float
    checked_at: datetime
    details: Dict[str, Any]
    error: Optional[str] = None
    consecutive_failures: int = 0
    uptime_percentage: float = 100.0


@dataclass
class SLAMetrics:
    """Service Level Agreement metrics"""
    service_name: str
    availability_target: float  # e.g., 99.9%
    response_time_target_ms: float  # e.g., 1000ms
    error_rate_target: float  # e.g., 0.1%
    current_availability: float
    current_response_time: float
    current_error_rate: float
    sla_met: bool
    period_start: datetime
    period_end: datetime


class EndpointHealthChecker:
    """Check API endpoint health"""

    def __init__(self, timeout_seconds: int = 10):
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.session: Optional[aiohttp.ClientSession] = None

    async def ensure_session(self):
        """Ensure HTTP session is created"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def check_endpoint(
        self,
        url: str,
        method: str = "GET",
        expected_status: int = 200,
        headers: Optional[Dict] = None
    ) -> HealthCheckResult:
        """Check a single endpoint"""
        await self.ensure_session()

        start_time = time.time()
        status = HealthStatus.UNKNOWN
        error = None
        details = {}

        try:
            async with self.session.request(method, url, headers=headers) as response:
                response_time = (time.time() - start_time) * 1000

                if response.status == expected_status:
                    status = HealthStatus.UP
                else:
                    status = HealthStatus.DEGRADED
                    error = f"Unexpected status: {response.status}"

                details = {
                    'status_code': response.status,
                    'headers': dict(response.headers),
                    'url': str(response.url)
                }

        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            status = HealthStatus.DOWN
            error = "Request timeout"

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            status = HealthStatus.DOWN
            error = str(e)

        return HealthCheckResult(
            service_name=url,
            service_type=ServiceType.API,
            status=status,
            response_time_ms=response_time,
            checked_at=datetime.utcnow(),
            details=details,
            error=error
        )

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()


class DatabaseHealthChecker:
    """Check database health"""

    async def check_postgres(
        self,
        db: AsyncSession,
        timeout_seconds: int = 5
    ) -> HealthCheckResult:
        """Check PostgreSQL health"""
        start_time = time.time()
        status = HealthStatus.UNKNOWN
        error = None
        details = {}

        try:
            # Simple query to check connectivity
            result = await db.execute(text("SELECT 1"))
            result.scalar()

            # Get database stats
            stats_query = text("""
                SELECT
                    pg_database_size(current_database()) as size,
                    (SELECT count(*) FROM pg_stat_activity) as connections
            """)
            stats = await db.execute(stats_query)
            row = stats.fetchone()

            response_time = (time.time() - start_time) * 1000
            status = HealthStatus.UP

            details = {
                'database_size_mb': row[0] / 1024 / 1024 if row else 0,
                'active_connections': row[1] if row else 0
            }

        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            status = HealthStatus.DOWN
            error = "Database query timeout"

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            status = HealthStatus.DOWN
            error = str(e)

        return HealthCheckResult(
            service_name="PostgreSQL",
            service_type=ServiceType.DATABASE,
            status=status,
            response_time_ms=response_time,
            checked_at=datetime.utcnow(),
            details=details,
            error=error
        )


class CacheHealthChecker:
    """Check Redis cache health"""

    async def check_redis(
        self,
        redis_url: str,
        timeout_seconds: int = 5
    ) -> HealthCheckResult:
        """Check Redis health"""
        start_time = time.time()
        status = HealthStatus.UNKNOWN
        error = None
        details = {}
        redis_client = None

        try:
            redis_client = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )

            # Ping Redis
            await redis_client.ping()

            # Get Redis info
            info = await redis_client.info()

            response_time = (time.time() - start_time) * 1000
            status = HealthStatus.UP

            details = {
                'redis_version': info.get('redis_version'),
                'used_memory_mb': info.get('used_memory', 0) / 1024 / 1024,
                'connected_clients': info.get('connected_clients', 0),
                'uptime_seconds': info.get('uptime_in_seconds', 0)
            }

        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            status = HealthStatus.DOWN
            error = "Redis ping timeout"

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            status = HealthStatus.DOWN
            error = str(e)

        finally:
            if redis_client:
                await redis_client.close()

        return HealthCheckResult(
            service_name="Redis",
            service_type=ServiceType.CACHE,
            status=status,
            response_time_ms=response_time,
            checked_at=datetime.utcnow(),
            details=details,
            error=error
        )


class ServiceHealthMonitor:
    """Main service health monitoring system"""

    def __init__(self):
        self.endpoint_checker = EndpointHealthChecker()
        self.db_checker = DatabaseHealthChecker()
        self.cache_checker = CacheHealthChecker()

        self.health_history: Dict[str, List[HealthCheckResult]] = {}
        self.max_history = 1000

        # SLA targets
        self.sla_targets = {
            'api_availability': 99.9,
            'api_response_time_ms': 1000,
            'database_availability': 99.95,
            'cache_availability': 99.9
        }

    async def check_all_services(
        self,
        api_endpoints: List[str],
        db_session: Optional[AsyncSession] = None,
        redis_url: Optional[str] = None
    ) -> Dict[str, HealthCheckResult]:
        """Check health of all configured services"""
        results = {}

        # Check API endpoints
        for endpoint in api_endpoints:
            result = await self.endpoint_checker.check_endpoint(endpoint)
            results[f"api_{endpoint}"] = result
            self._update_history(f"api_{endpoint}", result)

        # Check database
        if db_session:
            result = await self.db_checker.check_postgres(db_session)
            results['database'] = result
            self._update_history('database', result)

        # Check Redis
        if redis_url:
            result = await self.cache_checker.check_redis(redis_url)
            results['redis'] = result
            self._update_history('redis', result)

        return results

    def _update_history(self, service_name: str, result: HealthCheckResult):
        """Update service health history"""
        if service_name not in self.health_history:
            self.health_history[service_name] = []

        self.health_history[service_name].append(result)

        # Trim history if needed
        if len(self.health_history[service_name]) > self.max_history:
            self.health_history[service_name] = \
                self.health_history[service_name][-self.max_history:]

    async def calculate_sla_metrics(
        self,
        service_name: str,
        hours: int = 24
    ) -> Optional[SLAMetrics]:
        """Calculate SLA metrics for a service"""
        if service_name not in self.health_history:
            return None

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_checks = [
            check for check in self.health_history[service_name]
            if check.checked_at >= cutoff_time
        ]

        if not recent_checks:
            return None

        # Calculate availability
        up_checks = [c for c in recent_checks if c.status == HealthStatus.UP]
        availability = (len(up_checks) / len(recent_checks)) * 100

        # Calculate average response time
        response_times = [c.response_time_ms for c in recent_checks if c.status == HealthStatus.UP]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # Calculate error rate
        error_checks = [c for c in recent_checks if c.status == HealthStatus.DOWN]
        error_rate = (len(error_checks) / len(recent_checks)) * 100

        # Determine if SLA is met
        sla_met = (
            availability >= self.sla_targets.get('api_availability', 99.9) and
            avg_response_time <= self.sla_targets.get('api_response_time_ms', 1000)
        )

        return SLAMetrics(
            service_name=service_name,
            availability_target=self.sla_targets.get('api_availability', 99.9),
            response_time_target_ms=self.sla_targets.get('api_response_time_ms', 1000),
            error_rate_target=0.1,
            current_availability=availability,
            current_response_time=avg_response_time,
            current_error_rate=error_rate,
            sla_met=sla_met,
            period_start=cutoff_time,
            period_end=datetime.utcnow()
        )

    async def get_uptime_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate uptime report for all services"""
        report = {}
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        for service_name, history in self.health_history.items():
            recent_checks = [
                c for c in history if c.checked_at >= cutoff_time
            ]

            if not recent_checks:
                continue

            up_time = len([c for c in recent_checks if c.status == HealthStatus.UP])
            total_time = len(recent_checks)
            uptime_percentage = (up_time / total_time) * 100 if total_time > 0 else 0

            # Get current status
            current_status = recent_checks[-1].status if recent_checks else HealthStatus.UNKNOWN

            # Calculate consecutive failures
            consecutive_failures = 0
            for check in reversed(recent_checks):
                if check.status == HealthStatus.DOWN:
                    consecutive_failures += 1
                else:
                    break

            report[service_name] = {
                'status': current_status,
                'uptime_percentage': uptime_percentage,
                'total_checks': total_time,
                'successful_checks': up_time,
                'consecutive_failures': consecutive_failures,
                'last_check': recent_checks[-1].checked_at.isoformat() if recent_checks else None
            }

        return report

    async def start_monitoring(
        self,
        api_endpoints: List[str],
        check_interval_seconds: int = 60,
        db_session: Optional[AsyncSession] = None,
        redis_url: Optional[str] = None
    ):
        """Start continuous service health monitoring"""
        logger.info(f"Starting service health monitoring (interval: {check_interval_seconds}s)")

        while True:
            try:
                results = await self.check_all_services(
                    api_endpoints,
                    db_session,
                    redis_url
                )

                # Log results
                for service, result in results.items():
                    if result.status == HealthStatus.DOWN:
                        logger.error(
                            f"Service {service} is DOWN: {result.error} "
                            f"(response time: {result.response_time_ms:.2f}ms)"
                        )
                    elif result.status == HealthStatus.DEGRADED:
                        logger.warning(
                            f"Service {service} is DEGRADED: {result.error} "
                            f"(response time: {result.response_time_ms:.2f}ms)"
                        )
                    else:
                        logger.info(
                            f"Service {service} is UP "
                            f"(response time: {result.response_time_ms:.2f}ms)"
                        )

                await asyncio.sleep(check_interval_seconds)

            except Exception as e:
                logger.error(f"Error in service monitoring loop: {e}")
                await asyncio.sleep(check_interval_seconds)

    async def cleanup(self):
        """Cleanup resources"""
        await self.endpoint_checker.close()


# Global monitor instance
service_health_monitor = ServiceHealthMonitor()