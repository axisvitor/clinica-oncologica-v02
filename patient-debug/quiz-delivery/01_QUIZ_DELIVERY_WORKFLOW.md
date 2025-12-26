# Quiz Delivery Workflow Documentation

## Overview
The quiz delivery system in Hormonia Backend uses a **dual-mode delivery strategy**:
1. **Link-based delivery** (via WhatsApp links with token authentication)
2. **Conversational delivery** (interactive WhatsApp chat with question-by-question flow)

The system intelligently routes patients to either mode based on configuration and rollout percentage.

---

## Complete Quiz Delivery Flow

### Phase 1: Quiz Triggering

#### Entry Points
1. **Scheduled Triggers** (Celery task)
   - **Task**: `check_quiz_triggers_task` (trigger_tasks.py)
   - **Schedule**: Runs periodically (e.g., daily)
   - **Logic**:
     - Query monthly flows at day 30
     - Check if patient is due for quiz
     - Calculate monthly cycle number
     - Trigger quiz delivery

2. **Manual Triggers** (API endpoint)
   - **Endpoint**: `POST /api/v2/quiz_sessions`
   - **Requires**: patient_id, quiz_template_id
   - **Protection**: Distributed lock prevents duplicate sessions

3. **Flow-Based Triggers** (QuizScheduler)
   - **Service**: `QuizScheduler.should_trigger_quiz()`
   - **Triggers**:
     - Day 15: Initial assessment
     - Day 45: Mid-treatment assessment
     - Every 30 days: Monthly checkups

#### Trigger Logic Flow
```
QuizTriggerService._is_patient_due_for_quiz()
  ↓
Calculate enrollment timeline
  ├─ Days since enrollment
  ├─ Monthly cycle number
  └─ Quiz day calculation
  ↓
Check existing sessions
  ├─ Active sessions?
  └─ Already completed this month?
  ↓
Return (is_due: bool, quiz_info: dict)
```

---

### Phase 2: Delivery Mode Selection

#### Configuration-Based Routing
```python
# Monthly quiz config
config = get_monthly_quiz_config()
use_link = should_use_link_based_quiz(str(patient_id))

# Decision based on rollout percentage (default 30%)
if use_link:
    trigger_quiz_via_link()
else:
    trigger_quiz_via_whatsapp()
```

#### Mode A: Link-Based Delivery

**Flow**:
```
1. QuizTriggerService._trigger_quiz_via_link()
   ↓
2. MonthlyQuizMessageIntegration.send_quiz_link()
   ↓
3. QuizSessionManager.create_quiz_link()
   ├─ SessionFactory.create_session_with_link()
   │   ├─ Generate JWT token
   │   ├─ Create QuizSession (status='started')
   │   └─ Store token hash in session_metadata
   ├─ LinkBuilder.build_link(token)
   └─ DeliveryService.send_quiz_link_notification()
       ├─ MessageFactory.create_monthly_quiz_link_message()
       ├─ UnifiedWhatsAppService.send_message()
       │   ├─ Retry mechanism (3 attempts)
       │   └─ Exponential backoff
       └─ Record delivery attempt
```

**Token Structure**:
```python
JWT Payload:
{
  "patient_id": "uuid",
  "quiz_template_id": "uuid",
  "exp": timestamp,
  "rotation_count": 0
}

Session Metadata:
{
  "delivery_method": "whatsapp",
  "token_hash": "sha256_hash",
  "expires_at": "2025-12-25T12:00:00Z",
  "link_status": "active",
  "access_count": 0,
  "delivery_attempts": [...]
}
```

**Reminder Scheduling**:
```python
_schedule_link_reminders(quiz_session_id, expires_at)
  ├─ First reminder: 24h before expiry
  │   └─ send_quiz_link_reminder_task.apply_async(eta=...)
  └─ Second reminder: 6h before expiry
      └─ send_quiz_link_reminder_task.apply_async(eta=...)
```

#### Mode B: Conversational Delivery

**Flow**:
```
1. QuizTriggerService._trigger_quiz_via_whatsapp()
   ↓
2. Create QuizSession (status='started')
   ├─ Set session metadata:
   │   ├─ monthly_cycle
   │   ├─ triggered_by: "flow_system"
   │   └─ delivery_method: "whatsapp_conversational"
   ├─ Update flow state:
   │   ├─ quiz_session_id
   │   ├─ quiz_state: "IN_PROGRESS"
   │   └─ quiz_started_at
   └─ Send introduction message
       ↓
3. _send_quiz_introduction_message()
   ├─ MessageFactory.create_quiz_introduction()
   ├─ Include first question
   └─ MessageSender.send_message()
```

