# Wave 2 API - Quick Reference Guide

**Version**: 1.0.0 | **Date**: 2025-10-06

---

## Quick Links

- **Full API Documentation**: [API_WAVE_2_ENDPOINTS.md](./API_WAVE_2_ENDPOINTS.md)
- **TypeScript Types**: [typescript-types-wave2.ts](./typescript-types-wave2.ts)
- **Implementation Spec**: [WAVE_2_ENDPOINTS_SPECIFICATION.md](./WAVE_2_ENDPOINTS_SPECIFICATION.md)
- **Summary**: [WAVE_2_API_DOCUMENTATION_SUMMARY.md](./WAVE_2_API_DOCUMENTATION_SUMMARY.md)

---

## 4 New Endpoints

### 1. Admin System Stats

```bash
GET /api/v1/admin/system-stats
Authorization: Bearer <token>
Role: admin, super_admin
Cache: 30 seconds
```

**Returns**: CPU, memory, disk, user counts, database metrics, service status

**Use Case**: Admin dashboard real-time monitoring

---

### 2. Treatment Distribution

```bash
GET /api/v1/analytics/treatment-distribution?period=30d
Authorization: Bearer <token>
Role: Any authenticated
Cache: 5 minutes
```

**Query Params**:
- `period`: `7d` | `30d` | `90d` | `all` (default: `30d`)
- `doctor_id`: UUID (admin only)

**Returns**: Treatment types with counts, percentages, colors, trends

**Use Case**: Analytics charts showing treatment breakdown

---

### 3. Physician Risk Assessments

```bash
GET /api/v1/physician/risk-assessments?risk_level=high&limit=20
Authorization: Bearer <token>
Role: physician, doctor, admin
Cache: 1 minute
```

**Query Params**:
- `patient_id`: UUID (optional)
- `risk_level`: `low` | `medium` | `high` | `critical` (optional)
- `limit`: 1-100 (default: `20`)

**Returns**: Patient risk data with alerts and summary

**Use Case**: Physician dashboard patient monitoring

**Performance**: 98% reduction in API calls (51 → 1), 10-15x faster

---

### 4. Medico Dashboard Stats

```bash
GET /api/v1/medico/dashboard-stats
Authorization: Bearer <token>
Role: medico, doctor
Cache: 2 minutes
```

**Returns**: Overview, patient breakdown, engagement, alerts, activity

**Use Case**: Doctor dashboard overview

---

## TypeScript Import

```typescript
import {
  // Response types
  SystemStatsResponse,
  TreatmentDistributionResponse,
  RiskAssessmentsResponse,
  MedicoDashboardStatsResponse,

  // Request params
  TreatmentDistributionParams,
  RiskAssessmentsParams,

  // Error types
  ApiErrorResponse,

  // Type guards
  isApiError,

  // Constants
  ENDPOINTS,
  CACHE_TTL
} from './typescript-types-wave2'
```

---

## React Query Hooks

### useSystemStats

```typescript
import { useSystemStats } from '@/hooks/useSystemStats'

function AdminDashboard() {
  const { data, isLoading, error } = useSystemStats()

  return (
    <div>
      <p>CPU: {data?.system_health.cpu_percent}%</p>
      <p>Users: {data?.active_users.total}</p>
    </div>
  )
}
```

### useTreatmentDistribution

```typescript
import { useTreatmentDistribution } from '@/hooks/useTreatmentDistribution'

function TreatmentChart({ period = '30d' }) {
  const { data } = useTreatmentDistribution(period)

  return (
    <PieChart data={data?.distribution} />
  )
}
```

### useRiskAssessments

```typescript
import { useRiskAssessments } from '@/hooks/useRiskAssessments'

function PhysicianDashboard() {
  const { data } = useRiskAssessments(undefined, 'high', 50)

  return (
    <table>
      {data?.assessments.map(assessment => (
        <tr key={assessment.patient_id}>
          <td>{assessment.patient_name}</td>
          <td>{assessment.risk_score}</td>
        </tr>
      ))}
    </table>
  )
}
```

### useMedicoDashboardStats

```typescript
import { useMedicoDashboardStats } from '@/hooks/useMedicoDashboardStats'

function MedicoDashboard() {
  const { data } = useMedicoDashboardStats()

  return (
    <div>
      <StatCard label="Pacientes" value={data?.overview.total_patients} />
      <StatCard label="Pendências" value={data?.overview.pending_reviews} />
    </div>
  )
}
```

---

## Error Handling

```typescript
const { data, error } = useSystemStats()

if (error) {
  if (isApiError(error)) {
    switch (error.error_code) {
      case 'UNAUTHORIZED':
        // Redirect to login
        break
      case 'FORBIDDEN':
        // Show access denied message
        break
      case 'RATE_LIMIT_EXCEEDED':
        // Show rate limit message
        break
    }
  }
}
```

---

## Response Time Targets

| Endpoint | p95 | p99 |
|----------|-----|-----|
| Admin system stats | 100ms | 200ms |
| Treatment distribution | 150ms | 300ms |
| Risk assessments | 200ms | 400ms |
| Medico dashboard | 100ms | 250ms |

---

## Cache TTLs

| Endpoint | TTL |
|----------|-----|
| Admin system stats | 30 seconds |
| Treatment distribution | 5 minutes |
| Risk assessments | 1 minute |
| Medico dashboard | 2 minutes |

