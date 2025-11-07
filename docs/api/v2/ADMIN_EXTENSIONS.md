# Admin Extensions API v2 - Documentation

## Overview

The Admin Extensions API provides comprehensive administrative tools for **Dead Letter Queue (DLQ) management** and **Audit Log management**. These endpoints are critical for system monitoring, troubleshooting, and compliance (HIPAA, LGPD).

**Base Path**: `/api/v2/admin-extensions`

**Authentication**: Admin-only (requires `UserRole.ADMIN`)

**Features**:
- ✅ Dead Letter Queue management for failed operations
- ✅ Comprehensive audit logging for compliance
- ✅ Cursor-based pagination
- ✅ Redis caching with SHORT TTLs (2-10 minutes)
- ✅ Rate limiting (30-60 req/min)
- ✅ Field selection
- ✅ Export functionality (CSV, JSON)
- ✅ RBAC enforcement

---

## Table of Contents

1. [Dead Letter Queue (DLQ) Endpoints](#dead-letter-queue-dlq-endpoints)
2. [Audit Log Management Endpoints](#audit-log-management-endpoints)
3. [Authentication & Authorization](#authentication--authorization)
4. [Pagination](#pagination)
5. [Caching Strategy](#caching-strategy)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Examples](#examples)

---

## Dead Letter Queue (DLQ) Endpoints

The DLQ stores failed operations (messages, tasks) that couldn't be processed after multiple retry attempts.

### 1. List DLQ Items

**GET** `/admin-extensions/dlq`

Retrieve paginated list of DLQ items with comprehensive filters.

**Query Parameters**:
- `cursor` (string, optional): Pagination cursor
- `limit` (integer, optional): Items per page (1-100, default: 20)
- `fields` (string, optional): Comma-separated fields to include
- `status` (string, optional): Filter by status (pending, retry_scheduled, resolved, etc.)
- `error_code` (string, optional): Filter by error code
- `patient_id` (UUID, optional): Filter by patient
- `search` (string, optional): Search in error messages

**Response** (200 OK):
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "patient_id": "660e8400-e29b-41d4-a716-446655440000",
      "phone_number": "+5511999999999",
      "message_type": "appointment_reminder",
      "message_content": "Your appointment is tomorrow at 10 AM",
      "error_message": "Failed to deliver: Network timeout",
      "error_code": "TIMEOUT",
      "retry_count": 2,
      "max_retries": 5,
      "next_retry_at": "2025-01-17T16:00:00Z",
      "last_retry_at": "2025-01-17T15:00:00Z",
      "status": "retry_scheduled",
      "resolved_at": null,
      "dlq_metadata": {"category": "transient"},
      "created_at": "2025-01-17T14:00:00Z",
      "updated_at": "2025-01-17T15:00:00Z"
    }
  ],
  "next_cursor": "eyJpZCI6MTIzfQ==",
  "has_more": true,
  "total": null
}
```

**Cache**: 2 minutes TTL

**Rate Limit**: 60 requests/minute

---

### 2. Get DLQ Item

**GET** `/admin-extensions/dlq/{dlq_id}`

Retrieve detailed information about a specific DLQ item.

**Path Parameters**:
- `dlq_id` (UUID, required): DLQ item ID

**Query Parameters**:
- `fields` (string, optional): Comma-separated fields to include

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_id": "660e8400-e29b-41d4-a716-446655440000",
  "phone_number": "+5511999999999",
  "message_type": "appointment_reminder",
  "error_message": "Failed to deliver: Network timeout",
  "error_code": "TIMEOUT",
  "retry_count": 2,
  "max_retries": 5,
  "status": "retry_scheduled",
  "dlq_metadata": {"category": "transient", "source": "whatsapp"},
  "created_at": "2025-01-17T14:00:00Z"
}
```

**Cache**: 2 minutes TTL

---

### 3. Retry DLQ Item

**POST** `/admin-extensions/dlq/{dlq_id}/retry`

Manually retry a failed operation from the DLQ.

**Path Parameters**:
- `dlq_id` (UUID, required): DLQ item ID

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Message reprocessed successfully",
  "dlq_id": "550e8400-e29b-41d4-a716-446655440000",
  "error": null
}
```

**Rate Limit**: 30 requests/minute

**Note**: Invalidates DLQ caches on success.

---

### 4. Bulk Retry DLQ Items

**POST** `/admin-extensions/dlq/retry-bulk`

Retry multiple DLQ items at once (max 50).

**Request Body**:
```json
{
  "dlq_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "660e8400-e29b-41d4-a716-446655440001",
    "770e8400-e29b-41d4-a716-446655440002"
  ]
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "total_requested": 10,
  "successful": 9,
  "failed": 1,
  "errors": [
    {"dlq_id": "550e8400-e29b-41d4-a716-446655440000", "error": "Item not found"}
  ],
  "message": "Bulk retry completed: 9 successful, 1 failed"
}
```

**Rate Limit**: 10 requests/minute

**Validation**: Maximum 50 DLQ IDs per request.

---

### 5. Delete DLQ Item

**DELETE** `/admin-extensions/dlq/{dlq_id}`

Mark DLQ item as discarded (soft delete).

**Path Parameters**:
- `dlq_id` (UUID, required): DLQ item ID

**Query Parameters**:
- `reason` (string, required): Reason for deletion

**Response** (200 OK):
```json
{
  "success": true,
  "message": "DLQ item deleted successfully",
  "dlq_id": "550e8400-e29b-41d4-a716-446655440000",
  "error": null
}
```

**Rate Limit**: 30 requests/minute

---

### 6. Get DLQ Statistics

**GET** `/admin-extensions/dlq/stats`

Get comprehensive DLQ statistics.

**Response** (200 OK):
```json
{
  "total": 150,
  "pending": 20,
  "retry_scheduled": 30,
  "retrying": 5,
  "resolved": 80,
  "discarded": 10,
  "max_retries_exceeded": 5,
  "transient_errors_24h": 25,
  "permanent_errors_24h": 8,
  "unknown_errors_24h": 2,
  "retry_success_rate": 75.5,
  "top_errors": [
    {"error_code": "TIMEOUT", "count": 45},
    {"error_code": "INVALID_PHONE", "count": 15}
  ],
  "by_module": {
    "whatsapp": 100,
    "email": 30,
    "sms": 20
  }
}
```

**Cache**: 10 minutes TTL

---

### 7. Purge Old DLQ Items

**DELETE** `/admin-extensions/dlq/purge`

Purge DLQ items older than specified days (default: 90 days).

**⚠️ WARNING**: This is a destructive operation. Use `dry_run=true` first.

**Query Parameters**:
- `days` (integer, optional): Delete items older than this many days (30-365, default: 90)
- `dry_run` (boolean, optional): Preview without deleting (default: false)

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Would delete 45 DLQ items",
  "count": 45,
  "days": 90,
  "cutoff_date": "2024-10-17T00:00:00Z",
  "dry_run": true
}
```