---

### Phase 3: Quiz Session Lifecycle

#### Session States
```
QuizFlowState (Enum):
  - AWAITING_RESPONSE  # Link sent, waiting for access
  - IN_PROGRESS        # Quiz started (conversational)
  - PAUSED             # Temporarily paused
  - COMPLETED          # All questions answered
  - EXPIRED            # Link expired or timeout
```

#### Session Metadata Tracking
```python
flow_state.state_data = {
    # Common fields
    "quiz_session_id": "uuid",
    "quiz_state": "IN_PROGRESS",
    "quiz_started_at": "2025-12-24T...",
    "quiz_delivery_method": "link" | "whatsapp_conversational",
    "monthly_cycle": 1,

    # Link-specific fields
    "quiz_link_token": "jwt_token",
    "quiz_link_expires_at": "2025-12-26T...",
    "quiz_link_created_at": "2025-12-24T...",
    "quiz_link_access_count": 0,

    # Fallback fields (if link fails)
    "quiz_fallback_triggered": True,
    "quiz_fallback_reason": "error message",
    "quiz_fallback_at": "2025-12-24T..."
}
```

---

### Phase 4: Response Handling

#### Link-Based Response
- Patient clicks link → Opens frontend interface
- Frontend submits all responses at once
- Backend validates and scores
- Completion notification sent

#### Conversational Response Flow
```
Webhook receives message
  ↓
ConversationalQuizService.process_quiz_response()
  ├─ Get active session
  ├─ Validate response against question type
  │   ├─ SCALE: Extract 1-5 number (AI interpretation if needed)
  │   ├─ MULTIPLE_CHOICE: Match option text (AI if unclear)
  │   ├─ YES_NO: Detect affirmative/negative
  │   └─ OPEN_TEXT: Accept any text
  ├─ Save QuizResponse
  ├─ Record response latency metric
  └─ Determine next action
      ├─ Last question? → Complete session
      ├─ Invalid response? → Send clarification
      └─ Valid response? → Send next question
```

#### AI-Assisted Response Interpretation
```python
# For unclear responses
_interpret_scale_response(response_text, question)
  ↓
Gemini prompt:
  "Analyze patient response for scale 1-5
   Question: {question.text}
   Response: {response_text}
   Return number 1-5 or INVALID"
  ↓
Parse AI response
  ├─ Valid number? → Use it
  └─ Invalid? → Request clarification
```

---

### Phase 5: Quiz Completion

#### Completion Flow
```
ConversationalQuizService._complete_quiz_session()
  ├─ QuizSessionService.complete_session()
  │   └─ Set status='completed', completed_at=now
  ├─ Update flow state
  │   ├─ quiz_state: "COMPLETED"
  │   └─ quiz_completed_at
  ├─ Schedule report generation
  │   └─ generate_quiz_report.delay(session_id)
  └─ Send completion message
      ├─ Link-based: MonthlyQuizMessageIntegration.send_completion_confirmation()
      └─ Conversational: MessageFactory.create_quiz_completion()
```

#### Report Generation (Async Task)
```
generate_quiz_report_task(quiz_session_id)
  ├─ Get quiz session and responses
  ├─ QuizResponseEvaluator.evaluate_quiz_session()
  │   ├─ Check alert rules (QUIZ_ALERT_RULES)
  │   ├─ Create alerts for triggered rules
  │   └─ Calculate overall risk score
  ├─ ReportService.generate_quiz_report()
  └─ Notify healthcare providers
      ├─ Dashboard notification (WebSocket)
      ├─ Email (HIGH/CRITICAL alerts)
      └─ WhatsApp (CRITICAL alerts only)
```

---

### Phase 6: Error Handling & Fallbacks

#### Fallback Scenarios

**1. Link Creation Failure**
```
_trigger_quiz_via_link() fails
  ↓
_trigger_quiz_via_whatsapp_with_fallback()
  ├─ Get template
  ├─ Trigger conversational flow
  └─ Update flow state with fallback metadata
```

**2. Delivery Failure**
- **Retry mechanism**: 3 attempts with exponential backoff
- **Tracking**: All attempts recorded in session_metadata
- **Final failure**: Logged and alerted to admin

