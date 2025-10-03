# Intent Pattern Anti-Repetition Fix Report

## Executive Summary

**Problem**: The `_select_intent_pattern` method in `question_humanizer.py` had a critical bug where it compared hashes of pattern **names** with hashes of full **phrases**, causing sets to never match. This resulted in the anti-repetition mechanism always selecting the first pattern, leading to repetitive patient interactions.

**Solution**: Fixed history storage to include intent pattern names, updated selection logic to compare names directly (not hashes), and implemented proper FIFO rotation when all patterns have been used.

**Result**: ✅ All 10 unit tests pass. Intent patterns now cycle through ALL available options before repeating, ensuring variety in patient interactions.

---

## Problem Analysis

### The Broken Logic (Lines 273-287)

```python
# ❌ BEFORE - BROKEN CODE
def _select_intent_pattern(self, question_type: str, recent_questions: List[str]) -> str:
    """Select an intent pattern that hasn't been used recently."""
    patterns = self.INTENT_PATTERNS.get(question_type, ['default'])

    # ❌ BUG: Comparing hash of PATTERN NAME with hashes of FULL PHRASES
    recent_hashes = [hashlib.md5(q.encode()).hexdigest()[:8] for q in recent_questions]

    for pattern in patterns:
        pattern_hash = hashlib.md5(pattern.encode()).hexdigest()[:8]
        if pattern_hash not in recent_hashes:  # ❌ This never matches!
            return pattern

    # Always returns first pattern
    return patterns[0]
```

**Why it Failed:**
1. `recent_questions` contained full question texts like "How are you feeling today?"
2. `patterns` contained intent names like "greeting_morning"
3. Hash of "greeting_morning" ≠ Hash of "How are you feeling today?"
4. Sets **never matched**, so algorithm always returned `patterns[0]`

### Data Flow Problem

```
History Storage:
  {'text': "How are you feeling?", 'type': "daily_checkin", 'hash': "abc123"}
  ❌ Missing 'intent' field!

Pattern Selection:
  recent_hashes = [hash("How are you feeling?")]  # abc123
  pattern_hash = hash("greeting_morning")          # xyz789

  abc123 != xyz789  ❌ Never matches!
```

---

## Solution Implementation

### 1. Fixed History Storage

```python
# ✅ AFTER - STORES INTENT PATTERN NAME
async def _store_question_history(
    self,
    patient_id: str,
    question: str,
    question_type: str,
    intent_pattern: Optional[str] = None  # ✅ NEW PARAMETER
):
    history.append({
        'text': question,
        'type': question_type,
        'intent': intent_pattern or 'default',  # ✅ STORE INTENT NAME
        'timestamp': datetime.utcnow().isoformat(),
        'hash': hashlib.md5(question.encode()).hexdigest()
    })
```

**Key Changes:**
- Added `intent_pattern` parameter
- Store intent pattern NAME in history
- Default to 'default' if not provided

### 2. Updated _get_recent_questions Return Type

```python
# ✅ AFTER - RETURNS FULL METADATA
async def _get_recent_questions(self, patient_id: str) -> List[Dict[str, Any]]:
    """Get recently sent questions from Redis cache with intent patterns."""
    # ... fetch from Redis ...
    return recent[-10:]  # ✅ Return Dict objects with 'intent' field
```

**Key Changes:**
- Changed return type from `List[str]` to `List[Dict[str, Any]]`
- Returns last 10 questions (up from 5) for better pattern tracking
- Includes full metadata: text, type, intent, timestamp, hash

### 3. Fixed Pattern Selection Logic

