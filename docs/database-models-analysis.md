# Database Models Analysis - Quiz, Flow, and Onboarding Tables

**Project:** Hormonia - Oncology Clinic Management System
**Analysis Date:** 2025-12-22
**Analyzed Files:**
- `/backend-hormonia/app/models/quiz.py`
- `/backend-hormonia/app/models/flow.py`
- `/backend-hormonia/app/models/flow_analytics.py`
- `/backend-hormonia/app/models/patient_onboarding_saga.py`
- `/backend-hormonia/app/models/patient_summary.py`

---

## Executive Summary

This analysis documents the database schema for the Hormonia patient management system, focusing on quiz assessments, conversation flows, onboarding processes, and patient summaries. The system implements a sophisticated architecture for:

- **Medical Assessments:** Versioned quiz templates with session tracking
- **Conversation Management:** Flow-based patient interactions with state tracking
- **Distributed Transactions:** Saga pattern for reliable patient onboarding
- **Analytics & Reporting:** Performance metrics and AI-generated summaries

---

## 1. Quiz System Tables

### 1.1 `quiz_templates`

**Purpose:** Master template storage for medical assessments and questionnaires.

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (inherited from BaseModel) |
| `name` | String(255) | Template name (required) |
| `version` | String(50) | Version identifier (required) |
| `questions` | JSONB | Array of question objects |
| `is_active` | Boolean | Active status flag |
| `description` | Text | Template description |
| `category` | String(100) | Quiz category (indexed) |
| `passing_score` | Integer | Minimum score to pass |
| `time_limit_minutes` | Integer | Time limit for completion |
| `randomize_questions` | Boolean | Question randomization flag |
| `tags` | JSONB | Categorization tags (array) |

**Relationships:**
- **1:N** → `quiz_responses`: All responses using this template
- **1:N** → `quiz_sessions`: All sessions using this template

**Constraints:**
- Unique: `(name, version)` - Ensures version control
- Check: `name` and `version` not empty
- Check: `questions` must be valid JSON structure
- Index: `category`, `is_active` for filtering

**Business Workflow Usage:**
1. Doctors create quiz templates with medical questions
2. Templates versioned for audit trail and iterative improvements
3. Active templates available for patient assessments
4. Categories enable organization by medical specialty

---

### 1.2 `quiz_sessions`

**Purpose:** Track individual patient quiz-taking sessions with state management.

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `patient_id` | UUID | FK to patients (CASCADE delete) |
| `quiz_template_id` | UUID | FK to quiz_templates (RESTRICT) |
| `status` | String(50) | started \| completed \| cancelled \| expired |
| `current_question` | Integer | Current question index (0-based) |
| `total_questions` | Integer | Total questions in session |
| `answered_questions` | Integer | Number of answered questions |
| `score` | Numeric(5,2) | Final score (0.00-999.99) |
| `max_score` | Numeric(5,2) | Maximum possible score |
| `passed` | Boolean | Pass/fail result |
| `started_at` | DateTime(TZ) | Session start timestamp |
| `completed_at` | DateTime(TZ) | Session completion timestamp |
| `expiration_date` | DateTime(TZ) | Auto-calculated (started_at + 48h) |
| `time_spent_seconds` | Integer | Total time spent |
| `session_metadata` | JSONB | Additional session data |

**Relationships:**
- **N:1** → `patients`: Patient taking the quiz
- **N:1** → `quiz_templates`: Template being used
- **1:N** → `quiz_responses`: All responses in this session

**Constraints:**
- Check: `current_question >= 0`
- Check: `score >= 0`
- Check: `status` in valid set
- Check: Completed sessions must have `completed_at`
- **Partial Unique Index:** Only one `started` session per patient+template

**Indexes:**
- `patient_id`, `quiz_template_id`, `status`
- Composite: `(patient_id, status)`, `(quiz_template_id, status)`
- `created_at`, `completed_at` for time-based queries

