# Quiz Session Lifecycle & State Management

## Session State Machine

### States Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                     QUIZ SESSION STATES                          │
├─────────────────────────────────────────────────────────────────┤
│ 1. started    - Session created, awaiting completion            │
│ 2. completed  - All questions answered, report generated        │
│ 3. cancelled  - Manually cancelled by admin/system              │
│ 4. expired    - Timeout reached without completion              │
└─────────────────────────────────────────────────────────────────┘
```

### QuizFlowState (Enhanced State Tracking)
```
┌─────────────────────────────────────────────────────────────────┐
│                    QUIZ FLOW STATES                              │
├─────────────────────────────────────────────────────────────────┤
│ AWAITING_RESPONSE  - Link sent, waiting for patient to access  │
│ IN_PROGRESS        - Quiz actively being answered               │
│ PAUSED             - Temporarily paused (conversational only)   │
│ COMPLETED          - All responses submitted                    │
│ EXPIRED            - Session timed out                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete State Transition Diagram

```
                           ┌─────────────────┐
                           │   TRIGGERED     │
                           │   (No Session)  │
                           └────────┬────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            ┌───────▼────────┐             ┌───────▼────────┐
            │ Link-Based     │             │ Conversational │
            │ Delivery       │             │ Delivery       │
            └───────┬────────┘             └───────┬────────┘
                    │                               │
                    │                               │
        ┌───────────▼───────────┐       ┌──────────▼─────────┐
        │  CREATE SESSION       │       │  CREATE SESSION    │
        │  status: 'started'    │       │  status: 'started' │
        │  flow: AWAITING_RESP  │       │  flow: IN_PROGRESS │
        └───────────┬───────────┘       └──────────┬─────────┘
                    │                               │
                    │ Link Clicked                  │ Question Sent
                    │                               │
        ┌───────────▼───────────┐       ┌──────────▼─────────┐
        │  PATIENT ACCESSING    │       │  AWAITING RESPONSE │
        │  (Frontend Opens)     │       │  (via WhatsApp)    │
        └───────────┬───────────┘       └──────────┬─────────┘
                    │                               │
                    │ Submit All                    │ Response Received
                    │ Responses                     │
        ┌───────────▼───────────┐       ┌──────────▼─────────┐
        │  VALIDATING           │       │  VALIDATE RESPONSE │
        │  RESPONSES            │       └──────────┬─────────┘
        └───────────┬───────────┘                  │
                    │                               │
                    │ Valid                    ┌────┴────┐
                    │                          │ Valid?  │
        ┌───────────▼───────────┐              └────┬────┘
        │  COMPLETED            │                   │
        │  status: 'completed'  │    ┌─────────────┴──────────┐
        │  flow: COMPLETED      │    │ Invalid                │ Valid
        └───────────┬───────────┘    │                        │
                    │             ┌──▼───────────┐   ┌────────▼────────┐
                    │             │ CLARIFICATION│   │  SAVE RESPONSE  │
                    │             │  REQUESTED   │   │  & NEXT ACTION  │
                    │             └──┬───────────┘   └────────┬────────┘
                    │                │ Retry             │
                    │                └───────────────────┤
                    │                                    │
                    │              ┌────────────────────┴─────────────┐
                    │              │                                  │
                    │      ┌───────▼────────┐              ┌─────────▼────────┐
                    │      │  NEXT QUESTION │              │  LAST QUESTION?  │
                    │      │  (Continue)    │              │  (Complete)      │
                    │      └───────┬────────┘              └─────────┬────────┘
                    │              │                                 │
                    │              └───────────┐         ┌───────────┘
                    │                          │         │
                    │                   ┌──────▼─────────▼──────┐
                    │                   │   QUIZ COMPLETION     │
                    └───────────────────►  status: 'completed'  │
                                        │  flow: COMPLETED      │
                                        └──────────┬────────────┘
                                                   │
                            ┌──────────────────────┴──────────────────────┐
                            │                                             │
                    ┌───────▼────────┐                         ┌──────────▼─────────┐
                    │  REPORT        │                         │  ALERT EVALUATION  │
                    │  GENERATION    │                         │  (if rules met)    │
                    │  (Celery Task) │                         └──────────┬─────────┘
                    └───────┬────────┘                                    │
                            │                                             │
                    ┌───────▼────────┐                         ┌──────────▼─────────┐
                    │  NOTIFY        │                         │  NOTIFICATIONS     │
                    │  COMPLETION    │                         │  - Dashboard       │
                    │  (Patient)     │                         │  - Email (High)    │
                    └────────────────┘                         │  - WhatsApp (Crit) │
                                                               └────────────────────┘
```

---

## Timeout & Expiration States

