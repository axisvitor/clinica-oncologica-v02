# Metrics API - Technical Implementation Specification

**Version:** 1.0
**Status:** REQUIRED - Not Implemented
**Priority:** CRITICAL

---

## 1. API Endpoints Specification

### 1.1 GET /api/v2/metrics/summary

**Purpose:** Retrieve high-level KPI summary for dashboard cards

**Request:**
```http
GET /api/v2/metrics/summary
Authorization: Bearer {token}
Cookie: session_id={session_id}
```

**Query Parameters:** None

**Response (200 OK):**
```json
{
  "engagement_rate": 65.5,
  "quiz_completion_rate": 78.3,
  "ai_personalization_impact": 42.1,
  "active_patients": 247,
  "daily_messages": 1523,
  "system_health_score": 98.5,
  "timestamp": "2025-12-22T14:30:00Z"
}
```

**Error Responses:**
- 401 Unauthorized - Invalid/missing authentication
- 403 Forbidden - Insufficient permissions
- 500 Internal Server Error - Database/calculation error

**Cache:** 2 minutes (CACHE_TTL_REALTIME = 120)

**Calculation Logic:**
```
engagement_rate = (active_patients / total_patients) * 100
quiz_completion_rate = (completed_quizzes / sent_quizzes) * 100
ai_personalization_impact = (personalized_messages / total_messages) * 100
active_patients = count of patients with activity in last 7 days
daily_messages = count of messages sent/received today
system_health_score = average of (cpu < 80%, memory < 80%, disk < 90%, uptime)
```

**SQL Example:**
```python
# SQLAlchemy pseudo-code
summary = {
    'engagement_rate': (active_count / total_count * 100) if total_count else 0,
    'quiz_completion_rate': (completed_count / sent_count * 100) if sent_count else 0,
    'ai_personalization_impact': (personalized_count / processed_count * 100) if processed_count else 0,
    'active_patients': db.query(Patient).filter(Patient.last_activity >= now - 7days).count(),
    'daily_messages': db.query(Message).filter(Message.created_at >= today).count(),
    'system_health_score': calculate_system_health(),
    'timestamp': datetime.utcnow().isoformat()
}
```

---

### 1.2 GET /api/v2/metrics/realtime

**Purpose:** Retrieve detailed real-time metrics for dashboard charts

**Request:**
```http
GET /api/v2/metrics/realtime
Authorization: Bearer {token}
Cookie: session_id={session_id}
```

**Query Parameters:** None

**Response (200 OK):**
```json
{
  "engagement": {
    "total_patients": 350,
    "active_patients": 247,
    "engagement_rate": 70.5,
    "response_rate": 65.3,
    "avg_response_time_hours": 2.5,
    "daily_active_users": 180,
    "weekly_active_users": 245,
    "monthly_active_users": 320,
    "engagement_trend": [
      {"date": "2025-12-15", "active_users": 200},
      {"date": "2025-12-16", "active_users": 215},
      {"date": "2025-12-17", "active_users": 225},
      {"date": "2025-12-18", "active_users": 240},
      {"date": "2025-12-19", "active_users": 235},
      {"date": "2025-12-20", "active_users": 245},
      {"date": "2025-12-21", "active_users": 250},
      {"date": "2025-12-22", "active_users": 247}
    ]
  },
  "quiz": {
    "total_quizzes_sent": 580,
    "completed_quizzes": 455,
    "completion_rate": 78.4,
    "avg_completion_time_minutes": 12.5,
    "quiz_types": {
      "monthly_screening": {
        "total_sessions": 300,
        "completed_sessions": 245,
        "completion_rate": 81.7
      },
      "health_assessment": {
        "total_sessions": 180,
        "completed_sessions": 140,
        "completion_rate": 77.8
      },
      "treatment_feedback": {
        "total_sessions": 100,
        "completed_sessions": 70,
        "completion_rate": 70.0
      }
    },
    "monthly_quiz_stats": {
      "total_sent": 580,
      "total_completed": 455,
      "total_expired": 85,
      "total_active": 40,
      "average_score": 78.5,
      "completion_rate": 78.4,
      "expiration_rate": 14.7
    },
    "completion_trend": [
      {"date": "2025-12-15", "completed_quizzes": 45},
      {"date": "2025-12-16", "completed_quizzes": 52},
      {"date": "2025-12-17", "completed_quizzes": 58},
      {"date": "2025-12-18", "completed_quizzes": 62},
      {"date": "2025-12-19", "completed_quizzes": 59},
      {"date": "2025-12-20", "completed_quizzes": 65},
      {"date": "2025-12-21", "completed_quizzes": 68},
      {"date": "2025-12-22", "completed_quizzes": 52}
    ]
  },
  "ai_personalization": {
    "total_messages_processed": 1523,
    "personalized_messages": 642,
    "personalization_rate": 42.1,
    "avg_personalization_score": 7.8,
    "safety_interventions": 23,
    "fallback_rate": 3.2,
    "response_quality_score": 8.1,
    "personalization_impact": [
      {"metric": "engagement_increase", "value": 18.5, "unit": "%"},
      {"metric": "response_time_reduction", "value": 2.3, "unit": "hours"},
      {"metric": "satisfaction_increase", "value": 12.3, "unit": "%"}
    ]
  },
  "system_performance": {
    "cpu_usage": 42.5,
    "memory_usage": 68.3,
    "disk_usage": 54.2,
    "active_connections": 127,
    "response_time_ms": 145,
    "error_rate": 0.02,
    "uptime_seconds": 2592000,
    "throughput_rps": 125.5
  },
  "alerts_count": 3,
  "last_updated": "2025-12-22T14:30:15Z"
}
```

