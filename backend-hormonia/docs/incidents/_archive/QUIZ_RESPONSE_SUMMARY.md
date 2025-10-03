# 🎯 Quiz Response Persistence - Quick Reference

## 📊 What Was Fixed

### **Problem:**
- ❌ Multi-select responses converted to strings (broke arrays)
- ❌ "Outra" aliases not normalized
- ❌ Missing validation for `other_text` requirement

### **Solution:**
- ✅ Schema accepts `Union[str, List[str]]`
- ✅ Service preserves lists via JSON serialization
- ✅ "Outra/Outro/Otra/Autre/Altro" → "other"
- ✅ Comprehensive validation for multi-select and other_text

---

## 🚀 Quick Usage Guide

### **1. Single-Select Response**
```python
from app.schemas.quiz import QuizResponseCreate, QuestionType

response = QuizResponseCreate(
    patient_id=patient_uuid,
    quiz_template_id=template_uuid,
    question_id="q1",
    question_text="What is your age group?",
    response_type=QuestionType.SINGLE_CHOICE,
    response_value="25-34",  # Single string
    responded_at=datetime.utcnow()
)
```

### **2. Multi-Select Response**
```python
response = QuizResponseCreate(
    patient_id=patient_uuid,
    quiz_template_id=template_uuid,
    question_id="q2",
    question_text="Select all symptoms",
    response_type=QuestionType.MULTIPLE_CHOICE,
    response_value=["Headache", "Nausea", "Fatigue"],  # List of strings
    responded_at=datetime.utcnow()
)
```

### **3. Response with "Outra" (Custom Text)**
```python
response = QuizResponseCreate(
    patient_id=patient_uuid,
    quiz_template_id=template_uuid,
    question_id="q3",
    question_text="How did you hear about us?",
    response_type=QuestionType.SINGLE_CHOICE,
    response_value="Outra",  # Will be normalized to "other"
    other_text="I found you on Google",  # REQUIRED when "Outra" selected
    responded_at=datetime.utcnow()
)
```

### **4. Multi-Select with "Outra"**
```python
response = QuizResponseCreate(
    patient_id=patient_uuid,
    quiz_template_id=template_uuid,
    question_id="q4",
    question_text="Select all that apply",
    response_type=QuestionType.MULTIPLE_CHOICE,
    response_value=["Option 1", "Option 2", "Outra"],
    other_text="My custom reason",
    responded_at=datetime.utcnow()
)
```

---

## 🔧 API Request Examples

### **Frontend → Backend (Multi-Select)**
```json
POST /api/v1/quiz/responses
{
  "patient_id": "123e4567-e89b-12d3-a456-426614174000",
  "quiz_template_id": "987fcdeb-51a2-43f7-8abc-123456789012",
  "question_id": "q_symptoms",
  "question_text": "What symptoms do you have?",
  "response_type": "multiple_choice",
  "response_value": ["Headache", "Nausea", "Dizziness"],
  "responded_at": "2025-09-30T10:30:00Z"
}
```

### **Frontend → Backend (With "Outra")**
```json
POST /api/v1/quiz/responses
{
  "patient_id": "123e4567-e89b-12d3-a456-426614174000",
  "quiz_template_id": "987fcdeb-51a2-43f7-8abc-123456789012",
  "question_id": "q_referral",
  "question_text": "Como você soube da clínica?",
  "response_type": "single_choice",
  "response_value": "Outra",
  "other_text": "Encontrei no Google",
  "responded_at": "2025-09-30T10:30:00Z"
}
```

---

## 🎨 Database Storage Format

### **Single-Select:**
```sql
response_value: 'Option 1'  -- Plain text
other_text: NULL
```

### **Multi-Select:**
```sql
response_value: '["Option 1", "Option 2", "Option 3"]'  -- JSON array
other_text: NULL
```

### **With "Outra":**
```sql
response_value: 'other'  -- Normalized
other_text: 'Encontrei no Google'  -- Custom text
```

### **Multi-Select with "Outra":**
```sql
response_value: '["Option 1", "other"]'  -- JSON with normalized "other"
other_text: 'My custom reason'
```

---

## 🛡️ Validation Rules

