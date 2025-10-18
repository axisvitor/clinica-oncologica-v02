# API v2 Implementation Guide
## Sistema Hormonia - Sprint 4

**Version**: 2.0.0  
**Status**: ✅ Implemented  
**Last Updated**: January 17, 2025

---

## Overview

API v2 introduces modern REST API patterns with significant improvements over v1:

- **Cursor-based pagination** - Efficient for large datasets
- **Field selection** - Reduce payload size with sparse fieldsets
- **Eager loading** - Control relationship loading
- **Better performance** - Optimized queries and caching
- **Improved DX** - Better error messages and documentation

---

## Key Features

### 1. Cursor-Based Pagination

Instead of offset-based pagination (slow for large datasets), v2 uses cursor-based pagination:

```bash
# First page
GET /api/v2/patients?limit=20

# Response
{
  "data": [...],
  "next_cursor": "eyJpZCI6MTIzfQ==",
  "has_more": true,
  "total": 150
}

# Next page
GET /api/v2/patients?cursor=eyJpZCI6MTIzfQ==&limit=20
```

**Benefits**:
- Consistent performance regardless of page depth
- No duplicate/missing items when data changes
- Efficient database queries (uses indexed columns)

### 2. Field Selection

Request only the fields you need:

```bash
# Get only id, name, and email
GET /api/v2/patients?fields=id,name,email

# Response
{
  "data": [
    {
      "id": 123,
      "name": "João Silva",
      "email": "joao@example.com"
    }
  ]
}
```

**Benefits**:
- Reduced payload size (up to 70% smaller)
- Faster response times
- Lower bandwidth usage

### 3. Eager Loading

Control which relationships to include:

```bash
# Include doctor information
GET /api/v2/patients/123?include=doctor

# Response
{
  "id": 123,
  "name": "João Silva",
  "doctor": {
    "id": 1,
    "name": "Dr. Maria Santos",
    "crm": "12345-SP"
  }
}
```

**Benefits**:
- Avoid N+1 query problems
- Single request instead of multiple
- Controlled data loading

---

## Endpoints

### Patients

#### List Patients
```
GET /api/v2/patients
```

**Query Parameters**:
- `cursor` (string) - Pagination cursor
- `limit` (int, 1-100) - Items per page (default: 20)
- `fields` (string) - Comma-separated fields
- `include` (string) - Relations to include (doctor, quizzes)
- `search` (string) - Search by name or email
- `is_active` (boolean) - Filter by active status

**Example**:
```bash
curl -X GET "https://api.hormonia.com/api/v2/patients?limit=10&fields=id,name,email&include=doctor" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Patient
```
GET /api/v2/patients/{patient_id}
```

**Query Parameters**:
- `fields` (string) - Comma-separated fields
- `include` (string) - Relations to include

#### Create Patient
```
POST /api/v2/patients
```

**Body**:
```json
{
  "name": "João Silva",
  "email": "joao@example.com",
  "phone": "(11) 98765-4321",
  "birth_date": "1980-05-15T00:00:00Z",
  "cpf": "123.456.789-00",
  "doctor_id": 1
}
```

#### Update Patient
```
PATCH /api/v2/patients/{patient_id}
```

**Body** (partial update):
```json
{
  "phone": "(11) 91234-5678"
}
```

#### Delete Patient
```
DELETE /api/v2/patients/{patient_id}
```

Soft deletes the patient (sets `is_active=False`).

---

### Quiz

#### List Quizzes
```
GET /api/v2/quiz
```

**Query Parameters**:
- `cursor`, `limit`, `fields`, `include` (same as patients)
- `patient_id` (int) - Filter by patient
- `status` (string) - Filter by status
- `month` (int, 1-12) - Filter by month
- `year` (int) - Filter by year

**Example**:
```bash
curl -X GET "https://api.hormonia.com/api/v2/quiz?patient_id=123&status=completed" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Quiz
```
GET /api/v2/quiz/{quiz_id}
```

#### Create Quiz
```
POST /api/v2/quiz
```

**Body**:
```json
{
  "patient_id": 123,
  "month": 1,
  "year": 2025,
  "status": "pending",
  "template_id": 1
}
```

#### Update Quiz
```
PATCH /api/v2/quiz/{quiz_id}
```

