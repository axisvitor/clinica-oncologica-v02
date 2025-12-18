"""
Infrastructure Monitoring System
Comprehensive system resource and health monitoring for the healthcare platform.
"""

import asyncio
import psutil
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class ResourceStatus(str, Enum):
    """Resource health status"""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class ResourceMetrics:
    """Resource utilization metrics"""

    cpu_percent: float
    cpu_count: int
    cpu_per_core: List[float]
    memory_total: int
    memory_used: int
    memory_percent: float
    memory_available: int
    disk_total: int
    disk_used: int
    disk_percent: float
    disk_io_read_bytes: int
    disk_io_write_bytes: int
    network_bytes_sent: int
    network_bytes_recv: int
    network_packets_sent: int
    network_packets_recv: int
    timestamp: datetime
    status: ResourceStatus


@dataclass
class ProcessMetrics:
    """Process-level metrics"""

    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    memory_rss: int
    num_threads: int
    num_fds: int
    status: str
    create_time: float
    timestamp: datetime


@dataclass
class ServiceHealth:
    """Service health check result"""

    service_name: str
    is_healthy: bool
    response_time_ms: float
    status_code: Optional[int]
    error_message: Optional[str]
    last_check: datetime
    consecutive_failures: int


@dataclass
class InfrastructureAlert:
    """Infrastructure alert"""

    alert_id: str
    severity: AlertSeverity
    resource_type: str
    message: str
    metric_name: str
    current_value: float
    threshold_value: float
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class ResourceMonitor:
    """Monitor system resource utilization"""

    def __init__(self, history_size: int = 300):
        self.history_size = history_size
        self.cpu_history = deque(maxlen=history_size)
        self.memory_history = deque(maxlen=history_size)
        self.disk_history = deque(maxlen=history_size)
        self.network_history = deque(maxlen=history_size)

        # Thresholds
        self.cpu_warning_threshold = 70.0
        self.cpu_critical_threshold = 90.0
        self.memory_warning_threshold = 75.0
        self.memory_critical_threshold = 90.0
        self.disk_warning_threshold = 80.0
        self.disk_critical_threshold = 95.0

    async def collect_metrics(self) -> ResourceMetrics:
        """Collect current resource metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
            cpu_count = psutil.cpu_count()

            # Memory metrics
            memory = psutil.virtual_memory()

            # Disk metrics
            disk = psutil.disk_usage("/")
            disk_io = psutil.disk_io_counters()

            # Network metrics
            net_io = psutil.net_io_counters()

            # Determine status
            status = self._determine_status(cpu_percent, memory.percent, disk.percent)

            metrics = ResourceMetrics(
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                cpu_per_core=cpu_per_core,
                memory_total=memory.total,
                memory_used=memory.used,
                memory_percent=memory.percent,
                memory_available=memory.available,
                disk_total=disk.total,
                disk_used=disk.used,
                disk_percent=disk.percent,
                disk_io_read_bytes=disk_io.read_bytes,
                disk_io_write_bytes=disk_io.write_bytes,
                network_bytes_sent=net_io.bytes_sent,
                network_bytes_recv=net_io.bytes_recv,
                network_packets_sent=net_io.packets_sent,
                network_packets_recv=net_io.packets_recv,
                timestamp=datetime.utcnow(),
                status=status,
            )

            # Update history
            self.cpu_history.append(cpu_percent)
            self.memory_history.append(memory.percent)
            self.disk_history.append(disk.percent)
            self.network_history.append(
                {
                    "sent": net_io.bytes_sent,
                    "recv": net_io.bytes_recv,
                    "timestamp": time.time(),
                }
            )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting resource metrics: {e}")
            raise

    def _determine_status(
        self, cpu_percent: float, memory_percent: float, disk_percent: float
    ) -> ResourceStatus:
        """Determine overall resource status"""
        if (
            cpu_percent >= self.cpu_critical_threshold
            or memory_percent >= self.memory_critical_threshold
            or disk_percent >= self.disk_critical_threshold
        ):
            return ResourceStatus.CRITICAL

        if (
            cpu_percent >= self.cpu_warning_threshold
            or memory_percent >= self.memory_warning_threshold
            or disk_percent >= self.disk_warning_threshold
        ):
            return ResourceStatus.WARNING

        return ResourceStatus.HEALTHY

    async def get_trends(self, minutes: int = 30) -> Dict[str, Any]:
        """Calculate resource usage trends"""
        try:
            cpu_data = list(self.cpu_history)[-minutes:]
            memory_data = list(self.memory_history)[-minutes:]

            if not cpu_data or not memory_data:
                return {}

            return {
                "cpu": {
                    "current": cpu_data[-1] if cpu_data else 0,
                    "average": statistics.mean(cpu_data),
                    "max": max(cpu_data),
                    "min": min(cpu_data),
                    "trend": self._calculate_trend(cpu_data),
                },
                "memory": {
                    "current": memory_data[-1] if memory_data else 0,
                    "average": statistics.mean(memory_data),
                    "max": max(memory_data),
                    "min": min(memory_data),
                    "trend": self._calculate_trend(memory_data),
                },
            }
        except Exception as e:
            logger.error(f"Error calculating trends: {e}")
            return {}

    def _calculate_trend(self, data: List[float]) -> str:
        """Calculate trend direction"""
        if len(data) < 2:
            return "stable"

        # Simple linear regression
        n = len(data)
        x = list(range(n))
        y = data

        x_mean = sum(x) / n
        y_mean = sum(y) / n

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return "stable"

        slope = numerator / denominator

        if slope > 0.5:
            return "increasing"
        elif slope < -0.5:
            return "decreasing"
        else:
            return "stable"

    async def check_memory_leaks(self, threshold_mb: int = 100) -> List[Dict]:
        """Detect potential memory leaks"""
        leaks = []

        try:
            for proc in psutil.process_iter(["pid", "name", "memory_info"]):
                try:
                    memory_mb = proc.info["memory_info"].rss / 1024 / 1024

                    if memory_mb > threshold_mb:
                        leaks.append(
                            {
                                "pid": proc.info["pid"],
                                "name": proc.info["name"],
                                "memory_mb": memory_mb,
                                "timestamp": datetime.utcnow(),
                            }
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return leaks

        except Exception as e:
            logger.error(f"Error checking memory leaks: {e}")
            return []


class ProcessMonitor:
    """Monitor application processes"""

    def __init__(self, process_names: List[str]):
        self.process_names = process_names
        self.process_history = {}

    async def collect_process_metrics(self) -> List[ProcessMetrics]:
        """Collect metrics for monitored processes"""
        metrics = []

        try:
            for proc in psutil.process_iter(
                [
                    "pid",
                    "name",
                    "cpu_percent",
                    "memory_percent",
                    "memory_info",
                    "num_threads",
                    "status",
                    "create_time",
                ]
            ):
                try:
                    if proc.info["name"] in self.process_names:
                        # Get file descriptors count (Unix only)
                        num_fds = 0
                        try:
                            num_fds = proc.num_fds()
                        except (AttributeError, psutil.AccessDenied):
                            pass

                        metrics.append(
                            ProcessMetrics(
                                pid=proc.info["pid"],
                                name=proc.info["name"],
                                cpu_percent=proc.info["cpu_percent"] or 0,
                                memory_percent=proc.info["memory_percent"] or 0,
                                memory_rss=proc.info["memory_info"].rss,
                                num_threads=proc.info["num_threads"],
                                num_fds=num_fds,
                                status=proc.info["status"],
                                create_time=proc.info["create_time"],
                                timestamp=datetime.utcnow(),
                            )
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return metrics

        except Exception as e:
            logger.error(f"Error collecting process metrics: {e}")
            return []

    async def check_process_health(self) -> Dict[str, bool]:
        """Check if monitored processes are running"""
        health = {}

        for process_name in self.process_names:
            health[process_name] = any(
                p.info["name"] == process_name for p in psutil.process_iter(["name"])
            )

        return health


class InfrastructureMonitor:
    """Main infrastructure monitoring system"""

    def __init__(self):
        self.resource_monitor = ResourceMonitor()
        self.process_monitor = ProcessMonitor(
            ["python", "uvicorn", "gunicorn", "nginx", "redis-server", "postgres"]
        )
        self.alerts: List[InfrastructureAlert] = []
        self.service_health: Dict[str, ServiceHealth] = {}

    async def start_monitoring(self, interval_seconds: int = 60):
        """Start continuous monitoring"""
        logger.info("Starting infrastructure monitoring")

        while True:
            try:
                # Collect metrics
                resource_metrics = await self.resource_monitor.collect_metrics()
                await self.process_monitor.collect_process_metrics()

                # Check for alerts
                await self._check_resource_alerts(resource_metrics)

                # Check process health
                process_health = await self.process_monitor.check_process_health()
                await self._check_process_alerts(process_health)

                # Check for memory leaks
                leaks = await self.resource_monitor.check_memory_leaks()
                if leaks:
                    await self._alert_memory_leaks(leaks)

                # Log metrics
                logger.info(
                    f"Infrastructure metrics - "
                    f"CPU: {resource_metrics.cpu_percent}%, "
                    f"Memory: {resource_metrics.memory_percent}%, "
                    f"Disk: {resource_metrics.disk_percent}%, "
                    f"Status: {resource_metrics.status}"
                )

                await asyncio.sleep(interval_seconds)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)

    async def _check_resource_alerts(self, metrics: ResourceMetrics):
        """Check resource metrics against thresholds"""
        # CPU alerts
        if metrics.cpu_percent >= 90:
            await self._create_alert(
                AlertSeverity.CRITICAL,
                "cpu",
                f"Critical CPU usage: {metrics.cpu_percent}%",
                "cpu_percent",
                metrics.cpu_percent,
                90.0,
            )
        elif metrics.cpu_percent >= 70:
            await self._create_alert(
                AlertSeverity.WARNING,
                "cpu",
                f"High CPU usage: {metrics.cpu_percent}%",
                "cpu_percent",
                metrics.cpu_percent,
                70.0,
            )

        # Memory alerts
        if metrics.memory_percent >= 90:
            await self._create_alert(
                AlertSeverity.CRITICAL,
                "memory",
                f"Critical memory usage: {metrics.memory_percent}%",
                "memory_percent",
                metrics.memory_percent,
                90.0,
            )
        elif metrics.memory_percent >= 75:
            await self._create_alert(
                AlertSeverity.WARNING,
                "memory",
                f"High memory usage: {metrics.memory_percent}%",
                "memory_percent",
                metrics.memory_percent,
                75.0,
            )

        # Disk alerts
        if metrics.disk_percent >= 95:
            await self._create_alert(
                AlertSeverity.CRITICAL,
                "disk",
                f"Critical disk usage: {metrics.disk_percent}%",
                "disk_percent",
                metrics.disk_percent,
                95.0,
            )
        elif metrics.disk_percent >= 80:
            await self._create_alert(
                AlertSeverity.WARNING,
                "disk",
                f"High disk usage: {metrics.disk_percent}%",
                "disk_percent",
                metrics.disk_percent,
                80.0,
            )

    async def _check_process_alerts(self, health: Dict[str, bool]):
        """Check process health status"""
        for process_name, is_healthy in health.items():
            if not is_healthy:
                await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "process",
                    f"Process {process_name} is not running",
                    "process_status",
                    0.0,
                    1.0,
                )

    async def _alert_memory_leaks(self, leaks: List[Dict]):
        """Create alerts for potential memory leaks"""
        for leak in leaks:
            await self._create_alert(
                AlertSeverity.WARNING,
                "memory_leak",
                f"Potential memory leak in {leak['name']} (PID: {leak['pid']}): {leak['memory_mb']:.2f} MB",
                "memory_usage",
                leak["memory_mb"],
                100.0,
            )

    async def _create_alert(
        self,
        severity: AlertSeverity,
        resource_type: str,
        message: str,
        metric_name: str,
        current_value: float,
        threshold_value: float,
    ):
        """Create and store an alert"""
        alert = InfrastructureAlert(
            alert_id=f"{resource_type}_{int(time.time() * 1000)}",
            severity=severity,
            resource_type=resource_type,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=threshold_value,
            timestamp=datetime.utcnow(),
        )

        self.alerts.append(alert)
        logger.warning(f"Infrastructure alert: {message}")

    async def get_health_summary(self) -> Dict[str, Any]:
        """Get overall infrastructure health summary"""
        metrics = await self.resource_monitor.collect_metrics()
        trends = await self.resource_monitor.get_trends()
        active_alerts = [a for a in self.alerts if not a.resolved]

        return {
            "status": metrics.status,
            "timestamp": datetime.utcnow().isoformat(),
            "resources": {
                "cpu": {
                    "current": metrics.cpu_percent,
                    "count": metrics.cpu_count,
                    "per_core": metrics.cpu_per_core,
                },
                "memory": {
                    "used_gb": metrics.memory_used / 1024 / 1024 / 1024,
                    "total_gb": metrics.memory_total / 1024 / 1024 / 1024,
                    "percent": metrics.memory_percent,
                },
                "disk": {
                    "used_gb": metrics.disk_used / 1024 / 1024 / 1024,
                    "total_gb": metrics.disk_total / 1024 / 1024 / 1024,
                    "percent": metrics.disk_percent,
                },
            },
            "trends": trends,
            "alerts": {
                "total": len(self.alerts),
                "active": len(active_alerts),
                "by_severity": {
                    "critical": len(
                        [
                            a
                            for a in active_alerts
                            if a.severity == AlertSeverity.CRITICAL
                        ]
                    ),
                    "warning": len(
                        [
                            a
                            for a in active_alerts
                            if a.severity == AlertSeverity.WARNING
                        ]
                    ),
                },
            },
            "services": self.service_health,
        }


# Global monitor instance
infrastructure_monitor = InfrastructureMonitor()
