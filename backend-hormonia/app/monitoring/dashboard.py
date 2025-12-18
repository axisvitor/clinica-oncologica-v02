"""
Real-time Dashboard System.

WebSocket-based live dashboard with metrics streaming and alerts.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect


logger = logging.getLogger(__name__)


@dataclass
class DashboardMetrics:
    """Dashboard metrics snapshot."""

    timestamp: datetime
    apm_stats: Dict[str, Any]
    database_stats: Dict[str, Any]
    resource_stats: Dict[str, Any]
    business_stats: Dict[str, Any]
    alerts: List[Dict[str, Any]]
    system_health: Dict[str, Any]


class ConnectionManager:
    """Manages WebSocket connections for real-time dashboard."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = metadata or {}
        logger.info(f"Dashboard client {client_id} connected")

    def disconnect(self, client_id: str) -> None:
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            del self.connection_metadata[client_id]
            logger.info(f"Dashboard client {client_id} disconnected")

    async def send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send message to a specific client."""
        if client_id not in self.active_connections:
            return False

        try:
            websocket = self.active_connections[client_id]
            await websocket.send_text(json.dumps(message, default=str))
            return True
        except Exception as e:
            logger.error(f"Failed to send message to client {client_id}: {e}")
            self.disconnect(client_id)
            return False

    async def broadcast(
        self, message: Dict[str, Any], filter_metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Broadcast message to all or filtered connections."""
        sent_count = 0

        # Create list of clients to avoid dictionary size change during iteration
        clients_to_send = []

        for client_id, metadata in self.connection_metadata.items():
            if filter_metadata:
                # Check if client metadata matches filter
                if not all(metadata.get(k) == v for k, v in filter_metadata.items()):
                    continue
            clients_to_send.append(client_id)

        # Send to filtered clients
        for client_id in clients_to_send:
            if await self.send_to_client(client_id, message):
                sent_count += 1

        return sent_count

    def get_connected_clients(self) -> List[Dict[str, Any]]:
        """Get list of connected clients with metadata."""
        return [
            {
                "client_id": client_id,
                "metadata": metadata,
                "connected_at": metadata.get("connected_at", "unknown"),
            }
            for client_id, metadata in self.connection_metadata.items()
        ]


