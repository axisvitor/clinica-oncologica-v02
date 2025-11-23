"""
WebSocket heartbeat system for connection health monitoring.

This module provides a robust heartbeat system that:
- Monitors connection health with configurable intervals
- Detects dead connections automatically
- Provides connection health metrics
- Supports custom heartbeat strategies
- Handles cleanup of unresponsive connections
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Callable, Any, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

logger = logging.getLogger(__name__)


class HeartbeatStatus(Enum):
    """Heartbeat status for connections."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DEAD = "dead"


@dataclass
class HeartbeatMetrics:
    """Heartbeat metrics for a connection."""
    connection_id: str
    status: HeartbeatStatus = HeartbeatStatus.HEALTHY
    last_ping_sent: Optional[datetime] = None
    last_pong_received: Optional[datetime] = None
    ping_count: int = 0
    pong_count: int = 0
    missed_pings: int = 0
    average_latency: float = 0.0
    min_latency: float = float('inf')
    max_latency: float = 0.0
    latency_samples: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_latency_sample(self, latency: float) -> None:
        """Add a latency sample and update statistics."""
        self.latency_samples.append(latency)
        
        # Keep only last 10 samples for rolling average
        if len(self.latency_samples) > 10:
            self.latency_samples.pop(0)
        
        # Update statistics
        self.min_latency = min(self.min_latency, latency)
        self.max_latency = max(self.max_latency, latency)
        self.average_latency = sum(self.latency_samples) / len(self.latency_samples)
    
    def update_status(self, max_missed_pings: int, warning_threshold: int) -> None:
        """Update heartbeat status based on missed pings."""
        if self.missed_pings == 0:
            self.status = HeartbeatStatus.HEALTHY
        elif self.missed_pings < warning_threshold:
            self.status = HeartbeatStatus.WARNING
        elif self.missed_pings < max_missed_pings:
            self.status = HeartbeatStatus.CRITICAL
        else:
            self.status = HeartbeatStatus.DEAD


