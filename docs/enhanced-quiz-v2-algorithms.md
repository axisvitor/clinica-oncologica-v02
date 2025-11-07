# Enhanced Quiz V2 - Scoring Algorithms and Branching Logic

## Overview

This document describes the scoring algorithms and branching logic implemented in the Enhanced Quiz V2 API. The system provides advanced quiz capabilities including adaptive question flow, risk assessment, and intelligent scoring.

## Architecture

### Components

1. **Schema Layer** (`app/schemas/v2/enhanced_quiz.py`)
   - Pydantic V2 models with comprehensive validation
   - Branching logic definitions
   - Risk scoring models

2. **API Layer** (`app/api/v2/enhanced_quiz.py`)
   - 8 advanced endpoints
   - Redis caching (TTL: 10-30 minutes)
   - Rate limiting (10-40 requests/min)
   - RBAC enforcement

3. **Test Suite** (`tests/api/v2/test_enhanced_quiz.py`)
   - 26+ comprehensive test cases
   - Unit and integration tests
   - Scoring algorithm validation

## Scoring Algorithms

### 1. Risk Score Calculation

The risk scoring algorithm evaluates quiz responses to determine patient risk levels.

#### Algorithm: `_calculate_risk_score()`

**Input:**
- List of `QuizResponse` objects
- `QuizTemplate` with risk factor definitions

**Process:**

```python
risk_score = 0.0
risk_factors = []

# For each response
for response in responses:
    # Check if question has risk factors defined
    if question has risk_mapping:
        # Evaluate response value
        if numeric_value >= 7:  # High threshold
            risk_score += factor_weight * 10
            risk_factors.append(factor_name)

# Normalize to 0-100 scale
risk_score = min(risk_score, 100.0)
```

**Risk Level Classification:**

| Risk Score | Risk Level | Actions |
|-----------|-----------|---------|
| 75-100 | CRITICAL | Immediate physician contact, urgent consultation |
| 50-74 | HIGH | Consultation within 48 hours, close monitoring |
| 25-49 | MEDIUM | Routine follow-up scheduled |
| 0-24 | LOW | Continue current treatment plan |

**Confidence Calculation:**

```python
confidence = min(responses_count / total_questions, 1.0)
```

Higher completion rates increase confidence in the assessment.

**Output:**
- `overall_risk_level`: Enum (LOW, MEDIUM, HIGH, CRITICAL)
- `risk_score`: Float (0-100)
- `risk_factors`: List of identified factors
- `recommendations`: List of actionable recommendations
- `urgent_actions`: List of urgent actions required
- `confidence_score`: Float (0-1)

### 2. Adaptive Question Scoring

Questions can have custom scoring weights for importance:

```json
{
  "id": "q1_pain_level",
  "scoring_weight": 2.0,  // Double importance
  "risk_factors": {
    "high_pain": 0.8  // 80% contribution to risk score
  }
}
```

## Branching Logic

### 1. Branching Conditions

Conditions determine when branching rules should apply.

#### Condition Structure

```json
{
  "field": "pain_level",          // Field to evaluate
  "operator": "gte",               // Comparison operator
  "value": 7                       // Expected value
}
```

#### Supported Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equal to | `{"field": "status", "operator": "eq", "value": "active"}` |
| `neq` | Not equal to | `{"field": "treatment", "operator": "neq", "value": "none"}` |
| `gt` | Greater than | `{"field": "score", "operator": "gt", "value": 50}` |
| `lt` | Less than | `{"field": "age", "operator": "lt", "value": 18}` |
| `gte` | Greater than or equal | `{"field": "pain", "operator": "gte", "value": 7}` |
| `lte` | Less than or equal | `{"field": "temp", "operator": "lte", "value": 38.5}` |
| `in` | In list | `{"field": "symptom", "operator": "in", "value": ["fever", "chills"]}` |
| `contains` | Contains substring | `{"field": "notes", "operator": "contains", "value": "urgent"}` |

### 2. Branching Rules

Rules define actions to take when conditions match.

#### Rule Structure

```json
{
  "conditions": [
    {"field": "pain_level", "operator": "gte", "value": 7}
  ],
  "logic": "AND",                    // AND or OR
  "next_question_id": "q_pain_location",
  "skip_to_section": "emergency",
  "show_alert": "High pain level detected"
}
```

#### Algorithm: `_evaluate_branching_condition()`

**Input:**
- Condition definition
- Response data dictionary

**Process:**

```python
def evaluate_condition(condition, response_data):
    field = condition["field"]
    operator = condition["operator"]
    expected = condition["value"]
    actual = response_data.get(field)

    if operator == "eq":
        return actual == expected
    elif operator == "gte":
        return actual >= expected
    # ... etc for all operators

    return False
```