class RealTimeDashboard:
    """Real-time dashboard with WebSocket streaming."""

    def __init__(
        self,
        apm_collector,
        db_monitor,
        resource_monitor,
        business_metrics,
        redis_client: Optional[redis.Redis] = None,
    ):
        self.apm_collector = apm_collector
        self.db_monitor = db_monitor
        self.resource_monitor = resource_monitor
        self.business_metrics = business_metrics
        self.redis_client = redis_client

        self.connection_manager = ConnectionManager()
        self.streaming_active = False
        self.stream_task: Optional[asyncio.Task] = None
        self.update_interval = 5.0  # 5 seconds

        # Alert thresholds
        self.alert_thresholds = {
            "response_time_p95": 2000,  # 2 seconds
            "error_rate": 5.0,  # 5%
            "cpu_usage": 80.0,  # 80%
            "memory_usage": 85.0,  # 85%
            "db_slow_queries": 10.0,  # 10%
            "message_delivery_failure": 10.0,  # 10%
        }

    async def start_streaming(self) -> None:
        """Start real-time metrics streaming."""
        if self.streaming_active:
            return

        self.streaming_active = True
        self.stream_task = asyncio.create_task(self._streaming_loop())
        logger.info("Real-time dashboard streaming started")

    async def stop_streaming(self) -> None:
        """Stop metrics streaming."""
        self.streaming_active = False

        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass
            self.stream_task = None

        logger.info("Real-time dashboard streaming stopped")

    async def _streaming_loop(self) -> None:
        """Main streaming loop."""
        while self.streaming_active:
            try:
                # Collect current metrics
                metrics = await self._collect_dashboard_metrics()

                # Check for alerts
                alerts = await self._check_alerts(metrics)

                # Prepare dashboard update
                dashboard_update = {
                    "type": "metrics_update",
                    "timestamp": metrics.timestamp.isoformat(),
                    "data": {
                        "apm": metrics.apm_stats,
                        "database": metrics.database_stats,
                        "resources": metrics.resource_stats,
                        "business": metrics.business_stats,
                        "system_health": metrics.system_health,
                    },
                }

                # Send alerts separately
                if alerts:
                    alert_update = {
                        "type": "alerts",
                        "timestamp": metrics.timestamp.isoformat(),
                        "alerts": alerts,
                    }
                    await self.connection_manager.broadcast(alert_update)

                # Broadcast metrics update
                sent_count = await self.connection_manager.broadcast(dashboard_update)

                if sent_count > 0:
                    logger.debug(f"Sent dashboard update to {sent_count} clients")

                await asyncio.sleep(self.update_interval)

            except Exception as e:
                logger.error(f"Error in dashboard streaming loop: {e}")
                await asyncio.sleep(self.update_interval)

    async def _collect_dashboard_metrics(self) -> DashboardMetrics:
        """Collect all dashboard metrics."""
        timestamp = datetime.utcnow()

        # APM metrics
        apm_stats = self.apm_collector.get_global_stats()

        # Database metrics
        db_stats = self.db_monitor.get_query_stats()
        db_pool_stats = self.db_monitor.get_connection_pool_stats()
        db_stats.update({"connection_pool": db_pool_stats})

        # Resource metrics
        resource_stats = self.resource_monitor.get_current_stats()

        # Business metrics
        business_stats = self.business_metrics.get_all_metrics_summary(
            time_range_hours=1
        )

        # System health
        system_health = await self._calculate_system_health(
            apm_stats, db_stats, resource_stats, business_stats
        )

        return DashboardMetrics(
            timestamp=timestamp,
            apm_stats=apm_stats,
            database_stats=db_stats,
            resource_stats=resource_stats,
            business_stats=business_stats,
            alerts=[],
            system_health=system_health,
        )

    async def _calculate_system_health(
        self,
        apm_stats: Dict[str, Any],
        db_stats: Dict[str, Any],
        resource_stats: Dict[str, Any],
        business_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate overall system health score."""
        health_score = 100
        issues = []

        # APM health checks
        if apm_stats.get("error_rate", 0) > self.alert_thresholds["error_rate"]:
            health_score -= 15
            issues.append(f"High error rate: {apm_stats['error_rate']:.1f}%")

        if apm_stats.get("p95", 0) > self.alert_thresholds["response_time_p95"]:
            health_score -= 10
            issues.append(f"High response time P95: {apm_stats['p95']:.0f}ms")

        # Database health checks
        if (
            db_stats.get("slow_query_percentage", 0)
            > self.alert_thresholds["db_slow_queries"]
        ):
            health_score -= 15
            issues.append(
                f"High slow query rate: {db_stats['slow_query_percentage']:.1f}%"
            )

        if not db_stats.get("connection_pool", {}).get("is_healthy", True):
            health_score -= 20
            issues.append("Database connection pool unhealthy")

        # Resource health checks
        cpu_percent = resource_stats.get("cpu", {}).get("percent", 0)
        if cpu_percent > self.alert_thresholds["cpu_usage"]:
            health_score -= 15
            issues.append(f"High CPU usage: {cpu_percent:.1f}%")

        memory_percent = resource_stats.get("memory", {}).get("percent", 0)
        if memory_percent > self.alert_thresholds["memory_usage"]:
            health_score -= 15
            issues.append(f"High memory usage: {memory_percent:.1f}%")

        # Business metrics health checks
        message_metrics = business_stats.get("metrics", {}).get("message_delivery", {})
        if (
            message_metrics.get("failure_rate", 0)
            > self.alert_thresholds["message_delivery_failure"]
        ):
            health_score -= 10
            issues.append(
                f"High message delivery failure rate: {message_metrics['failure_rate']:.1f}%"
            )

        # Determine status
        if health_score >= 90:
            status = "excellent"
            status_color = "green"
        elif health_score >= 75:
            status = "good"
            status_color = "yellow"
        elif health_score >= 60:
            status = "degraded"
            status_color = "orange"
        else:
            status = "critical"
            status_color = "red"

        return {
            "score": max(0, health_score),
            "status": status,
            "status_color": status_color,
            "issues": issues,
            "components": {
                "api": "healthy" if apm_stats.get("error_rate", 0) < 5 else "degraded",
                "database": "healthy"
                if db_stats.get("connection_pool", {}).get("is_healthy", True)
                else "degraded",
                "resources": "healthy"
                if cpu_percent < 80 and memory_percent < 85
                else "degraded",
                "business": "healthy"
                if message_metrics.get("failure_rate", 0) < 10
                else "degraded",
            },
        }

    async def _check_alerts(self, metrics: DashboardMetrics) -> List[Dict[str, Any]]:
        """Check for alert conditions."""
        alerts = []

        # Response time alert
        if metrics.apm_stats.get("p95", 0) > self.alert_thresholds["response_time_p95"]:
            alerts.append(
                {
                    "type": "performance",
                    "severity": "warning",
                    "title": "High Response Time",
                    "message": f"95th percentile response time is {metrics.apm_stats['p95']:.0f}ms",
                    "timestamp": metrics.timestamp.isoformat(),
                    "value": metrics.apm_stats["p95"],
                    "threshold": self.alert_thresholds["response_time_p95"],
                }
            )

        # Error rate alert
        if metrics.apm_stats.get("error_rate", 0) > self.alert_thresholds["error_rate"]:
            alerts.append(
                {
                    "type": "reliability",
                    "severity": "critical"
                    if metrics.apm_stats["error_rate"] > 10
                    else "warning",
                    "title": "High Error Rate",
                    "message": f"Error rate is {metrics.apm_stats['error_rate']:.1f}%",
                    "timestamp": metrics.timestamp.isoformat(),
                    "value": metrics.apm_stats["error_rate"],
                    "threshold": self.alert_thresholds["error_rate"],
                }
            )

        # Resource alerts
        cpu_percent = metrics.resource_stats.get("cpu", {}).get("percent", 0)
        if cpu_percent > self.alert_thresholds["cpu_usage"]:
            alerts.append(
                {
                    "type": "resource",
                    "severity": "critical" if cpu_percent > 95 else "warning",
                    "title": "High CPU Usage",
                    "message": f"CPU usage is {cpu_percent:.1f}%",
                    "timestamp": metrics.timestamp.isoformat(),
                    "value": cpu_percent,
                    "threshold": self.alert_thresholds["cpu_usage"],
                }
            )

        memory_percent = metrics.resource_stats.get("memory", {}).get("percent", 0)
        if memory_percent > self.alert_thresholds["memory_usage"]:
            alerts.append(
                {
                    "type": "resource",
                    "severity": "critical" if memory_percent > 95 else "warning",
                    "title": "High Memory Usage",
                    "message": f"Memory usage is {memory_percent:.1f}%",
                    "timestamp": metrics.timestamp.isoformat(),
                    "value": memory_percent,
                    "threshold": self.alert_thresholds["memory_usage"],
                }
            )

        # Database alerts
        slow_query_pct = metrics.database_stats.get("slow_query_percentage", 0)
        if slow_query_pct > self.alert_thresholds["db_slow_queries"]:
            alerts.append(
                {
                    "type": "database",
                    "severity": "warning",
                    "title": "High Slow Query Rate",
                    "message": f"Slow query rate is {slow_query_pct:.1f}%",
                    "timestamp": metrics.timestamp.isoformat(),
                    "value": slow_query_pct,
                    "threshold": self.alert_thresholds["db_slow_queries"],
                }
            )

        return alerts

    async def handle_websocket_connection(
        self, websocket: WebSocket, client_id: str
    ) -> None:
        """Handle a new WebSocket connection."""
        try:
            # Connect client
            await self.connection_manager.connect(
                websocket, client_id, {"connected_at": datetime.utcnow().isoformat()}
            )

            # Send initial dashboard state
            initial_metrics = await self._collect_dashboard_metrics()
            initial_message = {
                "type": "initial_state",
                "timestamp": initial_metrics.timestamp.isoformat(),
                "data": {
                    "apm": initial_metrics.apm_stats,
                    "database": initial_metrics.database_stats,
                    "resources": initial_metrics.resource_stats,
                    "business": initial_metrics.business_stats,
                    "system_health": initial_metrics.system_health,
                },
            }

            await self.connection_manager.send_to_client(client_id, initial_message)

            # Keep connection alive and handle incoming messages
            while True:
                try:
                    # Wait for client messages
                    message = await websocket.receive_text()
                    await self._handle_client_message(client_id, json.loads(message))
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error handling client message: {e}")
                    break

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
        finally:
            self.connection_manager.disconnect(client_id)

    async def _handle_client_message(
        self, client_id: str, message: Dict[str, Any]
    ) -> None:
        """Handle incoming client message."""
        message_type = message.get("type")

        if message_type == "ping":
            # Respond to ping with pong
            await self.connection_manager.send_to_client(
                client_id, {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
            )

        elif message_type == "request_metrics":
            # Send current metrics
            metrics = await self._collect_dashboard_metrics()
            response = {
                "type": "metrics_response",
                "timestamp": metrics.timestamp.isoformat(),
                "data": {
                    "apm": metrics.apm_stats,
                    "database": metrics.database_stats,
                    "resources": metrics.resource_stats,
                    "business": metrics.business_stats,
                    "system_health": metrics.system_health,
                },
            }
            await self.connection_manager.send_to_client(client_id, response)

        elif message_type == "subscribe_alerts":
            # Update client metadata to indicate alert subscription
            if client_id in self.connection_manager.connection_metadata:
                self.connection_manager.connection_metadata[client_id][
                    "subscribe_alerts"
                ] = True

        else:
            logger.warning(
                f"Unknown message type from client {client_id}: {message_type}"
            )

    def get_dashboard_status(self) -> Dict[str, Any]:
        """Get dashboard status information."""
        return {
            "streaming_active": self.streaming_active,
            "connected_clients": len(self.connection_manager.active_connections),
            "update_interval_seconds": self.update_interval,
            "clients": self.connection_manager.get_connected_clients(),
        }