**Rate Limit**: 5 requests/hour

**Safety**: Only purges items with status: `resolved`, `discarded`, or `max_retries_exceeded`.

---

## Audit Log Management Endpoints

Audit logs track all security-relevant events for compliance and forensic analysis.

### 8. List Audit Logs

**GET** `/admin-extensions/audit-logs`

Retrieve paginated list of audit logs with comprehensive filters.

**Query Parameters**:
- `cursor` (string, optional): Pagination cursor
- `limit` (integer, optional): Items per page (1-100, default: 20)
- `fields` (string, optional): Comma-separated fields to include
- `event_type` (string, optional): Filter by event type (login_success, admin_user_create, etc.)
- `event_status` (string, optional): Filter by status (success, failure, error)
- `user_id` (UUID, optional): Filter by user
- `user_email` (string, optional): Filter by user email
- `ip_address` (string, optional): Filter by IP address
- `start_date` (datetime, optional): Filter from date
- `end_date` (datetime, optional): Filter to date
- `search` (string, optional): Search in messages

**Response** (200 OK):
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "event_type": "login_success",
      "event_status": "success",
      "user_id": "660e8400-e29b-41d4-a716-446655440000",
      "user_email": "doctor@example.com",
      "firebase_uid": "firebase_uid_123",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0...",
      "resource": "/api/v2/auth/login",
      "action": "login",
      "event_metadata": {"device": "desktop"},
      "message": "User logged in successfully",
      "created_at": "2025-01-17T14:00:00Z"
    }
  ],
  "next_cursor": "eyJpZCI6MTIzfQ==",
  "has_more": true,
  "total": null
}
```

**Cache**: 5 minutes TTL

**Rate Limit**: 60 requests/minute

---

### 9. Get Audit Log

**GET** `/admin-extensions/audit-logs/{log_id}`

Retrieve detailed information about a specific audit log.

**Path Parameters**:
- `log_id` (UUID, required): Audit log ID

**Query Parameters**:
- `fields` (string, optional): Comma-separated fields to include
- `redact_sensitive` (boolean, optional): Redact sensitive data (default: true)

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "admin_user_create",
  "event_status": "success",
  "user_email": "admin@example.com",
  "ip_address": "192.168.1.100",
  "event_metadata": {
    "created_role": "doctor",
    "password": "[REDACTED]"
  },
  "created_at": "2025-01-17T14:00:00Z"
}
```

