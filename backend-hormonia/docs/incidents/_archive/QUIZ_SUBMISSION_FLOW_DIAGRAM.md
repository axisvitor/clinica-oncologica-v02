# Quiz Submission Flow - Complete Architecture

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PATIENT INTERACTION                          │
│                      (WhatsApp/Email/SMS)                           │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ 1. Receives quiz link with token
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   QUIZ-MENSAL-INTERFACE                             │
│                    (Public Frontend)                                │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ 1. Access Quiz (/access)                                 │     │
│  │    - Validates token                                     │     │
│  │    - Gets quiz questions                                 │     │
│  │    - Shows current_question_index                        │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                                           │
│                         │ 2. Patient answers questions              │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ 2. Submit Response (/submit)                             │     │
│  │    - For each question                                   │     │
│  │    - Includes other_text if "Outra" selected            │     │
│  └──────────────────────────────────────────────────────────┘     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ API Request
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              /api/v1/monthly-quiz-public/submit                     │
│              (Backend Public Endpoint)                              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 1: Security & Validation                            │     │
│  │  ✓ Rate limiting check                                   │     │
│  │  ✓ Validate public request                               │     │
│  │  ✓ Sanitize token                                        │     │
│  │  ✓ Sanitize response_value (preserve arrays!) ◄────┐    │     │
│  │     - If list: sanitize each item                   │    │     │
│  │     - If string: sanitize normally                  │    │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                                FIX #1     │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 2: Extract Request Context                          │     │
│  │  • IP address                                            │     │
│  │  • User agent                                            │     │
│  │  • Referer/Origin                                        │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                                           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 3: Call Service Layer                               │     │
│  │  → MonthlyQuizService.submit_quiz_response()             │     │
│  └──────────────────────────────────────────────────────────┘     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│         MonthlyQuizService.submit_quiz_response()                   │
│         (Backend/app/services/monthly_quiz_service.py)              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 1: Token Verification                               │     │
│  │  ✓ Decode JWT token                                      │     │
│  │  ✓ Check expiration                                      │     │
│  │  ✓ Extract patient_id & quiz_template_id                │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                                           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 2: Find Quiz Session                                │     │
│  │  ✓ Match by token_hash                                   │     │
│  │  ✓ Verify not completed                                  │     │
│  │  ✓ Get current_question_index ◄──────────────────┐      │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                          FIX #3           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 3: Extract & Validate Data                          │     │
│  │  • Extract other_text from metadata ◄─────────────┐     │     │
│  │  • Get question from template                     │     │     │
│  │  • Store current_question_index                   │     │     │
│  │  • Normalize "other" options                      │     │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                          FIX #2           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 4: Process Response Value                           │     │
│  │  • Handle multiple_choice (array)                        │     │
│  │  • Handle single_choice (string)                         │     │
│  │  • Normalize "Outra" variations                          │     │
│  │  • Encrypt if sensitive                                  │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                                           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 5: Build Response Metadata ◄────────────────┐       │     │
│  │  • is_encrypted: bool                            │       │     │
│  │  • other_text: string (if provided)              │       │     │
│  │  • question_index: int                           │       │     │
│  │  • submitted_at: ISO timestamp                   │       │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                          FIX #2           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 6: Create QuizResponse                              │     │
│  │  → QuizResponseService.create_response()                 │     │
│  │     - Stores in database                                 │     │
│  │     - Returns response object                            │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                                           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 7: Update QuizSession ◄─────────────────────┐       │     │
│  │  • Increment current_question_index               │       │     │
│  │  • Check if last question                         │       │     │
│  │  • If complete:                                   │       │     │
│  │     - Set is_completed = True                     │       │     │
│  │     - Set completed_at = now()                    │       │     │
│  │     - Set status = "completed"                    │       │     │
│  │     - Calculate total_score ──────────────────────┘       │     │
│  │  • Commit to database                                     │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                          FIX #3, #4       │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 8: Token Rotation (if enabled) ◄────────────┐       │     │
│  │  • Check MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION       │       │     │
│  │  • Generate new token with rotation_count++       │       │     │
│  │  • Update token_hash in session metadata          │       │     │
│  │  • Record rotation metrics                        │       │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                          FIX #5           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 9: Build Response ◄──────────────────────────┐      │     │
│  │  {                                                 │      │     │
│  │    "response_id": uuid,                            │      │     │
│  │    "success": true,                                │      │     │
│  │    "message": "Response submitted successfully",   │      │     │
│  │    "next_question_index": int,  ───────────────────┘      │     │
│  │    "is_completed": bool,        ◄──────────────────┐      │     │
│  │    "total_score": int|null,     ◄──────────────────┤      │     │
│  │    "new_token": string|null     ◄──────────────────┘      │     │
│  │  }                                                         │     │
│  └──────────────────────────────────────────────────────────┘     │
│                         │                  FIX #3, #4, #5           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ STEP 10: Record Metrics & Audit Log                      │     │
│  │  • Business metrics (submission success)                  │     │
│  │  • Audit log (response submitted)                         │     │
│  │  • Token rotation metrics (if applicable)                 │     │
│  └──────────────────────────────────────────────────────────┘     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ Response JSON
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FRONTEND RECEIVES                              │
│                                                                     │
│  IF is_completed = false:                                           │
│    • Show next question (use next_question_index)                   │
│    • Update token (use new_token if provided)                       │
│    • Continue quiz                                                  │
│                                                                     │
│  IF is_completed = true:                                            │
│    • Show completion message                                        │
│    • Display total_score                                            │
│    • Thank patient                                                  │
│    • No more questions                                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema Updates