**Error Responses:**
- 401 Unauthorized
- 403 Forbidden
- 500 Internal Server Error

**Cache:** 2 minutes

**Data Collection Query Pattern:**
```python
def get_realtime_metrics():
    last_7_days = datetime.utcnow() - timedelta(days=7)
    last_30_days = datetime.utcnow() - timedelta(days=30)
    today = datetime.utcnow().date()

    return {
        'engagement': {
            'total_patients': db.query(Patient).count(),
            'active_patients': db.query(Patient).filter(
                Patient.last_activity >= last_7_days
            ).count(),
            'engagement_trend': db.query(
                func.date(Message.created_at),
                func.count(distinct(Message.patient_id))
            ).filter(
                Message.created_at >= last_7_days
            ).group_by(func.date(Message.created_at)).all(),
            # ... other fields
        },
        'quiz': {
            # ... quiz statistics
        },
        # ... other sections
    }
```

---

### 1.3 GET /api/v2/metrics/alerts

**Purpose:** Retrieve list of active alerts for the alert panel

**Request:**
```http
GET /api/v2/metrics/alerts
Authorization: Bearer {token}
Cookie: session_id={session_id}
```

**Query Parameters:**
- `severity` (optional): Filter by severity (low|medium|high|critical)
- `category` (optional): Filter by category (system|healthcare|security|performance|data_integrity|ai_service)
- `status` (optional): Filter by status (active|acknowledged|resolved|suppressed)

**Response (200 OK):**
```json
{
  "alerts": [
    {
      "id": "a1b2c3d4-e5f6-4g7h-8i9j-0k1l2m3n4o5p",
      "title": "High CPU Usage Detected",
      "description": "CPU usage has exceeded 80% threshold for 5 minutes",
      "severity": "high",
      "category": "system",
      "status": "active",
      "created_at": "2025-12-22T14:20:00Z",
      "acknowledged_at": null,
      "acknowledged_by": null,
      "resolved_at": null,
      "resolved_by": null,
      "current_value": 85.2,
      "threshold_value": 80.0,
      "source": "monitoring_service",
      "metadata": {
        "component": "api_server",
        "duration_minutes": 5,
        "peak_value": 92.3
      },
      "escalation_level": 1,
      "notification_channels": ["email", "dashboard"]
    },
    {
      "id": "b2c3d4e5-f6g7-4h8i-9j0k-1l2m3n4o5p6q",
      "title": "Quiz Response Delay",
      "description": "Average quiz completion time increased by 40%",
      "severity": "medium",
      "category": "performance",
      "status": "active",
      "created_at": "2025-12-22T13:45:00Z",
      "acknowledged_at": null,
      "acknowledged_by": null,
      "resolved_at": null,
      "resolved_by": null,
      "current_value": 17.8,
      "threshold_value": 15.0,
      "source": "analytics_service",
      "metadata": {
        "previous_avg": 12.5,
        "current_avg": 17.8,
        "increase_percent": 42.4
      },
      "escalation_level": null,
      "notification_channels": ["dashboard"]
    },
    {
      "id": "c3d4e5f6-g7h8-4i9j-0k1l-2m3n4o5p6q7r",
      "title": "Patient Engagement Alert",
      "description": "Engagement rate dropped below 65% threshold",
      "severity": "critical",
      "category": "healthcare",
      "status": "active",
      "created_at": "2025-12-22T14:15:00Z",
      "acknowledged_at": null,
      "acknowledged_by": null,
      "resolved_at": null,
      "resolved_by": null,
      "current_value": 62.3,
      "threshold_value": 65.0,
      "source": "engagement_monitor",
      "metadata": {
        "trend": "downward",
        "affected_segment": "dialysis",
        "patients_impacted": 45
      },
      "escalation_level": 2,
      "notification_channels": ["email", "sms", "dashboard"]
    }
  ]
}
```