**Logic Evaluation:**

- **AND Logic**: All conditions must match
  ```python
  all(evaluate_condition(c, data) for c in conditions)
  ```

- **OR Logic**: At least one condition must match
  ```python
  any(evaluate_condition(c, data) for c in conditions)
  ```

### 3. Adaptive Flow Processing

The adaptive flow algorithm determines the next question based on responses.

#### Algorithm Flow

```
1. Receive response for current question
2. Save response to database
3. Retrieve question definition from template
4. For each branching rule:
   a. Evaluate conditions
   b. If match found:
      - Generate alerts
      - Determine next question
      - Break loop
5. If no match:
   - Use next sequential question
6. Update session progress
7. Check completion status
8. Return next question or completion
```

#### Example Flow

**Question 1: Pain Level**
```json
{
  "id": "q1_pain_level",
  "question_text": "Rate your pain (0-10)",
  "branching_rules": [
    {
      "conditions": [
        {"field": "pain_level", "operator": "gte", "value": 7}
      ],
      "next_question_id": "q2_pain_emergency",
      "show_alert": "High pain - immediate assessment needed"
    },
    {
      "conditions": [
        {"field": "pain_level", "operator": "lt", "value": 4}
      ],
      "next_question_id": "q3_general_wellness",
      "show_alert": null
    }
  ]
}
```

**Flow:**
- If user answers 8: → Go to `q2_pain_emergency`, show alert
- If user answers 2: → Go to `q3_general_wellness`, no alert
- If user answers 5: → Go to next question in sequence

## Performance Optimization

### 1. Caching Strategy

**Cache Keys:**
```python
cache_key = f"enhanced_quiz:v2:{endpoint}:{params_hash}"
```

**TTL by Endpoint:**
- Analytics: 15 minutes (900s)
- Quiz Templates: 30 minutes (1800s)
- Results: 10 minutes (600s)

**Cache Implementation:**
```python
# Check cache
cached = await redis.get(cache_key)
if cached:
    return json.loads(cached)

# Generate result
result = compute_result()

# Store in cache
await redis.setex(cache_key, ttl, json.dumps(result))
return result
```

### 2. Database Optimization

**Eager Loading:**
```python
query = query.options(
    joinedload(QuizSession.quiz_template),
    joinedload(QuizSession.responses),
    joinedload(QuizSession.patient)
)
```

**Indexed Fields:**
- `quiz_sessions.patient_id`
- `quiz_sessions.status`
- `quiz_sessions.created_at`
- `quiz_templates.category`
- `quiz_templates.is_active`

### 3. Rate Limiting

| Endpoint | Rate Limit | Purpose |
|----------|-----------|---------|
| `/analytics` | 20/min | Prevent analytics abuse |
| `/templates/advanced` | 30/hour | Control template creation |
| `/adaptive-flow` | 40/min | Allow active quiz taking |
| `/risk-scoring` | 30/min | Balance load on scoring |
| `/recommendations` | 30/min | Recommendation queries |
| `/performance-metrics` | 30/min | Metrics access |
| `/bulk-operations` | 20/hour | Prevent bulk abuse |
| `/export` | 10/hour | Export generation |

## API Endpoints

### 1. Advanced Analytics
**Endpoint:** `GET /api/v2/enhanced-quiz/analytics`

**Features:**
- Completion rate analysis
- Category breakdown
- Risk distribution
- Temporal trends
- Top performing templates

**Cache:** 15 minutes

### 2. Advanced Template Creation
**Endpoint:** `POST /api/v2/enhanced-quiz/templates/advanced`

**Features:**
- Branching logic definition
- Risk factor configuration
- Custom scoring weights
- Validation rules

**Rate Limit:** 30/hour

### 3. Adaptive Quiz Flow
**Endpoint:** `POST /api/v2/enhanced-quiz/adaptive-flow`

**Features:**
- Dynamic question routing
- Conditional logic evaluation
- Alert generation
- Progress tracking

**Rate Limit:** 40/minute

### 4. Risk Scoring
**Endpoint:** `POST /api/v2/enhanced-quiz/risk-scoring`

**Features:**
- Multi-factor risk assessment
- Historical trend analysis
- Actionable recommendations
- Confidence scoring

**Cache:** 10 minutes

### 5. Quiz Recommendations
**Endpoint:** `GET /api/v2/enhanced-quiz/recommendations`

**Features:**
- Historical pattern analysis
- Risk-based recommendations
- Priority scoring
- Due date suggestions

**Cache:** 15 minutes

### 6. Performance Metrics
**Endpoint:** `GET /api/v2/enhanced-quiz/performance-metrics`

**Features:**
- Period-over-period comparison
- Trend analysis
- Key performance indicators
- Actionable insights

