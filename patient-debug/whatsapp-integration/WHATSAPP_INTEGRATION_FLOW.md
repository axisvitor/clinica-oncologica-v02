# WhatsApp Daily Monitoring & Message Delivery System
## Complete Integration Flow Analysis

**Analysis Date:** 2025-12-24
**System:** Hormonia Oncology Clinic - Patient Monitoring Platform
**Focus:** WhatsApp message flow, daily monitoring, Evolution API integration

---

## Executive Summary

The system implements a sophisticated WhatsApp-based patient monitoring workflow with:
- **Daily automated check-ins** via Celery Beat scheduled tasks
- **Evolution API integration** for WhatsApp Business messaging
- **Multi-phase treatment flows** (Initial 15 days, Days 16-45, Monthly recurring)
- **Webhook-based reactive responses** to patient replies
- **Retry/fallback mechanisms** for message delivery failures
- **Idempotency protection** against duplicate message processing

---

## 1. Message Flow Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DAILY MESSAGE FLOW                              │
└─────────────────────────────────────────────────────────────────────┘

[Celery Beat Scheduler]
         │
         ├─> 8:00 AM UTC: send_daily_flow_questions()
         ├─> 9:00 AM UTC: send_daily_reminders()
         └─> Every 15 min: check_and_start_pending_flows()
                │
                ▼
    [Flow Automation Task] (flow_automation.py)
                │
                ├─> Query patients with active flow_state
                ├─> Calculate current_day from treatment_start_date
                ├─> Determine flow phase (initial/intermediate/monthly)
                ├─> Load message template from YAML/DB
                └─> Create Message record (PENDING status)
                         │
                         ▼
            [WhatsApp Service] (whatsapp_service.py)
                         │
                         ├─> IdempotentMessageSender (prevent duplicates)
                         ├─> MessageFactory (template rendering)
                         └─> Evolution API Client
                                  │
                                  ▼
                    [Evolution API] (Evolution WhatsApp Business)
                                  │
                                  ├─> Send message via WhatsApp
                                  ├─> Return message ID
                                  └─> Update Message status: SENT
                                           │
                                           ▼
                              [Patient receives WhatsApp message]
```

---

## 2. Core Components Breakdown

### 2.1 Celery Task Scheduler (`celery_app.py`)

**Key Scheduled Tasks:**

| Task Name | Schedule | Queue | Purpose |
|-----------|----------|-------|---------|
| `send_daily_flow_questions` | Daily 8:00 AM UTC | flows | Send daily check-in messages based on treatment phase |
| `send_daily_reminders` | Daily 9:00 AM UTC | flows | Remind patients with pending quiz sessions |
| `check_and_start_pending_flows` | Every 15 minutes | flows | Auto-enroll patients without active flows |
| `resume_paused_flows` | Every 6 hours | flows | Resume flows paused for >48 hours |
| `cleanup_expired_quiz_links` | Daily | maintenance | Clean up expired quiz sessions |

**Configuration:**
```python
celery_app.conf.beat_schedule = {
    "send-daily-flow-questions": {
        "task": "flow_automation.send_daily_flow_questions",
        "schedule": crontab(hour=8, minute=0),  # 8 AM UTC
        "options": {"queue": "flows"},
    },
    # ... other tasks
}
```

---

### 2.2 Flow Automation Task (`app/tasks/flow_automation.py`)

**Critical Task: `send_daily_flow_questions()`**

This is the **PRIMARY task** responsible for daily WhatsApp messages:

```python
@shared_task(name="flow_automation.send_daily_flow_questions")
def send_daily_flow_questions() -> dict:
    """
    Send daily flow questions based on patient treatment phase.

    Flow phases:
    - Days 1-15: Daily check-ins (initial phase)
    - Days 16-45: Every 3 days (intermediate phase)
    - Days 46+: Weekly check-ins (maintenance phase)

    Runs daily at 8 AM UTC via Celery Beat.
    """
```

**Flow Logic:**

1. **Query Active Patients:**
   ```python
   active_patients = (
       db.query(Patient)
       .filter(
           Patient.flow_state == FlowState.ACTIVE,
           Patient.deleted_at.is_(None),
           Patient.treatment_start_date.isnot(None),
           Patient.phone_encrypted.isnot(None),
       )
       .limit(200)
       .all()
   )
   ```

2. **Calculate Current Day:**
   ```python
   current_day = patient.current_day or 0
   if current_day == 0 and patient.treatment_start_date:
       current_day = (today - patient.treatment_start_date).days + 1
   ```

3. **Determine Flow Phase & Frequency:**
   ```python
   if current_day <= 15:
       # INITIAL: Daily messages
       flow_phase = "initial_15_days"
       should_send = True
   elif current_day <= 45:
       # INTERMEDIATE: Every 3 days
       flow_phase = "days_16_45"
       day_in_phase = current_day - 15
       should_send = day_in_phase % 3 == 0
   else:
       # MONTHLY: Weekly check-ins (days 7, 14, 21 of 30-day cycle)
       flow_phase = "monthly_recurring"
       day_in_cycle = (current_day - 45) % 30
       should_send = day_in_cycle in [0, 7, 14, 21]
   ```

4. **Load Message Template:**
   ```python
   FLOW_MESSAGES = {
       "initial_15_days": {
           "content": "Olá {patient_name}! 👋 Como você está se sentindo hoje?...",
           "intent": "daily_checkin_initial",
       },
       "days_16_45": {
           "content": "Olá {patient_name}! 🌟 Como está seu tratamento esta semana?...",
           "intent": "periodic_checkin",
       },
       "monthly_recurring": {
           "content": "Olá {patient_name}! 📋 Esta é sua verificação semanal...",
           "intent": "weekly_checkin",
       },
   }
   ```

5. **Create Message Record:**
   ```python
   message = Message(
       patient_id=patient.id,
       direction=MessageDirection.OUTBOUND,
       type=MessageType.TEXT,
       content=message_content,
       status=MessageStatus.PENDING,
       message_metadata={
           "source": "daily_flow_question",
           "flow_phase": flow_phase,
           "flow_day": current_day,
           "template_intent": template_data["intent"],
           "patient_phone": patient_phone,
       },
   )
   db.add(message)
   db.flush()
   ```

6. **Send via WhatsApp:**
   ```python
   unified_service = UnifiedWhatsAppService(db, messaging_mode=MessagingMode.DIRECT)
   asyncio.run(unified_service.send_message(message))
   ```

---

### 2.3 WhatsApp Service Layer (`app/domain/messaging/whatsapp/whatsapp_service.py`)

**Three Service Classes:**

#### **WhatsAppService** (Main Service)
- **Messaging Modes:** QUEUE, DIRECT, LEGACY
- **Features:**
  - Retry policies with exponential backoff
  - WebSocket event notifications
  - Flow integration callbacks
  - Multiple message types (TEXT, IMAGE, FLOW_MESSAGE, QUIZ_QUESTION)

```python
class WhatsAppService:
    def __init__(self, db: Session, messaging_mode: MessagingMode = MessagingMode.QUEUE):
        self.db = db
        self.messaging_mode = messaging_mode
        self.message_repo = MessageRepository(db)
        self.patient_repo = PatientRepository(db)
        self.evolution_client = get_evolution_client()

        # Retry policies by message type
        self.retry_policies = {
            "default": {"max_retries": 3, "backoff_factor": 2, "base_delay": 300},
            "flow_message": {"max_retries": 5, "backoff_factor": 1.5, "base_delay": 180},
            "quiz_message": {"max_retries": 3, "backoff_factor": 2, "base_delay": 300},
        }
