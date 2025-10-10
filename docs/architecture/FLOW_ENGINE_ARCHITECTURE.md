# Flow Engine Architecture

## Executive Summary

The Flow Engine is the core automation system orchestrating patient monitoring, message scheduling, and clinical workflow management. It implements a versioned template system with state machine-based progression, AI-powered message humanization, and comprehensive error handling.

**Document Version:** 1.0
**Last Updated:** 2025-10-09
**Status:** Production
**Technology Stack:** Python 3.13, SQLAlchemy, Celery, PostgreSQL, Redis

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Components](#architecture-components)
3. [Flow Lifecycle](#flow-lifecycle)
4. [Data Models](#data-models)
5. [State Machine](#state-machine)
6. [Template System](#template-system)
7. [Integration Points](#integration-points)
8. [Error Handling](#error-handling)
9. [Performance Considerations](#performance-considerations)
10. [Recommendations](#recommendations)

---

## System Overview

### Purpose

The Flow Engine manages automated patient engagement through:
- **Versioned Flow Templates**: Reusable workflow definitions with version control
- **State-Based Progression**: Deterministic state machine for flow advancement
- **Scheduled Messaging**: Time-based message delivery with timezone handling
- **AI Humanization**: Contextual message personalization
- **Quiz Integration**: Patient assessment workflow orchestration
- **Alert Generation**: Automated alert creation based on flow events

### Key Characteristics

- **Database-Driven**: All templates stored in PostgreSQL with versioning
- **Event-Driven**: Celery tasks for async message scheduling
- **Fault-Tolerant**: Retry mechanisms with DB transaction management
- **Scalable**: Repository pattern with eager loading optimization
- **Monitored**: Comprehensive health checks and performance tracking

---

## Architecture Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      FLOW ENGINE LAYERS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              API/Router Layer                           │    │
│  │  - FlowManagementService (flow_management.py)          │    │
│  │  - REST endpoints for flow operations                  │    │
│  └────────────────────────────────────────────────────────┘    │
│                            ↓                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Core Engine Layer                          │    │
│  │  - FlowEngine (flow_engine.py)                         │    │
│  │  - EnhancedFlowEngine (enhanced_flow_engine.py)        │    │
│  │  - FlowCore (flow_core.py) - Shared base               │    │
│  └────────────────────────────────────────────────────────┘    │
│                            ↓                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │          State Machine & Execution                      │    │
│  │  - StateMachine (state_machine.py)                     │    │
│  │  - ConditionEvaluator                                   │    │
│  │  - Template Loader (template_loader.py)                │    │
│  └────────────────────────────────────────────────────────┘    │
│                            ↓                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │           Integration Services                          │    │
│  │  - MessageScheduler (message_scheduler.py)             │    │
│  │  - QuizSessionService                                   │    │
│  │  - AI Humanizer (question_humanizer.py)                │    │
│  │  - FlowEventBroadcaster                                 │    │
│  └────────────────────────────────────────────────────────┘    │
│                            ↓                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Repository Layer                           │    │
│  │  - FlowStateRepository (flow.py)                       │    │
│  │  - FlowTemplateRepository (flow_template.py)           │    │
│  │  - PatientRepository, MessageRepository                │    │
│  └────────────────────────────────────────────────────────┘    │
│                            ↓                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │               Data Models                               │    │
│  │  - PatientFlowState, FlowKind, FlowTemplateVersion     │    │
│  │  - Patient, Message, QuizSession                       │    │
│  └────────────────────────────────────────────────────────┘    │
│                            ↓                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │            PostgreSQL Database                          │    │
│  │  - Tables: patient_flow_states, flow_kinds,            │    │
│  │    flow_template_versions, patients, messages          │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

External Systems:
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Celery     │    │    Redis     │    │   Gemini AI  │
│  (Async      │    │  (Cache &    │    │  (Message    │
│   Tasks)     │    │   Metrics)   │    │  Humanizer)  │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Component Responsibilities

#### 1. **FlowEngine** (`flow_engine.py`)
**Primary flow execution engine**
- Flow lifecycle management (start, process, complete)
- State transition orchestration
- Message scheduling with AI humanization
- Template-to-instance conversion
- Fallback template handling
- Error recovery with retry logic

#### 2. **EnhancedFlowEngine** (`enhanced_flow_engine.py`)
**AI-powered execution extension**
- Inherits from `FlowCore` (shared functionality)
- AI message generation and personalization
- Patient response sentiment analysis
- Conversation history integration
- Empathetic follow-up generation
- Gemini AI client integration

#### 3. **FlowCore** (`flow_core.py`)
**Shared base class**
- Patient enrollment and day calculation
- Flow type determination
- Template handling and caching
- Message timing optimization
- Health monitoring
- Common repository operations

#### 4. **FlowManagementService** (`flow_management.py`)
**High-level flow operations API**
- Flow state queries
- Flow advancement
- Pause/resume operations
- Flow history retrieval
- Template listing
- Error handling and validation

#### 5. **StateMachine** (`state_machine.py`)
**Flow progression logic**
- Step-by-step transition management
- Condition evaluation (quiz, time, patient data)
- Transition validation
- Flow completion detection
- Available transitions enumeration

#### 6. **MessageScheduler** (`message_scheduler.py`)
**Time-based message delivery**
- Timezone-aware scheduling
- Celery task integration
- Delivery window enforcement
- Message cancellation/rescheduling
- Delivery status tracking
- Metrics collection

#### 7. **Template Loader** (`template_loader.py`)
**Template management**
- Database-only template loading
- Version resolution
- MessageTemplate → FlowStep conversion
- Template validation
- Caching with TTL

---

## Flow Lifecycle

### Complete Flow Journey

```
┌─────────────────────────────────────────────────────────────────┐
│                         FLOW LIFECYCLE                           │
└─────────────────────────────────────────────────────────────────┘

[1] TEMPLATE DEFINITION (Database)
    ↓
    FlowKind (flow_type='initial_15_days')
    ↓
    FlowTemplateVersion (version='1.0', is_current=true)
    ↓
    JSONB fields: messages, quiz_templates, alerts


[2] FLOW INSTANTIATION (FlowEngine.start_flow)
    ↓
    a. Get patient
    b. Resolve template (with fallback hierarchy)
    c. Validate template via StateMachine
    d. Check for active flow conflict
    e. Get FlowKind and current FlowTemplateVersion
    f. Create PatientFlowState
       - template_version_id (FK to FlowTemplateVersion)
       - current_step = entry_step
       - started_at = UTC timestamp
       - state_data = initial context
    g. Schedule initial step actions (async)


[3] STATE PROGRESSION (FlowEngine.process_patient_day)
    ↓
    a. Get patient and active flow
    b. Load template_version → kind → flow_type
    c. Build FlowTemplateData from DB
    d. Create StateMachine instance
    e. Build execution context (patient, flow, quiz data)
    f. Attempt state transition:
       - Evaluate conditions (quiz_response, time_based, patient_data)
       - Determine next step
       - Validate transition
    g. Handle transition result:
       - SUCCESS → Update current_step, schedule next actions
       - CONDITION_NOT_MET → Log failed transition
       - FLOW_COMPLETED → Mark completed_at
    h. Commit database changes


[4] STEP EXECUTION (FlowEngine._schedule_step)
    ↓
    a. Calculate scheduled_for (base_time + delay_hours)
    b. Determine question type for humanization control
    c. Apply AI humanization:
       - QuestionHumanizer for quiz/message content
       - Selective humanization (avoid medical/critical)
       - Fallback to original on error
    d. Schedule message via MessageService
    e. Create Celery task (send_scheduled_message)
    f. For quiz steps:
       - Start QuizSession
       - Create placeholder response


[5] MESSAGE DELIVERY (MessageScheduler)
    ↓
    a. Create Message record (status=SCHEDULED)
    b. Calculate optimal delivery time:
       - Patient timezone
       - Scheduling window (morning/business/evening)
       - Minimum buffer (15 minutes)
    c. Schedule Celery task with ETA
    d. Store task_id in message.metadata
    e. Celery executes at scheduled time:
       - Update status → SENT
       - Send via WhatsApp
       - Track delivery/read status


[6] QUIZ INTEGRATION (QuizSessionService)
    ↓
    a. Start quiz session from template
    b. Patient responds → QuizResponse created
    c. Response stored in quiz_responses table
    d. FlowEngine reads responses for condition evaluation
    e. Conditions determine next step


[7] FLOW COMPLETION
    ↓
    a. StateMachine detects next_step=None
    b. FlowEngine._handle_transition_result:
       - Set completed_at timestamp
       - Mark flow as complete
       - Store completion metadata
    c. Patient can start new flow


[8] MONITORING (FlowMonitoringService)
    ↓
    - Track active flows
    - Detect stale flows (>24h no activity)
    - Calculate error rates
    - Generate alerts for anomalies
    - Health checks on components
```

### Key Lifecycle States

| State | DB Field | Description |
|-------|----------|-------------|
| **Not Started** | `flow_state = None` | Patient has no active flow |
| **Active** | `completed_at = NULL` | Flow is running, progressing through steps |
| **Paused** | `state_data.paused = true` | Flow temporarily halted by user/system |
| **Completed** | `completed_at != NULL` | Flow reached final step or manually completed |
| **Error** | `state_data.failed_transitions` | Flow stuck due to condition failures |

---

## Data Models

### Core Tables

#### **flow_kinds** (Flow Type Definition)
```sql
CREATE TABLE flow_kinds (
    id UUID PRIMARY KEY,
    flow_type VARCHAR(100) UNIQUE NOT NULL,  -- 'initial_15_days', 'monthly_recurring'
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    metadata JSONB,  -- Additional configuration
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Purpose:** Defines distinct flow types. Each flow type can have multiple versions.

**Key Fields:**
- `flow_type`: Unique identifier used in code
- `is_active`: Controls visibility in UI/API
- `metadata`: Flexible storage for flow-specific config

---

#### **flow_template_versions** (Versioned Templates)
```sql
CREATE TABLE flow_template_versions (
    id UUID PRIMARY KEY,
    kind_id UUID REFERENCES flow_kinds(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,  -- '1.0', '1.1', '2.0-beta'
    status VARCHAR(20) NOT NULL,   -- 'draft', 'published', 'archived'
    is_current BOOLEAN DEFAULT FALSE,  -- Only ONE per kind

    -- Template Content (JSONB)
    messages JSONB NOT NULL,        -- {day: message_template}
    quiz_templates JSONB,           -- Quiz configurations
    alerts JSONB,                   -- Alert rules
    changelog TEXT,                 -- Version change notes

    -- Audit Trail
    created_by UUID,
    approved_by UUID,
    published_at TIMESTAMP,
    archived_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,

    UNIQUE(kind_id, version)
);
```

**Purpose:** Stores versioned flow templates. Allows A/B testing, rollback, and gradual migration.

**Key Fields:**
- `is_current`: Denotes the active version for new flow instances
- `messages`: Complete day-by-day message templates
- `status`: Lifecycle management (draft → published → archived)

**JSONB Structure Examples:**

```json
// messages field
{
  "1": {
    "day": 1,
    "intent": "welcome",
    "base_content": "Olá [nome], bem-vindo ao programa!",
    "message_type": "text",
    "core_elements": {"greeting": true},
    "personalization_hints": ["patient_name", "treatment_type"],
    "ai_instructions": "Generate warm welcome message",
    "variations": []
  },
  "3": {
    "day": 3,
    "intent": "daily_checkin",
    "base_content": "Como você está se sentindo hoje?",
    "message_type": "text",
    "conditions": [
      {
        "type": "time_based",
        "field": "hours_since_start",
        "operator": "greater_than",
        "value": 48
      }
    ]
  }
}

// quiz_templates field
{
  "symptom_check": {
    "template_name": "daily_symptoms",
    "questions": [...]
  }
}

// alerts field
{
  "high_severity_response": {
    "trigger": "quiz_response",
    "condition": {"severity": "high"},
    "action": "create_alert",
    "priority": "urgent"
  }
}
```

---

#### **patient_flow_states** (Flow Instance)
```sql
CREATE TABLE patient_flow_states (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id) NOT NULL,
    template_version_id UUID REFERENCES flow_template_versions(id) NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0,

    -- Timing
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,  -- NULL = active, NOT NULL = completed

    -- State Management
    state_data JSONB,  -- Dynamic state storage

    created_at TIMESTAMP,
    updated_at TIMESTAMP,

    INDEX idx_patient_active (patient_id, completed_at)
);
```

**Purpose:** Represents a patient's active or historical flow instance.

**Key Fields:**
- `template_version_id`: Locks flow to specific template version (immutable)
- `current_step`: Current position in flow progression
- `state_data`: Stores runtime state, conditions, transitions

**state_data Structure:**
```json
{
  "requested_flow_type": "initial_15_days",
  "actual_flow_type": "initial_15_days",
  "fallback_used": false,
  "entry_step": 1,
  "last_transition": {
    "timestamp": "2025-10-09T10:30:00Z",
    "from_step": 1,
    "to_step": 2,
    "conditions": [...]
  },
  "failed_transitions": [
    {
      "timestamp": "2025-10-08T15:00:00Z",
      "from_step": 3,
      "to_step": 4,
      "reason": "conditions_not_met",
      "conditions": [...]
    }
  ],
  "paused": false,
  "completion": {
    "timestamp": "2025-10-25T18:00:00Z",
    "final_step": 15,
    "manual_completion": false
  }
}
```

---

### Relationships

```
FlowKind (1) ──┬──> (N) FlowTemplateVersion
               │       ↑
               │       │ (1 is_current per kind)
               │       │
               └──────┘

FlowTemplateVersion (1) ──> (N) PatientFlowState
                                       ↓
                              Patient (1) ──> (N) Message
                                       ↓
                              Patient (1) ──> (N) QuizResponse
```

**Versioning Strategy:**
1. **Template Updates:** Create new `FlowTemplateVersion` with incremented version
2. **Gradual Migration:** Set `is_current=true` on new version
3. **Active Flows:** Continue on locked `template_version_id` (no disruption)
4. **New Flows:** Use current version via `kind_id → is_current=true`
5. **Rollback:** Change `is_current` to previous version

---

## State Machine

### Flow Step Definition

```python
@dataclass
class FlowStep:
    id: int                              # Step identifier (day number)
    name: str                            # "day_1", "welcome_message"
    type: str                            # "message", "quiz"
    content: str                         # Message content
    delay_hours: int = 0                 # Hours to wait before execution
    conditions: List[Dict[str, Any]]     # Transition conditions
    next_step: Optional[int] = None      # Next step ID (None = completed)
    quiz_template: Optional[str] = None  # Quiz template name
```

### State Transition Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    STATE MACHINE FLOW                            │
└─────────────────────────────────────────────────────────────────┘

[Entry Point]
    ↓
┌────────────────┐
│  Step 1 (Day 1)│ ← current_step = 1
│  Welcome Msg   │
└────────────────┘
    ↓ (no conditions)
    ↓ delay_hours = 0
    ↓
[Execute Step 1]
    ↓
    ↓ next_step = 3
    ↓
┌────────────────┐
│  Step 3 (Day 3)│ ← current_step = 3
│  Daily Check   │
└────────────────┘
    ↓ conditions: [
    │   {type: "time_based",
    │    field: "hours_since_start",
    │    operator: "greater_than",
    │    value: 48}
    │ ]
    ↓
[Evaluate Conditions]
    ├──> PASS → Execute Step 3 → next_step = 7
    └──> FAIL → Stay at Step 3, retry later

┌────────────────┐
│  Step 7 (Day 7)│ ← current_step = 7
│  Quiz Trigger  │
└────────────────┘
    ↓ conditions: [
    │   {type: "quiz_response",
    │    field: "symptom_severity",
    │    operator: "greater_than",
    │    value: 3}
    │ ]
    ↓
[Evaluate Quiz Response]
    ├──> severity > 3 → next_step = 8 (follow-up)
    └──> severity ≤ 3 → next_step = 10 (normal)

┌────────────────┐
│ Step 15 (Day 15)│ ← current_step = 15
│ Completion Msg  │
└────────────────┘
    ↓ next_step = None
    ↓
[Flow Completed]
    ↓
    completed_at = NOW()
```

### Condition Types

#### 1. **Quiz Response Conditions**
```python
{
  "type": "quiz_response",
  "field": "symptom_severity",      # Quiz question ID
  "operator": "greater_than",       # equals, not_equals, >, <, contains
  "value": 5                        # Expected value
}
```

**Use Case:** Branch flow based on patient's quiz answers
- High symptom severity → Urgent follow-up
- Low adherence score → Reminder messages

#### 2. **Time-Based Conditions**
```python
{
  "type": "time_based",
  "field": "hours_since_start",     # or "time_of_day"
  "operator": "greater_than",
  "value": 72                       # 3 days
}
```

**Use Case:** Ensure minimum time gaps between steps
- Wait 48 hours before follow-up
- Only send messages during business hours

#### 3. **Patient Data Conditions**
```python
{
  "type": "patient_data",
  "field": "treatment_type",
  "operator": "equals",
  "value": "chemotherapy"
}
```

**Use Case:** Personalize flow based on patient attributes
- Different messages for cancer types
- Age-specific content

#### 4. **Message Count Conditions**
```python
{
  "type": "message_count",
  "field": "total_messages",
  "operator": "greater_equal",
  "value": 5
}
```

**Use Case:** Prevent message flooding
- Limit daily message count
- Require minimum engagement

### Transition Algorithm

```python
def transition(from_step_id: int, context: dict, force: bool = False) -> StateTransition:
    """
    1. Validate current step exists
    2. Get next_step from current FlowStep
    3. If next_step is None → FLOW_COMPLETED
    4. If force=True → Skip condition evaluation
    5. Evaluate all conditions for current step:
       - If ANY condition fails → CONDITION_NOT_MET
       - If ALL conditions pass → SUCCESS
    6. Return StateTransition with result
    """

    # Example evaluation
    current_step = get_step(from_step_id)

    if current_step.next_step is None:
        return StateTransition(result=FLOW_COMPLETED)

    if not force:
        for condition in current_step.conditions:
            passed, message = evaluate_condition(condition, context)
            if not passed:
                return StateTransition(result=CONDITION_NOT_MET, message=message)

    return StateTransition(
        result=SUCCESS,
        from_step=from_step_id,
        to_step=current_step.next_step
    )
```

---

## Template System

### Template Resolution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                  TEMPLATE RESOLUTION                             │
└─────────────────────────────────────────────────────────────────┘

User Request: start_flow(patient_id, flow_type='hormonia_fluxo_mama')
    ↓
[1] Query FlowKind by flow_type
    SELECT * FROM flow_kinds WHERE flow_type = 'hormonia_fluxo_mama'
    ↓
[2] Get Current Version
    SELECT * FROM flow_template_versions
    WHERE kind_id = ? AND is_current = TRUE AND status = 'published'
    ↓
[3] Load Template Data
    template_version.messages → FlowTemplateData
    ↓
    ┌─────────────────────────────────────┐
    │  FlowTemplateData                   │
    │  - flow_type: 'hormonia_fluxo_mama' │
    │  - version: '1.0'                   │
    │  - messages: {1: ..., 3: ..., 7: ...}│
    │  - metadata: {...}                  │
    └─────────────────────────────────────┘
    ↓
[4] Convert to FlowSteps (via .steps property)
    [
      FlowStep(id=1, next_step=3, delay_hours=0),
      FlowStep(id=3, next_step=7, delay_hours=48),
      FlowStep(id=7, next_step=15, delay_hours=96),
      FlowStep(id=15, next_step=None, delay_hours=192)
    ]
    ↓
[5] Create StateMachine
    StateMachine(template=flow_template_data)
    ↓
[6] Validate Flow
    state_machine.validate_flow() → errors[]
    ↓
[7] Create PatientFlowState
    PatientFlowState(
        template_version_id=template_version.id,
        current_step=1  # Entry point
    )


FALLBACK HIERARCHY (if primary template not found):

    'hormonia_fluxo_mama' NOT FOUND
        ↓
    Try: 'hormonia_fluxo_hormonal'
        ↓
    Try: 'hormonia_fluxo_padrao'
        ↓
    Try: Any active template (emergency)
        ↓
    Error: NotFoundError
```

### Template Caching Strategy

```python
# TemplateCache (Redis-backed)

cache_key = f"template:{flow_type}:{version}"
ttl = 3600  # 1 hour

# Read flow
[1] Check Redis: GET cache_key
    ├──> HIT → Return cached FlowTemplateData
    └──> MISS → Load from DB → SET cache_key

# Invalidation
[2] On template publish/update:
    - DEL template:{flow_type}:*
    - Broadcast cache_invalidation event

# Cache warming
[3] On app startup:
    - Load all is_current=true templates
    - Pre-populate Redis cache
```

### Template Versioning Example

```
Timeline:

2025-01-01: Create flow_template_version v1.0
            - kind_id: 'initial_15_days'
            - version: '1.0'
            - is_current: TRUE
            - status: 'published'
            ↓
            Patient A starts flow → locked to v1.0

2025-02-15: Create flow_template_version v1.1 (bug fixes)
            - kind_id: 'initial_15_days'
            - version: '1.1'
            - is_current: TRUE  (v1.0.is_current → FALSE)
            - status: 'published'
            ↓
            Patient B starts flow → locked to v1.1
            Patient A continues on v1.0 (no disruption)

2025-03-01: Create flow_template_version v2.0-beta (major redesign)
            - kind_id: 'initial_15_days'
            - version: '2.0-beta'
            - is_current: FALSE (not production-ready)
            - status: 'draft'
            ↓
            Test with select patients manually

2025-03-20: Promote v2.0-beta → v2.0
            - version: '2.0'
            - is_current: TRUE (v1.1.is_current → FALSE)
            - status: 'published'
            ↓
            All new patients use v2.0
            Patients A, B continue on their locked versions

Database State:
┌──────────────────────────────────────────────────────────┐
│ flow_template_versions                                    │
├──────────────────────────────────────────────────────────┤
│ version │ is_current │ status    │ active_patients       │
│ 1.0     │ FALSE      │ published │ 50 (completed)        │
│ 1.1     │ FALSE      │ published │ 120 (active + done)   │
│ 2.0     │ TRUE       │ published │ 30 (new enrollments)  │
└──────────────────────────────────────────────────────────┘
```

---

## Integration Points

### 1. Message Scheduler Integration

```
FlowEngine._schedule_step(flow_state, step, base_time)
    ↓
[1] Calculate send time
    scheduled_for = base_time + timedelta(hours=step.delay_hours)

[2] Apply AI humanization
    humanized_content = await question_humanizer.humanize_question(
        question=step.content,
        question_type=determine_question_type(step),
        patient=patient,
        context={...}
    )

[3] Create message via MessageService
    message = message_service.schedule_message(
        patient_id=flow_state.patient_id,
        content=humanized_content,
        scheduled_for=scheduled_for,
        metadata={
            'flow_step_id': step.name,
            'ai_humanized': True,
            'original_content': step.content
        }
    )

[4] Schedule Celery task
    send_scheduled_message.apply_async(
        args=[str(message.id)],
        eta=scheduled_for
    )
```

**Message Flow:**
1. **FlowEngine** creates message intent
2. **MessageScheduler** calculates delivery time (timezone-aware)
3. **Celery** schedules async task
4. **MessageSender** delivers via WhatsApp
5. **Webhook** updates delivery status

### 2. Quiz Integration

```
Step Type: "quiz"
    ↓
[1] FlowEngine schedules quiz message
    - Question content humanized
    - QuizSession created

[2] Patient receives WhatsApp message

[3] Patient responds
    ↓
[4] WhatsApp webhook → QuizResponseService
    - Parse response
    - Create QuizResponse record
    - Store in quiz_responses table

[5] Next flow progression (process_patient_day)
    ↓
[6] FlowContext.build_context()
    - Loads recent quiz_responses
    - Adds to context.quiz_responses

[7] StateMachine.transition()
    - Evaluates quiz_response conditions
    - Example: IF symptom_severity > 5 THEN urgent_followup

[8] Conditional branching based on quiz data
```

**Quiz Condition Example:**
```python
# Template definition
step_7 = FlowStep(
    id=7,
    type="quiz",
    quiz_template="symptom_assessment",
    conditions=[
        {
            "type": "quiz_response",
            "field": "severity_score",
            "operator": "greater_than",
            "value": 5
        }
    ],
    next_step=8  # Urgent follow-up if severity > 5
)

# Evaluation
context = {
    "quiz_responses": {
        "severity_score": 7  # Patient reported high severity
    }
}

result, message = evaluate_condition(step_7.conditions[0], context)
# result = True → Transition to step 8 (urgent)
```

### 3. Alert Generation

```
Flow Event → Alert Trigger
    ↓
[1] FlowEngine detects alert condition
    - High quiz severity
    - Missed scheduled message
    - Stale flow (>24h no progress)

[2] Check alert rules in template
    template_version.alerts = {
        "high_severity": {
            "trigger": "quiz_response",
            "condition": {"severity": ">= 8"},
            "action": "create_alert",
            "priority": "urgent"
        }
    }

[3] Create Alert record
    Alert(
        patient_id=patient_id,
        flow_state_id=flow_state.id,
        alert_type="high_symptom_severity",
        severity="urgent",
        message="Patient reported severity 8/10",
        alert_metadata={
            "quiz_response_id": response.id,
            "severity_score": 8
        }
    )

[4] Notify healthcare team
    - Push notification
    - Email to assigned doctor
    - Dashboard alert badge
```

### 4. AI Humanization Pipeline

```
Original Template Content (Portuguese):
"Como você está se sentindo hoje?"
    ↓
[1] Determine question type
    question_type = determine_question_type(step)
    # Returns: 'daily_checkin', 'symptom_tracking', 'mood_assessment'

[2] Check if safe to humanize
    should_humanize_message(content)
    # Skips if contains: 'medicação', 'mg', 'ml', 'consentimento'
    # Returns: True (safe for this content)

[3] Build patient context
    patient_context = PatientContext(
        name="Maria Silva",
        treatment_type="chemotherapy",
        current_day=5,
        recent_messages=[...]
    )

[4] Call AI humanizer
    humanized = await gemini_client.humanize_question(
        question=content,
        question_type='daily_checkin',
        patient_context=patient_context
    )
    # Returns: "Oi Maria, tudo bem? Como você está se sentindo hoje? 😊"

[5] Fallback handling
    if humanization_fails:
        return original_content  # Safe fallback

[6] Store metadata
    message.metadata = {
        'ai_humanized': True,
        'original_content': "Como você está se sentindo hoje?",
        'humanization_method': 'gemini',
        'question_type': 'daily_checkin'
    }
```

**Selective Humanization Rules:**

| Question Type | Humanize? | Reason |
|---------------|-----------|--------|
| daily_checkin | ✅ Yes | Safe, conversational |
| mood_assessment | ✅ Yes | Emotional support |
| symptom_tracking | ✅ Yes | Empathetic phrasing |
| medication_verification | ❌ No | Critical medical info |
| surgery_preparation | ❌ No | Precision required |
| consent_collection | ❌ No | Legal language |

### 5. Event Broadcasting

```
Flow State Change → Broadcast Event
    ↓
[1] FlowEventBroadcaster.broadcast_flow_state_change(
    patient_id=patient_id,
    flow_state=updated_flow_state,
    previous_state=old_state
)
    ↓
[2] Publish to Redis Pub/Sub
    PUBLISH flow_events {
        "event_type": "flow_state_changed",
        "patient_id": "uuid",
        "from_step": 3,
        "to_step": 7,
        "timestamp": "2025-10-09T14:30:00Z"
    }
    ↓
[3] Subscribers receive event
    - Frontend dashboard (real-time updates)
    - Analytics service (metric collection)
    - Audit log service (compliance tracking)

[4] Platform synchronization
    PlatformSyncService.sync_patient_record_update(
        patient_id=patient_id,
        flow_interaction_data={...}
    )
```

---

## Error Handling

### Retry Strategy

```python
@with_db_retry(max_retries=3)
def process_patient_day(patient_id: UUID):
    """
    Retry logic for transient database errors:
    - Connection timeouts
    - Deadlocks
    - Temporary unavailability

    Retry schedule:
    - Attempt 1: Immediate
    - Attempt 2: 1 second delay
    - Attempt 3: 2 second delay
    - Attempt 4: Fail with exception
    """
```

### Error Classification

#### 1. **Validation Errors** (User-correctable)
```python
# Example: Patient already has active flow
raise ValidationError("Patient already has an active flow")

# Handling: Return 400 Bad Request, user can resolve
```

#### 2. **Not Found Errors** (Data missing)
```python
# Example: Template not found
raise NotFoundError(f"Flow template '{flow_type}' not found")

# Handling:
# - Try fallback template hierarchy
# - If all fail, return 404
```

#### 3. **Transient Errors** (Retry-able)
```python
# Examples:
# - Database connection timeout
# - Redis cache miss
# - Celery queue full

# Handling: Automatic retry with exponential backoff
```

#### 4. **Critical Errors** (Alert immediately)
```python
# Examples:
# - AI service unavailable (fallback to original content)
# - Message delivery failure (retry queue)
# - Data corruption detected (quarantine flow)

# Handling:
# 1. Log error with full context
# 2. Send critical alert to monitoring
# 3. Attempt graceful degradation
# 4. Notify on-call team
```

### Fallback Mechanisms

#### Template Fallback
```
Requested: 'hormonia_fluxo_mama'
    ↓ NOT FOUND
Fallback 1: 'hormonia_fluxo_hormonal'
    ↓ NOT FOUND
Fallback 2: 'hormonia_fluxo_padrao'
    ↓ FOUND → Use this

Log Warning: "Using fallback template for hormonia_fluxo_mama"
```

#### AI Humanization Fallback
```
Try: Gemini API humanization (3 retries, 10s timeout each)
    ↓ ALL ATTEMPTS FAILED
Fallback: Return original template content (Portuguese)

Log Error: "AI humanization failed after 3 attempts, using original"
Message still sent → No patient impact
```

#### Message Scheduling Fallback
```
Try: Calculate optimal delivery time
    ↓ TIMEZONE PARSING FAILED
Fallback: UTC + 1 hour from now

Log Warning: "Timezone calculation failed, using 1-hour delay"
```

### Stuck Flow Detection

```python
FlowMonitoringService._count_stale_flows():
    """
    Detect flows stuck for >24 hours:

    SELECT COUNT(*) FROM patient_flow_states
    WHERE completed_at IS NULL
      AND (
        last_message_sent < NOW() - INTERVAL '24 hours'
        OR last_message_sent IS NULL
      )

    If count > threshold:
        Create Alert(severity='high', title='Stale Flows Detected')
        Trigger recovery workflow:
        - Attempt to advance flow
        - Check for condition blockers
        - Manual review queue
    """
```

---

## Performance Considerations

### Database Optimizations

#### 1. **Eager Loading** (N+1 Query Prevention)
```python
# ❌ BAD: N+1 queries
flows = db.query(PatientFlowState).all()
for flow in flows:
    print(flow.patient.name)          # +1 query per flow
    print(flow.template_version.version)  # +1 query per flow

# ✅ GOOD: Eager loading
flows = (
    db.query(PatientFlowState)
    .options(
        joinedload(PatientFlowState.patient).joinedload(Patient.doctor),
        joinedload(PatientFlowState.template_version).joinedload(FlowTemplateVersion.kind)
    )
    .all()
)
# Only 1 query with JOINs

# Performance Impact:
# Before: 100 flows = 1 + 100 + 100 = 201 queries
# After:  100 flows = 1 query
```

#### 2. **Indexes**
```sql
-- Active flow lookup (most common query)
CREATE INDEX idx_patient_active
ON patient_flow_states(patient_id, completed_at)
WHERE completed_at IS NULL;

-- Template resolution
CREATE INDEX idx_template_current
ON flow_template_versions(kind_id, is_current, status)
WHERE is_current = TRUE AND status = 'published';

-- Message scheduling
CREATE INDEX idx_message_scheduled
ON messages(scheduled_for, status)
WHERE status = 'SCHEDULED';
```

#### 3. **JSONB Indexing** (PostgreSQL-specific)
```sql
-- Index for state_data queries
CREATE INDEX idx_flow_state_paused
ON patient_flow_states USING GIN (state_data)
WHERE (state_data->>'paused')::boolean = true;

-- Index for template messages
CREATE INDEX idx_template_messages
ON flow_template_versions USING GIN (messages);
```

### Caching Strategy

```
┌──────────────────────────────────────────────────────────┐
│              MULTI-LEVEL CACHE                            │
└──────────────────────────────────────────────────────────┘

[L1] In-Memory Cache (LRU, Python @lru_cache)
    - Template validation results
    - Flow type enums
    - Static configuration
    TTL: Process lifetime

[L2] Redis Cache (Shared across workers)
    - FlowTemplateData objects
    - Patient context data
    - Message scheduling windows
    TTL: 1 hour, invalidated on template update

[L3] Database (Source of truth)
    - All flow templates
    - Flow states
    - Messages, quizzes
    TTL: Permanent


Cache Read Path:
    Request template 'initial_15_days'
        ↓
    Check L1 (@lru_cache) → MISS
        ↓
    Check L2 (Redis) → HIT
        ↓
    Return cached FlowTemplateData
    Store in L1 for next request

Cache Write Path:
    Template updated in DB
        ↓
    Invalidate L2 (DEL template:initial_15_days:*)
        ↓
    L1 expires naturally (process restart)
```

### Async Task Management

```python
# ❌ ANTI-PATTERN: Nested event loops
def schedule_step():
    asyncio.run(humanize_message())  # Creates new loop
    asyncio.run(send_message())      # Another new loop

# ✅ CORRECT: Single event loop with safe_create_task
async def schedule_step():
    humanization_task = safe_create_task(
        humanize_message(),
        name=f"humanize_{message_id}",
        context={"patient_id": str(patient_id)}
    )

    send_task = safe_create_task(
        send_message(),
        name=f"send_{message_id}",
        context={"scheduled_for": scheduled_time}
    )

    await asyncio.gather(humanization_task, send_task)
```

**Memory Leak Prevention:**
- `EventLoopManager` tracks all created tasks
- `AsyncFlowEngineBase.cleanup()` cancels pending tasks
- Task context metadata for debugging
- Automatic task timeout (prevents orphaned tasks)

### Batch Processing

```python
# Process multiple patients in parallel
async def process_daily_batch(patient_ids: List[UUID]):
    tasks = [
        process_patient_day_async(patient_id)
        for patient_id in patient_ids
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Log failures without stopping entire batch
    for patient_id, result in zip(patient_ids, results):
        if isinstance(result, Exception):
            logger.error(f"Failed to process {patient_id}: {result}")
```

### Monitoring Metrics

```python
FlowMonitoringService.collect_performance_metrics():
    {
        "total_active_flows": 1523,
        "messages_sent_last_hour": 342,
        "average_response_time": 1.2,  # seconds
        "error_rate": 0.02,             # 2%
        "success_rate": 0.98,           # 98%
        "queue_depth": 45,
        "redis_memory_usage": 0.35,    # 35%
        "database_connection_count": 12
    }
```

**Alert Thresholds:**
| Metric | Warning | Critical |
|--------|---------|----------|
| Error Rate | 5% | 15% |
| Avg Response Time | 5s | 15s |
| Queue Depth | 100 | 500 |
| Redis Memory | 80% | 95% |
| Stale Flows | 10 | 50 |

---

## Recommendations

### Architecture Improvements

#### 1. **Consolidate Flow Engines** ⚠️ HIGH PRIORITY
**Problem:** Multiple overlapping flow engine implementations:
- `FlowEngine` (flow_engine.py) - Main execution
- `EnhancedFlowEngine` (enhanced_flow_engine.py) - AI-powered
- `FlowCore` (flow_core.py) - Shared base
- `FlowEngineIntegrationService` (flow.py) - Wrapper

**Impact:** Code duplication, maintenance burden, confusion

**Recommendation:**
```
Create single unified engine:

FlowEngine (consolidated)
├── Core operations (from FlowCore)
├── State machine integration
├── AI humanization (from EnhancedFlowEngine)
└── Template management

Deprecate:
- FlowEngineIntegrationService (move to FlowManagementService)
- EnhancedFlowEngine (merge into FlowEngine)
```

#### 2. **Strengthen Template Validation**
**Current:** Basic validation in TemplateValidator
**Needed:**
- DAG (Directed Acyclic Graph) validation for step chains
- Unreachable step detection
- Infinite loop prevention
- Condition logic validation

```python
class TemplateValidator:
    def validate_step_graph(self, steps: List[FlowStep]) -> List[str]:
        """
        Detect graph issues:
        - Orphaned steps (no incoming edges)
        - Unreachable steps
        - Cycles (infinite loops)
        - Missing next_step references
        """
        errors = []

        # Build adjacency list
        graph = {step.id: step.next_step for step in steps}

        # Check for cycles using DFS
        visited, rec_stack = set(), set()
        if has_cycle(graph, visited, rec_stack):
            errors.append("Flow contains cycle (infinite loop)")

        # Check reachability from entry point
        reachable = get_reachable_nodes(graph, entry_step)
        unreachable = set(graph.keys()) - reachable
        if unreachable:
            errors.append(f"Unreachable steps: {unreachable}")

        return errors
```

#### 3. **Implement Flow Versioning UI**
**Current:** Database-only version management
**Needed:** Admin UI for:
- Template version comparison (diff viewer)
- A/B testing configuration
- Gradual rollout (% of patients)
- Rollback mechanism

#### 4. **Add Distributed Tracing**
**Current:** Logs scattered across services
**Recommendation:** OpenTelemetry integration
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("process_patient_day")
def process_patient_day(patient_id: UUID):
    span = trace.get_current_span()
    span.set_attribute("patient_id", str(patient_id))
    span.set_attribute("flow_type", flow_type)

    # Trace flows through:
    # FlowEngine → StateMachine → MessageScheduler → Celery → WhatsApp
```

#### 5. **Circuit Breaker for AI Services**
**Current:** Retry with fallback
**Recommendation:** Circuit breaker pattern
```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def humanize_with_ai(content: str) -> str:
    """
    Circuit opens after 5 failures:
    - Next 60 seconds: Skip AI, use original content
    - After 60s: Allow 1 test request
    - If success: Close circuit, resume normal operation
    """
    return await gemini_client.humanize(content)
```

### Operational Improvements

#### 1. **Flow Health Dashboard**
Real-time monitoring panel:
- Active flows count (by type, by status)
- Success/error rates (last 1h, 24h, 7d)
- Message delivery latency histogram
- Stale flow alerts
- Template version distribution

#### 2. **Automated Recovery Workflows**
```python
# Stuck Flow Recovery
if flow_state.last_updated > 24 hours ago:
    1. Check if waiting for quiz response
       → Send reminder message
    2. Check if condition blocker
       → Evaluate if condition now met
    3. Check if Celery task failed
       → Reschedule message
    4. Else: Create manual review ticket
```

#### 3. **Performance Baselines**
Establish SLOs (Service Level Objectives):
- Flow progression latency: p50 < 1s, p95 < 3s
- Message scheduling latency: p50 < 500ms, p95 < 2s
- Template resolution: p50 < 100ms, p95 < 300ms
- AI humanization: p50 < 5s, p95 < 10s (with fallback)

#### 4. **Database Migration Strategy**
For production template updates:
```
1. Create new template version (draft)
2. Test with 5% of new enrollments (A/B test)
3. Monitor metrics for 7 days
4. If metrics stable, promote to is_current=true
5. Gradual rollout: 25% → 50% → 100%
6. Archive old version after 30 days
```

---

## Appendix

### Key File Locations

```
backend-hormonia/
├── app/
│   ├── models/
│   │   ├── flow.py                      # Core data models
│   │   └── flow_analytics.py            # FlowMessage, analytics
│   ├── repositories/
│   │   ├── flow.py                      # FlowStateRepository
│   │   ├── flow_template.py             # FlowTemplateRepository
│   │   └── message.py                   # MessageRepository
│   ├── services/
│   │   ├── flow_engine.py               # Main execution engine ⭐
│   │   ├── enhanced_flow_engine.py      # AI-powered engine
│   │   ├── flow_core.py                 # Shared base class
│   │   ├── flow_management.py           # High-level API
│   │   ├── flow_monitoring.py           # Health monitoring
│   │   ├── state_machine.py             # State transitions ⭐
│   │   ├── template_loader.py           # Template management ⭐
│   │   ├── message_scheduler.py         # Message scheduling ⭐
│   │   └── question_humanizer.py        # AI humanization
│   └── api/
│       └── v1/flows.py                  # REST endpoints
└── alembic/versions/
    └── *_flow_versioning.py             # DB migrations
```

### Glossary

| Term | Definition |
|------|------------|
| **FlowKind** | Flow type definition (e.g., 'initial_15_days') |
| **FlowTemplateVersion** | Versioned template with messages/quizzes |
| **PatientFlowState** | Active or historical flow instance for a patient |
| **FlowStep** | Individual step in flow (message/quiz) |
| **StateTransition** | Result of attempting to progress to next step |
| **MessageTemplate** | Day-specific message with personalization hints |
| **Condition** | Rule determining if transition allowed |
| **Humanization** | AI-powered message personalization |
| **Eager Loading** | Preloading related data to prevent N+1 queries |

### References

- **SQLAlchemy ORM:** https://docs.sqlalchemy.org/en/20/
- **Celery Distributed Tasks:** https://docs.celeryq.dev/
- **PostgreSQL JSONB:** https://www.postgresql.org/docs/current/datatype-json.html
- **State Machine Pattern:** https://refactoring.guru/design-patterns/state

---

**END OF DOCUMENT**

Last Review: 2025-10-09
Reviewed By: System Architecture Designer
Next Review: 2025-11-09
