# Flow Domain - Domain-Driven Design Architecture

**Version**: 2.0.0
**Status**: ✅ Production Ready
**Refactored**: 2025-11-07

---

## Quick Start

### Import the Orchestrator

```python
# ✅ Recommended (new location)
from app.domain.flows import FlowOrchestrator, create_flow_orchestrator

# ⚠️  Deprecated (still works but shows warnings)
from app.services.orchestrators.flow_orchestrator import FlowOrchestrator
```

### Create an Orchestrator

```python
from app.domain.flows import create_flow_orchestrator

orchestrator = create_flow_orchestrator(db_session)
```

### Use Flow Operations

```python
# Start a flow
result = await orchestrator.start_patient_flow(patient_id)

# Advance a flow
result = await orchestrator.advance_patient_flow(patient_id, target_day=5)

# Pause a flow
result = await orchestrator.pause_patient_flow(patient_id, reason="Patient request")

# Resume a flow
result = await orchestrator.resume_patient_flow(patient_id)

# Stop a flow
result = await orchestrator.stop_patient_flow(patient_id, reason="Treatment completed")
```

---

## Architecture Overview

### Module Structure

```
app/domain/flows/
├── orchestrator.py          # Main coordinator
│
├── state/                   # State Management
│   ├── state_manager.py     # State CRUD and caching
│   └── state_validator.py   # Validation rules
│
├── messaging/               # Message Handling
│   ├── message_composer.py  # AI personalization
│   └── message_sender.py    # Delivery scheduling
│
├── scheduling/              # Scheduling Logic
│   ├── quiz_scheduler.py    # Quiz triggers
│   └── follow_up_scheduler.py # Follow-ups
│
├── templates/               # Template Management
│   ├── renderer.py          # Template loading
│   └── context_builder.py   # Context creation
│
├── rules/                   # Business Rules
│   ├── engine.py            # Rule execution
│   └── evaluator.py         # Condition evaluation
│
├── ab_testing/              # A/B Testing
│   ├── manager.py           # Test management
│   └── variant_selector.py  # Variant selection
│
├── analytics/               # Analytics
│   ├── collector.py         # Event tracking
│   └── metrics.py           # Metric calculation
│
└── error_handling/          # Error Handling
    ├── handler.py           # Error classification
    └── recovery.py          # Recovery strategies
```

---

## Module Responsibilities

### 🔄 State Management
**Purpose**: Manage flow state lifecycle

```python
from app.domain.flows.state import FlowStateManager, FlowStateValidator

# State manager handles CRUD and caching
state_manager = FlowStateManager(db, flow_state_repo)
flow_state = state_manager.get_cached_flow_state(patient_id)

# State validator enforces business rules
validator = FlowStateValidator()
is_valid, error = validator.validate_flow_start(patient, existing_flow, flow_type)
```

---

### 📧 Messaging
**Purpose**: Compose and send messages

```python
from app.domain.flows.messaging import MessageComposer, MessageSender

# Composer generates personalized messages
composer = MessageComposer(ai_service, ai_circuit_breaker)
message = await composer.generate_personalized_message(patient, template, day, flow_type)

# Sender handles delivery
sender = MessageSender(db, message_scheduler, whatsapp_circuit_breaker)
result = await sender.schedule_flow_message(...)
```

---

### 📅 Scheduling
**Purpose**: Schedule quizzes and follow-ups

```python
from app.domain.flows.scheduling import QuizScheduler, FollowUpScheduler

# Quiz scheduler handles quiz triggers
quiz_scheduler = QuizScheduler(db)
should_trigger = await quiz_scheduler.should_trigger_quiz(flow_type, day, flow_state)

# Follow-up scheduler calculates timing
follow_up_scheduler = FollowUpScheduler()
next_time = follow_up_scheduler.calculate_next_follow_up(base_time, 'daily')
```

---

### 📝 Templates
**Purpose**: Load and render templates