**Cache**: 15 minutes TTL

**Note**: Sensitive fields (password, token, secret, api_key) are automatically redacted when `redact_sensitive=true`.

---

### 10. Export Audit Logs

**POST** `/admin-extensions/audit-logs/export`

Export audit logs to CSV or JSON format with filters.

**⚠️ CRITICAL**: This exports sensitive compliance data. All exports are logged.

**Query Parameters** (filters):
- `event_type` (string, optional): Filter by event type
- `event_status` (string, optional): Filter by status
- `user_email` (string, optional): Filter by user email
- `start_date` (datetime, optional): Filter from date
- `end_date` (datetime, optional): Filter to date

**Request Body**:
```json
{
  "format": "csv",
  "fields": ["id", "event_type", "user_email", "ip_address", "created_at"],
  "redact_sensitive": true
}
```

**Response** (200 OK):
- **CSV**: `Content-Type: text/csv`
- **JSON**: `Content-Type: application/json`

**Example CSV**:
```csv
id,event_type,user_email,ip_address,created_at
550e8400-e29b-41d4-a716-446655440000,login_success,admin@example.com,192.168.1.100,2025-01-17T14:00:00Z
660e8400-e29b-41d4-a716-446655440001,admin_user_create,admin@example.com,192.168.1.100,2025-01-17T14:05:00Z
```

**Rate Limit**: 10 requests/hour

**Limit**: Maximum 10,000 audit logs per export.

---

## Authentication & Authorization

### Required Role

All Admin Extensions endpoints require **`UserRole.ADMIN`** access.

### Error Responses

**403 Forbidden**:
```json
{
  "detail": "Admin access required for Admin Extensions"
}
```

**401 Unauthorized**:
```json
{
  "detail": "Authentication required"
}
```

---

## Pagination

All list endpoints use **cursor-based pagination** for optimal performance.

### Cursor Format

Cursors are **base64-encoded JSON** containing pagination state:
```json
{"id": 123}
```

### Example Flow

```bash
# First page
GET /admin-extensions/dlq?limit=20
Response: { "next_cursor": "eyJpZCI6MjB9", "has_more": true }

# Second page
GET /admin-extensions/dlq?limit=20&cursor=eyJpZCI6MjB9
Response: { "next_cursor": "eyJpZCI6NDB9", "has_more": true }
```

### Benefits

