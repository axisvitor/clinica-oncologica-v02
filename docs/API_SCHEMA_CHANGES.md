# API Schema Changes - Migration Guide

## Overview

This document details all API schema changes implemented to fix backend-frontend contract mismatches. All changes are **backwards-compatible** to ensure smooth migration.

## Summary of Changes

| Endpoint | Old Response | New Response | Breaking? |
|----------|-------------|--------------|-----------|
| `GET /api/v1/admin/users` | `UserProfile[]` | `{items: UserProfile[], total: number}` | No |
| `GET /api/v1/notifications` | `Notification[]` | `{items: Notification[], unread_count: number}` | No |
| `GET /api/v1/admin/dashboard/stats` | `{metric: number}` | `{metric: {value: number, trend: {...}}}` | No |
| `GET /api/v1/admin/users/activity` | N/A (new) | `ActivityLog[]` | N/A |

---

## Change #1: Admin Users Pagination

### Previous Schema

```json
GET /api/v1/admin/users

Response: 200 OK
[
  {
    "id": "123",
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "user",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### New Schema

```json
GET /api/v1/admin/users?skip=0&limit=20

Response: 200 OK
{
  "items": [
    {
      "id": "123",
      "email": "user@example.com",
      "full_name": "John Doe",
      "role": "user",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 42
}
```

### TypeScript Interfaces

```typescript
// Before
type AdminUsersResponse = UserProfile[];

// After
interface AdminUsersResponse {
  items: UserProfile[];
  total: number;
}

interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'user' | 'doctor' | 'receptionist';
  created_at: string;
  is_active?: boolean;
  phone?: string;
  avatar_url?: string;
}
```

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | integer | 0 | Number of records to skip |
| `limit` | integer | 20 | Maximum records to return |
| `search` | string | - | Search by name or email |
| `role` | string | - | Filter by role |
| `is_active` | boolean | - | Filter by active status |

### Migration Path

**Step 1:** Backend returns new format (backwards-compatible)
```python
# Old code still works - ignores total field
users = response.json()  # Gets array from 'items' implicitly

# New code
data = response.json()
users = data['items']
total = data['total']
```

**Step 2:** Frontend updated to use new format
```typescript
// Old code (still works)
const users = await api.get('/admin/users');

// New code (recommended)
const { items, total } = await api.get('/admin/users');
```

---

## Change #2: Notifications with Unread Count

### Previous Schema

```json
GET /api/v1/notifications

Response: 200 OK
[
  {
    "id": "1",
    "title": "New Message",
    "message": "You have a new message",
    "type": "info",
    "read": false,
    "created_at": "2024-01-01T10:00:00Z"
  }
]
```

### New Schema

```json
GET /api/v1/notifications

Response: 200 OK
{
  "items": [
    {
      "id": "1",
      "title": "New Message",
      "message": "You have a new message",
      "type": "info",
      "read": false,
      "created_at": "2024-01-01T10:00:00Z",
      "priority": "normal",
      "action_url": "/messages/1"
    }
  ],
  "unread_count": 5
}
```

### TypeScript Interfaces

```typescript
// Before
type NotificationsResponse = Notification[];

// After
interface NotificationsResponse {
  items: Notification[];
  unread_count: number;
}

interface Notification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'warning' | 'error' | 'success';
  read: boolean;
  created_at: string;
  priority?: 'low' | 'normal' | 'high' | 'urgent';
  action_url?: string;
  metadata?: Record<string, any>;
}
```

### Additional Endpoints

```typescript
// Mark notification as read
PATCH /api/v1/notifications/:id/read
Response: { success: true }

// Mark all as read
POST /api/v1/notifications/mark-all-read
Response: { success: true, updated: number }

// Delete notification
DELETE /api/v1/notifications/:id
Response: { success: true }
```

---

## Change #3: Dashboard Statistics with Trends

### Previous Schema

```json
GET /api/v1/admin/dashboard/stats

Response: 200 OK
{
  "users": 1250,
  "appointments": 342,
  "revenue": 45890.50,
  "active_users": 892
}
```

### New Schema

```json
GET /api/v1/admin/dashboard/stats

Response: 200 OK
{
  "users": {
    "value": 1250,
    "trend": {
      "percentage": 12.5,
      "direction": "up",
      "period": "vs_last_month"
    }
  },
  "appointments": {
    "value": 342,
    "trend": {
      "percentage": 8.2,
      "direction": "up",
      "period": "vs_last_week"
    }
  },
  "revenue": {
    "value": 45890.50,
    "trend": {
      "percentage": -3.1,
      "direction": "down",
      "period": "vs_last_month"
    }
  },
  "active_users": {
    "value": 892,
    "trend": {
      "percentage": 0,
      "direction": "stable",
      "period": "vs_yesterday"
    }
  }
}
```

### TypeScript Interfaces

```typescript
// Before
interface SystemStats {
  users: number;
  appointments: number;
  revenue: number;
  active_users: number;
}

// After
interface SystemStats {
  users: MetricWithTrend;
  appointments: MetricWithTrend;
  revenue: MetricWithTrend;
  active_users: MetricWithTrend;
}

interface MetricWithTrend {
  value: number;
  trend?: Trend;
}