class WebSocketHeartbeatManager:
    """
    Manages heartbeat system for WebSocket connections.
    
    Features:
    - Configurable heartbeat intervals and timeouts
    - Connection health monitoring and metrics
    - Automatic cleanup of dead connections
    - Custom heartbeat strategies
    - Health status reporting
    """
    
    def __init__(
        self,
        heartbeat_interval: int = 30,      # seconds
        heartbeat_timeout: int = 10,       # seconds
        max_missed_pings: int = 3,
        warning_threshold: int = 2,
        cleanup_interval: int = 60,        # seconds
        latency_history_size: int = 10,
        send_ping_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[bool]]] = None,
        on_connection_dead: Optional[Callable[[str], None]] = None,
        on_connection_warning: Optional[Callable[[str, 'HeartbeatMetrics'], None]] = None,
        on_ping_timeout: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize heartbeat manager.
        
        Args:
            heartbeat_interval: Interval between heartbeat pings (seconds)
            heartbeat_timeout: Timeout for heartbeat responses (seconds)
            max_missed_pings: Maximum missed pings before marking as dead
            warning_threshold: Missed pings threshold for warning status
            cleanup_interval: Interval for cleanup tasks (seconds)
            latency_history_size: Number of latency samples to keep
        """
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.max_missed_pings = max_missed_pings
        self.warning_threshold = warning_threshold
        self.cleanup_interval = cleanup_interval
        self.latency_history_size = latency_history_size
        
        # Connection tracking
        self.connection_metrics: Dict[str, HeartbeatMetrics] = {}
        self.pending_pings: Dict[str, Dict[str, float]] = {}  # connection_id -> {ping_id -> timestamp}
        self.ping_counter = 0
        
        # Callbacks
        self.send_ping_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[bool]]] = send_ping_callback
        self.on_connection_dead: Optional[Callable[[str], None]] = on_connection_dead
        self.on_connection_warning: Optional[Callable[[str, HeartbeatMetrics], None]] = on_connection_warning
        self.on_ping_timeout: Optional[Callable[[str, str], None]] = on_ping_timeout
        
        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics
        self.total_pings_sent = 0
        self.total_pongs_received = 0
        self.total_timeouts = 0
        self.total_dead_connections = 0
        
        logger.info("WebSocket heartbeat manager initialized")
    
    async def start(self) -> None:
        """Start the heartbeat manager."""
        if self._running:
            return
        
        self._running = True
        
        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("WebSocket heartbeat manager started")
    
    async def stop(self) -> None:
        """Stop the heartbeat manager."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("WebSocket heartbeat manager stopped")
    
    def register_connection(self, connection_id: str) -> None:
        """
        Register a new connection for heartbeat monitoring.
        
        Args:
            connection_id: Connection to register
        """
        if connection_id not in self.connection_metrics:
            self.connection_metrics[connection_id] = HeartbeatMetrics(
                connection_id=connection_id
            )
            self.pending_pings[connection_id] = {}
            
            logger.debug(f"Registered connection for heartbeat monitoring: {connection_id}")
    
    def unregister_connection(self, connection_id: str) -> None:
        """
        Unregister a connection from heartbeat monitoring.
        
        Args:
            connection_id: Connection to unregister
        """
        if connection_id in self.connection_metrics:
            del self.connection_metrics[connection_id]
        
        if connection_id in self.pending_pings:
            del self.pending_pings[connection_id]
        
        logger.debug(f"Unregistered connection from heartbeat monitoring: {connection_id}")
    
    async def send_ping(
        self,
        connection_id: str,
        send_callback: Optional[Callable[[str, dict], Awaitable[bool]]] = None
    ) -> bool:
        """
        Send a ping to a connection.
        
        Args:
            connection_id: Connection to ping
            send_callback: Function to send the ping message
            
        Returns:
            True if ping sent successfully, False otherwise
        """
        if connection_id not in self.connection_metrics:
            return False

        callback = send_callback or self.send_ping_callback
        if not callback:
            logger.error("No send_ping_callback provided for WebSocketHeartbeatManager")
            return False
        
        metrics = self.connection_metrics[connection_id]
        ping_id = str(uuid4())
        timestamp = time.time()
        
        # Create ping message
        ping_message = {
            "type": "ping",
            "data": {
                "ping_id": ping_id,
                "timestamp": datetime.utcnow().isoformat(),
                "server_time": timestamp
            }
        }
        
        # Send ping
        success = await callback(connection_id, ping_message)
        
        if success:
            # Track ping
            self.pending_pings[connection_id][ping_id] = timestamp
            metrics.ping_count += 1
            metrics.last_ping_sent = datetime.utcnow()
            self.total_pings_sent += 1
            
            # Schedule timeout check
            asyncio.create_task(self._check_ping_timeout(connection_id, ping_id))
            
            logger.debug(f"Sent ping to connection {connection_id}: {ping_id}")
        else:
            # Ping failed to send
            metrics.missed_pings += 1
            metrics.update_status(self.max_missed_pings, self.warning_threshold)
            
            logger.warning(f"Failed to send ping to connection {connection_id}")
        
        return success
    
    def handle_pong(self, connection_id: str, ping_id: str, client_timestamp: Optional[str] = None) -> bool:
        """
        Handle a pong response from a connection.
        
        Args:
            connection_id: Connection that sent the pong
            ping_id: Ping ID being responded to
            client_timestamp: Optional client timestamp
            
        Returns:
            True if pong was valid, False otherwise
        """
        if connection_id not in self.connection_metrics:
            return False
        
        metrics = self.connection_metrics[connection_id]
        
        # Check if we have a pending ping for this ID
        if ping_id not in self.pending_pings.get(connection_id, {}):
            logger.warning(f"Received pong for unknown ping {ping_id} from {connection_id}")
            return False
        
        # Calculate latency
        ping_timestamp = self.pending_pings[connection_id][ping_id]
        latency = (time.time() - ping_timestamp) * 1000  # Convert to milliseconds
        
        # Update metrics
        metrics.pong_count += 1
        metrics.last_pong_received = datetime.utcnow()
        metrics.missed_pings = 0  # Reset missed pings counter
        metrics.add_latency_sample(latency)
        metrics.update_status(self.max_missed_pings, self.warning_threshold)
        
        # Remove pending ping
        del self.pending_pings[connection_id][ping_id]
        
        self.total_pongs_received += 1
        
        logger.debug(f"Received pong from connection {connection_id}: {ping_id} (latency: {latency:.2f}ms)")
        
        return True
    
    def get_connection_health(self, connection_id: str) -> Optional[HeartbeatMetrics]:
        """
        Get health metrics for a connection.
        
        Args:
            connection_id: Connection to get health for
            
        Returns:
            HeartbeatMetrics or None if connection not found
        """
        return self.connection_metrics.get(connection_id)
    
    def get_all_connection_health(self) -> Dict[str, HeartbeatMetrics]:
        """
        Get health metrics for all connections.
        
        Returns:
            Dictionary of connection_id -> HeartbeatMetrics
        """
        return self.connection_metrics.copy()
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get summary of connection health statistics.
        
        Returns:
            Dictionary with health summary
        """
        total_connections = len(self.connection_metrics)
        
        status_counts = {
            HeartbeatStatus.HEALTHY: 0,
            HeartbeatStatus.WARNING: 0,
            HeartbeatStatus.CRITICAL: 0,
            HeartbeatStatus.DEAD: 0
        }
        
        total_latency = 0
        latency_samples = 0
        
        for metrics in self.connection_metrics.values():
            status_counts[metrics.status] += 1
            if metrics.latency_samples:
                total_latency += metrics.average_latency
                latency_samples += 1
        
        average_latency = total_latency / latency_samples if latency_samples > 0 else 0
        
        return {
            "total_connections": total_connections,
            "healthy_connections": status_counts[HeartbeatStatus.HEALTHY],
            "warning_connections": status_counts[HeartbeatStatus.WARNING],
            "critical_connections": status_counts[HeartbeatStatus.CRITICAL],
            "dead_connections": status_counts[HeartbeatStatus.DEAD],
            "average_latency_ms": round(average_latency, 2),
            "total_pings_sent": self.total_pings_sent,
            "total_pongs_received": self.total_pongs_received,
            "total_timeouts": self.total_timeouts,
            "total_dead_connections": self.total_dead_connections,
            "ping_success_rate": (
                self.total_pongs_received / self.total_pings_sent * 100
                if self.total_pings_sent > 0 else 0
            )
        }
    
    def set_callbacks(
        self,
        send_ping_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[bool]]] = None,
        on_connection_dead: Optional[Callable[[str], None]] = None,
        on_connection_warning: Optional[Callable[[str, HeartbeatMetrics], None]] = None,
        on_ping_timeout: Optional[Callable[[str, str], None]] = None
    ) -> None:
        """
        Set callback functions for heartbeat events.
        
        Args:
            on_connection_dead: Called when a connection is marked as dead
            on_connection_warning: Called when a connection enters warning state
            on_ping_timeout: Called when a ping times out
        """
        if send_ping_callback is not None:
            self.send_ping_callback = send_ping_callback
        if on_connection_dead is not None:
            self.on_connection_dead = on_connection_dead
        if on_connection_warning is not None:
            self.on_connection_warning = on_connection_warning
        if on_ping_timeout is not None:
            self.on_ping_timeout = on_ping_timeout
    
    async def _heartbeat_loop(self) -> None:
        """Background task for sending heartbeat pings."""
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if not self._running:
                    break
                
                # Check connection health and trigger callbacks
                dead_connections = []
                
                for connection_id, metrics in self.connection_metrics.items():
                    # Check if connection should be marked as dead
                    if metrics.missed_pings >= self.max_missed_pings:
                        if metrics.status != HeartbeatStatus.DEAD:
                            metrics.status = HeartbeatStatus.DEAD
                            dead_connections.append(connection_id)
                            self.total_dead_connections += 1
                    
                    # Check for warning status
                    elif (metrics.missed_pings >= self.warning_threshold and 
                          metrics.status == HeartbeatStatus.HEALTHY):
                        metrics.status = HeartbeatStatus.WARNING
                        if self.on_connection_warning:
                            self.on_connection_warning(connection_id, metrics)
                
                # Trigger dead connection callbacks
                for connection_id in dead_connections:
                    if self.on_connection_dead:
                        self.on_connection_dead(connection_id)
                
                logger.debug(f"Heartbeat cycle completed. Monitored connections: {len(self.connection_metrics)}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Background task for periodic cleanup."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                if not self._running:
                    break
                
                await self._perform_cleanup()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _perform_cleanup(self) -> None:
        """Perform periodic cleanup tasks."""
        now = time.time()
        cleanup_threshold = now - (self.cleanup_interval * 2)  # 2x cleanup interval
        
        # Clean up old pending pings
        for connection_id, pings in self.pending_pings.items():
            expired_pings = [
                ping_id for ping_id, timestamp in pings.items()
                if timestamp < cleanup_threshold
            ]
            
            for ping_id in expired_pings:
                del pings[ping_id]
                self.total_timeouts += 1
                
                if self.on_ping_timeout:
                    self.on_ping_timeout(connection_id, ping_id)
        
        if any(self.pending_pings.values()):
            logger.debug(f"Cleaned up expired pings. Total timeouts: {self.total_timeouts}")
    
    async def _check_ping_timeout(self, connection_id: str, ping_id: str) -> None:
        """
        Check if a ping has timed out.
        
        Args:
            connection_id: Connection that was pinged
            ping_id: Ping ID to check
        """
        await asyncio.sleep(self.heartbeat_timeout)
        
        # Check if ping is still pending (not responded to)
        if (connection_id in self.pending_pings and 
            ping_id in self.pending_pings[connection_id]):
            
            # Ping timed out
            del self.pending_pings[connection_id][ping_id]
            self.total_timeouts += 1
            
            # Update connection metrics
            if connection_id in self.connection_metrics:
                metrics = self.connection_metrics[connection_id]
                metrics.missed_pings += 1
                metrics.update_status(self.max_missed_pings, self.warning_threshold)
            
            if self.on_ping_timeout:
                self.on_ping_timeout(connection_id, ping_id)
            
            logger.debug(f"Ping timeout for connection {connection_id}: {ping_id}")


# Global heartbeat manager instance
heartbeat_manager = WebSocketHeartbeatManager()


def get_heartbeat_manager() -> WebSocketHeartbeatManager:
    """Get the global heartbeat manager instance."""
    return heartbeat_manager
