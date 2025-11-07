# Quick Start Guide - Refactored Flow Service

## 🚀 Quick Import

```python
from app.domain.flows.core import FlowService

# Initialize
service = FlowService(db)

# Process daily flows
results = await service.process_daily_flows(limit=1000)

# Generate message preview
preview = await service.generate_personalized_message_preview(
    patient_id=patient_id,
    flow_type="monthly_recurring",
    day=15
)

# Process patient response
result = await service.process_patient_response_with_flow_context(
    patient_id=patient_id,
    response_text="Estou me sentindo melhor hoje",
    message_id=message_id
)

# Health check
health = await service.health_check()
```

---

## 📦 Module Overview

### FlowService (Main Orchestrator)
```python
from app.domain.flows.core import FlowService

service = FlowService(db)
await service.process_daily_flows()
```

### FlowIntegrityService (State Validation)
```python
from app.domain.flows.core import FlowIntegrityService

integrity = FlowIntegrityService(db)
await integrity.validate_flow_consistency(flow_state)
```

### MessageHandler (Message Operations)
```python
from app.domain.flows.core import MessageHandler

handler = MessageHandler(db)
await handler.create_and_schedule_flow_message(...)
```

### FlowScheduler (Scheduling Logic)
```python
from app.domain.flows.core import FlowScheduler

scheduler = FlowScheduler(db)
send_time = await scheduler.calculate_optimal_send_time(patient, day)
```

### TemplateManager (Template Loading)
```python
from app.domain.flows.core import TemplateManager

templates = TemplateManager(db)
template = await templates.get_message_template_for_day(flow_type, day)
```

### AnalyticsTracker (Metrics & Analytics)
```python
from app.domain.flows.core import AnalyticsTracker

analytics = AnalyticsTracker(db)
metrics = await analytics.get_flow_processing_metrics(date_range)
```

---

## 🔄 Migration from Old API

### Before (Old Location)
```python
from app.services.flow import FlowEngineIntegrationService

service = FlowEngineIntegrationService(db)
results = await service.process_daily_flows()
```

### After (New Location)
```python
from app.domain.flows.core import FlowService

service = FlowService(db)
results = await service.process_daily_flows()
```

**Note:** Old imports still work but show deprecation warnings!

---

## 🎯 Common Use Cases

### 1. Process Daily Flows
```python
from app.domain.flows.core import FlowService

service = FlowService(db)
results = await service.process_daily_flows(limit=1000)

print(f"Processed: {results['processed_patients']} patients")
print(f"Scheduled: {results['messages_scheduled']} messages")
print(f"Errors: {results['errors']}")
```

### 2. Generate Message Preview
```python
preview = await service.generate_personalized_message_preview(
    patient_id=patient_uuid,
    flow_type="initial_15_days",
    day=7
)

if preview['status'] == 'success':
    print(preview['preview']['personalized_content'])
```

### 3. Validate Flow Consistency
```python
result = await service.validate_flow_consistency(patient_id)

if result['valid']:
    print("Flow is consistent")
else:
    print(f"Validation error: {result['error']}")
```

### 4. Calculate Optimal Send Time
```python
from app.domain.flows.core import FlowScheduler

scheduler = FlowScheduler(db)
patient = patient_repo.get(patient_id)
send_time = await scheduler.calculate_optimal_send_time(patient, current_day=10)

print(f"Optimal send time: {send_time}")
```

### 5. Load Template with Fallback
```python
from app.domain.flows.core import TemplateManager
from app.services.enhanced_flow_engine import FlowType

manager = TemplateManager(db)
template = await manager.get_message_template_for_day(
    FlowType.MONTHLY_RECURRING,
    day=30
)

if template:
    print(f"Template intent: {template.intent}")
else:
    print("No template available")
```

### 6. Track Analytics
```python
from app.domain.flows.core import AnalyticsTracker
from datetime import datetime, timedelta

tracker = AnalyticsTracker(db)

# Get metrics for last 7 days
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=7)
metrics = await tracker.get_flow_processing_metrics((start_date, end_date))

print(f"Messages generated: {metrics['flow_processing']['messages_generated']}")
```

---

## 🔧 Advanced Usage

### Custom Module Initialization
```python
from app.domain.flows.core import (
    FlowService,
    MessageHandler,
    FlowScheduler
)

# Custom message handler with specific settings
custom_handler = MessageHandler(
    db=db,
    use_unified_service=True  # Use unified WhatsApp service
)

# Custom scheduler
custom_scheduler = FlowScheduler(db)

# Initialize service with custom modules
service = FlowService(
    db=db,
    message_scheduler=my_scheduler,
    use_unified_service=True
)
```