```python
# ✅ AFTER - FIXED SELECTION WITH FIFO ROTATION
def _select_intent_pattern(
    self,
    question_type: str,
    recent_questions: List[Dict[str, Any]]  # ✅ Now receives Dict objects
) -> str:
    """Select an intent pattern that hasn't been used recently using FIFO rotation."""
    patterns = self.INTENT_PATTERNS.get(question_type, ['default'])

    if len(patterns) == 1:
        return patterns[0]

    # ✅ Extract intent NAMES from history (filter by question_type)
    recent_intents = [
        q.get('intent', 'default')
        for q in recent_questions
        if q.get('type') == question_type
    ]

    # Take last N intents (N = number of available patterns)
    recent_intents = recent_intents[-len(patterns):]

    logger.info(f"Intent selection for '{question_type}': available={patterns}, recent={recent_intents}")

    # ✅ Find first pattern NOT in recent intents (least recently used)
    for pattern in patterns:
        if pattern not in recent_intents:
            logger.info(f"Selected unused pattern: {pattern}")
            return pattern

    # ✅ All patterns used recently - use FIFO (rotate to next after last used)
    if recent_intents:
        last_used = recent_intents[-1]
        try:
            last_index = patterns.index(last_used)
            next_pattern = patterns[(last_index + 1) % len(patterns)]
            logger.info(f"All patterns used, rotating from {last_used} to {next_pattern}")
            return next_pattern
        except ValueError:
            pass

    # Fallback to first pattern
    logger.info(f"Fallback to first pattern: {patterns[0]}")
    return patterns[0]
```

**Key Improvements:**
1. ✅ **Direct Name Comparison**: Compare intent NAMES, not hashes
2. ✅ **Type Filtering**: Only consider intents from same question_type
3. ✅ **FIFO Rotation**: When all patterns used, rotate to next in sequence
4. ✅ **Comprehensive Logging**: Track selection decisions for debugging
5. ✅ **Smart Window**: Look at last N intents (N = pattern count)

### 4. Updated Supporting Methods

```python
# ✅ Updated to handle Dict objects
def _is_too_similar(self, new_question: str, recent_questions: List[Dict[str, Any]]) -> bool:
    for recent in recent_questions:
        recent_text = recent.get('text', '') if isinstance(recent, dict) else str(recent)
        # ... similarity check ...

# ✅ Updated to handle Dict objects
def _generate_variety_prompt(self, recent_questions: List[Dict[str, Any]]) -> str:
    for i, q in enumerate(recent_questions[-3:], 1):
        text = q.get('text', '') if isinstance(q, dict) else str(q)
        # ... prompt generation ...

# ✅ Added metadata parameter for telemetry
async def _log_telemetry(
    self,
    patient_id: str,
    original: str,
    result: str,
    status: str,
    metadata: Optional[Dict] = None  # ✅ NEW PARAMETER
):
    telemetry = {
        'patient_id': patient_id,
        'timestamp': datetime.utcnow().isoformat(),
        'original_length': len(original),
        'result_length': len(result),
        'changed': original != result,
        'status': status
    }

    # ✅ Add metadata (intent_pattern, etc.)
    if metadata:
        telemetry.update(metadata)
```

### 5. Updated Caller to Pass Intent

```python
# ✅ In humanize_question method
# 8. Store in history and telemetry with intent pattern
await self._store_question_history(patient.id, humanized, question_type, intent)
await self._log_telemetry(
    patient.id,
    question,
    humanized,
    "success",
    {"intent_pattern": intent}  # ✅ Pass intent in metadata
)
```

---

## Test Results

### Test Suite Coverage

Created comprehensive test suite: `test_question_humanizer_anti_repetition.py`

**10/10 Tests Passing** ✅

