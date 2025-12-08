# API Migration Guide: v2 → v3

**Version:** 1.0.0
**Last Updated:** 2025-01-16
**Sunset Date:** v2 will be sunset on **2025-07-01**

## Executive Summary

This guide helps you migrate from API v2 to v3. The migration timeline is **6 months** from announcement (January 2025) to sunset (July 2025).

### Why Migrate?

✅ **Better Performance**: v3 uses cursor-based pagination (faster for large datasets)
✅ **Standardized Errors**: Consistent error format across all endpoints
✅ **English Field Names**: More intuitive for international developers
✅ **HIPAA Compliance**: Enhanced security and audit features
✅ **Future-Proof**: v2 will be removed on July 1, 2025

### Migration Timeline

| Phase | Dates | Actions |
|-------|-------|---------|
| **Announce** | Jan - Mar 2025 | v3 available, v2 marked deprecated |
| **Warn** | Apr - Jun 2025 | Email reminders, usage tracking |
| **Sunset** | Jul 1, 2025 | v2 removed, returns 410 Gone |

---

## Breaking Changes

### 1. Base URL Change

**v2:**
```
https://api.clinica.com/api/v2/patients
```

**v3:**
```
https://api.clinica.com/api/v3/patients
```

**Migration:**
- Update all API endpoint URLs to use `/api/v3/` instead of `/api/v2/`
- Most SDKs allow setting a base URL in configuration

### 2. Error Response Format

**v2 Format:**
```json
{
  "error": "Patient not found"
}
```

**v3 Format:**
```json
{
  "error": {
    "code": "PATIENT_NOT_FOUND",
    "message": "Patient not found",
    "field": "patient_id"
  }
}
```

**Migration:**
- Update error parsing code to handle nested `error` object
- Use `error.code` for programmatic error handling
- Use `error.message` for user-facing messages
- Check `error.field` to identify which field caused validation errors

**Example (JavaScript):**
```javascript
// v2
if (response.error) {
  console.error(response.error);
}

// v3
if (response.error) {
  console.error(`[${response.error.code}] ${response.error.message}`);
  if (response.error.field) {
    console.error(`Problem with field: ${response.error.field}`);
  }
}
```

### 3. Patient Schema Changes

#### Field Renaming

| v2 Field | v3 Field | Notes |
|----------|----------|-------|
| `telefone` | `phone` | Now in English |
| `data_nascimento` | `date_of_birth` | Now in English |
| `endereco` | `address` | Now in English |

**v2 Example:**
```json
{
  "patient_id": "123",
  "nome": "João Silva",
  "cpf": "12345678901",
  "telefone": "+5511999999999",
  "data_nascimento": "1980-05-15"
}
```

**v3 Example:**
```json
{
  "patient_id": "123",
  "name": "João Silva",
  "cpf": "123.456.789-01",
  "phone": "+5511999999999",
  "date_of_birth": "1980-05-15"
}
```

#### CPF Formatting

**v2:** CPF returned as raw digits
```json
{
  "cpf": "12345678901"
}
```

**v3:** CPF includes formatting
```json
{
  "cpf": "123.456.789-01"
}
```

**Migration:**
- Update CPF parsing to handle formatted strings
- For comparisons, remove formatting: `cpf.replace(/[.-]/g, '')`

### 4. Pagination Changes

**v2: Offset-based pagination**
```http
GET /api/v2/patients?page=10&limit=50
```

**v3: Cursor-based pagination**
```http
GET /api/v3/patients?cursor=abc123&limit=50
```

**Response Format:**

**v2:**
```json
{
  "data": [...],
  "pagination": {
    "page": 10,
    "limit": 50,
    "total_pages": 100,
    "total_items": 5000
  }
}
```

**v3:**
```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "xyz789",
    "has_more": true,
    "limit": 50
  }
}
```

**Migration:**
- Replace `page` parameter with `cursor`
- Store `next_cursor` from response for next request
- Check `has_more` instead of calculating remaining pages
- Note: `total_items` not available in cursor-based pagination

**Example (JavaScript):**
```javascript
// v2
async function fetchAllPatients() {
  let page = 1;
  let allPatients = [];

  while (true) {
    const response = await fetch(`/api/v2/patients?page=${page}&limit=50`);
    const data = await response.json();

    allPatients.push(...data.data);

    if (page >= data.pagination.total_pages) break;
    page++;
  }

  return allPatients;
}

// v3
async function fetchAllPatients() {
  let cursor = null;
  let allPatients = [];

  while (true) {
    const url = cursor
      ? `/api/v3/patients?cursor=${cursor}&limit=50`
      : `/api/v3/patients?limit=50`;

    const response = await fetch(url);
    const data = await response.json();

    allPatients.push(...data.data);

    if (!data.pagination.has_more) break;
    cursor = data.pagination.next_cursor;
  }

  return allPatients;
}
```