**Body**:
```json
{
  "status": "completed",
  "responses": {
    "q1": "answer1",
    "q2": "answer2"
  },
  "completed_at": "2025-01-17T15:00:00Z"
}
```

#### Delete Quiz
```
DELETE /api/v2/quiz/{quiz_id}
```

---

### Analytics

#### Overview
```
GET /api/v2/analytics/overview
```

**Query Parameters**:
- `start_date` (datetime) - Start date for filtering
- `end_date` (datetime) - End date for filtering

**Response**:
```json
{
  "total_patients": 150,
  "total_quizzes": 450,
  "completed_quizzes": 380,
  "completion_rate": 84.44,
  "active_patients_30d": 120
}
```

#### Quiz Status Distribution
```
GET /api/v2/analytics/quiz-status
```

**Query Parameters**:
- `month` (int) - Filter by month
- `year` (int) - Filter by year

#### Completion Trend
```
GET /api/v2/analytics/completion-trend
```

**Query Parameters**:
- `months` (int, 1-24) - Number of months (default: 6)

#### Patient Engagement
```
GET /api/v2/analytics/patient-engagement
```

---

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "ValidationError",
  "message": "Invalid field selection",
  "details": {
    "fields": ["invalid_field"]
  },
  "request_id": "req_123abc"
}
```

**Common Error Codes**:
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (missing/invalid token)
- `404` - Not Found
- `409` - Conflict (duplicate resource)
- `422` - Validation Error
- `500` - Internal Server Error

---

## Performance Tips

### 1. Use Field Selection
```bash
# ❌ Bad - Returns all fields (large payload)
GET /api/v2/patients

# ✅ Good - Returns only needed fields
GET /api/v2/patients?fields=id,name,email
```

### 2. Use Cursor Pagination
```bash
# ❌ Bad - Slow for large offsets
GET /api/v1/patients?page=100&limit=20

# ✅ Good - Consistent performance
GET /api/v2/patients?cursor=eyJpZCI6MTk4MH0=&limit=20
```

### 3. Eager Load Relationships
```bash
# ❌ Bad - N+1 queries (1 + N requests)
GET /api/v2/patients
# Then for each patient:
GET /api/v2/doctors/{doctor_id}

# ✅ Good - Single request
GET /api/v2/patients?include=doctor
```

### 4. Use Appropriate Limits
```bash
# ❌ Bad - Too many items
GET /api/v2/patients?limit=100

# ✅ Good - Reasonable page size
GET /api/v2/patients?limit=20
```

---

## Migration from v1

### Pagination

**v1**:
```bash
GET /api/v1/patients?page=2&limit=20
```

**v2**:
```bash
# First page
GET /api/v2/patients?limit=20

# Next page (use cursor from response)
GET /api/v2/patients?cursor=eyJpZCI6MjB9&limit=20
```

### Field Selection

**v1**: Not supported (always returns all fields)

**v2**:
```bash
GET /api/v2/patients?fields=id,name,email
```

### Eager Loading

**v1**: Not supported (requires separate requests)

**v2**:
```bash
GET /api/v2/patients?include=doctor,quizzes
```

---

## Testing

Run v2 API tests:

```bash
# All v2 tests
pytest tests/api/v2/ -v

# Specific endpoint
pytest tests/api/v2/test_patients.py -v

# With coverage
pytest tests/api/v2/ --cov=app/api/v2 --cov-report=html
```

---

## OpenAPI Documentation

Access interactive API documentation:

- **Swagger UI**: `https://api.hormonia.com/docs`
- **ReDoc**: `https://api.hormonia.com/redoc`
- **OpenAPI JSON**: `https://api.hormonia.com/openapi.json`

Filter by v2 endpoints using the tag selector.

---

## Rate Limiting

API v2 includes rate limiting:

- **Default**: 100 requests/minute per user
- **Burst**: 20 requests/second

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642435200
```

---

## Versioning Policy

- **v1**: Maintained for 6 months (until July 2025)
- **v2**: Current stable version
- **Breaking changes**: New major version (v3)
- **Non-breaking changes**: Minor version updates

---

## Support

- **Documentation**: https://docs.hormonia.com/api/v2
- **Issues**: https://github.com/hormonia/backend/issues
- **Email**: api-support@hormonia.com

---

**Document Version**: 1.0  
**Created**: January 2025  
**Owner**: Backend Team