**Business Workflow Usage:**
1. Patient starts quiz → session created with `status='started'`
2. Progress tracked via `current_question` and `answered_questions`
3. Auto-expiration after 48 hours if not completed
4. Only one active session per patient+template (enforced by partial unique index)
5. Session state persisted for resume capability

**Properties & Methods:**
- `current_question_index`: Backward-compatible alias
- `is_completed`: Boolean property mapped to status
- `is_expired`: Checks expiration logic
- `set_expiration_date()`: Calculates 48-hour expiration

---

### 1.3 `quiz_responses`

**Purpose:** Store individual patient answers to quiz questions.

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `patient_id` | UUID | FK to patients (CASCADE delete) |
| `quiz_template_id` | UUID | FK to quiz_templates (RESTRICT) |
| `quiz_session_id` | UUID | FK to quiz_sessions (CASCADE delete) |
| `question_id` | String(100) | Question identifier |
| `question_text` | Text | Full question text (snapshot) |
| `response_type` | String(50) | Type: multiple_choice \| open_text \| scale \| boolean \| rating \| yes_no \| number \| date \| single_choice |
| `response_value` | JSONB | Structured response data |
| `response_metadata` | JSONB | Sentiment analysis, entities, etc. |
| `other_text` | Text | Custom "other" option text |
| `responded_at` | DateTime(TZ) | Response timestamp |

**Relationships:**
- **N:1** → `patients`: Patient who responded
- **N:1** → `quiz_templates`: Template being answered
- **N:1** → `quiz_sessions`: Session context

**Constraints:**
- **Unique:** `(quiz_session_id, question_id)` - One response per question per session
- Check: `question_id`, `question_text`, `response_value` not empty
- Check: `response_type` in valid set

**Indexes:**
- `patient_id`, `quiz_template_id`, `quiz_session_id`, `responded_at`
- Covering index: `(quiz_template_id, question_id, response_value, responded_at)` for analytics
- Composite: `(patient_id, quiz_template_id, responded_at)` for patient history

**Response Value Structure:**
```json
{
  // Plain text
  "response text" or {"text": "response text"},

  // Multiple choice
  ["option1", "option2"],

  // Scale
  {"value": 7, "type": "scale"},

  // Boolean
  {"text": "yes", "boolean": true}
}
```

**Business Workflow Usage:**
1. Patient answers question → response created
2. Question text snapshot ensures historical accuracy
3. Flexible JSONB storage supports multiple response types
4. Sentiment analysis stored in `response_metadata`
5. Analytics queries optimized with covering indexes

---

## 2. Flow System Tables

### 2.1 `flow_kinds`

**Purpose:** Define different types of conversation flows (e.g., onboarding, treatment, follow-up).

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `kind_key` | String(100) | Unique flow identifier (indexed) |
| `display_name` | String(255) | Human-readable name |
| `description` | Text | Flow purpose description |
| `is_active` | Boolean | Active status (default: true) |

**Relationships:**
- **1:N** → `flow_template_versions`: All versions of this flow

**Constraints:**
- Unique: `kind_key`

**Compatibility Aliases:**
- `flow_type` → `kind_key`
- `name` → `display_name`

**Business Workflow Usage:**
1. Define flow categories (e.g., "onboarding", "treatment_follow_up")
2. Enable/disable entire flow categories via `is_active`
3. Organize conversation templates by purpose

---

### 2.2 `flow_template_versions`

**Purpose:** Version-controlled conversation flow templates.

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `flow_kind_id` | UUID | FK to flow_kinds (CASCADE delete) |
| `version_number` | Integer | Version number (1, 2, 3...) |
| `template_name` | String(255) | Template name |
| `description` | Text | Version description |
| `is_active` | Boolean | Active version flag (default: false) |
| `steps` | JSONB | Conversation steps/messages |
| `metadata` | JSONB | Template metadata |
| `created_by` | UUID | User who created version |
| `published_at` | DateTime(TZ) | Publication timestamp |
| `deprecated_at` | DateTime(TZ) | Deprecation timestamp |

**Relationships:**
- **N:1** → `flow_kinds`: Flow type
- **1:N** → `patient_flow_states`: Patient progress in this version