---

## Rate Limits

- **Admin endpoints**: 100 requests/minute
- **Analytics endpoints**: 50 requests/minute
- **User endpoints**: 200 requests/minute

---

## Common Error Codes

| Code | Status | Meaning |
|------|--------|---------|
| `UNAUTHORIZED` | 401 | Invalid token |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 422 | Invalid parameters |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Example: Complete Component

```tsx
import { useMedicoDashboardStats } from '@/hooks/useMedicoDashboardStats'
import { isApiError } from './typescript-types-wave2'

function MedicoDashboard() {
  const { data, isLoading, error } = useMedicoDashboardStats()

  if (isLoading) {
    return <DashboardSkeleton />
  }

  if (error) {
    if (isApiError(error)) {
      return (
        <ErrorState
          title="Erro ao carregar dashboard"
          message={error.detail}
          code={error.error_code}
        />
      )
    }
    return <ErrorState title="Erro desconhecido" />
  }

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="Total Pacientes"
          value={data.overview.total_patients}
          icon="users"
        />
        <MetricCard
          label="Tratamentos Ativos"
          value={data.overview.active_treatments}
          icon="activity"
        />
        <MetricCard
          label="Pendências"
          value={data.overview.pending_reviews}
          icon="alert-circle"
          status={data.overview.pending_reviews > 0 ? 'warning' : 'normal'}
        />
        <MetricCard
          label="Alertas Hoje"
          value={data.overview.new_alerts_today}
          icon="bell"
        />
      </div>

      {/* Engagement Metrics */}
      <div className="grid grid-cols-3 gap-4">
        <MetricCard
          label="Mensagens Hoje"
          value={data.engagement_metrics.messages_today}
          icon="message-square"
        />
        <MetricCard
          label="Taxa de Resposta (7d)"
          value={`${data.engagement_metrics.response_rate_7d.toFixed(1)}%`}
          icon="trending-up"
        />
        <MetricCard
          label="Tempo Médio de Resposta"
          value={`${data.engagement_metrics.avg_response_time_hours.toFixed(1)}h`}
          icon="clock"
        />
      </div>

      {/* Alerts Summary */}
      <AlertsSummaryCard
        unacknowledged={data.alerts_summary.unacknowledged}
        bySeverity={data.alerts_summary.by_severity}
      />

      {/* Treatment Distribution */}
      <TreatmentBreakdownChart
        data={data.patient_breakdown.by_treatment_type}
      />

      {/* Recent Activity Feed */}
      <RecentActivityFeed
        activities={data.recent_activity}
      />
    </div>
  )
}
```

---

## Testing

### Backend Unit Test

```python
def test_medico_dashboard_stats(client, doctor_token):
    response = client.get(
        "/api/v1/medico/dashboard-stats",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "overview" in data
    assert "engagement_metrics" in data
    assert data["overview"]["total_patients"] >= 0
```

### Frontend Component Test

```typescript
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import MedicoDashboard from './MedicoDashboard'

test('renders dashboard stats', async () => {
  const queryClient = new QueryClient()

  render(
    <QueryClientProvider client={queryClient}>
      <MedicoDashboard />
    </QueryClientProvider>
  )

  expect(await screen.findByText('Total Pacientes')).toBeInTheDocument()
  expect(await screen.findByText('Tratamentos Ativos')).toBeInTheDocument()
})
```

---

## Performance Monitoring

### Prometheus Metrics

```
# Response time
http_request_duration_seconds{endpoint="/api/v1/medico/dashboard-stats"}

# Request count
http_requests_total{endpoint="/api/v1/medico/dashboard-stats"}

# Cache hit rate
cache_hit_rate{endpoint="/api/v1/medico/dashboard-stats"}

# Error rate
http_errors_total{endpoint="/api/v1/medico/dashboard-stats"}
```

### Grafana Queries

```promql
# p95 response time
histogram_quantile(0.95, http_request_duration_seconds_bucket{endpoint="/api/v1/medico/dashboard-stats"})

# Request rate
rate(http_requests_total{endpoint="/api/v1/medico/dashboard-stats"}[5m])

# Error rate
rate(http_errors_total{endpoint="/api/v1/medico/dashboard-stats"}[5m]) / rate(http_requests_total{endpoint="/api/v1/medico/dashboard-stats"}[5m])
```

---

## Deployment Checklist

### Backend

- [ ] Implement 4 endpoint handlers
- [ ] Configure Redis caching
- [ ] Set up rate limiting
- [ ] Add Prometheus metrics
- [ ] Configure CORS
- [ ] Test authentication
- [ ] Load test (100+ requests)

### Frontend

- [ ] Install React Query
- [ ] Copy TypeScript types
- [ ] Implement 4 hooks
- [ ] Update dashboard components
- [ ] Add loading states
- [ ] Add error handling
- [ ] Test integration

### Production

- [ ] Deploy to staging
- [ ] Run smoke tests
- [ ] Monitor metrics
- [ ] Deploy to production
- [ ] Verify cache hit rates
- [ ] Monitor error rates

---

## Support

**Email**: api-support@hormonia.com
**Slack**: #api-support
**Documentation**: https://docs.hormonia.com/api

---

**Last Updated**: 2025-10-06
**Version**: 1.0.0