**3. Session Expiry**
```
monitor_quiz_links_task (hourly)
  ├─ Check all active sessions
  ├─ Calculate session age
  └─ For expired sessions (>24h):
      ├─ Set status='expired'
      ├─ Set completed_at=now
      └─ Send expiration notice
```

**4. Invalid Responses**
- Send clarification message
- Keep session at same question
- Track clarification attempts in metadata

---

## Database Schema Impact

### QuizSession Model
```python
quiz_sessions:
  - id (UUID, PK)
  - patient_id (UUID, FK)
  - quiz_template_id (UUID, FK)
  - status (VARCHAR): 'started' | 'completed' | 'cancelled' | 'expired'
  - current_question (INT): Question index
  - started_at (TIMESTAMP)
  - completed_at (TIMESTAMP, nullable)
  - expiration_date (TIMESTAMP): Auto-set to started_at + 48h
  - session_metadata (JSONB): Token hash, delivery info, etc.

Indexes:
  - idx_quiz_session_unique_active (patient_id, quiz_template_id WHERE status='started')
  - idx_quiz_sessions_patient_status_v2
  - idx_quiz_sessions_completed_at_v2
```

### QuizResponse Model
```python
quiz_responses:
  - id (UUID, PK)
  - quiz_session_id (UUID, FK)
  - patient_id (UUID, FK)
  - question_id (VARCHAR)
  - question_text (TEXT)
  - response_type (VARCHAR)
  - response_value (JSONB)
  - response_metadata (JSONB): AI interpretation, sentiment
  - responded_at (TIMESTAMP)

Constraints:
  - UNIQUE(quiz_session_id, question_id): One response per question
```

---

## Configuration & Rollout

### Monthly Quiz Config
```python
class MonthlyQuizConfig:
    MONTHLY_QUIZ_LINK_PERCENTAGE = 30  # 30% get links
    MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS = 48
    MONTHLY_QUIZ_AUDIT_ENABLED = True
    MONTHLY_QUIZ_ENCRYPTION_ENABLED = True
    MAX_LINK_REGENERATIONS = 2
```

### Rollout Logic
```python
def should_use_link_based_quiz(patient_id: str) -> bool:
    # Hash-based consistent routing
    hash_value = int(hashlib.sha256(patient_id.encode()).hexdigest(), 16)
    percentage = hash_value % 100
    return percentage < config.MONTHLY_QUIZ_LINK_PERCENTAGE
```

---

## Performance Optimizations

### 1. Distributed Locking
- Prevents duplicate session creation
- Uses Redis-based locks with 5s timeout

### 2. Caching
- Template caching for frequently used quizzes
- Response validation rules cached

### 3. Async Processing
- Report generation via Celery
- Notification sending in background
- Metric collection non-blocking

### 4. Database Optimization
- Partial unique index on active sessions
- Covering indexes for analytics queries
- JSONB indexes for metadata searches

---

## Monitoring & Metrics

### Key Metrics Tracked
1. **Response Latency**: Time from question sent to response received
2. **Quiz Completion Rate**: % of started sessions completed
3. **Link Access Rate**: % of links actually accessed
4. **Delivery Success Rate**: Message delivery statistics
5. **Alert Trigger Rate**: % of sessions generating alerts

### Audit Trail
- All link creations logged
- All delivery attempts tracked
- All alert triggers recorded
- Complete session lifecycle tracked

---

## Integration Points

### 1. Patient Flow System
- QuizScheduler checks flow state for trigger timing
- Flow state updated with quiz progress
- Quiz completion triggers flow transitions

### 2. Alert System
- QuizResponseEvaluator generates alerts
- Configurable alert rules (QUIZ_ALERT_RULES)
- Multi-channel notifications

### 3. Messaging System
- UnifiedWhatsAppService for delivery
- MessageFactory for templated messages
- Evolution API integration for WhatsApp

### 4. AI Services
- Gemini for response interpretation
- Sentiment analysis on open text
- Pattern recognition for risk assessment

---

## Security Measures

### 1. Token Security
- JWT with short expiration (48h default)
- SHA256 token hashing in database
- Token rotation on access
- Single-use enforcement possible

### 2. Access Control
- Doctor-patient ownership validation
- Admin bypass for monitoring
- Audit logging for all access

### 3. Data Protection
- JSONB for encrypted sensitive data
- No PII in logs
- Secure token transmission

---

## Next: Session Lifecycle & State Management
See `02_SESSION_LIFECYCLE_DIAGRAM.md` for detailed state transitions and edge cases.