**Error Responses:**
- 401 Unauthorized
- 403 Forbidden
- 500 Internal Server Error

**Cache:** 1 minute (or real-time for active alerts)

---

### 1.4 POST /api/v2/metrics/alerts/{alert_id}/acknowledge

**Purpose:** Mark an alert as acknowledged by the user

**Request:**
```http
POST /api/v2/metrics/alerts/a1b2c3d4-e5f6-4g7h-8i9j-0k1l2m3n4o5p/acknowledge
Authorization: Bearer {token}
Cookie: session_id={session_id}
Content-Type: application/json

{
  "notes": "Investigating the issue"
}
```

**Request Body:**
```json
{
  "notes": "Optional notes about the acknowledgment"
}
```

**Response (200 OK):**
```json
{
  "id": "a1b2c3d4-e5f6-4g7h-8i9j-0k1l2m3n4o5p",
  "title": "High CPU Usage Detected",
  "status": "acknowledged",
  "acknowledged_at": "2025-12-22T14:30:00Z",
  "acknowledged_by": "doctor_user_id"
}
```

**Error Responses:**
- 400 Bad Request - Invalid alert ID
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found - Alert not found
- 409 Conflict - Alert already resolved
- 500 Internal Server Error

**Side Effects:**
- Update alert.status = 'acknowledged'
- Set alert.acknowledged_at = now()
- Set alert.acknowledged_by = current_user_id
- Store alert.metadata['notes'] = provided_notes
- Broadcast update to connected WebSocket clients
- Log action to audit trail

---

### 1.5 POST /api/v2/metrics/export

**Purpose:** Export metrics data in specified format

**Request:**
```http
POST /api/v2/metrics/export
Authorization: Bearer {token}
Cookie: session_id={session_id}
Content-Type: application/json

{
  "start_date": "2025-11-22T00:00:00Z",
  "end_date": "2025-12-22T23:59:59Z",
  "format": "json"
}
```

**Request Body:**
```json
{
  "start_date": "ISO8601 datetime",
  "end_date": "ISO8601 datetime",
  "format": "json|csv|pdf"
}
```

**Response (200 OK):**
- Content-Type: application/json|text/csv|application/pdf
- File attachment with name: `metrics-export-2025-12-22.{json|csv|pdf}`

**Example JSON Export:**
```json
{
  "metadata": {
    "start_date": "2025-11-22T00:00:00Z",
    "end_date": "2025-12-22T23:59:59Z",
    "format": "json",
    "generated_at": "2025-12-22T14:30:00Z",
    "generated_by": "user_id"
  },
  "engagement": {
    "summary": {...},
    "daily": [...]
  },
  "quiz_performance": {
    "summary": {...},
    "daily": [...]
  },
  "ai_personalization": {
    "summary": {...},
    "daily": [...]
  },
  "system_performance": {
    "summary": {...},
    "daily": [...]
  }
}
```

**Error Responses:**
- 400 Bad Request - Invalid date range or format
- 401 Unauthorized
- 403 Forbidden
- 422 Unprocessable Entity - Invalid parameters
- 500 Internal Server Error

**Cache:** No cache (generate on demand)

**Rate Limiting:** 5 exports per hour per user

---

## 2. WebSocket Endpoint Specification

### 2.1 WS /api/v2/metrics/live

**Purpose:** Real-time streaming of metrics updates to subscribed clients

**Connection:**
```javascript
const ws = new WebSocket(
  (window.location.protocol === 'https:' ? 'wss:' : 'ws:') +
  window.location.host +
  '/api/v2/metrics/live'
);
```

**Authentication:** WebSocket connection includes cookies automatically (httpOnly cookies)

**Message Format - Server to Client:**