### QuizSession Table
```sql
-- Already exists, needs values updated during submission
CREATE TABLE quiz_sessions (
    id UUID PRIMARY KEY,
    patient_id UUID NOT NULL,
    quiz_template_id UUID NOT NULL,
    current_question_index INTEGER DEFAULT 0,  -- ✅ UPDATED after each response
    is_completed BOOLEAN DEFAULT FALSE,         -- ✅ SET to TRUE when done
    status VARCHAR(50) DEFAULT 'in_progress',   -- ✅ SET to 'completed'
    total_score INTEGER DEFAULT 0,              -- ✅ CALCULATED when done
    session_metadata JSONB,                     -- Contains token_hash, rotation_count
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE       -- ✅ SET when done
);
```

### QuizResponse Table
```sql
-- Already exists, new responses stored here
CREATE TABLE quiz_responses (
    id UUID PRIMARY KEY,
    patient_id UUID NOT NULL,
    quiz_template_id UUID NOT NULL,
    quiz_session_id UUID REFERENCES quiz_sessions(id),
    question_id VARCHAR(100) NOT NULL,
    question_text TEXT NOT NULL,
    response_type VARCHAR(50) NOT NULL,
    response_value TEXT NOT NULL,               -- ✅ Array for multi-select
    response_metadata JSONB,                    -- ✅ Contains other_text
    other_text TEXT,                            -- ✅ Could be used (deprecated)
    responded_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(quiz_session_id, question_id)
);
```

### Response Metadata Structure
```json
{
  "is_encrypted": false,
  "other_text": "Dor de cabeça constante",      // ✅ NEW
  "question_index": 0,                          // ✅ NEW
  "submitted_at": "2025-09-30T10:30:45.123Z",   // ✅ NEW
  "score": 0                                    // Optional per-question score
}
```

---

## API Response Examples

### Submission Response (Mid-Quiz)
```json
{
  "response_id": "123e4567-e89b-12d3-a456-426614174000",
  "success": true,
  "message": "Response submitted successfully",
  "next_question_index": 1,           // ✅ Frontend knows which question next
  "is_completed": false,               // ✅ Quiz not done yet
  "total_score": null,                 // ✅ Only available when complete
  "new_token": "eyJhbGc..."           // ✅ Use for next request (if rotation enabled)
}
```

### Submission Response (Last Question)
```json
{
  "response_id": "123e4567-e89b-12d3-a456-426614174001",
  "success": true,
  "message": "Response submitted successfully",
  "next_question_index": 2,           // ✅ Equals total_questions
  "is_completed": true,                // ✅ Quiz complete!
  "total_score": 45,                   // ✅ Final calculated score
  "new_token": null                    // ✅ No more questions, no new token needed
}
```

---

## Key Improvements

| Fix # | Component | What Was Broken | What's Fixed |
|-------|-----------|----------------|--------------|
| **1** | `monthly_quiz_public.py` | Arrays converted to strings | Each item sanitized individually |
| **2** | `monthly_quiz_service.py` | other_text not stored | Persisted in response_metadata |
| **3** | `monthly_quiz_service.py` | Progress not tracked | current_question_index updated |
| **4** | `monthly_quiz_service.py` | Completion not marked | is_completed, completed_at, total_score set |
| **5** | `monthly_quiz_service.py` | No token rotation | new_token returned when enabled |
| **6** | `monthly_quiz.py` (schema) | Missing field in docs | average_score added to schema |

---

## Testing Checklist

- [ ] Multi-select response (["A", "B", "C"]) stored as array
- [ ] "Outra" option with other_text persisted
- [ ] current_question_index increments after each submission
- [ ] is_completed set to true on last question
- [ ] completed_at timestamp recorded
- [ ] total_score calculated correctly
- [ ] new_token returned (if rotation enabled)
- [ ] Old token invalidated (if rotation enabled)
- [ ] Frontend receives all required fields
- [ ] Average score shows in dashboard

---

## Files Modified

1. ✅ `Backend/app/api/v1/monthly_quiz_public.py` (line 183-191)
2. ✅ `Backend/app/services/monthly_quiz_service.py` (lines 314-445)
3. ✅ `Backend/app/schemas/monthly_quiz.py` (lines 103-117)

**Total LOC Changed**: ~120 lines
**New Helper Method**: `_calculate_total_score()` (~40 lines)

---

**Generated**: 2025-09-30
**Version**: 1.0