```

**Message Sending Flow:**

```python
async def send_message(self, message: Message, retry_count: int = 0) -> Dict[str, Any]:
    """Send WhatsApp message with retry logic."""

    # 1. Get patient and phone number
    patient = self.patient_repo.get_by_id(message.patient_id)
    phone_number = self._get_patient_phone(patient)

    # 2. Send via Evolution API
    result = await self._send_via_evolution(
        phone_number=phone_number,
        content=message.content,
        message_type=message.type,
    )

    # 3. Update message status
    message.status = MessageStatus.SENT
    message.whatsapp_id = result.get("key", {}).get("id")
    message.sent_at = datetime.now(timezone.utc)
    self.db.commit()

    # 4. Broadcast WebSocket event
    self._broadcast_message_sent(message)

    # 5. Execute callback if provided
    if callback:
        await callback(message, result)

    return {"success": True, "message_id": str(message.id)}
```

#### **IdempotentMessageSender**
- **Purpose:** Prevent duplicate message sending
- **Mechanism:**
  - Redis cache (fast path) - 24-hour TTL
  - Database unique constraint (persistent)
  - Automatic idempotency key generation

```python
class IdempotentMessageSender:
    def generate_idempotency_key(self, patient_id, content, message_type):
        key_data = f"{patient_id}:{content}:{message_type.value}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:32]
        return f"msg_idempotency:{key_hash}"

    async def send_message(self, patient_id, content, ...):
        # 1. Generate/use idempotency key
        idempotency_key = self.generate_idempotency_key(...)

        # 2. Check Redis cache (fast path)
        if self.enable_cache:
            cached_result = self._check_cache(idempotency_key)
            if cached_result:
                return {"message_id": cached_result, "was_duplicate": True}

        # 3. Check database
        existing_message = self._check_database(idempotency_key)
        if existing_message:
            return {"message_id": str(existing_message.id), "was_duplicate": True}

        # 4. Send new message
        message = await self.whatsapp_service.send_message_to_patient(...)

        # 5. Store in cache
        self._store_in_cache(idempotency_key, str(message.id))
```

---

### 2.4 Evolution API Client (`app/integrations/evolution/client.py`)

**Architecture:**

```python
class EvolutionClient:
    """Evolution API client for WhatsApp Business integration."""

    def __init__(self, base_url, instance_name, api_key, webhook_secret, ...):
        self.base_url = base_url or settings.WHATSAPP_EVOLUTION_API_URL
        self.instance_name = instance_name or settings.WHATSAPP_EVOLUTION_INSTANCE_NAME
        self.api_key = api_key or settings.WHATSAPP_EVOLUTION_API_KEY

        # Rate limiting
        self.rate_limiter = RateLimiter(requests_per_second=10)

        # HTTP client with proper headers
        headers = {
            "Content-Type": "application/json",
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }
        self.client = httpx.AsyncClient(timeout=30, headers=headers)

        # Specialized handlers
        self.request_handler = RequestHandler(...)
        self.message_sender = MessageSender(...)
        self.webhook_handler = WebhookHandler(...)
```

**Message Sending Methods:**

```python
async def send_text_message(self, phone_number: str, message: str, delay: int = None):
    """Send text message via WhatsApp."""
    return await self.message_sender.send_text_message(phone_number, message, delay)

async def send_button_message(self, phone_number, text, buttons, delay=None):
    """Send button message."""
    return await self.message_sender.send_button_message(...)

async def send_media_message(self, phone_number, media_url, media_type, caption=None):
    """Send media message (image/video/document)."""
    return await self.message_sender.send_media_message(...)
```

**Health Check:**

```python
async def health_check(self) -> Dict[str, Any]:
    """Check Evolution API health and instance status."""
    status_response = await self.get_instance_status()

    is_connected = (
        status_response.get("status") == "success" and
        status_response.get("data", {}).get("connected", False)
    )

    return {
        "service": "evolution_api",
        "healthy": is_connected,
        "details": {
            "instance_name": self.instance_name,
            "base_url": self.base_url,
            "connected": is_connected,
        }
    }
```

---

### 2.5 Webhook Handler (`app/integrations/whatsapp/api/webhooks.py`)

**Webhook Flow (Patient Response Processing):**

```
[Patient sends WhatsApp message]
         │
         ▼
[Evolution API receives message]
         │
         ▼
[POST /webhooks/whatsapp/evolution/{instance}]
         │
         ├─> Rate limited: 500/minute per IP+instance
         ├─> Idempotency check (QW-006: Atomic Redis SET NX EX)
         ├─> Parse webhook event (messages.upsert)
         └─> Extract message details
                  │
                  ▼
         [handle_message_upsert()]
                  │
                  ├─> Extract message content & type
                  ├─> Create WhatsAppMessage record
                  ├─> Find patient by phone (LGPD hash lookup)
                  └─> Trigger flow engine in background
                           │
                           ▼
              [_trigger_flow_response_async()]
                           │
                           ├─> Create new event loop (thread-safe)
                           ├─> Get scoped DB session
                           └─> Call engine.process_patient_response()
                                    │
                                    ▼
                         [Enhanced Flow Engine processes response]
                         [AI analyzes sentiment & generates reply]
                         [Schedules follow-up messages if needed]