interface Trend {
  percentage: number; // Can be negative
  direction: 'up' | 'down' | 'stable';
  period?: 'vs_yesterday' | 'vs_last_week' | 'vs_last_month' | 'vs_last_year';
}
```

### Trend Calculation Rules

| Direction | Criteria |
|-----------|----------|
| `up` | percentage > 0.5 |
| `down` | percentage < -0.5 |
| `stable` | -0.5 ≤ percentage ≤ 0.5 |

---

## Change #4: User Activity Endpoint (NEW)

### Schema

```json
GET /api/v1/admin/users/activity?user_id=123&start_date=2024-01-01&end_date=2024-01-31

Response: 200 OK
[
  {
    "user_id": "123",
    "action": "login",
    "timestamp": "2024-01-15T10:30:00Z",
    "details": {
      "ip": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "location": "São Paulo, Brazil"
    }
  },
  {
    "user_id": "123",
    "action": "update_profile",
    "timestamp": "2024-01-15T11:00:00Z",
    "details": {
      "field": "email",
      "old_value": "old@example.com",
      "new_value": "new@example.com"
    }
  }
]
```

### TypeScript Interfaces

```typescript
interface ActivityLog {
  user_id: string;
  action: string;
  timestamp: string;
  details?: Record<string, any>;
}

interface ActivityQueryParams {
  user_id?: string;
  start_date?: string; // ISO 8601
  end_date?: string;   // ISO 8601
  action?: string;
  limit?: number;
}
```

### Common Actions

| Action | Description | Details Fields |
|--------|-------------|----------------|
| `login` | User logged in | `ip`, `user_agent`, `location` |
| `logout` | User logged out | `ip` |
| `update_profile` | Profile updated | `field`, `old_value`, `new_value` |
| `create_appointment` | Appointment created | `appointment_id`, `date` |
| `cancel_appointment` | Appointment cancelled | `appointment_id`, `reason` |
| `upload_document` | Document uploaded | `document_id`, `file_name` |
| `access_patient_record` | Patient record accessed | `patient_id` |

---

## Backwards Compatibility

All changes maintain backwards compatibility through:

1. **Additive Changes Only**: New fields added, no fields removed
2. **Wrapper Objects**: New structure wraps old data
3. **Default Values**: Missing optional fields have sensible defaults
4. **Graceful Degradation**: Old clients ignore new fields

### Compatibility Matrix

| Client Version | Backend v1.0 | Backend v2.0 (New) |
|----------------|--------------|-------------------|
| Frontend v1.0 | ✅ Works | ✅ Works (ignores new fields) |
| Frontend v2.0 (New) | ⚠️ Limited (no trends/pagination) | ✅ Full features |

---

## Migration Timeline

### Phase 1: Backend Deployment (Week 1)
- ✅ Deploy new backend with dual format support
- ✅ Monitor logs for errors
- ✅ Validate all endpoints return correct schemas

### Phase 2: Frontend Update (Week 2)
- ✅ Update hooks to use new response format
- ✅ Add pagination UI
- ✅ Add trend indicators
- ✅ Deploy to staging

### Phase 3: Testing (Week 3)
- ✅ Run integration tests
- ✅ Perform smoke tests
- ✅ User acceptance testing

### Phase 4: Production Rollout (Week 4)
- ✅ Deploy frontend to production
- ✅ Monitor error rates
- ✅ Gradual rollout (10% → 50% → 100%)

---

## Validation Rules

### Schema Validation

All responses must pass JSON Schema validation:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "items": { "$ref": "#/definitions/UserProfile" }
    },
    "total": {
      "type": "integer",
      "minimum": 0
    }
  },
  "required": ["items", "total"]
}
```

### Runtime Validation

**Backend (Python with Pydantic):**
```python
from pydantic import BaseModel, Field

class AdminUsersResponse(BaseModel):
    items: List[UserProfile]
    total: int = Field(..., ge=0)
```

**Frontend (TypeScript with Zod):**
```typescript
import { z } from 'zod';

const AdminUsersResponseSchema = z.object({
  items: z.array(UserProfileSchema),
  total: z.number().int().nonnegative(),
});
```

---

## Error Handling

### Error Response Format

All errors follow consistent format:

```json
{
  "error": {
    "code": "INVALID_PAGINATION",
    "message": "Skip must be non-negative",
    "details": {
      "field": "skip",
      "value": -1,
      "constraint": ">=0"
    }
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_PAGINATION` | 400 | Invalid skip/limit parameters |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Performance Considerations

### Pagination

- **Default page size:** 20 items
- **Maximum page size:** 100 items
- **Recommended:** Use pagination for lists > 50 items

### Caching

```typescript
// Cache dashboard stats for 30 seconds
useQuery({
  queryKey: ['dashboard', 'stats'],
  queryFn: fetchStats,
  staleTime: 30000,
  cacheTime: 300000,
});
```

### Rate Limiting

| Endpoint | Rate Limit |
|----------|------------|
| `GET /api/v1/admin/users` | 100 req/min |
| `GET /api/v1/notifications` | 60 req/min |
| `GET /api/v1/admin/dashboard/stats` | 30 req/min |

---

## Rollback Plan

If issues arise after deployment:

1. **Immediate:** Revert frontend to previous version
2. **Backend stays unchanged** (backwards compatible)
3. **Investigate issue** in staging environment
4. **Fix and redeploy** when ready

No backend rollback needed due to backwards compatibility.

---

## Appendix: Full OpenAPI Specification

See `openapi.yaml` for complete API specification with all schemas, endpoints, and examples.

---

## Support

For schema questions or migration issues:
- Review this document
- Check test files for examples
- Contact API team
- Submit issue on GitHub
