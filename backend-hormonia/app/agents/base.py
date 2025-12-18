"""
Base Agent class for Hive-Mind system.

Provides core functionality for all agents including communication,
memory access, consensus participation, and Claude-Flow integration.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from uuid import uuid4
from dataclasses import dataclass, asdict
from enum import Enum

from sqlalchemy.orm import Session

from app.utils.logging import get_logger


class AgentStatus(Enum):
    """Agent operational status."""

    INITIALIZING = "initializing"
    ACTIVE = "active"
    BUSY = "busy"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class AgentCapabilities:
    """Agent capabilities definition."""

    can_process_messages: bool = True
    can_generate_content: bool = False
    can_make_decisions: bool = False
    can_learn: bool = False
    can_coordinate: bool = False
    max_concurrent_tasks: int = 1
    supported_message_types: List[str] = None
    required_permissions: List[str] = None

    # Define capability constants for agents
    MESSAGE_COMPOSITION = "message_composition"
    PERSONALIZATION = "personalization"
    EMOTIONAL_INTELLIGENCE = "emotional_intelligence"
    PATIENT_ADAPTATION = "patient_adaptation"
    RESPONSE_INTERPRETATION = "response_interpretation"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    MEDICAL_NLP = "medical_nlp"
    FLOW_COORDINATION = "flow_coordination"
    DECISION_MAKING = "decision_making"
    LEARNING = "learning"

    def __post_init__(self):
        if self.supported_message_types is None:
            self.supported_message_types = []
        if self.required_permissions is None:
            self.required_permissions = []


class MessagePriority(Enum):
    """Inter-agent message priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentMessage:
    """Inter-agent communication message."""

    id: str
    from_agent: str
    to_agent: str
    message_type: str
    payload: Dict[str, Any]
    priority: MessagePriority
    timestamp: datetime
    requires_response: bool = False
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            **asdict(self),
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AgentMetrics:
    """Agent performance metrics."""

    tasks_completed: int = 0
    tasks_failed: int = 0
    average_response_time: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    uptime: timedelta = timedelta()
    last_activity: Optional[datetime] = None

    def success_rate(self) -> float:
        """Calculate task success rate."""
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 0.0