**Constraints:**
- **Unique:** `(flow_kind_id, version_number)` - One version per number per kind
- Index: `(flow_kind_id, is_active)` for active version lookup

**Compatibility Aliases:**
- `version` → `str(version_number)`
- `messages` → `steps`
- `kind_id` → `flow_kind_id`
- `is_current` → `is_active`
- `status` → `"published"` if `is_active` else `"draft"`

**Business Workflow Usage:**
1. Create new flow versions without disrupting active flows
2. Test drafts before publishing (`is_active=true`)
3. Track who created each version for audit trail
4. Deprecate old versions while maintaining historical data
5. Only one active version per flow kind at a time

---

### 2.3 `patient_flow_states`

**Purpose:** Track patient progress through conversation flows.

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `patient_id` | UUID | FK to patients (CASCADE delete) |
| `flow_template_version_id` | UUID | FK to flow_template_versions |
| `current_step` | Integer | Current step index (default: 0) |
| `status` | String(50) | onboarding \| active \| paused \| completed... |
| `step_data` | JSONB | Step-specific data (default: {}) |
| `flow_metadata` | JSONB | Additional flow metadata |
| `started_at` | DateTime(TZ) | Flow start time (default: NOW()) |
| `completed_at` | DateTime(TZ) | Flow completion time |
| `next_scheduled_at` | DateTime(TZ) | Next scheduled interaction |
| `last_interaction_at` | DateTime(TZ) | Last interaction timestamp |

**Relationships:**
- **N:1** → `patients`: Patient in the flow
- **N:1** → `flow_template_versions`: Template being followed

**Constraints:**
- **Unique:** `(patient_id, flow_template_version_id)` - One state per patient per flow version

**Business Workflow Usage:**
1. Patient enters flow → state created at step 0
2. Each message/interaction advances `current_step`
3. `step_data` stores answers, selections, state variables
4. Scheduled messages tracked via `next_scheduled_at`
5. Pause/resume flows by updating `status`
6. Complete flow sets `completed_at`

---

## 3. Analytics Tables

### 3.1 `flow_analytics`

**Purpose:** Aggregate performance metrics for patient flow interactions.

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `patient_id` | UUID | FK to patients (CASCADE delete) |
| `flow_template_version_id` | UUID | FK to flow_template_versions |
| `total_messages_sent` | Integer | Outbound message count |
| `total_messages_received` | Integer | Inbound message count |
| `total_interactions` | Integer | Total interaction count |
| `avg_response_time_minutes` | Float | Average response time |
| `completion_rate` | Float | 0.0 - 1.0 completion percentage |
| `engagement_score` | Float | 0.0 - 100.0 engagement metric |
| `quiz_completion_rate` | Float | Quiz completion percentage |
| `avg_quiz_score` | Float | Average quiz score |
| `first_interaction_at` | DateTime(TZ) | First interaction timestamp |
| `last_interaction_at` | DateTime(TZ) | Last interaction timestamp |
| `interaction_patterns` | JSONB | Behavioral patterns (stored as `analytics_data`) |
| `period_start` | DateTime(TZ) | Analytics period start |
| `period_end` | DateTime(TZ) | Analytics period end |
| `success_rate` | Numeric | Overall success rate |
| `completed_steps` | Integer | Steps completed count |
| `total_steps` | Integer | Total steps in flow |
| `step_analytics` | JSONB | Per-step analytics |
| `avg_response_time_seconds` | Integer | Response time in seconds |

**Relationships:**
- **N:1** → `patients`: Patient analytics

**Business Workflow Usage:**
1. Aggregate patient engagement metrics
2. Track message exchange patterns
3. Calculate completion and success rates
4. Identify slow responders or engagement issues
5. Generate dashboards and reports
6. Trigger interventions based on thresholds

---

### 3.2 `flow_messages`

