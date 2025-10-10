# Quiz System Architecture

**System Architecture Designer Review**
**Date:** 2025-10-09
**Project:** Hormonia Oncology Platform
**Component:** Quiz & Questionnaire System

---

## Executive Summary

The Quiz System is a comprehensive patient assessment platform that enables creation, delivery, response collection, and analysis of medical questionnaires through multiple channels (WhatsApp conversational, web links). It integrates deeply with the Flow Engine for automated scheduling and patient engagement workflows.

**Key Capabilities:**
- Multi-channel quiz delivery (WhatsApp conversational + web links)
- Dynamic question types with validation
- Real-time progress tracking
- Automated scoring and alert generation
- Integration with patient flows and medical reporting

---

## 1. System Architecture Overview

### 1.1 Architectural Layers

```
┌─────────────────────────────────────────────────────────┐
│              FRONTEND PRESENTATION LAYER                 │
│  ┌────────────────┐  ┌────────────────┐                │
│  │  QuizForm.tsx  │  │ Dashboard      │                │
│  │  (Patient UI)  │  │ (Medico View)  │                │
│  └────────────────┘  └────────────────┘                │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   API LAYER                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │  /api/v1/quiz.py - Quiz Template & Session CRUD   │ │
│  │  • Templates: CRUD operations                      │ │
│  │  • Sessions: Start, advance, complete              │ │
│  │  • Responses: Submit, retrieve                     │ │
│  │  • Analytics: Patient & template analytics         │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 SERVICE LAYER                            │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │ QuizTemplate     │  │ QuizSession              │    │
│  │ Service          │  │ Service                  │    │
│  └──────────────────┘  └──────────────────────────┘    │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │ QuizResponse     │  │ QuizAnalytics            │    │
│  │ Service          │  │ Service                  │    │
│  └──────────────────┘  └──────────────────────────┘    │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │ MonthlyQuiz      │  │ Conversational           │    │
│  │ Service          │  │ QuizService              │    │
│  └──────────────────┘  └──────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 INTEGRATION LAYER                        │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │ QuizTrigger      │  │ MonthlyQuizMessage       │    │
│  │ Service          │  │ Integration              │    │
│  └──────────────────┘  └──────────────────────────┘    │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │ WhatsApp         │  │ Flow Engine              │    │
│  │ Integration      │  │ Integration              │    │
│  └──────────────────┘  └──────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 DATA LAYER                               │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │ QuizTemplate     │  │ QuizSession              │    │
│  │ Repository       │  │ Repository               │    │
│  └──────────────────┘  └──────────────────────────┘    │
│  ┌──────────────────┐                                   │
│  │ QuizResponse     │                                   │
│  │ Repository       │                                   │
│  └──────────────────┘                                   │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              DATABASE (PostgreSQL)                       │
│  • quiz_templates    • quiz_sessions                    │
│  • quiz_responses    • patient_flow_states              │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Data Model Architecture

### 2.1 Core Data Models

#### QuizTemplate
**Purpose:** Stores reusable quiz templates with versioning

```python
QuizTemplate {
    id: UUID (PK)
    name: String (max 255)
    version: String (max 50)
    questions: JSONB [
        {
            id: String (unique within template)
            type: QuestionType (enum)
            text: String
            description: Optional[String]
            required: Boolean
            options: Optional[List[QuestionOption]]
            validation_rules: Optional[List[ValidationRule]]
            metadata: Dict[String, Any]
            allow_other: Boolean
        }
    ]
    is_active: Boolean
    created_at: DateTime
    updated_at: DateTime

    # Constraints
    UNIQUE(name, version)  # uq_quiz_template_name_version
}
```

**Question Types:**
```python
QuestionType = Enum(
    MULTIPLE_CHOICE = "multiple_choice"  # Single selection
    SINGLE_CHOICE = "single_choice"       # Radio buttons
    OPEN_TEXT = "open_text"               # Free text
    SCALE = "scale"                        # 1-10 rating
    YES_NO = "yes_no"                      # Boolean
    DATE = "date"                          # Date picker
    NUMBER = "number"                      # Numeric input
    BOOLEAN = "boolean"                    # True/False
    RATING = "rating"                      # Star rating
)
```

#### QuizSession
**Purpose:** Tracks individual quiz completion sessions

```python
QuizSession {
    id: UUID (PK)
    patient_id: UUID (FK -> patients)
    quiz_template_id: UUID (FK -> quiz_templates)
    current_question_index: Integer (default: 0)
    status: String (default: 'pending')
        # Values: pending, in_progress, completed, expired, cancelled
    is_completed: Boolean (default: False)
    started_at: DateTime
    completed_at: Optional[DateTime]
    state_data: JSONB {
        delivery_method: String  # 'whatsapp_conversational' | 'link'
        link_token: Optional[String]
        link_expires_at: Optional[DateTime]
        reminder_sent: Boolean
        attempt_number: Integer
        context: Dict
    }
    created_at: DateTime
    updated_at: DateTime

    # Constraints
    UNIQUE(patient_id, quiz_template_id, is_completed=False)
    # uq_active_quiz_session_per_patient
}
```

#### QuizResponse
**Purpose:** Stores individual question responses

```python
QuizResponse {
    id: UUID (PK)
    patient_id: UUID (FK -> patients)
    quiz_template_id: UUID (FK -> quiz_templates)
    quiz_session_id: Optional[UUID] (FK -> quiz_sessions)
    question_id: String
    question_text: String
    response_type: QuestionType
    response_value: String | List[String]
        # Single value or array for multi-select
    response_metadata: JSONB {
        score: Optional[Integer]
        risk_level: Optional[String]
        validation_errors: Optional[List[String]]
        processing_context: Dict
    }
    other_text: Optional[String]  # For "Other" option
    responded_at: DateTime
    created_at: DateTime
    updated_at: DateTime

    # Constraints
    UNIQUE(quiz_session_id, question_id)
    # uq_quiz_response_per_question_session
}
```

### 2.2 Entity Relationship Diagram

```
┌──────────────────┐         ┌──────────────────┐
│  QuizTemplate    │         │    Patient       │
│                  │         │                  │
│  id (PK)         │         │  id (PK)         │
│  name            │         │  name            │
│  version         │         │  cpf             │
│  questions (JSON)│         │  contact         │
│  is_active       │         └──────────────────┘
└──────────────────┘                 │
         │                           │
         │                           │
         │    ┌──────────────────────┘
         │    │
         ▼    ▼
┌────────────────────────────────────┐
│        QuizSession                 │
│                                    │
│  id (PK)                          │
│  patient_id (FK)                  │
│  quiz_template_id (FK)            │
│  current_question_index           │
│  status                           │
│  is_completed                     │
│  state_data (JSON)                │
│  started_at                       │
│  completed_at                     │
└────────────────────────────────────┘
                │
                │
                ▼
┌────────────────────────────────────┐
│        QuizResponse                │
│                                    │
│  id (PK)                          │
│  patient_id (FK)                  │
│  quiz_template_id (FK)            │
│  quiz_session_id (FK)             │
│  question_id                      │
│  response_type                    │
│  response_value                   │
│  response_metadata (JSON)         │
│  other_text                       │
│  responded_at                     │
└────────────────────────────────────┘
```

---

## 3. Quiz Lifecycle State Machine

### 3.1 Session States

```
┌─────────────┐
│   PENDING   │  Initial state when quiz is triggered
└─────────────┘
       │
       │ Start session
       ▼
