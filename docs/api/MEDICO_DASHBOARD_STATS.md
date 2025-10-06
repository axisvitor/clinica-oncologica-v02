# Medico Dashboard Statistics API

## Overview

The Medico Dashboard Statistics endpoint provides real-time metrics for doctor's administrative panel in the Hormonia oncology patient management system.

**Endpoint**: `GET /api/v1/medico/dashboard-stats`

**Authentication**: Required (Doctor role or higher)

**Rate Limiting**: Standard API rate limits apply

**Caching**: 2-minute Redis cache (TTL: 120 seconds)

---

## Response Schema

### MedicoDashboardStats

```typescript
interface MedicoDashboardStats {
  pacientes_ativos: number;        // Active patients count
  consultas_hoje: number;          // Today's consultations
  pendencias: number;              // Pending tasks (messages + exams)
  exames_aguardando: number;       // Exams awaiting review
  engagement: EngagementMetrics;   // Message engagement data
  alerts: AlertMetrics;            // Alert counts by severity
  timestamp: string;               // ISO 8601 timestamp
}

interface EngagementMetrics {
  messages_today: number;          // Messages sent today
  messages_unread: number;         // Unread messages
  response_rate: number;           // Response rate (0.0 - 1.0)
  avg_response_time_minutes: number | null; // Avg response time
}

interface AlertMetrics {
  total: number;                   // Total active alerts
  critical: number;                // Critical alerts
  high: number;                    // High priority alerts
  medium: number;                  // Medium priority alerts
  low: number;                     // Low priority alerts
}
```

---

## Example Response

```json
{
  "pacientes_ativos": 45,
  "consultas_hoje": 8,
  "pendencias": 12,
  "exames_aguardando": 5,
  "engagement": {
    "messages_today": 23,
    "messages_unread": 4,
    "response_rate": 0.87,
    "avg_response_time_minutes": 45
  },
  "alerts": {
    "total": 15,
    "critical": 2,
    "high": 5,
    "medium": 6,
    "low": 2
  },
  "timestamp": "2025-10-06T14:30:00Z"
}
```

---

## Field Descriptions

### Core Metrics

| Field | Type | Description | Calculation |
|-------|------|-------------|-------------|
| `pacientes_ativos` | `integer` | Active patients count | Patients with `flow_state` NOT IN ('inactive', 'completed') |
| `consultas_hoje` | `integer` | Today's consultations | Outbound messages sent today (proxy for consultations) |
| `pendencias` | `integer` | Pending tasks | Unread inbound messages from last 48 hours |
| `exames_aguardando` | `integer` | Exams awaiting review | Currently returns 0 (exams table not implemented) |

### Engagement Metrics

| Field | Type | Description | Calculation |
|-------|------|-------------|-------------|
| `messages_today` | `integer` | Messages sent today | Outbound messages with `created_at` = today |
| `messages_unread` | `integer` | Unread messages | Inbound messages with `status` != 'READ' |
| `response_rate` | `float` | Response rate (0-1) | (Read messages / Total inbound messages) in last 7 days |
| `avg_response_time_minutes` | `integer\|null` | Avg response time | Currently returns `null` (threading not implemented) |

### Alert Metrics

| Field | Type | Description | Calculation |
|-------|------|-------------|-------------|
| `total` | `integer` | Total active alerts | Alerts with `status` IN ('pending', 'active') |
| `critical` | `integer` | Critical alerts | Alerts with `severity` = 'CRITICAL' |
| `high` | `integer` | High priority | Alerts with `severity` = 'HIGH' |
| `medium` | `integer` | Medium priority | Alerts with `severity` = 'MEDIUM' |
| `low` | `integer` | Low priority | Alerts with `severity` = 'LOW' |

---

## Database Tables

The endpoint queries the following tables:

1. **`patients`** - Active patients filtering
   - `doctor_id` (FK to users)
   - `flow_state` (enum)

2. **`messages`** - Message engagement metrics
   - `patient_id` (FK to patients)
   - `direction` (inbound/outbound)
   - `status` (pending/sent/delivered/read/failed)
   - `created_at` (timestamp)

3. **`alerts`** - Alert severity counts
   - `patient_id` (FK to patients)
   - `severity` (low/medium/high/critical)
   - `status` (pending/active/acknowledged/resolved)

---

## API Usage

### cURL Example

```bash
curl -X GET "https://api.hormonia.com/api/v1/medico/dashboard-stats" \
  -H "Authorization: Bearer <FIREBASE_ID_TOKEN>" \
  -H "Accept: application/json"
```

### JavaScript (Fetch)

```javascript
const response = await fetch('/api/v1/medico/dashboard-stats', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`,
    'Accept': 'application/json'
  }
});

const stats = await response.json();
console.log('Active Patients:', stats.pacientes_ativos);
console.log('Unread Messages:', stats.engagement.messages_unread);
```

### Python (requests)

```python
import requests

headers = {
    'Authorization': f'Bearer {firebase_token}',
    'Accept': 'application/json'
}

response = requests.get(
    'https://api.hormonia.com/api/v1/medico/dashboard-stats',
    headers=headers
)

stats = response.json()
print(f"Active Patients: {stats['pacientes_ativos']}")
print(f"Critical Alerts: {stats['alerts']['critical']}")
```

---

## Frontend Integration

### React Component Example

```tsx
import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';