**Purpose:** Individual messages within flow templates (aligned with DB schema).

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `flow_template_version_id` | UUID | FK to flow_template_versions |
| `step_number` | Integer | Message sequence number |
| `message_key` | String(100) | Message identifier |
| `message_text` | Text | Message content |
| `message_type` | String(50) | text \| interactive \| image... |
| `buttons` | JSONB | Button options |
| `list_items` | JSONB | List selections |
| `conditions` | JSONB | Display conditions |
| `delay_seconds` | Integer | Delay before sending (default: 0) |
| `metadata` | JSONB | Message metadata (stored as `message_metadata`) |

**Legacy Columns (backward compatibility):**
- `patient_id`, `message_id`, `step_name`, `content`, `scheduled_for`, `sent_at`, `status`

**Business Workflow Usage:**
1. Define message sequences in flows
2. Interactive messages with buttons/lists
3. Conditional message display
4. Scheduled message delivery
5. Track sent messages per patient

---

### 3.3 `quiz_questions`

**Purpose:** Individual quiz question model (decomposed from JSONB).

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `quiz_template_id` | UUID | FK to quiz_templates |
| `question_text` | String | Question text |
| `question_type` | String(50) | multiple_choice \| text \| scale \| yes_no |
| `question_order` | Integer | Display order |
| `options` | JSONB | Multiple choice options (array) |
| `correct_answer` | String | Correct answer (if applicable) |
| `points` | Integer | Point value (default: 1) |
| `is_required` | Boolean | Required question flag |
| `metadata` | JSONB | Question metadata (stored as `question_metadata`) |

**Business Workflow Usage:**
1. Alternative to storing all questions in `quiz_templates.questions` JSONB
2. Easier querying of individual questions
3. Points-based scoring system
4. Required questions enforcement

---

## 4. Onboarding System

### 4.1 `patient_onboarding_saga`

**Purpose:** Distributed transaction management for patient onboarding using Saga Pattern.

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `patient_id` | UUID | FK to patients (CASCADE delete) |
| `doctor_id` | UUID | FK to users (CASCADE delete) |
| `status` | Enum | STARTED \| IN_PROGRESS \| STEP_1_PATIENT_CREATED \| STEP_2_FIREBASE_USER_CREATED (deprecated) \| STEP_3_FLOW_INITIALIZED \| STEP_4_MESSAGE_SENT \| COMPLETED \| FAILED \| COMPENSATING \| COMPENSATED \| RETRY_SCHEDULED |
| `current_step` | Integer | Current step (0-4) |
| `retry_count` | Integer | Number of retries executed |
| `max_retries` | Integer | Maximum retries (default: 3) |
| `next_retry_at` | DateTime(TZ) | Next retry timestamp |
| `last_retry_at` | DateTime(TZ) | Last retry timestamp |
| `patient_data` | JSONB | Patient creation data |
| `execution_log` | JSONB | Array of step execution logs |
| `error_message` | Text | Error message if failed |
| `error_type` | String(255) | Error classification |
| `started_at` | DateTime(TZ) | Saga start time |
| `completed_at` | DateTime(TZ) | Saga completion time |
| `failed_at` | DateTime(TZ) | Saga failure time |

**Relationships:**
- **N:1** → `patients`: Patient being onboarded
- **N:1** → `users` (doctor_id): Responsible doctor

**Constraints:**
- Index: `patient_id`, `status`, `doctor_id`
- Partial Index: `(status, next_retry_at)` WHERE `status='RETRY_SCHEDULED'`

**Saga Steps:**
1. **Step 1:** Create patient record in database
2. **Step 2:** Create Firebase user (DEPRECATED - skipped in execution)
3. **Step 3:** Initialize patient flow state
4. **Step 4:** Send welcome message via WhatsApp

**Business Workflow Usage:**
1. **Atomicity:** Ensures all onboarding steps complete or compensate
2. **Retry Logic:** Automatic retry with exponential backoff (max 3 retries)
3. **Compensation:** Rollback previous steps on failure (reverse order)
4. **Audit Trail:** `execution_log` tracks every step attempt
5. **Monitoring:** Scheduled retry jobs check `status='RETRY_SCHEDULED'`

