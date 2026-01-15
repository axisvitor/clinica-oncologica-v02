"""
SwarmManager - Central coordination system for Hive-Mind agents.

Handles agent lifecycle, task distribution, message routing, and health monitoring
across the distributed agent network.
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from collections import defaultdict
from dataclasses import dataclass, asdict
from enum import Enum

from sqlalchemy.orm import Session

from app.config import settings
from app.utils.logging import get_logger
from app.agents.base import BaseAgent, AgentMessage, AgentStatus, MessagePriority
from app.monitoring.agent_health_monitor import (
    SystemHealthMonitor,
    get_system_health_monitor,
)


class SwarmStatus(Enum):
    """Overall swarm operational status."""

    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    SHUTDOWN = "shutdown"


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SwarmTask:
    """Task assigned to swarm for execution."""

    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: MessagePriority
    required_capabilities: List[str]
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = None
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass
class AgentHealth:
    """Agent health and performance metrics."""

    agent_id: str
    status: AgentStatus
    last_heartbeat: datetime
    response_time: float
    success_rate: float
    active_tasks: int
    error_count: int
    uptime: timedelta

    def is_healthy(
        self, max_response_time: float = 5.0, min_success_rate: float = 0.8
    ) -> bool:
        """Check if agent is healthy based on metrics."""
        time_since_heartbeat = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()

        return (
            self.status == AgentStatus.ACTIVE
            and time_since_heartbeat < 60  # Heartbeat within last minute
            and self.response_time < max_response_time
            and self.success_rate >= min_success_rate
        )


class SwarmManager:
    """
    Central coordinator for the Hive-Mind agent swarm.

    Responsibilities:
    - Agent registration and lifecycle management
    - Task assignment and load balancing
    - Inter-agent message routing
    - Health monitoring and recovery
    - Performance metrics collection
    - Integration with Claude-Flow hooks
    """

    def __init__(self):
        """Initialize SwarmManager."""
        self.logger = get_logger("swarm_manager")

        # Swarm state
        self.status = SwarmStatus.INITIALIZING
        self.swarm_id = str(uuid4())
        self.created_at = datetime.now(timezone.utc)

        # Health monitoring
        self.health_monitor: Optional[SystemHealthMonitor] = None

        # Agent management
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_health: Dict[str, AgentHealth] = {}
        self.agent_capabilities: Dict[str, List[str]] = {}

        # Task management
        self.tasks: Dict[str, SwarmTask] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.completed_tasks: List[str] = []

        # Communication
        self.message_bus: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

        # Configuration
        self.max_agents = settings.get("SWARM_MAX_AGENTS", 50)
        self.task_timeout = settings.get("SWARM_TASK_TIMEOUT", 300)  # 5 minutes
        self.health_check_interval = settings.get(
            "SWARM_HEALTH_CHECK_INTERVAL", 30
        )  # 30 seconds

        # Background tasks
        self.background_tasks: List[asyncio.Task] = []

        # Hooks and callbacks
        self.event_callbacks: Dict[str, List[Callable]] = defaultdict(list)

        self.logger.info(f"SwarmManager initialized with ID: {self.swarm_id}")

    async def start(self):
        """Start the swarm manager and background processes."""
        try:
            self.logger.info("Starting SwarmManager")

            # Initialize health monitoring
            self.health_monitor = await get_system_health_monitor()

            # Start background tasks with proper error handling
            self.background_tasks = [
                self._create_background_task(self._task_processor(), "task_processor"),
                self._create_background_task(self._health_monitor(), "health_monitor"),
                self._create_background_task(self._message_router(), "message_router"),
                self._create_background_task(
                    self._metrics_collector(), "metrics_collector"
                ),
            ]

            self.status = SwarmStatus.ACTIVE
            await self._emit_event("swarm_started", {"swarm_id": self.swarm_id})

            self.logger.info("SwarmManager started successfully")

        except Exception as e:
            self.status = SwarmStatus.CRITICAL
            self.logger.error(f"Failed to start SwarmManager: {e}")
            raise

    async def stop(self):
        """Gracefully stop the swarm manager."""
        try:
            self.logger.info("Stopping SwarmManager")
            self.status = SwarmStatus.SHUTDOWN

            # Stop all agents
            for agent in self.agents.values():
                try:
                    await agent.stop()
                except Exception as e:
                    self.logger.error(f"Error stopping agent {agent.agent_id}: {e}")

            # Cancel background tasks
            for task in self.background_tasks:
                task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

            await self._emit_event("swarm_stopped", {"swarm_id": self.swarm_id})
            self.logger.info("SwarmManager stopped successfully")

        except Exception as e:
            self.logger.error(f"Error stopping SwarmManager: {e}")

    # Agent Management
    async def register_agent(self, agent: BaseAgent) -> bool:
        """
        Register agent with the swarm.

        Args:
            agent: Agent instance to register

        Returns:
            True if registration successful
        """
        try:
            if len(self.agents) >= self.max_agents:
                self.logger.warning(
                    f"Cannot register agent {agent.agent_id}: swarm at capacity"
                )
                return False

            # Start the agent
            await agent.start()

            # Register agent
            self.agents[agent.agent_id] = agent
            self.agent_capabilities[agent.agent_id] = await agent.get_capabilities()

            # Initialize health tracking
            self.agent_health[agent.agent_id] = AgentHealth(
                agent_id=agent.agent_id,
                status=agent.status,
                last_heartbeat=datetime.now(timezone.utc),
                response_time=0.0,
                success_rate=1.0,
                active_tasks=0,
                error_count=0,
                uptime=timedelta(),
            )

            # Register with system health monitor
            if self.health_monitor:
                await self.health_monitor.register_agent(agent)

            await self._emit_event(
                "agent_registered",
                {
                    "agent_id": agent.agent_id,
                    "agent_type": agent.agent_type,
                    "specialization": agent.specialization,
                    "capabilities": self.agent_capabilities[agent.agent_id],
                },
            )

            self.logger.info(
                f"Registered agent {agent.agent_id} ({agent.specialization})"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to register agent {agent.agent_id}: {e}")
            return False

    async def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister agent from the swarm.

        Args:
            agent_id: ID of agent to unregister

        Returns:
            True if unregistration successful
        """
        try:
            if agent_id not in self.agents:
                return False

            agent = self.agents[agent_id]

            # Stop the agent
            await agent.stop()

            # Clean up
            del self.agents[agent_id]
            del self.agent_capabilities[agent_id]
            del self.agent_health[agent_id]

            # Reassign any active tasks
            await self._reassign_agent_tasks(agent_id)

            await self._emit_event("agent_unregistered", {"agent_id": agent_id})
            self.logger.info(f"Unregistered agent {agent_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to unregister agent {agent_id}: {e}")
            return False

    async def agent_heartbeat(self, agent_id: str):
        """Record heartbeat from agent."""
        if agent_id in self.agent_health:
            self.agent_health[agent_id].last_heartbeat = datetime.now(timezone.utc)

    # Task Management
    async def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        required_capabilities: List[str],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """
        Submit task to the swarm for execution.

        Args:
            task_type: Type of task
            payload: Task data
            required_capabilities: Required agent capabilities
            priority: Task priority

        Returns:
            Task ID
        """
        task_id = str(uuid4())

        task = SwarmTask(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            required_capabilities=required_capabilities,
        )

        self.tasks[task_id] = task
        await self.task_queue.put(task)

        await self._emit_event(
            "task_submitted",
            {"task_id": task_id, "task_type": task_type, "priority": priority.value},
        )

        self.logger.info(f"Submitted task {task_id} ({task_type})")
        return task_id

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific task."""
        task = self.tasks.get(task_id)
        if not task:
            return None

        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "assigned_agent": task.assigned_agent,
            "created_at": task.created_at.isoformat(),
            "assigned_at": task.assigned_at.isoformat() if task.assigned_at else None,
            "completed_at": task.completed_at.isoformat()
            if task.completed_at
            else None,
            "result": task.result,
            "error": task.error,
        }

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel pending or in-progress task."""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ]:
            return False

        task.status = TaskStatus.CANCELLED

        # If assigned, notify agent
        if task.assigned_agent:
            await self.send_message_to_agent(
                task.assigned_agent, "task_cancelled", {"task_id": task_id}
            )

        await self._emit_event("task_cancelled", {"task_id": task_id})
        self.logger.info(f"Cancelled task {task_id}")
        return True

    # Message Routing
    async def route_message(self, message: AgentMessage):
        """Route message between agents."""
        target_queue = self.message_bus[message.to_agent]
        await target_queue.put(message)

        # Handle task completion messages
        if message.message_type in ["task_completed", "task_failed"]:
            task_id = message.payload.get("task_id")
            if task_id:
                result = message.payload.get("result")
                error = message.payload.get("error")
                await self.complete_task(task_id, result, error)

    async def send_message_to_agent(
        self,
        agent_id: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ):
        """Send message to specific agent."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        message = AgentMessage(
            id=str(uuid4()),
            from_agent="swarm_manager",
            to_agent=agent_id,
            message_type=message_type,
            payload=payload,
            priority=priority,
            timestamp=datetime.now(timezone.utc),
        )

        await self.route_message(message)

    async def broadcast_message(
        self,
        message_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        filter_capabilities: Optional[List[str]] = None,
    ):
        """Broadcast message to all agents or filtered subset."""
        target_agents = self.agents.keys()

        if filter_capabilities:
            # Filter agents by capabilities
            target_agents = [
                agent_id
                for agent_id in target_agents
                if any(
                    cap in self.agent_capabilities.get(agent_id, [])
                    for cap in filter_capabilities
                )
            ]

        for agent_id in target_agents:
            await self.send_message_to_agent(agent_id, message_type, payload, priority)

    # Background Processes
    async def _task_processor(self):
        """Background task to process and assign tasks."""
        while self.status != SwarmStatus.SHUTDOWN:
            try:
                # Get next task
                try:
                    task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Find suitable agent
                suitable_agent = await self._find_suitable_agent(task)

                if suitable_agent:
                    await self._assign_task_to_agent(task, suitable_agent)
                else:
                    # No suitable agent, requeue with lower priority
                    self.logger.warning(
                        f"No suitable agent for task {task.task_id}, requeueing"
                    )
                    await asyncio.sleep(5)  # Wait before requeuing
                    await self.task_queue.put(task)

            except Exception as e:
                self.logger.error(f"Task processor error: {e}")

    async def _find_suitable_agent(self, task: SwarmTask) -> Optional[str]:
        """Find agent suitable for executing the task."""
        suitable_agents = []

        for agent_id, agent in self.agents.items():
            # Check capabilities
            agent_caps = self.agent_capabilities.get(agent_id, [])
            if not all(cap in agent_caps for cap in task.required_capabilities):
                continue

            # Check health
            health = self.agent_health.get(agent_id)
            if not health or not health.is_healthy():
                continue

            # Check capacity
            if health.active_tasks >= agent.max_concurrent_tasks:
                continue

            suitable_agents.append((agent_id, health))

        if not suitable_agents:
            return None

        # Select best agent based on load and performance
        best_agent = min(
            suitable_agents,
            key=lambda x: (
                x[1].active_tasks,  # Prefer less loaded
                -x[1].success_rate,  # Prefer higher success rate
                x[1].response_time,  # Prefer faster response
            ),
        )

        return best_agent[0]

    async def _assign_task_to_agent(self, task: SwarmTask, agent_id: str):
        """Assign task to specific agent."""
        try:
            # Update task status
            task.status = TaskStatus.ASSIGNED
            task.assigned_agent = agent_id
            task.assigned_at = datetime.now(timezone.utc)

            # Send task to agent
            await self.send_message_to_agent(
                agent_id,
                "task_assignment",
                {
                    "task_id": task.task_id,
                    "task_data": {
                        "type": task.task_type,
                        "payload": task.payload,
                        "priority": task.priority.value,
                    },
                },
            )

            # Update agent health
            if agent_id in self.agent_health:
                self.agent_health[agent_id].active_tasks += 1

            # Set up task completion callback
            task.status = TaskStatus.IN_PROGRESS

            await self._emit_event(
                "task_assigned", {"task_id": task.task_id, "agent_id": agent_id}
            )

            self.logger.info(f"Assigned task {task.task_id} to agent {agent_id}")

        except Exception as e:
            # Reset task status on failure
            task.status = TaskStatus.PENDING
            task.assigned_agent = None
            task.assigned_at = None

            self.logger.error(
                f"Failed to assign task {task.task_id} to agent {agent_id}: {e}"
            )

            # Requeue task
            await self.task_queue.put(task)

    async def _health_monitor(self):
        """Background task to monitor agent health."""
        while self.status != SwarmStatus.SHUTDOWN:
            try:
                unhealthy_agents = []

                for agent_id, health in self.agent_health.items():
                    if not health.is_healthy():
                        unhealthy_agents.append(agent_id)

                # Handle unhealthy agents
                for agent_id in unhealthy_agents:
                    await self._handle_unhealthy_agent(agent_id)

                # Update swarm status
                self._update_swarm_status()

                await asyncio.sleep(self.health_check_interval)

            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")

    async def _handle_unhealthy_agent(self, agent_id: str):
        """Handle unhealthy agent."""
        self.logger.warning(f"Agent {agent_id} is unhealthy")

        # Try to recover agent
        if agent_id in self.agents:
            try:
                # Send ping to check if agent is responsive
                await self.send_message_to_agent(agent_id, "ping", {})

                # Give agent time to respond
                await asyncio.sleep(5)

                # If still unhealthy, unregister
                health = self.agent_health.get(agent_id)
                if health and not health.is_healthy():
                    self.logger.error(
                        f"Agent {agent_id} failed recovery, unregistering"
                    )
                    await self.unregister_agent(agent_id)

            except Exception as e:
                self.logger.error(f"Failed to recover agent {agent_id}: {e}")
                await self.unregister_agent(agent_id)

    async def _message_router(self):
        """Background task to route messages to agents."""
        while self.status != SwarmStatus.SHUTDOWN:
            try:
                # Process messages for each agent
                for agent_id in list(self.agents.keys()):
                    queue = self.message_bus[agent_id]

                    # Process pending messages
                    messages_processed = 0
                    while (
                        not queue.empty() and messages_processed < 10
                    ):  # Limit per iteration
                        try:
                            message = queue.get_nowait()
                            agent = self.agents.get(agent_id)

                            if agent:
                                await agent.receive_message(message)
                                messages_processed += 1
                            else:
                                # Agent no longer exists
                                break

                        except asyncio.QueueEmpty:
                            break
                        except Exception as e:
                            self.logger.error(
                                f"Message routing error for agent {agent_id}: {e}"
                            )

                await asyncio.sleep(0.1)  # Short delay between iterations

            except Exception as e:
                self.logger.error(f"Message router error: {e}")

    def _create_background_task(self, coro, name: str) -> asyncio.Task:
        """Create background task with proper error handling."""

        async def safe_wrapper():
            try:
                result = await coro
                # Notify task completion for health tracking
                if name in self.agent_health:
                    agent_health = self.agent_health.get(name)
                    if agent_health and agent_health.active_tasks > 0:
                        agent_health.active_tasks -= 1
                return result
            except asyncio.CancelledError:
                self.logger.info(f"Background task {name} cancelled")
                raise
            except Exception as e:
                self.logger.error(f"Background task {name} failed: {e}", exc_info=True)
                # Attempt recovery based on task type
                if self.status != SwarmStatus.SHUTDOWN:
                    await asyncio.sleep(5)  # Wait before potential restart
                raise

        task = asyncio.create_task(safe_wrapper(), name=name)
        return task

    async def _metrics_collector(self):
        """Background task to collect metrics."""
        while self.status != SwarmStatus.SHUTDOWN:
            try:
                # Collect metrics from agents
                for agent_id, agent in self.agents.items():
                    try:
                        # Request metrics from agent
                        await self.send_message_to_agent(
                            agent_id, "metrics_request", {}
                        )

                        # Update health monitor with metrics
                        if self.health_monitor and agent_id in self.agent_health:
                            health = self.agent_health[agent_id]
                            await self.health_monitor.update_agent_metrics(
                                agent_id=agent_id,
                                response_time_ms=health.response_time
                                * 1000,  # Convert to ms
                                tasks_completed=health.active_tasks,
                                tasks_failed=health.error_count,
                                cpu_usage=0.0,  # Would be collected from agent
                                memory_usage=0.0,  # Would be collected from agent
                            )

                    except Exception as e:
                        self.logger.error(
                            f"Failed to collect metrics from agent {agent_id}: {e}"
                        )

                await asyncio.sleep(60)  # Collect metrics every minute

            except Exception as e:
                self.logger.error(f"Metrics collector error: {e}")

    # Utility Methods
    def _update_swarm_status(self):
        """Update overall swarm status based on agent health."""
        if not self.agents:
            self.status = SwarmStatus.CRITICAL
            return

        healthy_agents = sum(
            1 for health in self.agent_health.values() if health.is_healthy()
        )

        total_agents = len(self.agents)
        health_ratio = healthy_agents / total_agents if total_agents > 0 else 0

        if health_ratio >= 0.9:
            self.status = SwarmStatus.ACTIVE
        elif health_ratio >= 0.6:
            self.status = SwarmStatus.DEGRADED
        else:
            self.status = SwarmStatus.CRITICAL

    async def _reassign_agent_tasks(self, agent_id: str):
        """Reassign tasks from unregistered agent."""
        tasks_to_reassign = [
            task
            for task in self.tasks.values()
            if task.assigned_agent == agent_id and task.status == TaskStatus.IN_PROGRESS
        ]

        for task in tasks_to_reassign:
            task.status = TaskStatus.PENDING
            task.assigned_agent = None
            task.assigned_at = None
            await self.task_queue.put(task)

            self.logger.info(
                f"Reassigned task {task.task_id} from failed agent {agent_id}"
            )

    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit event to registered callbacks."""
        callbacks = self.event_callbacks.get(event_type, [])

        for callback in callbacks:
            try:
                await callback(event_type, data)
            except Exception as e:
                self.logger.error(f"Event callback error for {event_type}: {e}")

    # Public API
    def register_event_callback(self, event_type: str, callback: Callable):
        """Register callback for specific event type."""
        self.event_callbacks[event_type].append(callback)

    def get_swarm_status(self) -> Dict[str, Any]:
        """Get comprehensive swarm status."""
        return {
            "swarm_id": self.swarm_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "total_agents": len(self.agents),
            "healthy_agents": sum(
                1 for h in self.agent_health.values() if h.is_healthy()
            ),
            "active_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.IN_PROGRESS]
            ),
            "pending_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]
            ),
            "completed_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]
            ),
            "agents": {
                agent_id: agent.get_agent_info()
                for agent_id, agent in self.agents.items()
            },
        }

    def get_agent_list(self) -> List[Dict[str, Any]]:
        """Get list of all registered agents."""
        return [
            {
                "agent_id": agent_id,
                "agent_type": agent.agent_type,
                "specialization": agent.specialization,
                "status": agent.status.value,
                "capabilities": self.agent_capabilities.get(agent_id, []),
                "health": asdict(self.agent_health[agent_id])
                if agent_id in self.agent_health
                else None,
            }
            for agent_id, agent in self.agents.items()
        ]

    async def complete_task(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Mark task as completed and update agent health."""
        task = self.tasks.get(task_id)
        if not task:
            return False

        # Update task status
        if error:
            task.status = TaskStatus.FAILED
            task.error = error
        else:
            task.status = TaskStatus.COMPLETED
            task.result = result

        task.completed_at = datetime.now(timezone.utc)

        # Decrement agent active tasks
        if task.assigned_agent and task.assigned_agent in self.agent_health:
            health = self.agent_health[task.assigned_agent]
            if health.active_tasks > 0:
                health.active_tasks -= 1

            # Update success rate
            if error:
                health.error_count += 1
            else:
                # Calculate new success rate (simplified)
                total_tasks = health.active_tasks + 1  # The just completed task
                successful_tasks = total_tasks - health.error_count
                health.success_rate = (
                    successful_tasks / total_tasks if total_tasks > 0 else 1.0
                )

        # Emit completion event
        event_type = "task_failed" if error else "task_completed"
        await self._emit_event(
            event_type,
            {
                "task_id": task_id,
                "agent_id": task.assigned_agent,
                "result": result,
                "error": error,
            },
        )

        self.logger.info(
            f"Task {task_id} {'failed' if error else 'completed'} by agent {task.assigned_agent}"
        )
        return True


# Global swarm manager instance
_swarm_manager: Optional[SwarmManager] = None


async def get_swarm_manager() -> SwarmManager:
    """Get global swarm manager instance."""
    global _swarm_manager

    if _swarm_manager is None:
        _swarm_manager = SwarmManager()
        await _swarm_manager.start()

    return _swarm_manager


async def initialize_swarm_manager(db_session: Session | None = None) -> SwarmManager:
    """Initialize swarm manager with optional database session (unused)."""
    global _swarm_manager

    if _swarm_manager is None:
        _swarm_manager = SwarmManager()
        await _swarm_manager.start()

    return _swarm_manager