### 5. Authentication Headers

**No change**, but v3 is stricter about validation.

Both versions use the same auth:
```http
Authorization: Bearer <token>
```

**New in v3:**
- Tokens are validated more strictly
- Expired tokens return 401 immediately (v2 sometimes returned 200 with stale data)
- Better error messages for auth failures

### 6. Date/Time Format

**v2:** Inconsistent date formats
```json
{
  "created_at": "2025-01-15 10:30:00",
  "updated_at": "15/01/2025"
}
```

**v3:** Always ISO 8601 with timezone
```json
{
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T14:20:00Z"
}
```

**Migration:**
- Parse all dates as ISO 8601
- Use standard libraries (e.g., `new Date()` in JavaScript, `datetime.fromisoformat()` in Python)

### 7. HTTP Status Codes

v3 uses more specific status codes:

| Scenario | v2 | v3 |
|----------|----|----|
| Success | 200 | 200 |
| Created | 200 | **201** |
| No Content | 200 | **204** |
| Bad Request | 400 | 400 |
| Unauthorized | 401 | 401 |
| Forbidden | 200 with error | **403** |
| Not Found | 200 with error | **404** |
| Conflict | 400 | **409** |
| Rate Limited | 200 with error | **429** |

**Migration:**
- Check for 2xx status codes instead of just 200
- Handle new error codes: 403, 404, 409, 429

---

## Non-Breaking Enhancements

These features are **new in v3** but don't require code changes:

✅ **New Fields**: v3 responses include additional fields (your code can ignore them)
✅ **Better Validation**: More helpful error messages
✅ **HIPAA Audit**: Enhanced logging (transparent to clients)
✅ **Performance**: Faster response times

---

## Step-by-Step Migration

### Step 1: Test v3 in Staging (Week 1)

1. Update base URL to v3 in your **staging** environment
2. Run your test suite
3. Fix any breaking changes (error parsing, pagination, field names)
4. Verify all critical workflows work

### Step 2: Gradual Production Rollout (Weeks 2-4)

**Option A: Feature Flag**
```javascript
const API_VERSION = process.env.API_VERSION || 'v2';
const BASE_URL = `https://api.clinica.com/api/${API_VERSION}`;
```

**Option B: Gradual Traffic Shift**
- Week 2: 10% of users on v3
- Week 3: 50% of users on v3
- Week 4: 100% of users on v3

### Step 3: Monitor for Issues (Week 4+)

Watch for:
- Increased error rates
- Failed requests
- User complaints

Dashboard: `https://grafana.clinica.com/d/api-versioning`

### Step 4: Cleanup (After full migration)

Remove v2-specific code:
```javascript
// Delete this
if (API_VERSION === 'v2') {
  // Old pagination logic
}
```

---

## Common Migration Issues

### Issue 1: CPF Validation Fails

**Problem:**
```javascript
// v2: Expects 11 digits
if (cpf.length !== 11) { /* error */ }

// v3: Returns formatted CPF (14 chars)
"123.456.789-01".length // 14, not 11
```

**Solution:**
```javascript
function normalizeCPF(cpf) {
  return cpf.replace(/[.-]/g, ''); // Remove formatting
}

if (normalizeCPF(cpf).length !== 11) { /* error */ }
```

### Issue 2: Pagination Loop Never Ends

**Problem:**
```javascript
// v2 logic doesn't work with v3
while (page < totalPages) { ... }
```

**Solution:**
```javascript
// Use has_more flag
while (data.pagination.has_more) {
  cursor = data.pagination.next_cursor;
  // fetch next page
}
```

### Issue 3: Error Handling Breaks

**Problem:**
```javascript
// v2: response.error is a string
if (response.error === "Patient not found") { ... }

// v3: response.error is an object
// Above comparison always false
```

**Solution:**
```javascript
// Use error.code for reliable comparisons
if (response.error?.code === "PATIENT_NOT_FOUND") { ... }
```

---

## SDK Examples

### JavaScript/TypeScript

```typescript
// v2
import { ClinicaAPI } from '@clinica/api-client';

const client = new ClinicaAPI({
  baseURL: 'https://api.clinica.com/api/v2',
  token: process.env.API_TOKEN
});

// v3
const client = new ClinicaAPI({
  baseURL: 'https://api.clinica.com/api/v3', // Only change
  token: process.env.API_TOKEN
});

// Update error handling
try {
  const patient = await client.patients.get(id);
} catch (error) {
  // v2
  console.error(error.message);

  // v3
  console.error(`[${error.code}] ${error.message}`);
  if (error.field) {
    console.error(`Field: ${error.field}`);
  }
}
```