┌─────────────┐
│ IN_PROGRESS │  Patient actively answering questions
└─────────────┘
       │
       ├─── Advance question → (loops)
       │
       ├─── Complete all questions
       │         ▼
       │    ┌──────────┐
       │    │COMPLETED │  All questions answered
       │    └──────────┘
       │
       ├─── Timeout (48hrs) or Link expiry
       │         ▼
       │    ┌──────────┐
       │    │ EXPIRED  │  Session expired, may trigger fallback
       │    └──────────┘
       │
       └─── User cancels
                ▼
           ┌──────────┐
           │CANCELLED │  Explicitly cancelled
           └──────────┘
```

### 3.2 Lifecycle Flow

```
┌──────────────────────────────────────────────────────┐
│ 1. TRIGGER                                           │
│    • Flow Engine reaches day 30 (monthly quiz)       │
│    • Manual trigger by physician                     │
│    • Scheduled reminder                              │
└──────────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ 2. DELIVERY METHOD DECISION                          │
│    IF patient.preferred_method == "link":            │
│       → Generate link quiz                           │
│    ELSE:                                             │
│       → Conversational WhatsApp quiz                 │
└──────────────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│  LINK DELIVERY   │    │ CONVERSATIONAL   │
│                  │    │  DELIVERY        │
│ • Generate token │    │ • Send Q1 via WA │
│ • Send link msg  │    │ • Wait response  │
│ • Set expiry 24h │    │ • Process answer │
└──────────────────┘    │ • Send Q2...     │
        │               └──────────────────┘
        │                        │
        ▼                        │
┌──────────────────┐             │
│ LINK MONITORING  │             │
│ • Check expiry   │             │
│ • Send reminders │             │
│ • Fallback to WA │             │
└──────────────────┘             │
        │                        │
        └────────┬───────────────┘
                 ▼
┌──────────────────────────────────────────────────────┐
│ 3. RESPONSE COLLECTION                               │
│    • Validate response format                        │
│    • Save to quiz_responses                          │
│    • Update session state                            │
│    • Advance to next question                        │
└──────────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ 4. COMPLETION                                        │
│    • Mark session as completed                       │
│    • Calculate scores/risk levels                    │
│    • Generate medical report                         │
│    • Trigger alerts if needed                        │
│    • Resume flow engine                              │
└──────────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│ 5. POST-PROCESSING                                   │
│    • Store analytics data                            │
│    • Notify physicians (if flagged)                  │
│    • Update patient metrics                          │
│    • Schedule next quiz (if recurring)               │
└──────────────────────────────────────────────────────┘
```

---

## 4. Question Type System

### 4.1 Question Type Definitions

| Type | Input | Validation | Use Case |
|------|-------|------------|----------|
| `multiple_choice` | Radio buttons | Must select one option | "Qual seu tipo de tratamento?" |
| `single_choice` | Radio buttons | Must select one | "Escolha uma opção" |
| `open_text` | Textarea | Min/max length | "Descreva seus sintomas" |
| `scale` | Slider (1-10) | Within min/max range | "Nível de dor (1-10)" |
| `yes_no` | Boolean toggle | Yes/No only | "Teve náusea esta semana?" |
| `date` | Date picker | Valid date format | "Data do último tratamento" |
| `number` | Number input | Numeric validation | "Quantos dias de febre?" |
| `boolean` | Checkbox | True/False | "Aceita termos" |
| `rating` | Star rating | 1-5 stars | "Avalie sua experiência" |

### 4.2 Question Validation System

```python
ValidationRule {
    type: String  # "required", "min_length", "max_length", "range", "pattern"
    value: Union[String, Int, Float, List]
    message: String  # Error message if validation fails
}

# Example validation rules
[
    {
        "type": "required",
        "value": true,
        "message": "Esta pergunta é obrigatória"
    },
    {
        "type": "min_length",
        "value": 10,
        "message": "Mínimo de 10 caracteres"
    },
    {
        "type": "range",
        "value": [1, 10],
        "message": "Valor deve estar entre 1 e 10"
    }
]
```

### 4.3 Response Processing

```python
# Backend validation flow
def validate_quiz_response(question: QuizQuestion, response_value: Any) -> ValidationResult:
    """
    Validates quiz response against question definition.

    Validation Steps:
    1. Check question type matches response format
    2. Apply validation rules
    3. Validate "other" text if applicable
    4. Check required constraints

    Returns:
        ValidationResult with is_valid, errors, warnings
    """

    # Type validation
    if question.type in [QuestionType.MULTIPLE_CHOICE, QuestionType.SINGLE_CHOICE]:
        if question.options and response_value not in [opt.value for opt in question.options]:
            if not (question.allow_other and response_value in ["other", "outra"]):
                return ValidationResult(is_valid=False, errors=["Opção inválida"])

    # Required validation
    if question.required and not response_value:
        return ValidationResult(is_valid=False, errors=["Campo obrigatório"])

    # Custom validation rules
    for rule in question.validation_rules:
        if not _apply_validation_rule(rule, response_value):
            return ValidationResult(is_valid=False, errors=[rule.message])

    return ValidationResult(is_valid=True)
```

---

## 5. Scoring and Alert System

### 5.1 Scoring Architecture

The quiz system supports multiple scoring strategies:

```python
# Scoring metadata in question options
QuestionOption {
    id: "opt_1"
    text: "Nenhuma dor"
    value: 0
    is_correct: None  # For knowledge quizzes
    score_weight: 0   # For symptom severity
}

# Response metadata includes score
QuizResponse.response_metadata {
    "score": 0,
    "risk_level": "low",  # low, medium, high, critical
    "alert_triggered": false,
    "score_calculation": {
        "base_score": 0,
        "weighted_score": 0,
        "threshold_exceeded": false
    }
}
```

### 5.2 Alert Generation Logic

```python
# Alert trigger conditions
ALERT_THRESHOLDS = {
    "pain_level": {
        "high": 7,      # Score >= 7 triggers high priority alert
        "critical": 9   # Score >= 9 triggers immediate alert
    },
    "nausea_frequency": {
        "high": 4,      # 4+ days per week
        "critical": 7   # Daily
    },
    "weight_loss": {
        "high": 5,      # 5% body weight
        "critical": 10  # 10% body weight
    }
}

async def process_quiz_completion(session: QuizSession, responses: List[QuizResponse]):
    """
    Processes completed quiz and generates alerts.

    Alert Generation Flow:
    1. Calculate aggregate scores
    2. Identify threshold violations
    3. Create alerts for physician review
    4. Send notifications
    5. Update patient risk profile
    """

    aggregate_score = calculate_aggregate_score(responses)
    risk_assessment = assess_risk_level(aggregate_score)

    if risk_assessment.level in ["high", "critical"]:
        alert = create_alert(
            patient_id=session.patient_id,
            alert_type="quiz_risk_flagged",
            priority=risk_assessment.level,
            title=f"{risk_assessment.level.upper()} Risk Detected in Monthly Quiz",
            message=risk_assessment.summary,
            metadata={
                "quiz_session_id": session.id,
                "aggregate_score": aggregate_score,
                "flagged_questions": risk_assessment.flagged_questions,
                "requires_immediate_action": risk_assessment.level == "critical"
            }
        )

        # Notify physicians
        await notify_care_team(alert)
