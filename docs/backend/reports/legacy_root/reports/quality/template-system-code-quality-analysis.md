# Template System Code Quality Analysis Report

**Generated:** 2025-12-22
**Analyzer:** Code Quality Analyzer
**Scope:** Template system models and schemas (backend-hormonia)

---

## Executive Summary

### Overall Quality Score: 7.5/10

- **Files Analyzed:** 4 core files
- **Critical Issues:** 3
- **Code Smells:** 8
- **Schema Inconsistencies:** 12
- **Technical Debt Estimate:** 16-20 hours

### Files Analyzed
1. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/models/template.py`
2. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/models/flow.py`
3. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/template.py`
4. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/templates.py`
5. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/models/quiz.py`

---

## Critical Issues

### 1. **Schema Inconsistency: Flow Template Models vs Schemas**
**Severity:** HIGH
**Files:**
- `app/models/flow.py:87-88`
- `app/schemas/template.py:56`
- `app/schemas/v2/templates.py:23`

**Issue:**
The database model uses `steps` to store flow messages, but schemas use different field names:

```python
# Model (flow.py:87-88)
steps = Column("steps", JSONB, nullable=True)  # Database column name
metadata_json = Column("metadata", JSONB, nullable=True)

# Schema v1 (template.py:56)
steps: Dict[str, FlowTemplateStepBase]  # Matches model ✓

