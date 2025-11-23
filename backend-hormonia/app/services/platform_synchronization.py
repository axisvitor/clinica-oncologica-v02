"""
Platform synchronization service for integrating flow system with core Hormonia platform.
Handles patient record updates, audit trails, and cross-platform data consistency.
"""
import logging
import asyncio
from typing import Any, List, Optional, Tuple
from datetime import datetime
from uuid import UUID
import json

# from sqlalchemy.orm import
from redis import Redis

from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.models.flow_analytics import FlowMessage
from app.models.user import User
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.services.websocket_events import WebSocketEventService
from app.schemas.websocket import WebSocketEventType

logger = logging.getLogger(__name__)


class PlatformSynchronizationService:
    """Service for synchronizing flow system data with core platform."""
    
    def __init__(self, db: Any, redis: Redis, 
                 patient_repository: PatientRepository,
                 flow_repository: FlowStateRepository,
                 websocket_service: WebSocketEventService):
        self.db = db
        self.redis = redis
        self.patient_repository = patient_repository
        self.flow_repository = flow_repository
        self.websocket_service = websocket_service
        
        # Sync configuration
        self.sync_config = {
            'batch_size': 100,
            'sync_interval_seconds': 300,  # 5 minutes
            'audit_retention_days': 365,
            'max_retry_attempts': 3,
            'sync_timeout_seconds': 30
        }
    
    async def sync_patient_record_updates(self, patient_id: UUID, 
                                        flow_interactions: List[dict[str, Any]]) -> bool:
        """Sync flow interactions to patient record."""
        try:
            # Get patient record
            patient = self.patient_repository.get_by_id(patient_id)
            if not patient:
                logger.error(f"Patient {patient_id} not found for sync")
                return False
            
            # Process flow interactions and update patient record
            updates_applied = 0
            
            for interaction in flow_interactions:
                try:
                    # Extract relevant data from interaction
                    interaction_data = await self._extract_interaction_data(interaction)
                    
                    # Update patient record based on interaction type
                    if interaction['type'] == 'flow_progression':
                        await self._update_patient_flow_status(patient, interaction_data)
                        updates_applied += 1
                    
                    elif interaction['type'] == 'message_response':
                        await self._update_patient_response_data(patient, interaction_data)
                        updates_applied += 1
                    
                    elif interaction['type'] == 'quiz_completion':
                        await self._update_patient_quiz_data(patient, interaction_data)
                        updates_applied += 1
                    
                    elif interaction['type'] == 'alert_triggered':
                        await self._update_patient_alert_status(patient, interaction_data)
                        updates_applied += 1
                    
                    # Create audit trail entry
                    await self._create_audit_trail_entry(
                        patient_id, 
                        interaction['type'], 
                        interaction_data,
                        'flow_system'
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing interaction {interaction.get('id', 'unknown')}: {e}")
            
            # Save patient updates
            if updates_applied > 0:
                self.db.commit()
                
                # Broadcast patient update event
                await self.websocket_service.broadcast_flow_event(
                    WebSocketEventType.PATIENT_UPDATED,
                    patient_id,
                    {
                        'patient_id': str(patient_id),
                        'updates_applied': updates_applied,
                        'last_sync': datetime.utcnow().isoformat()
                    }
                )
            
            logger.info(f"Synced {updates_applied} interactions for patient {patient_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing patient record updates for {patient_id}: {e}")
            self.db.rollback()
            return False
    
    async def create_audit_trail_entry(self, entity_type: str, entity_id: UUID,
                                     action: str, changes: dict[str, Any],
                                     user_id: Optional[UUID] = None,
                                     source_system: str = 'flow_system') -> bool:
        """Create audit trail entry for platform logging."""
        try:
            audit_entry = {
                'id': str(UUID()),
                'entity_type': entity_type,
                'entity_id': str(entity_id),
                'action': action,
                'changes': changes,
                'user_id': str(user_id) if user_id else None,
                'source_system': source_system,
                'timestamp': datetime.utcnow().isoformat(),
                'ip_address': None,  # Would be populated from request context
                'user_agent': None   # Would be populated from request context
            }
            
            # Store in Redis for immediate access
            audit_key = f"audit:{entity_type}:{entity_id}:{datetime.utcnow().strftime('%Y%m%d')}"
            await self.redis.lpush(audit_key, json.dumps(audit_entry))
            await self.redis.expire(audit_key, 86400 * self.sync_config['audit_retention_days'])
            
            # Store in database for permanent record
            await self._store_audit_entry_in_database(audit_entry)
            
            logger.debug(f"Created audit trail entry for {entity_type} {entity_id}: {action}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating audit trail entry: {e}")
            return False
    
    async def validate_cross_platform_consistency(self) -> dict[str, Any]:
        """Validate data consistency across platform components."""
        try:
            consistency_report = {
                'timestamp': datetime.utcnow().isoformat(),
                'checks_performed': 0,
                'inconsistencies_found': 0,
                'issues': []
            }
            
            # Check patient-flow consistency
            patient_flow_issues = await self._check_patient_flow_consistency()
            consistency_report['issues'].extend(patient_flow_issues)
            consistency_report['checks_performed'] += 1
            
            # Check message-flow consistency
            message_flow_issues = await self._check_message_flow_consistency()
            consistency_report['issues'].extend(message_flow_issues)
            consistency_report['checks_performed'] += 1
            
            # Check audit trail completeness
            audit_issues = await self._check_audit_trail_completeness()
            consistency_report['issues'].extend(audit_issues)
            consistency_report['checks_performed'] += 1
            
            # Check data synchronization lag
            sync_lag_issues = await self._check_synchronization_lag()
            consistency_report['issues'].extend(sync_lag_issues)
            consistency_report['checks_performed'] += 1
            
            consistency_report['inconsistencies_found'] = len(consistency_report['issues'])
            
            # Store report for monitoring
            await self._store_consistency_report(consistency_report)
            
            return consistency_report
            
        except Exception as e:
            logger.error(f"Error validating cross-platform consistency: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'checks_performed': 0,
                'inconsistencies_found': 0,
                'issues': []
            }
    
    async def sync_authentication_integration(self, user_id: UUID, 
                                            flow_permissions: dict[str, Any]) -> bool:
        """Sync flow system permissions with JWT authentication system."""
        try:
            # Get user from database
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User {user_id} not found for permission sync")
                return False
            
            # Update user permissions for flow system
            current_permissions = user.permissions or {}
            
            # Merge flow permissions
            flow_perms = current_permissions.get('flow_system', {})
            flow_perms.update(flow_permissions)
            current_permissions['flow_system'] = flow_perms
            
            user.permissions = current_permissions
            user.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            # Cache permissions in Redis for fast access
            permission_key = f"user_permissions:{user_id}"
            await self.redis.setex(
                permission_key, 
                3600,  # 1 hour cache
                json.dumps(current_permissions)
            )
            
            # Create audit trail
            await self.create_audit_trail_entry(
                'user',
                user_id,
                'permissions_updated',
                {
                    'flow_permissions': flow_permissions,
                    'updated_by': 'flow_system'
                },
                source_system='authentication_sync'
            )
            
            logger.info(f"Synced flow permissions for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing authentication integration for user {user_id}: {e}")
            self.db.rollback()
            return False
    
    async def run_periodic_synchronization(self) -> dict[str, Any]:
        """Run periodic synchronization tasks."""
        try:
            sync_results = {
                'started_at': datetime.utcnow().isoformat(),
                'tasks_completed': 0,
                'tasks_failed': 0,
                'results': {}
            }
            
            # Sync pending patient updates
            patient_sync_result = await self._sync_pending_patient_updates()
            sync_results['results']['patient_updates'] = patient_sync_result
            if patient_sync_result['success']:
                sync_results['tasks_completed'] += 1
            else:
                sync_results['tasks_failed'] += 1
            
            # Sync audit trail entries
            audit_sync_result = await self._sync_pending_audit_entries()
            sync_results['results']['audit_sync'] = audit_sync_result
            if audit_sync_result['success']:
                sync_results['tasks_completed'] += 1
            else:
                sync_results['tasks_failed'] += 1
            
            # Validate data consistency
            consistency_result = await self.validate_cross_platform_consistency()
            sync_results['results']['consistency_check'] = consistency_result
            sync_results['tasks_completed'] += 1
            
            # Clean up old sync data
            cleanup_result = await self._cleanup_old_sync_data()
            sync_results['results']['cleanup'] = cleanup_result
            if cleanup_result['success']:
                sync_results['tasks_completed'] += 1
            else:
                sync_results['tasks_failed'] += 1
            
            sync_results['completed_at'] = datetime.utcnow().isoformat()
            
            # Store sync results
            await self._store_sync_results(sync_results)
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Error in periodic synchronization: {e}")
            return {
                'started_at': datetime.utcnow().isoformat(),
                'error': str(e),
                'tasks_completed': 0,
                'tasks_failed': 1
            }
    
    # Private helper methods
    async def _extract_interaction_data(self, interaction: dict[str, Any]) -> dict[str, Any]:
        """Extract relevant data from flow interaction."""
        return {
            'interaction_id': interaction.get('id'),
            'timestamp': interaction.get('timestamp', datetime.utcnow().isoformat()),
            'data': interaction.get('data', {}),
            'metadata': interaction.get('metadata', {})
        }
    
    async def _update_patient_flow_status(self, patient: Patient, 
                                        interaction_data: dict[str, Any]) -> None:
        """Update patient flow status from interaction."""
        try:
            # Update patient's flow-related fields
            flow_data = interaction_data.get('data', {})
            
            if 'current_day' in flow_data:
                patient.current_flow_day = flow_data['current_day']
            
            if 'flow_type' in flow_data:
                patient.current_flow_type = flow_data['flow_type']
            
            if 'milestone_reached' in flow_data:
                milestones = patient.flow_milestones or []
                milestones.append({
                    'milestone': flow_data['milestone_reached'],
                    'reached_at': interaction_data['timestamp']
                })
                patient.flow_milestones = milestones
            
            patient.updated_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error updating patient flow status: {e}")
    
    async def _update_patient_response_data(self, patient: Patient,
                                          interaction_data: dict[str, Any]) -> None:
        """Update patient response data from interaction."""
        try:
            response_data = interaction_data.get('data', {})
            
            # Update response history
            responses = patient.response_history or []
            responses.append({
                'response': response_data.get('response'),
                'sentiment': response_data.get('sentiment'),
                'timestamp': interaction_data['timestamp']
            })
            
            # Keep only last 100 responses
            patient.response_history = responses[-100:]
            patient.updated_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error updating patient response data: {e}")
    
    async def _update_patient_quiz_data(self, patient: Patient,
                                      interaction_data: dict[str, Any]) -> None:
        """Update patient quiz data from interaction."""
        try:
            quiz_data = interaction_data.get('data', {})
            
            # Update quiz completion history
            quiz_history = patient.quiz_history or []
            quiz_history.append({
                'quiz_id': quiz_data.get('quiz_id'),
                'score': quiz_data.get('score'),
                'completed_at': interaction_data['timestamp'],
                'responses': quiz_data.get('responses', [])
            })
            
            patient.quiz_history = quiz_history
            patient.last_quiz_completed = datetime.fromisoformat(interaction_data['timestamp'])
            patient.updated_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error updating patient quiz data: {e}")
    
    async def _update_patient_alert_status(self, patient: Patient,
                                         interaction_data: dict[str, Any]) -> None:
        """Update patient alert status from interaction."""
        try:
            alert_data = interaction_data.get('data', {})
            
            # Update alert history
            alerts = patient.alert_history or []
            alerts.append({
                'alert_type': alert_data.get('alert_type'),
                'severity': alert_data.get('severity'),
                'triggered_at': interaction_data['timestamp'],
                'resolved': alert_data.get('resolved', False)
            })
            
            patient.alert_history = alerts
            patient.updated_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error updating patient alert status: {e}")
    
    async def _create_audit_trail_entry(self, patient_id: UUID, interaction_type: str,
                                      interaction_data: dict[str, Any],
                                      source_system: str) -> None:
        """Create audit trail entry for interaction."""
        await self.create_audit_trail_entry(
            'patient',
            patient_id,
            f'flow_{interaction_type}',
            interaction_data,
            source_system=source_system
        )
    
    async def _store_audit_entry_in_database(self, audit_entry: dict[str, Any]) -> None:
        """Store audit entry in database."""
        try:
            # This would integrate with your actual audit table
            # For now, store in Redis as backup
            audit_key = f"audit_db:{audit_entry['id']}"
            await self.redis.setex(audit_key, 86400 * 365, json.dumps(audit_entry))
            
        except Exception as e:
            logger.error(f"Error storing audit entry in database: {e}")
    
    async def _check_patient_flow_consistency(self) -> List[dict[str, Any]]:
        """Check consistency between patient records and flow states."""
        issues = []
        
        try:
            # Get patients with active flows
            patients_with_flows = self.db.query(Patient).join(FlowState).all()
            
            for patient in patients_with_flows:
                flow_state = self.flow_repository.get_by_patient_id(patient.id)
                
                if flow_state:
                    # Check if patient flow day matches flow state
                    if patient.current_flow_day != flow_state.current_day:
                        issues.append({
                            'type': 'patient_flow_day_mismatch',
                            'patient_id': str(patient.id),
                            'patient_day': patient.current_flow_day,
                            'flow_state_day': flow_state.current_day,
                            'severity': 'medium'
                        })
                    
                    # Check if flow type matches
                    if patient.current_flow_type != flow_state.flow_type.value:
                        issues.append({
                            'type': 'patient_flow_type_mismatch',
                            'patient_id': str(patient.id),
                            'patient_type': patient.current_flow_type,
                            'flow_state_type': flow_state.flow_type.value,
                            'severity': 'high'
                        })
            
            return issues
            
        except Exception as e:
            logger.error(f"Error checking patient-flow consistency: {e}")
            return [{'type': 'consistency_check_error', 'error': str(e), 'severity': 'critical'}]
    
    async def _check_message_flow_consistency(self) -> List[dict[str, Any]]:
        """Check consistency between messages and flow states."""
        issues = []
        
        try:
            # Check for messages without corresponding flow states
            orphaned_messages = self.db.query(FlowMessage).outerjoin(FlowState).filter(
                FlowState.id.is_(None)
            ).limit(100).all()
            
            for message in orphaned_messages:
                issues.append({
                    'type': 'orphaned_flow_message',
                    'message_id': str(message.id),
                    'patient_id': str(message.patient_id),
                    'severity': 'medium'
                })
            
            return issues
            
        except Exception as e:
            logger.error(f"Error checking message-flow consistency: {e}")
            return [{'type': 'consistency_check_error', 'error': str(e), 'severity': 'critical'}]
    
    async def _check_audit_trail_completeness(self) -> List[dict[str, Any]]:
        """Check audit trail completeness."""
        issues = []
        
        try:
            # Check for recent flow state changes without audit entries
            recent_flows = self.db.query(FlowState).filter(
                FlowState.updated_at >= datetime.utcnow() - timedelta(hours=24)
            ).all()
            
            for flow in recent_flows:
                audit_key = f"audit:flow_state:{flow.id}:{datetime.utcnow().strftime('%Y%m%d')}"
                audit_entries = await self.redis.lrange(audit_key, 0, -1)
                
                if not audit_entries:
                    issues.append({
                        'type': 'missing_audit_trail',
                        'entity_type': 'flow_state',
                        'entity_id': str(flow.id),
                        'patient_id': str(flow.patient_id),
                        'severity': 'low'
                    })
            
            return issues
            
        except Exception as e:
            logger.error(f"Error checking audit trail completeness: {e}")
            return [{'type': 'audit_check_error', 'error': str(e), 'severity': 'critical'}]
    
    async def _check_synchronization_lag(self) -> List[dict[str, Any]]:
        """Check for synchronization lag between systems."""
        issues = []
        
        try:
            # Check Redis sync queue depth
            sync_queue_depth = await self.redis.llen("sync_queue")
            
            if sync_queue_depth > 100:
                issues.append({
                    'type': 'high_sync_queue_depth',
                    'queue_depth': sync_queue_depth,
                    'severity': 'medium'
                })
            
            # Check last sync timestamp
            last_sync = await self.redis.get("last_sync_timestamp")
            if last_sync:
                last_sync_time = datetime.fromisoformat(last_sync.decode())
                lag_minutes = (datetime.utcnow() - last_sync_time).total_seconds() / 60
                
                if lag_minutes > 30:  # 30 minutes lag threshold
                    issues.append({
                        'type': 'high_sync_lag',
                        'lag_minutes': lag_minutes,
                        'last_sync': last_sync_time.isoformat(),
                        'severity': 'high'
                    })
            
            return issues
            
        except Exception as e:
            logger.error(f"Error checking synchronization lag: {e}")
            return [{'type': 'sync_lag_check_error', 'error': str(e), 'severity': 'critical'}]
    
    async def _store_consistency_report(self, report: dict[str, Any]) -> None:
        """Store consistency report."""
        try:
            report_key = f"consistency_report:{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            await self.redis.setex(report_key, 86400 * 7, json.dumps(report))
            
        except Exception as e:
            logger.error(f"Error storing consistency report: {e}")
    
    async def _sync_pending_patient_updates(self) -> dict[str, Any]:
        """Sync pending patient updates."""
        try:
            # Get pending updates from sync queue
            pending_updates = await self.redis.lrange("patient_sync_queue", 0, self.sync_config['batch_size'] - 1)
            
            synced_count = 0
            failed_count = 0
            
            for update_data in pending_updates:
                try:
                    update = json.loads(update_data)
                    patient_id = UUID(update['patient_id'])
                    interactions = update['interactions']
                    
                    success = await self.sync_patient_record_updates(patient_id, interactions)
                    
                    if success:
                        synced_count += 1
                        # Remove from queue
                        await self.redis.lrem("patient_sync_queue", 1, update_data)
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing patient update: {e}")
                    failed_count += 1
            
            return {
                'success': failed_count == 0,
                'synced_count': synced_count,
                'failed_count': failed_count,
                'total_processed': len(pending_updates)
            }
            
        except Exception as e:
            logger.error(f"Error syncing pending patient updates: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _sync_pending_audit_entries(self) -> dict[str, Any]:
        """Sync pending audit entries."""
        try:
            # Get pending audit entries
            pending_audits = await self.redis.lrange("audit_sync_queue", 0, self.sync_config['batch_size'] - 1)
            
            synced_count = 0
            failed_count = 0
            
            for audit_data in pending_audits:
                try:
                    audit_entry = json.loads(audit_data)
                    await self._store_audit_entry_in_database(audit_entry)
                    
                    synced_count += 1
                    # Remove from queue
                    await self.redis.lrem("audit_sync_queue", 1, audit_data)
                    
                except Exception as e:
                    logger.error(f"Error syncing audit entry: {e}")
                    failed_count += 1
            
            return {
                'success': failed_count == 0,
                'synced_count': synced_count,
                'failed_count': failed_count,
                'total_processed': len(pending_audits)
            }
            
        except Exception as e:
            logger.error(f"Error syncing pending audit entries: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _cleanup_old_sync_data(self) -> dict[str, Any]:
        """Clean up old synchronization data."""
        try:
            cleaned_count = 0
            
            # Clean up old consistency reports
            report_keys = await self.redis.keys("consistency_report:*")
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            for key in report_keys:
                try:
                    # Extract date from key
                    date_str = key.decode().split(':')[1]
                    report_date = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                    
                    if report_date < cutoff_date:
                        await self.redis.delete(key)
                        cleaned_count += 1
                        
                except Exception as e:
                    logger.error(f"Error cleaning up report key {key}: {e}")
            
            # Clean up old audit entries
            audit_keys = await self.redis.keys("audit_db:*")
            for key in audit_keys:
                try:
                    ttl = await self.redis.ttl(key)
                    if ttl == -1:  # No expiration set
                        await self.redis.expire(key, 86400 * 365)  # Set 1 year expiration
                        
                except Exception as e:
                    logger.error(f"Error setting expiration for audit key {key}: {e}")
            
            return {
                'success': True,
                'cleaned_count': cleaned_count
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up old sync data: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _store_sync_results(self, results: dict[str, Any]) -> None:
        """Store synchronization results."""
        try:
            results_key = f"sync_results:{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            await self.redis.setex(results_key, 86400 * 7, json.dumps(results))
            
            # Update last sync timestamp
            await self.redis.set("last_sync_timestamp", datetime.utcnow().isoformat())
            
        except Exception as e:
            logger.error(f"Error storing sync results: {e}")


# Service factory function
def get_platform_sync_service(db: Any) -> PlatformSynchronizationService:
    """Factory function to create PlatformSynchronizationService instance."""
    from redis import Redis
    from app.repositories.patient import PatientRepository
    from app.repositories.flow import FlowStateRepository
    from app.services.websocket_events import WebSocketEventService
    
    # Initialize dependencies
    redis = Redis(host='localhost', port=6379, db=0)
    patient_repository = PatientRepository(db)
    flow_repository = FlowStateRepository(db)
    websocket_service = WebSocketEventService()
    
    return PlatformSynchronizationService(
        db=db,
        redis=redis,
        patient_repository=patient_repository,
        flow_repository=flow_repository,
        websocket_service=websocket_service
    )


# Enum for sync event types
class SyncEventType:
    """Enum for synchronization event types."""
    PATIENT_UPDATED = "patient_updated"
    FLOW_STATE_CHANGED = "flow_state_changed"
    MESSAGE_SENT = "message_sent"
    QUIZ_COMPLETED = "quiz_completed"
    ALERT_TRIGGERED = "alert_triggered"
    AUDIT_ENTRY_CREATED = "audit_entry_created"