- ✅ Consistent pagination (no missing/duplicate items)
- ✅ Efficient database queries (indexed lookups)
- ✅ No performance degradation on deep pages
- ❌ No total count (for performance)
- ❌ Cannot jump to arbitrary pages

---

## Caching Strategy

Admin Extensions use **Redis caching** with **SHORT TTLs** due to time-sensitive nature of data.

| Resource | TTL | Key Prefix |
|----------|-----|------------|
| DLQ Items List | 2 minutes | `admin_ext:dlq:list` |
| DLQ Item Detail | 2 minutes | `admin_ext:dlq:item:{id}` |
| DLQ Statistics | 10 minutes | `admin_ext:dlq:stats` |
| Audit Logs List | 5 minutes | `admin_ext:audit:list` |
| Audit Log Detail | 15 minutes | `admin_ext:audit:item:{id}` |

### Cache Invalidation

Caches are automatically invalidated on:
- ✅ DLQ retry/delete operations
- ✅ DLQ purge operations
- ✅ Audit log exports

---

## Error Handling

### Standard Error Responses

**400 Bad Request**:
```json
{
  "detail": "Invalid cursor format: {error}"
}
```

**404 Not Found**:
```json
{
  "detail": "DLQ item not found"
}
```

**422 Unprocessable Entity**:
```json
{
  "detail": [
    {
      "loc": ["query", "limit"],
      "msg": "ensure this value is less than or equal to 100",
      "type": "value_error.number.not_le"
    }
  ]
}
```

**500 Internal Server Error**:
```json
{
  "detail": "Error retrieving DLQ items"
}
```

---

## Rate Limiting

Rate limits protect system resources and prevent abuse.

| Endpoint | Rate Limit |
|----------|------------|
| List DLQ Items | 60/minute |
| Get DLQ Item | No limit (cached) |
| Retry DLQ Item | 30/minute |
| Bulk Retry DLQ Items | 10/minute |
| Delete DLQ Item | 30/minute |
| Purge DLQ Items | 5/hour |
| List Audit Logs | 60/minute |
| Export Audit Logs | 10/hour |

### Rate Limit Headers

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642425600
```

### Rate Limit Exceeded (429)

```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

---

## Examples

### Example 1: Monitor Failed Messages

```bash
# Get DLQ statistics
curl -X GET "https://api.example.com/api/v2/admin-extensions/dlq/stats" \
  -H "Authorization: Bearer {token}"

# List pending DLQ items
curl -X GET "https://api.example.com/api/v2/admin-extensions/dlq?status=pending&limit=50" \
  -H "Authorization: Bearer {token}"

# Retry a failed message
curl -X POST "https://api.example.com/api/v2/admin-extensions/dlq/{dlq_id}/retry" \
  -H "Authorization: Bearer {token}"
```

### Example 2: Audit Trail Investigation

```bash
# Search for failed logins
curl -X GET "https://api.example.com/api/v2/admin-extensions/audit-logs?event_type=login_failure&limit=100" \
  -H "Authorization: Bearer {token}"

# Export last 30 days of admin actions
curl -X POST "https://api.example.com/api/v2/admin-extensions/audit-logs/export?start_date=2025-01-01T00:00:00Z" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "csv",
    "fields": ["event_type", "user_email", "ip_address", "created_at"],
    "redact_sensitive": true
  }'
```

### Example 3: Bulk DLQ Cleanup

```bash
# Preview purge (dry run)
curl -X DELETE "https://api.example.com/api/v2/admin-extensions/dlq/purge?days=90&dry_run=true" \
  -H "Authorization: Bearer {token}"

# Execute purge
curl -X DELETE "https://api.example.com/api/v2/admin-extensions/dlq/purge?days=90&dry_run=false" \
  -H "Authorization: Bearer {token}"
```

### Example 4: Bulk Retry with Error Handling

