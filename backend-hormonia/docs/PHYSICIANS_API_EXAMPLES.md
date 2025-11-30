# Physicians API - Usage Examples

## Overview

Examples demonstrating how to use the refactored physicians module with optimized performance.

## Service Layer Usage

### Basic Statistics Calculation

```python
from app.api.v2.routers.physicians.services import PhysicianStatisticsService

def get_physician_stats(physician_id: UUID, db: Session):
    """Get physician statistics with caching."""
    stats_service = PhysicianStatisticsService(db, cache_ttl=300)

    # Automatically uses Redis cache if available
    statistics = stats_service.calculate_statistics(
        physician_id,
        use_cache=True
    )

    return statistics
```

### Batch Statistics Processing

```python
from app.api.v2.routers.physicians.services import PhysicianStatisticsService

def get_all_physician_stats(db: Session):
    """Get statistics for all physicians efficiently."""
    # Get all physician IDs
    physician_ids = db.query(User.id).filter(
        User.role == UserRole.DOCTOR,
        User.is_active == True
    ).all()

    physician_ids = [pid[0] for pid in physician_ids]

    # Batch calculate with caching
    stats_service = PhysicianStatisticsService(db)
    all_stats = stats_service.calculate_batch_statistics(physician_ids)

    return all_stats
```

### Cache Invalidation

```python
from app.api.v2.routers.physicians.services import PhysicianStatisticsService

def update_physician_and_invalidate_cache(
    physician_id: UUID,
    db: Session,
    update_data: dict
):
    """Update physician and invalidate cached statistics."""
    # Update physician
    physician = db.query(User).filter(User.id == physician_id).first()
    for key, value in update_data.items():
        setattr(physician, key, value)

    db.commit()

    # Invalidate cache
    stats_service = PhysicianStatisticsService(db)
    stats_service.invalidate_cache(physician_id)
```

## Availability Service Usage

### Check Availability

```python
from app.api.v2.routers.physicians.services import PhysicianAvailabilityService
from datetime import datetime, timedelta

def is_physician_free(physician_id: UUID, db: Session):
    """Check if physician is available tomorrow at 2 PM."""
    availability_service = PhysicianAvailabilityService(db)

    requested_time = datetime.utcnow().replace(
        hour=14, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)

    is_available = availability_service.is_available(
        physician_id,
        requested_time,
        duration_minutes=30
    )

    return is_available
```

### Get Weekly Schedule

```python
from app.api.v2.routers.physicians.services import PhysicianAvailabilityService
from datetime import date, timedelta

def get_weekly_schedule(physician_id: UUID, db: Session):
    """Get physician's schedule for the next week."""
    availability_service = PhysicianAvailabilityService(db)

    today = date.today()
    next_week = today + timedelta(days=7)

    schedule = availability_service.get_schedule(
        physician_id,
        start_date=today,
        end_date=next_week
    )

    return schedule
```

## API Endpoint Examples

### List Physicians with Filters

```bash
# List all active physicians
curl -X GET "http://localhost:8000/api/v2/physicians?status=active" \
  -H "Authorization: Bearer ${TOKEN}"

# Search by name
curl -X GET "http://localhost:8000/api/v2/physicians?search=Smith" \
  -H "Authorization: Bearer ${TOKEN}"

# Filter by workload level
curl -X GET "http://localhost:8000/api/v2/physicians?workload=low" \
  -H "Authorization: Bearer ${TOKEN}"

# Filter by patient count range
curl -X GET "http://localhost:8000/api/v2/physicians?min_patients=10&max_patients=50" \
  -H "Authorization: Bearer ${TOKEN}"

# With statistics included
curl -X GET "http://localhost:8000/api/v2/physicians?include=statistics" \
  -H "Authorization: Bearer ${TOKEN}"

# Field selection (reduce payload)
curl -X GET "http://localhost:8000/api/v2/physicians?fields=id,email,full_name,workload_level" \
  -H "Authorization: Bearer ${TOKEN}"
```

### Get Physician Details

```bash
# Basic profile
curl -X GET "http://localhost:8000/api/v2/physicians/${PHYSICIAN_ID}" \
  -H "Authorization: Bearer ${TOKEN}"

# With statistics
curl -X GET "http://localhost:8000/api/v2/physicians/${PHYSICIAN_ID}?include=statistics" \
  -H "Authorization: Bearer ${TOKEN}"
```

### Get Statistics

```bash
# Detailed statistics
curl -X GET "http://localhost:8000/api/v2/physicians/${PHYSICIAN_ID}/statistics" \
  -H "Authorization: Bearer ${TOKEN}"

# Force recalculation (bypass cache)
curl -X GET "http://localhost:8000/api/v2/physicians/${PHYSICIAN_ID}/statistics?use_cache=false" \
  -H "Authorization: Bearer ${TOKEN}"
```

### Update Physician

```bash
# Update physician information (Admin only)
curl -X PATCH "http://localhost:8000/api/v2/physicians/${PHYSICIAN_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Dr. John Smith",
    "specialties": ["oncology", "hematology"],
    "phone": "+1234567890",
    "bio": "Experienced oncologist with 15+ years"
  }'
```

### Availability Endpoints

