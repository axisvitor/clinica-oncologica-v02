# Response Handling & Validation Flow

## Overview
Quiz responses are processed differently based on delivery mode (link vs conversational) but both converge on the same validation and storage pipeline.

---

## Response Processing Modes

### Mode A: Link-Based (Frontend Submission)

**Frontend → Backend Flow**:
```
Frontend Quiz Interface
  ├─ Patient answers all questions
  ├─ Collect responses in JSON
  └─ Submit via POST /api/quiz-responses

Backend API Endpoint
  ├─ Validate token (JWT)
  ├─ Find session by token hash
  ├─ Validate all responses
  ├─ Save QuizResponse records
  ├─ Complete session
  └─ Return completion status
```

**Response Payload Example**:
```json
{
  "session_token": "jwt_token_here",
  "responses": [
    {
      "question_id": "mood_assessment",
      "response_type": "scale",
      "response_value": "4"
    },
    {
      "question_id": "energy_levels",
      "response_type": "multiple_choice",
      "response_value": "normal"
    },
    {
      "question_id": "side_effects",
      "response_type": "open_text",
      "response_value": "Feeling some nausea but manageable"
    }
  ]
}
```

---

### Mode B: Conversational (Question-by-Question)

**WhatsApp → Backend Flow**:
```
Evolution Webhook Receives Message
  ↓
WebhookHandler.handle_incoming_message()
  ↓
Detect active quiz session
  ├─ Check patient has active session
  ├─ Get current question index
  └─ Extract response text from message
  ↓
ConversationalQuizService.process_quiz_response()
  ├─ Get active session
  ├─ Get current question
  ├─ Validate response for question type
  ├─ Save response OR request clarification
  └─ Send next question OR complete quiz
```

---

## Response Validation Pipeline

### 1. Question Type Detection
```python
current_question = questions[session.current_question_index]
question_type = current_question["type"]  # QuestionType enum

Supported Types:
  - OPEN_TEXT: Any text accepted
  - SCALE: Numbers 1-5
  - MULTIPLE_CHOICE: Match against options
  - YES_NO: Detect affirmative/negative
  - SINGLE_CHOICE: One option from list
```

### 2. Type-Specific Validation

#### SCALE Questions (1-5 Rating)
```python
def _process_question_response(question, response_text):
    # Extract numbers from text
    numbers = re.findall(r'\d+', response_text)

    if numbers:
        scale_value = int(numbers[0])
        if 1 <= scale_value <= 5:
            return {
                "valid": True,
                "value": str(scale_value),
                "type": "scale"
            }

    # Fallback: AI interpretation
    interpreted_value = _interpret_scale_response(response_text, question)

    if interpreted_value:
        return {
            "valid": True,
            "value": str(interpreted_value),
            "type": "scale",
            "interpreted": True
        }

    # Invalid
    return {
        "valid": False,
        "error": "Por favor, responda com um número de 1 a 5"
    }
```

**AI Interpretation (Gemini)**:
```python
async def _interpret_scale_response(response_text, question):
    prompt = f"""
    Analise a resposta do paciente para uma pergunta de escala de 1 a 5:

    Pergunta: {question["text"]}
    Resposta do paciente: "{response_text}"

    Escala:
    1 = Muito ruim/baixo/negativo
    2 = Ruim/baixo/negativo
    3 = Neutro/regular/médio
    4 = Bom/alto/positivo
    5 = Muito bom/alto/positivo

    Retorne apenas o número (1-5) que melhor representa a resposta.
    Se não conseguir interpretar, retorne "INVALID".
    """

    response = await gemini_client.generate_content(prompt)

    if response.strip().isdigit():
        value = int(response.strip())
        if 1 <= value <= 5:
            return value

    return None
```

**Examples**:
```
Input: "Muito mal"           → AI interprets → 1
Input: "Estou me sentindo ok" → AI interprets → 3
Input: "Ótimo!"              → AI interprets → 5
Input: "não sei"             → AI returns     → INVALID
```

---

#### MULTIPLE_CHOICE Questions
```python
def _process_question_response(question, response_text):
    options = question.get("options", [])

    # Direct text matching (case-insensitive)
    for option in options:
        if (response_text.lower() in option["text"].lower() or
            option["text"].lower() in response_text.lower()):
            return {
                "valid": True,
                "value": option["value"],
                "type": "multiple_choice"
            }

    # AI interpretation if no match
    interpreted_option = _interpret_multiple_choice_response(
        response_text, options
    )

    if interpreted_option:
        return {
            "valid": True,
            "value": interpreted_option,
            "type": "multiple_choice",
            "interpreted": True
        }

    # Invalid - show options
    options_text = "\n".join([f"• {opt['text']}" for opt in options])
    return {
        "valid": False,
        "error": f"Por favor, escolha uma das opções:\n{options_text}"
    }
```

