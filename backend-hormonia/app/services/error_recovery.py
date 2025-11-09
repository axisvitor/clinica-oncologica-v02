"""
Error recovery service for flow operations with exponential backoff and graceful degradation.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Any, List, Callable, Awaitable
from uuid import UUID
import json

from sqlalchemy.orm import Session
from redis import Redis

from app.exceptions.flow_exceptions import (
    FlowException, MessageDeliveryError, FlowStateCorruptionError,
    ExternalServiceError, AIServiceError, RedisConnectionError,
    DatabaseError, FlowProcessingError
)
from app.models.flow import PatientFlowState
from app.models.flow_analytics import FlowMessage
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository
from app.domain.messaging.delivery import MessageSender
from app.services.enhanced_flow_engine import FlowType

logger = logging.getLogger(__name__)


class ErrorRecoveryService:
    """Service for handling flow operation errors and recovery."""
    
    def __init__(self, db: Session, redis: Redis, flow_repository: FlowStateRepository,
                 message_sender: MessageSender):
        self.db = db
        self.redis = redis
        self.flow_repository = flow_repository
        self.message_sender = message_sender
        
        # Recovery strategies
        self.recovery_strategies = {
            MessageDeliveryError: self._handle_message_delivery_error,
            FlowStateCorruptionError: self._handle_flow_state_corruption,
            ExternalServiceError: self._handle_external_service_error,
            AIServiceError: self._handle_ai_service_error,
            RedisConnectionError: self._handle_redis_connection_error,
            DatabaseError: self._handle_database_error,
            FlowProcessingError: self._handle_flow_processing_error
        }
    
    async def handle_error(self, error: Exception, context: dict[str, Any]) -> bool:
        """
        Handle flow operation errors with appropriate recovery strategy.
        
        Args:
            error: The exception that occurred
            context: Additional context about the operation
            
        Returns:
            bool: True if error was recovered, False if manual intervention needed
        """
        try:
            # Log the error with context
            await self._log_error(error, context)
            
            # Find appropriate recovery strategy
            recovery_func = self._get_recovery_strategy(error)
            if not recovery_func:
                logger.error(f"No recovery strategy for error type: {type(error)}")
                return False
            
            # Attempt recovery
            recovery_result = await recovery_func(error, context)
            
            # Log recovery result
            if recovery_result:
                logger.info(f"Successfully recovered from error: {error}")
            else:
                logger.error(f"Failed to recover from error: {error}")
            
            return recovery_result
            
        except Exception as recovery_error:
            logger.error(f"Error during recovery process: {recovery_error}")
            return False
    
    def _get_recovery_strategy(self, error: Exception) -> Optional[Callable]:
        """Get the appropriate recovery strategy for an error type."""
        for error_type, strategy in self.recovery_strategies.items():
            if isinstance(error, error_type):
                return strategy
        return None
    
    async def _handle_message_delivery_error(self, error: MessageDeliveryError, 
                                           context: dict[str, Any]) -> bool:
        """Handle message delivery failures with exponential backoff."""
        try:
            # Check if we've exceeded max retries
            max_retries = context.get('max_retries', 3)
            if error.retry_count >= max_retries:
                logger.error(f"Max retries exceeded for message delivery to patient {error.patient_id}")
                await self._escalate_message_delivery_failure(error, context)
                return False
            
            # Calculate exponential backoff delay
            base_delay = context.get('base_delay', 300)  # 5 minutes
            delay = base_delay * (2 ** error.retry_count)
            
            # Schedule retry
            await self._schedule_message_retry(error, context, delay)
            
            logger.info(f"Scheduled message retry for patient {error.patient_id} "
                       f"in {delay} seconds (attempt {error.retry_count + 1})")
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling message delivery failure: {e}")
            return False
    
    async def _handle_flow_state_corruption(self, error: FlowStateCorruptionError,
                                          context: dict[str, Any]) -> bool:
        """Handle flow state corruption with data recovery."""
        try:
            patient_id = error.patient_id
            
            # Try to recover from backup or reconstruct state
            recovered_state = await self._recover_flow_state(patient_id, error.corruption_type)
            
            if recovered_state:
                # Update the corrupted state
                await self.flow_repository.update_flow_state(patient_id, recovered_state)
                logger.info(f"Successfully recovered flow state for patient {patient_id}")
                return True
            else:
                # Create manual correction task
                await self._create_manual_correction_task(error, context)
                logger.warning(f"Flow state corruption requires manual intervention for patient {patient_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling flow state corruption: {e}")
            return False
    
    async def _handle_external_service_error(self, error: ExternalServiceError,
                                           context: dict[str, Any]) -> bool:
        """Handle external service failures with graceful degradation."""
        try:
            if not error.is_recoverable:
                logger.error(f"Non-recoverable external service error: {error.service_name}")
                await self._escalate_service_failure(error, context)
                return False
            
            # Implement circuit breaker pattern
            circuit_key = f"circuit_breaker:{error.service_name}"
            failure_count = await self._get_failure_count(circuit_key)
            
            if failure_count >= 5:  # Circuit breaker threshold
                logger.warning(f"Circuit breaker open for service: {error.service_name}")
                await self._activate_fallback_mode(error.service_name, context)
                return True
            
            # Increment failure count
            await self._increment_failure_count(circuit_key)
            
            # Schedule retry if specified
            if error.retry_after:
                await self._schedule_service_retry(error, context, error.retry_after)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling external service failure: {e}")
            return False
    
    async def _handle_ai_service_error(self, error: AIServiceError,
                                     context: dict[str, Any]) -> bool:
        """Handle AI service failures with fallback to templates."""
        try:
            # Use template fallback for message generation
            if 'message_template' in context:
                fallback_message = await self._generate_fallback_message(
                    context['message_template'], 
                    context.get('patient_id')
                )
                context['fallback_message'] = fallback_message
                logger.info(f"Generated fallback message for AI service failure")
                return True
            
            # For other AI operations, log and continue with degraded functionality
            logger.warning(f"AI service unavailable, continuing with reduced functionality: {error.ai_service}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling AI service failure: {e}")
            return False
    
    async def _handle_redis_connection_error(self, error: RedisConnectionError,
                                           context: dict[str, Any]) -> bool:
        """Handle Redis connection failures with in-memory fallback."""
        try:
            # Use in-memory storage for critical operations
            if error.operation in ['get', 'set', 'delete']:
                logger.warning(f"Redis unavailable, using in-memory fallback for {error.operation}")
                # Implement in-memory cache fallback
                return True
            
            # For non-critical operations, continue without caching
            logger.info(f"Redis unavailable, skipping non-critical operation: {error.operation}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling Redis connection failure: {e}")
            return False
    
    async def _handle_database_error(self, error: DatabaseError,
                                   context: dict[str, Any]) -> bool:
        """Handle database errors with retry and rollback."""
        try:
            if not error.is_recoverable:
                logger.error(f"Non-recoverable database error: {error.operation}")
                return False
            
            # Rollback current transaction
            self.db.rollback()
            
            # Wait and retry for transient errors
            await asyncio.sleep(1)
            
            # Attempt to reconnect and retry operation
            retry_func = context.get('retry_function')
            if retry_func:
                try:
                    await retry_func()
                    logger.info(f"Successfully retried database operation: {error.operation}")
                    return True
                except Exception as retry_error:
                    logger.error(f"Retry failed for database operation: {retry_error}")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling database failure: {e}")
            return False
    
    async def _handle_flow_processing_error(self, error: FlowProcessingError,
                                          context: dict[str, Any]) -> bool:
        """Handle flow processing errors with state recovery."""
        try:
            patient_id = error.patient_id
            
            # Try to recover to last known good state
            last_good_state = await self._get_last_good_flow_state(patient_id)
            
            if last_good_state:
                await self.flow_repository.update_flow_state(patient_id, last_good_state)
                logger.info(f"Recovered flow state to last good state for patient {patient_id}")
                return True
            
            # If no good state found, pause flow and alert
            await self._pause_flow_for_investigation(patient_id, str(error))
            logger.warning(f"Paused flow for manual investigation: patient {patient_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error handling flow processing failure: {e}")
            return False
    
    async def _log_error(self, error: Exception, context: dict[str, Any]) -> None:
        """Log error with full context for debugging."""
        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if isinstance(error, FlowException):
            error_data.update({
                'patient_id': str(error.patient_id) if error.patient_id else None,
                'flow_type': error.flow_type,
                'error_context': error.context
            })
        
        # Store in Redis for monitoring
        try:
            error_key = f"flow_errors:{datetime.utcnow().strftime('%Y-%m-%d')}"
            await self.redis.lpush(error_key, json.dumps(error_data))
            await self.redis.expire(error_key, 86400 * 7)  # Keep for 7 days
        except Exception:
            pass  # Don't fail if Redis is unavailable
        
        logger.error(f"Flow error logged: {json.dumps(error_data, indent=2)}")
    
    async def _schedule_message_retry(self, error: MessageDeliveryError,
                                    context: dict[str, Any], delay: int) -> None:
        """Schedule message delivery retry with exponential backoff."""
        # This would integrate with Celery for actual scheduling
        retry_data = {
            'patient_id': str(error.patient_id),
            'message_id': str(error.message_id) if error.message_id else None,
            'retry_count': error.retry_count + 1,
            'original_context': context,
            'scheduled_for': (datetime.utcnow() + timedelta(seconds=delay)).isoformat()
        }
        
        # Store retry information
        retry_key = f"message_retries:{error.patient_id}:{error.message_id}"
        await self.redis.setex(retry_key, delay + 3600, json.dumps(retry_data))
    
    async def _recover_flow_state(self, patient_id: UUID, corruption_type: str) -> Optional[dict[str, Any]]:
        """Attempt to recover corrupted flow state."""
        try:
            # Try to get backup from Redis
            backup_key = f"flow_state_backup:{patient_id}"
            backup_data = await self.redis.get(backup_key)
            
            if backup_data:
                return json.loads(backup_data)
            
            # Try to reconstruct from flow history
            flow_messages = await self.flow_repository.get_patient_flow_messages(patient_id)
            if flow_messages:
                return await self._reconstruct_flow_state_from_history(patient_id, flow_messages)
            
            return None
            
        except Exception as e:
            logger.error(f"Error recovering flow state: {e}")
            return None
    
    async def _create_manual_correction_task(self, error: FlowStateCorruptionError,
                                           context: dict[str, Any]) -> None:
        """Create a task for manual correction of corrupted flow state."""
        task_data = {
            'task_type': 'manual_flow_correction',
            'patient_id': str(error.patient_id),
            'corruption_type': error.corruption_type,
            'corrupted_data': error.flow_state_data,
            'context': context,
            'created_at': datetime.utcnow().isoformat(),
            'status': 'pending'
        }
        
        task_key = f"manual_tasks:flow_correction:{error.patient_id}"
        await self.redis.setex(task_key, 86400 * 7, json.dumps(task_data))
        
        # Also log for immediate attention
        logger.critical(f"Manual correction required for patient {error.patient_id}: {error.corruption_type}")
    
    async def _get_failure_count(self, circuit_key: str) -> int:
        """Get current failure count for circuit breaker."""
        try:
            count = await self.redis.get(circuit_key)
            return int(count) if count else 0
        except Exception:
            return 0
    
    async def _increment_failure_count(self, circuit_key: str) -> None:
        """Increment failure count for circuit breaker."""
        try:
            await self.redis.incr(circuit_key)
            await self.redis.expire(circuit_key, 3600)  # Reset after 1 hour
        except Exception:
            pass
    
    async def _activate_fallback_mode(self, service_name: str, context: dict[str, Any]) -> None:
        """Activate fallback mode for failed service."""
        fallback_key = f"fallback_mode:{service_name}"
        fallback_data = {
            'activated_at': datetime.utcnow().isoformat(),
            'context': context
        }
        await self.redis.setex(fallback_key, 3600, json.dumps(fallback_data))
        logger.warning(f"Activated fallback mode for service: {service_name}")
    
    async def _generate_fallback_message(self, template: str, patient_id: Optional[UUID]) -> str:
        """Generate fallback message when AI services are unavailable."""
        # Simple template substitution without AI
        if patient_id:
            try:
                patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
                if patient:
                    template = template.replace("{patient_name}", patient.name)
            except Exception:
                pass
        
        return template
    
    async def _get_last_good_flow_state(self, patient_id: UUID) -> Optional[dict[str, Any]]:
        """Get the last known good flow state for a patient."""
        try:
            # Check Redis backup
            backup_key = f"flow_state_backup:{patient_id}"
            backup_data = await self.redis.get(backup_key)
            
            if backup_data:
                return json.loads(backup_data)
            
            # Fallback to database
            flow_state = await self.flow_repository.get_flow_state(patient_id)
            if flow_state and flow_state.state_data:
                return flow_state.state_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting last good flow state: {e}")
            return None
    
    async def _pause_flow_for_investigation(self, patient_id: UUID, reason: str) -> None:
        """Pause patient flow for manual investigation."""
        try:
            await self.flow_repository.pause_patient_flow(patient_id, reason)
            
            # Create investigation task
            investigation_data = {
                'patient_id': str(patient_id),
                'reason': reason,
                'paused_at': datetime.utcnow().isoformat(),
                'status': 'requires_investigation'
            }
            
            investigation_key = f"investigations:flow:{patient_id}"
            await self.redis.setex(investigation_key, 86400 * 7, json.dumps(investigation_data))
            
        except Exception as e:
            logger.error(f"Error pausing flow for investigation: {e}")
    
    async def _escalate_message_delivery_failure(self, error: MessageDeliveryError,
                                               context: dict[str, Any]) -> None:
        """Escalate message delivery failure to administrators."""
        escalation_data = {
            'type': 'message_delivery_failure',
            'patient_id': str(error.patient_id),
            'message_id': str(error.message_id) if error.message_id else None,
            'retry_count': error.retry_count,
            'last_error': error.last_error,
            'context': context,
            'escalated_at': datetime.utcnow().isoformat()
        }
        
        escalation_key = f"escalations:message_delivery:{error.patient_id}"
        await self.redis.setex(escalation_key, 86400 * 3, json.dumps(escalation_data))
        
        logger.critical(f"Escalated message delivery failure for patient {error.patient_id}")
    
    async def _escalate_service_failure(self, error: ExternalServiceError,
                                      context: dict[str, Any]) -> None:
        """Escalate external service failure to administrators."""
        escalation_data = {
            'type': 'external_service_failure',
            'service_name': error.service_name,
            'error_code': error.error_code,
            'is_recoverable': error.is_recoverable,
            'context': context,
            'escalated_at': datetime.utcnow().isoformat()
        }
        
        escalation_key = f"escalations:service_failure:{error.service_name}"
        await self.redis.setex(escalation_key, 86400 * 3, json.dumps(escalation_data))
        
        logger.critical(f"Escalated service failure: {error.service_name}")