```bash
# Get schedule for date range
curl -X GET "http://localhost:8000/api/v2/physicians/${PHYSICIAN_ID}/schedule?start_date=2025-12-01&end_date=2025-12-07" \
  -H "Authorization: Bearer ${TOKEN}"

# Check availability for specific time
curl -X GET "http://localhost:8000/api/v2/physicians/${PHYSICIAN_ID}/availability?requested_datetime=2025-12-01T14:00:00Z&duration_minutes=30" \
  -H "Authorization: Bearer ${TOKEN}"

# Find next available slot
curl -X GET "http://localhost:8000/api/v2/physicians/${PHYSICIAN_ID}/next-available?duration_minutes=30&max_days_ahead=14" \
  -H "Authorization: Bearer ${TOKEN}"
```

## Custom Integration Examples

### Dashboard Widget

```python
from app.api.v2.routers.physicians.services import PhysicianStatisticsService

async def get_dashboard_stats(db: Session):
    """Get statistics for dashboard widget."""
    stats_service = PhysicianStatisticsService(db)

    # Get all physicians
    physicians = db.query(User).filter(
        User.role == UserRole.DOCTOR,
        User.is_active == True
    ).all()

    physician_ids = [p.id for p in physicians]

    # Batch calculate
    all_stats = stats_service.calculate_batch_statistics(physician_ids)

    # Aggregate for dashboard
    dashboard_data = {
        "total_physicians": len(physicians),
        "total_patients": sum(s.total_patients for s in all_stats.values()),
        "avg_workload": sum(s.total_patients for s in all_stats.values()) / len(physicians),
        "physicians_overloaded": sum(
            1 for s in all_stats.values()
            if s.workload_level == WorkloadLevel.OVERLOADED
        ),
    }

    return dashboard_data
```

### Automated Reporting

```python
from app.api.v2.routers.physicians.services import PhysicianStatisticsService
from datetime import datetime

async def generate_weekly_report(db: Session):
    """Generate weekly performance report."""
    stats_service = PhysicianStatisticsService(db)

    physicians = db.query(User).filter(
        User.role == UserRole.DOCTOR,
        User.is_active == True
    ).all()

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "physicians": []
    }

    for physician in physicians:
        stats = stats_service.calculate_statistics(physician.id)

        physician_report = {
            "id": str(physician.id),
            "name": physician.full_name,
            "total_patients": stats.total_patients,
            "active_patients": stats.active_patients,
            "workload_level": stats.workload_level.value,
            "patient_satisfaction": stats.patient_satisfaction_score,
            "response_rate": stats.messages.response_rate,
            "avg_response_time": stats.messages.avg_response_time_minutes,
        }

        report["physicians"].append(physician_report)

    return report
```

### Performance Monitoring

```python
from app.api.v2.routers.physicians.services import PhysicianStatisticsService
import time

async def benchmark_statistics_calculation(db: Session):
    """Benchmark statistics calculation performance."""
    physicians = db.query(User).filter(
        User.role == UserRole.DOCTOR
    ).limit(10).all()

    stats_service = PhysicianStatisticsService(db)

    # Without cache
    start = time.time()
    for physician in physicians:
        stats_service.calculate_statistics(physician.id, use_cache=False)
    no_cache_time = time.time() - start

    # With cache
    start = time.time()
    for physician in physicians:
        stats_service.calculate_statistics(physician.id, use_cache=True)
    with_cache_time = time.time() - start

    return {
        "physicians_count": len(physicians),
        "no_cache_time_seconds": no_cache_time,
        "with_cache_time_seconds": with_cache_time,
        "speedup": no_cache_time / with_cache_time if with_cache_time > 0 else 0,
    }
```

## Response Examples

### List Physicians Response

```json
{
  "data": [
    {
      "id": "uuid-here",
      "email": "physician@clinic.com",
      "full_name": "Dr. John Smith",
      "role": "doctor",
      "is_active": true,
      "specialties": ["oncology"],
      "status": "active",
      "assigned_patients_count": 25,
      "active_patients_count": 20,
      "workload_level": "medium",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-11-30T10:00:00Z"
    }
  ],
  "next_cursor": "base64-encoded-cursor",
  "has_more": true,
  "total": 50
}
```

### Statistics Response

```json
{
  "total_patients": 25,
  "active_patients": 20,
  "inactive_patients": 5,
  "new_patients_this_month": 3,
  "workload_level": "medium",
  "messages": {
    "total_sent": 150,
    "total_received": 200,
    "unread_count": 5,
    "response_rate": 0.95,
    "avg_response_time_minutes": 12.5
  },
  "appointments": {
    "total_scheduled": 30,
    "completed": 25,
    "cancelled": 2,
    "upcoming": 3,
    "today": 1
  },
  "alerts": {
    "total": 10,
    "critical": 1,
    "high": 2,
    "medium": 4,
    "low": 3
  },
  "patient_satisfaction_score": 4.2,
  "avg_treatment_duration_days": 45.3,
  "calculated_at": "2025-11-30T10:30:00Z"
}
```

## Performance Tips

1. **Use Caching**: Always use `use_cache=True` in production
2. **Batch Processing**: Use `calculate_batch_statistics` for multiple physicians
3. **Field Selection**: Use `?fields=` to reduce response payload
4. **Pagination**: Use cursor-based pagination for large datasets
5. **Cache Invalidation**: Invalidate cache after updates to ensure data consistency