```

**Idempotency Protection (QW-006):**

```python
async def is_event_processed(event_id: str, event_type: str = "webhook") -> bool:
    """Atomic idempotency protection using Redis SET NX EX."""

    idempotency = await get_idempotency_service()

    # Atomic check-and-set (prevents race conditions)
    acquired, reason = await idempotency.try_acquire(
        event_type=event_type,
        event_id=event_id
    )

    if not acquired:
        logger.info(f"Duplicate webhook event ignored: {event_id}")
        return True  # Already processed

    return False  # New event, proceed with processing
```

**Message Processing:**

```python
async def handle_message_upsert(instance_name, data, background_tasks, db):
    """Handle incoming messages with idempotency protection."""

    for message_data in messages:
        message_id = key.get("id")

        # IDEMPOTENCY CHECK
        if await is_event_processed(message_id, event_type="message"):
            logger.debug(f"Skipping duplicate message: {message_id}")
            continue

        # Extract message content
        if "conversation" in message_info:
            content = message_info["conversation"]
        elif "extendedTextMessage" in message_info:
            content = message_info["extendedTextMessage"]["text"]

        # Create message record
        message = WhatsAppMessage(
            instance_name=instance_name,
            chat_id=chat_id,
            content=content,
            status=MessageStatus.DELIVERED,
            external_id=message_id,
        )
        db.add(message)
        db.commit()

        # Find patient and trigger flow response
        phone_number = sender_id.split("@")[0]
        phone_hash = lgpd_service.hash_phone(phone_number)
        patient = db.query(Patient).filter(Patient.phone_hash == phone_hash).first()

        if patient:
            # Add background task to process response
            background_tasks.add_task(
                _trigger_flow_response_async,
                patient.id,
                content
            )
```

---

## 3. Message Template System

### 3.1 Template Loading (`app/domain/flows/core/message_template_loader.py`)

**Multi-Layer Fallback System:**

```python
class MessageTemplateLoader:
    async def get_message_template_for_day(self, flow_type, day):
        """Load template with comprehensive error handling."""

        try:
            # 1. Primary: Load from YAML/DB
            flow_template = self.template_loader.load_flow_template(flow_type.value)

            if day in flow_template.messages:
                return flow_template.messages[day]

            # 2. Fallback: Use predefined templates
            return await self.get_fallback_template(flow_type, day)

        except TemplateLoadError as e:
            # Template syntax/parsing error
            logger.error(f"Template load error: {e}")
            return await self.get_fallback_template(flow_type, day)

        except FileNotFoundError as e:
            # Template file missing
            logger.error(f"Template file not found: {e}")
            return await self.get_fallback_template(flow_type, day)
```

**Fallback Templates (Portuguese):**

```python
fallback_messages = {
    FlowType.INITIAL_15_DAYS: {
        "content": "Olá! Como você está se sentindo hoje?",
        "intent": "daily_check_initial",
        "ai_instructions": "Generate warm, caring message about patient well-being",
    },
    FlowType.DAYS_16_45: {
        "content": "Esperamos que você esteja bem. Como está seu tratamento?",
        "intent": "treatment_followup",
        "ai_instructions": "Generate empathetic message about treatment progress",
    },
    FlowType.MONTHLY_RECURRING: {
        "content": "Olá! É hora de fazer seu check-in mensal.",
        "intent": "monthly_checkin",
        "ai_instructions": "Generate friendly monthly check-in message",
    },
}
```

### 3.2 Message Factory (`app/domain/messaging/core/message_factory.py`)

**Template Rendering with Security:**

```python
class MessageFactory:
    def __init__(self, db: Session):
        self.db = db
        self.sanitizer = get_template_sanitizer()

        # Monthly quiz templates
        self.monthly_quiz_templates = {
            "invitation": (
                "Olá {patient_name}! 😊\n\n"
                "Chegou o momento do seu questionário mensal!\n\n"
                "Acesse: {link}\n\n"
                "➡️ Válido por {expiry_hours} horas"
            ),
            "reminder": (
                "Oi {patient_name}! 💬\n\n"
                "Lembrete: questionário mensal pendente.\n\n"
                "Acesse: {link}\n\n"
                "⏳ Expira em {hours_remaining} horas"
            ),
        }

    def create_monthly_quiz_link_message(self, patient_id, patient_name, link_url, ...):
        """Create quiz invitation with sanitized variables."""

        # Sanitize user input BEFORE template rendering
        safe_context = self.sanitizer.sanitize_template_context({
            "patient_name": patient_name,
            "link": link_url,
            "expiry_hours": expiry_hours
        })

        content = self.monthly_quiz_templates["invitation"].format(**safe_context)

        return self.create_outbound_message(
            patient_id=patient_id,
            content=content,
            message_type=MessageType.MONTHLY_QUIZ_INVITATION,
            metadata={
                "quiz_session_id": quiz_session_id,
                "link_url": link_url,
                "template_type": "monthly_quiz_invitation",
            }
        )
