# MessageScheduler Package Architecture

## Canonical Import Entry Point

Use `app.domain.messaging.scheduling` as the stable import gateway for
`MessageScheduler` and related types. The
`core.message_service.scheduler` module is kept only as a legacy compatibility
surface.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    MessageScheduler Package                      │
│                         (__init__.py)                            │
│                   [Public API Gateway]                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┴────────────────┬──────────────────────┐
         │                                │                      │
┌────────▼─────────┐           ┌─────────▼────────┐   ┌────────▼────────┐
│   models.py      │           │   config.py      │   │ scheduler.py    │
│                  │           │                  │   │                 │
│ - Exceptions     │           │ - Configuration  │   │ - Main Service  │
│ - Enums          │           │ - Constants      │   │ - Orchestration │
│ - SchedulingWindow│          │ - Defaults       │   │ - Coordination  │
└──────────────────┘           └──────────────────┘   └────────┬────────┘
                                                                │
                                         ┌──────────────────────┼────────────────┐
                                         │                      │                │
                              ┌──────────▼────────┐  ┌─────────▼────────┐ ┌────▼──────────┐
                              │ timezone_handler.py│  │ task_scheduler.py│ │ retry_handler.py│
                              │                    │  │                  │ │                 │
                              │ - Timezone Logic   │  │ - Celery Tasks   │ │ - Retry Logic   │
                              │ - Time Calculation │  │ - Distributed    │ │ - DLQ Routing   │
                              │ - Window Scheduling│  │   Locking        │ │ - Flow Notify   │
                              └────────────────────┘  └──────────────────┘ └─────────────────┘
                                                                │
                                                      ┌─────────▼──────────┐
                                                      │    metrics.py      │
                                                      │                    │
                                                      │ - Metrics Collection│
                                                      │ - Analytics        │
                                                      │ - Monitoring       │
                                                      └────────────────────┘
```

## Data Flow

### Message Scheduling Flow
```
User Request
    │
    ▼
MessageScheduler.schedule_message()
    │
    ├──► Validate Input (config.py)
    │
    ├──► Get Patient (repositories)
    │
    ├──► Calculate Delivery Time
    │    └──► TimezoneHandler.calculate_optimal_delivery_time()
    │         ├──► Get patient timezone
    │         ├──► Apply scheduling window
    │         └──► Normalize to Sao Paulo timezone
    │
    ├──► Create Message Record (database)
    │
    ├──► Schedule Celery Task
    │    └──► TaskScheduler.schedule_celery_task()
    │         ├──► Acquire distributed lock
    │         ├──► Create Celery task
    │         └──► Return task ID
    │
    └──► Return Result
```

### Failure Handling Flow
```
Delivery Failure
    │
    ▼
MessageScheduler.on_delivery_failure()
    │
    ├──► Get Message Record
    │
    ├──► Update Status & Metadata
    │
    ├──► Check Retry Count
    │
    ├──► If < MAX_RETRIES:
    │    └──► RetryHandler.schedule_retry()
    │         ├──► Calculate backoff delay
    │         ├──► Schedule retry task
    │         └──► Update metadata
    │
    └──► If >= MAX_RETRIES:
         ├──► RetryHandler.route_to_dlq_on_max_retries()
         │    ├──► Categorize failure
         │    ├──► Get patient info
         │    └──► Route to DLQ
         │
         └──► RetryHandler.notify_flow_engine_failure()
              └──► Update flow state