### Python

```python
# v2
from clinica_api import ClinicaClient

client = ClinicaClient(
    base_url="https://api.clinica.com/api/v2",
    token=os.getenv("API_TOKEN")
)

# v3
client = ClinicaClient(
    base_url="https://api.clinica.com/api/v3",  # Only change
    token=os.getenv("API_TOKEN")
)

# Update error handling
try:
    patient = client.patients.get(patient_id)
except APIError as e:
    # v2
    print(f"Error: {e}")

    # v3
    print(f"[{e.code}] {e.message}")
    if e.field:
        print(f"Field: {e.field}")
```

---

## Testing Checklist

Use this checklist to verify your migration:

### Authentication
- [ ] Login still works
- [ ] Token refresh works
- [ ] Expired token returns 401 (not 200)

### Patient Management
- [ ] List patients (with pagination)
- [ ] Get patient by ID
- [ ] Create new patient
- [ ] Update patient
- [ ] Delete patient
- [ ] CPF formatting handled correctly

### Quiz/Forms
- [ ] Create quiz session
- [ ] Submit quiz responses
- [ ] Get quiz results

### Error Handling
- [ ] 404 errors parsed correctly
- [ ] Validation errors show field name
- [ ] Rate limiting detected (429)

### Pagination
- [ ] First page loads
- [ ] Next page loads using cursor
- [ ] Stop when `has_more` is false

---

## Getting Help

### Resources
- **API Documentation**: https://api.clinica.com/docs/v3
- **Migration Dashboard**: https://grafana.clinica.com/d/api-versioning
- **Status Page**: https://status.clinica.com

### Support Channels
- **Email**: api-support@clinica.com
- **Slack**: #api-migration
- **Office Hours**: Tuesdays 10am-12pm BRT

### Report Issues
- **GitHub**: https://github.com/clinica/api/issues
- **Priority Support**: For critical production issues, email support@clinica.com with "[API-CRITICAL]" in subject

---

## FAQ

### Q: Can I use both v2 and v3 simultaneously?

**A:** Yes! During the transition period (Jan-Jul 2025), you can have some clients on v2 and others on v3. This is useful for gradual rollout.

### Q: What happens if I don't migrate by July 1, 2025?

**A:** After July 1, 2025:
- All v2 endpoints will return **410 Gone**
- Your application will break
- You'll need to emergency-migrate to v3

**Recommendation:** Migrate well before the deadline to avoid last-minute issues.

### Q: Is there an automatic migration tool?

**A:** Not yet, but we're working on:
- Migration linter (detects v2 patterns in your code)
- Request translator proxy (translates v2 requests to v3)
- Contact api-support@clinica.com for early access

### Q: Will v3 also be deprecated eventually?

**A:** Yes, eventually. But we commit to:
- **Minimum 1 year** of support for each version
- **6 months notice** before deprecation
- **6 months migration period** after deprecation announced

v3 will be supported at least until **January 2026**.

### Q: Can I request a deadline extension?

**A:** Extensions are granted on a case-by-case basis for:
- Large enterprise clients
- Critical production systems
- Unforeseen technical blockers

Contact api-support@clinica.com with your situation.

### Q: Are there any performance differences?

**A:** Yes, v3 is faster:
- **20-30% faster response times** (cursor pagination)
- **Better caching** (standardized ETags)
- **Reduced payload size** (optimized field names)

---

## Appendix: Complete Field Mapping

### Patient Resource

| v2 Field | v3 Field | Type | Notes |
|----------|----------|------|-------|
| `patient_id` | `patient_id` | string | No change |
| `nome` | `name` | string | Renamed |
| `cpf` | `cpf` | string | Now formatted |
| `telefone` | `phone` | string | Renamed |
| `email` | `email` | string | No change |
| `data_nascimento` | `date_of_birth` | string | Renamed |
| `endereco` | `address` | object | Renamed |
| `created_at` | `created_at` | string | Now ISO 8601 |
| `updated_at` | `updated_at` | string | Now ISO 8601 |
| - | `timezone` | string | **New field** |

### Error Response

| v2 Field | v3 Field | Type | Notes |
|----------|----------|------|-------|
| `error` | `error.message` | string | Now nested |
| - | `error.code` | string | **New field** |
| - | `error.field` | string | **New field** |
| - | `error.details` | object | **New field** |

---

**Last Updated:** 2025-01-16
**Document Version:** 1.0.0
**Questions?** Email api-support@clinica.com