interface DashboardStats {
  pacientes_ativos: number;
  consultas_hoje: number;
  pendencias: number;
  exames_aguardando: number;
  engagement: {
    messages_today: number;
    messages_unread: number;
    response_rate: number;
    avg_response_time_minutes: number | null;
  };
  alerts: {
    total: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  timestamp: string;
}

export function useMedicoDashboardStats() {
  const { token } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/v1/medico/dashboard-stats', {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error('Failed to fetch dashboard stats');
        }

        const data = await response.json();
        setStats(data);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();

    // Refresh every 2 minutes (matches cache TTL)
    const interval = setInterval(fetchStats, 120000);
    return () => clearInterval(interval);
  }, [token]);

  return { stats, loading, error };
}

// Usage in MedicoDashboard component
export function MedicoDashboard() {
  const { stats, loading, error } = useMedicoDashboardStats();

  if (loading) return <Skeleton />;
  if (error) return <ErrorAlert message={error} />;
  if (!stats) return null;

  return (
    <div className="grid grid-cols-4 gap-4">
      <StatCard
        title="Pacientes Ativos"
        value={stats.pacientes_ativos}
        icon={<UsersIcon />}
      />
      <StatCard
        title="Consultas Hoje"
        value={stats.consultas_hoje}
        icon={<CalendarIcon />}
      />
      <StatCard
        title="Pendências"
        value={stats.pendencias}
        icon={<ClockIcon />}
        variant={stats.pendencias > 10 ? 'warning' : 'default'}
      />
      <StatCard
        title="Exames Aguardando"
        value={stats.exames_aguardando}
        icon={<FileTextIcon />}
      />

      <AlertsSummary alerts={stats.alerts} />
      <EngagementSummary engagement={stats.engagement} />
    </div>
  );
}
```

---

## Edge Cases

### New Doctor (No Data)

```json
{
  "pacientes_ativos": 0,
  "consultas_hoje": 0,
  "pendencias": 0,
  "exames_aguardando": 0,
  "engagement": {
    "messages_today": 0,
    "messages_unread": 0,
    "response_rate": 0.0,
    "avg_response_time_minutes": null
  },
  "alerts": {
    "total": 0,
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "timestamp": "2025-10-06T14:30:00Z"
}
```

### No Messages Today

```json
{
  "consultas_hoje": 0,
  "engagement": {
    "messages_today": 0,
    "messages_unread": 5,
    "response_rate": 0.0,
    "avg_response_time_minutes": null
  }
}
```

---

## Performance

### Query Optimization

- **Indexed Fields**: `doctor_id`, `created_at`, `status`, `severity`
- **Query Count**: 5 separate queries (could be optimized with CTEs)
- **Execution Time**:
  - Uncached: 50-100ms
  - Cached: ~5ms
- **Cache Strategy**: Redis with 2-minute TTL

### Recommendations

1. **Frontend Polling**: Fetch every 2-3 minutes to match cache TTL
2. **Loading States**: Show skeleton while loading
3. **Error Handling**: Display user-friendly error messages
4. **Real-time Updates**: Consider WebSocket for critical alerts

---

## Error Responses

### 401 Unauthorized

```json
{
  "error": "unauthorized",
  "message": "Could not validate credentials",
  "timestamp": "2025-10-06T14:30:00Z",
  "request_id": "req_abc123"
}
```

### 403 Forbidden

```json
{
  "error": "forbidden",
  "message": "Not enough permissions. Doctor role required.",
  "timestamp": "2025-10-06T14:30:00Z",
  "request_id": "req_abc123"
}
```

### 500 Internal Server Error

```json
{
  "error": "internal_server_error",
  "message": "Failed to retrieve dashboard statistics",
  "timestamp": "2025-10-06T14:30:00Z",
  "request_id": "req_abc123"
}
```

---

## Testing

### Unit Tests

Located in: `backend-hormonia/tests/test_medico_dashboard.py`

```bash
# Run medico dashboard tests
pytest tests/test_medico_dashboard.py -v

# Run with coverage
pytest tests/test_medico_dashboard.py --cov=app.services.medico_stats_service
```

### Manual Testing

```bash
# Get Firebase token (replace with your test user)
TOKEN=$(firebase login:ci)

# Test endpoint
curl -X GET "http://localhost:8000/api/v1/medico/dashboard-stats" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json" | jq
```

---

## Future Enhancements

1. **Exams Table Implementation**
   - Add `exames` table with `status` field
   - Update `get_exames_aguardando()` to query real data

2. **Message Threading**
   - Implement `thread_id` in messages table
   - Calculate accurate `avg_response_time_minutes`

3. **Appointments Table**
   - Create dedicated `appointments` table
   - Update `get_consultas_hoje()` to use real appointments

4. **Real-time Updates**
   - WebSocket notifications for critical alerts
   - Live dashboard updates without polling

5. **Historical Analytics**
   - Trend data (daily/weekly/monthly)
   - Comparison with previous periods
   - Performance benchmarks

---

## Related Documentation

- [Medico Dashboard Frontend](../frontend/MEDICO_DASHBOARD.md)
- [Authentication Guide](./AUTHENTICATION.md)
- [Redis Caching Strategy](./REDIS_CACHING.md)
- [Database Schema](../database/SCHEMA.md)

---

## Changelog

### v1.0.0 (2025-10-06)
- Initial implementation of dashboard stats endpoint
- Redis caching with 2-minute TTL
- Pydantic response models
- Comprehensive error handling
- Doctor role authentication requirement
