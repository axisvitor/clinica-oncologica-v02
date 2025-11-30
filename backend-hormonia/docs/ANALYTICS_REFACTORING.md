# Analytics Refactoring Documentation

## Overview

The `analytics.py` file has been refactored from a monolithic structure into a modular, maintainable architecture organized by domain responsibility.

## New Structure

```
app/api/v2/routers/analytics/
├── __init__.py                   # Main router aggregator (24 lines)
├── base.py                       # Common utilities & caching (170 lines)
├── patient_analytics.py          # Patient metrics & risk assessment (150 lines)
├── quiz_analytics.py             # Quiz status & completion trends (140 lines)
└── dashboard_analytics.py        # Overview & treatment distribution (250 lines)
```

## Migration Details

### Original File
- **Location**: `app/api/v2/routers/analytics.py`
- **Size**: 672 lines
- **Backed up to**: `app/api/v2/routers/analytics_legacy.py`

### Modular Architecture

#### 1. `__init__.py` - Router Aggregator
**Purpose**: Central router that includes all analytics sub-routers

**Exports**:
- `router` - Main APIRouter with all analytics endpoints

**Tags**:
- `analytics-base`
- `analytics-patients`
- `analytics-quizzes`
- `analytics-dashboard`

#### 2. `base.py` - Shared Utilities
**Purpose**: Common functions, types, and caching logic

**Functions**:
- `get_role_and_user()` - Extract role and UUID from current_user
- `serialize_patient_risk()` - Convert PatientRisk to JSON
- `get_cache_key()` - Generate Redis cache keys
- `get_cached_result()` - Read from Redis cache
- `set_cached_result()` - Write to Redis cache

**Constants**:
- `ANALYTICS_CACHE_TTL` - 900 seconds (15 minutes)
- `COLOR_PALETTE` - Chart color scheme

#### 3. `patient_analytics.py` - Patient Metrics
**Purpose**: Patient engagement and risk assessment endpoints

**Endpoints**:
- `GET /patient-engagement` - Engagement levels distribution
- `GET /risk-assessment` - At-risk patients identification

**Metrics**:
- No quizzes / Low engagement / High engagement
- Average quizzes per patient
- Risk levels with recommended actions

#### 4. `quiz_analytics.py` - Quiz Analytics
**Purpose**: Quiz-related analytics and trends

**Endpoints**:
- `GET /quiz-status` - Status distribution (started/completed/cancelled)
- `GET /completion-trend` - Monthly completion trends

**Features**:
- Month/year filtering
- Configurable lookback periods (1-24 months)
- Doctor-specific filtering for non-admin users

#### 5. `dashboard_analytics.py` - Dashboard Metrics
**Purpose**: High-level overview and treatment analytics

**Endpoints**:
- `GET /overview` - Key metrics dashboard
- `GET /treatment-distribution` - Treatment type distribution

**Features**:
- Total patients, quizzes, completion rates
- Active patients (last 30 days)
- Weekly trend analysis
- Period filtering (7d/30d/90d/all)

## Backward Compatibility

### Import Path Changes

**Before**:
```python
from app.api.v2.routers.analytics import router as analytics_router
```

**After** (No change required):
```python
from app.api.v2.routers.analytics import router as analytics_router
```

The import path remains the same - the package `__init__.py` exports the aggregated router.

### API Endpoints

All endpoints maintain the same URLs and response structures:

```
GET /api/v2/analytics/overview
GET /api/v2/analytics/quiz-status
GET /api/v2/analytics/completion-trend
GET /api/v2/analytics/patient-engagement
GET /api/v2/analytics/treatment-distribution
GET /api/v2/analytics/risk-assessment
```

## Benefits

### 1. **Maintainability**
- Each module has < 300 lines
- Single Responsibility Principle
- Clear domain boundaries

### 2. **Testability**
- Isolated functions easier to unit test
- Mock dependencies per module
- Separate test files per domain

### 3. **Performance**
- Shared caching logic in `base.py`
- Redis-based result caching
- Optimized database queries

### 4. **Scalability**
- Easy to add new analytics modules
- Clear patterns for new endpoints
- Minimal coupling between modules

## Code Quality Improvements

### Type Hints
```python
def get_role_and_user(current_user) -> Tuple[UserRole, Optional[UUID]]:
    """Extract role and user UUID from current_user."""
    ...
```

### Docstrings
```python
async def get_patient_engagement(
    db = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Get patient engagement metrics.

    Returns:
    - Patients with 0 quizzes
    - Patients with 1-5 quizzes
    - Patients with 6+ quizzes
    - Average quizzes per patient
    """
```

### Error Handling
```python
try:
    cached = await redis_client.get(cache_key)
    if cached:
        logger.debug(f"Cache HIT: {cache_key}")
        return json.loads(cached)
except Exception as e:
    logger.warning(f"Cache read failed: {e}")
    return None
```

## Testing Strategy

### Unit Tests
```python
# tests/api/v2/test_patient_analytics.py
def test_get_patient_engagement():
    """Test patient engagement endpoint."""
    ...

# tests/api/v2/test_quiz_analytics.py
def test_completion_trend():
    """Test completion trend calculation."""
    ...
```

### Integration Tests
```python
# tests/integration/test_analytics_cache.py
async def test_cache_hit_miss():
    """Verify caching behavior."""
    ...
```

## Migration Checklist

- [x] Create modular structure
- [x] Extract base utilities to `base.py`
- [x] Separate patient analytics
- [x] Separate quiz analytics
- [x] Separate dashboard analytics
- [x] Create aggregator `__init__.py`
- [x] Backup original file
- [x] Maintain backward compatibility
- [x] Document changes
- [ ] Run existing tests
- [ ] Update tests if needed
- [ ] Deploy to staging
- [ ] Monitor production metrics

## Rollback Plan

If issues are encountered, restore the original file:

```bash
cd backend-hormonia/app/api/v2/routers
rm -rf analytics/
mv analytics_legacy.py analytics.py
```

## Future Enhancements

### Potential New Modules

1. **medication_analytics.py**
   - Medication adherence rates
   - Side effect tracking
   - Treatment efficacy metrics

2. **treatment_analytics.py**
   - Treatment plan analytics
   - Outcome tracking
   - Protocol compliance

3. **message_analytics.py**
   - WhatsApp message analytics
   - Response time metrics
   - Engagement patterns

4. **physician_analytics.py**
   - Doctor performance metrics
   - Patient load distribution
   - Response quality metrics

5. **export_analytics.py**
   - CSV/Excel export
   - PDF report generation
   - Scheduled reports

## Performance Metrics

### File Size Reduction
- Original: 1 file × 672 lines
- Refactored: 5 files (avg 147 lines each)
- **Improvement**: Each module < 300 lines

### Code Organization
- **Separation of Concerns**: ✓ High
- **Testability**: ✓ Improved
- **Maintainability**: ✓ Excellent

## Contact

For questions or issues with this refactoring, contact the development team or create an issue in the project repository.

## References

- Original file: `app/api/v2/routers/analytics_legacy.py`
- FastAPI documentation: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- Python module best practices: https://docs.python.org/3/tutorial/modules.html