```
        ┌─────────────────────────────────────────────────────────┐
        │                  TIMEOUT SCENARIOS                      │
        └─────────────────────────────────────────────────────────┘

                    ┌───────────────────┐
                    │  SESSION CREATED  │
                    │  started_at = NOW │
                    │  expiration_date  │
                    │  = NOW + 48h      │
                    └─────────┬─────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
        ┌───────▼────────┐          ┌──────▼──────┐
        │  LINK BASED    │          │ CONVERS.    │
        │  Exp: 48h      │          │ Exp: 24h    │
        └───────┬────────┘          └──────┬──────┘
                │                          │
                │ Time > 48h               │ Time > 24h
                │                          │
        ┌───────▼────────┐          ┌──────▼──────┐
        │  EXPIRED       │          │  EXPIRED    │
        │  (Monitoring)  │          │  (Monitor)  │
        └───────┬────────┘          └──────┬──────┘
                │                          │
                │ Celery Task:            │ Celery Task:
                │ monitor_quiz_links      │ monitor_quiz_links
                │                          │
        ┌───────▼────────────────────┐     │
        │  AUTO-EXPIRE ACTION        │◄────┘
        │  - Set status='expired'    │
        │  - Set completed_at=NOW    │
        │  - Send expiration notice  │
        │  - Update flow state       │
        └────────────────────────────┘
```

---

## Pause & Resume Flow (Conversational Only)

```
        ┌─────────────────────────────────────────────────────────┐
        │              PAUSE/RESUME MECHANISM                      │
        └─────────────────────────────────────────────────────────┘

                    ┌───────────────────┐
                    │  IN_PROGRESS      │
                    │  (Question N)     │
                    └─────────┬─────────┘
                              │
                    Patient sends: "pausar" / "parar"
                              │
                    ┌─────────▼─────────┐
                    │  PAUSE REQUEST    │
                    │  Detected         │
                    └─────────┬─────────┘
                              │
            ConversationalQuizService.pause_quiz_session()
                              │
                    ┌─────────▼─────────┐
                    │  STATE UPDATED    │
                    │  quiz_state:      │
                    │    PAUSED         │
                    │  quiz_paused_at   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  CONFIRMATION     │
                    │  Message Sent     │
                    │  "Quiz pausado"   │
                    └─────────┬─────────┘
                              │
                    Patient sends: "continuar" / "retomar"
                              │
                    ┌─────────▼─────────┐
                    │  RESUME REQUEST   │
                    │  Detected         │
                    └─────────┬─────────┘
                              │
            ConversationalQuizService.resume_quiz_session()
                              │
                    ┌─────────▼─────────┐
                    │  STATE UPDATED    │
                    │  quiz_state:      │
                    │    IN_PROGRESS    │
                    │  quiz_resumed_at  │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  CURRENT QUESTION │
                    │  Re-sent          │
                    └───────────────────┘
```

---

## Fallback Mechanism

```
        ┌─────────────────────────────────────────────────────────┐
        │                 FALLBACK STRATEGY                        │
        └─────────────────────────────────────────────────────────┘

                    ┌───────────────────┐
                    │  LINK TRIGGER     │
                    │  Attempt          │
                    └─────────┬─────────┘
                              │
                    _trigger_quiz_via_link()
                              │
                    ┌─────────▼─────────┐
                    │  LINK CREATION    │
                    │  MonthlyQuizMsg   │
                    │  Integration      │
                    └─────────┬─────────┘
                              │
                        ┌─────┴─────┐
                        │           │
                   SUCCESS      FAILURE
                        │           │
                        │     ┌─────▼─────────────┐
                        │     │  EXCEPTION        │
                        │     │  CAUGHT           │
                        │     └─────┬─────────────┘
                        │           │
                        │     Log warning:
                        │     "Attempting fallback..."
                        │           │
                        │     ┌─────▼─────────────┐
                        │     │  FALLBACK         │
                        │     │  _trigger_quiz_   │
                        │     │  via_whatsapp_    │
                        │     │  with_fallback()  │
                        │     └─────┬─────────────┘
                        │           │
                        │     ┌─────▼─────────────┐
                        │     │  CONVERSATIONAL   │
                        │     │  FLOW STARTED     │
                        │     └─────┬─────────────┘
                        │           │
                        │     ┌─────▼─────────────┐
                        │     │  METADATA UPDATED │
                        │     │  fallback: true   │
                        │     │  fallback_reason  │
                        │     │  fallback_at      │
                        │     └─────┬─────────────┘
                        │           │
                        └───────────┴─────►SUCCESS
```

---

## Error State Handling

### Invalid Response Handling
```
Response Received
     │
     ▼
┌────────────────────┐
│ VALIDATE RESPONSE  │
└────────┬───────────┘
         │
    ┌────┴────┐
    │ Valid?  │
    └────┬────┘
         │
    ┌────┴────┐
    │         │
  Invalid   Valid
    │         │
    ▼         ▼
┌─────────────┐  ┌──────────────┐
│ INCREMENT   │  │ SAVE RESPONSE│
│ RETRY COUNT │  │ CONTINUE     │
└──────┬──────┘  └──────────────┘
       │
    ┌──▼──┐
    │ >3? │
    └──┬──┘
       │
  ┌────┴────┐
  │         │
 Yes       No
  │         │
  ▼         ▼
┌──────────┐ ┌─────────────────┐
│ SKIP     │ │ CLARIFICATION   │
│ QUESTION │ │ MESSAGE         │
└──────────┘ │ "Por favor..."  │
             └─────────────────┘
```