```

## Component Responsibilities

### Core Components

#### `scheduler.py` (Main Orchestrator)
- **Role:** Central coordination and public API
- **Dependencies:** All other components
- **Key Methods:**
  - `schedule_message()` - Main scheduling entry point
  - `schedule_flow_message()` - Flow-specific scheduling
  - `cancel_scheduled_message()` - Cancel scheduled messages
  - `reschedule_message()` - Reschedule messages
  - `on_delivery_failure()` - Handle delivery failures

#### `models.py` (Data Definitions)
- **Role:** Core data structures
- **Dependencies:** None (base module)
- **Exports:**
  - `MessageSchedulingError` - Base exception
  - `TimezoneError` - Timezone errors
  - `TaskSchedulingError` - Task errors
  - `SchedulingWindow` - Time window enum

#### `config.py` (Configuration)
- **Role:** System configuration
- **Dependencies:** `models.py` (for enums)
- **Exports:**
  - `MessageSchedulerConfig` - Configuration class

### Specialized Handlers

#### `timezone_handler.py`
- **Role:** Timezone and time calculations
- **Dependencies:** `models.py`, `config.py`
- **Key Methods:**
  - `get_patient_timezone()` - Extract timezone
  - `calculate_optimal_delivery_time()` - Calculate send time

#### `task_scheduler.py`
- **Role:** Celery task management
- **Dependencies:** Models (Message), distributed locks
- **Key Methods:**
  - `schedule_celery_task()` - Create Celery task
  - `get_task_status()` - Check task status
  - `cancel_celery_task()` - Cancel task

#### `retry_handler.py`
- **Role:** Retry logic and failure handling
- **Dependencies:** `config.py`, repositories, DLQ handler
- **Key Methods:**
  - `calculate_retry_delay()` - Exponential backoff
  - `schedule_retry()` - Schedule retry attempt
  - `route_to_dlq_on_max_retries()` - DLQ routing
  - `categorize_failure_reason()` - Failure categorization
  - `notify_flow_engine_failure()` - Flow notification

#### `metrics.py`
- **Role:** Metrics and monitoring
- **Dependencies:** Models (Message)
- **Key Methods:**
  - `get_scheduled_messages()` - List scheduled messages
  - `get_delivery_metrics()` - Calculate metrics

## Dependency Graph

```
scheduler.py ──────┬─────► timezone_handler.py ──► config.py ──► models.py
                   │
                   ├─────► task_scheduler.py
                   │
                   ├─────► retry_handler.py ─────► config.py
                   │
                   └─────► metrics.py

__init__.py ───────────► All modules (re-exports)
```

## Integration Points

### External Dependencies
- **SQLAlchemy:** Database operations via repositories
- **Celery:** Task scheduling and execution
- **Redis:** Distributed locking for task ordering
- **pytz:** Timezone handling
- **WhatsApp API:** Message delivery (via tasks)
- **DLQ Handler:** Failed message routing

### Internal Dependencies
- **Repositories:** PatientRepository, MessageRepository
- **Models:** Patient, Message, MessageStatus, DeliveryStatus
- **Exceptions:** ValidationError, NotFoundError
- **Utilities:** with_db_retry, distributed locks

## Testing Strategy

### Unit Tests
- **models.py:** Exception classes, enum values
- **config.py:** Configuration validation
- **timezone_handler.py:** Time calculations, timezone handling
- **task_scheduler.py:** Task creation, status checking
- **retry_handler.py:** Backoff calculation, DLQ routing
- **metrics.py:** Metric calculations, data aggregation

### Integration Tests
- **scheduler.py:** End-to-end scheduling flows
- Database transactions
- Celery task creation
- Lock acquisition

### Mock Points
- Database session
- Celery app
- Redis connection
- Repository methods
- External API calls

## Performance Considerations

### Optimization Points
1. **Database Queries:** Indexed on `status`, `scheduled_for`, `patient_id`
2. **Caching:** Task status results can be cached
3. **Batching:** Multiple message scheduling can be batched
4. **Async Operations:** All major operations are async

### Scalability
- **Distributed Locks:** Prevent race conditions across workers
- **Celery Tasks:** Horizontal scaling via workers
- **Database Connection Pooling:** Configured per environment
- **Retry Logic:** Exponential backoff prevents overwhelming system

## Security Considerations

### Input Validation
- Message content length validation
- Phone number validation
- UUID validation
- Scheduling window validation

### Data Protection
- WhatsApp IDs encrypted in transit
- Patient data access via repositories
- Metadata sanitization

### Error Handling
- Graceful degradation
- Detailed logging without exposing sensitive data
- Database rollback on failures

## Monitoring & Observability

### Logging
- Structured logging throughout
- Correlation IDs for request tracking
- Performance metrics logging

### Metrics
- Message delivery success rate
- Retry counts and patterns
- Task scheduling latency
- Lock contention metrics

### Health Checks
- Task scheduler availability
- Database connection health
- Redis connection health
- Celery worker status