```json
{
  "type": "metrics_update|alert|ping|pong",
  "data": {
    // Metrics or alert data
  },
  "timestamp": "2025-12-22T14:30:15Z"
}
```

**Metrics Update Example (every 5-10 seconds):**
```json
{
  "type": "metrics_update",
  "data": {
    "engagement": {
      "active_patients": 247,
      "response_rate": 65.3
    },
    "quiz": {
      "completion_rate": 78.4,
      "completed_today": 52
    },
    "ai_personalization": {
      "personalization_rate": 42.1,
      "safety_interventions": 1
    },
    "system_performance": {
      "cpu_usage": 42.5,
      "memory_usage": 68.3
    }
  },
  "timestamp": "2025-12-22T14:30:15Z"
}
```

**Alert Update Example (on alert trigger):**
```json
{
  "type": "alert",
  "data": {
    "id": "alert_id",
    "title": "High CPU Usage",
    "severity": "high",
    "status": "active",
    "created_at": "2025-12-22T14:30:00Z"
  },
  "timestamp": "2025-12-22T14:30:15Z"
}
```

**Ping/Pong (every 30 seconds):**
```json
{
  "type": "ping",
  "timestamp": "2025-12-22T14:30:15Z"
}
```

**Client to Server:**

```json
{
  "type": "pong"
}
```

**Connection Lifecycle:**

1. **Client connects** → Server validates auth via cookies
2. **Server sends ping** every 30 seconds
3. **Client responds with pong** to keep connection alive
4. **Server sends metrics_update** every 5-10 seconds
5. **Server sends alert** when threshold exceeded
6. **Client disconnects** (page unload, manual close)
7. **Server closes connection**

**Error Handling:**

```json
{
  "type": "error",
  "data": {
    "code": "UNAUTHORIZED|INVALID_SESSION|SERVER_ERROR",
    "message": "Human-readable error message"
  },
  "timestamp": "2025-12-22T14:30:15Z"
}
```

**Connection Close Codes:**
- 1000: Normal closure
- 1001: Going away
- 4000: Authentication error
- 4001: Invalid/expired session
- 4002: Authorization error
- 1011: Server error

---

## 3. Database Schema Requirements

### 3.1 Engagement Metrics

```sql
CREATE TABLE engagement_metrics (
    id UUID PRIMARY KEY,
    patient_id UUID FOREIGN KEY,
    date DATE NOT NULL,
    daily_active BOOLEAN,
    response_received BOOLEAN,
    response_time_hours FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX (date, patient_id)
);
```

### 3.2 Quiz Metrics

```sql
CREATE TABLE quiz_response_metrics (
    id UUID PRIMARY KEY,
    patient_id UUID FOREIGN KEY,
    quiz_id UUID FOREIGN KEY,
    template_type VARCHAR(50),
    completed_at TIMESTAMP,
    completion_time_minutes FLOAT,
    score FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX (created_at, template_type)
);
```

### 3.3 Alerts

```sql
CREATE TABLE system_alerts (
    id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    severity ENUM('low', 'medium', 'high', 'critical'),
    category VARCHAR(50),
    status ENUM('active', 'acknowledged', 'resolved', 'suppressed'),
    created_at TIMESTAMP DEFAULT NOW(),
    acknowledged_at TIMESTAMP NULL,
    acknowledged_by UUID FOREIGN KEY,
    resolved_at TIMESTAMP NULL,
    resolved_by UUID FOREIGN KEY,
    current_value FLOAT,
    threshold_value FLOAT,
    source VARCHAR(100),
    metadata JSON,
    INDEX (status, severity, created_at)
);
```

---

## 4. Performance Considerations

### 4.1 Caching Strategy

| Endpoint | TTL | Invalidation | Strategy |
|----------|-----|--------------|----------|
| /metrics/summary | 2 min | Timer | Redis key expiry |
| /metrics/realtime | 2 min | Timer | Redis key expiry |
| /metrics/alerts | 1 min | Event | Real-time alert creation |
| /metrics/live | N/A | Streaming | No caching |

### 4.2 Query Optimization

```python
# Use database indexes on:
# - Message.created_at (for daily metrics)
# - QuizResponse.created_at (for quiz metrics)
# - Patient.last_activity (for engagement)
# - SystemAlert.status, created_at (for alerts)

# Batch queries together:
with db.session() as session:
    engagement_stats = session.query(...).all()  # Single query
    quiz_stats = session.query(...).all()  # Single query
    alert_count = session.query(...).count()  # Single query
    # Avoid N+1 queries
```