**Methods:**
- `add_log_entry(step, action, status, message)`: Append to execution log
- `get_execution_summary()`: Return saga execution details
- `is_completed()`, `is_failed()`: Status checks
- `can_retry()`: Check if retry allowed
- `should_compensate()`: Check if compensation needed
- `get_steps_to_compensate()`: Return steps in reverse order

**Execution Log Structure:**
```json
[
  {
    "step": 1,
    "action": "create_patient",
    "status": "success",
    "timestamp": "2025-12-22T10:00:00Z",
    "message": "Patient created with ID: abc-123"
  },
  {
    "step": 3,
    "action": "initialize_flow",
    "status": "failed",
    "timestamp": "2025-12-22T10:00:05Z",
    "message": "Flow template not found"
  },
  {
    "step": 3,
    "action": "initialize_flow",
    "status": "success",
    "timestamp": "2025-12-22T10:01:00Z",
    "message": "Retry succeeded"
  }
]
```

---

## 5. Reporting System

### 5.1 `patient_summaries`

**Purpose:** AI-generated comprehensive patient summaries for doctor consultations.

**Key Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `patient_id` | UUID | FK to patients (CASCADE delete) |
| `generated_by` | UUID | FK to users (SET NULL on delete) |
| `start_date` | Date | Summary period start |
| `end_date` | Date | Summary period end |
| `content` | JSONB | Structured summary content |
| `pdf_data` | BYTEA | PDF export (optional) |
| `token_usage` | Integer | AI tokens consumed |
| `model_used` | String(100) | AI model (default: gemini-2.5-flash-latest) |
| `generation_time_ms` | Integer | Generation duration |

**Relationships:**
- **N:1** → `patients`: Patient being summarized
- **N:1** → `users` (generated_by): Doctor who generated summary

**Indexes:**
- Composite: `(patient_id, start_date, end_date)` for period queries
- `created_at` for historical summaries

**Content Structure:**
```json
{
  "overview": "2-3 paragraphs summary",
  "quiz_findings": {
    "total_completed": 5,
    "key_findings": ["symptom X improving", "concern Y detected"],
    "symptom_trends": {
      "fatigue": "decreasing",
      "pain": "stable"
    }
  },
  "health_concerns": [
    {
      "concern": "Severe pain reported",
      "severity": "high",
      "date": "2025-12-20"
    }
  ],
  "engagement_metrics": {
    "response_rate": 0.95,
    "avg_response_time_minutes": 15.5,
    "total_messages": 42
  },
  "treatment_compliance": {
    "adherence_score": 0.88,
    "notes": "Missed 2 scheduled check-ins"
  },
  "recommendations": [
    "Schedule follow-up consultation",
    "Adjust pain medication dosage",
    "Monitor symptom X closely"
  ]
}
```

**Business Workflow Usage:**
1. Doctor requests patient summary for consultation
2. AI analyzes quiz responses, messages, engagement data
3. Generate structured summary with key findings
4. Export as PDF for patient records
5. Track AI usage (tokens, model, time) for cost analysis
6. Historical summaries enable trend analysis

---

## 6. Cross-Table Relationships Map

```
patients (core table)
├── quiz_sessions (1:N)
│   ├── quiz_responses (1:N)
│   └── quiz_template (N:1)
│       └── quiz_responses (1:N)
│
├── patient_flow_states (1:N)
│   └── flow_template_versions (N:1)
│       └── flow_kinds (N:1)
│
├── flow_analytics (1:N)
│
├── onboarding_sagas (1:N)
│   └── doctor (users, N:1)
│
└── patient_summaries (1:N)
    └── generated_by (users, N:1)
```

---

## 7. Key Design Patterns

### 7.1 Versioning Pattern
- **Tables:** `quiz_templates`, `flow_template_versions`
- **Pattern:** `(name, version)` unique constraint
- **Benefits:** Audit trail, A/B testing, safe updates

### 7.2 State Machine Pattern
- **Tables:** `quiz_sessions`, `patient_flow_states`, `patient_onboarding_saga`
- **Pattern:** Explicit `status` column with constrained values
- **Benefits:** Clear state transitions, validation, debugging

