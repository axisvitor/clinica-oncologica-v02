# Quiz System Guide - Hormonia Oncology Platform

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quiz Templates](#quiz-templates)
4. [Session Management](#session-management)
5. [Token-Based Access](#token-based-access)
6. [AI Humanization Pipeline](#ai-humanization-pipeline)
7. [Score Calculation](#score-calculation)
8. [Monthly Quiz Scheduling](#monthly-quiz-scheduling)
9. [API Reference](#api-reference)
10. [Code Examples](#code-examples)
11. [Configuration](#configuration)

---

## Overview

The Quiz System is a comprehensive patient assessment module designed for oncology care in the Hormonia platform. It provides:

- **Monthly patient wellness assessments** via secure tokenized links
- **AI-powered question humanization** for personalized patient experience
- **Adaptive quiz sessions** with real-time mood and engagement tracking
- **Multi-agent orchestration** for intelligent quiz conduction
- **Comprehensive scoring** with statistical analysis

### Key Features

| Feature | Description |
|---------|-------------|
| Token-Based Access | Secure JWT tokens for quiz link authentication |
| AI Humanization | Context-aware question personalization |
| Adaptive Intelligence | Real-time session adaptation based on patient responses |
| Multi-Channel Delivery | WhatsApp, Email, SMS support |
| LGPD Compliance | Built-in privacy and consent management |

---

## Architecture

### System Architecture Diagram

```
+-------------------------------------------------------------------+
|                        QUIZ SYSTEM ARCHITECTURE                    |
+-------------------------------------------------------------------+
|                                                                    |
|  +------------------+     +-------------------+     +------------+ |
|  |   Frontend UI    |     |   API Gateway     |     |  WhatsApp  | |
|  |  (Patient View)  |<--->|  /api/v2/quiz/*   |<--->|  Service   | |
|  +------------------+     +-------------------+     +------------+ |
|           |                        |                               |
|           v                        v                               |
|  +------------------------------------------------------------------+
|  |                     DOMAIN LAYER                                 |
|  +------------------------------------------------------------------+
|  |                                                                  |
|  |  +------------------+  +------------------+  +----------------+  |
|  |  | QuizSessionManager|  | QuizConductor   |  | QuizScheduler  |  |
|  |  | - Token mgmt     |  | - Session flow  |  | - Monthly cycle|  |
|  |  | - Link creation  |  | - Adaptation    |  | - Triggering   |  |
|  |  | - Delivery       |  | - Multi-agent   |  |                |  |
|  |  +------------------+  +------------------+  +----------------+  |
|  |           |                    |                    |           |
|  |           v                    v                    v           |
|  |  +------------------+  +------------------+  +----------------+  |
|  |  | TemplateService  |  | QuestionHumanizer|  | ScoreCalculator|  |
|  |  | - Load templates |  | - AI integration|  | - Aggregation  |  |
|  |  | - Validation     |  | - Anti-repetition|  | - Statistics   |  |
|  |  +------------------+  +------------------+  +----------------+  |
|  |                                                                  |
|  +------------------------------------------------------------------+
|           |                        |                               |
|           v                        v                               |
|  +------------------------------------------------------------------+
|  |                    DATA LAYER                                    |
|  +------------------------------------------------------------------+
|  |  +------------------+  +------------------+  +----------------+  |
|  |  | QuizTemplate     |  | QuizSession      |  | QuizResponse   |  |
|  |  | (PostgreSQL)     |  | (PostgreSQL)     |  | (PostgreSQL)   |  |
|  |  +------------------+  +------------------+  +----------------+  |
|  |                                                                  |
|  |  +------------------+  +------------------+                      |
|  |  | Redis Cache      |  | Question History |                      |
|  |  | - Token cache    |  | - Anti-repetition|                      |
|  |  +------------------+  +------------------+                      |
|  +------------------------------------------------------------------+
|                                                                    |
+-------------------------------------------------------------------+
```

### Domain Structure

```
app/domain/quizzes/
|-- __init__.py              # Main exports
|-- manager.py               # QuizSessionManager orchestrator
|-- score_calculator.py      # Score computation
|-- question_renderer.py     # Question display
|-- answer_validator.py      # Response validation
|-- report_generator.py      # Report generation
|-- quiz_trigger_policy.py   # Centralized trigger logic
|
|-- templates/
|   |-- __init__.py
|   |-- template_service.py  # Database-backed templates
|
|-- session/
|   |-- token_manager.py     # JWT token handling
|   |-- factory.py           # Session creation
|
|-- delivery/
|   |-- link_builder.py      # URL generation
|   |-- service.py           # Notification delivery
|
|-- operations/
|   |-- link_ops.py          # Link operations
|   |-- expiry_handler.py    # Token expiration
|   |-- bulk_manager.py      # Bulk operations
|
|-- evaluation/
|   |-- response_evaluator.py
|
|-- integration/
|   |-- flow_integration_service.py
|   |-- flow_integration/
|       |-- trigger_service.py
|       |-- response_handler.py
|
|-- security/
|   |-- token_rotation.py
```

---

## Quiz Templates

### Template Structure

Quiz templates are stored in PostgreSQL as JSONB and define the structure of assessments.

**Database Model** (`app/models/quiz.py`):

```python
class QuizTemplate(BaseModel):
    __tablename__ = "quiz_templates"

    name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    questions = Column(JSONB, nullable=False)  # Array of questions
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    passing_score = Column(Integer, nullable=True)
    time_limit_minutes = Column(Integer, nullable=True)
    randomize_questions = Column(Boolean, nullable=True)
    tags = Column(JSONB, nullable=True)
```

### Question Types

| Type | Description | Example Use |
|------|-------------|-------------|
| `multiple_choice` | Single or multiple selection | Symptom checklists |
| `scale` | Numeric range (1-10) | Pain level assessment |
| `open_text` | Free-form text | Patient comments |
| `yes_no` | Boolean response | Medication confirmation |

### Question Schema

```json
{
  "id": "q_symptom_01",
  "type": "scale",
  "text": "Em uma escala de 1 a 10, qual seu nivel de dor hoje?",
  "options": null,
  "validation_rules": [
    {
      "type": "range",
      "value": {"min": 1, "max": 10}
    }
  ],
  "alert_threshold": {
    "type": "above",
    "value": 7,
    "priority": "high"
  },
  "metadata": {
    "category": "pain_assessment",
    "humanizable": false
  }
}
```

### Template Service Usage

**Location**: `app/domain/quizzes/templates/template_service.py`

```python
from app.domain.quizzes import QuizTemplateService, get_quiz_template_service

# Get template service instance
service = get_quiz_template_service(db_session)

# Load template by name
template = service.load_quiz_template("Quizz de Bem-Estar Mensal")

# Load all active templates
all_templates = service.load_all_quiz_templates()

# Get template by ID
template = service.get_template_by_id(template_uuid)

# Get specific question
question = service.get_question_by_id("monthly_wellness", "q_symptom_01")
```

---

## Session Management

### Session Lifecycle

```
+----------+     +----------+     +-----------+     +-----------+
| CREATED  | --> | STARTED  | --> | COMPLETED | or  | CANCELLED |
+----------+     +----------+     +-----------+     +-----------+
                      |                                   ^
                      |           +----------+            |
                      +---------> | EXPIRED  |------------+
                                  +----------+
```

### QuizSession Model

**Location**: `app/models/quiz.py`

```python
class QuizSession(BaseModel):
    __tablename__ = "quiz_sessions"

    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"))
    quiz_template_id = Column(UUID(as_uuid=True), ForeignKey("quiz_templates.id"))

    status = Column(String(50), default="started")  # started, completed, cancelled, expired
    current_question = Column(Integer, default=0)
    total_questions = Column(Integer, nullable=True)
    answered_questions = Column(Integer, default=0)

    score = Column(Numeric(5, 2), nullable=True)
    max_score = Column(Numeric(5, 2), nullable=True)
    passed = Column(Boolean, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expiration_date = Column(DateTime(timezone=True), nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)

    session_metadata = Column(JSONB, default=dict)  # Token hash, delivery info, etc.
```

### Session Manager Usage

**Location**: `app/domain/quizzes/manager.py`

```python
from app.domain.quizzes import QuizSessionManager
from app.schemas.monthly_quiz import MonthlyQuizLinkCreate, DeliveryMethod

# Initialize manager
manager = QuizSessionManager(db_session)

# Create quiz link
link_data = MonthlyQuizLinkCreate(
    patient_id=patient_uuid,
    quiz_template_id=template_uuid,
    delivery_method=DeliveryMethod.WHATSAPP,
    expiry_hours=72,
    send_immediately=True,
    custom_message="Ola {nome}, seu questionario mensal esta disponivel!"
)

response = await manager.create_quiz_link(
    link_data=link_data,
    actor_id=doctor_uuid,
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent")
)

# Response includes:
# - id: Session UUID
# - token: JWT token for access
# - link_url: Full quiz URL
# - status: QuizLinkStatus.ACTIVE
# - expires_at: Expiration datetime
```

---

## Token-Based Access

### Token Architecture

The quiz system uses JWT (JSON Web Tokens) for secure, stateless access to quiz sessions.

```
+----------------+     +------------------+     +----------------+
|    Patient     |     |    Token         |     |    Backend     |
|    Device      |     |    Validation    |     |    Services    |
+----------------+     +------------------+     +----------------+
        |                      |                       |
        | 1. Click quiz link   |                       |
        |--------------------->|                       |
        |                      | 2. Verify JWT         |
        |                      |---------------------->|
        |                      |                       |
        |                      | 3. Check expiration   |
        |                      |<----------------------|
        |                      |                       |
        |                      | 4. Validate session   |
        |                      |<----------------------|
        |                      |                       |
        | 5. Return quiz       |                       |
        |<---------------------|                       |
        |                      |                       |
```

### Token Manager

**Location**: `app/domain/quizzes/session/token_manager.py`

```python
class TokenManager:
    """Handles JWT token generation and verification for quiz sessions."""

    def generate_token(
        self,
        patient_id: UUID,
        quiz_template_id: UUID,
        expires_at: datetime,
        rotation_count: int = 0,
    ) -> str:
        """
        Generate a JWT token for quiz session access.

        Token payload includes:
        - patient_id: Patient UUID
        - quiz_template_id: Template UUID
        - exp: Expiration timestamp
        - iat: Issued at timestamp
        - rotation: Token rotation count
        - jti: Unique token ID (prevents replay)
        """
        payload = {
            "patient_id": str(patient_id),
            "quiz_template_id": str(quiz_template_id),
            "exp": int(expires_at.timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "rotation": rotation_count,
            "jti": secrets.token_urlsafe(16),
        }
        return jwt.encode(
            payload,
            self.config.MONTHLY_QUIZ_TOKEN_SECRET,
            algorithm="HS256"
        )

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode a JWT token.

        Raises:
            jwt.ExpiredSignatureError: Token has expired
            jwt.InvalidTokenError: Token is invalid
        """
        return jwt.decode(
            token,
            self.config.MONTHLY_QUIZ_TOKEN_SECRET,
            algorithms=["HS256"]
        )

    def hash_token(self, token: str) -> str:
        """Generate SHA256 hash of token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
```

### Token Flow Diagram

```
Patient receives WhatsApp message:
  "Ola Maria! Seu questionario de bem-estar esta disponivel.
   Acesse: https://hormonia.app/quiz?t=eyJhbGciOiJIUzI1..."

                      +
                      |
                      v
+----------------------------------------------------------+
|                 TOKEN VALIDATION FLOW                     |
+----------------------------------------------------------+
|                                                          |
|  1. Extract token from URL parameter                     |
|     GET /quiz?t={JWT_TOKEN}                              |
|                                                          |
|  2. Verify JWT signature (MONTHLY_QUIZ_TOKEN_SECRET)     |
|     - Check algorithm: HS256                             |
|     - Validate signature integrity                       |
|                                                          |
|  3. Check token expiration (exp claim)                   |
|     - Default: 72 hours from creation                    |
|     - Configurable via MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS   |
|                                                          |
|  4. Validate token uniqueness (jti claim)                |
|     - Prevent replay attacks                             |
|     - Optional single-use mode                           |
|                                                          |
|  5. Find session by token hash                           |
|     - session_metadata['token_hash'] = SHA256(token)     |
|     - Verify patient_id and template_id match            |
|                                                          |
|  6. Check session status                                 |
|     - Must be 'started' (not completed/cancelled)        |
|     - Not past expiration_date                           |
|                                                          |
|  7. Optional: Rotate token on access                     |
|     - Generate new token with incremented rotation       |
|     - Update session_metadata with new token_hash        |
|                                                          |
+----------------------------------------------------------+
```

### Security Features

| Feature | Description | Configuration |
|---------|-------------|---------------|
| Token Expiration | Default 72 hours | `MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS` |
| Token Rotation | New token on each access | `MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION` |
| Single-Use Tokens | Optional one-time access | `MONTHLY_QUIZ_SINGLE_USE_TOKENS` |
| Rate Limiting | 10 accesses per hour | `MONTHLY_QUIZ_RATE_LIMIT_PER_HOUR` |
| Lockout | 30 min after 3 failures | `MONTHLY_QUIZ_LOCKOUT_MINUTES` |

---

## AI Humanization Pipeline

### Overview

The AI Humanization system personalizes quiz questions based on patient context while maintaining medical accuracy for critical assessments.

### Architecture

```
+-------------------------------------------------------------------+
|                    AI HUMANIZATION PIPELINE                        |
+-------------------------------------------------------------------+
|                                                                    |
|  +----------------+     +------------------+     +---------------+ |
|  | Quiz Question  |     | Safety Check     |     | Context Build | |
|  | (Template)     |---->| (Type Filter)    |---->| (Patient Data)| |
|  +----------------+     +------------------+     +---------------+ |
|                                |                        |          |
|                                v                        v          |
|                    +-------------------+     +------------------+  |
|                    | CRITICAL TYPES    |     | SAFE TYPES       |  |
|                    | (No Humanization) |     | (Humanize)       |  |
|                    +-------------------+     +------------------+  |
|                                                     |              |
|                                                     v              |
|                              +-----------------------------+       |
|                              | Anti-Repetition Engine      |       |
|                              | - Recent question history   |       |
|                              | - Intent pattern rotation   |       |
|                              | - Similarity detection      |       |
|                              +-----------------------------+       |
|                                           |                        |
|                                           v                        |
|                              +-----------------------------+       |
|                              | AI Service (Gemini)         |       |
|                              | - Patient context           |       |
|                              | - Tone selection            |       |
|                              | - Variety prompts           |       |
|                              +-----------------------------+       |
|                                           |                        |
|                                           v                        |
|                              +-----------------------------+       |
|                              | Similarity Validation       |       |
|                              | - 80% overlap threshold     |       |
|                              | - Fallback variations       |       |
|                              +-----------------------------+       |
|                                           |                        |
|                                           v                        |
|                              +-----------------------------+       |
|                              | Humanized Question Output   |       |
|                              +-----------------------------+       |
+-------------------------------------------------------------------+
```

### Question Type Classification

**Location**: `app/services/question_humanizer.py`

```python
class QuestionHumanizer:
    # CRITICAL: Never humanize these - exact wording required
    CRITICAL_QUESTION_TYPES = [
        "medication_verification",
        "dosage_confirmation",
        "allergy_check",
        "emergency_symptoms",
        "consent_collection",
        "vital_signs",
        "side_effects_severe",
    ]

    # SAFE: Can be humanized for better experience
    SAFE_QUESTION_TYPES = [
        "daily_checkin",
        "mood_assessment",
        "symptom_tracking",
        "comfort_level",
        "sleep_quality",
        "appetite_check",
        "activity_level",
        "social_support",
        "general_wellbeing",
        "feedback_request",
    ]
```

### Intent Pattern Rotation

To prevent repetitive communication, the system rotates through different communication intents:

```python
INTENT_PATTERNS = {
    "daily_checkin": [
        "greeting_morning",
        "greeting_afternoon",
        "greeting_evening",
        "casual_checkin",
        "warm_inquiry",
    ],
    "symptom_tracking": [
        "direct_inquiry",
        "gentle_approach",
        "detailed_assessment",
        "quick_check",
        "comprehensive_review",
    ],
    "mood_assessment": [
        "emotional_check",
        "feeling_inquiry",
        "mood_scale",
        "emotional_support",
        "wellbeing_check",
    ],
}
```

### Humanization Example

```python
from app.services.question_humanizer import get_question_humanizer

humanizer = get_question_humanizer()

# Original template question
original = "Como voce esta se sentindo hoje?"

# Humanized with patient context
humanized = await humanizer.humanize_question(
    question=original,
    question_type="daily_checkin",
    patient=patient,
    context={"quiz_type": "monthly"}
)

# Result (varies by context and intent):
# "Bom dia, Maria! Como voce tem se sentido esta semana?"
# "Ola, querida! Gostaria de saber como voce esta hoje."
# "Boa tarde, Maria! Como esta seu dia?"
```

### Integration with Quiz Service

**Location**: `app/services/quiz_question_humanizer_integration.py`

```python
from app.services.quiz_question_humanizer_integration import (
    QuizQuestionHumanizerIntegration
)

# Initialize integration
integrator = QuizQuestionHumanizerIntegration(db_session)

# Humanize all quiz questions
humanized_questions = await integrator.humanize_quiz_questions(
    questions=template.questions,
    patient_id=patient.id,
    quiz_type="monthly"
)

# Each humanized question includes:
# - text: Humanized question text
# - original_text: Original template text
# - humanized: Boolean flag
```

---

## Score Calculation

### Score Calculator

**Location**: `app/domain/quizzes/score_calculator.py`

```python
class ScoreCalculator:
    """Calculates and analyzes quiz scores."""

    async def calculate_score(self, session_id: UUID) -> float:
        """
        Calculate score for a completed quiz session.
        Returns average score (0-100 scale).
        """
        responses = self.db.query(QuizResponse)\
            .filter(QuizResponse.quiz_session_id == session_id)\
            .all()

        total_score = 0.0
        scored_responses = 0

        for response in responses:
            metadata = response.response_metadata or {}
            if "score" in metadata and metadata["score"] is not None:
                total_score += float(metadata["score"])
                scored_responses += 1

        return round(total_score / scored_responses, 2) if scored_responses > 0 else 0.0
```

### Scoring Rules by Question Type

| Question Type | Scoring Method | Partial Credit |
|---------------|----------------|----------------|
| `single_choice` | Exact match: 100 or 0 | No |
| `multiple_choice` | Configurable partial credit | Yes |
| `numeric` | Tolerance-based | Optional |
| `boolean` | Exact match: 100 or 0 | No |
| `open_text` | Manual scoring required | N/A |

### Multiple Choice Partial Credit

```python
def _score_multiple_choice(
    self,
    response_value: List[str],
    correct_answer: List[str],
    scoring_rules: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Score multiple choice with partial credit.

    Example:
        Correct: ["A", "B", "C"]
        Response: ["A", "B"]
        Score: 66.67% (2/3 correct)

        With penalty for incorrect:
        Response: ["A", "B", "D"]
        Score: 66.67% - 33.33% penalty = ~33%
    """
```

### Session Statistics

```python
stats = calculator.calculate_session_statistics(session_id)

# Returns:
{
    "session_id": "uuid",
    "total_questions": 10,
    "answered_questions": 10,
    "scored_questions": 8,
    "total_score": 720.0,
    "average_score": 90.0,
    "completion_time_seconds": 420,
    "status": "completed",
    "individual_scores": [100, 80, 90, 85, 95, 90, 85, 95]
}
```

### Performance Categories

```python
def get_performance_category(self, score: float) -> str:
    """
    Categorize performance based on score.

    Categories:
    - excellent:          >= 90
    - good:              75-89
    - satisfactory:      60-74
    - needs_improvement: 50-59
    - poor:              < 50
    """
```

---

## Monthly Quiz Scheduling

### Quiz Trigger Policy

**Location**: `app/domain/quizzes/quiz_trigger_policy.py`

```python
class QuizTriggerPolicy:
    """
    Centralized policy for quiz triggers and scheduling.

    Trigger Days:
    - Monthly Quiz: Day 15 of each 30-day cycle
    - Initial Assessment: Day 15 of enrollment
    - Mid-Treatment: Day 45 after enrollment
    """

    MONTHLY_QUIZ_DAY = 15
    INITIAL_ASSESSMENT_DAY = 15
    MID_TREATMENT_DAY = 45
```

### Treatment Timeline

```
+--------------------------------------------------------------------+
|                    PATIENT TREATMENT TIMELINE                        |
+--------------------------------------------------------------------+
|                                                                      |
|  Day 1                    Day 15                    Day 45           |
|    |                        |                         |              |
|    v                        v                         v              |
|  +----------+          +----------+            +----------+          |
|  | Onboard  |          | Initial  |            | Mid-Treat|          |
|  | Start    |          | Quiz     |            | Quiz     |          |
|  +----------+          +----------+            +----------+          |
|                                                                      |
|    |<----------- Initial Phase (Day 1-15) -------->|                |
|                                                                      |
|                          |<------ Day 16-45 Phase ------>|          |
|                                                                      |
|                                                    |                 |
|  Day 46+: Monthly Recurring Phase                  v                 |
|    |<------------------------------------------------->             |
|                                                                      |
|  +----------+    +----------+    +----------+    +----------+       |
|  | Month 1  |    | Month 2  |    | Month 3  |    | Month N  |       |
|  | Day 15   |    | Day 15   |    | Day 15   |    | Day 15   |       |
|  | Quiz     |    | Quiz     |    | Quiz     |    | Quiz     |       |
|  +----------+    +----------+    +----------+    +----------+       |
|                                                                      |
+--------------------------------------------------------------------+
```

### Quiz Scheduler Usage

**Location**: `app/domain/flows/scheduling/quiz_scheduler.py`

```python
from app.domain.flows.scheduling.quiz_scheduler import QuizScheduler

scheduler = QuizScheduler(db_session)

# Check if quiz should trigger
should_trigger = await scheduler.should_trigger_quiz(
    flow_type="monthly_recurring",
    current_day=15,
    flow_state=patient_flow_state
)

# Execute quiz step
result = await scheduler.execute_quiz_step(
    patient_id=patient_uuid,
    flow_state=flow_state,
    flow_type="monthly_recurring",
    current_day=15
)

# Result:
{
    "success": True,
    "message": "Quiz step executed",
    "quiz_triggered": True,
    "quiz_session_id": "uuid",
    "delivery_method": "whatsapp",
    "quiz_type": "monthly_assessment",
    "monthly_cycle": 3
}
```

### Monthly Cycle Calculation

```python
@classmethod
def calculate_monthly_cycle(cls, days_since_enrollment: int) -> tuple[int, int]:
    """
    Calculate which monthly cycle the patient is in.

    Examples:
        days_since_enrollment=50 -> (1, 5)  # Cycle 1, day 5
        days_since_enrollment=75 -> (2, 0)  # Cycle 2, day 0
        days_since_enrollment=105 -> (3, 0) # Cycle 3, day 0
    """
    if days_since_enrollment < 45:
        return 0, days_since_enrollment  # Still in initial phase

    days_in_monthly_phase = days_since_enrollment - 45
    monthly_cycle = (days_in_monthly_phase // 30) + 1
    day_in_cycle = days_in_monthly_phase % 30

    return monthly_cycle, day_in_cycle
```

---

## API Reference

### Quiz Sessions Endpoints

**Location**: `app/api/v2/routers/quiz_sessions.py`

#### List Quiz Sessions

```http
GET /api/v2/quizzes
Authorization: Bearer {token}

Query Parameters:
  - patient_id: UUID (optional)
  - status: string (optional) - started, completed, cancelled, expired
  - cursor: string (optional) - pagination cursor
  - limit: int (default: 50)
  - fields: string (optional) - comma-separated field selection
  - include: string (optional) - relationships to include (patient)

Response: 200 OK
{
  "data": [
    {
      "id": "uuid",
      "patient_id": "uuid",
      "quiz_template_id": "uuid",
      "status": "completed",
      "created_at": "2025-01-01T10:00:00Z",
      "completed_at": "2025-01-01T10:30:00Z",
      "score": 85.5,
      "passed": true,
      "patient": {
        "id": "uuid",
        "name": "Maria Silva",
        "email": "maria@example.com"
      }
    }
  ],
  "next_cursor": "base64_encoded_cursor",
  "has_more": true,
  "total": 150
}
```

#### Get Quiz Session

```http
GET /api/v2/quizzes/{quiz_id}
Authorization: Bearer {token}

Response: 200 OK
{
  "id": "uuid",
  "patient_id": "uuid",
  "quiz_template_id": "uuid",
  "status": "started",
  "current_question": 3,
  "total_questions": 10,
  "answered_questions": 3,
  "time_spent_seconds": 180,
  "session_metadata": {
    "token_hash": "sha256_hash",
    "delivery_method": "whatsapp"
  }
}
```

#### Create Quiz Session

```http
POST /api/v2/quizzes
Authorization: Bearer {token}
Content-Type: application/json

Request Body:
{
  "patient_id": "uuid",
  "quiz_template_id": "uuid",
  "status": "started"
}

Response: 201 Created
{
  "id": "uuid",
  "patient_id": "uuid",
  "quiz_template_id": "uuid",
  "status": "started",
  "created_at": "2025-01-01T10:00:00Z",
  "started_at": "2025-01-01T10:00:00Z"
}

Error Responses:
  - 400: Invalid UUID format
  - 404: Patient or template not found
  - 409: Active session already exists
  - 503: Service busy (distributed lock)
```

#### Update Quiz Session

```http
PATCH /api/v2/quizzes/{quiz_id}
Authorization: Bearer {token}
Content-Type: application/json

Request Body:
{
  "status": "completed",
  "score": 85.5,
  "max_score": 100.0,
  "passed": true,
  "completed_at": "2025-01-01T10:30:00Z"
}

Response: 200 OK
```

#### Delete Quiz Session

```http
DELETE /api/v2/quizzes/{quiz_id}
Authorization: Bearer {token}

Response: 204 No Content
```

### Public Quiz Access (Token-Based)

```http
GET /api/v2/quiz/public/{token}

Response: 200 OK
{
  "session_id": "uuid",
  "template_name": "Quizz de Bem-Estar Mensal",
  "questions": [...],
  "current_question_index": 0,
  "total_questions": 10,
  "patient_name": "Maria"
}

Error Responses:
  - 401: Token expired or invalid
  - 404: Session not found
  - 410: Session already completed
```

### Quiz Response Submission

```http
POST /api/v2/quiz/public/{token}/responses
Content-Type: application/json

Request Body:
{
  "question_id": "q_symptom_01",
  "response_value": 7,
  "response_type": "scale"
}

Response: 200 OK
{
  "success": true,
  "next_question_index": 2,
  "progress": {
    "answered": 2,
    "total": 10,
    "percentage": 20
  }
}
```

---

## Code Examples

### Creating a Monthly Quiz Link

```python
from app.domain.quizzes import QuizSessionManager
from app.schemas.monthly_quiz import MonthlyQuizLinkCreate, DeliveryMethod
from uuid import UUID

async def create_monthly_quiz_for_patient(
    db_session,
    patient_id: UUID,
    template_id: UUID,
    doctor_id: UUID
):
    """Create and send a monthly quiz link to a patient."""

    manager = QuizSessionManager(db_session)

    link_data = MonthlyQuizLinkCreate(
        patient_id=patient_id,
        quiz_template_id=template_id,
        delivery_method=DeliveryMethod.WHATSAPP,
        expiry_hours=72,
        send_immediately=True,
        custom_message=(
            "Ola {nome}! Seu questionario mensal de bem-estar esta disponivel. "
            "Por favor, responda para que possamos acompanhar seu tratamento."
        )
    )

    response = await manager.create_quiz_link(
        link_data=link_data,
        actor_id=doctor_id
    )

    return {
        "session_id": response.id,
        "link_url": response.link_url,
        "expires_at": response.expires_at,
        "status": response.status
    }
```

### Processing Quiz Responses with the Conductor Agent

```python
from app.domain.agents.quiz import QuizConductor
from uuid import UUID

async def process_patient_quiz_response(
    db_session,
    patient_id: UUID,
    response_text: str
):
    """Process a patient's quiz response using the conductor agent."""

    conductor = QuizConductor(db_session)
    await conductor.start()  # Initialize AI services

    try:
        result = await conductor.process_task({
            "type": "process_quiz_response",
            "payload": {
                "patient_id": str(patient_id),
                "response_text": response_text
            }
        })

        return result
    finally:
        await conductor.stop()
```

### Calculating Quiz Statistics

```python
from app.domain.quizzes import QuizScoreCalculator
from uuid import UUID

def analyze_quiz_session(db_session, session_id: UUID):
    """Calculate comprehensive statistics for a quiz session."""

    calculator = QuizScoreCalculator(db_session)

    # Get session statistics
    stats = calculator.calculate_session_statistics(session_id)

    # Get performance category
    category = calculator.get_performance_category(stats["average_score"])

    # Calculate percentile among all patients
    all_scores = [...]  # Get from database
    percentile = calculator.calculate_percentile_rank(
        stats["average_score"],
        all_scores
    )

    return {
        **stats,
        "performance_category": category,
        "percentile_rank": percentile
    }
```

### Humanizing Quiz Questions

```python
from app.services.question_humanizer import get_question_humanizer
from app.services.quiz_question_humanizer_integration import (
    QuizQuestionHumanizerIntegration
)

async def prepare_humanized_quiz(db_session, patient_id: UUID, template):
    """Prepare quiz questions with AI humanization."""

    integrator = QuizQuestionHumanizerIntegration(db_session)

    # Humanize all questions for the patient
    humanized_questions = await integrator.humanize_quiz_questions(
        questions=template.questions,
        patient_id=patient_id,
        quiz_type="monthly"
    )

    # Each question now has:
    # - text: Humanized text (if applicable)
    # - original_text: Original template text
    # - humanized: Boolean flag

    return humanized_questions
```

---

## Configuration

### Environment Variables

**Location**: `app/core/monthly_quiz_config.py`

| Variable | Description | Default |
|----------|-------------|---------|
| `MONTHLY_QUIZ_VIA_LINK` | Enable link-based quiz access | `true` |
| `MONTHLY_QUIZ_BASE_URL` | Base URL for quiz links | `http://localhost:3001` |
| `MONTHLY_QUIZ_TOKEN_SECRET` | JWT signing secret | **Required** |
| `MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS` | Token validity period | `72` |
| `MONTHLY_QUIZ_MAX_ATTEMPTS` | Max attempts per month | `3` |
| `MONTHLY_QUIZ_RATE_LIMIT_PER_HOUR` | Rate limit per hour | `10` |
| `MONTHLY_QUIZ_ENABLE_ENCRYPTION` | Enable response encryption | `true` |
| `MONTHLY_QUIZ_AUDIT_ENABLED` | Enable audit logging | `true` |
| `MONTHLY_QUIZ_LOCKOUT_MINUTES` | Lockout after failures | `30` |
| `MONTHLY_QUIZ_DEFAULT_DELIVERY` | Default delivery method | `whatsapp` |
| `MONTHLY_QUIZ_DEFAULT_TEMPLATE` | Default template name | `Quizz de Bem-Estar Mensal` |
| `MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION` | Rotate tokens on access | `true` |
| `MONTHLY_QUIZ_ENABLE_REMINDERS` | Enable automatic reminders | `true` |
| `MONTHLY_QUIZ_REMINDER_1_HOURS_BEFORE` | First reminder timing | `24` |
| `MONTHLY_QUIZ_REMINDER_2_HOURS_BEFORE` | Second reminder timing | `6` |

### Gradual Rollout Configuration

```python
# Enable cohort-based rollout
MONTHLY_QUIZ_LINK_PERCENTAGE=50  # 50% of patients
MONTHLY_QUIZ_LINK_ROLLOUT_BY_COHORT=true  # Deterministic by patient_id
MONTHLY_QUIZ_FALLBACK_TO_WHATSAPP=true  # Fallback if link fails
```

### Circuit Breaker Settings

```python
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5  # Failures to open circuit
CIRCUIT_BREAKER_WINDOW_MINUTES=60    # Tracking window
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=300 # Recovery timeout (seconds)
```

### LGPD Compliance Settings

```python
LGPD_CONSENT_REQUIRED=true
LGPD_ANONYMIZE_AFTER_DAYS=730  # 2 years
MONTHLY_QUIZ_DATA_RETENTION_DAYS=365
```

---

## Related Documentation

- [Patient Flow System](/docs/flows/FLOW_SYSTEM_GUIDE.md)
- [Alert Management](/docs/alerts/ALERT_SYSTEM_GUIDE.md)
- [WhatsApp Integration](/docs/messaging/WHATSAPP_GUIDE.md)
- [API Documentation](/docs/api/API_REFERENCE.md)

---

*Last Updated: December 2025*
*Version: 2.0.0*
