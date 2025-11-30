# AlertManager Refactored - Usage Examples

## Table of Contents
1. [Basic Usage](#basic-usage)
2. [Dependency Injection](#dependency-injection)
3. [Custom Handlers](#custom-handlers)
4. [Testing Examples](#testing-examples)
5. [Advanced Scenarios](#advanced-scenarios)

## Basic Usage

### Quick Start (Default Configuration)

```python
from app.services.alerts import get_alert_manager
from uuid import UUID

# Get default configured instance
manager = get_alert_manager()

# Evaluate patient alerts
patient_id = UUID("...")
context = {
    "last_inbound_message_at": datetime.now() - timedelta(days=3),
    "quiz_responses_count": 0,
    "sentiment_scores": [-0.8, -0.9],
}

alerts = await manager.evaluate_patient_alerts(patient_id, context)

# Process each alert
for alert in alerts:
    result = await manager.process_alert(alert)
    print(f"Alert {alert.id}: {result.total_sent} notifications sent")
```

### Using Individual Handlers

```python
from app.services.alerts import (
    NotificationHandler,
    EscalationHandler,
    PersistenceHandler,
    ThresholdManager,
    MetricsCollector,
)

# Initialize handlers independently
notification_handler = NotificationHandler()
escalation_handler = EscalationHandler()
persistence_handler = PersistenceHandler()
threshold_manager = ThresholdManager()
metrics_collector = MetricsCollector()

# Use handlers directly
if await threshold_manager.should_debounce(alert):
    print("Alert debounced")
else:
    # Store alert
    await persistence_handler.store_alert(alert)

    # Get targets
    targets = [...]

    # Dispatch
    result = await notification_handler.dispatch(alert, targets)

    # Track metrics
    metrics_collector.record_alert_dispatched(alert, result)
```

## Dependency Injection

### Custom Configuration

```python
from app.services.alerts import (
    AlertManager,
    NotificationHandler,
    EscalationHandler,
    AlertSystemConfig,
)

# Create custom config
config = AlertSystemConfig(
    debounce_minutes=10,
    max_escalation_level=5,
    notification_timeout=60,
)

# Initialize handlers with custom config
notification_handler = NotificationHandler(config=config)
escalation_handler = EscalationHandler(config=config)

# Inject into AlertManager
manager = AlertManager(
    notification_handler=notification_handler,
    escalation_handler=escalation_handler,
    config=config,
)
```

### With Custom Repository

```python
from app.services.alerts import (
    AlertManager,
    PersistenceHandler,
)
from app.services.alerts.base import AlertRepository

# Implement custom repository
class PostgresAlertRepository(AlertRepository):
    def __init__(self, db_session):
        self.db = db_session

    async def create(self, alert: Alert) -> Alert:
        # Store in PostgreSQL
        db_alert = AlertModel(**alert.dict())
        self.db.add(db_alert)
        await self.db.commit()
        return alert

    async def get_by_id(self, alert_id: UUID) -> Optional[Alert]:
        # Retrieve from PostgreSQL
        db_alert = await self.db.query(AlertModel).filter_by(id=alert_id).first()
        return Alert(**db_alert.dict()) if db_alert else None

    # Implement other methods...

# Use custom repository
persistence_handler = PersistenceHandler(
    repository=PostgresAlertRepository(db_session)
)

manager = AlertManager(
    persistence_handler=persistence_handler,
)
```

## Custom Handlers

### Custom Notification Channel

```python
from app.services.alerts.base import NotificationChannelHandler
from app.services.alerts import NotificationHandler, NotificationChannel

class TelegramChannelHandler(NotificationChannelHandler):
    """Custom Telegram notification handler."""

    def __init__(self, bot_token: str, config=None):
        super().__init__(config)
        self.bot_token = bot_token

    async def send(
        self, alert: Alert, target: NotificationTarget
    ) -> NotificationResult:
        """Send notification via Telegram."""
        try:
            # Get user's Telegram chat ID
            chat_id = target.metadata.get("telegram_chat_id")

            if not chat_id:
                return NotificationResult(
                    channel=NotificationChannel.TELEGRAM,
                    target=target,
                    success=False,
                    error="No Telegram chat ID configured",
                    sent_at=datetime.now(),
                )

            # Send message via Telegram API
            message = f"🚨 {alert.title}\n\n{alert.message}"
            # ... Telegram API call ...

            return NotificationResult(
                channel=NotificationChannel.TELEGRAM,
                target=target,
                success=True,
                sent_at=datetime.now(),
            )

        except Exception as e:
            return NotificationResult(
                channel=NotificationChannel.TELEGRAM,
                target=target,
                success=False,
                error=str(e),
                sent_at=datetime.now(),
            )


# Register custom channel
notification_handler = NotificationHandler()
notification_handler.register_channel(
    NotificationChannel.TELEGRAM,
    TelegramChannelHandler(bot_token="YOUR_BOT_TOKEN")
)

# Use in AlertManager
manager = AlertManager(notification_handler=notification_handler)
```

### Custom Escalation Strategy

```python
from app.services.alerts import EscalationHandler

class PriorityEscalationHandler(EscalationHandler):
    """Custom escalation with priority-based delays."""

    def _get_escalation_delay(self, alert: Alert) -> int:
        """Custom delay based on patient priority."""

        # Get patient priority from context
        priority = alert.context.get("patient_priority", "normal")

        # Custom delays based on priority
        delays = {
            "vip": 300,      # 5 minutes
            "high": 600,     # 10 minutes
            "normal": 1800,  # 30 minutes
            "low": 3600,     # 1 hour
        }

        base_delay = delays.get(priority, 1800)

        # Shorter delays for higher severity
        if alert.severity == AlertSeverity.FATAL:
            return base_delay // 4
        elif alert.severity == AlertSeverity.CRITICAL:
            return base_delay // 2

        return base_delay


# Use custom escalation
manager = AlertManager(
    escalation_handler=PriorityEscalationHandler()
)
```

## Testing Examples

### Unit Test with Mocks

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.alerts import (
    AlertManager,
    NotificationHandler,
    EscalationHandler,
)

@pytest.fixture
def mock_notification_handler():
    """Mock notification handler."""
    handler = AsyncMock(spec=NotificationHandler)
    handler.dispatch = AsyncMock(return_value=DispatchResult(
        alert_id=UUID("..."),
        total_sent=1,
        total_failed=0,
        results=[],
        dispatched_at=datetime.now(),
    ))
    return handler

@pytest.fixture
def mock_escalation_handler():
    """Mock escalation handler."""
    handler = MagicMock(spec=EscalationHandler)
    handler.should_escalate = MagicMock(return_value=False)
    return handler

async def test_process_alert_success(
    mock_notification_handler,
    mock_escalation_handler,
):
    """Test successful alert processing."""

    # Create manager with mocks
    manager = AlertManager(
        notification_handler=mock_notification_handler,
        escalation_handler=mock_escalation_handler,
    )

    # Create test alert
    alert = Alert(
        id=UUID("..."),
        rule_id=UUID("..."),
        rule_type=AlertRuleType.NO_RESPONSE,
        severity=AlertSeverity.WARNING,
        status=AlertStatus.PENDING,
        title="Test Alert",
        message="Test message",
        created_at=datetime.now(),
    )

    # Process alert
    result = await manager.process_alert(alert)

    # Verify
    assert result.total_sent == 1
    assert result.total_failed == 0
    mock_notification_handler.dispatch.assert_called_once()
    mock_escalation_handler.should_escalate.assert_called_once()
```

### Integration Test

```python
@pytest.mark.integration
async def test_complete_alert_flow():
    """Test complete alert flow end-to-end."""

    # Use real handlers
    manager = get_alert_manager()

    # Evaluate alerts
    patient_id = UUID("...")
    context = {
        "last_inbound_message_at": datetime.now() - timedelta(days=5),
    }

    alerts = await manager.evaluate_patient_alerts(patient_id, context)

    assert len(alerts) > 0

    # Process first alert
    alert = alerts[0]
    result = await manager.process_alert(alert)

    assert result.total_sent > 0

    # Acknowledge alert
    user_id = UUID("...")
    acknowledged = await manager.acknowledge_alert(alert.id, user_id)

    assert acknowledged.status == AlertStatus.ACKNOWLEDGED
    assert acknowledged.acknowledged_by == user_id

    # Resolve alert
    resolved = await manager.resolve_alert(
        alert.id,
        resolution="Issue resolved manually"
    )

    assert resolved.status == AlertStatus.RESOLVED
```

### Testing Custom Handler

```python
async def test_telegram_handler():
    """Test custom Telegram channel handler."""

    handler = TelegramChannelHandler(bot_token="test_token")

    alert = Alert(
        id=UUID("..."),
        title="Test",
        message="Test message",
        # ... other fields
    )

    target = NotificationTarget(
        user_id=UUID("..."),
        channels=[NotificationChannel.TELEGRAM],
        metadata={"telegram_chat_id": "12345"},
    )

    result = await handler.send(alert, target)

    assert result.success is True
    assert result.channel == NotificationChannel.TELEGRAM
```

## Advanced Scenarios

### Multi-Tenant Alert System

```python
from app.services.alerts import (
    AlertManager,
    PersistenceHandler,
)

class TenantPersistenceHandler(PersistenceHandler):
    """Tenant-aware persistence handler."""

    def __init__(self, tenant_id: str, repository=None):
        super().__init__(repository)
        self.tenant_id = tenant_id

    async def store_alert(self, alert: Alert) -> Alert:
        # Add tenant context
        alert.metadata["tenant_id"] = self.tenant_id
        return await super().store_alert(alert)

    async def list_alerts(self, filters=None, **kwargs):
        # Filter by tenant
        filters = filters or {}
        filters["tenant_id"] = self.tenant_id
        return await super().list_alerts(filters, **kwargs)


# Create tenant-specific manager
def create_tenant_manager(tenant_id: str) -> AlertManager:
    persistence = TenantPersistenceHandler(tenant_id)
    return AlertManager(persistence_handler=persistence)


# Use
clinic_a_manager = create_tenant_manager("clinic_a")
clinic_b_manager = create_tenant_manager("clinic_b")
```

### Alert Batching

```python
from app.services.alerts import NotificationHandler

class BatchingNotificationHandler(NotificationHandler):
    """Handler that batches notifications."""

    def __init__(self, batch_size=10, batch_delay=60, **kwargs):
        super().__init__(**kwargs)
        self.batch_size = batch_size
        self.batch_delay = batch_delay
        self._batch_queue = []
        self._batch_task = None

    async def dispatch(self, alert, targets, channels=None):
        """Add to batch queue instead of sending immediately."""

        self._batch_queue.append((alert, targets, channels))

        # Start batch timer if not running
        if not self._batch_task:
            self._batch_task = asyncio.create_task(
                self._process_batch()
            )

        # If batch full, process immediately
        if len(self._batch_queue) >= self.batch_size:
            await self._process_batch()

        # Return placeholder result
        return DispatchResult(
            alert_id=alert.id,
            total_sent=0,
            total_failed=0,
            results=[],
            dispatched_at=datetime.now(),
        )

    async def _process_batch(self):
        """Process batched notifications."""
        await asyncio.sleep(self.batch_delay)

        if not self._batch_queue:
            return

        # Process all in batch
        for alert, targets, channels in self._batch_queue:
            await super().dispatch(alert, targets, channels)

        # Clear queue
        self._batch_queue.clear()
        self._batch_task = None
```

### Alert Analytics

```python
from app.services.alerts import MetricsCollector

class AnalyticsCollector(MetricsCollector):
    """Extended metrics with analytics."""

    def __init__(self):
        super().__init__()
        self._hourly_stats = defaultdict(lambda: defaultdict(int))

    def record_alert_created(self, alert: Alert):
        """Track creation with hourly buckets."""
        super().record_alert_created(alert)

        # Track by hour
        hour_key = alert.created_at.strftime("%Y-%m-%d %H:00")
        self._hourly_stats[hour_key]["total"] += 1
        self._hourly_stats[hour_key][alert.severity.value] += 1

    def get_hourly_report(self, hours=24):
        """Get hourly breakdown."""
        now = datetime.now()
        report = []

        for i in range(hours):
            hour = now - timedelta(hours=i)
            hour_key = hour.strftime("%Y-%m-%d %H:00")
            stats = self._hourly_stats.get(hour_key, {})

            report.append({
                "hour": hour_key,
                "total": stats.get("total", 0),
                "by_severity": {
                    k: v for k, v in stats.items() if k != "total"
                }
            })

        return report


# Use
manager = AlertManager(metrics_collector=AnalyticsCollector())
```

### Conditional Escalation

```python
from app.services.alerts import EscalationHandler

class ConditionalEscalationHandler(EscalationHandler):
    """Escalation with business hours consideration."""

    def should_escalate(self, alert: Alert) -> bool:
        """Only escalate during business hours."""

        if not super().should_escalate(alert):
            return False

        # Check business hours (9 AM - 6 PM weekdays)
        now = datetime.now()

        if now.weekday() >= 5:  # Weekend
            # Only escalate FATAL alerts on weekends
            return alert.severity == AlertSeverity.FATAL

        if now.hour < 9 or now.hour >= 18:  # Outside business hours
            # Only escalate CRITICAL/FATAL
            return alert.severity in [
                AlertSeverity.CRITICAL,
                AlertSeverity.FATAL
            ]

        return True


# Use
manager = AlertManager(
    escalation_handler=ConditionalEscalationHandler()
)
```

## Summary

The refactored AlertManager provides:

✅ **Flexible Configuration**: Customize any component
✅ **Easy Testing**: Mock any dependency
✅ **Extensibility**: Add custom handlers easily
✅ **Type Safety**: Full type hints throughout
✅ **Backward Compatible**: Existing code works unchanged

For more examples, see:
- `REFACTORING_GUIDE.md` - Complete migration guide
- `REFACTORING_SUMMARY.md` - Executive summary
- Unit tests in `tests/services/alerts/`
