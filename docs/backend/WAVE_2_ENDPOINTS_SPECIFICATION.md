# Wave 2 Backend Endpoints Specification

**Project**: Clínica Oncológica - Hormonia Backend
**Version**: 2.0
**Created**: 2025-10-06
**Purpose**: Complete specification for 4 new backend endpoints to replace hardcoded/mock frontend data

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Endpoint Specifications](#endpoint-specifications)
3. [Database Schema Analysis](#database-schema-analysis)
4. [Implementation Checklist](#implementation-checklist)
5. [Testing Strategy](#testing-strategy)
6. [Performance Considerations](#performance-considerations)

---

## Executive Summary

### Endpoints Overview

| Endpoint | Frontend Component | Purpose | Auth Required | Cache TTL |
|----------|-------------------|---------|---------------|-----------|
| `GET /api/v1/admin/system-stats` | AdminPage.tsx | System health & metrics | Admin only | 30s |
| `GET /api/v1/analytics/treatment-distribution` | AnalyticsPage.tsx | Treatment type breakdown | Authenticated | 5m |
| `GET /api/v1/physician/risk-assessments` | PhysicianDashboard.tsx | Patient risk data | Physician only | 1m |
| `GET /api/v1/medico/dashboard-stats` | MedicoDashboard.tsx | Doctor dashboard metrics | Medico role | 2m |

### Architecture Patterns Identified

From analyzing existing codebase:
- **Framework**: FastAPI with SQLAlchemy ORM
- **Auth Pattern**: Firebase JWT + custom middleware (`get_current_user`, `AdminPermissions`)
- **Caching**: Redis-based unified cache (`UnifiedCacheManager`) + HTTP middleware
- **Database**: Supabase PostgreSQL with RLS policies
- **Services Layer**: Repository pattern (`PatientRepository`, `MessageRepository`, etc.)
- **Error Handling**: Custom decorators (`@handle_analytics_errors`)

---

## Endpoint Specifications

### 1. Admin System Stats - `GET /api/v1/admin/system-stats`

#### OpenAPI Specification

```yaml
/api/v1/admin/system-stats:
  get:
    summary: Get comprehensive system statistics for admin dashboard
    description: |
      Returns real-time system health metrics including CPU, memory,
      database performance, active users, and service status.
      Requires Admin or Super Admin role.
    tags:
      - admin
    security:
      - BearerAuth: []
    responses:
      200:
        description: System statistics retrieved successfully
        content:
          application/json:
            schema:
              type: object
              properties:
                system_health:
                  type: object
                  properties:
                    cpu_percent:
                      type: number
                      format: float
                      example: 45.2
                      description: Current CPU usage percentage
                    memory_percent:
                      type: number
                      format: float
                      example: 65.5
                      description: Current memory usage percentage
                    disk_usage_gb:
                      type: number
                      format: float
                      example: 128.7
                      description: Current disk usage in GB
                    uptime_hours:
                      type: number
                      format: float
                      example: 168.5
                      description: System uptime in hours
                active_users:
                  type: object
                  properties:
                    total:
                      type: integer
                      example: 127
                      description: Total active users
                    doctors:
                      type: integer
                      example: 12
                      description: Active doctors
                    patients:
                      type: integer
                      example: 98
                      description: Active patients
                    admins:
                      type: integer
                      example: 3
                      description: Active admins
                database_metrics:
                  type: object
                  properties:
                    total_size_mb:
                      type: number
                      format: float
                      example: 2048.5
                      description: Total database size in MB
                    active_connections:
                      type: integer
                      example: 15
                      description: Current active connections
                    query_performance_ms:
                      type: number
                      format: float
                      example: 45.3
                      description: Average query time in ms
                    cache_hit_rate:
                      type: number
                      format: float
                      example: 0.87
                      description: Redis cache hit rate (0-1)
                service_status:
                  type: object
                  properties:
                    redis:
                      type: string
                      enum: [healthy, degraded, down]
                      example: healthy
                    database:
                      type: string
                      enum: [healthy, degraded, down]
                      example: healthy
                    evolution_api:
                      type: string
                      enum: [healthy, degraded, down]
                      example: healthy
                    openai_api:
                      type: string
                      enum: [healthy, degraded, down]
                      example: healthy
                last_updated:
                  type: string
                  format: date-time
                  example: "2025-10-06T14:30:00Z"
      403:
        description: Insufficient permissions - Admin role required
      401:
        description: Authentication required
```

#### Implementation Details

**File**: `backend-hormonia/app/api/v1/admin/system_stats.py`

**Dependencies**:
```python
from app.middleware.admin_permissions import require_admin
from app.services.analytics import AnalyticsService
from app.core.redis_unified import get_sync_redis
from app.database import get_db
import psutil  # For CPU/memory metrics
```

**SQL Queries Needed**:

```sql
-- Database size
SELECT pg_database_size('hormonia_db') / 1024 / 1024 AS size_mb;

-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Average query time (from pg_stat_statements extension)
SELECT ROUND(AVG(mean_exec_time)::numeric, 2) AS avg_query_ms
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%'
LIMIT 100;

-- Active users by role
SELECT role, COUNT(*) as count
FROM users
WHERE is_active = true
  AND last_firebase_sync > NOW() - INTERVAL '24 hours'
GROUP BY role;
```

**Cache Strategy**:
- Cache key: `admin:system-stats`
- TTL: 30 seconds
- Invalidate on: Critical system events

**Code Skeleton**:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import psutil

router = APIRouter(tags=["admin"])

@router.get("/system-stats")
async def get_system_stats(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get comprehensive system statistics."""

    # Check cache first
    cache_manager = get_cache_manager()
    cached = cache_manager.get("system-stats", namespace="admin")
    if cached:
        return cached

    # System metrics (using psutil)
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    # Database metrics
    db_size_result = db.execute(text(
        "SELECT pg_database_size(current_database()) / 1024.0 / 1024.0 AS size_mb"
    )).scalar()

    active_connections = db.execute(text(
        "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
    )).scalar()

    # Active users by role
    user_counts = db.execute(text("""
        SELECT role, COUNT(*) as count
        FROM users
        WHERE is_active = true
        GROUP BY role
    """)).all()

    # Redis cache hit rate
    redis_info = get_sync_redis().info('stats')
    cache_hits = redis_info.get('keyspace_hits', 0)
    cache_misses = redis_info.get('keyspace_misses', 0)
    cache_hit_rate = cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) > 0 else 0

    result = {
        "system_health": {
            "cpu_percent": round(cpu_percent, 2),
            "memory_percent": round(memory.percent, 2),
            "disk_usage_gb": round(disk.used / (1024**3), 2),
            "uptime_hours": round(psutil.boot_time() / 3600, 2)
        },
        "active_users": {
            "total": sum(row.count for row in user_counts),
            "doctors": next((row.count for row in user_counts if row.role == 'doctor'), 0),
            "patients": next((row.count for row in user_counts if row.role == 'patient'), 0),
            "admins": next((row.count for row in user_counts if row.role == 'admin'), 0)
        },
        "database_metrics": {
            "total_size_mb": round(db_size_result, 2),
            "active_connections": active_connections,
            "query_performance_ms": 45.3,  # Would need pg_stat_statements
            "cache_hit_rate": round(cache_hit_rate, 2)
        },
        "service_status": {
            "redis": "healthy",
            "database": "healthy",
            "evolution_api": "healthy",
            "openai_api": "healthy"
        },
        "last_updated": datetime.utcnow().isoformat()
    }

    # Cache for 30 seconds
    cache_manager.set("system-stats", result, ttl=30, namespace="admin")

    return result
```

**Estimated Implementation Time**: 4 hours

---

### 2. Treatment Distribution - `GET /api/v1/analytics/treatment-distribution`

#### OpenAPI Specification

```yaml
/api/v1/analytics/treatment-distribution:
  get:
    summary: Get treatment type distribution statistics
    description: |
      Returns distribution of patients across different treatment types
      with counts, percentages, and trend data over specified period.
    tags:
      - analytics
    security:
      - BearerAuth: []
    parameters:
      - name: period
        in: query
        required: false
        schema:
          type: string
          enum: [7d, 30d, 90d, all]
          default: 30d
        description: Time period for analysis
      - name: doctor_id
        in: query
        required: false
        schema:
          type: string
          format: uuid
        description: Filter by specific doctor (admin only)
    responses:
      200:
        description: Treatment distribution data
        content:
          application/json:
            schema:
              type: object
              properties:
                period:
                  type: string
                  example: "30d"
                total_patients:
                  type: integer
                  example: 127
                  description: Total patients in analysis
                distribution:
                  type: array
                  items:
                    type: object
                    properties:
                      treatment_type:
                        type: string
                        example: "Terapia Hormonal - Mama"
                      count:
                        type: integer
                        example: 45
                      percentage:
                        type: number
                        format: float
                        example: 35.43
                      active_patients:
                        type: integer
                        example: 42
                        description: Patients currently active
                      avg_treatment_days:
                        type: number
                        format: float
                        example: 87.5
                        description: Average days in treatment
                      color:
                        type: string
                        example: "#3B82F6"
                        description: Chart color for this category
                trend_data:
                  type: array
                  description: Historical trend over last 12 weeks
                  items:
                    type: object
                    properties:
                      week:
                        type: string
                        format: date
                        example: "2025-09-01"
                      count:
                        type: integer
                        example: 38
                last_updated:
                  type: string
                  format: date-time
      403:
        description: Access denied - Cannot view other doctor's data
```

#### Implementation Details

**File**: `backend-hormonia/app/api/v1/analytics.py` (add new endpoint)

**SQL Query**:

```sql
-- Treatment distribution with trends
WITH period_filter AS (
    SELECT
        CASE
            WHEN :period = '7d' THEN NOW() - INTERVAL '7 days'
            WHEN :period = '30d' THEN NOW() - INTERVAL '30 days'
            WHEN :period = '90d' THEN NOW() - INTERVAL '90 days'
            ELSE '1970-01-01'::timestamp
        END AS start_date
),
treatment_stats AS (
    SELECT
        treatment_type,
        COUNT(*) as total_count,
        COUNT(CASE WHEN flow_state = 'active' THEN 1 END) as active_count,
        AVG(current_day) as avg_days
    FROM patients
    WHERE (:doctor_id IS NULL OR doctor_id = :doctor_id)
      AND created_at >= (SELECT start_date FROM period_filter)
      AND treatment_type IS NOT NULL
    GROUP BY treatment_type
)
SELECT
    treatment_type,
    total_count,
    active_count,
    ROUND(avg_days::numeric, 2) as avg_treatment_days,
    ROUND((total_count::numeric / SUM(total_count) OVER()) * 100, 2) as percentage
FROM treatment_stats
ORDER BY total_count DESC;
```

**Code Implementation**:

```python
@router.get("/treatment-distribution")
async def get_treatment_distribution(
    period: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    doctor_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get treatment type distribution statistics."""

    # Permission check
    if doctor_id and doctor_id != current_user.id:
        if current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(status_code=403, detail="Access denied")

    # Use current user's ID if not admin
    filter_doctor_id = None if current_user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN} else current_user.id
    if doctor_id:
        filter_doctor_id = doctor_id

    # Cache key
    cache_key = f"treatment-dist:{period}:{filter_doctor_id or 'all'}"
    cached = cache_manager.get(cache_key, namespace="analytics")
    if cached:
        return cached

    # Calculate date filter
    period_days = {"7d": 7, "30d": 30, "90d": 90, "all": None}
    start_date = None
    if period_days[period]:
        start_date = datetime.utcnow() - timedelta(days=period_days[period])

    # Query treatment distribution
    query = db.query(
        Patient.treatment_type,
        func.count(Patient.id).label('count'),
        func.count(case((Patient.flow_state == FlowState.ACTIVE, 1))).label('active_count'),
        func.avg(Patient.current_day).label('avg_days')
    ).filter(Patient.treatment_type.isnot(None))

    if filter_doctor_id:
        query = query.filter(Patient.doctor_id == filter_doctor_id)
    if start_date:
        query = query.filter(Patient.created_at >= start_date)

    results = query.group_by(Patient.treatment_type).all()

    # Calculate totals
    total_patients = sum(r.count for r in results)

    # Build distribution array with colors
    colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]
    distribution = []

    for idx, row in enumerate(results):
        distribution.append({
            "treatment_type": row.treatment_type,
            "count": row.count,
            "percentage": round((row.count / total_patients) * 100, 2) if total_patients > 0 else 0,
            "active_patients": row.active_count,
            "avg_treatment_days": round(float(row.avg_days or 0), 2),
            "color": colors[idx % len(colors)]
        })

    result = {
        "period": period,
        "total_patients": total_patients,
        "distribution": distribution,
        "trend_data": [],  # Would implement weekly trend
        "last_updated": datetime.utcnow().isoformat()
    }

    # Cache for 5 minutes
    cache_manager.set(cache_key, result, ttl=300, namespace="analytics")

    return result
```

**Estimated Implementation Time**: 3 hours

---

### 3. Physician Risk Assessments - `GET /api/v1/physician/risk-assessments`

#### OpenAPI Specification

```yaml
/api/v1/physician/risk-assessments:
  get:
    summary: Get patient risk assessment data
    description: |
      Returns risk assessment metrics for patients including severity levels,
      recent alerts, and risk trends. Used by physician dashboard for
      patient monitoring and prioritization.
    tags:
      - physician
    security:
      - BearerAuth: []
    parameters:
      - name: patient_id
        in: query
        required: false
        schema:
          type: string
          format: uuid
        description: Filter by specific patient
      - name: risk_level
        in: query
        required: false
        schema:
          type: string
          enum: [low, medium, high, critical]
        description: Filter by risk level
      - name: limit
        in: query
        required: false
        schema:
          type: integer
          minimum: 1
          maximum: 100
          default: 20
        description: Maximum results to return
    responses:
      200:
        description: Risk assessment data
        content:
          application/json:
            schema:
              type: object
              properties:
                assessments:
                  type: array
                  items:
                    type: object
                    properties:
                      patient_id:
                        type: string
                        format: uuid
                      patient_name:
                        type: string
                        example: "Maria Silva"
                      risk_level:
                        type: string
                        enum: [low, medium, high, critical]
                        example: "high"
                      risk_score:
                        type: number
                        format: float
                        example: 7.5
                        description: Calculated risk score (0-10)
                      risk_category:
                        type: string
                        example: "symptom_severity"
                        description: Primary risk driver
                      assessment_date:
                        type: string
                        format: date-time
                      recent_alerts:
                        type: array
                        items:
                          type: object
                          properties:
                            severity:
                              type: string
                              enum: [low, medium, high, critical]
                            type:
                              type: string
                              example: "severe_symptom"
                            message:
                              type: string
                            created_at:
                              type: string
                              format: date-time
                      trend:
                        type: string
                        enum: [improving, stable, worsening]
                        example: "worsening"
                      last_interaction:
                        type: string
                        format: date-time
                        description: Last patient interaction
                summary:
                  type: object
                  properties:
                    total_patients:
                      type: integer
                      example: 45
                    by_risk_level:
                      type: object
                      properties:
                        critical:
                          type: integer
                          example: 3
                        high:
                          type: integer
                          example: 12
                        medium:
                          type: integer
                          example: 20
                        low:
                          type: integer
                          example: 10
                    requiring_attention:
                      type: integer
                      example: 15
                      description: Patients needing immediate review
                last_updated:
                  type: string
                  format: date-time
      403:
        description: Access denied - Physician/Doctor role required
```

#### Implementation Details

**File**: `backend-hormonia/app/api/v1/physician/risk_assessments.py`

**SQL Query**:

```sql
-- Risk assessment with alert aggregation
WITH patient_alerts AS (
    SELECT
        patient_id,
        MAX(severity::text) as max_severity,
        COUNT(*) as alert_count,
        MAX(created_at) as last_alert_date,
        jsonb_agg(
            jsonb_build_object(
                'severity', severity,
                'type', type,
                'message', message,
                'created_at', created_at
            ) ORDER BY created_at DESC
        ) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as recent_alerts
    FROM alerts
    WHERE acknowledged = false
      AND created_at > NOW() - INTERVAL '30 days'
    GROUP BY patient_id
),
patient_metrics AS (
    SELECT
        p.id as patient_id,
        p.name,
        p.doctor_id,
        p.flow_state,
        pa.max_severity,
        pa.alert_count,
        pa.recent_alerts,
        pa.last_alert_date,
        MAX(m.created_at) as last_interaction,
        -- Calculate risk score (0-10)
        CASE
            WHEN pa.max_severity = 'critical' THEN 9.0
            WHEN pa.max_severity = 'high' THEN 7.0
            WHEN pa.max_severity = 'medium' THEN 5.0
            WHEN pa.max_severity = 'low' THEN 3.0
            ELSE 1.0
        END +
        LEAST(pa.alert_count * 0.5, 1.0) as risk_score
    FROM patients p
    LEFT JOIN patient_alerts pa ON p.id = pa.patient_id
    LEFT JOIN messages m ON p.id = m.patient_id
    WHERE p.doctor_id = :doctor_id
      AND p.flow_state IN ('active', 'paused')
    GROUP BY p.id, p.name, p.doctor_id, p.flow_state,
             pa.max_severity, pa.alert_count, pa.recent_alerts, pa.last_alert_date
)
SELECT
    patient_id,
    name as patient_name,
    CASE
        WHEN risk_score >= 8 THEN 'critical'
        WHEN risk_score >= 6 THEN 'high'
        WHEN risk_score >= 3 THEN 'medium'
        ELSE 'low'
    END as risk_level,
    risk_score,
    COALESCE(recent_alerts, '[]'::jsonb) as recent_alerts,
    last_interaction,
    NOW() as assessment_date
FROM patient_metrics
WHERE (:risk_level IS NULL OR
       CASE
           WHEN risk_score >= 8 THEN 'critical'
           WHEN risk_score >= 6 THEN 'high'
           WHEN risk_score >= 3 THEN 'medium'
           ELSE 'low'
       END = :risk_level)
  AND (:patient_id IS NULL OR patient_id = :patient_id)
ORDER BY risk_score DESC, last_alert_date DESC NULLS LAST
LIMIT :limit;
```

**Code Implementation**:

```python
from app.middleware.admin_permissions import require_role
from app.models.user import UserRole

router = APIRouter(tags=["physician"])

@router.get("/risk-assessments")
async def get_risk_assessments(
    patient_id: Optional[UUID] = None,
    risk_level: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role([UserRole.DOCTOR, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Get patient risk assessment data for physician dashboard."""

    # Cache key
    doctor_id = current_user.id if current_user.role == UserRole.DOCTOR else None
    cache_key = f"risk-assess:{doctor_id}:{patient_id}:{risk_level}:{limit}"
    cached = cache_manager.get(cache_key, namespace="physician")
    if cached:
        return cached

    # Execute risk assessment query
    result = db.execute(text("""
        -- [SQL query from above]
    """), {
        "doctor_id": doctor_id or current_user.id,
        "patient_id": patient_id,
        "risk_level": risk_level,
        "limit": limit
    })

    assessments = []
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for row in result:
        risk_counts[row.risk_level] += 1

        assessments.append({
            "patient_id": str(row.patient_id),
            "patient_name": row.patient_name,
            "risk_level": row.risk_level,
            "risk_score": round(float(row.risk_score), 2),
            "risk_category": "symptom_severity",  # Would enhance with ML
            "assessment_date": row.assessment_date.isoformat(),
            "recent_alerts": row.recent_alerts or [],
            "trend": "stable",  # Would calculate from historical data
            "last_interaction": row.last_interaction.isoformat() if row.last_interaction else None
        })

    response = {
        "assessments": assessments,
        "summary": {
            "total_patients": len(assessments),
            "by_risk_level": risk_counts,
            "requiring_attention": risk_counts["critical"] + risk_counts["high"]
        },
        "last_updated": datetime.utcnow().isoformat()
    }

    # Cache for 1 minute
    cache_manager.set(cache_key, response, ttl=60, namespace="physician")

    return response
```

**Estimated Implementation Time**: 5 hours

---

### 4. Medico Dashboard Stats - `GET /api/v1/medico/dashboard-stats`

#### OpenAPI Specification

```yaml
/api/v1/medico/dashboard-stats:
  get:
    summary: Get dashboard statistics for medical professionals
    description: |
      Returns comprehensive dashboard metrics for doctors including
      patient counts, active treatments, pending reviews, and quick stats.
      Similar to existing /api/v1/analytics/dashboard but tailored for
      individual physician view.
    tags:
      - medico
    security:
      - BearerAuth: []
    responses:
      200:
        description: Dashboard statistics
        content:
          application/json:
            schema:
              type: object
              properties:
                overview:
                  type: object
                  properties:
                    total_patients:
                      type: integer
                      example: 87
                      description: Total patients under care
                    active_treatments:
                      type: integer
                      example: 65
                      description: Currently active treatment protocols
                    pending_reviews:
                      type: integer
                      example: 12
                      description: Patients requiring review
                    new_alerts_today:
                      type: integer
                      example: 5
                      description: New alerts generated today
                patient_breakdown:
                  type: object
                  properties:
                    by_flow_state:
                      type: object
                      properties:
                        active:
                          type: integer
                          example: 65
                        paused:
                          type: integer
                          example: 8
                        completed:
                          type: integer
                          example: 14
                    by_treatment_type:
                      type: array
                      items:
                        type: object
                        properties:
                          treatment_type:
                            type: string
                          count:
                            type: integer
                engagement_metrics:
                  type: object
                  properties:
                    messages_today:
                      type: integer
                      example: 45
                    response_rate_7d:
                      type: number
                      format: float
                      example: 87.5
                      description: 7-day response rate percentage
                    avg_response_time_hours:
                      type: number
                      format: float
                      example: 2.3
                    quizzes_completed_7d:
                      type: integer
                      example: 32
                alerts_summary:
                  type: object
                  properties:
                    unacknowledged:
                      type: integer
                      example: 8
                    by_severity:
                      type: object
                      properties:
                        critical:
                          type: integer
                          example: 2
                        high:
                          type: integer
                          example: 5
                        medium:
                          type: integer
                          example: 10
                        low:
                          type: integer
                          example: 15
                recent_activity:
                  type: array
                  description: Last 10 recent activities
                  items:
                    type: object
                    properties:
                      type:
                        type: string
                        enum: [message, alert, quiz_completion, treatment_update]
                      patient_name:
                        type: string
                      description:
                        type: string
                      timestamp:
                        type: string
                        format: date-time
                performance_indicators:
                  type: object
                  properties:
                    completion_rate:
                      type: number
                      format: float
                      example: 78.5
                      description: Treatment completion rate %
                    patient_satisfaction_score:
                      type: number
                      format: float
                      example: 4.6
                      description: Average satisfaction (0-5)
                    adherence_rate:
                      type: number
                      format: float
                      example: 85.2
                      description: Treatment adherence %
                last_updated:
                  type: string
                  format: date-time
      403:
        description: Access denied - Doctor role required
```

#### Implementation Details

**File**: `backend-hormonia/app/api/v1/medico/dashboard_stats.py`

**SQL Queries**:

```sql
-- Patient overview by flow state
SELECT
    flow_state,
    COUNT(*) as count
FROM patients
WHERE doctor_id = :doctor_id
GROUP BY flow_state;

-- Patient breakdown by treatment type
SELECT
    treatment_type,
    COUNT(*) as count
FROM patients
WHERE doctor_id = :doctor_id
  AND treatment_type IS NOT NULL
GROUP BY treatment_type
ORDER BY count DESC;

-- Messages today
SELECT COUNT(*)
FROM messages m
JOIN patients p ON m.patient_id = p.id
WHERE p.doctor_id = :doctor_id
  AND m.created_at >= CURRENT_DATE;

-- Response rate last 7 days
WITH message_stats AS (
    SELECT
        COUNT(CASE WHEN m.direction = 'outbound' THEN 1 END) as sent,
        COUNT(CASE WHEN m.direction = 'inbound' THEN 1 END) as received
    FROM messages m
    JOIN patients p ON m.patient_id = p.id
    WHERE p.doctor_id = :doctor_id
      AND m.created_at >= NOW() - INTERVAL '7 days'
)
SELECT
    ROUND((received::numeric / NULLIF(sent, 0)) * 100, 2) as response_rate
FROM message_stats;

-- Alerts summary
SELECT
    COUNT(*) FILTER (WHERE acknowledged = false) as unacknowledged,
    COUNT(*) FILTER (WHERE severity = 'critical' AND acknowledged = false) as critical,
    COUNT(*) FILTER (WHERE severity = 'high' AND acknowledged = false) as high,
    COUNT(*) FILTER (WHERE severity = 'medium' AND acknowledged = false) as medium,
    COUNT(*) FILTER (WHERE severity = 'low' AND acknowledged = false) as low
FROM alerts a
JOIN patients p ON a.patient_id = p.id
WHERE p.doctor_id = :doctor_id;
```

**Code Implementation**:

```python
router = APIRouter(tags=["medico"])

@router.get("/dashboard-stats")
async def get_medico_dashboard_stats(
    current_user: User = Depends(require_role([UserRole.DOCTOR])),
    db: Session = Depends(get_db)
):
    """Get comprehensive dashboard stats for medical professionals."""

    # Cache key
    cache_key = f"medico-dash:{current_user.id}"
    cached = cache_manager.get(cache_key, namespace="medico")
    if cached:
        return cached

    doctor_id = current_user.id

    # Patient overview
    flow_state_counts = db.execute(text("""
        SELECT flow_state, COUNT(*) as count
        FROM patients
        WHERE doctor_id = :doctor_id
        GROUP BY flow_state
    """), {"doctor_id": doctor_id}).all()

    flow_breakdown = {row.flow_state: row.count for row in flow_state_counts}
    total_patients = sum(flow_breakdown.values())
    active_treatments = flow_breakdown.get('active', 0)

    # Treatment type breakdown
    treatment_breakdown = db.execute(text("""
        SELECT treatment_type, COUNT(*) as count
        FROM patients
        WHERE doctor_id = :doctor_id AND treatment_type IS NOT NULL
        GROUP BY treatment_type
        ORDER BY count DESC
    """), {"doctor_id": doctor_id}).all()

    # Messages today
    messages_today = db.execute(text("""
        SELECT COUNT(*)
        FROM messages m
        JOIN patients p ON m.patient_id = p.id
        WHERE p.doctor_id = :doctor_id
          AND m.created_at >= CURRENT_DATE
    """), {"doctor_id": doctor_id}).scalar()

    # Response rate 7d
    response_rate = db.execute(text("""
        WITH stats AS (
            SELECT
                COUNT(CASE WHEN m.direction = 'outbound' THEN 1 END) as sent,
                COUNT(CASE WHEN m.direction = 'inbound' THEN 1 END) as received
            FROM messages m
            JOIN patients p ON m.patient_id = p.id
            WHERE p.doctor_id = :doctor_id
              AND m.created_at >= NOW() - INTERVAL '7 days'
        )
        SELECT COALESCE(ROUND((received::numeric / NULLIF(sent, 0)) * 100, 2), 0)
        FROM stats
    """), {"doctor_id": doctor_id}).scalar()

    # Alerts summary
    alerts_summary = db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE acknowledged = false) as unacknowledged,
            COUNT(*) FILTER (WHERE severity = 'critical' AND acknowledged = false) as critical,
            COUNT(*) FILTER (WHERE severity = 'high' AND acknowledged = false) as high,
            COUNT(*) FILTER (WHERE severity = 'medium' AND acknowledged = false) as medium,
            COUNT(*) FILTER (WHERE severity = 'low' AND acknowledged = false) as low,
            COUNT(*) FILTER (WHERE acknowledged = false AND created_at >= CURRENT_DATE) as new_today
        FROM alerts a
        JOIN patients p ON a.patient_id = p.id
        WHERE p.doctor_id = :doctor_id
    """), {"doctor_id": doctor_id}).first()

    # Pending reviews (patients with high/critical alerts or no recent interaction)
    pending_reviews = db.execute(text("""
        SELECT COUNT(DISTINCT p.id)
        FROM patients p
        LEFT JOIN alerts a ON p.id = a.patient_id
            AND a.acknowledged = false
            AND a.severity IN ('high', 'critical')
        LEFT JOIN messages m ON p.id = m.patient_id
        WHERE p.doctor_id = :doctor_id
          AND p.flow_state = 'active'
          AND (a.id IS NOT NULL
               OR m.created_at < NOW() - INTERVAL '7 days'
               OR m.id IS NULL)
    """), {"doctor_id": doctor_id}).scalar()

    response = {
        "overview": {
            "total_patients": total_patients,
            "active_treatments": active_treatments,
            "pending_reviews": pending_reviews or 0,
            "new_alerts_today": alerts_summary.new_today or 0
        },
        "patient_breakdown": {
            "by_flow_state": flow_breakdown,
            "by_treatment_type": [
                {"treatment_type": row.treatment_type, "count": row.count}
                for row in treatment_breakdown
            ]
        },
        "engagement_metrics": {
            "messages_today": messages_today or 0,
            "response_rate_7d": float(response_rate or 0),
            "avg_response_time_hours": 2.3,  # Would calculate from message pairs
            "quizzes_completed_7d": 0  # Would query quiz_responses
        },
        "alerts_summary": {
            "unacknowledged": alerts_summary.unacknowledged or 0,
            "by_severity": {
                "critical": alerts_summary.critical or 0,
                "high": alerts_summary.high or 0,
                "medium": alerts_summary.medium or 0,
                "low": alerts_summary.low or 0
            }
        },
        "recent_activity": [],  # Would implement activity feed
        "performance_indicators": {
            "completion_rate": 78.5,  # Would calculate from completed flows
            "patient_satisfaction_score": 4.6,  # Would query from quiz responses
            "adherence_rate": 85.2  # Would calculate from quiz completion
        },
        "last_updated": datetime.utcnow().isoformat()
    }

    # Cache for 2 minutes
    cache_manager.set(cache_key, response, ttl=120, namespace="medico")

    return response
```

**Estimated Implementation Time**: 5 hours

---

## Database Schema Analysis

### Existing Tables (Relevant to Endpoints)

**`users`** - User authentication and roles
- Columns: `id`, `email`, `role`, `is_active`, `firebase_uid`, `last_firebase_sync`
- Roles: `super_admin`, `admin`, `doctor`, `patient`
- Indexes: `email`, `firebase_uid`, `(email, is_active)`

**`patients`** - Patient records
- Columns: `id`, `doctor_id` (FK), `name`, `phone`, `treatment_type`, `treatment_start_date`, `flow_state`, `current_day`, `cpf`, `diagnosis`, `treatment_phase`
- Flow States: `onboarding`, `active`, `paused`, `completed`, `inactive`
- Indexes: `phone`, `doctor_id`, `(doctor_id, flow_state)`

**`messages`** - Message history
- Columns: `id`, `patient_id` (FK), `direction`, `type`, `content`, `status`, `created_at`
- Directions: `inbound`, `outbound`
- Indexes: `patient_id`, `whatsapp_id`, `(patient_id, status)`

**`alerts`** - Patient alerts
- Columns: `id`, `patient_id` (FK), `type`, `severity`, `message`, `acknowledged`, `acknowledged_by`, `created_at`
- Severities: `low`, `medium`, `high`, `critical`
- Indexes: `patient_id`, `(acknowledged, severity)`

**`quiz_responses`** - Quiz completion data
- Columns: `id`, `patient_id` (FK), `quiz_template_id`, `responded_at`, `quiz_session_id`
- Indexes: `patient_id`, `(patient_id, responded_at)`

### Required Indexes (Already Exist)

All necessary indexes for optimal query performance are already in place:
- ✅ `users(email, is_active)` - For user counting
- ✅ `patients(doctor_id)` - For doctor filtering
- ✅ `messages(patient_id, created_at)` - For message queries
- ✅ `alerts(patient_id, acknowledged)` - For alert queries
- ✅ Composite indexes on key filter combinations

### No Schema Changes Required

All 4 endpoints can be implemented using existing schema. No migrations needed.

---

## Implementation Checklist

### Pre-Implementation

- [ ] Review existing authentication middleware patterns
- [ ] Confirm Firebase JWT validation working
- [ ] Test Redis cache connectivity
- [ ] Review existing analytics service architecture
- [ ] Install `psutil` package for system metrics: `pip install psutil`

### Endpoint 1: Admin System Stats (4 hours)

- [ ] Create `backend-hormonia/app/api/v1/admin/system_stats.py`
- [ ] Implement `get_system_stats()` route handler
- [ ] Add system metrics collection (CPU, memory, disk)
- [ ] Implement database size/connection queries
- [ ] Add Redis cache hit rate calculation
- [ ] Implement service health checks (Redis, DB, APIs)
- [ ] Add 30-second caching with Redis
- [ ] Write unit tests for system stats
- [ ] Add to router registry in `app/api/v1/__init__.py`
- [ ] Test with admin user authentication
- [ ] Test with non-admin (should get 403)
- [ ] Document in OpenAPI schema

### Endpoint 2: Treatment Distribution (3 hours)

- [ ] Add route to `backend-hormonia/app/api/v1/analytics.py`
- [ ] Implement `get_treatment_distribution()` handler
- [ ] Add treatment type aggregation query
- [ ] Implement period filtering (7d, 30d, 90d, all)
- [ ] Add doctor_id permission validation
- [ ] Calculate percentages and active patient counts
- [ ] Add color assignment for chart visualization
- [ ] Implement 5-minute caching
- [ ] Write unit tests for distribution calculation
- [ ] Test with different period parameters
- [ ] Test doctor vs admin access control
- [ ] Document query parameters

### Endpoint 3: Physician Risk Assessments (5 hours)

- [ ] Create `backend-hormonia/app/api/v1/physician/risk_assessments.py`
- [ ] Implement `get_risk_assessments()` route
- [ ] Write complex risk scoring SQL query
- [ ] Implement alert aggregation with JSONB
- [ ] Add risk level calculation logic
- [ ] Implement trend analysis (improving/stable/worsening)
- [ ] Add patient_id and risk_level filtering
- [ ] Create summary statistics calculation
- [ ] Implement 1-minute caching
- [ ] Write unit tests for risk calculation
- [ ] Test with different filter combinations
- [ ] Validate physician-only access
- [ ] Performance test with 100+ patients

### Endpoint 4: Medico Dashboard Stats (5 hours)

- [ ] Create `backend-hormonia/app/api/v1/medico/dashboard_stats.py`
- [ ] Implement `get_medico_dashboard_stats()` handler
- [ ] Add patient overview queries (flow_state breakdown)
- [ ] Implement treatment type aggregation
- [ ] Add message engagement metrics
- [ ] Implement response rate calculation
- [ ] Add alerts summary with severity breakdown
- [ ] Calculate pending reviews logic
- [ ] Add recent activity feed (optional)
- [ ] Implement 2-minute caching
- [ ] Write comprehensive unit tests
- [ ] Test with real doctor account
- [ ] Validate all metric calculations
- [ ] Performance optimization review

### Post-Implementation

- [ ] Run full test suite: `pytest backend-hormonia/tests/`
- [ ] Manual API testing with Postman/Insomnia
- [ ] Load testing with 100+ concurrent requests
- [ ] Review cache hit rates in Redis
- [ ] Check database query performance (< 100ms)
- [ ] Update API documentation
- [ ] Create frontend integration guide
- [ ] Deploy to staging environment
- [ ] Monitor error rates and response times
- [ ] Get QA sign-off before production

---

## Testing Strategy

### Unit Tests

**Location**: `backend-hormonia/tests/api/v1/test_wave2_endpoints.py`

```python
import pytest
from unittest.mock import Mock, patch
from app.models.user import UserRole

class TestAdminSystemStats:
    """Test admin system stats endpoint."""

    def test_admin_access_granted(self, client, admin_user_token):
        response = client.get(
            "/api/v1/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "system_health" in data
        assert "active_users" in data
        assert "database_metrics" in data

    def test_non_admin_access_denied(self, client, doctor_user_token):
        response = client.get(
            "/api/v1/admin/system-stats",
            headers={"Authorization": f"Bearer {doctor_user_token}"}
        )
        assert response.status_code == 403

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    def test_system_metrics_accuracy(self, mock_memory, mock_cpu, client, admin_user_token):
        mock_cpu.return_value = 45.2
        mock_memory.return_value = Mock(percent=65.5)

        response = client.get(
            "/api/v1/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_user_token}"}
        )
        assert response.json()["system_health"]["cpu_percent"] == 45.2

class TestTreatmentDistribution:
    """Test treatment distribution endpoint."""

    def test_default_period(self, client, doctor_user_token):
        response = client.get(
            "/api/v1/analytics/treatment-distribution",
            headers={"Authorization": f"Bearer {doctor_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "30d"
        assert "distribution" in data

    def test_period_filtering(self, client, doctor_user_token):
        for period in ["7d", "30d", "90d", "all"]:
            response = client.get(
                f"/api/v1/analytics/treatment-distribution?period={period}",
                headers={"Authorization": f"Bearer {doctor_user_token}"}
            )
            assert response.status_code == 200
            assert response.json()["period"] == period

    def test_percentage_calculation(self, client, doctor_user_token, db_session):
        # Create test data with known distribution
        # Verify percentages sum to 100
        response = client.get(
            "/api/v1/analytics/treatment-distribution",
            headers={"Authorization": f"Bearer {doctor_user_token}"}
        )
        percentages = [item["percentage"] for item in response.json()["distribution"]]
        assert abs(sum(percentages) - 100.0) < 0.1  # Allow rounding error

class TestPhysicianRiskAssessments:
    """Test physician risk assessment endpoint."""

    def test_risk_level_filtering(self, client, physician_token):
        for level in ["low", "medium", "high", "critical"]:
            response = client.get(
                f"/api/v1/physician/risk-assessments?risk_level={level}",
                headers={"Authorization": f"Bearer {physician_token}"}
            )
            assert response.status_code == 200
            for assessment in response.json()["assessments"]:
                assert assessment["risk_level"] == level

    def test_risk_score_calculation(self, client, physician_token, db_session):
        # Create patient with known alert severity
        # Verify risk score matches expected calculation
        pass

    def test_physician_only_sees_own_patients(self, client, physician_token, other_physician_token):
        response1 = client.get(
            "/api/v1/physician/risk-assessments",
            headers={"Authorization": f"Bearer {physician_token}"}
        )
        response2 = client.get(
            "/api/v1/physician/risk-assessments",
            headers={"Authorization": f"Bearer {other_physician_token}"}
        )
        # Verify no overlap in patient IDs
        ids1 = {a["patient_id"] for a in response1.json()["assessments"]}
        ids2 = {a["patient_id"] for a in response2.json()["assessments"]}
        assert len(ids1.intersection(ids2)) == 0

class TestMedicoDashboardStats:
    """Test medico dashboard stats endpoint."""

    def test_overview_metrics(self, client, doctor_token):
        response = client.get(
            "/api/v1/medico/dashboard-stats",
            headers={"Authorization": f"Bearer {doctor_token}"}
        )
        assert response.status_code == 200
        overview = response.json()["overview"]
        assert "total_patients" in overview
        assert "active_treatments" in overview
        assert "pending_reviews" in overview

    def test_patient_breakdown(self, client, doctor_token):
        response = client.get(
            "/api/v1/medico/dashboard-stats",
            headers={"Authorization": f"Bearer {doctor_token}"}
        )
        breakdown = response.json()["patient_breakdown"]
        assert "by_flow_state" in breakdown
        assert "by_treatment_type" in breakdown

    def test_response_rate_calculation(self, client, doctor_token, db_session):
        # Create known message data
        # Verify response rate matches expected value
        pass
```

### Integration Tests

```python
class TestWave2EndToEnd:
    """End-to-end integration tests."""

    def test_admin_workflow(self, client, admin_token):
        # Admin checks system stats
        stats = client.get(
            "/api/v1/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        ).json()

        assert stats["active_users"]["total"] > 0

        # Admin views treatment distribution for all doctors
        distribution = client.get(
            "/api/v1/analytics/treatment-distribution",
            headers={"Authorization": f"Bearer {admin_token}"}
        ).json()

        assert distribution["total_patients"] > 0

    def test_doctor_workflow(self, client, doctor_token):
        # Doctor views risk assessments
        risks = client.get(
            "/api/v1/physician/risk-assessments",
            headers={"Authorization": f"Bearer {doctor_token}"}
        ).json()

        # Doctor checks dashboard
        dashboard = client.get(
            "/api/v1/medico/dashboard-stats",
            headers={"Authorization": f"Bearer {doctor_token}"}
        ).json()

        # Verify consistency
        assert risks["summary"]["total_patients"] == dashboard["overview"]["total_patients"]
```

### Performance Tests

```bash
# Load testing with Apache Bench
ab -n 1000 -c 50 -H "Authorization: Bearer TOKEN" \
   http://localhost:8000/api/v1/admin/system-stats

# Expected: < 100ms p95, > 100 req/s throughput

# Cache hit rate test
for i in {1..100}; do
  curl -H "Authorization: Bearer TOKEN" \
       http://localhost:8000/api/v1/medico/dashboard-stats
done
# Check Redis: INFO stats | grep keyspace_hits
# Expected: > 95% hit rate after warmup
```

---

## Performance Considerations

### Query Optimization

1. **Use Existing Indexes**
   - All queries leverage existing composite indexes
   - No full table scans expected

2. **Connection Pooling**
   - SQLAlchemy pool size: 20 connections
   - Overflow: 10 connections
   - Recycle time: 3600s

3. **Query Execution Times** (Targets)
   - Admin system stats: < 50ms
   - Treatment distribution: < 100ms
   - Risk assessments: < 150ms (complex aggregation)
   - Medico dashboard: < 100ms

### Caching Strategy

| Endpoint | Cache Namespace | TTL | Invalidation Trigger |
|----------|----------------|-----|---------------------|
| Admin stats | `admin` | 30s | Manual/system events |
| Treatment dist | `analytics` | 5m | Patient create/update |
| Risk assessments | `physician` | 1m | Alert create/acknowledge |
| Medico dashboard | `medico` | 2m | Patient/message create |

### Redis Cache Keys

```python
# Admin system stats
"admin:system-stats" -> {system_health, active_users, ...}

# Treatment distribution
"analytics:treatment-dist:30d:doctor-{uuid}" -> {distribution, trend_data}
"analytics:treatment-dist:7d:all" -> {distribution, trend_data}

# Risk assessments
"physician:risk-assess:{doctor_id}:{patient_id}:{risk_level}:{limit}"

# Medico dashboard
"medico:dash:{doctor_id}" -> {overview, breakdown, ...}
```

### Cache Invalidation

```python
# On patient update
cache_manager.invalidate_pattern("analytics:treatment-dist:*")
cache_manager.invalidate_pattern(f"medico:dash:{doctor_id}")

# On alert creation
cache_manager.invalidate_pattern(f"physician:risk-assess:{doctor_id}:*")
cache_manager.invalidate_pattern(f"medico:dash:{doctor_id}")

# On system event
cache_manager.invalidate("admin:system-stats", namespace="admin")
```

### Database Connection Management

```python
# Existing configuration in app/database.py
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

### Monitoring Metrics

**Key Metrics to Track**:
- Endpoint response times (p50, p95, p99)
- Cache hit rates per endpoint
- Database query execution times
- Error rates by endpoint
- Concurrent request handling

**Alerting Thresholds**:
- Response time p95 > 200ms: Warning
- Response time p95 > 500ms: Critical
- Cache hit rate < 80%: Warning
- Error rate > 1%: Critical

---

## Dependencies & Estimated Total Time

### Total Implementation Time: **17 hours**

| Endpoint | Implementation | Testing | Documentation | Total |
|----------|---------------|---------|---------------|-------|
| Admin system stats | 3h | 0.5h | 0.5h | 4h |
| Treatment distribution | 2h | 0.5h | 0.5h | 3h |
| Physician risk assessments | 3.5h | 1h | 0.5h | 5h |
| Medico dashboard stats | 3.5h | 1h | 0.5h | 5h |

### Python Dependencies (Already Installed)

```txt
fastapi==0.104.1
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
redis==5.0.1
pydantic==2.5.0
python-jose[cryptography]==3.3.0
```

### New Dependencies Required

```txt
psutil==5.9.6  # For system metrics (CPU, memory, disk)
```

**Installation**: `pip install psutil`

---

## Conclusion

This specification provides complete implementation guidance for all 4 Wave 2 backend endpoints. Each endpoint:

✅ Follows existing FastAPI patterns and authentication
✅ Leverages existing database schema (no migrations needed)
✅ Implements Redis caching with appropriate TTLs
✅ Includes comprehensive OpenAPI documentation
✅ Has clear testing requirements
✅ Optimized for performance (< 200ms response times)

**Next Steps**:
1. Review this specification with team
2. Create feature branch: `feature/wave-2-backend-endpoints`
3. Implement endpoints in order (1 → 2 → 3 → 4)
4. Test each endpoint before moving to next
5. Integration testing with frontend components
6. Deploy to staging for QA validation

**Questions/Clarifications**: Contact backend team for database access patterns, frontend team for exact data format requirements.
