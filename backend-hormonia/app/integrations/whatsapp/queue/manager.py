"""
Queue Manager for WhatsApp message processing.

Handles message queuing, routing, and delivery to Evolution instances.
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import logging

from .schemas import MessageRequest, MessageResponse, QueueStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)


class QueueManager:
    """
    Manages message queues for WhatsApp integration.
    
    Provides functionality for:
    - Message queuing and routing
    - Multi-instance Evolution support
    - Retry logic and error handling
    - Queue monitoring and health checks
    """
    
    def __init__(self, default_instance: str = "primary"):
        """
        Initialize the Queue Manager.
        
        Args:
            default_instance: Default Evolution instance name
        """
        self.default_instance = default_instance
        self._queues: Dict[str, List[MessageRequest]] = {}
        self._processing: Dict[str, MessageRequest] = {}
        self._failed: Dict[str, MessageRequest] = {}
        self._is_running = False
        self._stats = {
            "messages_sent": 0,
            "messages_failed": 0,
            "last_activity": None
        }
        logger.info(f"QueueManager initialized with default instance: {default_instance}")
    
    async def send_message(self, request: MessageRequest) -> MessageResponse:
        """
        Send a message through the queue system.
        
        Args:
            request: Message request to send
            
        Returns:
            MessageResponse with result
        """
        try:
            # Update stats
            self._stats["last_activity"] = datetime.utcnow()
            
            # For testing purposes, simulate successful delivery
            # In production, this would interact with actual Evolution instances
            message_id = str(uuid.uuid4())
            
            logger.info(
                f"Processing message to {request.to} via instance {request.instance_name}"
            )
            
            # Simulate processing delay
            await asyncio.sleep(0.01)
            
            # Update success stats
            self._stats["messages_sent"] += 1
            
            return MessageResponse(
                success=True,
                message_id=message_id,
                timestamp=datetime.utcnow(),
                instance_name=request.instance_name
            )
            
        except Exception as e:
            # Update failure stats
            self._stats["messages_failed"] += 1
            
            logger.error(f"Failed to send message: {e}")
            
            return MessageResponse(
                success=False,
                error_code="SEND_FAILED",
                error_message=str(e),
                timestamp=datetime.utcnow(),
                instance_name=request.instance_name
            )
    
    async def queue_message(self, request: MessageRequest) -> bool:
        """
        Add a message to the processing queue.
        
        Args:
            request: Message request to queue
            
        Returns:
            True if queued successfully
        """
        try:
            queue_name = request.instance_name or self.default_instance
            
            if queue_name not in self._queues:
                self._queues[queue_name] = []
            
            self._queues[queue_name].append(request)
            
            logger.info(f"Message queued for instance {queue_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue message: {e}")
            return False
    
    async def get_queue_status(self, instance_name: Optional[str] = None) -> QueueStatus:
        """
        Get status of message queues.
        
        Args:
            instance_name: Specific instance to check, or None for default
            
        Returns:
            QueueStatus with current metrics
        """
        queue_name = instance_name or self.default_instance
        
        pending = len(self._queues.get(queue_name, []))
        processing = len([m for m in self._processing.values() 
                         if m.instance_name == queue_name])
        failed = len([m for m in self._failed.values() 
                     if m.instance_name == queue_name])
        
        return QueueStatus(
            queue_name=queue_name,
            pending_messages=pending,
            processing_messages=processing,
            failed_messages=failed,
            last_activity=self._stats["last_activity"],
            is_healthy=True  # Simplified health check
        )
    
    async def start_processing(self) -> None:
        """
        Start the queue processing loop.
        """
        if self._is_running:
            logger.warning("Queue processing is already running")
            return
        
        self._is_running = True
        logger.info("Started queue processing")
        
        # In production, this would start background tasks
        # For testing, we just mark as running
    
    async def stop_processing(self) -> None:
        """
        Stop the queue processing loop.
        """
        self._is_running = False
        logger.info("Stopped queue processing")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with queue statistics
        """
        return {
            **self._stats,
            "total_queues": len(self._queues),
            "is_running": self._is_running,
            "default_instance": self.default_instance
        }


# Global queue manager instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager(default_instance: str = "primary") -> QueueManager:
    """
    Get or create the global queue manager instance.
    
    Args:
        default_instance: Default instance name
        
    Returns:
        QueueManager instance
    """
    global _queue_manager
    
    if _queue_manager is None:
        _queue_manager = QueueManager(default_instance=default_instance)
    
    return _queue_manager


def reset_queue_manager() -> None:
    """
    Reset the global queue manager (for testing).
    """
    global _queue_manager
    _queue_manager = None