```python
from app.domain.flows.templates import TemplateRenderer, TemplateContextBuilder

# Renderer loads templates
renderer = TemplateRenderer(template_loader, flow_template_loader)
template = await renderer.get_message_template_for_day(flow_type, day)

# Context builder creates data structures
context_builder = TemplateContextBuilder()
context = context_builder.build_message_context(patient, flow_type, day, intent)
```

---

### ⚖️ Rules
**Purpose**: Execute business rules

```python
from app.domain.flows.rules import FlowRulesEngine, RuleConditionEvaluator

# Rules engine determines flow behavior
rules_engine = FlowRulesEngine()
flow_type = rules_engine.determine_flow_type(treatment_day)

# Evaluator checks conditions
evaluator = RuleConditionEvaluator()
is_valid = evaluator.evaluate_time_condition(current_time, condition)
```

---

### 🧪 A/B Testing
**Purpose**: Manage experiments

```python
from app.domain.flows.ab_testing import ABTestManager, VariantSelector

# Manager handles tests
ab_test_manager = ABTestManager()
test_id = ab_test_manager.create_test('new_flow', ['control', 'variant_a'], {})

# Selector assigns variants
variant_selector = VariantSelector()
variant = variant_selector.select_variant(patient_id, variants, allocation)
```

---

### 📊 Analytics
**Purpose**: Track events and metrics

```python
from app.domain.flows.analytics import AnalyticsCollector, FlowMetricsCalculator

# Collector tracks events
collector = AnalyticsCollector(analytics_service)
await collector.track_flow_start(patient_id, flow_type, day, metadata)

# Calculator computes metrics
calculator = FlowMetricsCalculator()
metrics = calculator.calculate_batch_metrics(processed, successful, failed, skipped, time)
```

---

### ⚠️ Error Handling
**Purpose**: Handle and recover from errors

```python
from app.domain.flows.error_handling import FlowErrorHandler, ErrorRecoveryManager

# Handler classifies errors
error_handler = FlowErrorHandler()
flow_error = await error_handler.handle_error(error, context, operation)

# Recovery manager attempts recovery
recovery_manager = ErrorRecoveryManager()
success = await recovery_manager.recover(error_type, context)
```

---

## Common Use Cases

### 1. Starting a Patient Flow

```python
from app.domain.flows import create_flow_orchestrator

orchestrator = create_flow_orchestrator(db)

# Auto-detect flow type based on treatment day
result = await orchestrator.start_patient_flow(
    patient_id=patient_id
)

# Or specify flow type explicitly
result = await orchestrator.start_patient_flow(
    patient_id=patient_id,
    flow_type='day_1_15',
    metadata={'source': 'enrollment'}
)

if result.success:
    print(f"Flow started: {result.data['flow_type']}")
else:
    print(f"Error: {result.message}")
```

---

### 2. Processing Daily Flows (Batch)

```python
from app.domain.flows import get_flow_orchestrator

orchestrator = get_flow_orchestrator(db)

# Process all active flows
results = await orchestrator.process_daily_flows(limit=1000)

print(f"Processed: {results['processed_patients']}")
print(f"Successful: {results['successful_operations']}")
print(f"Failed: {results['failed_operations']}")
print(f"Quiz triggers: {results['quiz_triggers']}")
```

---

### 3. Scheduling Monthly Assessment

```python
from datetime import datetime, timedelta
from app.domain.flows import create_flow_orchestrator

orchestrator = create_flow_orchestrator(db)

# Schedule assessment for next month
next_month = datetime.utcnow() + timedelta(days=30)

result = await orchestrator.schedule_monthly_assessment(
    patient_id=patient_id,
    assessment_date=next_month
)

if result.success:
    print(f"Assessment scheduled: {result.data['quiz_session_id']}")
```

---

### 4. Health Check