### 4.3 Rate Limiting

```python
from app.utils.rate_limiter import limiter

@router.get("/summary")
@limiter.limit("30/minute")  # 30 requests per minute
async def get_metrics_summary(request: Request):
    pass
```

---

## 5. Security Requirements

### 5.1 Authentication
- All endpoints require valid Bearer token or httpOnly session cookie
- WebSocket connections validated via existing session cookies

### 5.2 Authorization
- Doctors: See only their own patients' metrics
- Admins: See all metrics
- System alerts visible to all authenticated users

### 5.3 Data Validation
```python
class MetricsExportRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    format: Literal['json', 'csv', 'pdf']

    @field_validator('end_date')
    def validate_date_range(cls, v, values):
        if v <= values.get('start_date'):
            raise ValueError('end_date must be after start_date')
        if (v - values.get('start_date')).days > 365:
            raise ValueError('Date range cannot exceed 365 days')
        return v
```

### 5.4 Logging & Audit
- Log all alert acknowledgments
- Log all metric exports
- Track user access to metrics endpoints
- Monitor unusual access patterns

---

## 6. Error Handling

### 6.1 Standard Error Response

```json
{
  "error": "error_code",
  "detail": "Human-readable error message",
  "timestamp": "2025-12-22T14:30:00Z",
  "request_id": "req_123456"
}
```

### 6.2 HTTP Status Codes

| Code | Scenario |
|------|----------|
| 200 | Success |
| 400 | Bad request (validation error) |
| 401 | Unauthorized (missing/invalid auth) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not found (alert not found) |
| 409 | Conflict (alert already resolved) |
| 422 | Unprocessable entity (invalid data) |
| 429 | Too many requests (rate limit) |
| 500 | Server error |
| 503 | Service unavailable |

---

## 7. Testing Requirements

### 7.1 Unit Tests

```python
# test_metrics_endpoints.py
def test_get_metrics_summary():
    # Should return correct format
    # Should respect cache
    # Should filter by user role

def test_get_realtime_metrics():
    # Should return complete structure
    # Should calculate metrics correctly
    # Should include all trend data

def test_acknowledge_alert():
    # Should update alert status
    # Should record acknowledger
    # Should broadcast to WebSocket clients
```

### 7.2 Integration Tests

```python
# test_metrics_integration.py
def test_metrics_workflow():
    # 1. Create test data (patients, messages, quizzes)
    # 2. Call /metrics/summary
    # 3. Verify values are calculated correctly
    # 4. Create alert
    # 5. Call /metrics/alerts
    # 6. Acknowledge alert
    # 7. Verify status updated
```

### 7.3 WebSocket Tests

```python
# test_metrics_websocket.py
async def test_websocket_metrics_stream():
    # Connect to WebSocket
    # Verify receive metrics every 5-10s
    # Verify ping/pong heartbeat
    # Create alert and verify broadcast
    # Disconnect and verify clean close
```

---

## 8. Deployment Checklist

- [ ] Create metrics router module
- [ ] Create WebSocket handler
- [ ] Add database indexes
- [ ] Configure Redis caching
- [ ] Implement data validation
- [ ] Add rate limiting
- [ ] Set up logging
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Performance test (1000 concurrent users)
- [ ] Security audit
- [ ] Documentation review
- [ ] Staging deployment
- [ ] Production deployment
- [ ] Monitor metrics in production

---

## 9. Related Components

### 9.1 Frontend Components Using These Endpoints

| Component | Endpoints Used |
|-----------|---|
| MetricsDashboard | /summary, /realtime, /alerts, /alerts/{id}/acknowledge |
| MetricsDashboardPage | /summary, /realtime, /export |
| MetricsWebSocket | /live (WebSocket) |
| EngagementChart | /realtime (engagement data) |
| QuizCompletionChart | /realtime (quiz data) |
| AIPersonalizationChart | /realtime (ai_personalization data) |
| SystemHealthChart | /realtime (system_performance data) |

### 9.2 Backend Services to Query

| Data | Source Service |
|------|---|
| Patient metrics | PatientService |
| Message metrics | MessageService |
| Quiz metrics | QuizService |
| Alert data | AlertService |
| System health | HealthCheckService |

---

**Document Status:** Ready for Implementation
**Last Updated:** 2025-12-22
**Next Steps:** Backend development of metrics endpoints