### Session Conflicts
```
API Request: Create Session
     │
     ▼
┌─────────────────────────┐
│ DISTRIBUTED LOCK        │
│ Key: quiz_session_      │
│      {patient_id}       │
│ TTL: 30s                │
└──────────┬──────────────┘
           │
      ┌────▼────┐
      │ LOCKED? │
      └────┬────┘
           │
      ┌────┴────┐
      │         │
    Yes        No
      │         │
      ▼         ▼
┌────────────┐ ┌─────────────────┐
│ PROCEED    │ │ 503 SERVICE     │
│ CHECK      │ │ UNAVAILABLE     │
│ EXISTING   │ │ Retry-After: 5  │
└─────┬──────┘ └─────────────────┘
      │
 ┌────▼────┐
 │ EXISTS? │
 └────┬────┘
      │
 ┌────┴────┐
 │         │
Yes       No
 │         │
 ▼         ▼
┌──────────┐ ┌─────────────┐
│ 409      │ │ CREATE      │
│ CONFLICT │ │ SESSION     │
└──────────┘ └─────────────┘
```

---

## Metadata Evolution

### Session Creation
```json
{
  "monthly_cycle": 1,
  "triggered_by": "flow_system",
  "trigger_date": "2025-12-24T10:00:00Z",
  "flow_state_id": "uuid",
  "delivery_method": "link"
}
```

### After Link Sent
```json
{
  "monthly_cycle": 1,
  "delivery_method": "whatsapp",
  "token_hash": "sha256...",
  "expires_at": "2025-12-26T10:00:00Z",
  "link_status": "active",
  "access_count": 0,
  "delivery_attempts": [
    {
      "timestamp": "2025-12-24T10:00:00Z",
      "action": "send",
      "delivery_method": "whatsapp",
      "status": "sent",
      "message_id": "msg_123"
    }
  ],
  "reminders_scheduled": {
    "first_reminder": "2025-12-25T10:00:00Z",
    "second_reminder": "2025-12-26T04:00:00Z",
    "scheduled_at": "2025-12-24T10:00:00Z"
  }
}
```

### After Fallback
```json
{
  "monthly_cycle": 1,
  "delivery_method": "whatsapp_conversational",
  "quiz_fallback_triggered": true,
  "quiz_fallback_reason": "Link creation failed: timeout",
  "quiz_fallback_at": "2025-12-24T10:05:00Z",
  "original_delivery_method": "link"
}
```

### After Completion
```json
{
  "monthly_cycle": 1,
  "delivery_method": "whatsapp_conversational",
  "quiz_state": "COMPLETED",
  "quiz_started_at": "2025-12-24T10:00:00Z",
  "quiz_completed_at": "2025-12-24T10:15:00Z",
  "total_questions": 5,
  "answered_questions": 5,
  "clarifications_needed": 1,
  "response_time_avg_seconds": 45,
  "report_generated": true,
  "report_id": "uuid",
  "alerts_generated": 2
}
```

---

## Database Constraints Impact

### Unique Active Session Constraint
```sql
CREATE UNIQUE INDEX idx_quiz_session_unique_active
ON quiz_sessions (patient_id, quiz_template_id)
WHERE status = 'started';
```

**Impact**:
- Only ONE active session per patient+template
- Prevents duplicate quiz launches
- Automatic violation → 409 Conflict error
- Must complete/expire before new session

### Status Check Constraint
```sql
ALTER TABLE quiz_sessions
ADD CONSTRAINT ck_quiz_session_completed_timing
CHECK (
  (status = 'completed' AND completed_at IS NOT NULL)
  OR (status != 'completed')
);
```

**Impact**:
- completed_at REQUIRED when status='completed'
- Database enforces completion timestamp
- Application must set both atomically

---

## Concurrent Access Scenarios

### Scenario 1: Duplicate Session Prevention
```
Time    Doctor 1              Database           Doctor 2
──────────────────────────────────────────────────────────
10:00   POST /quiz_sessions
        (patient: A)
                              Lock acquired
                              Check exists: NO
                                                 POST /quiz_sessions
                                                 (patient: A)

                                                 Wait for lock...
10:01   Session created
        Response: 201
                              Lock released
                                                 Lock acquired
                                                 Check exists: YES
                                                 Response: 409
```

### Scenario 2: Concurrent Responses (Conversational)
```
Time    WhatsApp Msg 1        Database           WhatsApp Msg 2
──────────────────────────────────────────────────────────────
10:00   "Resposta A"
        Process started
                              Session locked
                              current_question=0
                                                 "Resposta B"
                                                 Wait for lock...
10:01   Validation OK
        Save response
        Increment question
                              current_question=1
                              Commit & unlock
                                                 Session locked
                                                 current_question=1
                                                 (Msg 2 is for Q1)
10:02                                            Process normally
```

---

## Next: Response Handling & Validation
See `03_RESPONSE_HANDLING_FLOW.md` for detailed response processing and validation logic.
