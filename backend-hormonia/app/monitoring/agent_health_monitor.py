"""
Agent Health Monitoring System

Monitors the health, performance, and status of all agents in the Hive-Mind system.
Provides real-time metrics, alerts, and automatic recovery mechanisms.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from uuid import uuid4
from enum import Enum
from dataclasses import dataclass, asdict

from app.agents.base import BaseAgent
from app.utils.logging import get_logger


class HealthStatus(Enum):
    """Agent health status enumeration."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"
    RECOVERING = "recovering"


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class HealthMetrics:
    """Health metrics for an agent."""

    agent_id: str
    status: HealthStatus
    last_heartbeat: datetime
    response_time_ms: float
    tasks_completed: int
    tasks_failed: int
    error_rate: float
    cpu_usage: float
    memory_usage: float
    uptime_seconds: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["status"] = self.status.value
        data["last_heartbeat"] = self.last_heartbeat.isoformat()
        return data


@dataclass
class HealthAlert:
    """Health alert for monitoring issues."""

    id: str
    agent_id: str
    severity: AlertSeverity
    title: str
    description: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["severity"] = self.severity.value
        data["created_at"] = self.created_at.isoformat()
        if self.resolved_at:
            data["resolved_at"] = self.resolved_at.isoformat()
        return data


class AgentHealthMonitor:
    """
    Monitors health and performance of individual agents.
    Tracks metrics, detects issues, and triggers alerts.
    """

    def __init__(self, agent_id: str):
        """Initialize agent health monitor."""
        self.agent_id = agent_id
        self.logger = get_logger(f"health_monitor.{agent_id}")

        # Metrics storage
        self.current_metrics: Optional[HealthMetrics] = None
        self.metrics_history: List[HealthMetrics] = []
        self.active_alerts: List[HealthAlert] = []

        # Monitoring configuration
        self.config = {
            "heartbeat_interval": 30,  # seconds
            "response_time_threshold": 5000,  # milliseconds
            "error_rate_threshold": 0.1,  # 10%
            "cpu_threshold": 80.0,  # percentage
            "memory_threshold": 85.0,  # percentage
            "offline_threshold": 180,  # seconds without heartbeat
            "metrics_history_limit": 100,
        }

        # State
        self.start_time = datetime.utcnow()
        self.last_task_count = 0
        self.last_error_count = 0

        self.logger.info(f"Health monitor initialized for agent {agent_id}")

    async def update_metrics(
        self,
        response_time_ms: float,
        tasks_completed: int,
        tasks_failed: int,
        cpu_usage: float = 0.0,
        memory_usage: float = 0.0,
    ):
        """Update agent health metrics."""
        try:
            now = datetime.utcnow()
            uptime = int((now - self.start_time).total_seconds())

            # Calculate error rate
            total_tasks = tasks_completed + tasks_failed
            error_rate = (tasks_failed / total_tasks) if total_tasks > 0 else 0.0

            # Create current metrics
            self.current_metrics = HealthMetrics(
                agent_id=self.agent_id,
                status=self._determine_health_status(
                    response_time_ms, error_rate, cpu_usage, memory_usage
                ),
                last_heartbeat=now,
                response_time_ms=response_time_ms,
                tasks_completed=tasks_completed,
                tasks_failed=tasks_failed,
                error_rate=error_rate,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                uptime_seconds=uptime,
            )

            # Store in history
            self.metrics_history.append(self.current_metrics)

            # Trim history
            if len(self.metrics_history) > self.config["metrics_history_limit"]:
                self.metrics_history = self.metrics_history[
                    -self.config["metrics_history_limit"] :
                ]

            # Check for alerts
            await self._check_health_alerts()

        except Exception as e:
            self.logger.error(f"Failed to update metrics: {e}")

    def _determine_health_status(
        self,
        response_time_ms: float,
        error_rate: float,
        cpu_usage: float,
        memory_usage: float,
    ) -> HealthStatus:
        """Determine health status based on metrics."""
        # Check for critical conditions
        if (
            response_time_ms > self.config["response_time_threshold"] * 2
            or error_rate > self.config["error_rate_threshold"] * 3
            or cpu_usage > 95.0
            or memory_usage > 95.0
        ):
            return HealthStatus.CRITICAL

        # Check for warning conditions
        if (
            response_time_ms > self.config["response_time_threshold"]
            or error_rate > self.config["error_rate_threshold"]
            or cpu_usage > self.config["cpu_threshold"]
            or memory_usage > self.config["memory_threshold"]
        ):
            return HealthStatus.WARNING

        # Check if offline
        if self.current_metrics:
            time_since_heartbeat = (
                datetime.utcnow() - self.current_metrics.last_heartbeat
            ).total_seconds()
            if time_since_heartbeat > self.config["offline_threshold"]:
                return HealthStatus.OFFLINE

        return HealthStatus.HEALTHY

    async def _check_health_alerts(self):
        """Check current metrics and generate alerts if needed."""
        if not self.current_metrics:
            return

        metrics = self.current_metrics

        # Response time alert
        if metrics.response_time_ms > self.config["response_time_threshold"]:
            await self._create_alert(
                AlertSeverity.WARNING
                if metrics.response_time_ms < self.config["response_time_threshold"] * 2
                else AlertSeverity.CRITICAL,
                "High Response Time",
                f"Response time {metrics.response_time_ms:.2f}ms exceeds threshold {self.config['response_time_threshold']}ms",
                {"response_time": metrics.response_time_ms},
            )

        # Error rate alert
        if metrics.error_rate > self.config["error_rate_threshold"]:
            await self._create_alert(
                AlertSeverity.WARNING
                if metrics.error_rate < self.config["error_rate_threshold"] * 2
                else AlertSeverity.CRITICAL,
                "High Error Rate",
                f"Error rate {metrics.error_rate:.2%} exceeds threshold {self.config['error_rate_threshold']:.2%}",
                {"error_rate": metrics.error_rate},
            )

        # Resource usage alerts
        if metrics.cpu_usage > self.config["cpu_threshold"]:
            await self._create_alert(
                AlertSeverity.WARNING
                if metrics.cpu_usage < 95.0
                else AlertSeverity.CRITICAL,
                "High CPU Usage",
                f"CPU usage {metrics.cpu_usage:.1f}% exceeds threshold {self.config['cpu_threshold']:.1f}%",
                {"cpu_usage": metrics.cpu_usage},
            )

        if metrics.memory_usage > self.config["memory_threshold"]:
            await self._create_alert(
                AlertSeverity.WARNING
                if metrics.memory_usage < 95.0
                else AlertSeverity.CRITICAL,
                "High Memory Usage",
                f"Memory usage {metrics.memory_usage:.1f}% exceeds threshold {self.config['memory_threshold']:.1f}%",
                {"memory_usage": metrics.memory_usage},
            )

    async def _create_alert(
        self,
        severity: AlertSeverity,
        title: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Create health alert if not already active."""
        # Check if similar alert already exists
        existing_alert = next(
            (
                alert
                for alert in self.active_alerts
                if alert.title == title and alert.resolved_at is None
            ),
            None,
        )

        if existing_alert:
            return  # Don't create duplicate alerts

        alert = HealthAlert(
            id=str(uuid4()),
            agent_id=self.agent_id,
            severity=severity,
            title=title,
            description=description,
            created_at=datetime.utcnow(),
            metadata=metadata or {},
        )

        self.active_alerts.append(alert)
        self.logger.warning(f"Health alert created: {title} - {description}")

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert."""
        for alert in self.active_alerts:
            if alert.id == alert_id and alert.resolved_at is None:
                alert.resolved_at = datetime.utcnow()
                self.logger.info(f"Health alert resolved: {alert.title}")
                return True

        return False

    def get_current_metrics(self) -> Optional[HealthMetrics]:
        """Get current health metrics."""
        return self.current_metrics

    def get_metrics_history(self, limit: Optional[int] = None) -> List[HealthMetrics]:
        """Get metrics history."""
        history = self.metrics_history
        if limit:
            history = history[-limit:]
        return history

    def get_active_alerts(self) -> List[HealthAlert]:
        """Get active alerts."""
        return [alert for alert in self.active_alerts if alert.resolved_at is None]

    def get_all_alerts(self) -> List[HealthAlert]:
        """Get all alerts (active and resolved)."""
        return self.active_alerts


class SystemHealthMonitor:
    """
    Central system health monitor that manages all agent monitors.
    Provides system-wide health overview and coordination.
    """

    def __init__(self):
        """Initialize system health monitor."""
        self.logger = get_logger("system_health_monitor")

        # Agent monitors
        self.agent_monitors: Dict[str, AgentHealthMonitor] = {}

        # System-level metrics
        self.system_start_time = datetime.utcnow()
        self.system_alerts: List[HealthAlert] = []

        # Monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # Configuration
        self.config = {
            "monitoring_interval": 30,  # seconds
            "system_health_check_interval": 60,  # seconds
            "alert_retention_hours": 24,
            "auto_recovery_enabled": True,
        }

        self.logger.info("System health monitor initialized")

    async def start_monitoring(self):
        """Start health monitoring."""
        if self._monitoring_task and not self._monitoring_task.done():
            self.logger.warning("Monitoring already running")
            return

        self.logger.info("Starting health monitoring")
        self._shutdown_event.clear()
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self):
        """Stop health monitoring."""
        self.logger.info("Stopping health monitoring")
        self._shutdown_event.set()

        if self._monitoring_task:
            try:
                await asyncio.wait_for(self._monitoring_task, timeout=10.0)
            except asyncio.TimeoutError:
                self.logger.warning("Monitoring task did not stop gracefully")
                self._monitoring_task.cancel()

    async def register_agent(self, agent: BaseAgent) -> bool:
        """Register agent for health monitoring."""
        try:
            agent_id = agent.agent_id

            if agent_id in self.agent_monitors:
                self.logger.warning(f"Agent {agent_id} already registered")
                return False

            # Create health monitor for agent
            monitor = AgentHealthMonitor(agent_id)
            self.agent_monitors[agent_id] = monitor

            self.logger.info(f"Registered agent {agent_id} for health monitoring")
            return True

        except Exception as e:
            self.logger.error(f"Failed to register agent: {e}")
            return False

    async def unregister_agent(self, agent_id: str) -> bool:
        """Unregister agent from health monitoring."""
        if agent_id in self.agent_monitors:
            del self.agent_monitors[agent_id]
            self.logger.info(f"Unregistered agent {agent_id} from health monitoring")
            return True

        return False

    async def update_agent_metrics(
        self,
        agent_id: str,
        response_time_ms: float,
        tasks_completed: int,
        tasks_failed: int,
        cpu_usage: float = 0.0,
        memory_usage: float = 0.0,
    ) -> bool:
        """Update metrics for specific agent."""
        if agent_id not in self.agent_monitors:
            self.logger.warning(f"Agent {agent_id} not registered for monitoring")
            return False

        try:
            monitor = self.agent_monitors[agent_id]
            await monitor.update_metrics(
                response_time_ms, tasks_completed, tasks_failed, cpu_usage, memory_usage
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to update metrics for {agent_id}: {e}")
            return False

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Perform system health check
                    await self._perform_system_health_check()

                    # Clean up old alerts
                    await self._cleanup_old_alerts()

                    # Check for recovery opportunities
                    if self.config["auto_recovery_enabled"]:
                        await self._attempt_auto_recovery()

                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")

                # Wait for next cycle
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.config["monitoring_interval"],
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    continue  # Continue monitoring

        except Exception as e:
            self.logger.error(f"Monitoring loop failed: {e}")

    async def _perform_system_health_check(self):
        """Perform system-wide health check."""
        try:
            total_agents = len(self.agent_monitors)
            healthy_agents = 0
            warning_agents = 0
            critical_agents = 0
            offline_agents = 0

            for monitor in self.agent_monitors.values():
                metrics = monitor.get_current_metrics()
                if not metrics:
                    offline_agents += 1
                    continue

                if metrics.status == HealthStatus.HEALTHY:
                    healthy_agents += 1
                elif metrics.status == HealthStatus.WARNING:
                    warning_agents += 1
                elif metrics.status == HealthStatus.CRITICAL:
                    critical_agents += 1
                elif metrics.status == HealthStatus.OFFLINE:
                    offline_agents += 1

            # Create system alerts if needed
            if critical_agents > 0:
                await self._create_system_alert(
                    AlertSeverity.CRITICAL,
                    "Critical Agents Detected",
                    f"{critical_agents} agents in critical state",
                    {"critical_count": critical_agents, "total_agents": total_agents},
                )

            if offline_agents > total_agents * 0.5:  # More than 50% offline
                await self._create_system_alert(
                    AlertSeverity.EMERGENCY,
                    "System Degradation",
                    f"{offline_agents} agents offline out of {total_agents}",
                    {"offline_count": offline_agents, "total_agents": total_agents},
                )

            # Log system status
            if total_agents > 0:
                self.logger.debug(
                    f"System Status: {healthy_agents}H {warning_agents}W "
                    f"{critical_agents}C {offline_agents}O / {total_agents} total"
                )

        except Exception as e:
            self.logger.error(f"System health check failed: {e}")

    async def _create_system_alert(
        self,
        severity: AlertSeverity,
        title: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Create system-level alert."""
        # Check for duplicate alerts
        existing = next(
            (
                alert
                for alert in self.system_alerts
                if alert.title == title and alert.resolved_at is None
            ),
            None,
        )

        if existing:
            return

        alert = HealthAlert(
            id=str(uuid4()),
            agent_id="system",
            severity=severity,
            title=title,
            description=description,
            created_at=datetime.utcnow(),
            metadata=metadata or {},
        )

        self.system_alerts.append(alert)
        self.logger.warning(f"System alert: {title} - {description}")

    async def _cleanup_old_alerts(self):
        """Clean up old resolved alerts."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(
                hours=self.config["alert_retention_hours"]
            )

            # Clean up agent alerts
            for monitor in self.agent_monitors.values():
                monitor.active_alerts = [
                    alert
                    for alert in monitor.active_alerts
                    if alert.resolved_at is None or alert.resolved_at > cutoff_time
                ]

            # Clean up system alerts
            self.system_alerts = [
                alert
                for alert in self.system_alerts
                if alert.resolved_at is None or alert.resolved_at > cutoff_time
            ]

        except Exception as e:
            self.logger.error(f"Alert cleanup failed: {e}")

    async def _attempt_auto_recovery(self):
        """Attempt automatic recovery for agents in poor health."""
        try:
            for agent_id, monitor in self.agent_monitors.items():
                metrics = monitor.get_current_metrics()
                if not metrics:
                    continue

                # Skip if agent is already recovering
                if metrics.status == HealthStatus.RECOVERING:
                    continue

                # Attempt recovery for critical agents
                if metrics.status == HealthStatus.CRITICAL:
                    await self._attempt_agent_recovery(agent_id, monitor)

        except Exception as e:
            self.logger.error(f"Auto recovery failed: {e}")

    async def _attempt_agent_recovery(self, agent_id: str, monitor: AgentHealthMonitor):
        """Attempt recovery for specific agent."""
        try:
            self.logger.info(f"Attempting auto-recovery for agent {agent_id}")

            # This would implement actual recovery mechanisms
            # For now, just log the attempt

            # Mark as recovering (would be set by actual recovery process)
            # monitor.current_metrics.status = HealthStatus.RECOVERING

        except Exception as e:
            self.logger.error(f"Recovery attempt failed for {agent_id}: {e}")

    def get_system_overview(self) -> Dict[str, Any]:
        """Get system health overview."""
        overview = {
            "system_uptime_seconds": int(
                (datetime.utcnow() - self.system_start_time).total_seconds()
            ),
            "total_agents": len(self.agent_monitors),
            "agents_by_status": {
                "healthy": 0,
                "warning": 0,
                "critical": 0,
                "offline": 0,
                "recovering": 0,
            },
            "active_system_alerts": len(
                [a for a in self.system_alerts if a.resolved_at is None]
            ),
            "total_active_alerts": 0,
        }

        # Count agents by status
        for monitor in self.agent_monitors.values():
            metrics = monitor.get_current_metrics()
            if metrics:
                status_key = metrics.status.value
                overview["agents_by_status"][status_key] += 1

                # Count active alerts
                overview["total_active_alerts"] += len(monitor.get_active_alerts())
            else:
                overview["agents_by_status"]["offline"] += 1

        return overview

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status for specific agent."""
        if agent_id not in self.agent_monitors:
            return None

        monitor = self.agent_monitors[agent_id]
        metrics = monitor.get_current_metrics()

        return {
            "agent_id": agent_id,
            "current_metrics": metrics.to_dict() if metrics else None,
            "active_alerts": [alert.to_dict() for alert in monitor.get_active_alerts()],
            "total_alerts": len(monitor.get_all_alerts()),
        }

    def get_all_agents_status(self) -> List[Dict[str, Any]]:
        """Get status for all agents."""
        return [
            self.get_agent_status(agent_id) for agent_id in self.agent_monitors.keys()
        ]

    def get_system_alerts(self, active_only: bool = True) -> List[HealthAlert]:
        """Get system-level alerts."""
        if active_only:
            return [alert for alert in self.system_alerts if alert.resolved_at is None]
        return self.system_alerts


# Global system health monitor instance
_system_health_monitor: Optional[SystemHealthMonitor] = None


async def get_system_health_monitor() -> SystemHealthMonitor:
    """Get global system health monitor instance."""
    global _system_health_monitor

    if _system_health_monitor is None:
        _system_health_monitor = SystemHealthMonitor()
        await _system_health_monitor.start_monitoring()

    return _system_health_monitor


async def initialize_health_monitoring() -> SystemHealthMonitor:
    """Initialize health monitoring system."""
    monitor = await get_system_health_monitor()
    return monitor