```

---

## 6. Integration Architecture

### 6.1 WhatsApp Integration

#### Conversational Quiz Flow

```python
# app/services/quiz_flow_integration.py - ConversationalQuizService

class ConversationalQuizService:
    """
    Manages conversational quiz delivery via WhatsApp.

    Key Features:
    • Sequential question delivery
    • Real-time response processing
    • Context preservation across messages
    • Error handling and retry logic
    """

    async def send_next_question(
        self,
        patient_id: UUID,
        session: QuizSession,
        question_index: int
    ) -> Dict[str, Any]:
        """
        Sends next quiz question via WhatsApp.

        Message Format:
        ┌──────────────────────────────────────┐
        │ 📋 Questionário Mensal - Pergunta 3/10│
        │                                      │
        │ Como está seu nível de dor hoje?     │
        │                                      │
        │ 1️⃣ Nenhuma dor                       │
        │ 2️⃣ Dor leve                          │
        │ 3️⃣ Dor moderada                      │
        │ 4️⃣ Dor intensa                       │
        │ 5️⃣ Dor insuportável                  │
        │                                      │
        │ Responda com o número da opção       │
        └──────────────────────────────────────┘
        """

        question = session.template.questions[question_index]

        # Format question message
        message_content = self._format_question_message(
            question=question,
            question_number=question_index + 1,
            total_questions=len(session.template.questions)
        )

        # Send via WhatsApp
        message = await self.whatsapp_service.send_message(
            patient_id=patient_id,
            content=message_content,
            metadata={
                "quiz_session_id": str(session.id),
                "question_index": question_index,
                "question_id": question.id,
                "expected_response_type": question.type
            }
        )

        return {"success": True, "message_id": message.id}

    async def process_quiz_response(
        self,
        patient_id: UUID,
        response_text: str,
        message_metadata: Dict
    ) -> Dict[str, Any]:
        """
        Processes patient response to quiz question.

        Processing Flow:
        1. Get active quiz session
        2. Parse response based on question type
        3. Validate response
        4. Save to quiz_responses
        5. Advance to next question OR complete quiz
        6. Return next action
        """

        session = self.quiz_session_service.get_active_session(patient_id)
        if not session:
            return {"success": False, "error": "No active quiz session"}

        current_question = session.template.questions[session.current_question_index]

        # Parse and validate response
        parsed_response = self._parse_response(response_text, current_question)
        validation_result = self._validate_response(parsed_response, current_question)

        if not validation_result.is_valid:
            # Send error message and retry
            await self._send_validation_error(patient_id, validation_result.errors)
            return {"success": False, "action": "retry", "errors": validation_result.errors}

        # Save response
        quiz_response = await self.quiz_response_service.create_response({
            "patient_id": patient_id,
            "quiz_template_id": session.quiz_template_id,
            "quiz_session_id": session.id,
            "question_id": current_question.id,
            "question_text": current_question.text,
            "response_type": current_question.type,
            "response_value": parsed_response,
            "responded_at": datetime.utcnow()
        })

        # Check if quiz is complete
        if session.current_question_index + 1 >= len(session.template.questions):
            await self._complete_quiz(session)
            return {"success": True, "action": "quiz_completed"}
        else:
            # Advance to next question
            await self.quiz_session_service.advance_session(session.id)
            await self.send_next_question(
                patient_id=patient_id,
                session=session,
                question_index=session.current_question_index + 1
            )
            return {"success": True, "action": "next_question"}
```

#### Link-based Quiz Flow

```python
# app/services/monthly_quiz_service.py - MonthlyQuizService