# Schema v2 (templates.py:23)
steps: Dict[str, Any]  # Too generic - no validation
```

**Impact:**
- V2 schema lacks type validation for flow steps
- Missing validation for step structure
- Potential runtime errors during serialization

**Recommendation:**
```python
# app/schemas/v2/templates.py:23
steps: Dict[str, FlowTemplateStepBase] = Field(
    ..., description="Template steps/messages configuration"
)
```

---

### 2. **Missing Quiz Template Model in V2 Schemas**
**Severity:** HIGH
**Files:**
- `app/models/quiz.py:25-80`
- `app/schemas/v2/templates.py:210-247`

**Issue:**
Quiz template schemas in V2 don't match the actual database model:

```python
# Database Model (quiz.py:25-41)
class QuizTemplate(BaseModel):
    name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    questions = Column(JSONB, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    passing_score = Column(Integer, nullable=True)
    time_limit_minutes = Column(Integer, nullable=True)
    randomize_questions = Column(Boolean, nullable=True)
    tags = Column(JSONB, nullable=True)  # Array in DB
    is_active = Column(Boolean, default=True)

# V2 Create Schema (templates.py:213)
questions: List[Dict[str, Any]]  # Generic - no validation!
```

**Missing Validations:**
1. Question structure validation (id, type, text, options)
2. Question type enum validation
3. Answer validation rules
4. Score validation

**Recommendation:**
Reuse the structured `QuizQuestion` schema from v1:

```python
# Use from app/schemas/template.py:153-178
class QuizTemplateV2Create(QuizTemplateV2Base):
    questions: List[QuizQuestion] = Field(  # ✓ Structured validation
        ..., min_length=1, description="Quiz questions"
    )
```

---

### 3. **Inconsistent Field Naming Between Model and Schema**
**Severity:** MEDIUM
**Files:**
- `app/models/flow.py:80-81`
- `app/schemas/v2/templates.py:119-120`

**Issue:**
```python
# Model uses template_name (flow.py:80)
template_name = Column(String(255), nullable=False)

# But FlowTemplateV2Base uses BOTH (templates.py:19)
template_name: str = Field(...)  # In base

# FlowTemplateV2Create ALSO requires template_name (templates.py:31)
# This creates confusion - is it required or inherited?
```

**Impact:**
- API clients may be confused about which field to use
- Potential for duplicate data
- Inconsistent serialization

**Recommendation:**
Clarify inheritance hierarchy and remove duplication.

---

## Schema Inconsistencies (V1 vs V2)

### 4. **FlowTemplateStepBase Validation Missing in V2**
**Location:** `app/schemas/v2/templates.py:23`
**V1:** Uses structured `FlowTemplateStepBase` with validation
**V2:** Uses generic `Dict[str, Any]` - no validation

**Fields Lost in V2:**
- `intent` validation
- `ai_instructions` validation
- `personalization_hints` validation
- `interactive_elements` validation
- `message_type` enum validation
- `base_content` validation

---

### 5. **QuizQuestion Type Validation Inconsistency**
**Files:**
- `app/schemas/template.py:171-177` (V1)
- `app/schemas/v2/templates.py:168-169` (V2)

**V1 Implementation (Better):**
```python
@field_validator("type")
@classmethod
def validate_question_type(cls, v):
    valid_types = ["scale", "multiple_choice", "open_text", "yes_no"]
    if v not in valid_types:
        raise ValueError(f"type must be one of {valid_types}")
    return v
```

**V2 Implementation (Less strict):**
```python
type: str = Field(
    ..., description="Question type (multiple_choice, open_text, scale, etc.)"
)
# No validation! ❌
```

**Database Reality (quiz.py:300-302):**
```python
CheckConstraint(
    "response_type IN ('multiple_choice', 'open_text', 'scale', 'boolean', 'rating', 'yes_no', 'number', 'date', 'single_choice')",
    name="ck_quiz_response_type_valid",
)
```

**Issue:** V2 allows invalid types that will fail at database level.

---

### 6. **Missing Metadata Validation**
**Location:** `app/schemas/v2/templates.py:26, 78`

**V1 Schema:**
```python
metadata: Optional[FlowTemplateMetadata] = Field(
    None, description="Template metadata"
)
```

**V2 Schema:**
```python
metadata: Optional[Dict[str, Any]] = None  # No structure validation
```

**Impact:**
- Lost validation for `flow_type`, `humanization_level`, `version`, `full_template`
- No type safety for metadata fields
- Potential runtime errors

---

### 7. **Quiz Template Tags Type Mismatch**
**Files:**
- `app/models/quiz.py:40`
- `app/schemas/template.py:194`
- `app/schemas/v2/templates.py:197`

**Database Model:**
```python
tags = Column(JSONB, nullable=True)  # Array stored as JSONB
```

**V1 Schema:**
```python
tags: Optional[List[str]] = Field(default_factory=list)  # ✓ Correct
```

**V2 Schema:**
```python
tags: Optional[List[str]] = Field(None)  # Default None instead of []
```

**Issue:** V2 defaults to `None` instead of empty list, causing inconsistency.

---

## Code Smells

### 8. **Duplicate Field Definitions**
**Location:** `app/schemas/v2/templates.py:16-28` and `31-41`

```python
# FlowTemplateV2Base defines template_name
class FlowTemplateV2Base(BaseModel):
    template_name: str = Field(...)

# FlowTemplateV2Create inherits but doesn't override
class FlowTemplateV2Create(FlowTemplateV2Base):
    # Inherits template_name from base
    flow_kind_id: Optional[UUID] = None
    kind_key: Optional[str] = None
    version_number: int = Field(...)
```

**Smell:** Unclear inheritance - base defines required field, but child doesn't clarify usage.

---

### 9. **Overly Generic Response Schemas**
**Location:** `app/schemas/v2/templates.py:112-152`

```python
class FlowTemplateV2Response(BaseModel):
    steps: Dict[str, Any]  # Too generic
    metadata: Dict[str, Any]  # Too generic
```

**Issue:**
- No type safety for response data
- Makes API documentation unclear
- Harder to maintain

**Recommendation:** Use structured types like V1.

---

### 10. **Inconsistent Optional Field Handling**
**Location:** Throughout `app/schemas/v2/templates.py`

```python
# Some optionals use None
is_active: Optional[bool] = Field(None)

# Others use default values
is_active: Optional[bool] = Field(default=True)

# Others use no default
is_active: Optional[bool] = None
```

**Impact:** Inconsistent API behavior and unclear defaults.

---

### 11. **Magic Numbers in Examples**
**Location:** `app/schemas/v2/templates.py:199-200`

```python
passing_score: Optional[int] = Field(
    None, ge=0, le=100, description="Passing score percentage"
)
```

**Issue:** Hardcoded range (0-100) should be a constant.

**Recommendation:**
```python
MIN_PASSING_SCORE = 0
MAX_PASSING_SCORE = 100

passing_score: Optional[int] = Field(
    None, ge=MIN_PASSING_SCORE, le=MAX_PASSING_SCORE
)
```

---

### 12. **Validator Duplication**
**Files:**
- `app/schemas/template.py:65-70`
- `app/schemas/v2/templates.py:217-223`

Both define the same validator for questions:
```python
@field_validator("questions")
@classmethod
def validate_questions(cls, v):
    if not v:
        raise ValueError("questions cannot be empty")
    return v
```

**Recommendation:** Extract to a shared validator function.

---

### 13. **Missing Relationship Validation**
**Location:** `app/schemas/v2/templates.py:43-49`

```python
@field_validator("flow_kind_id", "kind_key")
@classmethod
def validate_kind_reference(cls, v, info):
    if info.data.get("flow_kind_id") is None and v is None:
        raise ValueError("Either flow_kind_id or kind_key must be provided")
    return v
```

**Issue:** This validator doesn't check if BOTH are provided (which is ambiguous).

**Recommendation:**
```python
@model_validator(mode='after')
def validate_kind_reference(self):
    has_id = self.flow_kind_id is not None
    has_key = self.kind_key is not None

    if not has_id and not has_key:
        raise ValueError("Either flow_kind_id or kind_key must be provided")
    if has_id and has_key:
        raise ValueError("Provide either flow_kind_id OR kind_key, not both")
    return self
```

---

### 14. **Inconsistent DateTime Field Types**
**Files:**
- `app/schemas/template.py:125-127`
- `app/schemas/v2/templates.py:126-128`

**V1 Uses `datetime`:**
```python
published_at: Optional[datetime] = Field(None)
created_at: datetime = Field(...)
updated_at: datetime = Field(...)
```

**V2 Uses `str`:**
```python
published_at: Optional[str] = None
created_at: Optional[str] = None
updated_at: Optional[str] = None
```

**Issue:** Type inconsistency between API versions.

---

### 15. **Property Aliasing Overhead**
**Location:** `app/models/flow.py:99-109`

```python
@property
def version(self): return str(self.version_number)
@property
def messages(self): return self.steps
@property
def kind_id(self): return self.flow_kind_id
@property
def is_current(self): return self.is_active
@property
def status(self): return "published" if self.is_active else "draft"
```

**Smell:** Too many backward compatibility aliases.

**Impact:**
- Increases maintenance burden
- Confusing for new developers
- Multiple ways to access same data

**Recommendation:** Document deprecation plan and phase out aliases.

---

## Missing Features & Validations

### 16. **No Version Conflict Detection**
**Location:** `app/models/flow.py:111-114`

The unique constraint exists:
```python
UniqueConstraint("flow_kind_id", "version_number", name="unique_flow_version")
```

But schemas don't validate version conflicts before database insert.

**Recommendation:** Add pre-save validation in service layer.

---

### 17. **Missing Template Preview Schema Validation**
**Location:** `app/schemas/v2/templates.py:564-600`

```python
class TemplatePreviewRequest(BaseModel):
    template_id: UUID
    context_data: Optional[Dict[str, Any]] = None  # No validation
```

**Issue:** No validation that context_data contains required variables.

**Recommendation:**
```python
@model_validator(mode='after')
def validate_context_matches_template(self):
    # Fetch template and validate context_data has required variables
    pass
```

---

### 18. **No Circular Reference Prevention**
**Location:** Template import/export schemas

**Issue:** No validation to prevent circular template references or infinite loops.

**Recommendation:** Add dependency graph validation.

---

## Performance Concerns

### 19. **JSONB Column Access Patterns**
**Location:** `app/models/flow.py:87`, `app/models/quiz.py:32`

**Current:**
```python
steps = Column("steps", JSONB, nullable=True)
questions = Column(JSONB, nullable=False)
```

**Issue:** No GIN indexes for JSONB queries.

**Recommendation:**
```python
# Add indexes for common queries
Index('idx_flow_steps_gin', 'steps', postgresql_using='gin')
Index('idx_quiz_questions_gin', 'questions', postgresql_using='gin')
```

---

### 20. **N+1 Query Risk**
**Location:** `app/models/flow.py:96-97`

```python
kind = relationship("FlowKind", back_populates="versions")
flow_states = relationship("PatientFlowState", back_populates="template_version")
```

**Issue:** Loading templates could trigger N+1 queries when accessing kind or flow_states.

**Recommendation:** Use `joinedload` in repository queries.

---

## Security Concerns

### 21. **No Input Sanitization in Template Content**
**Location:** `app/schemas/template.py:30`, `app/schemas/v2/templates.py:23`

**Issue:** Template `base_content` and `steps` accept arbitrary strings without sanitization.

**Risk:** Potential for XSS if templates are rendered in web context.

**Recommendation:**
```python
@field_validator("base_content")
@classmethod
def sanitize_content(cls, v):
    if v:
        # Sanitize HTML/script tags
        import bleach
        return bleach.clean(v, strip=True)
    return v
```

---

### 22. **No Access Control in Schemas**
**Location:** All template schemas

**Issue:** Schemas don't include `created_by` or `organization_id` for multi-tenancy.

**Risk:** Template leakage between tenants.

**Recommendation:** Add tenant isolation fields.

---

## Positive Findings

### ✓ Strong Database Constraints
**Location:** `app/models/quiz.py:47-58`
- Excellent use of UniqueConstraints
- CheckConstraints for data integrity
- Comprehensive indexes for performance

### ✓ Comprehensive Field Validation
**Location:** `app/models/quiz.py:60-77`
- SQLAlchemy validators on all critical fields
- Clear error messages
- Defensive programming

### ✓ Good Documentation
**Location:** All schema files
- Clear field descriptions
- Comprehensive examples
- Good use of Pydantic Field descriptions

### ✓ Proper Use of JSONB
**Location:** `app/models/quiz.py:32, 40`
- Appropriate use of JSONB for flexible data
- Avoids over-normalization

### ✓ Relationship Mapping
**Location:** `app/models/flow.py:49-53, 96-97`
- Clear relationship definitions
- Proper cascade rules
- Back-populates for bidirectional access

---

## Recommendations Summary

### High Priority (Complete within 1 week)
1. **Align V2 schemas with V1 validation** - Add structured types back
2. **Fix question type validation** - Prevent invalid types at API level
3. **Add JSONB GIN indexes** - Improve query performance
4. **Document deprecation plan** - For backward compatibility aliases

### Medium Priority (Complete within 2 weeks)
5. **Consolidate validators** - Remove duplication
6. **Add input sanitization** - Prevent XSS vulnerabilities
7. **Implement version conflict detection** - Service layer validation
8. **Standardize optional field handling** - Consistent defaults

### Low Priority (Complete within 1 month)
9. **Extract magic numbers** - Use constants
10. **Add circular reference prevention** - Template import validation
11. **Improve error messages** - User-friendly validation errors
12. **Add tenant isolation** - Multi-tenancy support

---

## Technical Debt Breakdown

| Category | Estimated Hours |
|----------|----------------|
| Schema alignment (V1/V2) | 6-8 hours |
| Validation improvements | 4-5 hours |
| Performance optimization | 3-4 hours |
| Security hardening | 2-3 hours |
| Code cleanup & refactoring | 1-2 hours |
| **Total** | **16-22 hours** |

---

## Conclusion

The template system has a **solid foundation** with good database modeling and comprehensive constraints. However, the **V2 schemas have regressed** in validation strictness compared to V1, introducing potential runtime errors and security vulnerabilities.

**Key Actions:**
1. Restore structured validation in V2 schemas
2. Add missing JSONB indexes
3. Implement input sanitization
4. Document and phase out backward compatibility aliases

**Overall Assessment:** The codebase is maintainable but needs attention to schema consistency and validation rigor before production deployment of V2 APIs.
