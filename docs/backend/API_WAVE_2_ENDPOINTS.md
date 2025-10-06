# Wave 2 Backend Endpoints - API Documentation

**Version**: 1.0.0
**Date**: 2025-10-06
**Base URL**: `https://api.hormonia.com/api/v1`
**Project**: Clínica Oncológica - Hormonia Backend

---

## Table of Contents

1. [Authentication](#authentication)
2. [Admin System Stats](#1-admin-system-stats)
3. [Analytics Treatment Distribution](#2-analytics-treatment-distribution)
4. [Physician Risk Assessments](#3-physician-risk-assessments)
5. [Medico Dashboard Stats](#4-medico-dashboard-stats)
6. [Rate Limiting](#rate-limiting)
7. [Caching Strategy](#caching-strategy)
8. [Error Response Format](#error-response-format)
9. [Performance Metrics](#performance-metrics)
10. [Frontend Integration Examples](#frontend-integration-examples)

---

## Authentication

All endpoints require Firebase JWT authentication passed in the Authorization header:

```bash
Authorization: Bearer <firebase_id_token>
```

### Role-Based Access Control

| Endpoint | Required Roles |
|----------|---------------|
| `/admin/system-stats` | `admin`, `super_admin` |
| `/analytics/treatment-distribution` | Any authenticated user |
| `/physician/risk-assessments` | `physician`, `doctor`, `admin` |
| `/medico/dashboard-stats` | `medico`, `doctor` |

### Authentication Flow

1. **Client**: Obtains Firebase ID token from Firebase Authentication
2. **Client**: Includes token in `Authorization` header
3. **Backend**: Validates token signature and expiration
4. **Backend**: Extracts user claims (uid, email, role)
5. **Backend**: Checks role-based permissions
6. **Backend**: Returns 401 (invalid token) or 403 (insufficient permissions)

---

## 1. Admin System Stats

### `GET /api/v1/admin/system-stats`

Get comprehensive system statistics for admin dashboard including real-time system health, user metrics, database performance, and service status.

#### Authorization

**Required Role**: `admin` or `super_admin`

#### Response Schema

**Status 200** - Success

```typescript
{
  system_health: {
    cpu_percent: number        // Current CPU usage (0-100)
    memory_percent: number     // Current memory usage (0-100)
    disk_usage_gb: number      // Current disk usage in GB
    uptime_hours: number       // System uptime in hours
  }
  active_users: {
    total: number              // Total active users
    doctors: number            // Active doctors
    patients: number           // Active patients
    admins: number             // Active admins
  }
  database_metrics: {
    total_size_mb: number      // Database size in MB
    active_connections: number // Current database connections
    query_performance_ms: number // Average query time
    cache_hit_rate: number     // Redis cache hit rate (0-1)
  }
  service_status: {
    redis: "healthy" | "degraded" | "down"
    database: "healthy" | "degraded" | "down"
    evolution_api: "healthy" | "degraded" | "down"
    openai_api: "healthy" | "degraded" | "down"
  }
  last_updated: string         // ISO8601 timestamp
}
```

#### Example Request

```bash
curl -X GET "https://api.hormonia.com/api/v1/admin/system-stats" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."
```

#### Example Response

```json
{
  "system_health": {
    "cpu_percent": 45.2,
    "memory_percent": 65.5,
    "disk_usage_gb": 128.7,
    "uptime_hours": 168.5
  },
  "active_users": {
    "total": 127,
    "doctors": 12,
    "patients": 98,
    "admins": 3
  },
  "database_metrics": {
    "total_size_mb": 2048.5,
    "active_connections": 15,
    "query_performance_ms": 45.3,
    "cache_hit_rate": 0.87
  },
  "service_status": {
    "redis": "healthy",
    "database": "healthy",
    "evolution_api": "healthy",
    "openai_api": "healthy"
  },
  "last_updated": "2025-10-06T14:30:00Z"
}
```

#### Cache Information

- **TTL**: 30 seconds
- **Cache Key**: `admin:system-stats`
- **Namespace**: `admin`

#### Error Responses

**Status 401** - Unauthorized

```json
{
  "detail": "Invalid or expired authentication token",
  "error_code": "UNAUTHORIZED",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

**Status 403** - Forbidden

```json
{
  "detail": "Admin role required to access system statistics",
  "error_code": "FORBIDDEN",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

**Status 500** - Internal Server Error

```json
{
  "detail": "Failed to retrieve system metrics",
  "error_code": "INTERNAL_ERROR",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

#### Performance Target

- **p50**: < 50ms
- **p95**: < 100ms
- **p99**: < 200ms

---

## 2. Analytics Treatment Distribution

### `GET /api/v1/analytics/treatment-distribution`

Get treatment type distribution statistics with patient counts, percentages, and trend data over a specified time period.

#### Authorization

**Required**: Any authenticated user

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `period` | string | No | `30d` | Time period: `7d`, `30d`, `90d`, or `all` |
| `doctor_id` | uuid | No | Current user | Filter by specific doctor (admin only) |

#### Response Schema

**Status 200** - Success

```typescript
{
  period: string                 // Selected period (7d, 30d, 90d, all)
  total_patients: number         // Total patients in analysis
  distribution: Array<{
    treatment_type: string       // Treatment type name
    count: number                // Number of patients
    percentage: number           // Percentage of total (0-100)
    active_patients: number      // Currently active patients
    avg_treatment_days: number   // Average days in treatment
    color: string                // Hex color for charts
  }>
  trend_data: Array<{
    week: string                 // ISO date (week start)
    count: number                // Patient count that week
  }>
  last_updated: string           // ISO8601 timestamp
}
```

#### Example Requests

**Default Period (30 days)**

```bash
curl -X GET "https://api.hormonia.com/api/v1/analytics/treatment-distribution" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."
```

**Custom Period**

```bash
curl -X GET "https://api.hormonia.com/api/v1/analytics/treatment-distribution?period=90d" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."
```

**Admin: Specific Doctor**

```bash
curl -X GET "https://api.hormonia.com/api/v1/analytics/treatment-distribution?doctor_id=550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."
```

#### Example Response

```json
{
  "period": "30d",
  "total_patients": 127,
  "distribution": [
    {
      "treatment_type": "Terapia Hormonal - Mama",
      "count": 45,
      "percentage": 35.43,
      "active_patients": 42,
      "avg_treatment_days": 87.5,
      "color": "#3B82F6"
    },
    {
      "treatment_type": "Quimioterapia - Próstata",
      "count": 38,
      "percentage": 29.92,
      "active_patients": 35,
      "avg_treatment_days": 62.3,
      "color": "#10B981"
    },
    {
      "treatment_type": "Radioterapia - Mama",
      "count": 28,
      "percentage": 22.05,
      "active_patients": 25,
      "avg_treatment_days": 45.8,
      "color": "#F59E0B"
    },
    {
      "treatment_type": "Imunoterapia",
      "count": 16,
      "percentage": 12.60,
      "active_patients": 14,
      "avg_treatment_days": 120.2,
      "color": "#EF4444"
    }
  ],
  "trend_data": [
    {
      "week": "2025-09-08",
      "count": 118
    },
    {
      "week": "2025-09-15",
      "count": 122
    },
    {
      "week": "2025-09-22",
      "count": 125
    },
    {
      "week": "2025-09-29",
      "count": 127
    }
  ],
  "last_updated": "2025-10-06T14:30:00Z"
}
```

#### Cache Information

- **TTL**: 5 minutes (300 seconds)
- **Cache Key**: `analytics:treatment-dist:{period}:{doctor_id}`
- **Namespace**: `analytics`

#### Error Responses

**Status 401** - Unauthorized

```json
{
  "detail": "Authentication required",
  "error_code": "UNAUTHORIZED",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

**Status 403** - Forbidden

```json
{
  "detail": "Cannot access other doctor's data",
  "error_code": "FORBIDDEN",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

**Status 422** - Validation Error

```json
{
  "detail": "Invalid period parameter. Must be one of: 7d, 30d, 90d, all",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

#### Performance Target

- **p50**: < 75ms
- **p95**: < 150ms
- **p99**: < 300ms

---

## 3. Physician Risk Assessments

### `GET /api/v1/physician/risk-assessments`

Get aggregated patient risk assessment data including severity levels, recent alerts, and risk trends. **Replaces N+1 query pattern** (51 requests → 1 request).

#### Authorization

**Required Role**: `physician`, `doctor`, or `admin`

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `patient_id` | uuid | No | All patients | Filter by specific patient |
| `risk_level` | string | No | All levels | Filter by risk: `low`, `medium`, `high`, `critical` |
| `limit` | integer | No | `20` | Maximum results (1-100) |

#### Response Schema

**Status 200** - Success

```typescript
{
  assessments: Array<{
    patient_id: string                    // Patient UUID
    patient_name: string                  // Patient full name
    risk_level: "low" | "medium" | "high" | "critical"
    risk_score: number                    // Calculated score (0-10)
    risk_category: string                 // Primary risk driver
    assessment_date: string               // ISO8601 timestamp
    recent_alerts: Array<{
      severity: "low" | "medium" | "high" | "critical"
      type: string                        // Alert type
      message: string                     // Alert message
      created_at: string                  // ISO8601 timestamp
    }>
    trend: "improving" | "stable" | "worsening"
    last_interaction: string | null       // Last patient interaction
  }>
  summary: {
    total_patients: number                // Total in result set
    by_risk_level: {
      critical: number
      high: number
      medium: number
      low: number
    }
    requiring_attention: number           // Critical + high count
  }
  last_updated: string                    // ISO8601 timestamp
}
```

#### Example Requests

**All Patients**

```bash
curl -X GET "https://api.hormonia.com/api/v1/physician/risk-assessments" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."
```

**Single Patient**

```bash
curl -X GET "https://api.hormonia.com/api/v1/physician/risk-assessments?patient_id=550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."
```

**Filter by Risk Level**

```bash
curl -X GET "https://api.hormonia.com/api/v1/physician/risk-assessments?risk_level=high&limit=50" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."
```

#### Example Response

```json
{
  "assessments": [
    {
      "patient_id": "550e8400-e29b-41d4-a716-446655440000",
      "patient_name": "Maria Silva",
      "risk_level": "high",
      "risk_score": 7.5,
      "risk_category": "symptom_severity",
      "assessment_date": "2025-10-06T14:30:00Z",
      "recent_alerts": [
        {
          "severity": "high",
          "type": "severe_symptom",
          "message": "Náusea severa reportada",
          "created_at": "2025-10-06T10:15:00Z"
        },
        {
          "severity": "medium",
          "type": "medication_missed",
          "message": "Medicação não tomada por 2 dias",
          "created_at": "2025-10-05T18:30:00Z"
        }
      ],
      "trend": "worsening",
      "last_interaction": "2025-10-06T12:00:00Z"
    },
    {
      "patient_id": "660e8400-e29b-41d4-a716-446655440001",
      "patient_name": "João Santos",
      "risk_level": "medium",
      "risk_score": 5.2,
      "risk_category": "adherence",
      "assessment_date": "2025-10-06T14:30:00Z",
      "recent_alerts": [
        {
          "severity": "medium",
          "type": "quiz_incomplete",
          "message": "Questionário diário não respondido",
          "created_at": "2025-10-06T09:00:00Z"
        }
      ],
      "trend": "stable",
      "last_interaction": "2025-10-05T20:15:00Z"
    }
  ],
  "summary": {
    "total_patients": 45,
    "by_risk_level": {
      "critical": 3,
      "high": 12,
      "medium": 20,
      "low": 10
    },
    "requiring_attention": 15
  },
  "last_updated": "2025-10-06T14:30:00Z"
}
```

#### Cache Information

- **TTL**: 1 minute (60 seconds)
- **Cache Key**: `physician:risk-assess:{doctor_id}:{patient_id}:{risk_level}:{limit}`
- **Namespace**: `physician`

#### Performance Impact

**Before (N+1 Pattern)**:
- 51 API calls (1 patient list + 50 individual risk calls)
- Total time: 2-3 seconds

**After (Aggregated)**:
- 1 API call
- Total time: 100-200ms
- **98% reduction in API calls**
- **10-15x faster load time**

#### Error Responses

**Status 401** - Unauthorized

```json
{
  "detail": "Authentication required",
  "error_code": "UNAUTHORIZED",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

**Status 403** - Forbidden

```json
{
  "detail": "Physician role required to access risk assessments",
  "error_code": "FORBIDDEN",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

**Status 404** - Not Found

```json
{
  "detail": "Patient not found or access denied",
  "error_code": "NOT_FOUND",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

#### Performance Target

- **p50**: < 100ms
- **p95**: < 200ms
- **p99**: < 400ms

---

## 4. Medico Dashboard Stats

### `GET /api/v1/medico/dashboard-stats`

Get comprehensive dashboard statistics for medical professionals including patient counts, treatment metrics, engagement data, and alerts summary.

#### Authorization

**Required Role**: `medico` or `doctor`

#### Response Schema

**Status 200** - Success

```typescript
{
  overview: {
    total_patients: number           // Total patients under care
    active_treatments: number        // Currently active protocols
    pending_reviews: number          // Patients requiring review
    new_alerts_today: number         // Alerts created today
  }
  patient_breakdown: {
    by_flow_state: {
      active: number
      paused: number
      completed: number
      onboarding: number
      inactive: number
    }
    by_treatment_type: Array<{
      treatment_type: string
      count: number
    }>
  }
  engagement_metrics: {
    messages_today: number           // Messages sent today
    response_rate_7d: number         // 7-day response rate (0-100)
    avg_response_time_hours: number  // Average response time
    quizzes_completed_7d: number     // Quizzes completed in 7 days
  }
  alerts_summary: {
    unacknowledged: number           // Total unacknowledged alerts
    by_severity: {
      critical: number
      high: number
      medium: number
      low: number
    }
  }
  recent_activity: Array<{
    type: "message" | "alert" | "quiz_completion" | "treatment_update"
    patient_name: string
    description: string
    timestamp: string                // ISO8601 timestamp
  }>
  performance_indicators: {
    completion_rate: number          // Treatment completion rate (%)
    patient_satisfaction_score: number // Average satisfaction (0-5)
    adherence_rate: number           // Treatment adherence (%)
  }
  last_updated: string               // ISO8601 timestamp
}
```

#### Example Request

```bash
curl -X GET "https://api.hormonia.com/api/v1/medico/dashboard-stats" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."
```

#### Example Response

```json
{
  "overview": {
    "total_patients": 87,
    "active_treatments": 65,
    "pending_reviews": 12,
    "new_alerts_today": 5
  },
  "patient_breakdown": {
    "by_flow_state": {
      "active": 65,
      "paused": 8,
      "completed": 14,
      "onboarding": 0,
      "inactive": 0
    },
    "by_treatment_type": [
      {
        "treatment_type": "Terapia Hormonal - Mama",
        "count": 32
      },
      {
        "treatment_type": "Quimioterapia - Próstata",
        "count": 28
      },
      {
        "treatment_type": "Radioterapia",
        "count": 18
      },
      {
        "treatment_type": "Imunoterapia",
        "count": 9
      }
    ]
  },
  "engagement_metrics": {
    "messages_today": 45,
    "response_rate_7d": 87.5,
    "avg_response_time_hours": 2.3,
    "quizzes_completed_7d": 32
  },
  "alerts_summary": {
    "unacknowledged": 8,
    "by_severity": {
      "critical": 2,
      "high": 5,
      "medium": 10,
      "low": 15
    }
  },
  "recent_activity": [
    {
      "type": "alert",
      "patient_name": "Maria Silva",
      "description": "Alerta de náusea severa",
      "timestamp": "2025-10-06T14:15:00Z"
    },
    {
      "type": "quiz_completion",
      "patient_name": "João Santos",
      "description": "Questionário diário completado",
      "timestamp": "2025-10-06T13:45:00Z"
    },
    {
      "type": "message",
      "patient_name": "Ana Costa",
      "description": "Mensagem enviada",
      "timestamp": "2025-10-06T13:30:00Z"
    }
  ],
  "performance_indicators": {
    "completion_rate": 78.5,
    "patient_satisfaction_score": 4.6,
    "adherence_rate": 85.2
  },
  "last_updated": "2025-10-06T14:30:00Z"
}
```

#### Cache Information

- **TTL**: 2 minutes (120 seconds)
- **Cache Key**: `medico:dash:{doctor_id}`
- **Namespace**: `medico`

#### Edge Cases

**New Doctor (No Patients)**

```json
{
  "overview": {
    "total_patients": 0,
    "active_treatments": 0,
    "pending_reviews": 0,
    "new_alerts_today": 0
  },
  "patient_breakdown": {
    "by_flow_state": {
      "active": 0,
      "paused": 0,
      "completed": 0,
      "onboarding": 0,
      "inactive": 0
    },
    "by_treatment_type": []
  },
  "engagement_metrics": {
    "messages_today": 0,
    "response_rate_7d": 0.0,
    "avg_response_time_hours": null,
    "quizzes_completed_7d": 0
  },
  "alerts_summary": {
    "unacknowledged": 0,
    "by_severity": {
      "critical": 0,
      "high": 0,
      "medium": 0,
      "low": 0
    }
  },
  "recent_activity": [],
  "performance_indicators": {
    "completion_rate": 0.0,
    "patient_satisfaction_score": 0.0,
    "adherence_rate": 0.0
  },
  "last_updated": "2025-10-06T14:30:00Z"
}
```

#### Error Responses

**Status 401** - Unauthorized

```json
{
  "detail": "Authentication required",
  "error_code": "UNAUTHORIZED",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

**Status 403** - Forbidden

```json
{
  "detail": "Doctor role required to access dashboard statistics",
  "error_code": "FORBIDDEN",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

**Status 500** - Internal Server Error

```json
{
  "detail": "Failed to retrieve dashboard statistics",
  "error_code": "INTERNAL_ERROR",
  "timestamp": "2025-10-06T14:30:00Z"
}
```

#### Performance Target

- **p50**: < 60ms
- **p95**: < 100ms
- **p99**: < 250ms

---

## Rate Limiting

All endpoints are subject to rate limiting to ensure fair usage and system stability.

### Rate Limit Headers

All responses include rate limit information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067800
```

### Rate Limits by Endpoint Category

| Category | Rate Limit | Window |
|----------|------------|--------|
| Admin endpoints | 100 requests | per minute |
| Analytics endpoints | 50 requests | per minute |
| User endpoints | 200 requests | per minute |

### Rate Limit Exceeded Response

**Status 429** - Too Many Requests

```json
{
  "detail": "Rate limit exceeded. Please wait before retrying.",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 45,
  "timestamp": "2025-10-06T14:30:00Z"
}
```

---

## Caching Strategy

All Wave 2 endpoints implement Redis-based caching for optimal performance.

### Cache Configuration Table

| Endpoint | TTL | Cache Key Pattern | Invalidation Trigger |
|----------|-----|-------------------|---------------------|
| `/admin/system-stats` | 30s | `admin:system-stats` | System events, manual |
| `/analytics/treatment-distribution` | 5min | `analytics:treatment-dist:{period}:{doctor_id}` | Patient create/update |
| `/physician/risk-assessments` | 1min | `physician:risk-assess:{doctor_id}:{patient_id}:{risk_level}:{limit}` | Alert create/acknowledge |
| `/medico/dashboard-stats` | 2min | `medico:dash:{doctor_id}` | Patient/message/alert changes |

### Cache Headers

Responses include cache-related headers:

```http
X-Cache-Status: HIT
X-Cache-TTL: 120
X-Cache-Age: 45
```

**Cache Status Values**:
- `HIT`: Response served from cache
- `MISS`: Response computed and cached
- `BYPASS`: Cache bypassed (e.g., admin force refresh)
- `EXPIRED`: Cache entry expired, recomputed

### Manual Cache Invalidation

Admin users can force cache invalidation:

```bash
POST /api/v1/cache/invalidate
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "patterns": [
    "analytics:treatment-dist:*",
    "medico:dash:*"
  ]
}
```

---

## Error Response Format

All errors follow a consistent structure for easy client-side handling.

### Standard Error Schema

```typescript
{
  detail: string              // Human-readable error message
  error_code: string          // Machine-readable error code
  timestamp: string           // ISO8601 timestamp
  request_id?: string         // Optional request tracking ID
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or expired authentication token |
| `FORBIDDEN` | 403 | Insufficient permissions for resource |
| `NOT_FOUND` | 404 | Resource not found or access denied |
| `VALIDATION_ERROR` | 422 | Invalid request parameters |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

### Validation Error Details

**Status 422** - Validation Error with Field Details

```json
{
  "detail": "Validation error",
  "error_code": "VALIDATION_ERROR",
  "errors": [
    {
      "field": "period",
      "message": "Must be one of: 7d, 30d, 90d, all",
      "value": "invalid_period"
    },
    {
      "field": "limit",
      "message": "Must be between 1 and 100",
      "value": 150
    }
  ],
  "timestamp": "2025-10-06T14:30:00Z"
}
```

---

## Performance Metrics

All endpoints are monitored for performance and availability.

### Response Time Targets

| Endpoint | p50 | p95 | p99 | Max |
|----------|-----|-----|-----|-----|
| `/admin/system-stats` | 50ms | 100ms | 200ms | 500ms |
| `/analytics/treatment-distribution` | 75ms | 150ms | 300ms | 600ms |
| `/physician/risk-assessments` | 100ms | 200ms | 400ms | 800ms |
| `/medico/dashboard-stats` | 60ms | 100ms | 250ms | 500ms |

### Performance Improvements

**PhysicianDashboard Optimization**:
- **Before**: 51 API calls, 2-3 seconds load time
- **After**: 1 API call, 100-200ms load time
- **Improvement**: 98% reduction in requests, 10-15x faster

### Monitoring Metrics

All endpoints expose Prometheus metrics:

```
# Response time histogram
http_request_duration_seconds{endpoint="/api/v1/admin/system-stats",status="200"}

# Request count
http_requests_total{endpoint="/api/v1/admin/system-stats",status="200"}

# Cache hit rate
cache_hit_rate{endpoint="/api/v1/analytics/treatment-distribution"}

# Error rate
http_errors_total{endpoint="/api/v1/physician/risk-assessments",status="500"}
```

---

## Frontend Integration Examples

### React Query (TypeScript)

#### 1. Admin System Stats Hook

**File**: `src/hooks/useSystemStats.ts`

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

interface SystemStats {
  system_health: {
    cpu_percent: number
    memory_percent: number
    disk_usage_gb: number
    uptime_hours: number
  }
  active_users: {
    total: number
    doctors: number
    patients: number
    admins: number
  }
  database_metrics: {
    total_size_mb: number
    active_connections: number
    query_performance_ms: number
    cache_hit_rate: number
  }
  service_status: {
    redis: string
    database: string
    evolution_api: string
    openai_api: string
  }
  last_updated: string
}

export function useSystemStats() {
  return useQuery({
    queryKey: ['admin', 'system-stats'],
    queryFn: async () => {
      const response = await apiClient.request<SystemStats>(
        '/api/v1/admin/system-stats'
      )
      return response.data
    },
    refetchInterval: 30000,  // Match cache TTL
    staleTime: 25000,
    retry: 2
  })
}
```

**Usage in Component**:

```tsx
import { useSystemStats } from '@/hooks/useSystemStats'

function AdminDashboard() {
  const { data: stats, isLoading, error } = useSystemStats()

  if (isLoading) return <LoadingSkeleton />
  if (error) return <ErrorState error={error} />

  return (
    <div className="grid grid-cols-2 gap-4">
      <StatCard
        label="CPU Usage"
        value={`${stats.system_health.cpu_percent}%`}
        status={stats.system_health.cpu_percent > 80 ? 'warning' : 'normal'}
      />
      <StatCard
        label="Active Users"
        value={stats.active_users.total}
      />
      <StatCard
        label="Database Size"
        value={`${stats.database_metrics.total_size_mb} MB`}
      />
      <StatCard
        label="Cache Hit Rate"
        value={`${(stats.database_metrics.cache_hit_rate * 100).toFixed(1)}%`}
      />
    </div>
  )
}
```

#### 2. Treatment Distribution Hook

**File**: `src/hooks/useTreatmentDistribution.ts`

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

interface TreatmentDistribution {
  period: string
  total_patients: number
  distribution: Array<{
    treatment_type: string
    count: number
    percentage: number
    active_patients: number
    avg_treatment_days: number
    color: string
  }>
  trend_data: Array<{
    week: string
    count: number
  }>
  last_updated: string
}

export function useTreatmentDistribution(period: string = '30d') {
  return useQuery({
    queryKey: ['analytics', 'treatment-distribution', period],
    queryFn: async () => {
      const response = await apiClient.request<TreatmentDistribution>(
        `/api/v1/analytics/treatment-distribution?period=${period}`
      )
      return response.data
    },
    refetchInterval: 300000,  // 5 minutes
    staleTime: 240000,
    enabled: !!period
  })
}
```

**Usage in Chart Component**:

```tsx
import { useTreatmentDistribution } from '@/hooks/useTreatmentDistribution'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

function TreatmentDistributionChart({ period = '30d' }) {
  const { data, isLoading } = useTreatmentDistribution(period)

  if (isLoading) return <ChartSkeleton />

  return (
    <div>
      <h3>Distribuição de Tratamentos ({data.period})</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data.distribution}
            dataKey="count"
            nameKey="treatment_type"
            cx="50%"
            cy="50%"
            outerRadius={80}
            label={({ percentage }) => `${percentage.toFixed(1)}%`}
          >
            {data.distribution.map((entry, index) => (
              <Cell key={index} fill={entry.color} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <p>Total de pacientes: {data.total_patients}</p>
    </div>
  )
}
```

#### 3. Physician Risk Assessments Hook

**File**: `src/hooks/useRiskAssessments.ts`

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

interface RiskAssessment {
  patient_id: string
  patient_name: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  risk_score: number
  risk_category: string
  assessment_date: string
  recent_alerts: Array<{
    severity: string
    type: string
    message: string
    created_at: string
  }>
  trend: 'improving' | 'stable' | 'worsening'
  last_interaction: string | null
}

interface RiskAssessmentsResponse {
  assessments: RiskAssessment[]
  summary: {
    total_patients: number
    by_risk_level: {
      critical: number
      high: number
      medium: number
      low: number
    }
    requiring_attention: number
  }
  last_updated: string
}

export function useRiskAssessments(
  patientId?: string,
  riskLevel?: string,
  limit: number = 20
) {
  const params = new URLSearchParams()
  if (patientId) params.append('patient_id', patientId)
  if (riskLevel) params.append('risk_level', riskLevel)
  if (limit) params.append('limit', limit.toString())

  return useQuery({
    queryKey: ['physician', 'risk-assessments', patientId, riskLevel, limit],
    queryFn: async () => {
      const response = await apiClient.request<RiskAssessmentsResponse>(
        `/api/v1/physician/risk-assessments?${params.toString()}`
      )
      return response.data
    },
    refetchInterval: 60000,  // 1 minute
    staleTime: 50000,
    retry: 3
  })
}
```

**Usage in Dashboard**:

```tsx
import { useRiskAssessments } from '@/hooks/useRiskAssessments'

function PhysicianDashboard() {
  const [riskFilter, setRiskFilter] = useState<string>()
  const { data, isLoading } = useRiskAssessments(undefined, riskFilter)

  if (isLoading) return <DashboardSkeleton />

  return (
    <div>
      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <SummaryCard
          label="Total Patients"
          value={data.summary.total_patients}
        />
        <SummaryCard
          label="Critical"
          value={data.summary.by_risk_level.critical}
          status="critical"
        />
        <SummaryCard
          label="High Risk"
          value={data.summary.by_risk_level.high}
          status="high"
        />
        <SummaryCard
          label="Requiring Attention"
          value={data.summary.requiring_attention}
          status="warning"
        />
      </div>

      {/* Risk Filter */}
      <div className="mb-4">
        <button onClick={() => setRiskFilter(undefined)}>All</button>
        <button onClick={() => setRiskFilter('critical')}>Critical</button>
        <button onClick={() => setRiskFilter('high')}>High</button>
        <button onClick={() => setRiskFilter('medium')}>Medium</button>
        <button onClick={() => setRiskFilter('low')}>Low</button>
      </div>

      {/* Patient List */}
      <table>
        <thead>
          <tr>
            <th>Patient</th>
            <th>Risk Level</th>
            <th>Risk Score</th>
            <th>Alerts</th>
            <th>Trend</th>
            <th>Last Interaction</th>
          </tr>
        </thead>
        <tbody>
          {data.assessments.map(assessment => (
            <tr key={assessment.patient_id}>
              <td>{assessment.patient_name}</td>
              <td>
                <RiskBadge level={assessment.risk_level} />
              </td>
              <td>{assessment.risk_score.toFixed(1)}</td>
              <td>{assessment.recent_alerts.length}</td>
              <td>
                <TrendIndicator trend={assessment.trend} />
              </td>
              <td>
                {assessment.last_interaction
                  ? formatRelativeTime(assessment.last_interaction)
                  : 'Never'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

#### 4. Medico Dashboard Stats Hook

**File**: `src/hooks/useMedicoDashboardStats.ts`

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

interface MedicoDashboardStats {
  overview: {
    total_patients: number
    active_treatments: number
    pending_reviews: number
    new_alerts_today: number
  }
  patient_breakdown: {
    by_flow_state: Record<string, number>
    by_treatment_type: Array<{
      treatment_type: string
      count: number
    }>
  }
  engagement_metrics: {
    messages_today: number
    response_rate_7d: number
    avg_response_time_hours: number
    quizzes_completed_7d: number
  }
  alerts_summary: {
    unacknowledged: number
    by_severity: {
      critical: number
      high: number
      medium: number
      low: number
    }
  }
  recent_activity: Array<{
    type: string
    patient_name: string
    description: string
    timestamp: string
  }>
  performance_indicators: {
    completion_rate: number
    patient_satisfaction_score: number
    adherence_rate: number
  }
  last_updated: string
}

export function useMedicoDashboardStats() {
  return useQuery({
    queryKey: ['medico', 'dashboard-stats'],
    queryFn: async () => {
      const response = await apiClient.request<MedicoDashboardStats>(
        '/api/v1/medico/dashboard-stats'
      )
      return response.data
    },
    refetchInterval: 120000,  // 2 minutes
    staleTime: 100000,
    retry: 2
  })
}
```

**Usage in Dashboard**:

```tsx
import { useMedicoDashboardStats } from '@/hooks/useMedicoDashboardStats'

function MedicoDashboard() {
  const { data: stats, isLoading, error } = useMedicoDashboardStats()

  if (isLoading) return <DashboardSkeleton />
  if (error) return <ErrorState error={error} />

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="Total Pacientes"
          value={stats.overview.total_patients}
          icon="users"
        />
        <MetricCard
          label="Tratamentos Ativos"
          value={stats.overview.active_treatments}
          icon="activity"
        />
        <MetricCard
          label="Pendências"
          value={stats.overview.pending_reviews}
          icon="alert-circle"
          status={stats.overview.pending_reviews > 0 ? 'warning' : 'normal'}
        />
        <MetricCard
          label="Alertas Hoje"
          value={stats.overview.new_alerts_today}
          icon="bell"
        />
      </div>

      {/* Engagement Metrics */}
      <div className="grid grid-cols-3 gap-4">
        <MetricCard
          label="Mensagens Hoje"
          value={stats.engagement_metrics.messages_today}
          icon="message-square"
        />
        <MetricCard
          label="Taxa de Resposta (7d)"
          value={`${stats.engagement_metrics.response_rate_7d.toFixed(1)}%`}
          icon="trending-up"
        />
        <MetricCard
          label="Tempo Médio de Resposta"
          value={`${stats.engagement_metrics.avg_response_time_hours.toFixed(1)}h`}
          icon="clock"
        />
      </div>

      {/* Alerts Summary */}
      <AlertsSummaryCard
        unacknowledged={stats.alerts_summary.unacknowledged}
        bySeverity={stats.alerts_summary.by_severity}
      />

      {/* Treatment Distribution */}
      <TreatmentBreakdownChart
        data={stats.patient_breakdown.by_treatment_type}
      />

      {/* Recent Activity Feed */}
      <RecentActivityFeed
        activities={stats.recent_activity}
      />
    </div>
  )
}
```

### Error Handling Pattern

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient, ApiError } from '@/lib/api-client'

function useApiData<T>(endpoint: string) {
  return useQuery({
    queryKey: [endpoint],
    queryFn: async () => {
      try {
        const response = await apiClient.request<T>(endpoint)
        return response.data
      } catch (error) {
        if (error instanceof ApiError) {
          // Handle specific API errors
          if (error.status === 401) {
            // Redirect to login
            window.location.href = '/login'
          } else if (error.status === 403) {
            // Show permission denied message
            throw new Error('You do not have permission to access this resource')
          } else if (error.status === 429) {
            // Rate limit exceeded
            throw new Error('Too many requests. Please wait before trying again.')
          }
        }
        throw error
      }
    },
    retry: (failureCount, error) => {
      // Don't retry on auth errors
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        return false
      }
      return failureCount < 3
    }
  })
}
```

---

## Changelog

### v1.0.0 (2025-10-06)

**Added**:
- Initial release of 4 Wave 2 endpoints
- `GET /api/v1/admin/system-stats` - Admin system statistics
- `GET /api/v1/analytics/treatment-distribution` - Treatment type distribution
- `GET /api/v1/physician/risk-assessments` - Patient risk assessments (N+1 resolver)
- `GET /api/v1/medico/dashboard-stats` - Doctor dashboard statistics
- Complete OpenAPI specifications
- TypeScript type definitions
- React Query integration examples
- Performance optimization guidelines
- Caching strategy documentation

---

## Support

**API Support**: api-support@hormonia.com
**Documentation**: https://docs.hormonia.com/api
**Slack Channel**: #api-support

**Response Times**:
- **Critical Issues**: < 1 hour
- **High Priority**: < 4 hours
- **Normal Priority**: < 24 hours

---

**Last Updated**: 2025-10-06
**Document Version**: 1.0.0
**API Version**: v1