class MonthlyQuizService:
    """
    Manages link-based quiz delivery.

    Features:
    • Secure token generation
    • Expiry management (24 hours)
    • Reminder scheduling
    • Fallback to conversational
    """

    async def generate_quiz_link(
        self,
        patient_id: UUID,
        template_id: UUID,
        expires_in_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Generates secure quiz link and sends to patient.

        Link Format:
        https://app.hormonia.com/quiz/{session_id}?token={secure_token}

        Returns:
            {
                "session_id": UUID,
                "link": String,
                "expires_at": DateTime,
                "message_sent": Boolean
            }
        """

        # Create quiz session
        session = await self.quiz_session_service.start_quiz_session({
            "patient_id": patient_id,
            "quiz_template_id": template_id
        })

        # Generate secure token
        token = self._generate_secure_token()
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

        # Update session with link metadata
        session.state_data.update({
            "delivery_method": "link",
            "link_token": token,
            "link_expires_at": expires_at.isoformat(),
            "reminder_sent": False
        })

        # Generate link
        quiz_link = f"{self.base_url}/quiz/{session.id}?token={token}"

        # Send link via WhatsApp
        message_content = f"""
📋 **Questionário Mensal Disponível**

Olá! É hora de responder seu questionário mensal de acompanhamento.

🔗 Acesse aqui: {quiz_link}

⏰ O link expira em 24 horas
📊 Leva aproximadamente 5-10 minutos

Sua saúde é nossa prioridade! 💚
        """

        await self.whatsapp_service.send_message(
            patient_id=patient_id,
            content=message_content,
            metadata={
                "quiz_session_id": str(session.id),
                "link": quiz_link,
                "expires_at": expires_at.isoformat()
            }
        )

        # Schedule reminder (18 hours later)
        self._schedule_reminder(session.id, hours_before_expiry=6)

        return {
            "session_id": session.id,
            "link": quiz_link,
            "expires_at": expires_at,
            "message_sent": True
        }

    async def handle_link_expiration(self, session_id: UUID):
        """
        Handles quiz link expiration.

        Expiration Flow:
        1. Mark session as expired
        2. Check if quiz is critical
        3. If critical: Trigger conversational fallback
        4. If non-critical: Schedule for next cycle
        """

        session = self.quiz_session_service.get_session(session_id)

        if not session or session.is_completed:
            return  # Already handled

        # Mark as expired
        session.status = "expired"
        session.state_data["expiration_reason"] = "link_timeout"

        # Check criticality
        if self._is_critical_quiz(session):
            # Trigger conversational fallback
            await self.quiz_trigger_service.trigger_conversational_quiz(
                patient_id=session.patient_id,
                template_id=session.quiz_template_id,
                reason="Link expired - critical assessment"
            )
        else:
            # Log for next cycle
            logger.info(f"Quiz link expired for patient {session.patient_id} - non-critical")
```

### 6.2 Flow Engine Integration

```python
# app/services/quiz_flow_integration.py - QuizTriggerService

class QuizTriggerService:
    """
    Integrates quiz system with Flow Engine.

    Responsibilities:
    • Trigger quizzes based on flow state
    • Pause flow during quiz completion
    • Resume flow after completion
    • Handle quiz failures
    """

    async def trigger_quiz_from_flow(
        self,
        flow_state: PatientFlowState,
        quiz_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Triggers quiz when flow reaches quiz day.

        Flow Integration:
        ┌────────────────┐
        │  Flow Day 29   │
        └────────────────┘
                │
                ▼
        ┌────────────────┐
        │  Flow Day 30   │  ← Quiz trigger point
        │  (PAUSED)      │
        └────────────────┘
                │
                │ Quiz triggered
                ▼
        ┌────────────────┐
        │  Quiz Active   │
        │  (Flow paused) │
        └────────────────┘
                │
                │ Quiz completed
                ▼
        ┌────────────────┐
        │  Flow Day 31   │  ← Flow resumed
        └────────────────┘
        """

        # Pause flow
        self.flow_service.pause_flow(flow_state.id, reason="quiz_in_progress")

        # Get patient preferences
        patient = self.patient_service.get_patient(flow_state.patient_id)
        delivery_method = patient.preferences.get("quiz_delivery_method", "link")

        # Trigger quiz based on delivery method
        if delivery_method == "link":
            result = await self.monthly_quiz_service.generate_quiz_link(
                patient_id=flow_state.patient_id,
                template_id=quiz_info["template_id"]
            )
        else:
            result = await self.conversational_quiz_service.start_conversational_quiz(
                patient_id=flow_state.patient_id,
                template_id=quiz_info["template_id"]
            )

        # Store quiz session reference in flow state
        flow_state.metadata["quiz_session_id"] = str(result["session_id"])

        return result

    async def resume_flow_after_quiz(self, quiz_session: QuizSession):
        """
        Resumes flow after quiz completion.

        Post-Quiz Actions:
        1. Generate medical report
        2. Calculate risk scores
        3. Create alerts if needed
        4. Update flow metadata
        5. Resume flow
        """

        # Get associated flow
        flow_state = self.flow_service.get_flow_by_patient(quiz_session.patient_id)

        if not flow_state:
            logger.warning(f"No flow found for patient {quiz_session.patient_id}")
            return

        # Process quiz results
        quiz_results = await self._process_quiz_results(quiz_session)

        # Update flow metadata
        flow_state.metadata.update({
            "last_quiz_completed": datetime.utcnow().isoformat(),
            "quiz_session_id": str(quiz_session.id),
            "quiz_risk_level": quiz_results["risk_level"],
            "quiz_score": quiz_results["aggregate_score"]
        })

        # Resume flow
        self.flow_service.resume_flow(
            flow_state.id,
            next_day=flow_state.current_day + 1
        )
```

---

## 7. Celery Task Architecture

### 7.1 Quiz Processing Tasks

```python
# app/tasks/quiz_flow.py

# Task Hierarchy
┌──────────────────────────────────────────────────────┐
│            SCHEDULED TASKS (Periodic)                │
├──────────────────────────────────────────────────────┤
│ • check_quiz_triggers_task (every 1 hour)            │
│   └─ Checks flows for quiz trigger conditions       │
│                                                      │
│ • monitor_quiz_links_task (every 1 hour)            │
│   └─ Monitors link expirations and sends reminders  │
│                                                      │
│ • cleanup_expired_quiz_sessions_task (daily)        │
│   └─ Cleans up sessions older than 48 hours         │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│            EVENT-DRIVEN TASKS                        │
├──────────────────────────────────────────────────────┤
│ • send_quiz_question_task                            │
│   Triggered: After patient responds                  │
│   Max retries: 3, Delay: 60s exponential backoff    │
│                                                      │
│ • process_quiz_response_task                        │
│   Triggered: When patient response received          │
│   Max retries: 2, Delay: 30s                        │
│                                                      │
│ • send_quiz_progress_update_task                    │
│   Triggered: Every 3 questions                       │
│   Max retries: 2, Delay: 30s                        │
│                                                      │
│ • generate_quiz_report_task                         │
│   Triggered: On quiz completion                      │
│   Max retries: 2, Delay: 120s                       │
│                                                      │
│ • send_quiz_link_reminder_task                      │
│   Triggered: 18 hours after link sent                │
│   Max retries: 3, Delay: 60s exponential backoff    │
└──────────────────────────────────────────────────────┘
```

### 7.2 Task Execution Flows

#### Conversational Quiz Task Flow

```
Patient responds to WhatsApp question
            │
            ▼
┌─────────────────────────────────┐
│ process_quiz_response_task      │
│ • Validate response             │
│ • Save to quiz_responses        │
│ • Determine next action         │
└─────────────────────────────────┘
            │
            ├─── Response valid
            │         │
            │         ▼
            │    ┌─────────────────────────────────┐
            │    │ Check completion status         │
            │    └─────────────────────────────────┘
            │              │
            │              ├─── More questions
            │              │         │
            │              │         ▼
            │              │    ┌─────────────────────────────────┐
            │              │    │ send_quiz_question_task         │
            │              │    │ • Format next question          │
            │              │    │ • Send via WhatsApp             │
            │              │    └─────────────────────────────────┘
            │              │
            │              └─── All questions answered
            │                         │
            │                         ▼
            │                    ┌─────────────────────────────────┐
            │                    │ generate_quiz_report_task       │
            │                    │ • Calculate scores              │
            │                    │ • Generate medical report       │
            │                    │ • Create alerts                 │
            │                    │ • Resume flow                   │
            │                    └─────────────────────────────────┘
            │
            └─── Response invalid
                      │
                      ▼
                 ┌─────────────────────────────────┐
                 │ Send validation error message   │
                 │ • Explain error                 │
                 │ • Re-send same question         │
                 └─────────────────────────────────┘
```

#### Link Quiz Monitoring Flow

```
┌─────────────────────────────────┐
│ monitor_quiz_links_task         │
│ (Runs every 1 hour)             │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│ Get all active quiz sessions    │
│ with delivery_method = "link"   │
└─────────────────────────────────┘
            │
            ▼
        For each session:
            │
            ├─── Session age < 18 hours
            │         │
            │         └─── No action
            │
            ├─── Session age 18-24 hours
            │         │
            │         ▼
            │    ┌─────────────────────────────────┐
            │    │ send_quiz_link_reminder_task    │
            │    │ • Send reminder WhatsApp        │
            │    │ • Mark reminder_sent = true     │
            │    └─────────────────────────────────┘
            │
            └─── Session age > 24 hours
                      │
                      ▼
                 ┌─────────────────────────────────┐
                 │ handle_link_expiration          │
                 │ • Mark session as expired       │
                 │ • Check criticality             │
                 │ • Trigger fallback if critical  │
                 └─────────────────────────────────┘
```

---

## 8. Frontend Quiz Interface

### 8.1 Component Architecture

```
frontend-hormonia/src/components/quiz/QuizForm.tsx

┌──────────────────────────────────────────────────────┐
│                  QuizForm Component                  │
├──────────────────────────────────────────────────────┤
│                                                      │
│  State Management:                                   │
│  • responses: Record<string, any>                    │
│  • submitResponseMutation: UseMutationResult         │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │          Progress Header Card                  │ │
│  │  • Template name                               │ │
│  │  • Progress bar (X/Y questions)                │ │
│  │  • Percentage complete                         │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │          Question Cards                        │ │
│  │  For each question:                            │ │
│  │    • Question number badge                     │ │
│  │    • Question text + required indicator        │ │
│  │    • Dynamic input component:                  │ │
│  │      - RadioGroup (multiple_choice/yes_no)     │ │
│  │      - Slider (scale)                          │ │
│  │      - Textarea (text)                         │ │
│  │      - Checkbox group (checkbox)               │ │
│  │    • Visual feedback (green when answered)     │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │          Submit Footer Card                    │ │
│  │  • Completion status                           │ │
│  │  • Submit button (disabled if incomplete)      │ │
│  │  • Loading state                               │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### 8.2 User Interaction Flow

```
Patient opens quiz link
         │
         ▼
┌──────────────────────────────────┐
│ API: GET /api/v1/quiz/sessions/  │
│      {session_id}?token={token}  │
│                                  │
│ Returns:                         │
│ • Session metadata               │
│ • Template with all questions    │
│ • Current progress               │
└──────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Render QuizForm                  │
│ • Load all questions at once     │
│ • Initialize empty responses     │
│ • Show progress: 0/N questions   │
└──────────────────────────────────┘
         │
         │ Patient answers questions
         │ (Client-side state only)
         ▼
┌──────────────────────────────────┐
│ Real-time validation             │
│ • Required field checks          │
│ • Format validation              │
│ • Progress indicator updates     │
└──────────────────────────────────┘
         │
         │ Patient clicks "Enviar Questionário"
         ▼
┌──────────────────────────────────┐
│ Frontend validation              │
│ • Check all required answered    │
│ • Validate response formats      │
│ • Show errors if invalid         │
└──────────────────────────────────┘
         │
         │ All valid
         ▼
┌──────────────────────────────────┐
│ API: POST /api/v1/quiz/responses │
│                                  │
│ Payload:                         │
│ {                                │
│   session_id: UUID,              │
│   responses: {                   │
│     "q1": "answer1",             │
│     "q2": "answer2",             │
│     ...                          │
│   }                              │
│ }                                │
└──────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Backend Processing               │
│ • Validate each response         │
│ • Save to quiz_responses (bulk)  │
│ • Mark session as completed      │
│ • Trigger report generation      │
│ • Resume flow                    │
└──────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Success Response                 │
│ • Show success toast             │
│ • Invalidate query cache         │
│ • Call onComplete callback       │
│ • Redirect or close              │
└──────────────────────────────────┘
```

### 8.3 Question Rendering Logic

```typescript
// frontend-hormonia/src/components/quiz/QuizForm.tsx

const renderQuestion = (question: Question) => {
  const value = responses[question.id]

  switch (question.type) {
    case 'multiple_choice':
      // Radio buttons for single selection
      return (
        <RadioGroup
          value={value || ''}
          onValueChange={(newValue) => handleResponseChange(question.id, newValue)}
        >
          {question.options?.map((option, index) => (
            <div key={index} className="flex items-center space-x-2">
              <RadioGroupItem value={option} id={`${question.id}-${index}`} />
              <Label htmlFor={`${question.id}-${index}`}>{option}</Label>
            </div>
          ))}
        </RadioGroup>
      )

    case 'scale':
      // Slider for 1-10 scale questions
      const scaleValue = value || question.min || 1
      return (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500">{question.min}</span>
            <span className="font-medium text-lg">{scaleValue}</span>
            <span className="text-sm text-gray-500">{question.max}</span>
          </div>
          <Slider
            value={[scaleValue]}
            onValueChange={(newValue) => handleResponseChange(question.id, newValue[0])}
            min={question.min || 1}
            max={question.max || 10}
            step={1}
          />
        </div>
      )

    case 'text':
      // Textarea for open-ended responses
      return (
        <Textarea
          value={value || ''}
          onChange={(e) => handleResponseChange(question.id, e.target.value)}
          placeholder="Digite sua resposta..."
          rows={4}
        />
      )

    case 'checkbox':
      // Multiple selection checkboxes
      const checkboxValues = value || []
      return (
        <div className="space-y-2">
          {question.options?.map((option, index) => (
            <div key={index} className="flex items-center space-x-2">
              <Checkbox
                id={`${question.id}-${index}`}
                checked={checkboxValues.includes(option)}
                onCheckedChange={(checked) => {
                  if (checked) {
                    handleResponseChange(question.id, [...checkboxValues, option])
                  } else {
                    handleResponseChange(question.id, checkboxValues.filter(v => v !== option))
                  }
                }}
              />
              <Label htmlFor={`${question.id}-${index}`}>{option}</Label>
            </div>
          ))}
        </div>
      )
  }
}
```

---

## 9. Analytics and Reporting

### 9.1 Analytics Data Model

```python
# app/schemas/quiz.py

class QuizAnalytics(BaseModel):
    """Quiz template analytics."""
    quiz_template_id: UUID
    total_responses: int
    completion_rate: float  # Percentage
    average_completion_time: Optional[float]  # Minutes
    question_analytics: List[Dict[str, Any]]
    trends: Dict[str, Any]

class PatientQuizAnalytics(BaseModel):
    """Patient-specific quiz analytics."""
    patient_id: UUID
    total_quizzes_completed: int
    completion_rate: float
    average_score: Optional[float]
    recent_activity: List[Dict[str, Any]]
    trends: Dict[str, Any]
```

### 9.2 Analytics Endpoints

```python
# GET /api/v1/quiz/analytics/patient/{patient_id}
{
  "patient_id": "uuid",
  "total_quizzes_completed": 12,
  "completion_rate": 92.3,  # 12/13 quizzes
  "average_score": 7.4,
  "recent_activity": [
    {
      "quiz_session_id": "uuid",
      "template_name": "Monthly Checkup",
      "completed_at": "2025-10-01T10:30:00Z",
      "score": 8,
      "risk_level": "low"
    }
  ],
  "trends": {
    "score_trend": "improving",  # improving, stable, declining
    "completion_time_trend": "stable",
    "risk_level_history": ["low", "low", "medium", "low"]
  }
}

# GET /api/v1/quiz/analytics/template/{template_id}
{
  "quiz_template_id": "uuid",
  "total_responses": 450,
  "completion_rate": 87.6,
  "average_completion_time": 8.5,  # minutes
  "question_analytics": [
    {
      "question_id": "q1",
      "question_text": "Como está seu nível de dor?",
      "response_distribution": {
        "Nenhuma dor": 45,
        "Dor leve": 120,
        "Dor moderada": 180,
        "Dor intensa": 85,
        "Dor insuportável": 20
      },
      "average_score": 6.2,
      "skip_rate": 2.3  # Percentage
    }
  ],
  "trends": {
    "monthly_completion_trend": [
      {"month": "2025-07", "completions": 145},
      {"month": "2025-08", "completions": 152},
      {"month": "2025-09", "completions": 153}
    ]
  }
}
```

### 9.3 Medical Report Generation

```python
# app/services/report.py

class ReportService:
    """
    Generates medical reports from quiz responses.
    """

    def generate_quiz_report(self, report_data: Dict[str, Any]) -> Report:
        """
        Generates comprehensive medical report from quiz.

        Report Sections:
        1. Patient Information
        2. Assessment Summary
        3. Risk Indicators
        4. Detailed Responses
        5. Trend Analysis
        6. Recommendations
        """

        patient_id = report_data["patient_id"]
        quiz_session_id = report_data["quiz_session_id"]
        responses = report_data["responses"]

        # Calculate aggregate metrics
        risk_assessment = self._assess_risk_level(responses)
        symptom_summary = self._summarize_symptoms(responses)
        trend_analysis = self._analyze_trends(patient_id, responses)

        # Generate report content
        report_content = {
            "patient_id": patient_id,
            "quiz_session_id": quiz_session_id,
            "generated_at": datetime.utcnow().isoformat(),

            "summary": {
                "overall_risk_level": risk_assessment["level"],
                "aggregate_score": risk_assessment["score"],
                "flagged_symptoms": risk_assessment["flagged_symptoms"],
                "requires_immediate_attention": risk_assessment["critical"]
            },

            "detailed_assessment": {
                "pain_level": symptom_summary["pain"],
                "nausea_frequency": symptom_summary["nausea"],
                "fatigue_level": symptom_summary["fatigue"],
                "appetite_changes": symptom_summary["appetite"],
                "weight_changes": symptom_summary["weight"],
                "emotional_wellbeing": symptom_summary["emotional"]
            },

            "trends": {
                "pain_trend": trend_analysis["pain_trend"],
                "overall_trend": trend_analysis["overall_trend"],
                "comparison_to_previous": trend_analysis["comparison"]
            },

            "recommendations": self._generate_recommendations(risk_assessment, symptom_summary),

            "responses": [
                {
                    "question": r.question_text,
                    "response": r.response_value,
                    "score": r.response_metadata.get("score"),
                    "risk_flag": r.response_metadata.get("risk_level")
                }
                for r in responses
            ]
        }

        # Store report
        report = Report(
            patient_id=patient_id,
            report_type="monthly_quiz_assessment",
            content=report_content,
            metadata={
                "quiz_session_id": str(quiz_session_id),
                "template_name": report_data.get("template_name"),
                "generated_by": "automated_quiz_processor"
            }
        )

        self.db.add(report)
        self.db.commit()

        return report
```

---

## 10. Security and Privacy

### 10.1 Access Control

```python
# API endpoint security

@router.post("/sessions", response_model=QuizSessionResponse)
async def start_quiz_session(
    session_data: QuizSessionCreate,
    current_user: User = Depends(get_current_user),  # Authentication
    patient_service: PatientService = Depends(get_patient_service)
) -> QuizSessionResponse:
    """
    Start quiz session with access control.

    Security Checks:
    1. User is authenticated
    2. User has permission to create quiz for patient
    3. Patient exists and is active
    4. Template exists and is active
    """

    # Validate patient access
    await validate_patient_access(session_data.patient_id, current_user, patient_service)

    # Proceed with session creation
    ...
```

### 10.2 Token Security (Link Quizzes)

```python
class MonthlyQuizService:
    """
    Secure token generation and validation.
    """

    def _generate_secure_token(self) -> str:
        """
        Generates cryptographically secure token.

        Token format:
        • 32 bytes of random data
        • URL-safe base64 encoding
        • Unique per session
        """
        return secrets.token_urlsafe(32)

    def validate_quiz_token(self, session_id: UUID, token: str) -> bool:
        """
        Validates quiz access token.

        Validation:
        1. Token matches session token
        2. Session is not completed
        3. Token has not expired
        4. Session belongs to expected patient
        """

        session = self.quiz_session_service.get_session(session_id)

        if not session:
            return False

        # Constant-time comparison to prevent timing attacks
        stored_token = session.state_data.get("link_token")
        if not secrets.compare_digest(stored_token, token):
            return False

        # Check expiration
        expires_at = datetime.fromisoformat(session.state_data["link_expires_at"])
        if datetime.utcnow() > expires_at:
            return False

        # Check completion status
        if session.is_completed:
            return False

        return True
```

### 10.3 Data Privacy

**LGPD/GDPR Compliance:**

1. **Data Minimization:** Only collect necessary quiz responses
2. **Purpose Limitation:** Quiz data used only for medical assessment
3. **Retention:** Quiz responses retained per medical record requirements
4. **Patient Rights:** Patients can view/export their quiz history
5. **Anonymization:** Analytics aggregate data without patient identifiers

```python
# Patient data export (LGPD Article 18)
@router.get("/export/patient/{patient_id}")
async def export_patient_quiz_data(
    patient_id: UUID,
    current_user: User = Depends(get_current_user)
) -> FileResponse:
    """
    Export patient's complete quiz history.

    Exported Data:
    • All quiz sessions
    • All responses
    • Analytics
    • Medical reports

    Format: JSON (structured) or PDF (human-readable)
    """
    ...
```

---

## 11. Performance Optimization

### 11.1 Database Query Optimization

```python
# app/repositories/quiz.py

class QuizResponseRepository(BaseRepository[QuizResponse]):
    """
    Optimized quiz response queries.
    """

    def get_session_responses(
        self,
        session_id: UUID,
        eager_load: bool = True
    ) -> List[QuizResponse]:
        """
        Get all responses for a quiz session.

        Optimization:
        • Single query with eager loading
        • Indexed on session_id
        • Ordered by question_index for display
        """

        query = self.db.query(QuizResponse).filter(
            QuizResponse.quiz_session_id == session_id
        )

        if eager_load:
            query = query.options(
                joinedload(QuizResponse.patient),
                joinedload(QuizResponse.quiz_template)
            )

        return query.order_by(QuizResponse.created_at).all()
```

### 11.2 Caching Strategy

```python
# Redis caching for frequently accessed data

class QuizTemplateService:
    """
    Quiz template service with caching.
    """

    @cache_result(ttl=3600, key_prefix="quiz_template")
    def get_template(self, template_id: UUID) -> QuizTemplateResponse:
        """
        Get quiz template with caching.

        Cache Strategy:
        • TTL: 1 hour
        • Key: quiz_template:{template_id}
        • Invalidate on template update
        """

        template = self.template_repository.get(template_id)
        return QuizTemplateResponse.from_orm(template)

    def update_template(self, template_id: UUID, data: QuizTemplateUpdate):
        """
        Update template and invalidate cache.
        """

        # Update database
        template = self.template_repository.update(template_id, data)

        # Invalidate cache
        cache_key = f"quiz_template:{template_id}"
        redis_client.delete(cache_key)

        return template
```

### 11.3 Frontend Performance

```typescript
// React Query optimization

const QuizPage = () => {
  // Prefetch quiz session on page load
  const { data: session, isLoading } = useQuery({
    queryKey: ['quiz-session', sessionId],
    queryFn: () => apiClient.quiz.getSession(sessionId),
    staleTime: 5 * 60 * 1000,  // 5 minutes
    refetchOnWindowFocus: false  // Don't refetch on focus
  })

  // Optimistic updates for better UX
  const submitMutation = useMutation({
    mutationFn: (responses) => apiClient.quiz.submitResponse(sessionId, responses),
    onMutate: async (responses) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries(['quiz-session', sessionId])

      // Snapshot previous value
      const previousSession = queryClient.getQueryData(['quiz-session', sessionId])

      // Optimistically update
      queryClient.setQueryData(['quiz-session', sessionId], (old) => ({
        ...old,
        responses: responses,
        status: 'completed'
      }))

      return { previousSession }
    },
    onError: (err, variables, context) => {
      // Rollback on error
      queryClient.setQueryData(['quiz-session', sessionId], context.previousSession)
    },
    onSettled: () => {
      // Refetch after mutation
      queryClient.invalidateQueries(['quiz-session', sessionId])
    }
  })
}
```

---

## 12. Error Handling and Resilience

### 12.1 Backend Error Handling

```python
# API endpoint error handling

@router.post("/sessions", response_model=QuizSessionResponse)
@handle_service_exceptions
async def start_quiz_session(
    session_data: QuizSessionCreate,
    service: QuizSessionService = Depends(get_quiz_session_service),
    current_user: User = Depends(get_current_user)
) -> QuizSessionResponse:
    """
    Start quiz session with comprehensive error handling.

    Error Scenarios:
    1. Patient not found → 404
    2. Template not found → 404
    3. Active session exists → 409 Conflict
    4. Database error → 500
    5. Validation error → 400
    """

    try:
        # Validation
        if not session_data.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient ID is required"
            )

        # Business logic validation
        existing_session = service.get_active_session(session_data.patient_id)
        if existing_session and existing_session.quiz_template_id == session_data.quiz_template_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient already has an active session. Session ID: {existing_session.id}"
            )

        return await service.start_quiz_session(session_data)

    except IntegrityError as e:
        if "uq_active_quiz_session_per_patient" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Patient already has an active quiz session for this template"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error occurred"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
```

### 12.2 Celery Task Retry Logic

```python
# Resilient task execution with exponential backoff

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_quiz_question_task(self, patient_id: str, quiz_session_id: str, question_index: int):
    """
    Send quiz question with retry logic.

    Retry Strategy:
    • Max retries: 3
    • Backoff: Exponential (1min, 2min, 4min)
    • On final failure: Log error, create alert
    """

    try:
        # Question sending logic
        ...

    except Exception as exc:
        logger.error(f"Error in send_quiz_question_task: {exc}")

        if self.request.retries < self.max_retries:
            # Exponential backoff
            delay = 60 * (2 ** self.request.retries)
            raise self.retry(countdown=delay, exc=exc)
        else:
            # Final failure - create alert for monitoring
            logger.error(f"Quiz question task failed after {self.max_retries} retries: {exc}")

            # Create system alert
            alert_service.create_system_alert(
                alert_type="quiz_delivery_failure",
                severity="high",
                message=f"Failed to send quiz question to patient {patient_id}",
                metadata={
                    "patient_id": patient_id,
                    "quiz_session_id": quiz_session_id,
                    "question_index": question_index,
                    "error": str(exc)
                }
            )

            return {
                'success': False,
                'error': str(exc),
                'final_failure': True
            }
```

### 12.3 Frontend Error Boundaries

```typescript
// Error handling in React components

const QuizForm = ({ session }: QuizFormProps) => {
  const { toast } = useToast()

  const submitMutation = useMutation({
    mutationFn: (responses) => apiClient.quiz.submitResponse(session.id, responses),
    onError: (error: any) => {
      // User-friendly error messages
      const errorMessage = {
        400: "Por favor, verifique suas respostas e tente novamente.",
        401: "Sua sessão expirou. Por favor, faça login novamente.",
        404: "Questionário não encontrado.",
        409: "Você já respondeu este questionário.",
        500: "Erro ao salvar respostas. Tente novamente em alguns minutos."
      }[error.status] || "Ocorreu um erro inesperado."

      toast({
        title: 'Erro ao enviar questionário',
        description: errorMessage,
        variant: 'destructive'
      })

      // Log to monitoring service
      logger.error('Quiz submission error', {
        sessionId: session.id,
        error: error,
        responses: responses
      })
    }
  })
}
```

---

## 13. Monitoring and Observability

### 13.1 Key Metrics

```python
# Metrics to track

QUIZ_METRICS = {
    # Delivery Metrics
    "quiz_triggered_total": Counter("Number of quizzes triggered"),
    "quiz_delivered_total": Counter("Number of quizzes successfully delivered"),
    "quiz_delivery_method": Counter("Delivery method distribution", ["method"]),

    # Completion Metrics
    "quiz_started_total": Counter("Number of quiz sessions started"),
    "quiz_completed_total": Counter("Number of quiz sessions completed"),
    "quiz_abandoned_total": Counter("Number of quiz sessions abandoned"),
    "quiz_completion_time": Histogram("Time to complete quiz (minutes)"),

    # Response Metrics
    "quiz_responses_total": Counter("Total quiz responses submitted"),
    "quiz_response_errors_total": Counter("Response validation errors"),

    # Alert Metrics
    "quiz_alerts_generated_total": Counter("Alerts generated from quizzes", ["risk_level"]),

    # Link Metrics (specific to link-based quizzes)
    "quiz_link_sent_total": Counter("Quiz links sent"),
    "quiz_link_opened_total": Counter("Quiz links opened"),
    "quiz_link_expired_total": Counter("Quiz links expired"),
    "quiz_link_reminder_sent_total": Counter("Quiz link reminders sent"),
    "quiz_link_fallback_triggered_total": Counter("Fallback to conversational triggered"),

    # Performance Metrics
    "quiz_question_send_duration": Histogram("Time to send quiz question (seconds)"),
    "quiz_response_processing_duration": Histogram("Time to process quiz response (seconds)")
}
```

### 13.2 Logging Strategy

```python
# Structured logging

import structlog

logger = structlog.get_logger()

# Quiz session logging
logger.info(
    "quiz_session_started",
    patient_id=str(patient_id),
    quiz_session_id=str(session.id),
    template_name=template.name,
    delivery_method=delivery_method,
    flow_day=flow_state.current_day if flow_state else None
)

logger.info(
    "quiz_question_sent",
    patient_id=str(patient_id),
    quiz_session_id=str(session.id),
    question_index=question_index,
    question_id=question.id,
    question_type=question.type,
    delivery_channel="whatsapp"
)

logger.info(
    "quiz_response_received",
    patient_id=str(patient_id),
    quiz_session_id=str(session.id),
    question_id=question.id,
    response_valid=validation_result.is_valid,
    validation_errors=validation_result.errors if not validation_result.is_valid else None
)

logger.info(
    "quiz_completed",
    patient_id=str(patient_id),
    quiz_session_id=str(session.id),
    total_questions=len(template.questions),
    completion_time_minutes=completion_time,
    aggregate_score=aggregate_score,
    risk_level=risk_assessment.level,
    alerts_generated=len(alerts)
)

# Error logging
logger.error(
    "quiz_delivery_failed",
    patient_id=str(patient_id),
    quiz_session_id=str(session.id),
    error=str(exc),
    retry_attempt=self.request.retries,
    max_retries=self.max_retries
)
```

### 13.3 Dashboard Metrics

```
┌─────────────────────────────────────────────────────────┐
│              QUIZ SYSTEM DASHBOARD                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Delivery Performance (Last 24h)                        │
│  ┌─────────────┬─────────────┬─────────────┐          │
│  │  Triggered  │  Delivered  │ Completion  │          │
│  │     156     │     152     │    87.5%    │          │
│  └─────────────┴─────────────┴─────────────┘          │
│                                                         │
│  Delivery Method Distribution                           │
│  ┌────────────────────────────────────────┐            │
│  │  WhatsApp Conversational: 45% ████████ │            │
│  │  Link (Web):              55% ██████████│            │
│  └────────────────────────────────────────┘            │
│                                                         │
│  Average Completion Time                                │
│  ┌────────────────────────────────────────┐            │
│  │  Link:            6.2 minutes           │            │
│  │  Conversational:  8.7 minutes           │            │
│  └────────────────────────────────────────┘            │
│                                                         │
│  Alert Distribution (Last 7 days)                       │
│  ┌────────────────────────────────────────┐            │
│  │  Critical:  12  🔴                      │            │
│  │  High:      34  🟠                      │            │
│  │  Medium:    67  🟡                      │            │
│  │  Low:       89  🟢                      │            │
│  └────────────────────────────────────────┘            │
│                                                         │
│  Link Quiz Performance                                  │
│  ┌────────────────────────────────────────┐            │
│  │  Links sent:       85                   │            │
│  │  Links opened:     78 (91.8%)           │            │
│  │  Links completed:  72 (92.3% of opened) │            │
│  │  Links expired:     7 (8.2%)            │            │
│  │  Fallbacks:         4 (4.7%)            │            │
│  └────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## 14. Architecture Decision Records (ADRs)

### ADR-001: Dual Delivery System (Link + Conversational)

**Context:** Need to support both patient preferences and ensure quiz completion.

**Decision:** Implement dual delivery system:
- Primary: Link-based for convenience
- Fallback: Conversational WhatsApp for reliability

**Rationale:**
- Links provide better UX (answer at own pace, visual UI)
- Conversational ensures completion even if link expires
- Patient preference drives initial delivery method

**Consequences:**
- Increased system complexity (two delivery paths)
- Better patient satisfaction
- Higher completion rates

---

### ADR-002: JSONB for Question Storage

**Context:** Need flexible question schema supporting multiple types.

**Decision:** Store questions as JSONB in `quiz_templates.questions`.

**Rationale:**
- Schema flexibility for different question types
- No need for multiple tables (questions, options, validations)
- PostgreSQL JSONB indexing and querying capabilities
- Simpler versioning (entire template is atomic)

**Consequences:**
- Faster development and easier schema evolution
- Potential for schema validation complexity
- Requires careful validation in application layer

---

### ADR-003: Session-Based Quiz Tracking

**Context:** Need to track quiz progress and support resume capability.

**Decision:** Create `quiz_sessions` table to track individual attempts.

**Rationale:**
- Separates template (reusable) from instance (specific attempt)
- Enables resume functionality
- Tracks delivery method and metadata per session
- Supports analytics per session

**Consequences:**
- Additional table and relationships
- Clear separation of concerns
- Better audit trail
- More complex query patterns

---

### ADR-004: Celery for Async Processing

**Context:** Quiz operations (delivery, processing, reporting) are time-intensive.

**Decision:** Use Celery tasks for all async operations.

**Rationale:**
- Decouples API response from background work
- Enables retry logic and error handling
- Scheduled tasks for monitoring and cleanup
- Better scalability

**Consequences:**
- Requires Redis/RabbitMQ infrastructure
- More complex debugging
- Better system resilience
- Improved API response times

---

## 15. Future Enhancements

### 15.1 Planned Features

1. **Adaptive Quizzes**
   - Skip questions based on previous answers
   - Dynamic question ordering based on risk
   - Personalized question sets per patient condition

2. **Multi-Language Support**
   - Template translations
   - Language preference per patient
   - Automatic language detection

3. **Voice Response Integration**
   - WhatsApp voice message responses
   - Speech-to-text processing
   - Accessibility for patients with visual impairment

4. **Advanced Analytics**
   - Predictive risk modeling
   - Patient cohort analysis
   - Treatment outcome correlation

5. **Gamification**
   - Streaks for consistent completion
   - Achievement badges
   - Progress milestones

### 15.2 Technical Improvements

1. **GraphQL API**
   - More efficient frontend queries
   - Reduce over-fetching
   - Real-time subscriptions for progress

2. **Offline Support**
   - Progressive Web App (PWA)
   - Offline response collection
   - Sync when online

3. **AI-Powered Insights**
   - Automatic report summarization
   - Anomaly detection in responses
   - Personalized recommendations

---

## 16. Testing Strategy

### 16.1 Backend Testing

```python
# Unit Tests
tests/unit/services/test_quiz_service.py
tests/unit/services/test_monthly_quiz_service.py

# Integration Tests
tests/integration/test_quiz_session_integration.py
tests/integration/test_quiz_flow_integration.py

# API Tests
tests/api/test_quiz_endpoints.py
tests/api/test_monthly_quiz_endpoints.py

# Key Test Scenarios
- Create quiz template with various question types
- Start quiz session (link and conversational)
- Submit responses with validation
- Complete quiz and generate report
- Handle link expiration and fallback
- Process quiz in flow context
```

### 16.2 Frontend Testing

```typescript
// Component Tests
tests/unit/components/QuizForm.test.tsx

// Integration Tests
tests/integration/quiz-flow.test.tsx

// E2E Tests
tests/e2e/quiz-completion.spec.ts

// Key Test Scenarios
- Render quiz with all question types
- Validate required questions
- Submit complete quiz
- Handle API errors gracefully
- Progress tracking accuracy
```

---

## 17. Recommendations

### 17.1 Immediate Improvements

1. **Implement Missing Analytics Endpoint**
   - `/api/v1/quiz/analytics/summary` currently returns placeholder data
   - Implement real aggregation queries
   - Add caching for performance

2. **Add Quiz Template Versioning UI**
   - Frontend interface for creating template versions
   - Version comparison tool
   - Migration path for active sessions

3. **Enhance Error Recovery**
   - Dead letter queue for failed tasks
   - Automatic retry with backoff
   - Admin notification for critical failures

4. **Improve Link Expiration Handling**
   - More graceful expiration messages
   - Extend link option (if close to expiry)
   - Better fallback communication

### 17.2 Architectural Improvements

1. **Separate Quiz Microservice**
   - Extract quiz system into independent service
   - API-first design
   - Better scaling and isolation

2. **Event-Driven Architecture**
   - Publish quiz events (started, completed, expired)
   - Enable loosely coupled integrations
   - Better audit trail

3. **Implement Circuit Breaker**
   - Protect WhatsApp integration
   - Graceful degradation
   - Better resilience

4. **Add Rate Limiting**
   - Per-patient quiz frequency limits
   - API rate limiting
   - Prevent abuse

### 17.3 Documentation Improvements

1. **API Documentation**
   - OpenAPI/Swagger specs
   - Example requests/responses
   - Authentication guide

2. **User Documentation**
   - Patient guide for quiz completion
   - Physician guide for quiz management
   - Template creation best practices

3. **Runbooks**
   - Quiz delivery failure troubleshooting
   - Link expiration handling
   - Data recovery procedures

---

## 18. Conclusion

The Quiz System is a well-architected, feature-rich patient assessment platform with strong integration into the broader Hormonia ecosystem. It demonstrates:

**Strengths:**
- ✅ Flexible question type system
- ✅ Dual delivery mechanism (link + conversational)
- ✅ Comprehensive state management
- ✅ Strong integration with Flow Engine
- ✅ Robust error handling and retry logic
- ✅ Detailed analytics capabilities

**Areas for Enhancement:**
- ⚠️ Complete analytics implementation
- ⚠️ Enhanced monitoring and alerting
- ⚠️ Performance optimization (caching, query optimization)
- ⚠️ Better documentation and runbooks

**Critical Dependencies:**
- PostgreSQL (data storage)
- Redis (caching, Celery broker)
- WhatsApp API (message delivery)
- Flow Engine (scheduling integration)
- Celery (async task processing)

The system successfully supports the monthly patient assessment workflow while maintaining flexibility for future enhancements and scale.

---

**Document Version:** 1.0
**Last Updated:** 2025-10-09
**Reviewed By:** System Architecture Designer (Claude Agent)
**Status:** Complete - Ready for Technical Review
