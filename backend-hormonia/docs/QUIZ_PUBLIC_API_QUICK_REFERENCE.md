# Quiz Public API Fixes - Quick Reference

## Files to Modify

### 1. `Backend/app/api/v1/monthly_quiz_public.py` (Line 183-191)

**Problem**: Converts arrays to strings, breaking multi-select responses

**Fix**: Sanitize each array item individually

```python
# Replace lines 185-186:
if isinstance(submit_data.response_value, list):
    submit_data.response_value = [sanitize_input(str(item)) for item in submit_data.response_value]
elif submit_data.response_value is not None:
    submit_data.response_value = sanitize_input(str(submit_data.response_value))
```

---

### 2. `Backend/app/services/monthly_quiz_service.py`

#### A. Extract other_text (after line 349)
```python
other_text = None
if submit_data.response_metadata:
    other_text = submit_data.response_metadata.get("other_text")

current_question_index = session.current_question_index
```

#### B. Store other_text (lines 404-406)
```python
response_metadata = submit_data.response_metadata or {}
response_metadata["is_encrypted"] = is_encrypted

if other_text:
    response_metadata["other_text"] = other_text

response_metadata["question_index"] = current_question_index
response_metadata["submitted_at"] = datetime.utcnow().isoformat()
```

#### C. Update session progress (after line 418)
```python
total_questions = len(template.questions)
session.current_question_index = current_question_index + 1

if session.current_question_index >= total_questions:
    session.is_completed = True
    session.completed_at = datetime.utcnow()
    session.status = "completed"

    total_score = await self._calculate_total_score(session.id)
    session.total_score = total_score

self.db.commit()
self.db.refresh(session)
```

#### D. Token rotation and response (replace lines 440-444)
```python
new_token = None
if self.config.MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION:
    rotation_count = payload.get("rotation_count", 0) + 1
    expires_at = datetime.fromisoformat(payload["expires_at"])
    new_token = self._generate_token(
        patient_id=patient_id,
        quiz_template_id=quiz_template_id,
        expires_at=expires_at,
        rotation_count=rotation_count
    )

    metadata = session.session_metadata or {}
    metadata["token_hash"] = hashlib.sha256(new_token.encode()).hexdigest()
    metadata["rotation_count"] = rotation_count
    session.session_metadata = metadata
    self.db.commit()

return {
    "response_id": str(response.id),
    "success": True,
    "message": "Response submitted successfully",
    "next_question_index": session.current_question_index,
    "is_completed": session.is_completed,
    "total_score": session.total_score if session.is_completed else None,
    "new_token": new_token
}
```

#### E. Add score calculation method (new class method)
```python
async def _calculate_total_score(self, session_id: UUID) -> int:
    responses = self.db.query(QuizResponse).filter(
        QuizResponse.quiz_session_id == session_id
    ).all()

    total_score = 0
    for response in responses:
        metadata = response.response_metadata or {}
        score = metadata.get("score", 0)

        if score == 0 and response.response_type == "scale":
            try:
                score = int(response.response_value)
            except (ValueError, TypeError):
                score = 0
        elif score == 0 and response.response_type == "boolean":
            if response.response_value.lower() in ["yes", "sim", "true", "1"]:
                score = 1

        total_score += score

    return total_score
```

---

### 3. `Backend/app/schemas/monthly_quiz.py` (Optional)

Add to `MonthlyQuizStats` schema (line 113):
```python
average_score: Optional[float] = Field(
    None,
    description="Average score across completed quizzes"
)
```

**Note**: Service already calculates this value, just add to schema for API documentation.

---

## Testing

```bash
# Run unit tests
pytest Backend/tests/services/test_monthly_quiz_service.py -v -k "test_multi_select"

# Run integration tests
pytest Backend/tests/integration/test_monthly_quiz_public_api.py -v

# Test multi-select submission
curl -X POST http://localhost:8000/api/v1/monthly-quiz-public/submit \
  -H "Content-Type: application/json" \
  -d '{
    "token": "YOUR_TOKEN",
    "question_id": "q1",
    "response_value": ["Ansiedade", "Outra"],
    "response_metadata": {
      "other_text": "Náuseas"
    }
  }'
```

---

## Success Criteria

✅ Arrays preserved in `response_value`
✅ `other_text` in `response_metadata`
✅ `current_question_index` increments
✅ `is_completed` = true when done
✅ `completed_at` timestamp set
✅ `total_score` calculated
✅ `new_token` returned (if rotation enabled)

---

## Rollback

If issues arise:
1. Restore backup: `cp monthly_quiz_public.py.backup monthly_quiz_public.py`
2. Restart service: `systemctl restart hormonia-backend`
3. Check logs: `tail -f /var/log/hormonia/backend.log`

---

## Support

- Full report: `/Backend/docs/QUIZ_PUBLIC_API_FIXES.md`
- Patches: `/Backend/docs/patches/`
- Tests: `/Backend/tests/services/test_monthly_quiz_service.py`