### 7.3 Saga Pattern (Distributed Transactions)
- **Table:** `patient_onboarding_saga`
- **Pattern:** Step-by-step execution with compensation logic
- **Benefits:** Reliability across services, automatic retry, rollback

### 7.4 Snapshot Pattern
- **Table:** `quiz_responses`
- **Pattern:** Store `question_text` snapshot alongside `question_id`
- **Benefits:** Historical accuracy, template changes don't affect past data

### 7.5 JSONB Flexibility Pattern
- **Columns:** `questions`, `response_value`, `steps`, `content`, `execution_log`
- **Pattern:** Schema-less storage for variable structures
- **Benefits:** Flexible data models, easy schema evolution

### 7.6 Partial Unique Index Pattern
- **Table:** `quiz_sessions`
- **Pattern:** `UNIQUE (patient_id, quiz_template_id) WHERE status='started'`
- **Benefits:** Only one active session, multiple historical sessions allowed

### 7.7 Soft Delete Pattern
- **Relationships:** `ondelete="SET NULL"` for `generated_by`
- **Pattern:** Preserve references when users deleted
- **Benefits:** Data retention, audit trail

---

## 8. Performance Optimization

### 8.1 Strategic Indexes

**Quiz System:**
- Covering index for analytics: `(quiz_template_id, question_id, response_value, responded_at)`
- Patient history: `(patient_id, quiz_template_id, responded_at)`
- Session filtering: `(patient_id, status)`, `(quiz_template_id, status)`

**Flow System:**
- Active versions: `(flow_kind_id, is_active)`
- Patient lookup: `patient_id`, `flow_template_version_id`

**Onboarding:**
- Retry scheduling: `(status, next_retry_at) WHERE status='RETRY_SCHEDULED'`

### 8.2 Data Types
- `Numeric(5,2)` for scores (precision without floating point errors)
- `JSONB` for fast querying (vs `JSON`)
- `DateTime(timezone=True)` for global deployments
- `BYTEA` for binary PDF data

### 8.3 Cascade Strategies
- `CASCADE DELETE` for dependent data (sessions → patient)
- `RESTRICT` for templates (prevent accidental deletion)
- `SET NULL` for audit trail preservation

---

## 9. Data Integrity Mechanisms

### Check Constraints
- Non-negative values: `score >= 0`, `current_question >= 0`
- Enum validation: `status IN ('started', 'completed', ...)`
- String non-empty: `LENGTH(name) >= 1`
- Completion logic: `status='completed' → completed_at IS NOT NULL`

### Unique Constraints
- Version control: `(name, version)` on templates
- One response per question: `(quiz_session_id, question_id)`
- One flow state: `(patient_id, flow_template_version_id)`

### Foreign Key Constraints
- Referential integrity across all relationships
- Cascade rules match business logic
- Orphan prevention

---

## 10. Migration & Compatibility Notes

### Backward Compatibility Aliases
**Flow System:**
- `flow_type` → `kind_key`
- `messages` → `steps`
- `is_current` → `is_active`

**Quiz System:**
- `current_question_index` → `current_question`
- `is_completed` → `status == 'completed'`

### Deprecated Features
- **Step 2 (Firebase User Creation):** Marked as `@deprecated`, skipped in saga execution
- Column retained for database compatibility

### SQLite Compatibility
- NOW() constraint removed (PostgreSQL only)
- Constraint enforced in production PostgreSQL database

---

## 11. Security Considerations

1. **Cascade Deletes:** Patient deletion removes all associated data (GDPR compliance)
2. **RESTRICT on Templates:** Prevents accidental deletion of active templates
3. **SET NULL on Users:** Preserves audit trail when users deleted
4. **JSONB Validation:** Validators prevent injection via `@validates` decorators
5. **Timezone-Aware Timestamps:** All `DateTime` columns use `timezone=True`

---

## 12. Recommended Queries

### Active Quiz Sessions for Patient
```sql
SELECT * FROM quiz_sessions
WHERE patient_id = :patient_id
  AND status = 'started'
ORDER BY created_at DESC;
```