| Scenario | Validation | Error Message |
|----------|-----------|---------------|
| Empty multi-select `[]` | ❌ FAIL | "Multi-select requires at least one selection" |
| Invalid option | ❌ FAIL | "Invalid option: {value}" |
| "Outra" without `other_text` | ❌ FAIL | "Custom text required when 'Outra' option is selected" |
| `other_text` when not allowed | ❌ FAIL | "other_text provided but question/option does not allow custom text" |
| Valid single-select | ✅ PASS | - |
| Valid multi-select | ✅ PASS | - |
| "Outra" with `other_text` | ✅ PASS | - |

---

## 🌍 Supported "Other" Aliases

All of these are normalized to `"other"`:

| Language | Alias |
|----------|-------|
| Portuguese | `outra`, `outro` |
| Spanish | `otra` |
| French | `autre` |
| Italian | `altro` |
| English | `other` |

**Example:**
```python
"Outra" → "other"
"OUTRO" → "other"
"otra" → "other"
```

---

## 🧪 Testing

### **Run All Tests:**
```bash
cd Backend
pytest tests/test_quiz_response_persistence.py -v
```

### **Test Coverage:**
- ✅ Schema validation (8 tests)
- ✅ Normalization (5 tests)
- ✅ Serialization (3 tests)
- ✅ Deserialization (4 tests)
- ✅ Multi-select validation (5 tests)
- ✅ other_text requirement (3 tests)

**Total: 28+ test cases**

---

## 📂 Files Changed

### **Modified:**
1. `Backend/app/schemas/quiz.py`
   - Lines 109-154: `QuizResponseCreate` schema
   - Added `Union[str, List[str]]` support
   - Enhanced `other_text` validation

2. `Backend/app/services/quiz.py`
   - Lines 1-29: Added utility imports
   - Lines 246-347: Refactored `create_response()`
   - Lines 349-396: Enhanced `_validate_response_by_type()`

### **Created:**
1. `Backend/app/services/quiz_response_utils.py`
   - Utility functions for normalization, serialization, validation

2. `Backend/tests/test_quiz_response_persistence.py`
   - Comprehensive test suite

3. `Backend/docs/quiz_response_persistence_report.md`
   - Detailed implementation report

4. `Backend/docs/QUIZ_RESPONSE_SUMMARY.md`
   - This quick reference guide

---

## 🔍 Troubleshooting

### **Issue: "Multi-select requires at least one selection"**
**Cause:** Empty list sent as `response_value`
**Fix:** Ensure frontend sends at least one selected option

### **Issue: "Custom text required when 'Outra' option is selected"**
**Cause:** "Outra" selected but `other_text` is empty/null
**Fix:** Validate frontend form requires text input when "Outra" is selected

### **Issue: "Invalid option: {value}"**
**Cause:** Selected value doesn't match any question option
**Fix:** Ensure frontend sends exact option values from question definition

### **Issue: Old responses not loading**
**Cause:** Attempting to deserialize old string-stored responses
**Fix:** Use `deserialize_response_value()` utility function:
```python
from app.services.quiz_response_utils import deserialize_response_value

stored_value = response.response_value  # From database
is_multi = response.response_type == 'multiple_choice'

parsed_value = deserialize_response_value(stored_value, is_multi_select=is_multi)
```

---

## 🚦 Migration Notes

### **No Database Migration Required!**
- ✅ Uses existing `response_value` TEXT column
- ✅ Uses existing `other_text` TEXT column
- ✅ Backward compatible with old data

### **Old Data Handling:**
```python
# Old format (already in DB)
response_value: '["Option 1", "Option 2"]'  # String representation

# New code handles it automatically
deserialize_response_value(old_value, is_multi_select=True)
# Returns: ["Option 1", "Option 2"]
```

---

## 📞 Support

**Questions?** Contact the backend team or refer to:
- Full report: `docs/quiz_response_persistence_report.md`
- Test file: `tests/test_quiz_response_persistence.py`
- Utils: `app/services/quiz_response_utils.py`

---

**Last Updated:** 2025-09-30
**Status:** ✅ Production Ready
**Backward Compatible:** ✅ YES