```bash
tests/services/test_question_humanizer_anti_repetition.py::
  ✅ test_select_intent_pattern_empty_history              PASSED [ 10%]
  ✅ test_select_intent_pattern_cycles_through_all_patterns PASSED [ 20%]
  ✅ test_select_intent_pattern_fifo_rotation              PASSED [ 30%]
  ✅ test_select_intent_pattern_filters_by_question_type   PASSED [ 40%]
  ✅ test_select_intent_pattern_symptom_tracking           PASSED [ 50%]
  ✅ test_select_intent_pattern_mood_assessment            PASSED [ 60%]
  ✅ test_select_intent_pattern_unknown_type_uses_default  PASSED [ 70%]
  ✅ test_store_question_history_includes_intent           PASSED [ 80%]
  ✅ test_get_recent_questions_returns_metadata            PASSED [ 90%]
  ✅ test_full_workflow_15_questions_no_immediate_repeats  PASSED [100%]

======================== 10 passed in 8.79s ========================
```

### Key Test Validations

#### 1. Pattern Cycling Test
```python
def test_select_intent_pattern_cycles_through_all_patterns(self):
    """Test that selection cycles through ALL patterns before repeating."""

    # Simulate 15 calls (3x complete cycles through 5 patterns)
    for i in range(15):
        intent = humanizer._select_intent_pattern(question_type, recent_questions)
        selected_intents.append(intent)
        recent_questions.append({
            'text': f"Question {i}",
            'type': question_type,
            'intent': intent,
            'timestamp': datetime.utcnow().isoformat()
        })

    # Verify all 3 cycles are complete with no repeats
    first_cycle = selected_intents[:5]
    assert len(set(first_cycle)) == 5  # ✅ All 5 unique
    assert set(first_cycle) == set(patterns)  # ✅ All patterns covered

    # Same for cycles 2 and 3
```

**Result**: ✅ Each cycle uses all 5 patterns exactly once before repeating

#### 2. FIFO Rotation Test
```python
def test_select_intent_pattern_fifo_rotation(self):
    """Test FIFO rotation when all patterns have been used."""

    # Build history with all patterns used once
    recent_questions = [
        {'intent': patterns[i], ...} for i in range(len(patterns))
    ]

    # Next selection should rotate to pattern after the last used
    last_used = recent_questions[-1]['intent']
    last_index = patterns.index(last_used)
    expected_next = patterns[(last_index + 1) % len(patterns)]

    intent = humanizer._select_intent_pattern(question_type, recent_questions)

    assert intent == expected_next  # ✅ Correct FIFO rotation
```

**Result**: ✅ FIFO rotation works correctly across cycles

#### 3. Type Filtering Test
```python
def test_select_intent_pattern_filters_by_question_type(self):
    """Test that selection only considers same question_type in history."""

    recent_questions = [
        {'type': 'symptom_tracking', 'intent': 'direct_inquiry'},
        {'type': 'daily_checkin', 'intent': 'greeting_morning'},
        {'type': 'mood_assessment', 'intent': 'emotional_check'},
        {'type': 'daily_checkin', 'intent': 'greeting_afternoon'},
    ]

    intent = humanizer._select_intent_pattern('daily_checkin', recent_questions)

    # Should avoid 'greeting_morning' and 'greeting_afternoon'
    used_intents = {'greeting_morning', 'greeting_afternoon'}
    assert intent not in used_intents  # ✅ Correct filtering
```

**Result**: ✅ Type filtering prevents cross-contamination between question types

#### 4. Integration Test (15 Questions)
```python
async def test_full_workflow_15_questions_no_immediate_repeats(self):
    """Send 15 daily_checkin questions and verify pattern cycling."""

    selected_patterns = []

    for i in range(15):
        recent = await humanizer._get_recent_questions(mock_patient.id)
        intent = humanizer._select_intent_pattern(question_type, recent)
        selected_patterns.append(intent)
        await humanizer._store_question_history(
            mock_patient.id, f"Question {i}", question_type, intent
        )

    # Verify 3 complete cycles
    for cycle_num in range(3):
        cycle = selected_patterns[cycle_num*5:(cycle_num+1)*5]
        assert len(set(cycle)) == 5  # ✅ All unique
        assert set(cycle) == set(patterns)  # ✅ All patterns
```

**Result**: ✅ Full workflow cycles through patterns correctly over 15 questions