class BaseAgent(ABC):
    """
    Base class for all Hive-Mind agents.

    Provides core functionality including:
    - Inter-agent communication
    - Memory system integration
    - Performance metrics
    - Claude-Flow hooks
    - Consensus participation
    - Error handling and recovery
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        specialization: str,
        db_session: Session,
        **kwargs,
    ):
        """
        Initialize base agent.

        Args:
            agent_id: Unique identifier for this agent
            agent_type: Type category (patient, communication, analytics)
            specialization: Specific role within type
            db_session: Database session for persistence
            **kwargs: Additional configuration
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.specialization = specialization
        self.db_session = db_session

        # Agent state
        self.status = AgentStatus.INITIALIZING
        self.created_at = datetime.utcnow()
        self.last_heartbeat = datetime.utcnow()

        # Configuration
        self.config = kwargs
        self.max_concurrent_tasks = kwargs.get("max_concurrent_tasks", 5)
        self.heartbeat_interval = kwargs.get("heartbeat_interval", 30)

        # Communication
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.message_handlers: Dict[str, Callable] = {}

        # Metrics
        self.metrics = AgentMetrics()
        self.start_time = datetime.utcnow()

        # Memory and coordination
        self.memory_store = {}
        self.consensus_votes = {}
        self.peer_agents = {}

        # Logging
        self.logger = get_logger(f"agent.{agent_type}.{specialization}")

        # Claude-Flow integration
        self.hooks_enabled = True
        self.session_id = str(uuid4())

        # Register message handlers
        self._register_default_handlers()

        self.logger.info(
            f"Agent {self.agent_id} initialized with specialization: {specialization}"
        )

    # Abstract methods that must be implemented by subclasses
    @abstractmethod
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a specific task assigned to this agent."""
        pass

    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this agent provides."""
        pass

    @abstractmethod
    async def validate_task(self, task_data: Dict[str, Any]) -> bool:
        """Validate if this agent can handle the given task."""
        pass

    # Core agent lifecycle methods
    async def start(self):
        """Start the agent and begin processing."""
        try:
            self.logger.info(f"Starting agent {self.agent_id}")

            # Run Claude-Flow pre-task hook
            await self._run_pre_task_hook("agent_start", {})

            # Initialize agent-specific resources
            await self._initialize()

            # Start background tasks
            await self._start_background_tasks()

            self.status = AgentStatus.ACTIVE
            self.logger.info(f"Agent {self.agent_id} started successfully")

        except Exception as e:
            self.status = AgentStatus.ERROR
            self.logger.error(f"Failed to start agent {self.agent_id}: {e}")
            raise

    async def stop(self):
        """Gracefully stop the agent."""
        try:
            self.logger.info(f"Stopping agent {self.agent_id}")
            self.status = AgentStatus.SHUTDOWN

            # Cancel active tasks
            for task_id, task in self.active_tasks.items():
                if not task.done():
                    task.cancel()
                    self.logger.debug(f"Cancelled task {task_id}")

            # Wait for tasks to complete
            if self.active_tasks:
                await asyncio.gather(
                    *self.active_tasks.values(), return_exceptions=True
                )

            # Run cleanup
            await self._cleanup()

            # Run Claude-Flow post-task hook
            await self._run_post_task_hook("agent_stop", {})

            self.logger.info(f"Agent {self.agent_id} stopped successfully")

        except Exception as e:
            self.logger.error(f"Error stopping agent {self.agent_id}: {e}")

    async def _initialize(self):
        """Initialize agent-specific resources. Override in subclasses."""
        pass

    async def _cleanup(self):
        """Cleanup agent-specific resources. Override in subclasses."""
        pass

    # Message handling system
    async def send_message(
        self,
        to_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        requires_response: bool = False,
    ) -> str:
        """
        Send message to another agent.

        Args:
            to_agent: Target agent ID
            message_type: Type of message
            payload: Message data
            priority: Message priority
            requires_response: Whether response is expected

        Returns:
            Message correlation ID
        """
        message_id = str(uuid4())
        correlation_id = str(uuid4()) if requires_response else None

        message = AgentMessage(
            id=message_id,
            from_agent=self.agent_id,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            priority=priority,
            timestamp=datetime.utcnow(),
            requires_response=requires_response,
            correlation_id=correlation_id,
        )

        # Route message through swarm manager
        from app.orchestration.swarm_manager import get_swarm_manager

        swarm_manager = await get_swarm_manager()
        await swarm_manager.route_message(message)

        self.logger.debug(f"Sent message {message_id} to {to_agent}")
        return correlation_id if requires_response else message_id

    async def receive_message(self, message: AgentMessage):
        """Receive and process message from another agent."""
        try:
            # Add to message queue
            await self.message_queue.put(message)
            self.logger.debug(
                f"Received message {message.id} from {message.from_agent}"
            )

        except Exception as e:
            self.logger.error(f"Error receiving message: {e}")

    async def _process_messages(self):
        """Background task to process incoming messages."""
        while self.status != AgentStatus.SHUTDOWN:
            try:
                # Get message with timeout
                try:
                    message = await asyncio.wait_for(
                        self.message_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Handle message
                await self._handle_message(message)

            except Exception as e:
                self.logger.error(f"Error processing messages: {e}")

    async def _handle_message(self, message: AgentMessage):
        """Handle individual message based on type."""
        handler = self.message_handlers.get(message.message_type)

        if not handler:
            self.logger.warning(f"No handler for message type: {message.message_type}")
            return

        try:
            # Process message
            response = await handler(message.payload)

            # Send response if required
            if message.requires_response:
                await self.send_message(
                    to_agent=message.from_agent,
                    message_type=f"{message.message_type}_response",
                    payload=response,
                    priority=message.priority,
                )

        except Exception as e:
            self.logger.error(f"Error handling message {message.id}: {e}")

            # Send error response if required
            if message.requires_response:
                await self.send_message(
                    to_agent=message.from_agent,
                    message_type=f"{message.message_type}_error",
                    payload={"error": str(e)},
                    priority=MessagePriority.HIGH,
                )

    def register_message_handler(self, message_type: str, handler: Callable):
        """Register handler for specific message type."""
        self.message_handlers[message_type] = handler
        self.logger.debug(f"Registered handler for {message_type}")

    def _register_default_handlers(self):
        """Register default message handlers."""
        self.register_message_handler("ping", self._handle_ping)
        self.register_message_handler("status_request", self._handle_status_request)
        self.register_message_handler("metrics_request", self._handle_metrics_request)
        self.register_message_handler("task_assignment", self._handle_task_assignment)

    # Default message handlers
    async def _handle_ping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping message."""
        self.last_heartbeat = datetime.utcnow()
        return {"pong": True, "timestamp": self.last_heartbeat.isoformat()}

    async def _handle_status_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle status request."""
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "uptime": (datetime.utcnow() - self.start_time).total_seconds(),
            "active_tasks": len(self.active_tasks),
            "capabilities": await self.get_capabilities(),
        }

    async def _handle_metrics_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle metrics request."""
        self.metrics.uptime = datetime.utcnow() - self.start_time
        self.metrics.last_activity = self.last_heartbeat
        return asdict(self.metrics)

    async def _handle_task_assignment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle task assignment from swarm manager."""
        task_id = payload.get("task_id", str(uuid4()))
        task_data = payload.get("task_data", {})

        # Validate task
        if not await self.validate_task(task_data):
            return {"accepted": False, "reason": "Task validation failed"}

        # Check capacity
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            return {"accepted": False, "reason": "At capacity"}

        # Accept and schedule task
        task = asyncio.create_task(self._execute_task(task_id, task_data))
        self.active_tasks[task_id] = task

        return {"accepted": True, "task_id": task_id}

    # Task execution
    async def _execute_task(self, task_id: str, task_data: Dict[str, Any]):
        """Execute assigned task with error handling and metrics."""
        start_time = datetime.utcnow()

        try:
            self.logger.info(f"Executing task {task_id}")

            # Run Claude-Flow pre-task hook
            await self._run_pre_task_hook(
                "task_execution", {"task_id": task_id, "task_data": task_data}
            )

            # Process task
            result = await self.process_task(task_data)

            # Update metrics
            self.metrics.tasks_completed += 1
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_average_response_time(execution_time)

            # Run Claude-Flow post-task hook
            await self._run_post_task_hook(
                "task_execution",
                {
                    "task_id": task_id,
                    "result": result,
                    "execution_time": execution_time,
                },
            )

            self.logger.info(f"Task {task_id} completed successfully")
            return result

        except Exception as e:
            # Update metrics
            self.metrics.tasks_failed += 1

            self.logger.error(f"Task {task_id} failed: {e}")
            raise

        finally:
            # Cleanup
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]

    # Background tasks
    async def _start_background_tasks(self):
        """Start background tasks for agent operation."""
        # Message processing task
        message_task = asyncio.create_task(self._process_messages())
        self.active_tasks["_message_processor"] = message_task

        # Heartbeat task
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.active_tasks["_heartbeat"] = heartbeat_task

    async def _heartbeat_loop(self):
        """Send periodic heartbeat to swarm manager."""
        while self.status != AgentStatus.SHUTDOWN:
            try:
                # Send heartbeat
                from app.orchestration.swarm_manager import get_swarm_manager

                swarm_manager = await get_swarm_manager()
                await swarm_manager.agent_heartbeat(self.agent_id)

                self.last_heartbeat = datetime.utcnow()

                # Wait for next heartbeat
                await asyncio.sleep(self.heartbeat_interval)

            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)  # Shorter retry interval

    # Claude-Flow integration
    async def _run_pre_task_hook(self, event_type: str, context: Dict[str, Any]):
        """Run Claude-Flow pre-task hook."""
        if not self.hooks_enabled:
            return

        try:
            # Would integrate with Claude-Flow MCP here
            self.logger.debug(f"Pre-task hook: {event_type}")
            # await claude_flow.hooks.pre_task(event_type, context)

        except Exception as e:
            self.logger.warning(f"Pre-task hook failed: {e}")

    async def _run_post_task_hook(self, event_type: str, context: Dict[str, Any]):
        """Run Claude-Flow post-task hook."""
        if not self.hooks_enabled:
            return

        try:
            # Would integrate with Claude-Flow MCP here
            self.logger.debug(f"Post-task hook: {event_type}")
            # await claude_flow.hooks.post_task(event_type, context)

        except Exception as e:
            self.logger.warning(f"Post-task hook failed: {e}")

    # Utility methods
    def _update_average_response_time(self, execution_time: float):
        """Update average response time metric."""
        if self.metrics.tasks_completed == 1:
            self.metrics.average_response_time = execution_time
        else:
            # Running average
            total_tasks = self.metrics.tasks_completed
            current_total = self.metrics.average_response_time * (total_tasks - 1)
            self.metrics.average_response_time = (
                current_total + execution_time
            ) / total_tasks

    def get_agent_info(self) -> Dict[str, Any]:
        """Get comprehensive agent information."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "specialization": self.specialization,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "active_tasks": len(self.active_tasks),
            "metrics": asdict(self.metrics),
            "config": self.config,
        }