### Direct Module Access
```python
# Access specialized modules directly
state_validator = service.state_machine
message_handler = service.message_handler
scheduler = service.scheduler
templates = service.template_manager
analytics = service.analytics_tracker

# Use them independently
await state_validator.validate_flow_consistency(flow_state)
send_time = await scheduler.calculate_optimal_send_time(patient, day)
```

---

## 🛡️ Error Handling

### Handle Template Loading Errors
```python
from app.domain.flows.core import TemplateManager
from app.services.enhanced_flow_engine import FlowType

manager = TemplateManager(db)
template = await manager.get_message_template_for_day(FlowType.INITIAL_15_DAYS, day=1)

if not template:
    # Fallback already attempted, use default behavior
    logger.warning("No template available, skipping patient")
```

### Handle Message Creation Errors
```python
from app.domain.flows.core import MessageHandler, SchedulerError

handler = MessageHandler(db)

try:
    success = await handler.create_and_schedule_flow_message(
        patient_id, flow_state, template, content, day, send_time
    )

    if not success:
        # Retries exhausted, message creation failed
        logger.error("Failed to create message after retries")

except SchedulerError as e:
    # Scheduling-specific error
    logger.error(f"Scheduler error: {e}")
```

### Handle Validation Errors
```python
from app.domain.flows.core import FlowIntegrityService
from app.exceptions import ValidationError

integrity = FlowIntegrityService(db)

try:
    await integrity.validate_flow_consistency(flow_state)
except ValidationError as e:
    # Flow validation failed
    logger.error(f"Flow validation error: {e}")
```

---

## 📊 Monitoring & Health Checks

### Service Health Check
```python
health = await service.health_check()

if health['overall_healthy']:
    print(f"✅ All systems operational")
    print(f"Health: {health['health_summary']['health_percentage']:.1f}%")
else:
    print(f"⚠️ {health['error_count']} components unhealthy")

    # Check individual components
    for component, status in health['components'].items():
        if not status.get('healthy', False):
            print(f"  ❌ {component}: {status.get('error', 'Unknown error')}")
```

---

## 🧪 Testing

### Unit Testing Individual Modules
```python
import pytest
from app.domain.flows.core import TemplateManager, FlowScheduler

@pytest.mark.asyncio
async def test_template_loading(db_session):
    manager = TemplateManager(db_session)
    template = await manager.get_message_template_for_day(
        FlowType.INITIAL_15_DAYS,
        day=1
    )
    assert template is not None
    assert template.intent is not None

@pytest.mark.asyncio
async def test_send_time_calculation(db_session, sample_patient):
    scheduler = FlowScheduler(db_session)
    send_time = await scheduler.calculate_optimal_send_time(
        sample_patient,
        current_day=5
    )
    assert send_time > datetime.utcnow()
```

### Integration Testing
```python
@pytest.mark.asyncio
async def test_daily_flow_processing(db_session):
    service = FlowService(db_session)
    results = await service.process_daily_flows(limit=10)

    assert results['processed_patients'] >= 0
    assert results['errors'] == 0
    assert 'details' in results
```

---

## 📚 Additional Resources

- **Full Documentation:** See `REFACTORING_SUMMARY.md`
- **Module APIs:** Check docstrings in individual module files
- **Project Guidelines:** Refer to `/CLAUDE.md`

---

## ⚡ Performance Tips

1. **Batch Processing:** Use `limit` parameter for large datasets
2. **Caching:** Template manager caches loaded templates
3. **Async Operations:** All methods are async for non-blocking I/O
4. **Transaction Safety:** Message handler uses atomic transactions
5. **Retry Logic:** Built-in exponential backoff for transient errors

---

## 🐛 Common Issues

### Issue: Deprecation Warnings
**Solution:** Update imports to new location:
```python
# Change from:
from app.services.flow import FlowEngineIntegrationService
# To:
from app.domain.flows.core import FlowService
```

### Issue: Template Not Found
**Solution:** Template manager has automatic fallbacks. Check logs for details.

### Issue: Message Scheduling Fails
**Solution:** Message handler retries 3 times with exponential backoff. Check failed message audit trail.

### Issue: Flow Validation Errors
**Solution:** Use FlowIntegrityService to validate flow state consistency.

---

## 📞 Support

For issues or questions:
1. Check module docstrings for detailed API documentation
2. Review `REFACTORING_SUMMARY.md` for architecture details
3. Consult project guidelines in `/CLAUDE.md`