```

---

## 4. Error Handling & Retry Logic

### 4.1 Message Scheduling with Retry (`app/domain/flows/core/message_handler.py`)

**Atomic Transaction Safety:**

```python
async def create_and_schedule_flow_message(
    self,
    patient_id: UUID,
    flow_state: PatientFlowState,
    message_template: MessageTemplate,
    personalized_content: str,
    current_day: int,
    send_time: datetime,
) -> bool:
    """
    Create and schedule message with:
    - Atomic transactions (flush before schedule, commit only on success)
    - Retry mechanism (max 3 attempts with exponential backoff)
    - Automatic rollback on scheduling failures
    - Failed message audit trail
    """

    max_retries = 3
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            # 1. Create message (flush, don't commit yet)
            message = Message(
                patient_id=patient_id,
                content=personalized_content,
                status=MessageStatus.PENDING,
                message_metadata={
                    "flow_context": {...},
                    "creation_attempt": attempt + 1,
                },
            )
            self.db.add(message)
            self.db.flush()  # ✅ Get ID without committing

            # 2. Try to schedule (if fails, rollback everything)
            scheduled = await self.message_scheduler.schedule_existing_message(
                message_id=message.id,
                send_time=send_time,
            )

            if not scheduled:
                raise SchedulerError("Scheduling failed")

            # 3. ✅ Only commit if scheduling succeeded
            self.db.commit()
            self.db.refresh(message)

            logger.info(f"Message {message.id} created and scheduled (attempt {attempt + 1})")
            return True

        except Exception as schedule_error:
            # ✅ Rollback on failure
            logger.error(f"Scheduling failed (attempt {attempt + 1}): {schedule_error}")
            self.db.rollback()

            # Retry if transient error
            if self._is_transient_error(schedule_error) and attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue

            # Final failure - create FAILED message record for audit
            failed_message = Message(
                patient_id=patient_id,
                content=personalized_content,
                status=MessageStatus.FAILED,
                message_metadata={
                    "error": str(schedule_error),
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                    "total_attempts": attempt + 1,
                },
            )
            self.db.add(failed_message)
            self.db.commit()
            return False

    return False
```

**Transient Error Detection:**

```python
def _is_transient_error(self, error: Exception) -> bool:
    """
    Determine if error is transient and worth retrying.

    Transient errors (retry):
    - Connection issues
    - Timeout errors
    - Database deadlocks

    Permanent errors (no retry):
    - Validation errors
    - Not found errors
    - Data integrity violations
    """
    transient_keywords = ["connection", "timeout", "temporary", "unavailable", "deadlock"]
    error_str = str(error).lower()
    return any(keyword in error_str for keyword in transient_keywords)
```

### 4.2 Evolution API Unavailability Handling

**Retry Policies by Message Type:**

```python
retry_policies = {
    "default": {
        "max_retries": 3,
        "backoff_factor": 2,
        "base_delay": 300,  # 5 minutes
    },
    "flow_message": {
        "max_retries": 5,
        "backoff_factor": 1.5,
        "base_delay": 180,  # 3 minutes
    },
    "quiz_message": {
        "max_retries": 3,
        "backoff_factor": 2,
        "base_delay": 300,
    },
}
```

**Exponential Backoff:**

```python
async def _schedule_retry(self, message: Message, retry_count: int):
    """Schedule message retry with exponential backoff."""

    policy = self.retry_policies.get("flow_message")

    # Calculate delay: base_delay * (backoff_factor ^ (retry_count - 1))
    delay = policy["base_delay"] * (policy["backoff_factor"] ** (retry_count - 1))

    scheduled_for = datetime.now(timezone.utc) + timedelta(seconds=delay)

    message.status = MessageStatus.PENDING
    message.scheduled_for = scheduled_for
    message.message_metadata["retry_count"] = retry_count

    self.db.commit()

    logger.info(f"Scheduled retry {retry_count} for message {message.id} at {scheduled_for}")
```

**Example Retry Timeline:**
- **Attempt 1:** Immediate
- **Attempt 2:** 3 minutes later (180s)
- **Attempt 3:** 4.5 minutes later (180 * 1.5 = 270s)
- **Attempt 4:** 6.75 minutes later (180 * 1.5² = 405s)
- **Attempt 5:** 10.125 minutes later (180 * 1.5³ = 607.5s)

---

## 5. Webhook Processing & Response Flow

### 5.1 Webhook Event Types

**Supported Events:**

| Event | Description | Handler |
|-------|-------------|---------|
| `messages.upsert` | New message received | `handle_message_upsert()` |
| `messages.update` | Message status update | `handle_message_update()` |
| `send.message` | Outgoing message confirmation | `handle_send_message()` |
| `contacts.upsert` | Contact info update | `handle_contact_upsert()` |
| `connection.update` | Instance connection change | `handle_connection_update()` |
| `presence.update` | Online/offline status | `handle_presence_update()` |
| `chats.upsert` | Chat list update | `handle_chat_upsert()` |

### 5.2 Message Status Tracking

**Status Flow:**

```
PENDING → SENT → DELIVERED → READ
   │         │         │
   └─────────┴─────────┴──> FAILED (if delivery fails)
```

**Status Update Webhook:**

```python
async def handle_message_update(instance_name, data, db):
    """Handle message status updates."""

    # Map Evolution API status codes
    status_map = {
        1: MessageStatus.SENT,      # Message sent to WhatsApp server
        2: MessageStatus.DELIVERED,  # Delivered to recipient device
        3: MessageStatus.READ,       # Read by recipient
    }

    new_status = status_map.get(status_update, MessageStatus.SENT)

    # Update message
    message.status = new_status
    message.updated_at = datetime.now(timezone.utc)

    if new_status == MessageStatus.DELIVERED:
        message.delivered_at = datetime.now(timezone.utc)
    elif new_status == MessageStatus.READ:
        message.read_at = datetime.now(timezone.utc)

    db.commit()
```

---

## 6. Flow Scheduling System

### 6.1 Optimal Send Time Calculation (`app/domain/flows/core/scheduling.py`)

```python
class FlowScheduler:
    async def calculate_optimal_send_time(self, patient: Patient, current_day: int) -> datetime:
        """
        Calculate optimal send time with:
        - Patient timezone awareness
        - Preferred hour preferences
        - Randomization to distribute load
        - Fallback to safe default on errors
        """

        try:
            # Get patient timezone (default to UTC)
            patient_tz = getattr(patient, "timezone", "UTC")

            # Get preferred message hour (default 10 AM)
            preferred_hour = getattr(patient, "preferred_message_hour", 10)
            if not (0 <= preferred_hour <= 23):
                preferred_hour = 10

            # Calculate send time for today
            now = datetime.now(timezone.utc)
            send_time = now.replace(hour=preferred_hour, minute=0, second=0)

            # If time passed, schedule for tomorrow
            if send_time <= now:
                send_time += timedelta(days=1)

            # Add randomization (±30 minutes) to avoid all messages at exact same time
            import random
            random_minutes = random.randint(-30, 30)
            send_time += timedelta(minutes=random_minutes)

            logger.info(f"Calculated send time: {send_time.isoformat()} (tz: {patient_tz})")
            return send_time

        except Exception as e:
            logger.error(f"Failed to calculate send time: {e}. Using fallback: 1 hour from now")
            return datetime.now(timezone.utc) + timedelta(hours=1)