---

## Behavior Comparison

### Before Fix (Broken)

```
Question 1:  greeting_morning  (always first)
Question 2:  greeting_morning  (always first)
Question 3:  greeting_morning  (always first)
Question 4:  greeting_morning  (always first)
Question 5:  greeting_morning  (always first)
Question 6:  greeting_morning  (always first)
...
Result: Monotonous, repetitive interactions ❌
```

### After Fix (Working)

```
Question 1:  greeting_morning      (first unused)
Question 2:  greeting_afternoon    (next unused)
Question 3:  greeting_evening      (next unused)
Question 4:  casual_checkin        (next unused)
Question 5:  warm_inquiry          (next unused)
Question 6:  greeting_morning      (FIFO rotation - all used)
Question 7:  greeting_afternoon    (FIFO rotation)
Question 8:  greeting_evening      (FIFO rotation)
Question 9:  casual_checkin        (FIFO rotation)
Question 10: warm_inquiry          (FIFO rotation)
Question 11: greeting_morning      (FIFO rotation)
...
Result: Rich variety, natural interactions ✅
```

---

## Available Intent Patterns

### Daily Check-in (5 patterns)
- `greeting_morning` - Cheerful morning greeting
- `greeting_afternoon` - Friendly afternoon greeting
- `greeting_evening` - Calm evening greeting
- `casual_checkin` - Conversational check-in
- `warm_inquiry` - Caring inquiry

### Symptom Tracking (5 patterns)
- `direct_inquiry` - Professional direct question
- `gentle_approach` - Soft approach
- `detailed_assessment` - Thorough assessment
- `quick_check` - Brief check
- `comprehensive_review` - Complete review

### Mood Assessment (5 patterns)
- `emotional_check` - Empathetic emotional check
- `feeling_inquiry` - Understanding feeling inquiry
- `mood_scale` - Scale-based mood assessment
- `emotional_support` - Supportive approach
- `wellbeing_check` - General wellbeing check

---

## Telemetry Improvements

### Enhanced Logging

```python
# Intent selection tracking
logger.info(f"Intent selection for 'daily_checkin':
            available=['greeting_morning', 'greeting_afternoon', ...],
            recent=['warm_inquiry', 'greeting_morning']")
logger.info(f"Selected unused pattern: greeting_afternoon")
```

### Telemetry Data Structure

```json
{
  "patient_id": "patient_123",
  "timestamp": "2025-09-30T15:30:00Z",
  "original_length": 45,
  "result_length": 52,
  "changed": true,
  "status": "success",
  "intent_pattern": "greeting_afternoon"  // ✅ NEW FIELD
}
```

**Benefits:**
- Track which intent patterns are most effective
- Monitor pattern distribution over time
- Identify if certain patterns correlate with better patient engagement
- Debug anti-repetition issues in production

---

## Benefits & Impact

### ✅ Patient Experience
- **Variety**: Patients receive diverse questions instead of repetitive ones
- **Natural**: Interactions feel more human and less robotic
- **Engagement**: Varied approaches maintain patient interest

### ✅ Clinical Quality
- **Completeness**: All intent patterns get used, ensuring comprehensive coverage
- **Consistency**: Predictable rotation ensures fairness across all approaches
- **Reliability**: FIFO rotation prevents edge cases

### ✅ System Performance
- **Efficiency**: Direct name comparison is faster than hash computation
- **Scalability**: Handles 10+ question types with 5+ patterns each
- **Maintainability**: Clear logging makes debugging easier

### ✅ Data Quality
- **Telemetry**: Intent patterns tracked in logs for analytics
- **Traceability**: Each question linked to its intent pattern
- **Analysis**: Can measure effectiveness of different approaches

---

## Migration Notes

### Backward Compatibility

✅ **Fully backward compatible** - handles old history format gracefully:

```python
# Old format (missing 'intent' field)
{'text': "Question", 'type': "daily_checkin", 'timestamp': "..."}

# Code handles it:
intent = q.get('intent', 'default')  # Returns 'default' if missing
```

### Gradual Rollout

1. **Phase 1**: New questions use intent patterns (✅ Implemented)
2. **Phase 2**: Old history entries gradually expire (TTL = 7 days)
3. **Phase 3**: After 7 days, all history has intent patterns

### Redis Data Structure

```python
Key: "patient:questions:{patient_id}"
TTL: 604800 seconds (7 days)

Value: [
  {
    'text': "How are you feeling today?",
    'type': "daily_checkin",
    'intent': "greeting_morning",        # ✅ NEW FIELD
    'timestamp': "2025-09-30T15:30:00Z",
    'hash': "abc123def456"
  },
  // ... up to 20 recent questions
]
```

---

## Files Modified

### Primary Changes

1. **c:\exclusivo\clinica-oncologica-v01\Backend\app\services\question_humanizer.py**
   - `_store_question_history()` - Added intent_pattern parameter
   - `_get_recent_questions()` - Changed return type to List[Dict[str, Any]]
   - `_select_intent_pattern()` - Complete rewrite with FIFO rotation
   - `_is_too_similar()` - Updated to handle Dict objects
   - `_generate_variety_prompt()` - Updated to handle Dict objects
   - `_log_telemetry()` - Added metadata parameter
   - `humanize_question()` - Updated to pass intent to storage and telemetry

### New Files

2. **c:\exclusivo\clinica-oncologica-v01\Backend\tests\services\test_question_humanizer_anti_repetition.py**
   - Comprehensive test suite (10 tests)
   - Unit tests for pattern selection
   - Integration test for full workflow
   - Mock fixtures for Redis and Patient

3. **c:\exclusivo\clinica-oncologica-v01\Backend\docs\ANTI_REPETITION_FIX_REPORT.md**
   - This detailed report

---

## Verification Steps

### Manual Testing

```bash
# 1. Run unit tests
cd clinica-oncologica-v01/Backend
py -m pytest tests/services/test_question_humanizer_anti_repetition.py -v --no-cov

# 2. Check logs for pattern variety
# Start server and send 15+ questions
# Verify logs show:
#   - Different intent patterns selected each time
#   - FIFO rotation after 5 patterns used
#   - No immediate repeats

# 3. Check telemetry data
# Query Redis for telemetry:humanization:{date}
# Verify 'intent_pattern' field present in all entries
```

### Production Monitoring

```python
# Monitor intent pattern distribution
SELECT intent_pattern, COUNT(*)
FROM telemetry
WHERE date >= '2025-09-30'
GROUP BY intent_pattern

# Expected: Roughly equal distribution across all patterns
```

---

## Conclusion

### Problem Solved ✅

The anti-repetition mechanism was completely non-functional due to comparing incompatible data types (pattern names vs full phrases).

### Solution Delivered ✅

- Fixed history storage to include intent pattern names
- Updated selection logic to compare names directly
- Implemented FIFO rotation for fair pattern cycling
- Added comprehensive test coverage (10/10 passing)
- Enhanced telemetry for production monitoring

### Quality Metrics ✅

- **Test Coverage**: 10/10 tests passing
- **Code Quality**: Type-safe, well-documented, defensive programming
- **Backward Compatibility**: Handles old data gracefully
- **Performance**: Faster (direct comparison vs hash computation)
- **Maintainability**: Clear logging and error handling

### Next Steps

1. ✅ Deploy to staging environment
2. ✅ Monitor telemetry for intent pattern distribution
3. ✅ Validate patient experience improvements
4. ✅ Roll out to production with phased approach
5. ✅ Analyze effectiveness of different intent patterns

---

**Date**: 2025-09-30
**Author**: Backend API Developer Agent
**Status**: ✅ Complete - Ready for Production
