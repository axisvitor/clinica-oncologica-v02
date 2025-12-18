"""
Resource Monitoring System.

Tracks CPU, memory, disk I/O, network, and process metrics.
"""

import asyncio
import psutil
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timedelta
import threading
import redis.asyncio as redis


logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    """Resource usage snapshot at a point in time."""

    timestamp: datetime
    cpu_percent: float
    cpu_cores: List[float]
    memory_total: int
    memory_available: int
    memory_used: int
    memory_percent: float
    disk_read_bytes: int
    disk_write_bytes: int
    disk_read_count: int
    disk_write_count: int
    network_bytes_sent: int
    network_bytes_recv: int
    network_packets_sent: int
    network_packets_recv: int
    process_count: int
    thread_count: int
    file_descriptors: int
    load_average: List[float]


class ResourceMonitor:
    """System resource monitoring."""

    def __init__(
        self, redis_client: Optional[redis.Redis] = None, sample_interval: float = 10.0
    ):
        self.redis_client = redis_client
        self.sample_interval = sample_interval
        self.snapshots: deque = deque(maxlen=720)  # 2 hours at 10s intervals
        self.monitoring_active = False
        self.monitor_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()

        # Alert thresholds
        self.cpu_threshold = 80.0
        self.memory_threshold = 85.0
        self.disk_threshold = 90.0

        # Previous values for rate calculations
        self._prev_disk_io = None
        self._prev_network_io = None
        self._prev_timestamp = None

    async def start_monitoring(self) -> None:
        """Start continuous resource monitoring."""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Resource monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        self.monitoring_active = False

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
            self.monitor_task = None

        logger.info("Resource monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                snapshot = await self._collect_snapshot()

                with self._lock:
                    self.snapshots.append(snapshot)

                # Store in Redis
                if self.redis_client:
                    await self._store_snapshot_redis(snapshot)

                # Check for alerts
                await self._check_alerts(snapshot)

                await asyncio.sleep(self.sample_interval)

            except Exception as e:
                logger.error(f"Error in resource monitoring loop: {e}")
                await asyncio.sleep(self.sample_interval)

    async def _collect_snapshot(self) -> ResourceSnapshot:
        """Collect current resource usage snapshot."""
        current_time = datetime.utcnow()

        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_cores = psutil.cpu_percent(interval=None, percpu=True)

        # Memory metrics
        memory = psutil.virtual_memory()

        # Disk I/O metrics
        disk_io = psutil.disk_io_counters()

        # Network I/O metrics
        network_io = psutil.net_io_counters()

        # Process metrics
        process_count = len(psutil.pids())

        # Current process metrics
        current_process = psutil.Process()
        thread_count = current_process.num_threads()

        try:
            file_descriptors = current_process.num_fds()
        except AttributeError:
            # Windows doesn't have num_fds
            file_descriptors = 0

        # Load average (Unix-like systems only)
        try:
            load_average = list(psutil.getloadavg())
        except AttributeError:
            # Windows doesn't have load average
            load_average = [0.0, 0.0, 0.0]

        return ResourceSnapshot(
            timestamp=current_time,
            cpu_percent=cpu_percent,
            cpu_cores=cpu_cores,
            memory_total=memory.total,
            memory_available=memory.available,
            memory_used=memory.used,
            memory_percent=memory.percent,
            disk_read_bytes=disk_io.read_bytes if disk_io else 0,
            disk_write_bytes=disk_io.write_bytes if disk_io else 0,
            disk_read_count=disk_io.read_count if disk_io else 0,
            disk_write_count=disk_io.write_count if disk_io else 0,
            network_bytes_sent=network_io.bytes_sent if network_io else 0,
            network_bytes_recv=network_io.bytes_recv if network_io else 0,
            network_packets_sent=network_io.packets_sent if network_io else 0,
            network_packets_recv=network_io.packets_recv if network_io else 0,
            process_count=process_count,
            thread_count=thread_count,
            file_descriptors=file_descriptors,
            load_average=load_average,
        )

    async def _store_snapshot_redis(self, snapshot: ResourceSnapshot) -> None:
        """Store snapshot in Redis for real-time access."""
        try:
            timestamp = int(snapshot.timestamp.timestamp())

            # Store current metrics
            metrics = {
                "timestamp": timestamp,
                "cpu_percent": snapshot.cpu_percent,
                "memory_percent": snapshot.memory_percent,
                "memory_used_gb": snapshot.memory_used / (1024**3),
                "memory_total_gb": snapshot.memory_total / (1024**3),
                "process_count": snapshot.process_count,
                "thread_count": snapshot.thread_count,
                "load_average_1m": snapshot.load_average[0]
                if snapshot.load_average
                else 0,
            }

            # Calculate rates if we have previous data
            if self._prev_disk_io and self._prev_network_io and self._prev_timestamp:
                time_delta = (snapshot.timestamp - self._prev_timestamp).total_seconds()

                if time_delta > 0:
                    # Disk I/O rates
                    disk_read_rate = (
                        snapshot.disk_read_bytes - self._prev_disk_io[0]
                    ) / time_delta
                    disk_write_rate = (
                        snapshot.disk_write_bytes - self._prev_disk_io[1]
                    ) / time_delta

                    # Network I/O rates
                    net_recv_rate = (
                        snapshot.network_bytes_recv - self._prev_network_io[0]
                    ) / time_delta
                    net_sent_rate = (
                        snapshot.network_bytes_sent - self._prev_network_io[1]
                    ) / time_delta

                    metrics.update(
                        {
                            "disk_read_rate_mbps": disk_read_rate / (1024**2),
                            "disk_write_rate_mbps": disk_write_rate / (1024**2),
                            "network_recv_rate_mbps": net_recv_rate / (1024**2),
                            "network_sent_rate_mbps": net_sent_rate / (1024**2),
                        }
                    )

            # Store in Redis
            await self.redis_client.lpush("resource_monitor:snapshots", str(metrics))

            # Keep only last 720 snapshots (2 hours at 10s intervals)
            await self.redis_client.ltrim("resource_monitor:snapshots", 0, 719)

            # Store latest metrics in hash for quick access
            await self.redis_client.hset(
                "resource_monitor:latest",
                mapping={k: str(v) for k, v in metrics.items()},
            )

            # Set expiration
            await self.redis_client.expire("resource_monitor:latest", 300)  # 5 minutes

            # Update previous values
            self._prev_disk_io = (snapshot.disk_read_bytes, snapshot.disk_write_bytes)
            self._prev_network_io = (
                snapshot.network_bytes_recv,
                snapshot.network_bytes_sent,
            )
            self._prev_timestamp = snapshot.timestamp

        except Exception as e:
            logger.error(f"Failed to store resource snapshot in Redis: {e}")

    async def _check_alerts(self, snapshot: ResourceSnapshot) -> None:
        """Check for resource usage alerts."""
        alerts = []

        # CPU alert
        if snapshot.cpu_percent > self.cpu_threshold:
            alerts.append(
                {
                    "type": "high_cpu",
                    "severity": "warning" if snapshot.cpu_percent < 95 else "critical",
                    "message": f"High CPU usage: {snapshot.cpu_percent:.1f}%",
                    "value": snapshot.cpu_percent,
                    "threshold": self.cpu_threshold,
                }
            )

        # Memory alert
        if snapshot.memory_percent > self.memory_threshold:
            alerts.append(
                {
                    "type": "high_memory",
                    "severity": "warning"
                    if snapshot.memory_percent < 95
                    else "critical",
                    "message": f"High memory usage: {snapshot.memory_percent:.1f}%",
                    "value": snapshot.memory_percent,
                    "threshold": self.memory_threshold,
                }
            )

        # Store alerts in Redis
        if alerts and self.redis_client:
            try:
                for alert in alerts:
                    alert["timestamp"] = int(snapshot.timestamp.timestamp())
                    await self.redis_client.lpush("resource_monitor:alerts", str(alert))

                await self.redis_client.ltrim("resource_monitor:alerts", 0, 99)
            except Exception as e:
                logger.error(f"Failed to store alerts in Redis: {e}")

    def get_current_stats(self) -> Dict[str, Any]:
        """Get current resource statistics."""
        with self._lock:
            if not self.snapshots:
                return self._empty_stats()

            latest = self.snapshots[-1]

            return {
                "timestamp": latest.timestamp.isoformat(),
                "cpu": {
                    "percent": latest.cpu_percent,
                    "cores": latest.cpu_cores,
                    "load_average": latest.load_average,
                },
                "memory": {
                    "total_gb": latest.memory_total / (1024**3),
                    "used_gb": latest.memory_used / (1024**3),
                    "available_gb": latest.memory_available / (1024**3),
                    "percent": latest.memory_percent,
                },
                "disk": {
                    "read_bytes": latest.disk_read_bytes,
                    "write_bytes": latest.disk_write_bytes,
                    "read_count": latest.disk_read_count,
                    "write_count": latest.disk_write_count,
                },
                "network": {
                    "bytes_sent": latest.network_bytes_sent,
                    "bytes_recv": latest.network_bytes_recv,
                    "packets_sent": latest.network_packets_sent,
                    "packets_recv": latest.network_packets_recv,
                },
                "processes": {
                    "count": latest.process_count,
                    "threads": latest.thread_count,
                    "file_descriptors": latest.file_descriptors,
                },
            }

    def get_historical_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """Get historical resource statistics."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

        with self._lock:
            recent_snapshots = [s for s in self.snapshots if s.timestamp >= cutoff_time]

        if not recent_snapshots:
            return self._empty_historical_stats()

        # Calculate statistics
        cpu_values = [s.cpu_percent for s in recent_snapshots]
        memory_values = [s.memory_percent for s in recent_snapshots]

        return {
            "time_range_minutes": minutes,
            "sample_count": len(recent_snapshots),
            "cpu": {
                "avg": sum(cpu_values) / len(cpu_values),
                "min": min(cpu_values),
                "max": max(cpu_values),
                "current": cpu_values[-1] if cpu_values else 0,
            },
            "memory": {
                "avg": sum(memory_values) / len(memory_values),
                "min": min(memory_values),
                "max": max(memory_values),
                "current": memory_values[-1] if memory_values else 0,
            },
            "trends": self._calculate_trends(recent_snapshots),
        }

    def get_system_info(self) -> Dict[str, Any]:
        """Get static system information."""
        try:
            # CPU info
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()

            # Memory info
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # Disk info
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage[partition.device] = {
                        "total_gb": usage.total / (1024**3),
                        "used_gb": usage.used / (1024**3),
                        "free_gb": usage.free / (1024**3),
                        "percent": (usage.used / usage.total) * 100,
                        "filesystem": partition.fstype,
                        "mountpoint": partition.mountpoint,
                    }
                except PermissionError:
                    continue

            # Network interfaces
            network_interfaces = {}
            for interface, stats in psutil.net_if_stats().items():
                network_interfaces[interface] = {
                    "is_up": stats.isup,
                    "speed_mbps": stats.speed,
                    "mtu": stats.mtu,
                }

            return {
                "cpu": {
                    "count": cpu_count,
                    "frequency_mhz": cpu_freq.current if cpu_freq else None,
                    "frequency_max_mhz": cpu_freq.max if cpu_freq else None,
                },
                "memory": {
                    "total_gb": memory.total / (1024**3),
                    "swap_total_gb": swap.total / (1024**3),
                },
                "disk": disk_usage,
                "network": network_interfaces,
                "platform": {
                    "system": psutil.LINUX if hasattr(psutil, "LINUX") else "unknown",
                    "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                },
            }
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {}

    def _calculate_trends(self, snapshots: List[ResourceSnapshot]) -> Dict[str, str]:
        """Calculate trends for metrics."""
        if len(snapshots) < 2:
            return {"cpu": "stable", "memory": "stable"}

        # Calculate trends based on first and last values
        first = snapshots[0]
        last = snapshots[-1]

        cpu_trend = "stable"
        if last.cpu_percent > first.cpu_percent + 5:
            cpu_trend = "increasing"
        elif last.cpu_percent < first.cpu_percent - 5:
            cpu_trend = "decreasing"

        memory_trend = "stable"
        if last.memory_percent > first.memory_percent + 5:
            memory_trend = "increasing"
        elif last.memory_percent < first.memory_percent - 5:
            memory_trend = "decreasing"

        return {"cpu": cpu_trend, "memory": memory_trend}

    def _empty_stats(self) -> Dict[str, Any]:
        """Return empty stats structure."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu": {"percent": 0, "cores": [], "load_average": [0, 0, 0]},
            "memory": {"total_gb": 0, "used_gb": 0, "available_gb": 0, "percent": 0},
            "disk": {
                "read_bytes": 0,
                "write_bytes": 0,
                "read_count": 0,
                "write_count": 0,
            },
            "network": {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_sent": 0,
                "packets_recv": 0,
            },
            "processes": {"count": 0, "threads": 0, "file_descriptors": 0},
        }

    def _empty_historical_stats(self) -> Dict[str, Any]:
        """Return empty historical stats structure."""
        return {
            "time_range_minutes": 0,
            "sample_count": 0,
            "cpu": {"avg": 0, "min": 0, "max": 0, "current": 0},
            "memory": {"avg": 0, "min": 0, "max": 0, "current": 0},
            "trends": {"cpu": "stable", "memory": "stable"},
        }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self.snapshots.clear()
            self._prev_disk_io = None
            self._prev_network_io = None
            self._prev_timestamp = None