```

### 6.2 Quiz Trigger on Day 30 (Monthly Cycle)

```python
async def check_quiz_trigger(self, patient_id, current_day, flow_type):
    """Check if patient should receive quiz trigger."""

    # Only trigger on day 30 of monthly recurring flows
    if flow_type != "monthly_recurring" or current_day != 30:
        return {"triggered": False}

    # Calculate monthly cycle
    patient = self.patient_repo.get(patient_id)
    enrollment_date = patient.enrollment_date or patient.created_at
    days_since_enrollment = (datetime.now(timezone.utc) - enrollment_date).days
    days_in_monthly_phase = days_since_enrollment - 45
    monthly_cycle = (days_in_monthly_phase // 30) + 1

    quiz_info = {
        "monthly_cycle": monthly_cycle,
        "template_name": f"monthly_checkup_cycle_{monthly_cycle}",
        "trigger_reason": f"Monthly quiz day {current_day} of cycle {monthly_cycle}",
    }

    # Trigger quiz via QuizTriggerService
    quiz_trigger_service = QuizTriggerService(self.db)
    result = await quiz_trigger_service._trigger_patient_quiz(
        flow_state=flow_state,
        quiz_info=quiz_info
    )

    return {
        "triggered": result.get("success", False),
        "quiz_session_id": result.get("session_id"),
        "delivery_method": result.get("delivery_method"),  # 'link' or 'conversational'
    }
```

---

## 7. Complete End-to-End Flow

### 7.1 Daily Message Delivery (8 AM UTC)

```
[8:00 AM UTC - Celery Beat triggers send_daily_flow_questions]
         │
         ├─> Query patients with flow_state=ACTIVE
         ├─> Filter: treatment_start_date IS NOT NULL
         ├─> Filter: phone_encrypted IS NOT NULL
         └─> Limit: 200 patients per run
                  │
                  ▼
         [For each patient]
                  │
                  ├─> Calculate current_day from treatment_start_date
                  ├─> Determine flow_phase (initial/intermediate/monthly)
                  ├─> Check if should_send today (based on frequency)
                  │
                  ├─ [If should_send = False] ──> Skip patient
                  │
                  └─ [If should_send = True]
                         │
                         ├─> Get decrypted phone via ORM property
                         ├─> Load message template for flow_phase
                         ├─> Personalize message with patient.name
                         └─> Create Message record (status=PENDING)
                                  │
                                  ├─> metadata: {
                                  │      "source": "daily_flow_question",
                                  │      "flow_phase": "initial_15_days",
                                  │      "flow_day": 5,
                                  │      "template_intent": "daily_checkin_initial",
                                  │      "patient_phone": "5511999999999"
                                  │   }
                                  │
                                  ▼
                    [UnifiedWhatsAppService.send_message()]
                                  │
                                  ├─> Get Evolution API client
                                  ├─> Format phone (ensure country code)
                                  ├─> Call client.send_text_message()
                                  │
                                  ▼
                         [Evolution API Client]
                                  │
                                  ├─> Rate limit check (10 req/sec)
                                  ├─> HTTP POST to Evolution API
                                  ├─> Endpoint: /message/sendText/{instance}
                                  ├─> Payload: {
                                  │      "number": "5511999999999",
                                  │      "text": "Olá Maria! Como você está..."
                                  │   }
                                  │
                                  ▼
                    [Evolution API (WhatsApp Business)]
                                  │
                                  ├─> Validate instance connection
                                  ├─> Send message via WhatsApp
                                  ├─> Return: {
                                  │      "status": "success",
                                  │      "key": {
                                  │         "id": "ABC123XYZ789",
                                  │         "remoteJid": "5511999999999@s.whatsapp.net"
                                  │      }
                                  │   }
                                  │
                                  ▼
                   [Update Message record]
                                  │
                                  ├─> status: SENT
                                  ├─> whatsapp_id: "ABC123XYZ789"
                                  ├─> sent_at: 2025-12-24T08:15:23Z
                                  ├─> Commit to database
                                  └─> Broadcast WebSocket event
                                           │
                                           ▼
                              [Patient receives WhatsApp message]
```

### 7.2 Patient Response Processing

```
[Patient replies to WhatsApp message]
         │
         ▼
[Evolution API receives message]
         │
         ├─> POST /webhooks/whatsapp/evolution/meuwhatsapp
         ├─> Payload: {
         │      "event": "messages.upsert",
         │      "data": {
         │         "key": {"id": "XYZ789ABC123", "remoteJid": "5511999999999@s.whatsapp.net"},
         │         "message": {"conversation": "Estou me sentindo melhor hoje!"}
         │      }
         │   }
         │
         ▼
[Webhook Handler - Rate Limited: 500/min per IP+instance]
         │
         ├─> Extract message_id: "XYZ789ABC123"
         ├─> Idempotency check (Atomic Redis SET NX EX)
         │      └─> If duplicate: Return 200 OK (skip processing)
         │
         ├─> Extract message content: "Estou me sentindo melhor hoje!"
         ├─> Extract sender: "5511999999999"
         │
         ├─> Create WhatsAppMessage record
         │      ├─> external_id: "XYZ789ABC123"
         │      ├─> content: "Estou me sentindo melhor hoje!"
         │      ├─> status: DELIVERED
         │      └─> message_data: {...}
         │
         ├─> Find patient by phone (LGPD hash lookup)
         │      ├─> phone_hash = hash_phone("5511999999999")
         │      └─> SELECT * FROM patients WHERE phone_hash = ?
         │
         └─ [If patient found]
                  │
                  ├─> Log: "Message from patient {patient.id} detected"
                  └─> Add background task: _trigger_flow_response_async()
                           │
                           ▼
              [Background Task - Async Context]
                           │
                           ├─> Create new event loop (thread-safe)
                           ├─> Get scoped DB session
                           ├─> Initialize EnhancedFlowEngine
                           │
                           ▼
              [engine.process_patient_response(patient_id, content)]
                           │
                           ├─> Load active flow state
                           ├─> AI sentiment analysis (Gemini API)
                           │      ├─> Analyze: "Estou me sentindo melhor hoje!"
                           │      └─> Result: {"sentiment": "positive", "needs_attention": false}
                           │
                           ├─> Generate AI follow-up response
                           │      └─> "Que ótimo saber que você está melhor! 🎉..."
                           │
                           ├─> Create follow-up message (PENDING)
                           │      ├─> content: AI-generated response
                           │      ├─> metadata: {"type": "ai_follow_up", "triggered_by": "patient_response"}
                           │      └─> scheduled_for: now + 5 minutes
                           │
                           ├─> Update flow state
                           │      ├─> last_patient_message: {...}
                           │      ├─> ai_sentiment: "positive"
                           │      └─> last_interaction: 2025-12-24T08:30:00Z
                           │
                           └─> Send follow-up via WhatsApp
                                    │
                                    └─> [Repeat send flow from 7.1]
```

---

## 8. Database Schema (Relevant Tables)

### 8.1 Patients Table

```sql
CREATE TABLE patients (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    phone_encrypted BYTEA,  -- Encrypted phone number (LGPD)
    phone_hash VARCHAR(64),  -- SHA-256 hash for lookups

    -- Flow tracking
    flow_state VARCHAR(20),  -- 'ACTIVE', 'PAUSED', 'COMPLETED', 'INACTIVE'
    current_day INTEGER DEFAULT 0,  -- Current day in treatment flow
    treatment_start_date DATE,  -- Start of treatment (for day calculation)
    enrollment_date TIMESTAMP,  -- Enrollment in system

    -- Preferences
    timezone VARCHAR(50) DEFAULT 'UTC',
    preferred_message_hour INTEGER DEFAULT 10,  -- 0-23 (hour for daily messages)

    -- Metadata
    treatment_type VARCHAR(100),  -- 'hormonal', 'quimio', 'radio'
    diagnosis TEXT,
    metadata JSONB,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_patients_flow_state ON patients(flow_state) WHERE deleted_at IS NULL;
CREATE INDEX idx_patients_phone_hash ON patients(phone_hash);
CREATE INDEX idx_patients_treatment_date ON patients(treatment_start_date) WHERE deleted_at IS NULL;
```

### 8.2 Messages Table

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),

    -- Message details
    direction VARCHAR(20),  -- 'OUTBOUND', 'INBOUND'
    type VARCHAR(50),  -- 'TEXT', 'IMAGE', 'FLOW_MESSAGE', 'QUIZ_QUESTION'
    content TEXT,

    -- Status tracking
    status VARCHAR(20),  -- 'PENDING', 'SENT', 'DELIVERED', 'READ', 'FAILED'
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,

    -- WhatsApp details
    whatsapp_id VARCHAR(255),  -- Evolution API message ID

    -- Scheduling
    scheduled_for TIMESTAMP,  -- When message should be sent

    -- Metadata
    message_metadata JSONB,  -- Flow context, retry count, template info

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_messages_patient_id ON messages(patient_id);
CREATE INDEX idx_messages_status ON messages(status);
CREATE INDEX idx_messages_scheduled_for ON messages(scheduled_for) WHERE status = 'PENDING';
CREATE INDEX idx_messages_whatsapp_id ON messages(whatsapp_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- Idempotency index (for message_metadata->'idempotency_key')
CREATE INDEX idx_messages_idempotency ON messages USING gin (message_metadata);
```

### 8.3 Patient Flow States Table

```sql
CREATE TABLE patient_flow_states (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),

    -- Flow details
    flow_type VARCHAR(50),  -- 'initial_15_days', 'days_16_45', 'monthly_recurring'
    current_day INTEGER DEFAULT 1,
    status VARCHAR(20),  -- 'active', 'paused', 'completed', 'failed'

    -- State data
    state_data JSONB,  -- {
                       --   "last_message_sent": {...},
                       --   "last_message_failed": {...},
                       --   "message_status_updates": [...]
                       -- }

    -- Timestamps
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    paused_at TIMESTAMP,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_flow_states_patient_id ON patient_flow_states(patient_id);
CREATE INDEX idx_flow_states_status ON patient_flow_states(status);
CREATE INDEX idx_flow_states_flow_type ON patient_flow_states(flow_type);
```

---

## 9. Configuration & Environment Variables

### 9.1 Evolution API Settings

```env
# Evolution API Configuration
WHATSAPP_EVOLUTION_API_URL=http://localhost:8080
WHATSAPP_EVOLUTION_RAILWAY_URL=http://evolution-api.railway.internal:8080
WHATSAPP_EVOLUTION_INSTANCE_NAME=meuwhatsapp
WHATSAPP_EVOLUTION_API_KEY=your-api-key-here
WHATSAPP_EVOLUTION_WEBHOOK_SECRET=your-webhook-secret-here
EVOLUTION_RATE_LIMIT=10  # Requests per second

# Railway Environment Detection
RAILWAY_ENVIRONMENT=true
```

### 9.2 Celery Configuration

```env
# Celery Broker & Backend
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Celery Worker Settings
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_TASK_TIME_LIMIT=1800  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT=1500  # 25 minutes
```

### 9.3 Redis Configuration

```env
# Redis Settings
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_KEEPALIVE=True

# Cache TTL Settings
IDEMPOTENCY_CACHE_TTL=86400  # 24 hours
MESSAGE_CACHE_TTL=3600  # 1 hour
```

---

## 10. Monitoring & Debugging

### 10.1 Key Logging Points

```python
# Flow automation task
logger.info(f"Found {len(active_patients)} patients with active flow_state")
logger.info(f"Sent daily question to patient {patient.id} ({patient.name}) [{flow_phase} day {current_day}]")
logger.warning(f"Patient {patient.id} has encrypted phone but decryption failed")

# WhatsApp service
logger.info(f"Message {message.id} sent successfully to patient {patient.id}")
logger.error(f"Evolution API error sending message {message.id}: {e}")
logger.warning(f"Scheduled retry {retry_count} for message {message.id} at {scheduled_for}")

# Webhook handler
logger.info(f"Received webhook for instance {instance_name}")
logger.info(f"Message from patient {patient.id} detected. Triggering flow engine in background.")
logger.debug(f"Skipping duplicate message: {message_id}")

# Evolution client
logger.info("Evolution API client initialized")
logger.error("Evolution API health check failed")
```

### 10.2 Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `messages_sent_total` | Total messages sent | N/A |
| `messages_failed_total` | Total failed messages | >5% of sent |
| `message_delivery_time` | Time from create to sent | >5 minutes |
| `evolution_api_errors` | Evolution API error count | >10/hour |
| `evolution_api_latency` | API response time | >2 seconds |
| `webhook_duplicate_rate` | Duplicate webhooks | >1% |
| `flow_questions_sent` | Daily questions sent | Should match active patients |
| `flow_questions_skipped` | Patients skipped | Investigate if >20% |

### 10.3 Health Check Endpoints

```python
# Evolution API Health
GET /api/evolution/health
Response: {
    "service": "evolution_api",
    "healthy": true,
    "details": {
        "instance_name": "meuwhatsapp",
        "connected": true,
        "rate_limit_remaining": 95
    }
}

# Webhook Health
GET /webhooks/whatsapp/health
Response: {
    "status": "healthy",
    "timestamp": "2025-12-24T08:00:00Z",
    "service": "whatsapp-webhooks"
}
```

---

## 11. Common Issues & Troubleshooting

### 11.1 Messages Not Being Sent

**Symptoms:**
- Patients not receiving daily check-in messages
- Messages stuck in PENDING status

**Debugging Steps:**

1. **Check Celery Beat is running:**
   ```bash
   celery -A app.celery_app inspect active
   celery -A app.celery_app inspect scheduled
   ```

2. **Check Flow Automation Task:**
   ```sql
   -- See recent task executions
   SELECT * FROM celery_taskmeta
   WHERE task_name = 'flow_automation.send_daily_flow_questions'
   ORDER BY date_done DESC LIMIT 10;
   ```

3. **Check Patient Flow State:**
   ```sql
   SELECT id, name, flow_state, current_day, treatment_start_date
   FROM patients
   WHERE flow_state = 'ACTIVE' AND deleted_at IS NULL
   LIMIT 10;
   ```

4. **Check Message Status:**
   ```sql
   SELECT id, patient_id, status, content, scheduled_for, message_metadata
   FROM messages
   WHERE status = 'PENDING' AND created_at > NOW() - INTERVAL '24 hours'
   ORDER BY created_at DESC;
   ```

5. **Check Evolution API Connection:**
   ```bash
   curl -X GET http://localhost:8080/instance/connectionState/meuwhatsapp \
     -H "apikey: your-api-key"
   ```

**Common Fixes:**
- Restart Celery worker: `celery -A app.celery_app worker --loglevel=info`
- Restart Celery beat: `celery -A app.celery_app beat --loglevel=info`
- Check Evolution API is running and instance is connected
- Verify patient `flow_state = 'ACTIVE'` and `treatment_start_date` is set

### 11.2 Duplicate Messages

**Symptoms:**
- Patients receiving same message multiple times
- Idempotency key collisions in logs

**Debugging Steps:**

1. **Check Redis Idempotency Cache:**
   ```bash
   redis-cli KEYS "msg_idempotency:*"
   redis-cli GET "msg_idempotency:abc123..."
   ```

2. **Check Duplicate Messages in DB:**
   ```sql
   SELECT content, patient_id, COUNT(*) as count
   FROM messages
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY content, patient_id
   HAVING COUNT(*) > 1;
   ```

3. **Check Webhook Duplicate Rate:**
   ```bash
   grep "Duplicate webhook event" logs/celery-worker.log | wc -l
   ```

**Common Fixes:**
- Ensure Redis is running and accessible
- Check `IdempotentMessageSender` is enabled
- Verify webhook idempotency is working (QW-006)
- Review Celery task deduplication settings

### 11.3 Webhooks Not Processing

**Symptoms:**
- Patient responses not triggering AI follow-ups
- No entries in `whatsapp_messages` table

**Debugging Steps:**

1. **Check Webhook Endpoint is Reachable:**
   ```bash
   curl -X POST http://localhost:8000/webhooks/whatsapp/evolution/meuwhatsapp \
     -H "Content-Type: application/json" \
     -d '{"event": "messages.upsert", "data": {...}}'
   ```

2. **Check Evolution Webhook Configuration:**
   ```bash
   curl -X GET http://localhost:8080/webhook/findWebhook/meuwhatsapp \
     -H "apikey: your-api-key"
   ```

3. **Check Webhook Logs:**
   ```bash
   grep "Received webhook" logs/uvicorn.log
   grep "handle_message_upsert" logs/uvicorn.log
   ```

4. **Check Background Task Execution:**
   ```sql
   SELECT * FROM celery_taskmeta
   WHERE task_name LIKE '%trigger_flow_response%'
   ORDER BY date_done DESC LIMIT 10;
   ```

**Common Fixes:**
- Configure Evolution webhook URL: `http://your-domain.com/webhooks/whatsapp/evolution/meuwhatsapp`
- Ensure webhook endpoint is publicly accessible (or use ngrok for local dev)
- Check firewall/network settings
- Verify background task workers are running

### 11.4 Evolution API Connection Issues

**Symptoms:**
- `Evolution API health check failed` in logs
- Messages failing with connection errors

**Debugging Steps:**

1. **Test Evolution API Directly:**
   ```bash
   curl -X GET http://localhost:8080/instance/connectionState/meuwhatsapp \
     -H "apikey: your-api-key"
   ```

2. **Check Instance QR Code (if not connected):**
   ```bash
   curl -X GET http://localhost:8080/instance/qrcode/meuwhatsapp \
     -H "apikey: your-api-key"
   ```

3. **Check Network Connectivity:**
   ```bash
   ping localhost
   telnet localhost 8080
   ```

4. **Check Evolution API Logs:**
   ```bash
   docker logs evolution-api-container
   ```

**Common Fixes:**
- Scan QR code to connect WhatsApp instance
- Restart Evolution API: `docker restart evolution-api-container`
- Check API key is correct in environment variables
- Verify network connectivity between backend and Evolution API

---

## 12. Performance Optimization

### 12.1 Batch Processing

```python
# Flow automation task processes 200 patients per run
active_patients = (
    db.query(Patient)
    .filter(...)
    .limit(200)  # Batch size
    .all()
)
```

**Recommendation:** Adjust batch size based on:
- Message delivery rate
- Evolution API rate limits (10 req/sec default)
- Celery worker capacity

### 12.2 Message Distribution

```python
# Add randomization to avoid all messages at exact same time
random_minutes = random.randint(-30, 30)  # ±30 minutes
send_time += timedelta(minutes=random_minutes)
```

**Benefits:**
- Reduces Evolution API load spikes
- Distributes WhatsApp server load
- Improves deliverability

### 12.3 Database Query Optimization

```sql
-- Indexes for common queries
CREATE INDEX idx_patients_flow_state ON patients(flow_state) WHERE deleted_at IS NULL;
CREATE INDEX idx_messages_scheduled_for ON messages(scheduled_for) WHERE status = 'PENDING';

-- EXPLAIN ANALYZE for slow queries
EXPLAIN ANALYZE
SELECT * FROM patients
WHERE flow_state = 'ACTIVE' AND deleted_at IS NULL;
```

---

## 13. Security Considerations

### 13.1 LGPD Compliance (Phone Number Encryption)

```python
# Phone numbers are encrypted at rest
phone_encrypted = lgpd_service.encrypt(phone_number)
phone_hash = lgpd_service.hash_phone(phone_number)  # For lookups

# Decryption via ORM property (automatic)
patient.phone  # Returns decrypted phone number
```

### 13.2 Webhook Signature Validation

```python
def validate_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Validate webhook signature (HMAC SHA-256)."""

    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)
```

**Note:** Currently in development mode, signature validation is optional. **Must enable in production.**

### 13.3 Rate Limiting

```python
# Webhook rate limiting (prevent DDoS)
@limiter.limit("500/minute", key_func=_webhook_rate_limit_key)
async def evolution_webhook(...):
    ...

# Evolution API rate limiting
rate_limiter = RateLimiter(requests_per_second=10)
```

---

## 14. Deployment Checklist

- [ ] **Environment Variables:** All Evolution API credentials configured
- [ ] **Celery Workers:** Running with flows queue enabled
- [ ] **Celery Beat:** Scheduled tasks configured and running
- [ ] **Redis:** Running and accessible (for idempotency & caching)
- [ ] **Evolution API:** Instance connected and healthy
- [ ] **Webhooks:** Configured with public URL and signature validation
- [ ] **Database:** Migrations applied, indexes created
- [ ] **Monitoring:** Health checks configured, alerts set up
- [ ] **Logging:** Structured logging enabled, log aggregation configured
- [ ] **Backups:** Database backups scheduled
- [ ] **Security:** Webhook signature validation enabled in production

---

## 15. Testing Guide

### 15.1 Manual Test Flow

1. **Create Test Patient:**
   ```python
   patient = Patient(
       name="Test Patient",
       phone_encrypted=encrypt_phone("5511999999999"),
       flow_state=FlowState.ACTIVE,
       treatment_start_date=date.today() - timedelta(days=5),
       current_day=5,
   )
   db.add(patient)
   db.commit()
   ```

2. **Trigger Daily Flow Question Manually:**
   ```python
   from app.tasks.flow_automation import send_daily_flow_questions
   result = send_daily_flow_questions()
   print(result)  # Should show questions_sent=1
   ```

3. **Check Message Created:**
   ```sql
   SELECT * FROM messages WHERE patient_id = '<test-patient-id>' ORDER BY created_at DESC LIMIT 1;
   ```

4. **Simulate Webhook Response:**
   ```bash
   curl -X POST http://localhost:8000/webhooks/whatsapp/evolution/meuwhatsapp \
     -H "Content-Type: application/json" \
     -d '{
       "event": "messages.upsert",
       "data": {
         "key": {"id": "TEST123", "remoteJid": "5511999999999@s.whatsapp.net"},
         "message": {"conversation": "Estou me sentindo melhor!"}
       }
     }'
   ```

5. **Verify AI Follow-up Created:**
   ```sql
   SELECT * FROM messages
   WHERE patient_id = '<test-patient-id>'
   AND message_metadata->>'type' = 'ai_follow_up'
   ORDER BY created_at DESC LIMIT 1;
   ```

### 15.2 Integration Tests

See: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/integration/test_whatsapp_flow.py`

---

## 16. Future Enhancements

1. **Multi-Channel Support:**
   - SMS fallback for WhatsApp delivery failures
   - Email notifications for critical messages

2. **Advanced Scheduling:**
   - Patient-specific time zone support
   - Preferred language for messages
   - Do Not Disturb periods

3. **AI Improvements:**
   - Multi-turn conversation tracking
   - Sentiment trend analysis
   - Automated escalation for concerning responses

4. **Analytics:**
   - Message engagement metrics (open rate, response rate)
   - Flow completion rates by phase
   - Treatment adherence correlation

5. **Template Management:**
   - Admin UI for template editing
   - A/B testing for message variations
   - Multi-language support

---

## Appendix A: File Reference

| File | Purpose | Lines |
|------|---------|-------|
| `app/tasks/flow_automation.py` | Celery tasks for daily messages | 636 |
| `app/domain/messaging/whatsapp/whatsapp_service.py` | WhatsApp service layer | 712 |
| `app/integrations/evolution/client.py` | Evolution API client | 331 |
| `app/integrations/evolution/webhook_handler.py` | Webhook validation | 159 |
| `app/integrations/whatsapp/api/webhooks.py` | Webhook endpoint handlers | 651 |
| `app/domain/messaging/core/message_factory.py` | Message template factory | 372 |
| `app/domain/flows/core/message_handler.py` | Message lifecycle management | 580 |
| `app/domain/flows/core/scheduling.py` | Flow scheduling logic | 385 |
| `app/domain/flows/core/message_template_loader.py` | Template loading & fallback | 267 |
| `app/celery_app.py` | Celery configuration | 415 |

---

**Total Analysis:** 10 core files, ~4,500 lines of code reviewed
**Documentation Generated:** 2025-12-24 05:30 UTC