**AI Interpretation**:
```python
async def _interpret_multiple_choice_response(response_text, options):
    options_text = "\n".join([
        f"- {opt['value']}: {opt['text']}" for opt in options
    ])

    prompt = f"""
    Analise a resposta do paciente e determine qual opção ela melhor representa:

    Resposta do paciente: "{response_text}"

    Opções disponíveis:
    {options_text}

    Retorne apenas o valor (value) da opção que melhor corresponde.
    Se não conseguir determinar, retorne "INVALID".
    """

    response = await gemini_client.generate_content(prompt)

    if response.strip() != "INVALID":
        option_values = [opt["value"] for opt in options]
        if response.strip() in option_values:
            return response.strip()

    return None
```

**Examples**:
```
Question: "Como estão seus níveis de energia?"
Options: ["very_low", "low", "normal", "high", "very_high"]

Input: "Estou com energia normal"    → "normal"
Input: "Muito cansada"                → AI → "very_low"
Input: "tenho bastante disposição"    → AI → "high"
Input: "xyz123"                       → INVALID
```

---

#### YES_NO Questions
```python
def _process_question_response(question, response_text):
    response_lower = response_text.lower()

    yes_words = ["sim", "yes", "s", "claro", "certamente", "com certeza"]
    no_words = ["não", "nao", "no", "n", "nunca", "jamais"]

    if any(word in response_lower for word in yes_words):
        return {"valid": True, "value": "yes", "type": "yes_no"}
    elif any(word in response_lower for word in no_words):
        return {"valid": True, "value": "no", "type": "yes_no"}
    else:
        return {
            "valid": False,
            "error": "Por favor, responda com 'sim' ou 'não'"
        }
```

**Examples**:
```
Input: "Sim"              → "yes"
Input: "não"              → "no"
Input: "claro que sim"    → "yes"
Input: "de jeito nenhum"  → "no"
Input: "talvez"           → INVALID
```

---

#### OPEN_TEXT Questions
```python
def _process_question_response(question, response_text):
    # Accept any non-empty text
    return {
        "valid": True,
        "value": response_text.strip(),
        "type": "text"
    }
```

**No validation, but metadata enrichment**:
- Sentiment analysis (optional)
- Entity extraction (optional)
- Keyword identification

---

## Response Storage

### Creating QuizResponse Record
```python
response_data = QuizResponseCreate(
    patient_id=patient_id,
    quiz_template_id=session.quiz_template_id,
    quiz_session_id=session.id,
    question_id=current_question["id"],
    question_text=current_question["text"],
    response_type=current_question["type"],
    response_value=processed_response["value"],
    response_metadata={
        "original_text": response_text,
        "processed_value": processed_response["value"],
        "session_id": str(session.id),
        "question_index": session.current_question_index,
        "interpreted": processed_response.get("interpreted", False),
        "ai_used": processed_response.get("interpreted", False)
    },
    responded_at=datetime.now(timezone.utc)
)

await quiz_response_service.create_response(response_data)
```

### Response Metadata Examples

**Scale Response (AI-interpreted)**:
```json
{
  "original_text": "Muito mal mesmo",
  "processed_value": "1",
  "session_id": "uuid",
  "question_index": 0,
  "interpreted": true,
  "ai_used": true,
  "ai_confidence": 0.95
}
```

**Multiple Choice (Direct match)**:
```json
{
  "original_text": "Níveis de energia normais",
  "processed_value": "normal",
  "session_id": "uuid",
  "question_index": 1,
  "interpreted": false,
  "ai_used": false,
  "matched_option": "normal"
}
```

**Open Text (With sentiment)**:
```json
{
  "original_text": "Estou com náuseas leves mas consigo comer",
  "processed_value": "Estou com náuseas leves mas consigo comer",
  "session_id": "uuid",
  "question_index": 3,
  "sentiment": {
    "score": -0.2,
    "magnitude": 0.4,
    "label": "slightly_negative"
  },
  "entities": ["náuseas"],
  "symptoms_detected": ["nausea"]
}
```

---

## Clarification Flow

### When Clarification Needed
```python
if not processed_response["valid"]:
    await _send_clarification_message(
        patient_id,
        current_question,
        processed_response["error"]
    )

    return {
        "success": False,
        "error": processed_response["error"],
        "action": "request_clarification"
    }
```

### Clarification Message
```python
async def _send_clarification_message(
    patient_id, question, error_message
):
    patient = patient_repo.get(patient_id)

    message = message_factory.create_quiz_clarification(
        patient_id=patient_id,
        patient_name=patient.name,
        question=question,
        error_message=error_message
    )

    await message_sender.send_message(message)
```

**Example Clarification Messages**:
```
Scale Question:
"Desculpe, não consegui entender sua resposta. Por favor,
responda com um número de 1 a 5, onde:
1 = Muito mal
2 = Mal
3 = Regular
4 = Bem
5 = Muito bem"

Multiple Choice:
"Por favor, escolha uma das opções abaixo:
• Muito baixos
• Baixos
• Normais
• Altos
• Muito altos"

Yes/No:
"Por favor, responda com 'sim' ou 'não'."
```