```python
import requests

# Prepare bulk retry request
dlq_ids = ["uuid1", "uuid2", "uuid3", ...]
bulk_data = {"dlq_ids": dlq_ids}

response = requests.post(
    "https://api.example.com/api/v2/admin-extensions/dlq/retry-bulk",
    json=bulk_data,
    headers={"Authorization": f"Bearer {token}"}
)

result = response.json()

print(f"Successful: {result['successful']}")
print(f"Failed: {result['failed']}")

# Handle errors
for error in result['errors']:
    print(f"Failed to retry {error['dlq_id']}: {error['error']}")
```

---

## Compliance Notes

### HIPAA Compliance

- ✅ All audit logs are encrypted at rest
- ✅ Access is logged and monitored
- ✅ Sensitive data is automatically redacted
- ✅ Export operations are tracked
- ✅ Admin actions require authentication

### LGPD Compliance

- ✅ Personal data retention policies enforced (90-day default purge)
- ✅ Right to access (audit log retrieval)
- ✅ Right to erasure (DLQ purge)
- ✅ Data processing logs (audit trail)
- ✅ Security incident tracking (DLQ monitoring)

---

## Best Practices

1. **Monitor DLQ regularly**: Check statistics daily to identify systemic issues
2. **Use dry_run for purges**: Always preview purge operations before executing
3. **Export audit logs regularly**: Maintain offline backups for compliance
4. **Investigate failed logins**: Monitor `login_failure` events for security threats
5. **Set up alerts**: Configure monitoring for high DLQ counts or security events
6. **Batch retry operations**: Use bulk retry instead of individual retries
7. **Cache-aware queries**: Consider cache TTLs when polling for updates
8. **Rate limit awareness**: Implement exponential backoff for bulk operations

---

## Troubleshooting

### Issue: High DLQ Count

**Solution**:
1. Check DLQ statistics: `GET /admin-extensions/dlq/stats`
2. Identify top errors: Review `top_errors` field
3. Filter by error code: `GET /admin-extensions/dlq?error_code=TIMEOUT`
4. Investigate root cause (network issues, invalid data, etc.)
5. Retry transient errors: `POST /admin-extensions/dlq/retry-bulk`

### Issue: Audit Export Timeout

**Solution**:
1. Reduce date range
2. Export in smaller batches (use pagination)
3. Select fewer fields
4. Consider CSV format (more efficient than JSON)

### Issue: Rate Limit Exceeded

**Solution**:
1. Implement exponential backoff
2. Batch operations instead of individual requests
3. Use caching to reduce API calls
4. Contact support for rate limit increase if needed

---

## Migration from V1

### V1 → V2 Endpoint Mapping

| V1 Endpoint | V2 Endpoint |
|-------------|-------------|
| `/admin/dlq` | `/admin-extensions/dlq` |
| `/admin/dlq/{id}` | `/admin-extensions/dlq/{dlq_id}` |
| `/admin/dlq/{id}/retry` | `/admin-extensions/dlq/{dlq_id}/retry` |
| `/admin/audit/stats` | `/admin-extensions/dlq/stats` (enhanced) |
| N/A | `/admin-extensions/dlq/retry-bulk` (new) |
| N/A | `/admin-extensions/dlq/purge` (new) |
| N/A | `/admin-extensions/audit-logs` (new) |
| N/A | `/admin-extensions/audit-logs/export` (new) |

### Breaking Changes

1. **Pagination**: V1 used offset pagination, V2 uses cursor pagination
2. **Response format**: V2 uses standardized `CursorPaginatedResponse`
3. **Cache behavior**: V2 has shorter cache TTLs (time-sensitive data)
4. **Rate limiting**: V2 enforces stricter rate limits
5. **Field selection**: V2 supports sparse fieldsets via `?fields=`

---

## Support

For questions or issues:
- **API Documentation**: https://docs.example.com/api/v2
- **Support Email**: api-support@example.com
- **Status Page**: https://status.example.com

---

**Version**: 2.0.0
**Last Updated**: 2025-01-17
**Phase**: 9 (Admin Extensions Migration)