### Patient Flow Progress
```sql
SELECT pfs.*, ftv.template_name, fk.display_name
FROM patient_flow_states pfs
JOIN flow_template_versions ftv ON pfs.flow_template_version_id = ftv.id
JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
WHERE pfs.patient_id = :patient_id
  AND pfs.status = 'active';
```

### Quiz Analytics by Template
```sql
SELECT
  qt.name,
  COUNT(DISTINCT qs.id) AS total_sessions,
  AVG(qs.score) AS avg_score,
  SUM(CASE WHEN qs.passed THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS pass_rate
FROM quiz_templates qt
LEFT JOIN quiz_sessions qs ON qt.id = qs.quiz_template_id
WHERE qs.status = 'completed'
GROUP BY qt.id, qt.name;
```

### Failed Sagas Requiring Retry
```sql
SELECT * FROM patient_onboarding_saga
WHERE status = 'RETRY_SCHEDULED'
  AND next_retry_at <= NOW()
  AND retry_count < max_retries
ORDER BY next_retry_at ASC;
```

### Patient Summary with Latest Data
```sql
SELECT ps.*, p.full_name, u.full_name AS generated_by_name
FROM patient_summaries ps
JOIN patients p ON ps.patient_id = p.id
LEFT JOIN users u ON ps.generated_by = u.id
WHERE ps.patient_id = :patient_id
ORDER BY ps.created_at DESC
LIMIT 1;
```

---

## 13. Maintenance Recommendations

### Scheduled Jobs
1. **Expire Quiz Sessions:** Mark sessions as `expired` after 48 hours
2. **Retry Sagas:** Process `RETRY_SCHEDULED` sagas every 5 minutes
3. **Aggregate Analytics:** Calculate daily `flow_analytics` metrics
4. **Archive Old Data:** Move completed sagas older than 90 days to archive

### Monitoring Queries
1. **Stuck Sessions:** Sessions in `started` status > 48 hours
2. **Failed Sagas:** Count of `FAILED` status sagas
3. **Response Time Trends:** Track `avg_response_time_minutes` over time
4. **Template Usage:** Most/least used quiz templates

### Index Maintenance
1. **REINDEX:** Monthly on high-traffic tables
2. **VACUUM ANALYZE:** Weekly on tables with high insert/delete rate
3. **Index Usage:** Monitor `pg_stat_user_indexes` for unused indexes

---

## 14. Code Quality Observations

### Strengths
1. **Comprehensive Validation:** `@validates` decorators on critical fields
2. **Clear Documentation:** Docstrings explain purpose and structure
3. **Consistent Naming:** Follows Python/SQLAlchemy conventions
4. **Type Hints:** Extensive use of type annotations
5. **Relationship Clarity:** Explicit `back_populates` relationships
6. **Index Strategy:** Performance-critical queries indexed
7. **Constraint Coverage:** Business rules enforced at DB level

### Areas for Improvement
1. **JSONB Schema Validation:** Consider JSON Schema validation in validators
2. **Enum Consolidation:** `SagaStatus` and `FlowState` could share base
3. **Audit Columns:** Consider adding `updated_by` alongside `created_by`
4. **Soft Deletes:** Consider adding `deleted_at` for soft delete pattern
5. **Version Migration:** Add migration scripts for schema changes

---

## 15. Conclusion

The Hormonia database schema demonstrates a well-architected system for managing patient interactions in an oncology clinic setting. Key strengths include:

- **Reliability:** Saga pattern ensures consistent onboarding
- **Flexibility:** JSONB columns allow schema evolution
- **Performance:** Strategic indexing for common query patterns
- **Auditability:** Versioning and execution logs
- **Scalability:** Proper normalization and relationship design

The system effectively balances flexibility (JSONB) with structure (constraints), and implements proven patterns (Saga, State Machine, Versioning) for a robust healthcare data management platform.

---

**Analysis Completed:** 2025-12-22
**Total Tables Analyzed:** 11
**Total Relationships Documented:** 20+
**Total Indexes Identified:** 30+
