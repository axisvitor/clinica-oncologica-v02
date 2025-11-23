"""
Critical error escalation and notification system.
Implements escalation logic for critical system errors and automated notifications.
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from uuid import uuid4
from enum import Enum
from dataclasses import dataclass
import json

# from sqlalchemy.orm import
from redis import Redis

from app.services.flow_monitoring import FlowMonitoringService, AlertSeverity
from app.services.websocket_events import WebSocketEventService
from app.schemas.websocket import WebSocketEventType, create_websocket_message

logger = logging.getLogger(__name__)


class EscalationLevel(Enum):
    LEVEL_1 = "level_1"  # Team lead notification
    LEVEL_2 = "level_2"  # Manager notification
    LEVEL_3 = "level_3"  # Director notification
    LEVEL_4 = "level_4"  # Executive notification


@dataclass
class EscalationRule:
    """Escalation rule configuration."""
    alert_severity: AlertSeverity
    component: str
    initial_delay: int  # seconds
    escalation_intervals: List[int]  # seconds between escalation levels
    max_level: EscalationLevel
    auto_resolve_threshold: int  # seconds after which to auto-resolve if no activity


@dataclass
class ActiveEscalation:
    """Active escalation tracking."""
    id: str
    alert_id: str
    rule: EscalationRule
    current_level: EscalationLevel
    created_at: datetime
    last_escalated_at: datetime
    acknowledged: bool
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    resolved: bool
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    resolution_note: Optional[str]
    notification_history: List[Dict[str, Any]]


class CriticalErrorEscalationService:
    """Service for escalating critical errors and managing notifications."""
    
    def __init__(self, db: Any, redis: Redis, 
                 monitoring_service: FlowMonitoringService,
                 websocket_service: WebSocketEventService):
        self.db = db
        self.redis = redis
        self.monitoring_service = monitoring_service
        self.websocket_service = websocket_service
        
        # Escalation rules configuration
        self.escalation_rules = [
            EscalationRule(
                alert_severity=AlertSeverity.CRITICAL,
                component="flow_processing",
                initial_delay=300,  # 5 minutes
                escalation_intervals=[900, 1800, 3600],  # 15min, 30min, 1hr
                max_level=EscalationLevel.LEVEL_4,
                auto_resolve_threshold=7200  # 2 hours
            ),
            EscalationRule(
                alert_severity=AlertSeverity.CRITICAL,
                component="database",
                initial_delay=60,  # 1 minute
                escalation_intervals=[300, 900, 1800],  # 5min, 15min, 30min
                max_level=EscalationLevel.LEVEL_4,
                auto_resolve_threshold=3600  # 1 hour
            ),
            EscalationRule(
                alert_severity=AlertSeverity.CRITICAL,
                component="redis",
                initial_delay=120,  # 2 minutes
                escalation_intervals=[600, 1200, 2400],  # 10min, 20min, 40min
                max_level=EscalationLevel.LEVEL_3,
                auto_resolve_threshold=3600  # 1 hour
            ),
            EscalationRule(
                alert_severity=AlertSeverity.HIGH,
                component="message_queue",
                initial_delay=600,  # 10 minutes
                escalation_intervals=[1800, 3600],  # 30min, 1hr
                max_level=EscalationLevel.LEVEL_2,
                auto_resolve_threshold=10800  # 3 hours
            ),
            EscalationRule(
                alert_severity=AlertSeverity.CRITICAL,
                component="data_integrity",
                initial_delay=180,  # 3 minutes
                escalation_intervals=[600, 1800, 3600],  # 10min, 30min, 1hr
                max_level=EscalationLevel.LEVEL_4,
                auto_resolve_threshold=7200  # 2 hours
            )
        ]
        
        # Notification channels by escalation level
        self.notification_channels = {
            EscalationLevel.LEVEL_1: ["team_leads", "websocket"],
            EscalationLevel.LEVEL_2: ["team_leads", "managers", "websocket", "email"],
            EscalationLevel.LEVEL_3: ["team_leads", "managers", "directors", "websocket", "email", "sms"],
            EscalationLevel.LEVEL_4: ["team_leads", "managers", "directors", "executives", "websocket", "email", "sms", "phone"]
        }
    
    async def check_escalation_triggers(self) -> List[Dict[str, Any]]:
        """Check for alerts that should trigger escalations."""
        try:
            # Get active alerts
            active_alerts = await self.monitoring_service.get_active_alerts()
            
            triggers = []
            
            for alert in active_alerts:
                # Check if alert matches any escalation rule
                matching_rule = self._find_matching_rule(alert)
                
                if matching_rule:
                    # Check if escalation already exists
                    escalation_key = f"escalation:{alert.id}"
                    existing_escalation = await self.redis.get(escalation_key)
                    
                    if not existing_escalation:
                        # Check if initial delay has passed
                        time_since_alert = (datetime.utcnow() - alert.created_at).total_seconds()
                        
                        if time_since_alert >= matching_rule.initial_delay:
                            # Create new escalation
                            escalation = await self._create_escalation(alert, matching_rule)
                            triggers.append({
                                'alert_id': alert.id,
                                'escalation_id': escalation.id,
                                'rule': {
                                    'severity': matching_rule.alert_severity.value,
                                    'component': matching_rule.component,
                                    'initial_delay': matching_rule.initial_delay
                                },
                                'action': 'escalation_created'
                            })
                    else:
                        # Check existing escalation for level progression
                        escalation_data = json.loads(existing_escalation)
                        escalation = self._deserialize_escalation(escalation_data)
                        
                        if not escalation.acknowledged and not escalation.resolved:
                            level_progression = await self._check_level_progression(escalation)
                            if level_progression:
                                triggers.append(level_progression)
            
            return triggers
            
        except Exception as e:
            logger.error(f"Error checking escalation triggers: {e}")
            return []
    
    async def get_active_escalations(self) -> List[Dict[str, Any]]:
        """Get all active escalations."""
        try:
            escalation_keys = await self.redis.keys("escalation:*")
            escalations = []
            
            for key in escalation_keys:
                escalation_data = await self.redis.get(key)
                if escalation_data:
                    escalation_dict = json.loads(escalation_data)
                    if not escalation_dict.get('resolved', False):
                        escalations.append(escalation_dict)
            
            return sorted(escalations, key=lambda x: x['created_at'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error getting active escalations: {e}")
            return []
    
    async def acknowledge_escalation(self, escalation_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an escalation."""
        try:
            escalation_key = f"escalation:{escalation_id}"
            escalation_data = await self.redis.get(escalation_key)
            
            if not escalation_data:
                return False
            
            escalation_dict = json.loads(escalation_data)
            escalation_dict['acknowledged'] = True
            escalation_dict['acknowledged_by'] = acknowledged_by
            escalation_dict['acknowledged_at'] = datetime.utcnow().isoformat()
            
            # Add to notification history
            escalation_dict['notification_history'].append({
                'action': 'acknowledged',
                'by': acknowledged_by,
                'at': datetime.utcnow().isoformat(),
                'level': escalation_dict['current_level']
            })
            
            await self.redis.setex(escalation_key, 86400 * 7, json.dumps(escalation_dict))
            
            # Send WebSocket notification
            await self._send_escalation_notification(
                escalation_dict, 
                f"Escalation acknowledged by {acknowledged_by}"
            )
            
            logger.info(f"Escalation {escalation_id} acknowledged by {acknowledged_by}")
            return True
            
        except Exception as e:
            logger.error(f"Error acknowledging escalation {escalation_id}: {e}")
            return False
    
    async def resolve_escalation(self, escalation_id: str, resolved_by: str, resolution_note: str) -> bool:
        """Resolve an escalation."""
        try:
            escalation_key = f"escalation:{escalation_id}"
            escalation_data = await self.redis.get(escalation_key)
            
            if not escalation_data:
                return False
            
            escalation_dict = json.loads(escalation_data)
            escalation_dict['resolved'] = True
            escalation_dict['resolved_by'] = resolved_by
            escalation_dict['resolved_at'] = datetime.utcnow().isoformat()
            escalation_dict['resolution_note'] = resolution_note
            
            # Add to notification history
            escalation_dict['notification_history'].append({
                'action': 'resolved',
                'by': resolved_by,
                'at': datetime.utcnow().isoformat(),
                'note': resolution_note,
                'level': escalation_dict['current_level']
            })
            
            await self.redis.setex(escalation_key, 86400 * 7, json.dumps(escalation_dict))
            
            # Send WebSocket notification
            await self._send_escalation_notification(
                escalation_dict, 
                f"Escalation resolved by {resolved_by}: {resolution_note}"
            )
            
            logger.info(f"Escalation {escalation_id} resolved by {resolved_by}")
            return True
            
        except Exception as e:
            logger.error(f"Error resolving escalation {escalation_id}: {e}")
            return False
    
    async def run_escalation_cycle(self) -> Dict[str, Any]:
        """Run escalation cycle to check for triggers and level progressions."""
        try:
            results = {
                'triggers_checked': 0,
                'escalations_created': 0,
                'level_progressions': 0,
                'auto_resolutions': 0,
                'notifications_sent': 0,
                'errors': []
            }
            
            # Check for new escalation triggers
            triggers = await self.check_escalation_triggers()
            results['triggers_checked'] = len(triggers)
            
            for trigger in triggers:
                if trigger['action'] == 'escalation_created':
                    results['escalations_created'] += 1
                elif trigger['action'] == 'level_progression':
                    results['level_progressions'] += 1
            
            # Check for auto-resolutions
            auto_resolutions = await self._check_auto_resolutions()
            results['auto_resolutions'] = len(auto_resolutions)
            
            # Send pending notifications
            notifications_sent = await self._send_pending_notifications()
            results['notifications_sent'] = notifications_sent
            
            return results
            
        except Exception as e:
            logger.error(f"Error running escalation cycle: {e}")
            return {'error': str(e)}
    
    def _find_matching_rule(self, alert) -> Optional[EscalationRule]:
        """Find escalation rule that matches the alert."""
        for rule in self.escalation_rules:
            if (rule.alert_severity == alert.severity and 
                rule.component == alert.component):
                return rule
        return None
    
    async def _create_escalation(self, alert, rule: EscalationRule) -> ActiveEscalation:
        """Create a new escalation."""
        escalation_id = str(uuid4())
        
        escalation = ActiveEscalation(
            id=escalation_id,
            alert_id=alert.id,
            rule=rule,
            current_level=EscalationLevel.LEVEL_1,
            created_at=datetime.utcnow(),
            last_escalated_at=datetime.utcnow(),
            acknowledged=False,
            acknowledged_by=None,
            acknowledged_at=None,
            resolved=False,
            resolved_by=None,
            resolved_at=None,
            resolution_note=None,
            notification_history=[]
        )
        
        # Store escalation
        escalation_key = f"escalation:{escalation_id}"
        escalation_data = self._serialize_escalation(escalation)
        await self.redis.setex(escalation_key, 86400 * 7, json.dumps(escalation_data))
        
        # Send initial notification
        await self._send_escalation_notification(
            escalation_data,
            f"Critical alert escalated: {alert.title}"
        )
        
        logger.warning(f"Created escalation {escalation_id} for alert {alert.id}")
        return escalation
    
    async def _check_level_progression(self, escalation: ActiveEscalation) -> Optional[Dict[str, Any]]:
        """Check if escalation should progress to next level."""
        if escalation.acknowledged or escalation.resolved:
            return None
        
        time_since_last_escalation = (datetime.utcnow() - escalation.last_escalated_at).total_seconds()
        current_level_index = list(EscalationLevel).index(escalation.current_level)
        
        if current_level_index < len(escalation.rule.escalation_intervals):
            required_interval = escalation.rule.escalation_intervals[current_level_index]
            
            if time_since_last_escalation >= required_interval:
                # Progress to next level
                next_level = list(EscalationLevel)[current_level_index + 1]
                
                if next_level.value <= escalation.rule.max_level.value:
                    escalation.current_level = next_level
                    escalation.last_escalated_at = datetime.utcnow()
                    
                    # Update stored escalation
                    escalation_key = f"escalation:{escalation.id}"
                    escalation_data = self._serialize_escalation(escalation)
                    await self.redis.setex(escalation_key, 86400 * 7, json.dumps(escalation_data))
                    
                    # Send escalation notification
                    await self._send_escalation_notification(
                        escalation_data,
                        f"Escalation progressed to {next_level.value}"
                    )
                    
                    return {
                        'alert_id': escalation.alert_id,
                        'escalation_id': escalation.id,
                        'action': 'level_progression',
                        'previous_level': list(EscalationLevel)[current_level_index].value,
                        'new_level': next_level.value
                    }
        
        return None
    
    async def _check_auto_resolutions(self) -> List[str]:
        """Check for escalations that should be auto-resolved."""
        auto_resolved = []
        
        try:
            escalation_keys = await self.redis.keys("escalation:*")
            
            for key in escalation_keys:
                escalation_data = await self.redis.get(key)
                if escalation_data:
                    escalation_dict = json.loads(escalation_data)
                    
                    if not escalation_dict.get('resolved', False):
                        created_at = datetime.fromisoformat(escalation_dict['created_at'])
                        time_since_creation = (datetime.utcnow() - created_at).total_seconds()
                        
                        # Get rule from escalation data
                        rule_data = escalation_dict['rule']
                        auto_resolve_threshold = rule_data.get('auto_resolve_threshold', 7200)
                        
                        if time_since_creation >= auto_resolve_threshold:
                            # Auto-resolve escalation
                            escalation_dict['resolved'] = True
                            escalation_dict['resolved_by'] = 'system'
                            escalation_dict['resolved_at'] = datetime.utcnow().isoformat()
                            escalation_dict['resolution_note'] = 'Auto-resolved due to timeout'
                            
                            escalation_dict['notification_history'].append({
                                'action': 'auto_resolved',
                                'by': 'system',
                                'at': datetime.utcnow().isoformat(),
                                'reason': 'timeout'
                            })
                            
                            await self.redis.setex(key, 86400 * 7, json.dumps(escalation_dict))
                            
                            # Send notification
                            await self._send_escalation_notification(
                                escalation_dict,
                                "Escalation auto-resolved due to timeout"
                            )
                            
                            auto_resolved.append(escalation_dict['id'])
                            logger.info(f"Auto-resolved escalation {escalation_dict['id']}")
            
            return auto_resolved
            
        except Exception as e:
            logger.error(f"Error checking auto-resolutions: {e}")
            return []
    
    async def _send_escalation_notification(self, escalation_data: Dict[str, Any], message: str) -> None:
        """Send escalation notification via WebSocket."""
        try:
            # Create WebSocket event
            event_data = {
                'escalation_id': escalation_data['id'],
                'alert_id': escalation_data['alert_id'],
                'level': escalation_data['current_level'],
                'message': message,
                'acknowledged': escalation_data.get('acknowledged', False),
                'resolved': escalation_data.get('resolved', False),
                'created_at': escalation_data['created_at']
            }
            
            websocket_message = create_websocket_message(
                WebSocketEventType.ALERT_CREATED,
                event_data
            )
            
            # Broadcast to all authenticated connections
            await self.websocket_service.broadcast_to_all_authenticated(websocket_message.dict())
            
        except Exception as e:
            logger.error(f"Error sending escalation notification: {e}")
    
    async def _send_pending_notifications(self) -> int:
        """Send any pending notifications."""
        # Placeholder for external notification system integration
        # This would integrate with email, SMS, phone call systems
        return 0
    
    def _serialize_escalation(self, escalation: ActiveEscalation) -> Dict[str, Any]:
        """Serialize escalation to dictionary."""
        return {
            'id': escalation.id,
            'alert_id': escalation.alert_id,
            'rule': {
                'alert_severity': escalation.rule.alert_severity.value,
                'component': escalation.rule.component,
                'initial_delay': escalation.rule.initial_delay,
                'escalation_intervals': escalation.rule.escalation_intervals,
                'max_level': escalation.rule.max_level.value,
                'auto_resolve_threshold': escalation.rule.auto_resolve_threshold
            },
            'current_level': escalation.current_level.value,
            'created_at': escalation.created_at.isoformat(),
            'last_escalated_at': escalation.last_escalated_at.isoformat(),
            'acknowledged': escalation.acknowledged,
            'acknowledged_by': escalation.acknowledged_by,
            'acknowledged_at': escalation.acknowledged_at.isoformat() if escalation.acknowledged_at else None,
            'resolved': escalation.resolved,
            'resolved_by': escalation.resolved_by,
            'resolved_at': escalation.resolved_at.isoformat() if escalation.resolved_at else None,
            'resolution_note': escalation.resolution_note,
            'notification_history': escalation.notification_history
        }
    
    def _deserialize_escalation(self, data: Dict[str, Any]) -> ActiveEscalation:
        """Deserialize escalation from dictionary."""
        rule = EscalationRule(
            alert_severity=AlertSeverity(data['rule']['alert_severity']),
            component=data['rule']['component'],
            initial_delay=data['rule']['initial_delay'],
            escalation_intervals=data['rule']['escalation_intervals'],
            max_level=EscalationLevel(data['rule']['max_level']),
            auto_resolve_threshold=data['rule']['auto_resolve_threshold']
        )
        
        return ActiveEscalation(
            id=data['id'],
            alert_id=data['alert_id'],
            rule=rule,
            current_level=EscalationLevel(data['current_level']),
            created_at=datetime.fromisoformat(data['created_at']),
            last_escalated_at=datetime.fromisoformat(data['last_escalated_at']),
            acknowledged=data['acknowledged'],
            acknowledged_by=data['acknowledged_by'],
            acknowledged_at=datetime.fromisoformat(data['acknowledged_at']) if data['acknowledged_at'] else None,
            resolved=data['resolved'],
            resolved_by=data['resolved_by'],
            resolved_at=datetime.fromisoformat(data['resolved_at']) if data['resolved_at'] else None,
            resolution_note=data['resolution_note'],
            notification_history=data['notification_history']
        )