**Cache:** 15 minutes

### 7. Bulk Operations
**Endpoint:** `POST /api/v2/enhanced-quiz/bulk-operations`

**Operations:**
- Assign templates to multiple patients
- Delete quiz sessions in bulk
- Update session data in bulk

**Rate Limit:** 20/hour

### 8. Quiz Export
**Endpoint:** `POST /api/v2/enhanced-quiz/export`

**Formats:**
- PDF: Formatted reports
- CSV: Tabular data
- JSON: Raw data
- XLSX: Excel spreadsheets

**Rate Limit:** 10/hour

## Security Considerations

### 1. Role-Based Access Control (RBAC)

**Admin:**
- Full access to all endpoints
- Can access all patients' data
- Can create/modify templates

**Doctor:**
- Access only to own patients
- Can create templates
- Can perform bulk operations on own patients

**Patient:**
- Access only to own quiz data
- Cannot create templates
- Cannot access analytics

### 2. Data Validation

All input data is validated using Pydantic V2 models with:
- Type checking
- Range validation
- Pattern matching
- Custom validators

### 3. SQL Injection Prevention

Using SQLAlchemy ORM with parameterized queries:
```python
query.filter(QuizSession.id == session_uuid)  # Safe
```

## Testing Strategy

### Test Coverage

1. **Unit Tests:**
   - Scoring algorithm correctness
   - Branching condition evaluation
   - Risk level classification

2. **Integration Tests:**
   - End-to-end quiz flow
   - Database operations
   - Cache functionality

3. **API Tests:**
   - All 8 endpoints
   - Authentication/Authorization
   - Error handling
   - Rate limiting

### Test Classes

- `TestEnhancedQuizAnalytics` (5 tests)
- `TestAdvancedTemplateCreation` (5 tests)
- `TestAdaptiveQuizFlow` (4 tests)
- `TestRiskScoring` (4 tests)
- `TestQuizRecommendations` (3 tests)
- `TestPerformanceMetrics` (3 tests)
- `TestBulkOperations` (5 tests)
- `TestQuizExport` (6 tests)
- `TestScoringAlgorithms` (3 tests)
- `TestCaching` (2 tests)
- `TestRateLimiting` (1 test)
- `TestRBAC` (3 tests)

**Total: 44+ test methods**

## Example Usage

### Creating an Adaptive Quiz

```python
import requests

# 1. Create advanced template
template = {
    "title": "Pain Assessment",
    "category": "pain_assessment",
    "difficulty": "advanced",
    "questions": [
        {
            "id": "q1",
            "question_text": "Rate pain (0-10)",
            "question_type": "scale",
            "required": True,
            "scoring_weight": 2.0,
            "branching_rules": [
                {
                    "conditions": [
                        {"field": "pain_level", "operator": "gte", "value": 7}
                    ],
                    "next_question_id": "q2_location",
                    "show_alert": "High pain detected"
                }
            ],
            "risk_factors": {"high_pain": 0.8}
        }
    ],
    "adaptive_flow_enabled": True,
    "risk_scoring_enabled": True
}

response = requests.post(
    "https://api.example.com/api/v2/enhanced-quiz/templates/advanced",
    json=template,
    headers={"Authorization": "Bearer TOKEN"}
)

# 2. Process adaptive flow
flow_response = requests.post(
    "https://api.example.com/api/v2/enhanced-quiz/adaptive-flow",
    json={
        "session_id": "session-uuid",
        "current_question_id": "q1",
        "response_value": 8
    },
    headers={"Authorization": "Bearer TOKEN"}
)

# 3. Calculate risk score
risk_response = requests.post(
    "https://api.example.com/api/v2/enhanced-quiz/risk-scoring",
    json={
        "patient_id": "patient-uuid",
        "lookback_days": 30
    },
    headers={"Authorization": "Bearer TOKEN"}
)
```

## Future Enhancements

1. **Machine Learning Integration:**
   - Predictive risk scoring
   - Question recommendation optimization
   - Response pattern analysis

2. **Advanced Branching:**
   - Complex multi-condition rules
   - Time-based branching
   - Context-aware routing

3. **Real-time Analytics:**
   - Live dashboard updates
   - Streaming metrics
   - Alert notifications

4. **Enhanced Exports:**
   - Custom report templates
   - Interactive dashboards
   - Data visualization

## Conclusion

The Enhanced Quiz V2 system provides a comprehensive solution for adaptive medical assessments with:
- Advanced branching logic for personalized question flow
- Sophisticated risk scoring algorithms
- Performance-optimized caching and database access
- Comprehensive testing coverage
- Secure RBAC implementation

For technical support or feature requests, please refer to the project repository.