### Retry Mechanism
```python
# Track clarification attempts in session metadata
session_metadata = session.session_metadata or {}
question_key = f"question_{session.current_question_index}"

if question_key not in session_metadata:
    session_metadata[question_key] = {
        "clarification_attempts": 0
    }

session_metadata[question_key]["clarification_attempts"] += 1

# Max 3 attempts per question
if session_metadata[question_key]["clarification_attempts"] >= 3:
    # Skip question or use default value
    logger.warning(f"Max clarifications reached for question {question_key}")
    # Handle gracefully (optional: skip question)
```

---

## Response Advancement Logic

### After Valid Response
```python
# Save response
await quiz_response_service.create_response(response_data)

# Check if last question
if session.current_question_index >= len(questions) - 1:
    # Complete quiz
    await _complete_quiz_session(session, patient_id)

    return {
        "success": True,
        "action": "quiz_completed",
        "session_id": str(session.id)
    }
else:
    # Advance to next question
    quiz_session_service.advance_session(session.id)

    # Send next question
    await _send_next_question(
        patient_id,
        session,
        questions,
        session.current_question_index + 1
    )

    return {
        "success": True,
        "action": "next_question",
        "question_index": session.current_question_index + 1
    }
```

### Session Advancement
```python
def advance_session(session_id: UUID):
    session = session_repository.get(session_id)

    # Increment question pointer
    session.current_question = session.current_question + 1
    session.answered_questions = (session.answered_questions or 0) + 1

    # Update session
    db.commit()
    db.refresh(session)

    return session
```

---

## Progress Tracking

### Response Latency Metric
```python
# Calculate time from question sent to response received
if message_metadata and "question_sent_at" in message_metadata:
    question_sent_at = datetime.fromisoformat(
        message_metadata["question_sent_at"]
    )

    response_latency = (
        datetime.now(timezone.utc) - question_sent_at
    ).total_seconds()

    # Record metric
    metrics = await get_quiz_metrics_collector()
    await metrics.record_response_latency(
        template_id=session.quiz_template_id,
        question_id=current_question["id"],
        session_id=session.id,
        latency_seconds=response_latency
    )
```

### Progress Messages
```python
# Send progress update every N questions (e.g., every 3 questions)
if (session.current_question_index + 1) % 3 == 0:
    current = session.answered_questions
    total = len(questions)
    progress_percent = int((current / total) * 100)

    progress_message = (
        f"Você está indo muito bem! 🌟 "
        f"Já respondeu {current} de {total} perguntas "
        f"({progress_percent}% completo). Continue assim! ✨"
    )

    # Send progress update (async task)
    send_quiz_progress_update_task.delay(
        patient_id=str(patient_id),
        quiz_session_id=str(session.id),
        progress_data={
            "current_question": current,
            "total_questions": total
        }
    )
```

---

## Edge Cases & Error Handling

### 1. Duplicate Responses
```sql
-- Database constraint prevents duplicates
CONSTRAINT uq_quiz_response_per_question_session
UNIQUE (quiz_session_id, question_id)
```

**Application handling**:
```python
try:
    await quiz_response_service.create_response(response_data)
except IntegrityError as e:
    if "uq_quiz_response_per_question_session" in str(e):
        # Response already exists for this question
        logger.warning(f"Duplicate response detected: {e}")
        # Update existing response instead
        await quiz_response_service.update_response(...)
```

### 2. Out-of-Order Responses
```python
# Patient sends response for wrong question
if message_metadata.get("question_index") != session.current_question_index:
    # Ignore or handle gracefully
    logger.warning(
        f"Out-of-order response: expected Q{session.current_question_index}, "
        f"got Q{message_metadata.get('question_index')}"
    )

    # Resend current question
    await _send_next_question(
        patient_id,
        session,
        questions,
        session.current_question_index
    )
```

### 3. Session Already Completed
```python
if session.status == "completed":
    # Session already completed
    return {
        "success": False,
        "error": "Quiz already completed",
        "action": "ignore"
    }
```

### 4. Session Expired
```python
if session.is_expired:
    # Session expired
    await quiz_session_service.expire_session(session.id)

    # Notify patient
    await _send_expiration_message(patient_id, session)

    return {
        "success": False,
        "error": "Quiz session expired",
        "action": "expired"
    }
```

### 5. Invalid Session State
```python
if session.current_question_index >= len(questions):
    # Index out of bounds
    logger.error(f"Invalid question index: {session.current_question_index}")

    # Force completion or reset
    await _complete_quiz_session(session, patient_id)
```

---

## Response Normalization

### Before Storage
```python
def _normalize_responses(responses: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {}

    for key, value in responses.items():
        # Handle nested structures
        if isinstance(value, dict):
            if "value" in value:
                value = value["value"]
            elif "response_value" in value:
                value = value["response_value"]

        # Convert string numbers to float
        if isinstance(value, str) and value.replace(".", "", 1).isdigit():
            value = float(value)

        # Normalize boolean strings
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in ("yes", "sim", "true", "1"):
                value = True
            elif value_lower in ("no", "não", "nao", "false", "0"):
                value = False

        normalized[key] = value

    return normalized
```

---

## Next: Alert Evaluation & Follow-ups
See `04_ALERT_EVALUATION_INTEGRATION.md` for quiz-triggered alert generation and follow-up flows.
