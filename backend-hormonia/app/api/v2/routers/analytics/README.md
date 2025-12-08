# Analytics Module - Developer Guide

## Quick Start

### Import the Router
```python
from app.api.v2.routers.analytics import router as analytics_router
```

### Add to Your API
```python
api_v2_router.include_router(analytics_router, prefix="/analytics", tags=["analytics-v2"])
```

## Module Structure

```
analytics/
├── __init__.py              # Router aggregator
├── base.py                  # Common utilities & caching
├── patient_analytics.py     # Patient engagement & risk
├── quiz_analytics.py        # Quiz status & trends
└── dashboard_analytics.py   # Overview & treatment distribution
```

## Available Endpoints

### Patient Analytics
- `GET /patient-engagement` - Patient engagement distribution
- `GET /risk-assessment` - At-risk patient identification

### Quiz Analytics
- `GET /quiz-status` - Quiz status distribution
- `GET /completion-trend` - Monthly completion trends

### Dashboard Analytics
- `GET /overview` - High-level overview metrics
- `GET /treatment-distribution` - Treatment type distribution

## Common Utilities (base.py)

### Role & User Extraction
```python
from .base import get_role_and_user

role, user_uuid = get_role_and_user(current_user)
```

### Caching
```python
from .base import get_cache_key, get_cached_result, set_cached_result

# Generate cache key
cache_key = get_cache_key("endpoint-name", param1=value1, param2=value2)

# Check cache
cached = await get_cached_result(cache_key)
if cached:
    return cached

# Set cache
result = {"data": "..."}
await set_cached_result(cache_key, result, ttl=900)
```

### Patient Risk Serialization
```python
from .base import serialize_patient_risk

serialized = serialize_patient_risk(patient_risk, patient_lookup)
```

## Adding New Analytics

### 1. Create New Module
```python
# analytics/medication_analytics.py
from fastapi import APIRouter, Depends
from .base import get_role_and_user, get_cache_key

router = APIRouter()

@router.get("/medication-adherence")
async def get_medication_adherence(...):
    """Your endpoint logic"""
    pass
```

### 2. Register in __init__.py
```python
from .medication_analytics import router as medication_router

router.include_router(medication_router, tags=["analytics-medications"])
```

## Best Practices

### 1. Always Use Caching
```python
# Check cache first
cache_key = get_cache_key("my-endpoint", **params)
cached = await get_cached_result(cache_key)
if cached:
    return cached

# ... compute result ...

# Cache before returning
await set_cached_result(cache_key, result)
return result
```

### 2. Apply Role-Based Filtering
```python
role, user_uuid = get_role_and_user(current_user)

if role != UserRole.ADMIN and user_uuid:
    query = query.filter(Patient.doctor_id == user_uuid)
```

### 3. Use Type Hints
```python
from typing import Optional, Dict, List
from datetime import datetime

async def my_endpoint(
    param: Optional[int] = None,
    db = Depends(get_db),
) -> Dict[str, Any]:
    """Always include docstrings."""
    pass
```

### 4. Include Docstrings
```python
async def get_analytics(...):
    """
    Get analytics metrics.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Dict with metrics data
    """
```

### 5. Error Handling
```python
try:
    result = await some_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise HTTPException(status_code=500, detail="Internal error")
```

## Testing

### Unit Test Example
```python
# tests/api/v2/analytics/test_patient_analytics.py
import pytest
from app.api.v2.routers.analytics.patient_analytics import get_patient_engagement

async def test_patient_engagement(mock_db, mock_user):
    result = await get_patient_engagement(db=mock_db, current_user=mock_user)
    assert "engagement_levels" in result
    assert result["total_active_patients"] >= 0
```

### Integration Test Example
```python
# tests/integration/test_analytics_endpoints.py
def test_patient_engagement_endpoint(client, auth_headers):
    response = client.get("/api/v2/analytics/patient-engagement", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "engagement_levels" in data
```

## Performance Tips

### 1. Use Database Indexes
Ensure indexes exist on commonly filtered columns:
- `Patient.doctor_id`
- `Patient.created_at`
- `QuizSession.patient_id`
- `QuizSession.created_at`
- `QuizSession.status`

### 2. Optimize Queries
```python
# Use func.count() instead of loading all records
total = db.query(func.count(Patient.id)).scalar()

# Use joins instead of multiple queries
query = db.query(Patient).join(QuizSession)
```

### 3. Cache Expensive Operations
```python
# Cache for 15 minutes
ANALYTICS_CACHE_TTL = 900
await set_cached_result(cache_key, result, ttl=ANALYTICS_CACHE_TTL)
```

## Monitoring

### Log Important Events
```python
from app.utils.logging import get_logger

logger = get_logger(__name__)

logger.info(f"Analytics query: endpoint={endpoint}, user={user_uuid}")
logger.debug(f"Cache HIT: {cache_key}")
logger.warning(f"Slow query detected: {duration}ms")
logger.error(f"Query failed: {error}")
```

### Track Metrics
```python
# Track query performance
start = datetime.utcnow()
result = await expensive_query()
duration = (datetime.utcnow() - start).total_seconds()

if duration > 1.0:
    logger.warning(f"Slow analytics query: {duration}s")
```

## Troubleshooting

### Import Errors
```bash
# Verify import works
python3 -c "from app.api.v2.routers.analytics import router; print('✓ OK')"
```

### Cache Issues
```bash
# Check Redis connection
redis-cli ping

# Clear analytics cache
redis-cli --scan --pattern "analytics:v2:*" | xargs redis-cli del
```

### Query Performance
```sql
-- Check for missing indexes
EXPLAIN ANALYZE SELECT ... FROM patients WHERE doctor_id = '...';

-- Create index if needed
CREATE INDEX idx_patients_doctor_id ON patients(doctor_id);
```

## Migration from Legacy

If you need to access legacy code:
```python
# Original file is backed up at:
from app.api.v2.routers.analytics_legacy import router as legacy_router
```

## References

- FastAPI Bigger Applications: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- SQLAlchemy Query API: https://docs.sqlalchemy.org/en/14/orm/query.html
- Redis Python Client: https://redis-py.readthedocs.io/en/stable/
- Pydantic Models: https://pydantic-docs.helpmanual.io/

## Support

- Issues: Create an issue in the repository
- Documentation: See `/docs/ANALYTICS_REFACTORING.md`
- Team: Contact the development team