```python
from app.domain.flows import get_flow_orchestrator

orchestrator = get_flow_orchestrator(db)

health = await orchestrator.health_check()

print(f"Overall Healthy: {health['overall_healthy']}")
print(f"Health Percentage: {health['health_percentage']}%")
print(f"Components: {health['components']}")
print(f"Circuit Breakers: {health['circuit_breakers']}")
```

---

### 5. Registering Flow Callbacks

```python
from app.domain.flows import create_flow_orchestrator, FlowExecutionContext

orchestrator = create_flow_orchestrator(db)

# Register callback for flow events
async def on_flow_start(context: FlowExecutionContext, **kwargs):
    print(f"Flow starting for patient {context.patient_id}")

orchestrator.register_flow_callback('before_execution', on_flow_start)
```

---

## Testing

### Unit Testing Modules

```python
# Test state manager
from app.domain.flows.state import FlowStateManager

def test_flow_state_caching(db, flow_state_repo):
    manager = FlowStateManager(db, flow_state_repo)

    # First call - cache miss
    state1 = manager.get_cached_flow_state(patient_id)

    # Second call - cache hit
    state2 = manager.get_cached_flow_state(patient_id)

    assert state1.id == state2.id
```

### Integration Testing Orchestrator

```python
from app.domain.flows import create_flow_orchestrator

async def test_complete_flow(db, patient):
    orchestrator = create_flow_orchestrator(db)

    # Start flow
    start_result = await orchestrator.start_patient_flow(patient.id)
    assert start_result.success

    # Advance flow
    advance_result = await orchestrator.advance_patient_flow(patient.id, target_day=5)
    assert advance_result.success

    # Stop flow
    stop_result = await orchestrator.stop_patient_flow(patient.id)
    assert stop_result.success
```

---

## Migration Guide

### Step 1: Update Imports

```python
# Before
from app.services.orchestrators.flow_orchestrator import (
    FlowOrchestrator,
    FlowExecutionContext,
    FlowExecutionResult
)

# After
from app.domain.flows import (
    FlowOrchestrator,
    FlowExecutionContext,
    FlowExecutionResult
)
```

### Step 2: Test

```bash
# Run tests to ensure compatibility
pytest tests/test_flow_orchestrator.py -v
```

### Step 3: Deploy

No code changes required - backward compatible!

---

## Performance Considerations

### Caching
- Flow states are cached for 10 minutes
- Cache automatically cleared on TTL expiration
- Manual invalidation on state updates

### Circuit Breakers
- WhatsApp service: 5 failures, 60s timeout
- AI service: 3 failures, 45s timeout
- Automatic recovery after successful calls

### Batch Processing
- Default limit: 1,000 patients
- Parallel processing support
- Metrics tracking for monitoring

---

## Troubleshooting

### Issue: Deprecation Warnings

```python
# Solution: Update imports
from app.domain.flows import FlowOrchestrator  # ✅ New
# Instead of
from app.services.orchestrators.flow_orchestrator import FlowOrchestrator  # ⚠️ Old
```

### Issue: Import Errors

```python
# Ensure domain package is in Python path
import sys
sys.path.append('/path/to/backend-hormonia')

# Or use proper package imports
from app.domain.flows import FlowOrchestrator
```

### Issue: Test Failures

```bash
# Check if all modules are properly installed
python -c "from app.domain.flows import FlowOrchestrator; print('OK')"

# Run tests with verbose output
pytest tests/test_flow_orchestrator.py -vvv
```

---

## Additional Resources

- **Refactoring Report**: `REFACTORING_REPORT.md`
- **Original Backup**: `app/services/orchestrators/flow_orchestrator_ORIGINAL_BACKUP.py`
- **Architecture Docs**: See individual module docstrings

---

## Support

For issues or questions:
1. Check module docstrings
2. Review REFACTORING_REPORT.md
3. Contact development team

---

**Last Updated**: 2025-11-07
**Maintainer**: Clínica Oncológica Development Team
